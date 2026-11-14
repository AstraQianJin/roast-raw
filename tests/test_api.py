"""API, SQLite, calendar, and real-process persistence contracts for Roast Raw."""

import copy
import json
import os
from contextlib import closing, contextmanager
from datetime import date, datetime, time as daytime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.calendar import calendar_state
from server.app.validation import validate_plan

PLAN_PATH = ROOT / 'data' / 'plan.json'
REQUIRED_TABLES = {'cycles', 'plans', 'logs', 'readiness', 'archives', 'body_metrics', 'questionnaires'}
LOG_FIELDS = ('load', 'sets', 'reps', 'rpe', 'note')
SHANGHAI_OFFSET = timezone(timedelta(hours=8))


def log_key(row):
    return f"{row['week']}|{row['day']}|{row['seq']}"


def actual_payload(plan, row, **changes):
    payload = {
        'cycle_id': plan['meta']['planId'],
        'week': row['week'], 'day': row['day'], 'seq': row['seq'],
        'load': 100.0, 'sets': 2, 'reps': 5, 'rpe': 8.0,
        'note': 'Actual working sets',
    }
    payload.update(changes)
    return payload


def fields_only(payload):
    return {field: payload[field] for field in LOG_FIELDS}


def rounded_tenth(value):
    return float(Decimal(str(round(value, 4))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


@contextmanager
def open_db(path):
    with closing(sqlite3.connect(path, timeout=2)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        with db:
            yield db


def seed_historical_log(path, cycle_id, row, payload):
    # Historical fixtures precede the read-only boundary; they are not live saves.
    key = log_key(row)
    stamp = '2026-11-01T00:00:00+00:00'
    with open_db(path) as db:
        db.execute('INSERT INTO logs_journal(cycle_id,key,payload,created_at) VALUES(?,?,?,?)',
                   (cycle_id, key, json.dumps(payload), stamp))
        db.execute('INSERT INTO logs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   (cycle_id, key, row['date'], f"{row['week']}|{row['day']}", row['movementId'],
                    payload['load'], payload['reps'], payload['rpe'], payload['sets'], payload['note'], stamp))
    return {'key': key, **payload, 'updated_at': stamp}


def database_rows(path):
    """Compare logical data, not WAL/checkpoint bookkeeping or file timestamps."""
    with open_db(path) as db:
        tables = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        return {
            table: db.execute('SELECT * FROM "' + table.replace('"', '""') + '" ORDER BY rowid').fetchall()
            for table in tables
        }


def local_noon(value):
    return datetime.combine(date.fromisoformat(value), daytime(12), SHANGHAI_OFFSET)


class GeneratedPlanCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Generated assets are prerequisites, not silently skipped or replaced fixtures.
        cls.seed = json.loads(PLAN_PATH.read_text(encoding='utf-8'))
        validate_plan(cls.seed, file='plan.json', lib=None)

    def main_row(self):
        rows = [row for row in self.seed['workouts'] if row['bucket'] == 'main' and row['sets'] > 0]
        self.assertTrue(rows, 'The generated plan must contain a positive-set main lift')
        return rows[0]

    def assert_timestamp(self, value):
        self.assertIsInstance(value, str)
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset(), timedelta(0))


class APITests(GeneratedPlanCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='roast-raw-api-')
        self.addCleanup(temporary.cleanup)
        self.db_path = Path(temporary.name) / 'test.sqlite3'
        # main also constructs a module-level app: isolate that import as well.
        with patch.dict(os.environ, {'RR_DB_PATH': str(self.db_path)}):
            from server.app.main import create_app
            self.app = create_app(db_path=self.db_path, plan_path=PLAN_PATH)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.row = self.main_row()
        self.cycle_id = self.seed['meta']['planId']

    def get_json(self, path, **kwargs):
        response = self.client.get(path, **kwargs)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def put_log(self, payload):
        response = self.client.put('/api/log', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.assertEqual(saved['key'], f"{payload['week']}|{payload['day']}|{payload['seq']}")
        self.assertEqual({key: saved[key] for key in LOG_FIELDS}, fields_only(payload))
        self.assert_timestamp(saved['updated_at'])
        return saved

    def archive_fixture(self, status='archived'):
        """Seed history directly because this API intentionally has no cycle-write route."""
        archived = copy.deepcopy(self.seed)
        archived['meta']['planId'] = self.cycle_id + '-' + status
        archived['meta']['name'] = 'Historical test cycle'
        meta = archived['meta']
        with open_db(self.db_path) as db:
            db.execute(
                'INSERT INTO cycles(id,name,start_date,end_date,status,schema_version) VALUES(?,?,?,?,?,?)',
                (meta['planId'], meta['name'], meta['startDate'], meta['endDate'], status, archived['schemaVersion']),
            )
            db.execute(
                'INSERT INTO plans(id,cycle_id,json,version,created_at) VALUES(?,?,?,?,?)',
                (meta['planId'], meta['planId'], json.dumps(archived), archived['schemaVersion'],
                 '2026-01-01T00:00:00+00:00'),
            )
        return archived

    def test_health_plan_and_cycles_are_read_only(self):
        before = database_rows(self.db_path)
        self.assertEqual(self.get_json('/api/health'), {
            'status': 'ok', 'version': f"0.{int(json.loads((ROOT / 'web/package.json').read_text(encoding='utf-8'))['version'].split('.')[2]):02d}", 'timezone': 'Asia/Shanghai', 'storage': 'SQLite',
        })
        self.assertEqual(self.get_json('/api/plan'), self.seed)
        self.assertEqual(self.get_json('/api/plan', params={'cycle_id': self.cycle_id}), self.seed)
        cycles = self.get_json('/api/cycle')
        self.assertEqual(cycles['active_cycle_id'], self.cycle_id)
        self.assertEqual(len(cycles['cycles']), 1)
        self.assertEqual(cycles['cycles'][0], {
            'id': self.cycle_id, 'name': self.seed['meta']['name'],
            'start_date': self.seed['meta']['startDate'], 'end_date': self.seed['meta']['endDate'],
            'status': 'active', 'schema_version': self.seed['schemaVersion'],
        })
        self.assertEqual(self.get_json('/api/log'), {'cycle_id': self.cycle_id, 'logs': {}})
        self.assertEqual(database_rows(self.db_path), before)

    def test_geometry_matches_generated_asset_without_writes(self):
        before = database_rows(self.db_path)
        expected = json.loads((ROOT / 'data' / 'muscle_geo.json').read_text(encoding='utf-8'))
        self.assertTrue(expected, 'Generated geometry must not be empty')
        self.assertEqual(self.get_json('/api/geometry'), expected)
        self.assertEqual(database_rows(self.db_path), before)

    def test_plan_validation_is_contractual_and_never_persists(self):
        self.put_log(actual_payload(self.seed, self.row))
        before = database_rows(self.db_path)
        response = self.client.post('/api/plan/validate', json=self.seed)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {
            'valid': True, 'persisted': False, 'schemaVersion': self.seed['schemaVersion'],
        })
        self.assertEqual(database_rows(self.db_path), before)
        response = self.client.post('/api/plan/validate', json={})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertTrue(response.json()['errors'])
        self.assertEqual(database_rows(self.db_path), before)
        response = self.client.post('/api/plan/validate', content='{', headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(database_rows(self.db_path), before)
        self.assertEqual(self.get_json('/api/plan'), self.seed)

    def test_analysis_plan_and_empty_log_modes(self):
        before = database_rows(self.db_path)
        planned = self.get_json('/api/analysis')
        self.assertEqual(planned, self.get_json('/api/analysis', params={'mode': 'plan'}))
        self.assertEqual(planned['schema'], 'RPL-Analysis-v1')
        self.assertEqual(planned['mode'], 'plan')
        self.assertEqual(planned['weeks'], len(self.seed['weeks']))
        self.assertEqual([week['n'] for week in planned['perWeek']], [week['n'] for week in self.seed['weeks']])
        self.assertEqual(planned['unresolved'], [])
        self.assertEqual(planned['cycle']['total'], sum(row['sets'] for row in self.seed['workouts']))
        self.assertEqual(planned['cycle']['tonnageKg'], rounded_tenth(sum(row['tonnageKg'] for row in self.seed['workouts'])))
        self.assertTrue(planned['leafOrder'])
        self.assertEqual(set(planned['cycle']['leaves']), set(planned['leafOrder']))
        for week in planned['perWeek']:
            self.assertEqual(week['total'], sum(row['sets'] for row in self.seed['workouts'] if row['week'] == week['n']))
        logged = self.get_json('/api/analysis', params={'mode': 'log'})
        self.assertEqual(logged['mode'], 'log')
        # Unlogged rows retain their prescription; completion is still zero.
        self.assertEqual(logged['cycle'], planned['cycle'])
        self.assertEqual(logged['perWeek'], planned['perWeek'])
        self.assertTrue(all(value == 0 for value in logged['completion']['actual'].values()))
        response = self.client.get('/api/analysis', params={'mode': 'unknown'})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(database_rows(self.db_path), before)

    def test_actual_sets_update_analysis_without_changing_plan(self):
        planned = self.get_json('/api/analysis', params={'mode': 'plan'})
        payload = actual_payload(self.seed, self.row, sets=self.row['sets'] + 1, load=112.5, reps=4, rpe=None)
        saved = self.put_log(payload)
        self.assertEqual(self.get_json('/api/log'), {
            'cycle_id': self.cycle_id,
            'logs': {saved['key']: {key: value for key, value in saved.items() if key != 'key'}},
        })
        logged = self.get_json('/api/analysis', params={'mode': 'log'})
        self.assertEqual(logged['cycle']['total'], planned['cycle']['total'] - self.row['sets'] + payload['sets'])
        expected_kg = sum(row['tonnageKg'] for row in self.seed['workouts']) - self.row['tonnageKg']
        expected_kg += payload['load'] * payload['sets'] * payload['reps']
        self.assertEqual(logged['cycle']['tonnageKg'], rounded_tenth(expected_kg))
        self.assertEqual(logged['completion']['actual'], {
            'main': payload['sets'], 'sbdVar': 0, 'nonSbdVar': 0, 'accessory': 0,
        })
        self.assertEqual(logged['completion']['planned'], planned['completion']['planned'])
        main_planned = sum(row['sets'] for row in self.seed['workouts'] if row['bucket'] == 'main')
        self.assertEqual(logged['completion']['main'], rounded_tenth(payload['sets'] / main_planned * 100))
        self.assertEqual(self.get_json('/api/plan'), self.seed)
        # Completion changes in either mode, but prescribed volumes do not.
        unchanged = self.get_json('/api/analysis', params={'mode': 'plan'})
        self.assertEqual(unchanged['cycle'], planned['cycle'])
        self.assertEqual(unchanged['perWeek'], planned['perWeek'])

    def test_zero_sets_are_saved_and_not_replaced_by_planned_sets(self):
        self.put_log(actual_payload(self.seed, self.row))
        saved = self.put_log(actual_payload(self.seed, self.row, sets=0, reps=0, load=None, rpe=None, note='Skipped'))
        self.assertEqual(self.get_json('/api/log')['logs'][saved['key']]['sets'], 0)
        logged = self.get_json('/api/analysis', params={'mode': 'log'})
        self.assertEqual(logged['cycle']['total'], sum(row['sets'] for row in self.seed['workouts']) - self.row['sets'])
        self.assertEqual(logged['cycle']['tonnageKg'], rounded_tenth(
            sum(row['tonnageKg'] for row in self.seed['workouts']) - self.row['tonnageKg']))
        self.assertEqual(logged['completion']['actual']['main'], 0)
        with open_db(self.db_path) as db:
            self.assertEqual(db.execute('SELECT set_count,reps,load,rpe FROM logs').fetchall(), [(0, 0, None, None)])
            self.assertEqual(db.execute('SELECT count(*) FROM logs_journal').fetchone()[0], 2)

    def test_accessory_accepts_null_load_and_optional_rpe(self):
        rows = [row for row in self.seed['workouts'] if row['bucket'] == 'accessory']
        self.assertTrue(rows, 'The generated plan must contain an accessory')
        payload = actual_payload(self.seed, rows[0], sets=3, reps=10, load=None, rpe=None)
        self.put_log(payload)
        logged = self.get_json('/api/analysis', params={'mode': 'log'})
        self.assertEqual(logged['completion']['actual']['accessory'], 3)
        self.assertEqual(logged['cycle']['tonnageKg'], rounded_tenth(
            sum(row['tonnageKg'] for row in self.seed['workouts']) - rows[0]['tonnageKg']))

    def test_optional_note_defaults_to_empty_string(self):
        payload = actual_payload(self.seed, self.row)
        del payload['note']
        response = self.client.put('/api/log', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['note'], '')
        self.assertEqual(self.get_json('/api/log')['logs'][log_key(self.row)]['note'], '')

    def test_invalid_values_are_422_and_do_not_write(self):
        baseline_payload = actual_payload(self.seed, self.row)
        self.put_log(baseline_payload)
        before = database_rows(self.db_path)
        cases = []
        for field in ('week', 'seq', 'sets', 'reps'):
            for value in (-1, 1.5, True, False, '2', None):
                cases.append((f'{field}={value!r}', {field: value}))
        for field in ('week', 'seq'):
            cases.append((f'{field}=0', {field: 0}))
        for field in ('load', 'rpe'):
            for value in (True, False, '8'):
                cases.append((f'{field}={value!r}', {field: value}))
        cases.extend([
            ('negative load', {'load': -0.5}),
            ('RPE below minimum', {'rpe': 5.49}),
            ('RPE above maximum', {'rpe': 10.01}),
            ('positive sets without reps', {'sets': 1, 'reps': 0}),
            ('main lift without load', {'load': None}),
            ('null cycle', {'cycle_id': None}),
            ('empty cycle', {'cycle_id': ''}),
            ('null day', {'day': None}),
            ('empty day', {'day': ''}),
            ('null note', {'note': None}),
            ('non-string note', {'note': 123}),
            ('oversize note', {'note': 'x' * 2001}),
            ('unknown field', {'unexpected': 'must not be ignored'}),
            ('client timestamp', {'updated_at': '2026-01-01T00:00:00+00:00'}),
        ])
        for label, changes in cases:
            with self.subTest(label=label):
                response = self.client.put('/api/log', json={**baseline_payload, **changes})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(database_rows(self.db_path), before)
        for field in ('cycle_id', 'week', 'day', 'seq', 'load', 'sets', 'reps', 'rpe'):
            with self.subTest(missing=field):
                payload = dict(baseline_payload)
                del payload[field]
                response = self.client.put('/api/log', json=payload)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(database_rows(self.db_path), before)

    def test_nonfinite_numbers_are_422_and_never_write(self):
        payload = actual_payload(self.seed, self.row)
        self.put_log(payload)
        before = database_rows(self.db_path)
        for field in ('week', 'seq', 'sets', 'reps', 'load', 'rpe'):
            for value in (float('nan'), float('inf'), float('-inf')):
                with self.subTest(field=field, value=str(value)):
                    # Raw JSON bypasses the HTTP client's own nonfinite-number guard.
                    response = self.client.put('/api/log', content=json.dumps({**payload, field: value}, allow_nan=True),
                                               headers={'Content-Type': 'application/json'})
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual(database_rows(self.db_path), before)

    def test_invalid_json_and_non_object_log_bodies_do_not_write(self):
        self.put_log(actual_payload(self.seed, self.row))
        before = database_rows(self.db_path)
        for body in ('{', 'null', '[]', '"not an object"'):
            with self.subTest(body=body):
                response = self.client.put('/api/log', content=body, headers={'Content-Type': 'application/json'})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(database_rows(self.db_path), before)

    def test_unknown_rows_and_cycles_are_404_without_writes(self):
        payload = actual_payload(self.seed, self.row)
        self.put_log(payload)
        before = database_rows(self.db_path)
        changes = [
            {'cycle_id': self.cycle_id + '-does-not-exist'},
            {'week': max(row['week'] for row in self.seed['workouts']) + 1},
            {'day': '__unknown_day__'},
            {'seq': max(row['seq'] for row in self.seed['workouts']) + 1},
        ]
        for change in changes:
            with self.subTest(change=change):
                response = self.client.put('/api/log', json={**payload, **change})
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual(database_rows(self.db_path), before)
        for path in ('/api/plan', '/api/log', '/api/analysis'):
            with self.subTest(path=path):
                response = self.client.get(path, params={'cycle_id': self.cycle_id + '-does-not-exist'})
                self.assertEqual(response.status_code, 404, response.text)
                self.assertEqual(database_rows(self.db_path), before)

    def test_last_write_wins_but_every_save_appends_immutable_journal(self):
        first = actual_payload(self.seed, self.row, sets=2, reps=5, load=100.0, rpe=7.0, note='First')
        second = actual_payload(self.seed, self.row, sets=4, reps=3, load=120.5, rpe=9.5, note='Replacement')
        stamps = ['2026-01-01T00:00:00+00:00', '2026-01-01T00:00:01+00:00', '2026-01-01T00:00:02+00:00']
        with patch('server.app.store.timestamp', side_effect=stamps):
            saved_first = self.put_log(first)
            with open_db(self.db_path) as db:
                journal_first = db.execute('SELECT * FROM logs_journal ORDER BY id').fetchall()
            self.put_log(second)
            saved_last = self.put_log(second)
        self.assertEqual(saved_first['updated_at'], stamps[0])
        self.assertEqual(saved_last['updated_at'], stamps[2])
        self.assertEqual(self.get_json('/api/log')['logs'], {
            log_key(self.row): {**fields_only(second), 'updated_at': stamps[2]},
        })
        with open_db(self.db_path) as db:
            self.assertEqual(db.execute(
                'SELECT cycle_id,key,date,session_id,exercise_id,load,reps,rpe,set_count,note,updated_at FROM logs'
            ).fetchall(), [(
                self.cycle_id, log_key(self.row), self.row['date'], f"{self.row['week']}|{self.row['day']}",
                self.row['movementId'], second['load'], second['reps'], second['rpe'], second['sets'], second['note'], stamps[2],
            )])
            journal = db.execute('SELECT * FROM logs_journal ORDER BY id').fetchall()
            self.assertEqual(journal[:1], journal_first)
            entries = db.execute('SELECT cycle_id,key,payload,created_at FROM logs_journal ORDER BY id').fetchall()
        self.assertEqual(len(entries), 3)
        for entry, payload, stamp in zip(entries, (first, second, second), stamps):
            self.assertEqual(entry[:2], (self.cycle_id, log_key(self.row)))
            self.assertEqual(json.loads(entry[2]), fields_only(payload))
            self.assertEqual(entry[3], stamp)

    def test_sql_schema_and_unique_active_cycle_constraint(self):
        with open_db(self.db_path) as db:
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue(REQUIRED_TABLES <= tables, f'Missing required tables: {REQUIRED_TABLES - tables}')
            self.assertIn('logs_journal', tables)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 5)
            self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0].lower(), 'wal')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            for table in ('plans', 'logs', 'logs_journal', 'readiness', 'archives', 'body_metrics'):
                with self.subTest(table=table):
                    foreign_keys = db.execute(f'PRAGMA foreign_key_list({table})').fetchall()
                    self.assertTrue(any(row[2:5] == ('cycles', 'cycle_id', 'id') for row in foreign_keys))
        before = database_rows(self.db_path)
        with self.assertRaises(sqlite3.IntegrityError):
            with open_db(self.db_path) as db:
                db.execute(
                    'INSERT INTO cycles(id,name,start_date,end_date,status,schema_version) VALUES(?,?,?,?,?,?)',
                    (self.cycle_id + '-second-active', 'Duplicate active', self.seed['meta']['startDate'],
                     self.seed['meta']['endDate'], 'active', self.seed['schemaVersion']),
                )
        self.assertEqual(database_rows(self.db_path), before)
        archived = self.archive_fixture()
        before = database_rows(self.db_path)
        with self.assertRaises(sqlite3.IntegrityError):
            with open_db(self.db_path) as db:
                db.execute("UPDATE cycles SET status='active' WHERE id=?", (archived['meta']['planId'],))
        self.assertEqual(database_rows(self.db_path), before)

    def test_journal_and_log_write_rollback_together_on_sql_failure(self):
        payload = actual_payload(self.seed, self.row)
        # First fail insertion; then fail the UPSERT update of an existing row.
        for event in ('INSERT', 'UPDATE'):
            with self.subTest(event=event):
                before = database_rows(self.db_path)
                with open_db(self.db_path) as db:
                    db.execute(f"CREATE TRIGGER reject_log_write BEFORE {event} ON logs "
                               "BEGIN SELECT RAISE(ABORT, 'injected test log failure'); END")
                try:
                    response = self.client.put('/api/log', json={**payload, 'sets': 7})
                    self.assertEqual(response.status_code, 500, response.text)
                    # The journal INSERT precedes the failed write and must roll back too.
                    self.assertEqual(database_rows(self.db_path), before)
                finally:
                    with open_db(self.db_path) as db:
                        db.execute('DROP TRIGGER reject_log_write')
                self.put_log(payload)
        with open_db(self.db_path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM logs').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM logs_journal').fetchone()[0], 2)

    def test_archived_and_completed_cycles_are_read_only(self):
        for status in ('archived', 'completed'):
            with self.subTest(status=status):
                archived = self.archive_fixture(status)
                cycle_id = archived['meta']['planId']
                self.assertEqual(self.get_json('/api/plan', params={'cycle_id': cycle_id}), archived)
                before = database_rows(self.db_path)
                response = self.client.put('/api/log', json=actual_payload(archived, self.row))
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(database_rows(self.db_path), before)
        self.assertEqual(self.get_json('/api/cycle')['active_cycle_id'], self.cycle_id)

    def test_same_row_key_in_two_cycles_never_conflates_logs_or_analysis(self):
        archived = self.archive_fixture()
        archive_id = archived['meta']['planId']
        archive_fields = fields_only(actual_payload(archived, self.row, sets=1, load=80.0, note='Historical'))
        saved_archive = seed_historical_log(self.db_path, archive_id, self.row, archive_fields)
        archive_logs = {'cycle_id': archive_id, 'logs': {
            saved_archive['key']: {key: value for key, value in saved_archive.items() if key != 'key'},
        }}
        self.assertEqual(self.get_json('/api/log'), {'cycle_id': self.cycle_id, 'logs': {}})
        self.assertEqual(self.get_json('/api/analysis', params={'mode': 'log'})['completion']['actual']['main'], 0)
        self.put_log(actual_payload(self.seed, self.row, sets=3, load=110.0, note='Current'))
        self.assertEqual(self.get_json('/api/log', params={'cycle_id': archive_id}), archive_logs)
        self.assertEqual(self.get_json('/api/log')['logs'][log_key(self.row)]['sets'], 3)
        self.assertEqual(self.get_json('/api/log', params={'cycle_id': self.cycle_id}), self.get_json('/api/log'))
        self.assertEqual(self.get_json('/api/plan'), self.seed)
        for cycle_id, count in ((self.cycle_id, 3), (archive_id, 1)):
            analysis = self.get_json('/api/analysis', params={'mode': 'log', 'cycle_id': cycle_id})
            self.assertEqual(analysis['completion']['actual']['main'], count)
        before = database_rows(self.db_path)
        response = self.client.put('/api/log', json=actual_payload(archived, self.row, sets=9))
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(database_rows(self.db_path), before)
        with open_db(self.db_path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM logs WHERE key=?', (log_key(self.row),)).fetchone()[0], 2)
            self.assertEqual(dict(db.execute('SELECT cycle_id,count(*) FROM logs_journal GROUP BY cycle_id')),
                             {self.cycle_id: 1, archive_id: 1})

    def performance_entries(self, plan=None, cycle_id=None):
        source = self.seed if plan is None else plan
        params = {} if cycle_id is None else {'cycle_id': cycle_id}
        result = self.get_json('/api/performance', params=params)
        self.assertEqual(set(result), {'movements'})
        self.assertIsInstance(result['movements'], list)
        entries = {entry['id']: entry for entry in result['movements']}
        self.assertEqual(len(entries), len(result['movements']), 'Movement IDs must be unique')
        self.assertEqual(set(entries), {row['movementId'] for row in source['workouts']})
        for entry in entries.values():
            self.assertEqual(set(entry), {'id', 'name', 'lift', 'system', 'weekly'})
            names = {row['movement'] for row in source['workouts'] if row['movementId'] == entry['id']}
            self.assertEqual(names, {entry['name']})
            self.assertIsInstance(entry['system'], bool)
            self.assertEqual([point['n'] for point in entry['weekly']], [week['n'] for week in source['weeks']])
            for point in entry['weekly']:
                self.assertEqual(set(point), {'n', 'value', 'estimated', 'method', 'date', 'key', 'load', 'reps', 'rpe'})
        return entries

    def assert_performance_week(self, entry, row, payload=None, value=None, estimated=None):
        point = next(point for point in entry['weekly'] if point['n'] == row['week'])
        if payload is None:
            self.assertEqual(point, {
                'n': row['week'], 'value': None, 'estimated': None, 'method': None,
                'date': None, 'key': None, 'load': None, 'reps': None, 'rpe': None,
            })
            return
        self.assertEqual({field: item for field, item in point.items() if field != 'method'}, {
            'n': row['week'], 'value': value, 'estimated': estimated,
            'date': row['date'], 'key': log_key(row), 'load': payload['load'],
            'reps': payload['reps'], 'rpe': payload['rpe'],
        })
        self.assertIs(point['estimated'], estimated)
        if estimated:
            self.assertIsInstance(point['method'], str)
            self.assertIn('Epley', point['method'])
        else:
            self.assertEqual(point['method'], 'Actual single')

    def test_performance_without_logs_has_explicit_nulls_and_never_writes(self):
        plan_before = self.get_json('/api/plan')
        prescription_before = self.get_json('/api/prescription', params={'cycle_id': self.cycle_id})
        before = database_rows(self.db_path)
        entries = self.performance_entries()
        self.assertEqual(self.performance_entries(cycle_id=self.cycle_id), entries)
        for entry in entries.values():
            for week in self.seed['weeks']:
                self.assert_performance_week(entry, {'week': week['n']})
        self.assertEqual(database_rows(self.db_path), before)
        self.assertEqual(self.get_json('/api/plan'), plan_before)
        self.assertEqual(self.get_json('/api/prescription', params={'cycle_id': self.cycle_id}), prescription_before)

    def test_performance_uses_independent_actual_load_anchors_without_updating_references(self):
        plan_before = self.get_json('/api/plan')
        prescription_before = self.get_json('/api/prescription', params={'cycle_id': self.cycle_id})
        # Hardcoded arithmetic anchors: never derive expectations from the stats engine.
        for load, reps, rpe, value, estimated in (
                (100, 3, None, 110, True),
                (101.25, 1, 9, 101.25, False),
                (100, 10, 8, 133.3, True)):
            with self.subTest(load=load, reps=reps):
                payload = actual_payload(self.seed, self.row, load=load, reps=reps, rpe=rpe)
                self.put_log(payload)
                before = database_rows(self.db_path)
                logs_before = self.get_json('/api/log')
                entries = self.performance_entries()
                self.assertEqual(self.performance_entries(cycle_id=self.cycle_id), entries)
                self.assert_performance_week(entries[self.row['movementId']], self.row, payload, value, estimated)
                for entry in entries.values():
                    for week in self.seed['weeks']:
                        if entry['id'] != self.row['movementId'] or week['n'] != self.row['week']:
                            self.assert_performance_week(entry, {'week': week['n']})
                self.assertEqual(database_rows(self.db_path), before)
                self.assertEqual(self.get_json('/api/log'), logs_before)
                self.assertEqual(self.get_json('/api/plan'), plan_before)
                self.assertEqual(self.get_json('/api/prescription', params={'cycle_id': self.cycle_id}), prescription_before)

    def test_performance_power_clean_pull_up_and_ohp_use_their_recorded_loads(self):
        rows = {}
        for name in ('Power Clean', 'Pull-Up', 'OHP'):
            matches = [row for row in self.seed['workouts'] if row['movement'] == name and row['sets'] > 0]
            self.assertTrue(matches, f'The generated plan must retain {name}')
            rows[name] = matches[0]
        plan_before = self.get_json('/api/plan')
        prescription_before = self.get_json('/api/prescription', params={'cycle_id': self.cycle_id})
        clean = rows['Power Clean']
        self.put_log(actual_payload(self.seed, clean, load=70, reps=3, rpe=None))
        pull = actual_payload(self.seed, rows['Pull-Up'], load=100, reps=3, rpe=None)
        ohp = actual_payload(self.seed, rows['OHP'], load=60, reps=5, rpe=8)
        self.put_log(pull)
        self.put_log(ohp)
        before = database_rows(self.db_path)
        entries = self.performance_entries()
        self.assert_performance_week(entries[clean['movementId']], clean)
        self.assert_performance_week(entries[rows['Pull-Up']['movementId']], rows['Pull-Up'], pull, 110, True)
        self.assert_performance_week(entries[rows['OHP']['movementId']], rows['OHP'], ohp, 70, True)
        self.assertEqual(entries[rows['Pull-Up']['movementId']]['lift'], 'D')
        self.assertIs(entries[rows['Pull-Up']['movementId']]['system'], True)
        self.assertEqual(entries[rows['OHP']['movementId']]['lift'], 'B')
        self.assertIs(entries[rows['OHP']['movementId']]['system'], False)
        self.assertEqual(database_rows(self.db_path), before)
        single = actual_payload(self.seed, clean, load=70, reps=1, rpe=9)
        self.put_log(single)
        before = database_rows(self.db_path)
        entries = self.performance_entries()
        self.assert_performance_week(entries[clean['movementId']], clean, single, 70, False)
        self.assertEqual(database_rows(self.db_path), before)
        self.assertEqual(self.get_json('/api/plan'), plan_before)
        self.assertEqual(self.get_json('/api/prescription', params={'cycle_id': self.cycle_id}), prescription_before)

    def test_performance_null_load_and_zero_sets_remove_observations_without_fallback(self):
        matches = [row for row in self.seed['workouts']
                   if row['movement'] == 'OHP' and row['bucket'] == 'accessory' and row['sets'] > 0]
        self.assertTrue(matches, 'The legacy fixture must retain an optional-load OHP row')
        optional = matches[0]
        self.put_log(actual_payload(self.seed, optional, load=60, reps=5))
        self.put_log(actual_payload(self.seed, self.row, load=100, reps=3))
        entries = self.performance_entries()
        self.assertEqual(next(point['value'] for point in entries[optional['movementId']]['weekly']
                              if point['n'] == optional['week']), 70)
        self.assertEqual(next(point['value'] for point in entries[self.row['movementId']]['weekly']
                              if point['n'] == self.row['week']), 110)
        self.put_log(actual_payload(self.seed, optional, load=None, reps=5, rpe=None))
        # Positive load/reps deliberately remain: explicit zero sets must still win.
        self.put_log(actual_payload(self.seed, self.row, sets=0, load=200, reps=3, rpe=9))
        plan_before = self.get_json('/api/plan')
        prescription_before = self.get_json('/api/prescription', params={'cycle_id': self.cycle_id})
        before = database_rows(self.db_path)
        entries = self.performance_entries()
        for entry in entries.values():
            for week in self.seed['weeks']:
                self.assert_performance_week(entry, {'week': week['n']})
        self.assertEqual(self.get_json('/api/log')['logs'][log_key(optional)]['load'], None)
        self.assertEqual(self.get_json('/api/log')['logs'][log_key(self.row)]['sets'], 0)
        self.assertEqual(database_rows(self.db_path), before)
        self.assertEqual(self.get_json('/api/plan'), plan_before)
        self.assertEqual(self.get_json('/api/prescription', params={'cycle_id': self.cycle_id}), prescription_before)

    def test_performance_archived_selectors_isolate_same_key_and_use_historical_plan(self):
        for status in ('archived', 'completed'):
            with self.subTest(status=status):
                archived = self.archive_fixture(status)
                archive_id = archived['meta']['planId']
                # Distinct historical dates expose an endpoint that uses the active plan.
                def shift(value):
                    return (date.fromisoformat(value) - timedelta(days=364)).isoformat()

                for field in ('startDate', 'endDate'):
                    archived['meta'][field] = shift(archived['meta'][field])
                for week in archived['weeks']:
                    for field in ('dateStart', 'dateEnd'):
                        week[field] = shift(week[field])
                for row in archived['workouts']:
                    row['date'] = shift(row['date'])
                with open_db(self.db_path) as db:
                    db.execute('UPDATE cycles SET start_date=?,end_date=? WHERE id=?',
                               (archived['meta']['startDate'], archived['meta']['endDate'], archive_id))
                    db.execute('UPDATE plans SET json=? WHERE cycle_id=?', (json.dumps(archived), archive_id))
                archive_row = next(row for row in archived['workouts'] if log_key(row) == log_key(self.row))
                historical = actual_payload(archived, archive_row, load=101.25, reps=1, rpe=9)
                seed_historical_log(self.db_path, archive_id, archive_row, fields_only(historical))
                if status == 'archived':
                    self.assert_performance_week(self.performance_entries()[self.row['movementId']], self.row)
                current = actual_payload(self.seed, self.row, load=100, reps=3, rpe=None)
                self.put_log(current)
                before = database_rows(self.db_path)
                plan_before = self.get_json('/api/plan')
                active_prescription = self.get_json('/api/prescription', params={'cycle_id': self.cycle_id})
                archive_prescription = self.get_json('/api/prescription', params={'cycle_id': archive_id})
                active = self.performance_entries()
                selected = self.performance_entries(archived, archive_id)
                self.assert_performance_week(active[self.row['movementId']], self.row, current, 110, True)
                self.assert_performance_week(selected[archive_row['movementId']], archive_row, historical, 101.25, False)
                self.assertEqual(self.performance_entries(cycle_id=self.cycle_id), active)
                self.assertEqual(self.performance_entries(archived, archive_id), selected)
                self.assertEqual(self.get_json('/api/plan'), plan_before)
                self.assertEqual(self.get_json('/api/plan', params={'cycle_id': archive_id}), archived)
                self.assertEqual(self.get_json('/api/prescription', params={'cycle_id': self.cycle_id}), active_prescription)
                self.assertEqual(self.get_json('/api/prescription', params={'cycle_id': archive_id}), archive_prescription)
                self.assertEqual(database_rows(self.db_path), before)

    def test_performance_unknown_cycle_is_404_and_route_is_read_only(self):
        self.put_log(actual_payload(self.seed, self.row, load=100, reps=3))
        before = database_rows(self.db_path)
        response = self.client.get('/api/performance', params={'cycle_id': self.cycle_id + '-does-not-exist'})
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(database_rows(self.db_path), before)
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            with self.subTest(method=method):
                response = self.client.request(method, '/api/performance', json={'cycle_id': self.cycle_id})
                self.assertEqual(response.status_code, 405, response.text)
                self.assertEqual(database_rows(self.db_path), before)

    def test_today_uses_shanghai_date_and_is_read_only(self):
        instant = local_noon(self.row['date']).astimezone(timezone.utc)
        before = database_rows(self.db_path)
        with patch('server.app.calendar.datetime') as clock:
            clock.now.return_value = instant
            today = self.get_json('/api/today')
        self.assertEqual(today['date'], self.row['date'])
        self.assertEqual(today['timezone'], 'Asia/Shanghai')
        self.assertEqual(today['status'], 'training')
        self.assertEqual(today['day'], self.row['day'])
        self.assertEqual(today['rows'], [row for row in self.seed['workouts'] if row['date'] == self.row['date']])
        self.assertEqual(database_rows(self.db_path), before)


class CalendarTests(GeneratedPlanCase):
    def setUp(self):
        self.plan = copy.deepcopy(self.seed)
        self.sessions = sorted({(row['date'], row['week'], row['day']) for row in self.plan['workouts']})
        self.assertGreaterEqual(len(self.sessions), 2, 'Calendar tests require at least two generated sessions')

    def test_shanghai_midnight_changes_at_1600_utc_on_previous_date(self):
        training_date = date.fromisoformat(self.sessions[0][0])
        midnight = datetime.combine(training_date, daytime.min, SHANGHAI_OFFSET)
        utc_boundary = midnight.astimezone(timezone.utc)
        self.assertEqual(utc_boundary.hour, 16)
        self.assertEqual(utc_boundary.date(), training_date - timedelta(days=1))
        before = calendar_state(self.plan, {}, utc_boundary - timedelta(microseconds=1))
        after = calendar_state(self.plan, {}, utc_boundary)
        self.assertEqual(before['date'], (training_date - timedelta(days=1)).isoformat())
        self.assertEqual(after['date'], training_date.isoformat())
        self.assertEqual(after['status'], 'training')
        self.assertEqual(after['day'], self.sessions[0][2])
        self.assertEqual(after, calendar_state(self.plan, {}, midnight))
        self.assertEqual(after['timezone'], 'Asia/Shanghai')

    def test_upcoming_training_rest_and_ended_are_date_based(self):
        start = date.fromisoformat(self.plan['meta']['startDate'])
        end = date.fromisoformat(self.plan['meta']['endDate'])
        training_dates = {session[0] for session in self.sessions}
        rest_dates = [start + timedelta(days=offset) for offset in range((end - start).days + 1)
                      if (start + timedelta(days=offset)).isoformat() not in training_dates]
        self.assertTrue(rest_dates, 'The generated plan must include a rest day')
        cases = [
            ((start - timedelta(days=1)).isoformat(), 'upcoming'),
            (self.sessions[0][0], 'training'),
            (rest_dates[0].isoformat(), 'rest'),
            ((end + timedelta(days=1)).isoformat(), 'ended'),
        ]
        for today, expected in cases:
            with self.subTest(status=expected):
                result = calendar_state(self.plan, {}, local_noon(today))
                self.assertEqual(result['status'], expected)
                self.assertEqual(result['date'], today)
                self.assertEqual(result['rows'], [row for row in self.plan['workouts'] if row['date'] == today])
                expected_week = next((week['n'] for week in self.plan['weeks']
                                      if week['dateStart'] <= today <= week['dateEnd']), None)
                self.assertEqual(result['week'], expected_week)
                following = next((session for session in self.sessions if session[0] > today), None)
                self.assertEqual(result['nextSession'], None if following is None else {
                    'date': following[0], 'week': following[1], 'day': following[2],
                })
                if expected != 'training':
                    self.assertIsNone(result['day'])
                    self.assertEqual(result['rows'], [])

    def test_missed_workout_is_incomplete_and_never_slides_to_next_session(self):
        original = copy.deepcopy(self.plan)
        first, second = self.sessions[:2]
        first_key = f'{first[1]}|{first[2]}'
        upcoming = calendar_state(self.plan, {}, local_noon(self.plan['meta']['startDate']) - timedelta(days=1))
        self.assertEqual(upcoming['sessionStates'][first_key], 'scheduled')
        first_day = calendar_state(self.plan, {}, local_noon(first[0]))
        self.assertEqual(first_day['sessionStates'][first_key], 'scheduled')
        on_second = calendar_state(self.plan, {}, local_noon(second[0]))
        self.assertEqual(on_second['sessionStates'][first_key], 'incomplete')
        self.assertEqual(on_second['day'], second[2])
        self.assertEqual(on_second['rows'], [row for row in self.plan['workouts'] if row['date'] == second[0]])
        self.assertEqual(on_second['sessionStates'][f'{second[1]}|{second[2]}'], 'scheduled')
        for day_offset in range(1, (date.fromisoformat(second[0]) - date.fromisoformat(first[0])).days):
            between = calendar_state(self.plan, {}, local_noon(first[0]) + timedelta(days=day_offset))
            self.assertEqual(between['status'], 'rest')
            self.assertEqual(between['rows'], [])
            self.assertEqual(between['sessionStates'][first_key], 'incomplete')
            self.assertEqual(between['nextSession'], {'date': second[0], 'week': second[1], 'day': second[2]})
        ended = calendar_state(self.plan, {}, local_noon(self.plan['meta']['endDate']) + timedelta(days=7))
        self.assertEqual(ended['status'], 'ended')
        self.assertIsNone(ended['nextSession'])
        self.assertEqual(ended['rows'], [])
        self.assertEqual(ended['sessionStates'][first_key], 'incomplete')
        self.assertEqual(self.plan, original)

    def test_completion_requires_actual_sets_for_every_row_and_stays_session_scoped(self):
        first, second = self.sessions[:2]
        rows = [row for row in self.plan['workouts'] if (row['week'], row['day']) == first[1:]]
        positive = [row for row in rows if row['sets'] > 0]
        self.assertTrue(positive)
        key = f'{first[1]}|{first[2]}'
        after_end = local_noon(self.plan['meta']['endDate']) + timedelta(days=1)
        full = {log_key(row): {'sets': row['sets']} for row in rows}
        partial = copy.deepcopy(full)
        partial[log_key(positive[0])]['sets'] -= 1
        zero = {log_key(row): {'sets': 0} for row in rows}
        for label, logs in (('missing', {}), ('partial', partial), ('zero', zero)):
            with self.subTest(label=label):
                self.assertEqual(calendar_state(self.plan, logs, after_end)['sessionStates'][key], 'incomplete')
        done = calendar_state(self.plan, full, after_end)
        self.assertEqual(done['sessionStates'][key], 'completed')
        self.assertEqual(done['sessionStates'][f'{second[1]}|{second[2]}'], 'incomplete')
        self.assertEqual(full, {log_key(row): {'sets': row['sets']} for row in rows})

    def test_naive_datetime_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'timezone-aware'):
            calendar_state(self.plan, {}, datetime.fromisoformat(self.sessions[0][0]))


