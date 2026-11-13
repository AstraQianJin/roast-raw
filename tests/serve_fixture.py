import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import tempfile

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
args = parser.parse_args()
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
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')
