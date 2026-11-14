import base64
import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from datetime import date as Date

from .stats.readiness import score_readiness
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import membership
from .calendar import calendar_state
from .questionnaire import skeleton, validate_questionnaire
from .stats.engine import analyze, library
from .stats.performance import performance
from .store import AiQuotaError, InviteError, ReadOnlyError, Store, timestamp
from .validation import Reject, validate_plan

ROOT = Path(__file__).resolve().parents[2]
OPEN_ACCOUNT = {'id': None, 'username': None, 'tier': 'ultra'}


class LoginInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class RegisterInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=200)
    invite_code: str = Field(min_length=1, max_length=64)


class RedeemInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1, max_length=64)


class LogInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    cycle_id: str = Field(min_length=1)
    week: StrictInt = Field(ge=1)
    day: str = Field(min_length=1)
    seq: StrictInt = Field(ge=1)
    load: float | None = Field(ge=0)
    sets: StrictInt = Field(ge=0)
    reps: StrictInt = Field(ge=0)
    rpe: float | None = Field(ge=5.5, le=10)
    note: str = Field(default='', max_length=2000)


class DatedInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    cycle_id: str = Field(min_length=1)
    date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')

    @field_validator('date')
    @classmethod
    def valid_date(cls, value):
        Date.fromisoformat(value)
        return value


class ReadinessInput(DatedInput):
    session_id: str = Field(min_length=1, max_length=100)
    recovery: StrictInt | None = Field(default=None, ge=1, le=7)
    arousal: StrictInt | None = Field(default=None, ge=1, le=7)
    nutrition: StrictInt | None = Field(default=None, ge=1, le=7)
    hrv: float | None = Field(default=None, gt=0)
    rhr: float | None = Field(default=None, gt=0)
    sleep_score: float | None = Field(default=None, ge=0, le=100)
    session_time: str | None = Field(default=None, pattern=r'^(?:[01]\d|2[0-3]):[0-5]\d$')
    joint_pain: bool = False
    note: str = Field(default='', max_length=2000)


class Measurements(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    waist: float | None = Field(default=None, gt=0)
    chest: float | None = Field(default=None, gt=0)
    hips: float | None = Field(default=None, gt=0)
    upper_arm: float | None = Field(default=None, gt=0)
    thigh: float | None = Field(default=None, gt=0)
    calf: float | None = Field(default=None, gt=0)


class MetricsInput(DatedInput):
    bodyweight: float | None = Field(default=None, gt=0)
    bodyfat: float | None = Field(default=None, ge=0, le=100)
    measurements: Measurements = Field(default_factory=Measurements)


class PrescriptionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)
    cycle_id: str = Field(min_length=1)
    current_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    references: dict[str, float | None]


class ApplyPrescription(PrescriptionInput):
    preview_id: str = Field(pattern=r'^[a-f0-9]{64}$')


class PlanImportInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    plan_json: str = Field(min_length=1, max_length=2_000_000)
    filename: str = Field(min_length=1, max_length=255)

    @field_validator('plan_json')
    @classmethod
    def upload_size(cls, value):
        try:
            size = len(value.encode('utf-8'))
        except UnicodeEncodeError as exc:
            raise ValueError('Plan file must be valid UTF-8 text') from exc
        if size > 2_000_000:
            raise ValueError('Plan file must be at most 2 MB')
        return value


class ConfirmPlanImport(PlanImportInput):
    current_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    candidate_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm: bool

    @field_validator('confirm')
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError('Explicit confirmation is required')
        return value