class UvicornRestartTests(GeneratedPlanCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='roast-raw-restart-')
        self.addCleanup(temporary.cleanup)
        self.db_path = Path(temporary.name) / 'restart.sqlite3'
        # Do not route loopback requests through machine-level proxy settings.
        self.http = build_opener(ProxyHandler({}))

    def request_json(self, base_url, path, method='GET', payload=None, timeout=2):
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        request = Request(base_url + path, data=data, method=method,
                          headers={'Content-Type': 'application/json'})
        with self.http.open(request, timeout=timeout) as response:
            self.assertEqual(response.status, 200)
            return json.loads(response.read().decode('utf-8'))

    @staticmethod
    def stop_owned_process(process):
        """Signal only this Popen child/group, reap it, and report forced shutdown."""
        if process.poll() is not None:
            return False
        try:
            if os.name == 'nt':
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
        except OSError:
            if process.poll() is None:
                process.terminate()
        try:
            process.wait(timeout=3)
            return False
        except subprocess.TimeoutExpired:
            process.terminate()
        try:
            process.wait(timeout=3)
            return True
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
            return True

    @contextmanager
    def running_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        base_url = f'http://127.0.0.1:{port}'
        environment = os.environ.copy()
        environment['RR_DB_PATH'] = str(self.db_path)
        environment['PYTHONDONTWRITEBYTECODE'] = '1'
        environment['PYTHONPATH'] = str(ROOT) + (os.pathsep + environment['PYTHONPATH'] if environment.get('PYTHONPATH') else '')
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        # A file avoids a full stdout pipe blocking startup or shutdown.
        with tempfile.TemporaryFile(mode='w+b', dir=self.db_path.parent) as output:
            deadline = time.monotonic() + 8.0
            process = subprocess.Popen(
                [sys.executable, '-m', 'uvicorn', 'server.app.main:app', '--host', '127.0.0.1',
                 '--port', str(port), '--lifespan', 'on', '--no-access-log', '--log-level', 'info'],
                cwd=str(ROOT), env=environment, stdout=output, stderr=subprocess.STDOUT,
                creationflags=flags,
            )
            failure = None
            forced = False
            try:
                last_error = 'No health response'
                while True:
                    if process.poll() is not None:
                        raise AssertionError(f'uvicorn exited during startup: {process.returncode}')
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AssertionError(f'uvicorn startup exceeded the 8-second budget: {last_error}')
                    try:
                        health = self.request_json(base_url, '/api/health', timeout=min(0.25, remaining))
                    except (URLError, OSError, ValueError) as error:
                        last_error = repr(error)
                    else:
                        self.assertEqual(health['status'], 'ok')
                        self.assertEqual(health['storage'], 'SQLite')
                        break
                    # Short bounded backoff; the deadline also bounds each HTTP attempt.
                    time.sleep(min(0.05, max(0, deadline - time.monotonic())))
                yield base_url, process
                self.assertIsNone(process.poll(), 'uvicorn exited unexpectedly during requests')
            except Exception as error:
                failure = error
            finally:
                forced = self.stop_owned_process(process)
                output.seek(0)
                captured = output.read().decode('utf-8', errors='replace')
            if failure is not None:
                raise AssertionError(f'{failure}\nCaptured uvicorn output:\n{captured}') from failure
            self.assertFalse(forced, f'uvicorn required forced shutdown. Captured output:\n{captured}')

    def test_log_and_timestamp_survive_real_uvicorn_process_restart(self):
        row = self.main_row()
        payload = actual_payload(self.seed, row, load=117.5, sets=3, reps=4, rpe=8.5, note='Survives process restart')
        with self.running_server() as (base_url, first_process):
            self.assertEqual(self.request_json(base_url, '/api/plan'), self.seed)
            self.assertEqual(self.request_json(base_url, '/api/log'), {'cycle_id': self.seed['meta']['planId'], 'logs': {}})
            saved = self.request_json(base_url, '/api/log', method='PUT', payload=payload)
            self.assertEqual(saved['key'], log_key(row))
            self.assertEqual({key: saved[key] for key in LOG_FIELDS}, fields_only(payload))
            self.assert_timestamp(saved['updated_at'])
            performance_before = self.request_json(base_url, '/api/performance')
            movement = next(entry for entry in performance_before['movements'] if entry['id'] == row['movementId'])
            point = next(point for point in movement['weekly'] if point['n'] == row['week'])
            self.assertEqual((point['value'], point['key'], point['date']), (133.2, log_key(row), row['date']))
            self.assertIs(point['estimated'], True)
            daily_query = f"?cycle_id={self.seed['meta']['planId']}&date={row['date']}&session_id={row['week']}|{row['day']}"
            readiness_payload = {'cycle_id': self.seed['meta']['planId'], 'date': row['date'],
                                 'session_id': f"{row['week']}|{row['day']}", 'recovery': 4, 'arousal': 5, 'nutrition': 6}
            readiness_before = self.request_json(base_url, '/api/readiness', method='PUT', payload=readiness_payload)
            metrics_payload = {'cycle_id': self.seed['meta']['planId'], 'date': row['date'], 'bodyweight': 82.5,
                               'bodyfat': None, 'measurements': {'waist': 80.0}}
            metrics_before = self.request_json(base_url, '/api/body-metrics', method='PUT', payload=metrics_payload)
            review_before = self.request_json(base_url, '/api/review/export')
            before = self.request_json(base_url, '/api/log')
            self.assertEqual(before, {
                'cycle_id': self.seed['meta']['planId'],
                'logs': {log_key(row): {**fields_only(payload), 'updated_at': saved['updated_at']}},
            })
        self.assertIsNotNone(first_process.poll())
        self.assertTrue(self.db_path.is_file())
        persisted = database_rows(self.db_path)
        self.assertEqual(len(persisted['logs']), 1)
        self.assertEqual(len(persisted['logs_journal']), 1)
        with self.running_server() as (base_url, second_process):
            self.assertIsNot(first_process, second_process)
            after = self.request_json(base_url, '/api/log')
            self.assertEqual(after, before)
            self.assertEqual(self.request_json(base_url, '/api/performance'), performance_before)
            review_after = self.request_json(base_url, '/api/review/export')
            for exported in (review_before, review_after):
                exported.pop('exported_at')
                exported.pop('integrity')
            self.assertEqual(review_after, review_before)
            self.assertEqual(self.request_json(base_url, '/api/readiness' + daily_query), readiness_before)
            metrics_query = f"?cycle_id={self.seed['meta']['planId']}&date={row['date']}"
            self.assertEqual(self.request_json(base_url, '/api/body-metrics' + metrics_query), metrics_before)
            self.assertEqual(after['logs'][log_key(row)]['updated_at'], saved['updated_at'])
            self.assertEqual(self.request_json(base_url, '/api/plan'), self.seed)
            cycles = self.request_json(base_url, '/api/cycle')
            self.assertEqual(cycles['active_cycle_id'], self.seed['meta']['planId'])
            self.assertEqual(len(cycles['cycles']), 1)
        self.assertIsNotNone(second_process.poll())
        self.assertEqual(database_rows(self.db_path), persisted)

    def test_import_and_frozen_archive_survive_real_uvicorn_restart(self):
        candidate = copy.deepcopy(self.seed)
        candidate['meta']['planId'] = 'restart-import-cycle'
        candidate['meta']['name'] = 'Restart import cycle'
        row = self.main_row()
        with self.running_server() as (base, first):
            payload = actual_payload(self.seed, row, load=101.25, reps=1, note='Archived actual')
            saved = self.request_json(base, '/api/log', method='PUT', payload=payload)
            upload = {'plan_json': json.dumps(candidate), 'filename': 'restart.json'}
            preview = self.request_json(base, '/api/plan/import/preview', method='POST', payload=upload)
            result = self.request_json(base, '/api/plan/import/confirm', method='POST', payload={
                **upload, 'current_id': preview['currentId'], 'candidate_id': preview['candidateId'], 'confirm': True})
            self.assertEqual(result, {'saved': True, 'active_cycle_id': 'restart-import-cycle',
                                      'archived_cycle_id': self.seed['meta']['planId']})
            archived = self.request_json(base, '/api/review/export?cycle_id=' + self.seed['meta']['planId'])
            self.assertEqual(archived['logs'][0]['load'], 101.25)
            self.assertEqual(archived['logs'][0]['updated_at'], saved['updated_at'])
            self.assertEqual(archived['cycle']['status'], 'archived')
        before = database_rows(self.db_path)
        with self.running_server() as (base, second):
            self.assertIsNot(first, second)
            self.assertEqual(self.request_json(base, '/api/plan'), candidate)
            self.assertEqual(self.request_json(base, '/api/log'), {'cycle_id': 'restart-import-cycle', 'logs': {}})
            self.assertEqual(self.request_json(base, '/api/review/export?cycle_id=' + self.seed['meta']['planId']), archived)
            self.assertEqual(self.request_json(base, '/api/plan?cycle_id=' + self.seed['meta']['planId']), self.seed)
        self.assertEqual(database_rows(self.db_path), before)


if __name__ == '__main__':
    unittest.main()
