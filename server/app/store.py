import json
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class ReadOnlyError(ValueError):
    pass


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
            if version not in (0, 1, 2, 3):
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
            ''')
            if version == 0:
                db.execute('PRAGMA user_version=1')
            if db.execute('SELECT count(*) FROM cycles').fetchone()[0] == 0:
                meta = plan['meta']
                db.execute('INSERT INTO cycles VALUES(?,?,?,?,?,?)',
                           (meta['planId'], meta['name'], meta['startDate'], meta['endDate'], 'active', plan['schemaVersion']))
                db.execute('INSERT INTO plans VALUES(?,?,?,?,?)',
                           (meta['planId'], meta['planId'], json.dumps(plan, ensure_ascii=False), plan['schemaVersion'], timestamp()))

    def snapshot(self):
        folder = self.path.parent / 'backups'
        folder.mkdir(exist_ok=True)
        target = folder / f"{self.path.stem}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.sqlite3"
        with self.connect() as source, closing(sqlite3.connect(target)) as backup:
            source.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed')
        return target

    def upgrade(self):
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
        if version in (2, 3):
            return
        if version != 1:
            raise RuntimeError('Unsupported database version; no data was changed')
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE readiness_v2 (
                cycle_id TEXT NOT NULL REFERENCES cycles(id), date TEXT NOT NULL,
                session_id TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(cycle_id,date,session_id))''')
            db.execute('''CREATE TABLE records_journal (
                id INTEGER PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES cycles(id),
                kind TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)''')
            db.execute('PRAGMA user_version=2')

    def upgrade_prescriptions(self):
        from .stats.variations import digest
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
        if version == 3:
            return
        if version != 2:
            raise RuntimeError('Unsupported database version; no data was changed')
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE prescription_versions (
                cycle_id TEXT NOT NULL REFERENCES cycles(id), id TEXT NOT NULL,
                json TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(cycle_id,id))''')
            for row in db.execute('SELECT cycle_id,json FROM plans').fetchall():
                db.execute('INSERT INTO prescription_versions VALUES(?,?,?,?)',
                           (row['cycle_id'], digest(json.loads(row['json'])), row['json'], timestamp()))
            db.execute('PRAGMA user_version=3')

    def prescription_versions(self, cycle_id):
        from .stats.variations import digest
        current = digest(self.plan(cycle_id))
        with self.connect() as db:
            rows = db.execute('SELECT * FROM prescription_versions WHERE cycle_id=? ORDER BY created_at DESC', (cycle_id,)).fetchall()
        return [{'id': row['id'], 'created_at': row['created_at'], 'current': row['id'] == current,
                 'policy': json.loads(row['json']).get('prescription', {}).get('version', 'legacy')}
                for row in rows]

    def prescription_version(self, cycle_id, revision_id):
        with self.connect() as db:
            row = db.execute('SELECT json FROM prescription_versions WHERE cycle_id=? AND id=?', (cycle_id, revision_id)).fetchone()
        return json.loads(row['json']) if row else None

    def replace_prescription(self, cycle_id, expected_id, plan, action):
        from .stats.variations import digest
        revision_id = digest(plan)
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_active(db, cycle_id)
            current = json.loads(db.execute('SELECT json FROM plans WHERE cycle_id=?', (cycle_id,)).fetchone()['json'])
            if digest(current) != expected_id:
                raise ReadOnlyError('Prescription changed. Refresh and review the new version before saving.')
            if revision_id != expected_id:
                encoded = json.dumps(plan, ensure_ascii=False, allow_nan=False)
                stamp = timestamp()
                db.execute('INSERT OR IGNORE INTO prescription_versions VALUES(?,?,?,?)', (cycle_id, revision_id, encoded, stamp))
                db.execute('INSERT INTO records_journal(cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?)',
                           (cycle_id, 'prescription', revision_id, json.dumps({'action': action, 'from': expected_id, 'to': revision_id}), stamp))
                db.execute('UPDATE plans SET json=? WHERE cycle_id=?', (encoded, cycle_id))
        return revision_id

    def readiness_records(self, cycle_id):
        with self.connect() as db:
            records = db.execute('SELECT payload,updated_at FROM readiness_v2 WHERE cycle_id=? ORDER BY date,updated_at', (cycle_id,)).fetchall()
        return [{**json.loads(row['payload']), 'updated_at': row['updated_at']} for row in records]

    def legacy_readiness(self, cycle_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM readiness WHERE cycle_id=? ORDER BY date,session_id', (cycle_id,))]

    def metrics(self, cycle_id):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM body_metrics WHERE cycle_id=? ORDER BY date', (cycle_id,)).fetchall()
        return [{'date': row['date'], 'bodyweight': row['bodyweight'], 'bodyfat': row['bodyfat'],
                 'measurements': json.loads(row['measurements_json'] or '{}')} for row in rows]

    def save_readiness(self, cycle_id, payload):
        stamp = timestamp()
        key = f"{payload['date']}|{payload['session_id']}"
        encoded = json.dumps(payload, ensure_ascii=False)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_active(db, cycle_id)
            db.execute('INSERT INTO records_journal(cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?)',
                       (cycle_id, 'readiness', key, encoded, stamp))
            db.execute('''INSERT INTO readiness_v2 VALUES(?,?,?,?,?)
                ON CONFLICT(cycle_id,date,session_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at''',
                       (cycle_id, payload['date'], payload['session_id'], encoded, stamp))

    def save_metrics(self, cycle_id, payload):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_active(db, cycle_id)
            db.execute('INSERT INTO records_journal(cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?)',
                       (cycle_id, 'body_metrics', payload['date'], json.dumps(payload), timestamp()))
            db.execute('''INSERT INTO body_metrics(cycle_id,date,bodyweight,bodyfat,measurements_json) VALUES(?,?,?,?,?)
                ON CONFLICT(cycle_id,date) DO UPDATE SET bodyweight=excluded.bodyweight,
                bodyfat=excluded.bodyfat,measurements_json=excluded.measurements_json''',
                       (cycle_id, payload['date'], payload['bodyweight'], payload['bodyfat'], json.dumps(payload['measurements'])))

    @staticmethod
    def require_active(db, cycle_id):
        if db.execute("SELECT 1 FROM cycles WHERE id=? AND status='active'", (cycle_id,)).fetchone() is None:
            raise ReadOnlyError('Archived cycles are read-only')

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