class RestorePrescription(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    cycle_id: str = Field(min_length=1)
    current_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    revision_id: str = Field(pattern=r'^[a-f0-9]{64}$')


class QuestionnaireInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    cycle_id: str = Field(min_length=1)
    status: Literal['draft', 'complete']
    payload: dict


def create_app(db_path=None, plan_path=None):
    store = Store(db_path or os.environ.get('RR_DB_PATH', ROOT / 'data' / 'roastraw.sqlite3'))
    access_password = os.environ.get('RR_ACCESS_PASSWORD', '')
    access_username = os.environ.get('RR_ACCESS_USERNAME', '')

    @asynccontextmanager
    async def lifespan(app):
        seed = json.loads(Path(plan_path or ROOT / 'data' / 'plan.json').read_text(encoding='utf-8'))
        validate_plan(seed)
        store.initialize(seed)
        store.upgrade()
        store.upgrade_prescriptions()
        store.upgrade_questionnaire()
        store.upgrade_ai()
        store.upgrade_accounts()
        store.upgrade_membership()
        store.seed_owner(access_username, access_password)
        yield

    package_version = json.loads((ROOT / 'web/package.json').read_text(encoding='utf-8'))['version']
    version_parts = package_version.split('.')
    release_version = f'{version_parts[0]}.{int(version_parts[2]):02d}'
    app = FastAPI(title='Roast Raw', version=package_version, lifespan=lifespan)
    app.state.store = store
    allowed_hosts = ['127.0.0.1', 'localhost', 'testserver']
    allowed_hosts += [host.strip() for host in os.environ.get('RR_ALLOWED_HOSTS', '').split(',') if host.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    public_api = {'/api/health', '/api/login', '/api/register', '/api/logout', '/api/session'}

    def basic_account(request):
        header = request.headers.get('authorization', '')
        if not header.lower().startswith('basic '):
            return None
        try:
            decoded = base64.b64decode(header[6:], validate=True).decode('utf-8')
        except (ValueError, UnicodeDecodeError):
            return None
        user, _, pwd = decoded.partition(':')
        verified = store.verify_account(user, pwd)
        return store.account(verified['id']) if verified else None

    @app.middleware('http')
    async def access_gate(request, call_next):
        path = request.url.path
        request.state.account = None
        if path.startswith('/api/'):
            request.state.account = store.session_account(request.cookies.get('rr_session')) or basic_account(request)
            if request.state.account is None and not access_password:
                request.state.account = dict(OPEN_ACCOUNT)
        if path.startswith('/api/') and path not in public_api and request.state.account is None:
            return JSONResponse(status_code=401, content={'error': 'Authentication required.'},
                                headers={'WWW-Authenticate': 'Basic realm="Roast Raw"'})
        return await call_next(request)

    @app.exception_handler(Reject)
    async def rejected(request, error):
        return JSONResponse(status_code=422, content={'error': 'Plan rejected. No data changed.', 'errors': error.errors})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        body = error.body if isinstance(error.body, dict) else {}
        errors = [{'file': body.get('filename', 'request'), 'week': body.get('week') if type(body.get('week')) is int else None,
                   'day': body.get('day') if isinstance(body.get('day'), str) else None,
                   'movement': body.get('seq') if type(body.get('seq')) is int else None,
                   'field': '.'.join(map(str, item['loc'])),
                   'expected': item['msg']} for item in error.errors()]
        return JSONResponse(status_code=422, content={'error': 'Invalid request. No data changed.', 'errors': errors})

    def active_plan(cycle_id=None):
        plan = store.plan(cycle_id)
        if plan is None:
            raise HTTPException(404, 'Cycle not found')
        return plan

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'version': release_version, 'timezone': 'Asia/Shanghai', 'storage': 'SQLite'}

    def membership_view(account):
        view = {'tier': account['tier'], 'capabilities': membership.capabilities(account['tier'])}
        if account.get('id') is not None:
            view.update({'base_tier': account['base_tier'], 'timed_tier': account['timed_tier'],
                         'timed_until': account['timed_until'], 'device_limit': membership.DEVICE_LIMIT})
        return view

    @app.get('/api/session')
    def session_status(request: Request):
        account = request.state.account
        if account is None:
            return {'authenticated': False, 'username': None, 'gate': True}
        return {'authenticated': True, 'username': account['username'], 'gate': bool(access_password), **membership_view(account)}

    def _session_response(account, request):
        response = JSONResponse(content={'ok': True, 'username': account['username'], **membership_view(account)})
        response.set_cookie('rr_session', store.create_session(account['id'], request.headers.get('user-agent', '')),
                            max_age=store.SESSION_DAYS * 86400, httponly=True, samesite='lax', path='/')
        return response

    @app.post('/api/login')
    def login(payload: LoginInput, request: Request):
        verified = store.verify_account(payload.username, payload.password)
        if verified is None:
            return JSONResponse(status_code=401, content={'error': 'Invalid username or password.'})
        return _session_response(store.account(verified['id']), request)

    @app.post('/api/register')
    def register(payload: RegisterInput, request: Request):
        username = payload.username.strip()
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{1,63}', username):
            return JSONResponse(status_code=422, content={'error': 'Username must start with a letter and use only letters, numbers, underscores or hyphens (2–64 characters).'})
        try:
            account = store.register_with_invite(username, payload.password, payload.invite_code)
        except InviteError as exc:
            return JSONResponse(status_code=422, content={'error': str(exc)})
        except ValueError as exc:
            return JSONResponse(status_code=409, content={'error': str(exc)})
        return _session_response(account, request)

    @app.post('/api/logout')
    def logout(request: Request):
        store.delete_session(request.cookies.get('rr_session'))
        response = JSONResponse(content={'ok': True})
        response.delete_cookie('rr_session', path='/')
        return response

    def signed_in(request):
        account = request.state.account
        if account is None or account.get('id') is None:
            raise HTTPException(409, 'Sign-in is off on this server, so there is no account to change.')
        return account

    @app.post('/api/membership/redeem')
    def redeem(payload: RedeemInput, request: Request):
        account = signed_in(request)
        try:
            result = store.redeem(account['id'], payload.code)
        except InviteError as exc:
            return JSONResponse(status_code=422, content={'error': str(exc)})
        message = ('Code redeemed. Your membership is updated.' if result['changed']
                   else 'This account already has that tier or higher. The code was not used.')
        return {'changed': result['changed'], 'message': message, **membership_view(result['account'])}

    @app.get('/api/membership/sessions')
    def membership_sessions(request: Request):
        account = signed_in(request)
        return {'limit': membership.DEVICE_LIMIT, 'current': account.get('session_id'),
                'sessions': store.sessions(account['id'])}

    @app.delete('/api/membership/sessions/{session_id}')
    def revoke_membership_session(session_id: int, request: Request):
        account = signed_in(request)
        if not store.revoke_session(account['id'], session_id):
            raise HTTPException(404, 'Session not found')
        return {'ok': True}

    @app.get('/api/cycle')
    def cycles():
        return store.cycles()

    def cycle_review(cycle_id=None):
        from .stats.review import build_review
        selected_id = cycle_id or store.cycles()['active_cycle_id']
        source = store.review_source(selected_id)
        if source is None:
            raise HTTPException(404, 'Cycle not found')
        if source['saved_review'] is not None and source['cycle']['status'] != 'active':
            return source['saved_review']
        as_of = calendar_state(source['plan'], source['logs'])['date']
        return build_review(source, timestamp(), package_version, as_of)

    @app.get('/api/review')
    def review(cycle_id: str | None = None):
        return cycle_review(cycle_id)

    @app.get('/api/review/export')
    def export_review(cycle_id: str | None = None):
        return JSONResponse(cycle_review(cycle_id), headers={
            'Content-Disposition': 'attachment; filename="RoastRaw-review.json"', 'Cache-Control': 'no-store'})

    @app.get('/api/archive')
    def archive():
        records = store.cycles()
        historical = []
        for cycle in records['cycles']:
            if cycle['status'] == 'active':
                continue
            selected = cycle_review(cycle['id'])
            historical.append({**cycle, 'weeks': len(selected['plan']['weeks']),
                               'completion': selected['completion'], 'attainment': selected['attainment'],
                               'e1rm': selected['e1rm']})
        return {'cycles': historical, 'active_cycle_id': records['active_cycle_id']}

    @app.get('/api/attempts')
    def attempts_state(cycle_id: str | None = None):
        from .stats.attempts import LIFTS, competition_info, next_attempt, references, suggested
        selected = active_plan(cycle_id)
        selected_id = selected['meta']['planId']
        questionnaire = store.questionnaire(selected_id)
        refs = references(questionnaire, selected)
        saved = {(row['lift'], row['number']): row for row in store.attempts(selected_id)}
        lifts = {}
        for lift in LIFTS:
            reference = refs[lift]['reference']
            history = [saved.get((lift, n)) for n in (1, 2, 3)]
            suggestions = []
            for n in (1, 2, 3):
                if reference is None:
                    suggestions.append(None)
                elif n == 1:
                    suggestions.append(suggested(reference)[0])
                else:
                    previous = history[n - 2]
                    suggestions.append(next_attempt(reference, previous['load'], previous['result'], n)
                                       if previous else suggested(reference)[n - 1])
            lifts[lift] = {'reference': refs[lift], 'suggested': suggested(reference) if reference else None,
                           'next': suggestions, 'attempts': history}
        return {'cycle_id': selected_id, 'competition': competition_info(questionnaire, selected), 'lifts': lifts}

    class AttemptInput(BaseModel):
        model_config = ConfigDict(extra='forbid')
        cycle_id: str = Field(min_length=1)
        lift: Literal['squat', 'bench', 'deadlift']
        number: int = Field(ge=1, le=3)
        load: float = Field(gt=0, le=500)
        result: Literal['good', 'miss'] | None = None

    @app.put('/api/attempts')
    def save_attempt(payload: AttemptInput):
        if abs(payload.load / 2.5 - round(payload.load / 2.5)) > 1e-6:
            raise HTTPException(422, 'Attempt load must be a multiple of 2.5 kg')
        try:
            return store.save_attempt(payload.cycle_id, payload.lift, payload.number, payload.load, payload.result)
        except ReadOnlyError as exc:
            raise HTTPException(409, str(exc)) from exc

    class DeletionPrepareInput(BaseModel):
        model_config = ConfigDict(extra='forbid')
        cycle_id: str = Field(min_length=1)

    @app.post('/api/archive/delete/prepare')
    def prepare_deletion(payload: DeletionPrepareInput):
        try:
            token = store.prepare_deletion(payload.cycle_id)
        except KeyError as exc:
            raise HTTPException(404, 'Cycle not found') from exc
        except ReadOnlyError as exc:
            raise HTTPException(409, str(exc)) from exc
        return JSONResponse({'token': token, 'cycle_id': payload.cycle_id, 'review': cycle_review(payload.cycle_id)},
                            headers={'Content-Disposition': f'attachment; filename="RoastRaw-delete-export-{payload.cycle_id}.json"',
                                     'Cache-Control': 'no-store'})

    class DeletionInput(BaseModel):
        model_config = ConfigDict(extra='forbid')
        token: str = Field(min_length=1)
        confirm: str = Field(min_length=1)

    @app.delete('/api/archive/{cycle_id}')
    def delete_cycle(cycle_id: str, payload: DeletionInput):
        if payload.confirm != cycle_id:
            raise HTTPException(422, 'Type the exact cycle ID to confirm deletion')
        try:
            return store.delete_cycle(cycle_id, payload.token)
        except KeyError as exc:
            raise HTTPException(404, 'Cycle not found') from exc
        except ReadOnlyError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/plan')
    def plan(cycle_id: str | None = None):
        return active_plan(cycle_id)

    @app.get('/api/performance')
    def recorded_performance(cycle_id: str | None = None):
        selected = active_plan(cycle_id)
        return performance(selected, store.logs(selected['meta']['planId']))

    @app.get('/api/log')
    def logs(cycle_id: str | None = None):
        selected = active_plan(cycle_id)
        return {'cycle_id': selected['meta']['planId'], 'logs': store.logs(selected['meta']['planId'])}

    @app.put('/api/log')
    def save_log(payload: LogInput):
        selected = active_plan(payload.cycle_id)
        if payload.cycle_id != store.cycles()['active_cycle_id']:
            raise HTTPException(409, 'Archived cycles are read-only')
        row = next((row for row in selected['workouts'] if (row['week'], row['day'], row['seq']) == (payload.week, payload.day, payload.seq)), None)
        if row is None:
            raise HTTPException(404, 'Workout row not found')
        if payload.sets > 0 and payload.reps == 0:
            raise HTTPException(422, 'Positive set count requires positive reps')
        if row['bucket'] != 'accessory' and payload.sets > 0 and payload.load is None:
            raise HTTPException(422, 'Main and variation logs require a load')
        fields = payload.model_dump(include={'load', 'sets', 'reps', 'rpe', 'note'})
        return store.save_log(payload.cycle_id, row, fields)

    def writable(cycle_id):
        active_plan(cycle_id)
        if cycle_id != store.cycles()['active_cycle_id']:
            raise HTTPException(409, 'Archived cycles are read-only')

    @app.exception_handler(ReadOnlyError)
    async def conflict(request, error):
        return JSONResponse(status_code=409, content={'error': str(error)})

    @app.get('/api/readiness')
    def readiness(cycle_id: str, date: str, session_id: str = 'daily'):
        active_plan(cycle_id)
        try:
            DatedInput(cycle_id=cycle_id, date=date)
        except ValueError:
            raise HTTPException(422, 'Expected a valid YYYY-MM-DD date')
        history = store.readiness_records(cycle_id)
        record = next((row for row in history if row['date'] == date and row['session_id'] == session_id), None)
        evaluation = score_readiness(record or {'date': date}, history)
        return {'record': record, 'evaluation': evaluation, 'legacy': store.legacy_readiness(cycle_id)}

    @app.put('/api/readiness')
    def save_readiness(payload: ReadinessInput):
        writable(payload.cycle_id)
        selected = active_plan(payload.cycle_id)
        if payload.session_id != 'daily' and not any(
                f"{row['week']}|{row['day']}" == payload.session_id and row['date'] == payload.date
                for row in selected['workouts']):
            raise HTTPException(422, 'Session must match the prescribed date')
        store.save_readiness(payload.cycle_id, payload.model_dump(exclude={'cycle_id'}))
        return readiness(payload.cycle_id, payload.date, payload.session_id)

    @app.get('/api/body-metrics')
    def metrics(cycle_id: str, date: str | None = None):
        active_plan(cycle_id)
        if date is not None:
            try:
                DatedInput(cycle_id=cycle_id, date=date)
            except ValueError:
                raise HTTPException(422, 'Expected a valid YYYY-MM-DD date')
        records = store.metrics(cycle_id)
        prior = [row for row in records if row['bodyweight'] is not None and (date is None or row['date'] <= date)]
        weight = {'value': prior[-1]['bodyweight'], 'date': prior[-1]['date']} if prior else None
        return {'records': records, 'bodyweight': weight}

    @app.put('/api/body-metrics')
    def save_metrics(payload: MetricsInput):
        writable(payload.cycle_id)
        store.save_metrics(payload.cycle_id, payload.model_dump(exclude={'cycle_id'}))
        return metrics(payload.cycle_id, payload.date)

    @app.get('/api/questionnaire')
    def questionnaire(cycle_id: str):
        active_plan(cycle_id)
        saved = store.questionnaire(cycle_id)
        if saved is None:
            return {'cycle_id': cycle_id, 'status': 'empty', 'payload': skeleton(), 'updated_at': None}
        return {'cycle_id': cycle_id, **saved}

    @app.put('/api/questionnaire')
    def save_questionnaire(payload: QuestionnaireInput):
        writable(payload.cycle_id)
        movement_ids = {entry['id'] for entry in library()['movements']}
        validate_questionnaire(payload.payload, payload.status, movement_ids)
        return {'cycle_id': payload.cycle_id,
                **store.save_questionnaire(payload.cycle_id, payload.payload, payload.status)}

    @app.get('/api/prescription')
    def prescription(cycle_id: str):
        from .stats.variations import POLICY, catalogue, defaults, digest, family, system_load
        selected = active_plan(cycle_id)
        policy = selected.get('prescription', {})
        readings = store.metrics(cycle_id)
        actuals = store.logs(cycle_id)
        system_loads = {}
        if policy.get('version') == POLICY:
            for row in selected['workouts']:
                info = family(row)
                if info and info['system']:
                    key = f"{row['week']}|{row['day']}|{row['seq']}"
                    log = actuals.get(key)
                    system_loads[key] = {
                        'planned': [system_load(segment['load'], row['date'], readings) for segment in row['segments']],
                        'logged': system_load(log['load'], row['date'], readings) if log and log['sets'] > 0 else None}
        return {'cycle_id': cycle_id, 'currentId': digest(selected), 'policy': policy.get('version', 'legacy'),
                'references': policy.get('references', defaults()),
                'catalogue': [entry for group in catalogue().values() for entry in group],
                'versions': store.prescription_versions(cycle_id), 'systemLoads': system_loads}

    def preview_payload(payload):
        from .stats.variations import changes, digest, recalculate
        writable(payload.cycle_id)
        selected = active_plan(payload.cycle_id)
        if digest(selected) != payload.current_id:
            raise HTTPException(409, 'Prescription changed. Refresh and review the new version before saving.')
        try:
            candidate = recalculate(selected, payload.references)
        except ValueError as exc:
            from .stats.variations import defaults
            message = str(exc)
            bad_id = next((key for key in defaults().keys() | payload.references.keys() if key == message or key in message), None)
            row = next((row for row in selected['workouts'] if f"{row['week']}|{row['day']}|{row['seq']} (" in message), {})
            raise Reject([{'file': 'request', 'week': row.get('week'), 'day': row.get('day'),
                           'movement': row.get('movement'), 'field': 'references' + ('.' + bad_id if bad_id else ''),
                           'expected': 'Known movement ID with a positive finite reference for prescribed variations. ' + message}])
        validate_plan(candidate, file='recalculated.json')
        return selected, candidate, {'previewId': digest(candidate), 'currentId': payload.current_id,
                                     'changes': changes(selected, candidate)}

    @app.post('/api/prescription/preview')
    def preview_prescription(payload: PrescriptionInput):
        return preview_payload(payload)[2]

    @app.post('/api/prescription/apply')
    def apply_prescription(payload: ApplyPrescription):
        _, candidate, preview = preview_payload(payload)
        if preview['previewId'] != payload.preview_id:
            raise HTTPException(409, 'Preview does not match these references. Review again before applying.')
        revision_id = store.replace_prescription(payload.cycle_id, payload.current_id, candidate, 'apply')
        return {'id': revision_id, 'saved': True}

    @app.get('/api/prescription/version')
    def prescription_version(cycle_id: str, revision_id: str):
        from .stats.variations import changes
        selected = active_plan(cycle_id)
        historical = store.prescription_version(cycle_id, revision_id)
        if historical is None:
            raise HTTPException(404, 'Prescription version not found')
        return {'id': revision_id, 'plan': historical, 'changes': changes(selected, historical)}

    @app.post('/api/prescription/restore')
    def restore_prescription(payload: RestorePrescription):
        writable(payload.cycle_id)
        historical = store.prescription_version(payload.cycle_id, payload.revision_id)
        if historical is None:
            raise HTTPException(404, 'Prescription version not found')
        validate_plan(historical, file='historical.json')
        revision_id = store.replace_prescription(payload.cycle_id, payload.current_id, historical, 'restore')
        return {'id': revision_id, 'saved': True}

    @app.get('/api/analysis')
    def analysis(mode: Literal['plan', 'log'] = 'plan', cycle_id: str | None = None):
        selected = active_plan(cycle_id)
        return analyze(selected, store.logs(selected['meta']['planId']), mode)

    @app.get('/api/today')
    def today():
        selected = active_plan()
        return calendar_state(selected, store.logs(selected['meta']['planId']))

    @app.get('/api/geometry')
    def geometry():
        return json.loads((ROOT / 'data' / 'muscle_geo.json').read_text(encoding='utf-8'))

    def import_preview(payload):
        from hashlib import sha256
        from .plan_import import parse_plan, summary
        from .stats.variations import digest
        candidate = parse_plan(payload.plan_json, payload.filename)
        records = store.cycles()
        source = store.review_source(records['active_cycle_id'])
        if source is None or source['cycle']['status'] != 'active':
            raise ReadOnlyError('Current cycle changed. Refresh before importing.')
        if any(cycle['id'] == candidate['meta']['planId'] for cycle in records['cycles']):
            raise ReadOnlyError('Cycle ID already exists. Existing cycles cannot be overwritten.')
        return candidate, {
            'currentId': digest(source), 'candidateId': digest(candidate),
            'current': summary(source['plan']), 'candidate': summary(candidate),
            'currentPlan': source['plan'], 'candidatePlan': candidate,
            'sourceSha256': sha256(payload.plan_json.encode('utf-8')).hexdigest()}

    @app.post('/api/plan/import/preview')
    def preview_plan_import(payload: PlanImportInput):
        return import_preview(payload)[1]

    @app.post('/api/plan/import/confirm')
    def confirm_plan_import(payload: ConfirmPlanImport):
        candidate, preview = import_preview(payload)
        if preview['candidateId'] != payload.candidate_id or preview['currentId'] != payload.current_id:
            raise ReadOnlyError('Preview or current records changed. Preview again before importing.')
        return store.activate_plan(candidate, payload.current_id, package_version)

    @app.post('/api/plan/validate')
    async def validate(request: Request):
        try:
            doc = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(422, 'Expected valid JSON')
        validate_plan(doc, file='request.json')
        return {'valid': True, 'persisted': False, 'schemaVersion': doc['schemaVersion']}

    @app.exception_handler(AiQuotaError)
    async def ai_quota_exhausted(request, error):
        return JSONResponse(status_code=429, content={'error': str(error)})

    class AiChatMessage(BaseModel):
        model_config = ConfigDict(extra='forbid', strict=True)
        role: Literal['user', 'assistant']
        content: str = Field(min_length=1, max_length=8000)

    class AiOutlookInput(BaseModel):
        model_config = ConfigDict(extra='forbid', strict=True)
        cycle_id: str = Field(min_length=1)

    class AiChatInput(AiOutlookInput):
        message: str = Field(min_length=1, max_length=4000)
        conversation: list[AiChatMessage] = Field(default_factory=list, max_length=40)

    def ai_context(cycle_id):
        review = cycle_review(cycle_id)
        saved = store.questionnaire(cycle_id)
        questionnaire = saved or {'status': 'empty', 'payload': skeleton()}
        return review, questionnaire

    @app.get('/api/ai/status')
    def ai_status(cycle_id: str):
        from . import ai
        active_plan(cycle_id)
        return {'configured': ai.configured(), 'quota': store.ai_quota(ai.beijing_day()),
                'calls': store.ai_calls(cycle_id)}

    @app.get('/api/ai/call/{call_id}')
    def ai_call_record(call_id: int):
        record = store.ai_call(call_id)
        if record is None:
            raise HTTPException(404, 'AI call not found')
        return record

    @app.get('/api/ai/export')
    def ai_export(cycle_id: str):
        from .ai import build_outlook_prompt
        review, questionnaire = ai_context(cycle_id)
        bundle = {'review': review, 'questionnaire': questionnaire,
                  'prompt': build_outlook_prompt(review, questionnaire)}
        return JSONResponse(bundle, headers={
            'Content-Disposition': 'attachment; filename="RoastRaw-ai-export.json"', 'Cache-Control': 'no-store'})

    def run_ai(cycle_id, kind, prompt, messages, parse=None):
        from . import ai
        if not ai.configured():
            raise HTTPException(503, 'DeepSeek is not configured on this server. Export the review, questionnaire and prompt for an external AI instead.')
        call_id = store.reserve_ai_call(cycle_id, ai.beijing_day(), kind, prompt, messages)
        try:
            content = ai.call_deepseek(messages)
            result = parse(content) if parse else content
        except Exception as exc:
            message = f'{type(exc).__name__}: {exc}'[:500]
            store.finish_ai_call(call_id, 'error', error=message)
            raise HTTPException(502, f'AI call failed ({message}). It counted against today\'s quota; retry manually or export for an external AI.')
        store.finish_ai_call(call_id, 'ok', response=content)
        return {'id': call_id, 'result': result, 'quota': store.ai_quota(ai.beijing_day())}

    @app.post('/api/ai/outlook')
    def ai_outlook(payload: AiOutlookInput):
        from .ai import build_outlook_prompt, parse_outlook
        writable(payload.cycle_id)
        review, questionnaire = ai_context(payload.cycle_id)
        prompt = build_outlook_prompt(review, questionnaire)
        return run_ai(payload.cycle_id, 'outlook', prompt,
                      [{'role': 'user', 'content': prompt}], parse=parse_outlook)

    @app.post('/api/ai/chat')
    def ai_chat(payload: AiChatInput):
        from .ai import CHAT_SYSTEM, build_outlook_prompt
        writable(payload.cycle_id)
        review, questionnaire = ai_context(payload.cycle_id)
        prompt = build_outlook_prompt(review, questionnaire)
        messages = ([{'role': 'system', 'content': CHAT_SYSTEM + '\n\nCONTEXT:\n' + prompt}]
                    + [entry.model_dump() for entry in payload.conversation]
                    + [{'role': 'user', 'content': payload.message}])
        return run_ai(payload.cycle_id, 'chat', prompt, messages)

    web = ROOT / 'web' / 'dist'
    if (web / 'index.html').is_file():
        app.mount('/assets', StaticFiles(directory=web / 'assets'), name='assets')
        shots = web / 'shots'
        if shots.is_dir():
            app.mount('/shots', StaticFiles(directory=shots), name='shots')

        @app.get('/{path:path}', include_in_schema=False)
        def frontend(path: str):
            if path == 'api' or path.startswith('api/'):
                raise HTTPException(404, 'API route not found')
            # The shell must always match the deployed hashed assets; only /assets/* is immutable.
            return FileResponse(web / 'index.html', headers={'Cache-Control': 'no-store'})

    return app


app = create_app()
