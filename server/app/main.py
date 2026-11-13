import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .calendar import calendar_state
from .stats.engine import analyze
from .store import Store
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


def create_app(db_path=None, plan_path=None):
    store = Store(db_path or os.environ.get('RR_DB_PATH', ROOT / 'data' / 'roastraw.sqlite3'))

    @asynccontextmanager
    async def lifespan(app):
        seed = json.loads(Path(plan_path or ROOT / 'data' / 'plan.json').read_text(encoding='utf-8'))
        validate_plan(seed)
        store.initialize(seed)
        yield

    app = FastAPI(title='Roast Raw', version='0.01', lifespan=lifespan)
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
        return {'status': 'ok', 'version': '0.01', 'timezone': 'Asia/Shanghai', 'storage': 'SQLite'}

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
