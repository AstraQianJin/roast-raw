import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self, plan):
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError('Unsupported database version; no data was changed')
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS cycles (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','completed','archived')),
                    schema_version TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_cycle ON cycles(status) WHERE status='active';
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL UNIQUE REFERENCES cycles(id),
                    json TEXT NOT NULL, version TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS logs (
                    cycle_id TEXT NOT NULL REFERENCES cycles(id), key TEXT NOT NULL,
                    date TEXT NOT NULL, session_id TEXT NOT NULL, exercise_id TEXT NOT NULL,
                    load REAL, reps INTEGER NOT NULL CHECK(reps>=0), rpe REAL CHECK(rpe>=5.5 AND rpe<=10),
                    set_count INTEGER NOT NULL CHECK(set_count>=0), note TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(cycle_id,key));
                CREATE TABLE IF NOT EXISTS logs_journal (
                    id INTEGER PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES cycles(id),
                    key TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS readiness (
                    cycle_id TEXT NOT NULL REFERENCES cycles(id), date TEXT NOT NULL, session_id TEXT NOT NULL,
                    fatigue INTEGER, arousal INTEGER, nutrition INTEGER, hrv REAL,
                    sleep_score REAL, rhr REAL, session_time TEXT, rec REAL, note TEXT,
                    PRIMARY KEY(cycle_id,date,session_id));
                CREATE TABLE IF NOT EXISTS archives (
                    id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL UNIQUE REFERENCES cycles(id),
                    review_json TEXT NOT NULL, exported_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS body_metrics (
                    id INTEGER PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES cycles(id),
                    date TEXT NOT NULL, bodyweight REAL, bodyfat REAL, measurements_json TEXT,
                    UNIQUE(cycle_id,date));
                PRAGMA user_version=1;
            ''')
            if db.execute('SELECT count(*) FROM cycles').fetchone()[0] == 0:
                meta = plan['meta']
                db.execute('INSERT INTO cycles VALUES(?,?,?,?,?,?)',
                           (meta['planId'], meta['name'], meta['startDate'], meta['endDate'], 'active', plan['schemaVersion']))
                db.execute('INSERT INTO plans VALUES(?,?,?,?,?)',
                           (meta['planId'], meta['planId'], json.dumps(plan, ensure_ascii=False), plan['schemaVersion'], timestamp()))

    def cycles(self):
        with self.connect() as db:
            cycles = [dict(row) for row in db.execute('SELECT * FROM cycles ORDER BY start_date DESC')]
        return {'cycles': cycles, 'active_cycle_id': next((row['id'] for row in cycles if row['status'] == 'active'), None)}

    def plan(self, cycle_id=None):
        with self.connect() as db:
            if cycle_id is None:
                row = db.execute("SELECT p.json FROM plans p JOIN cycles c ON c.id=p.cycle_id WHERE c.status='active'").fetchone()
            else:
                row = db.execute('SELECT json FROM plans WHERE cycle_id=?', (cycle_id,)).fetchone()
        return json.loads(row['json']) if row else None

    def logs(self, cycle_id):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM logs WHERE cycle_id=? ORDER BY key', (cycle_id,)).fetchall()
        return {row['key']: {'load': row['load'], 'sets': row['set_count'], 'reps': row['reps'],
                             'rpe': row['rpe'], 'note': row['note'], 'updated_at': row['updated_at']}
                for row in rows}

    def save_log(self, cycle_id, row, payload):
        key = f"{row['week']}|{row['day']}|{row['seq']}"
        stamp = timestamp()
        with self.connect() as db:
            db.execute('INSERT INTO logs_journal(cycle_id,key,payload,created_at) VALUES(?,?,?,?)',
                       (cycle_id, key, json.dumps(payload), stamp))
            db.execute('''INSERT INTO logs VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(cycle_id,key) DO UPDATE SET
                load=excluded.load,reps=excluded.reps,rpe=excluded.rpe,set_count=excluded.set_count,
                note=excluded.note,updated_at=excluded.updated_at''',
                (cycle_id, key, row['date'], f"{row['week']}|{row['day']}", row['movementId'],
                 payload['load'], payload['reps'], payload['rpe'], payload['sets'], payload['note'], stamp))
        return {'key': key, **payload, 'updated_at': stamp}
