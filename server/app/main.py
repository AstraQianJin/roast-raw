import json
import os
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

from .calendar import calendar_state
from .stats.engine import analyze
from .store import ReadOnlyError, Store
from .validation import Reject, validate_plan

ROOT = Path(__file__).resolve().parents[2]


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


def create_app(db_path=None, plan_path=None):
    store = Store(db_path or os.environ.get('RR_DB_PATH', ROOT / 'data' / 'roastraw.sqlite3'))

    @asynccontextmanager
    async def lifespan(app):
        seed = json.loads(Path(plan_path or ROOT / 'data' / 'plan.json').read_text(encoding='utf-8'))
        validate_plan(seed)
        store.initialize(seed)
        store.upgrade()
        yield

    package_version = json.loads((ROOT / 'web/package.json').read_text(encoding='utf-8'))['version']
    version_parts = package_version.split('.')
    release_version = f'{version_parts[0]}.{int(version_parts[2]):02d}'
    app = FastAPI(title='Roast Raw', version=package_version, lifespan=lifespan)
    app.state.store = store
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])

    @app.exception_handler(Reject)
    async def rejected(request, error):
        return JSONResponse(status_code=422, content={'error': 'Plan rejected. No data changed.', 'errors': error.errors})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        body = error.body if isinstance(error.body, dict) else {}
        errors = [{'file': 'request', 'week': body.get('week') if type(body.get('week')) is int else None,
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

    @app.get('/api/cycle')
    def cycles():
        return store.cycles()

    @app.get('/api/plan')
    def plan(cycle_id: str | None = None):
        return active_plan(cycle_id)

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

    @app.post('/api/plan/validate')
    async def validate(request: Request):
        try:
            doc = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(422, 'Expected valid JSON')
        validate_plan(doc, file='request.json')
        return {'valid': True, 'persisted': False, 'schemaVersion': doc['schemaVersion']}

    web = ROOT / 'web' / 'dist'
    if (web / 'index.html').is_file():
        app.mount('/assets', StaticFiles(directory=web / 'assets'), name='assets')

        @app.get('/{path:path}', include_in_schema=False)
        def frontend(path: str):
            if path == 'api' or path.startswith('api/'):
                raise HTTPException(404, 'API route not found')
            return FileResponse(web / 'index.html')

    return app


app = create_app()
