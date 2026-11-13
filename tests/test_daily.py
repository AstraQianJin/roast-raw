import copy
import json
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest

from fastapi.testclient import TestClient
from server.app.main import create_app
from server.app.store import Store

ROOT = Path(__file__).resolve().parents[1]


class DailyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'daily.db'
        self.app = create_app(db_path=self.path)
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.plan = self.client.get('/api/plan').json()
        self.cycle = self.plan['meta']['planId']
        self.row = self.plan['workouts'][0]

    def readiness(self, **changes):
        value = {'cycle_id': self.cycle, 'date': self.row['date'],
                 'session_id': f"{self.row['week']}|{self.row['day']}",
                 'recovery': 1, 'arousal': 4, 'nutrition': 7, 'hrv': 50.,
                 'rhr': 60., 'sleep_score': 80., 'session_time': '06:00',
                 'joint_pain': False, 'note': 'Recovery, not legacy fatigue'}
        value.update(changes)
        return value

    def test_save_readback_and_atomic_journal(self):
        payload = self.readiness()
        result = self.client.put('/api/readiness', json=payload)
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()
        self.assertEqual(data['evaluation']['score'], 57.5)
        self.assertEqual(data['evaluation']['validInputs'], 4)
        self.assertIsNone(data['evaluation']['scores']['hrv'])
        self.assertEqual(data['evaluation']['timeAdjustmentPct'], -3)
        query = {key: payload[key] for key in ('cycle_id', 'date', 'session_id')}
        self.assertEqual(self.client.get('/api/readiness', params=query).json(), data)
        self.client.put('/api/readiness', json=self.readiness(recovery=None, nutrition=None, sleep_score=None))
        self.assertIsNone(self.client.get('/api/readiness', params=query).json()['evaluation']['score'])
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute('SELECT count(*) FROM readiness_v2').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM records_journal').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT count(*) FROM readiness').fetchone()[0], 0)

    def test_invalid_input_and_archives_never_write(self):
        for changes in ({'recovery': 0}, {'arousal': True}, {'hrv': 0}, {'rhr': -1},
                        {'date': '2026-02-30'}, {'sleep_score': 101}, {'session_time': '24:00'},
                        {'session_id': '999|Z'}, {'joint_pain': 'yes'}, {'unexpected': 1}):
            with self.subTest(changes=changes):
                result = self.client.put('/api/readiness', json=self.readiness(**changes))
                self.assertEqual(result.status_code, 422, result.text)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute('SELECT count(*) FROM records_journal').fetchone()[0], 0)
            db.execute("UPDATE cycles SET status='archived'")
        self.assertEqual(self.client.put('/api/readiness', json=self.readiness()).status_code, 409)

    def test_bodyweight_same_day_or_prior_never_future(self):
        for day, weight in (('2026-01-01', 80.), ('2026-02-01', 85.), ('2026-03-01', 90.)):
            result = self.client.put('/api/body-metrics', json={'cycle_id': self.cycle, 'date': day,
                                    'bodyweight': weight, 'bodyfat': None, 'measurements': {'waist': 80.}})
            self.assertEqual(result.status_code, 200, result.text)
        for day, expected in (('2025-12-31', None), ('2026-02-01', {'value': 85., 'date': '2026-02-01'}),
                              ('2026-02-10', {'value': 85., 'date': '2026-02-01'})):
            data = self.client.get('/api/body-metrics', params={'cycle_id': self.cycle, 'date': day}).json()
            self.assertEqual(data['bodyweight'], expected)
        result = self.client.put('/api/body-metrics', json={'cycle_id': self.cycle, 'date': '2026-01-01',
                                'bodyweight': None, 'bodyfat': 0, 'measurements': {}})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['records'][0]['bodyfat'], 0)
        self.assertIsNone(result.json()['records'][0]['bodyweight'])

    def test_failed_record_and_journal_rollback(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TRIGGER fail_record BEFORE INSERT ON readiness_v2 BEGIN SELECT RAISE(ABORT,'injected'); END")
        with TestClient(self.app, raise_server_exceptions=False) as client:
            self.assertEqual(client.put('/api/readiness', json=self.readiness()).status_code, 500)
        with closing(sqlite3.connect(self.path)) as db, db:
            self.assertEqual(db.execute('SELECT count(*) FROM records_journal').fetchone()[0], 0)

    def test_fresh_app_readback(self):
        result = self.client.put('/api/readiness', json=self.readiness()).json()
        with TestClient(create_app(db_path=self.path)) as restarted:
            query = {key: self.readiness()[key] for key in ('cycle_id', 'date', 'session_id')}
            self.assertEqual(restarted.get('/api/readiness', params=query).json(), result)


class MigrationTests(unittest.TestCase):
    def test_v1_snapshot_preserves_legacy_meaning_and_all_tables(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy.db'
            plan = json.loads((ROOT / 'data/plan.json').read_text(encoding='utf-8'))
            store = Store(path)
            store.initialize(plan)
            cycle = plan['meta']['planId']
            with store.connect() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
                db.execute('INSERT INTO readiness(cycle_id,date,session_id,fatigue,note) VALUES(?,?,?,?,?)',
                           (cycle, '2026-01-01', 'daily', 7, 'Old meaning'))
                tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                before = {table: db.execute(f'SELECT * FROM {table}').fetchall() for table in tables}
            store.upgrade()
            with store.connect() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
                for table, values in before.items():
                    self.assertEqual(db.execute(f'SELECT * FROM {table}').fetchall(), values)
                self.assertEqual(db.execute('SELECT count(*) FROM readiness_v2').fetchone()[0], 0)
            snapshot = next((path.parent / 'backups').glob('*.sqlite3'))
            with closing(sqlite3.connect(snapshot)) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT fatigue,note FROM readiness').fetchone(), (7, 'Old meaning'))
            store.initialize(plan)
            store.upgrade()
            self.assertEqual(store.legacy_readiness(cycle)[0]['fatigue'], 7)

    def test_unknown_database_version_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'unknown.db'
            with closing(sqlite3.connect(path)) as db, db:
                db.execute('PRAGMA user_version=99')
            before = path.read_bytes()
            with self.assertRaises(RuntimeError):
                Store(path).initialize({})
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
