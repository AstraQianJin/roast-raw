import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile

# Fixture servers are hermetic: deployment secrets in the developer environment
# must not turn the gate on or make DeepSeek appear configured. --gate opts in
# with an explicit fixture password and the Astra owner, never the real secret.
os.environ.pop('RR_ACCESS_PASSWORD', None)
os.environ.pop('RR_ACCESS_USERNAME', None)
os.environ.pop('DEEPSEEK_API_KEY', None)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn
from server.app import main
from server.app.calendar import calendar_state, SHANGHAI
from server.tools.synth_plan import build

parser = argparse.ArgumentParser()
parser.add_argument('--port', required=True, type=int)
parser.add_argument('--weeks', type=int)
parser.add_argument('--date')
parser.add_argument('--archive', action='store_true')
parser.add_argument('--gate')
args = parser.parse_args()
if args.gate:
    os.environ['RR_ACCESS_PASSWORD'] = args.gate
    os.environ['RR_ACCESS_USERNAME'] = 'Astra'
if args.date:
    instant = datetime.fromisoformat(args.date).replace(tzinfo=SHANGHAI)
    main.calendar_state = lambda plan, logs: calendar_state(plan, logs, now=instant)
with tempfile.TemporaryDirectory(prefix='roastraw-browser-') as directory:
    path = Path(directory)
    plan_path = ROOT / 'data/plan.json'
    if args.weeks:
        plan_path = path / 'plan.json'
        plan_path.write_text(json.dumps(build(args.weeks)), encoding='utf-8')
    app = main.create_app(db_path=path / 'test.sqlite3', plan_path=plan_path)
    if args.archive:
        from copy import deepcopy
        from server.app.stats.variations import digest
        store = app.state.store
        active = json.loads(plan_path.read_text(encoding='utf-8'))
        store.initialize(active)
        store.upgrade()
        store.upgrade_prescriptions()
        historical = deepcopy(active)
        historical['meta']['planId'] = 'archive-fixture'
        historical['meta']['name'] = 'Historical cycle fixture'
        meta = historical['meta']
        with store.connect() as db:
            db.execute('INSERT INTO cycles VALUES(?,?,?,?,?,?)',
                       (meta['planId'], meta['name'], meta['startDate'], meta['endDate'], 'archived', historical['schemaVersion']))
            db.execute('INSERT INTO plans VALUES(?,?,?,?,?)',
                       (meta['planId'], meta['planId'], json.dumps(historical), historical['schemaVersion'], '2026-11-01T00:00:00+00:00'))
            db.execute('INSERT INTO prescription_versions VALUES(?,?,?,?)',
                       (meta['planId'], digest(historical), json.dumps(historical), '2026-11-01T00:00:00+00:00'))
            db.execute('INSERT INTO body_metrics(cycle_id,date,bodyweight,bodyfat,measurements_json) VALUES(?,?,?,?,?)',
                       (meta['planId'], meta['endDate'], 83.4, 0, '{}'))
            db.execute('INSERT INTO readiness(cycle_id,date,session_id,fatigue,note) VALUES(?,?,?,?,?)',
                       (meta['planId'], meta['endDate'], 'daily', 6, 'Original fatigue, not recovery'))
        row = next(row for row in active['workouts'] if row['bucket'] == 'main')
        store.save_log(active['meta']['planId'], row, {'load': 100.0, 'sets': 2, 'reps': 3, 'rpe': 8.0, 'note': 'Active fixture'})
        from test_api import seed_historical_log
        seed_historical_log(store.path, meta['planId'], row, {'load': 70.0, 'sets': 2, 'reps': 1, 'rpe': 9.0, 'note': 'Historical <script> data, not HTML'})
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')
