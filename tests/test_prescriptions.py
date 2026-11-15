"""Independent prescription, history, concurrency and SQLite migration contracts.

These tests deliberately retain the generated legacy fixture. Expected loads,
classification and transfer factors never come from recalculate().
"""

import copy
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, contextmanager
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PLAN_PATH = ROOT / 'data' / 'plan.json'
POLICY = 'eight-variations-v1'
# Approved product parameters, not values imported from the implementation.
APPROVED = {
    'Low-bar Squat': ('S', .90, 120, False),
    'Wide-grip Bench': ('B', .90, 90, False),
    'Sumo Deadlift': ('D', .85, 120, False),
    'Power Clean': ('D', .15, 70, False),
    'OHP': ('B', .35, 60, False),
    'Pull-Up': ('D', .10, 100, True),
    'Dip': ('B', .60, 105, True),
    'Bent-Over Barbell Row': ('D', .25, 90, False),
}
ALIASES = {'Weighted Pull-Up': 'Pull-Up', 'Weighted Dip': 'Dip'}


def row_key(row):
    return f"{row['week']}|{row['day']}|{row['seq']}"


def canonical_id(plan):
    encoded = json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def round_2_5(reference, percent):
    """Independent decimal arithmetic, including explicit half-up rounding."""
    raw = Decimal(str(reference)) * Decimal(str(percent)) / Decimal('100')
    return float((raw / Decimal('2.5')).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * Decimal('2.5'))


@contextmanager
def open_db(path):
    with closing(sqlite3.connect(path, timeout=2)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        with db:
            yield db


def database_rows(path):
    """Logical rows only: WAL pages, file mtimes and backups are not mutations."""
    with open_db(path) as db:
        tables = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {table: db.execute('SELECT * FROM "' + table.replace('"', '""') +
                                 '" ORDER BY rowid').fetchall() for table in tables}


def database_schema(path):
    with open_db(path) as db:
        return db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master "
                          "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()


def backups(path):
    return set((path.parent / 'backups').glob('*.sqlite3'))


def create_isolated_app(path):
    # Isolate main's module-level app on its first import as well as this factory.
    with patch.dict(os.environ, {'RR_DB_PATH': str(path)}):
        from server.app.main import create_app
        return create_app(db_path=path, plan_path=PLAN_PATH)


class PrescriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='roast-raw-prescription-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'prescriptions.sqlite3'
        self.seed = json.loads(PLAN_PATH.read_text(encoding='utf-8'))
        self.cycle = self.seed['meta']['planId']
        self.app = create_isolated_app(self.path)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def get_json(self, path, **params):
        response = self.client.get(path, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def current(self):
        return self.get_json('/api/prescription', cycle_id=self.cycle)

    def first_row(self, movement, plan=None):
        rows = [row for row in (plan or self.seed)['workouts'] if row['movement'] == movement]
        self.assertTrue(rows, f'Legacy fixture must retain {movement}')
        return rows[0]

    def request_payload(self, references=None):
        current = self.current()
        return {'cycle_id': self.cycle, 'current_id': current['currentId'],
                'references': copy.deepcopy(current['references'] if references is None else references)}

    def preview(self, payload):
        response = self.client.post('/api/prescription/preview', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['currentId'], payload['current_id'])
        self.assertRegex(result['previewId'], r'^[a-f0-9]{64}$')
        self.assertIsInstance(result['changes'], list)
        return result

    def apply(self, references=None):
        payload = self.request_payload(references)
        preview = self.preview(payload)
        response = self.client.post('/api/prescription/apply',
                                    json={**payload, 'preview_id': preview['previewId']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'id': preview['previewId'], 'saved': True})
        applied = self.get_json('/api/plan', cycle_id=self.cycle)
        self.assertEqual(canonical_id(applied), preview['previewId'])
        return applied, payload, preview

    def assert_catalogue(self, catalogue):
        self.assertIsInstance(catalogue, list)
        self.assertEqual({entry['lift'] for entry in catalogue}, {'S', 'B', 'D'})
        groups = {lift: [entry for entry in catalogue if entry['lift'] == lift] for lift in ('S', 'B', 'D')}
        library = json.loads((ROOT / 'data' / 'movements.json').read_text(encoding='utf-8'))
        permitted = {entry['id']: entry for entry in library['movements'] if entry.get('plan_allowed') is True}
        seen_ids, seen_names = set(), set()
        for lift, entries in groups.items():
            for entry in entries:
                self.assertNotIn(entry['id'], seen_ids)
                seen_ids.add(entry['id'])
                self.assertIn(entry['id'], permitted)
                self.assertEqual(entry['name'], permitted[entry['id']]['name_en'])
                self.assertEqual(entry['lift'], lift)
                name = ALIASES.get(entry['name'], entry['name'])
                if name in APPROVED:
                    expected_lift, transfer, reference, system = APPROVED[name]
                    self.assertEqual((entry['lift'], entry['transfer'], entry['default'], entry['system']),
                                     (expected_lift, transfer, reference, system))
                    seen_names.add(name)
                else:
                    self.assertIsNone(entry['transfer'], 'Unapproved movements cannot acquire transfer factors')
                    self.assertIsNone(entry['default'])
        self.assertEqual(seen_names, set(APPROVED))
        return seen_ids

    def save_existing_records(self):
        row = next(row for row in self.seed['workouts'] if row['bucket'] == 'main')
        log = {'cycle_id': self.cycle, 'week': row['week'], 'day': row['day'], 'seq': row['seq'],
               'load': 101.25, 'sets': 2, 'reps': 5, 'rpe': 8.5, 'note': 'Keep the raw actual load'}
        readiness = {'cycle_id': self.cycle, 'date': row['date'], 'session_id': 'daily',
                     'recovery': 1, 'arousal': 4, 'nutrition': 7, 'note': 'Positive recovery'}
        metrics = {'cycle_id': self.cycle, 'date': row['date'], 'bodyweight': 85.,
                   'bodyfat': 18., 'measurements': {'waist': 80.}}
        for path, payload in (('/api/log', log), ('/api/readiness', readiness), ('/api/body-metrics', metrics)):
            response = self.client.put(path, json=payload)
            self.assertEqual(response.status_code, 200, response.text)
        with open_db(self.path) as db:
            db.execute('INSERT INTO readiness(account_id,cycle_id,date,session_id,fatigue,note) VALUES(?,?,?,?,?,?)',
                       (db.execute('SELECT account_id FROM cycles LIMIT 1').fetchone()[0], self.cycle, row['date'],
                        'legacy', 7, 'Fatigue is not recovery'))
        return row

    def assert_snapshot(self, snapshot, rows, version=7):
        with open_db(snapshot) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], version)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(database_rows(snapshot), rows)

    def test_get_defaults_and_preview_are_read_only_with_fresh_current_version(self):
        before = database_rows(self.path)
        before_backups = backups(self.path)
        current = self.current()
        self.assertTrue({'currentId', 'policy', 'references', 'catalogue', 'versions', 'systemLoads'} <= set(current))
        self.assertEqual(current['currentId'], canonical_id(self.seed))
        self.assertEqual(current['policy'], 'legacy')
        self.assertEqual(current['systemLoads'], {})
        ids = self.assert_catalogue(current['catalogue'])
        self.assertEqual(set(current['references']), ids)
        for name, (_, _, reference, _) in APPROVED.items():
            self.assertEqual(current['references'][self.first_row(name)['movementId']], reference)
        for entry in current['catalogue']:
            name = ALIASES.get(entry['name'], entry['name'])
            expected = APPROVED[name][2] if name in APPROVED else None
            self.assertEqual(current['references'][entry['id']], expected)
        self.assertEqual(len(current['versions']), 1)
        self.assertEqual(current['versions'][0]['id'], canonical_id(self.seed))
        self.assertTrue(current['versions'][0]['current'])
        with open_db(self.path) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 7)
        payload = {'cycle_id': self.cycle, 'current_id': current['currentId'], 'references': current['references']}
        preview = self.preview(payload)
        self.assertTrue(preview['changes'])
        self.assertNotEqual(preview['previewId'], current['currentId'])
        self.assertEqual(self.preview(payload), preview, 'The same read-only preview must be deterministic')
        self.assertEqual(self.get_json('/api/plan'), self.seed)
        self.assertEqual(database_rows(self.path), before)
        self.assertEqual(backups(self.path), before_backups)

    def test_apply_has_independent_exact_loads_and_preserves_all_prescribed_identity(self):
        before, before_backups = database_rows(self.path), backups(self.path)
        applied, payload, preview = self.apply()
        self.assertEqual(applied['prescription'], {
            'version': POLICY, 'references': payload['references'], 'basePlan': self.seed})
        self.assertEqual(sum(row['sets'] for row in self.seed['workouts']), 732)
        self.assertEqual(sum(row['sets'] for row in applied['workouts']), 732)
        self.assertEqual(len(applied['workouts']), len(self.seed['workouts']))
        preserved = ('week', 'day', 'date', 'seq', 'rowIndex', 'movementId', 'movement',
                     'category', 'sets', 'reps', 'targetRpe', 'notes', 'mode')
        for original, revised in zip(self.seed['workouts'], applied['workouts']):
            with self.subTest(key=row_key(original)):
                self.assertEqual({key: revised[key] for key in preserved}, {key: original[key] for key in preserved})
                self.assertEqual([(s['sets'], s['reps'], s['unit'], s['amrap']) for s in revised['segments']],
                                 [(s['sets'], s['reps'], s['unit'], s['amrap']) for s in original['segments']])
                if original['movement'] in APPROVED:
                    self.assertEqual((revised['role'], revised['bucket'], revised['lift']),
                                     ('variation', 'sbdVar', APPROVED[original['movement']][0]))
                else:
                    self.assertEqual(revised, original)
        for field in ('schemaVersion', 'source', 'blocks', 'days', 'gpp', 'runPlan', 'testPlan'):
            self.assertEqual(applied.get(field), self.seed.get(field))
        low_original = self.first_row('Low-bar Squat')
        self.assertEqual(low_original['segments'][0]['pct'], 60.7)
        # Original explicit 60.7%, not a percentage inferred from rounded kilograms.
        expected_low = round_2_5(120, Decimal('60.7'))
        self.assertEqual(expected_low, 72.5)
        low = self.first_row('Low-bar Squat', applied)
        self.assertEqual(low['loadKg'], 72.5)
        self.assertEqual(low['segments'][0]['load'], expected_low)
        self.assertEqual(low['segments'][0]['pct'], 60.7)
        # Fixture W1 OHP: 6 reps @6.5 -> RTS slot 10 -> 74%; row: 8 @6.5 -> slot 12 -> 70%.
        # The table cells and final loads are literal independent anchors, not engine output.
        for name, reps, rpe, reference, percent, expected in (
                ('OHP', 6, 6.5, 60, 74, 45.),
                ('Bent-Over Barbell Row', 8, 6.5, 90, 70, 62.5)):
            original, revised = self.first_row(name), self.first_row(name, applied)
            self.assertEqual((original['reps'], original['targetRpe']), (reps, rpe))
            self.assertEqual(round_2_5(reference, percent), expected)
            self.assertEqual(revised['loadKg'], expected)
            self.assertEqual(revised['segments'][0]['load'], expected)
        changed = {change['key']: change for change in preview['changes']}
        self.assertEqual(changed[row_key(low)]['newLoad'], 72.5)
        self.assertEqual(changed[row_key(low)]['percent'], 60.7)
        self.assertEqual(changed[row_key(low)]['basis'], 'Prescribed percentage')
        self.assertEqual(changed[row_key(self.first_row('OHP'))]['newLoad'], 45.)
        self.assertEqual(changed[row_key(self.first_row('OHP'))]['basis'], 'Legacy RTS reps/RPE estimate')
        created = backups(self.path) - before_backups
        self.assertEqual(len(created), 1, 'Each prescription write must take a consistent pre-write snapshot')
        self.assert_snapshot(next(iter(created)), before)

    def test_equivalent_analysis_preserves_raw_volume_muscle_allocation_and_completion(self):
        baseline = self.get_json('/api/analysis')
        applied, _, _ = self.apply()
        analysis = self.get_json('/api/analysis')
        expected = {'S': 0., 'B': 0., 'D': 0.}
        for row in self.seed['workouts']:
            if row['movement'] in APPROVED:
                lift, transfer, _, _ = APPROVED[row['movement']]
                expected[lift] += row['sets'] * transfer
        for lift in expected:
            self.assertAlmostEqual(analysis['cycle']['equivalent'][lift]['var'], expected[lift])
            self.assertEqual(analysis['cycle']['equivalent'][lift]['main'], baseline['cycle']['lifts'][lift]['main'])
            self.assertEqual(analysis['cycle']['equivalent'][lift]['unknown'], 0)
            self.assertAlmostEqual(sum(week['equivalent'][lift]['var'] for week in analysis['perWeek']), expected[lift])
        self.assertEqual(analysis['cycle']['equivalent']['B']['total'], 156.7)
        self.assertEqual(analysis['cycle']['total'], 732)
        self.assertEqual(analysis['cycle']['groups'], baseline['cycle']['groups'])
        self.assertEqual(analysis['cycle']['leaves'], baseline['cycle']['leaves'])
        for week, original in zip(analysis['perWeek'], baseline['perWeek']):
            self.assertEqual(week['total'], original['total'])
            self.assertEqual(week['groups'], original['groups'])
            self.assertEqual(week['leaves'], original['leaves'])
        self.assertEqual(analysis['completion']['var'], 0)
        row = self.first_row('Pull-Up', applied)
        response = self.client.put('/api/log', json={
            'cycle_id': self.cycle, 'week': row['week'], 'day': row['day'], 'seq': row['seq'],
            'load': 90, 'sets': 2, 'reps': 3, 'rpe': None, 'note': ''})
        self.assertEqual(response.status_code, 200, response.text)
        logged = self.get_json('/api/analysis', mode='log')
        self.assertEqual(logged['completion']['actual']['sbdVar'], 2)
        self.assertAlmostEqual(logged['cycle']['equivalent']['D']['var'], expected['D'] - row['sets'] * .1 + .2)
        self.assertEqual(logged['cycle']['total'], 732 - row['sets'] + 2)

    def test_original_restore_preserves_schema_records_and_immutable_history(self):
        row = self.save_existing_records()
        original_id = self.current()['currentId']
        before, schema = database_rows(self.path), database_schema(self.path)
        applied, _, _ = self.apply()
        first_id = canonical_id(applied)
        first_history = database_rows(self.path)['prescription_versions']
        references = copy.deepcopy(applied['prescription']['references'])
        references[self.first_row('OHP')['movementId']] = 70.
        second, _, _ = self.apply(references)
        self.assertNotEqual(canonical_id(second), first_id)
        self.assertEqual(second['prescription']['basePlan'], self.seed)
        version = self.get_json('/api/prescription/version', cycle_id=self.cycle, revision_id=first_id)
        self.assertEqual(version['id'], first_id)
        self.assertEqual(version['plan'], applied)
        self.assertTrue(version['changes'])
        self.assertEqual(self.get_json('/api/prescription/version', cycle_id=self.cycle,
                                      revision_id=original_id)['plan'], self.seed)
        before_restore, prior_backups = database_rows(self.path), backups(self.path)
        response = self.client.post('/api/prescription/restore', json={
            'cycle_id': self.cycle, 'current_id': canonical_id(second), 'revision_id': original_id})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'id': original_id, 'saved': True})
        self.assertEqual(self.get_json('/api/plan'), self.seed)
        after = database_rows(self.path)
        for table, rows in before.items():
            if table not in {'prescription_versions', 'records_journal'}:
                self.assertEqual(after[table], rows, f'Restore must not rewrite {table}')
        self.assertEqual(after['records_journal'][:len(before['records_journal'])], before['records_journal'])
        journal = [json.loads(entry[5]) for entry in after['records_journal'] if entry[3] == 'prescription']
        self.assertEqual([entry['action'] for entry in journal], ['apply', 'apply', 'restore'])
        self.assertEqual(journal[-1], {'action': 'restore', 'from': canonical_id(second), 'to': original_id})
        self.assertEqual(after['prescription_versions'], before_restore['prescription_versions'])
        self.assertEqual(after['prescription_versions'][:len(first_history)], first_history)
        self.assertEqual(database_schema(self.path), schema)
        self.assertEqual(self.get_json('/api/log')['logs'][row_key(row)]['load'], 101.25)
        legacy = self.get_json('/api/readiness', cycle_id=self.cycle, date=row['date'])['legacy']
        self.assertEqual((legacy[0]['fatigue'], legacy[0]['note']), (7, 'Fatigue is not recovery'))
        created = backups(self.path) - prior_backups
        self.assertEqual(len(created), 1)
        self.assert_snapshot(next(iter(created)), before_restore)
        versions = self.current()['versions']
        self.assertEqual({item['id'] for item in versions if item['current']}, {original_id})
        self.assertEqual({item['id'] for item in versions}, {original_id, first_id, canonical_id(second)})

    def test_stale_second_apply_and_tampered_preview_are_conflicts_without_logical_writes(self):
        payload = self.request_payload()
        preview = self.preview(payload)
        forged = ('0' if preview['previewId'][0] != '0' else '1') + preview['previewId'][1:]
        different = copy.deepcopy(payload)
        different['references'][self.first_row('OHP')['movementId']] = 70.
        for body in ({**payload, 'preview_id': forged}, {**different, 'preview_id': preview['previewId']}):
            with self.subTest(body='forged token' if body['preview_id'] == forged else 'changed references'):
                before = database_rows(self.path)
                response = self.client.post('/api/prescription/apply', json=body)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(database_rows(self.path), before)
        self.apply()
        before = database_rows(self.path)
        response = self.client.post('/api/prescription/apply', json={**payload, 'preview_id': preview['previewId']})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(database_rows(self.path), before)
        response = self.client.post('/api/prescription/preview', json=payload)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(database_rows(self.path), before)

    def test_invalid_unknown_missing_boolean_null_negative_and_nonfinite_references_never_write(self):
        payload = self.request_payload()
        preview = self.preview(payload)
        identity = self.first_row('OHP')['movementId']
        unknown = copy.deepcopy(payload['references'])
        unknown['unknown|invented movement'] = 100.
        missing = copy.deepcopy(payload['references'])
        del missing[identity]
        cases = [('unknown', unknown), ('missing', missing)]
        for value in (True, False, None, 0, -1, '60', float('nan'), float('inf'), float('-inf')):
            references = copy.deepcopy(payload['references'])
            references[identity] = value
            cases.append((repr(value), references))
        before = database_rows(self.path)
        for label, references in cases:
            for endpoint in ('preview', 'apply'):
                with self.subTest(value=label, endpoint=endpoint):
                    body = {**payload, 'references': references}
                    if endpoint == 'apply':
                        body['preview_id'] = preview['previewId']
                    # Raw JSON permits testing NaN/Infinity beyond the HTTP client's encoder guard.
                    response = self.client.post('/api/prescription/' + endpoint,
                                                content=json.dumps(body, allow_nan=True),
                                                headers={'Content-Type': 'application/json'})
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertTrue(response.json()['errors'])
                    self.assertTrue(all(error['field'] and error['expected'] for error in response.json()['errors']))
                    self.assertEqual(database_rows(self.path), before)
        self.assertEqual(self.get_json('/api/plan'), self.seed)

    def test_forged_new_policy_sets_dates_coefficients_load_and_classification_have_exact_context(self):
        applied, _, _ = self.apply()
        index = next(i for i, row in enumerate(applied['workouts']) if row['movement'] == 'OHP')
        row = applied['workouts'][index]
        before = database_rows(self.path)
        valid = self.client.post('/api/plan/validate', json=applied)
        self.assertEqual(valid.status_code, 200, valid.text)
        self.assertEqual(valid.json(), {'valid': True, 'persisted': False, 'schemaVersion': 'RPL-Raw-v1'})
        next_date = (date.fromisoformat(row['date']) + timedelta(days=1)).isoformat()
        cases = [
            ('sets', row['sets'] + 1, f'$.workouts.{index}.sets', row['sets']),
            ('date', next_date, f'$.workouts.{index}.date', row['date']),
            ('loadKg', 47.5, f'$.workouts.{index}.loadKg', 45.),
            ('lift', 'S', f'$.workouts.{index}.lift', 'B'),
            ('coefStatus', 'estimated', f'workouts.{index}.coefStatus', "'exact' was expected"),
            ('coef16', {'chest': 1.0}, f'workouts.{index}',
             "Additional properties are not allowed ('coef16' was unexpected)"),
        ]
        for field, value, expected_path, expected in cases:
            with self.subTest(field=field):
                forged = copy.deepcopy(applied)
                forged['workouts'][index][field] = value
                response = self.client.post('/api/plan/validate', json=forged)
                self.assertEqual(response.status_code, 422, response.text)
                errors = response.json()['errors']
                matches = [error for error in errors if error['field'] == expected_path]
                self.assertTrue(matches, f'Expected exact field {expected_path}: {errors}')
                self.assertTrue(any(error['expected'] == expected for error in matches), matches)
                for error in matches:
                    self.assertEqual((error['file'], error['week'], error['day'], error['movement']),
                                     ('request.json', row['week'], row['day'], 'OHP'))
                self.assertEqual(database_rows(self.path), before)
        self.assertEqual(self.get_json('/api/plan'), applied)

    def test_injected_records_journal_failure_rolls_back_plan_and_version_together(self):
        self.save_existing_records()
        payload = self.request_payload()
        preview = self.preview(payload)
        before, before_backups = database_rows(self.path), backups(self.path)
        with open_db(self.path) as db:
            db.execute("CREATE TRIGGER reject_prescription_journal BEFORE INSERT ON records_journal "
                       "WHEN NEW.kind='prescription' BEGIN SELECT RAISE(ABORT,'injected prescription failure'); END")
        try:
            response = self.client.post('/api/prescription/apply',
                                        json={**payload, 'preview_id': preview['previewId']})
            self.assertEqual(response.status_code, 500, response.text)
            self.assertEqual(database_rows(self.path), before)
            self.assertEqual(self.get_json('/api/plan'), self.seed)
            self.assertEqual(self.current()['currentId'], canonical_id(self.seed))
            created = backups(self.path) - before_backups
            self.assertEqual(len(created), 1, 'An aborted write may leave its consistent pre-write snapshot')
            self.assert_snapshot(next(iter(created)), before)
        finally:
            with open_db(self.path) as db:
                db.execute('DROP TRIGGER reject_prescription_journal')
        # Removing only the injected trigger must allow the identical reviewed operation.
        applied, _, _ = self.apply()
        self.assertEqual(canonical_id(applied), preview['previewId'])

    def test_archived_writes_conflict_and_history_is_cycle_scoped(self):
        applied, _, _ = self.apply()
        archived = copy.deepcopy(self.seed)
        archived['meta']['planId'] += '-archived'
        archived_id = archived['meta']['planId']
        archived_revision = canonical_id(archived)
        meta = archived['meta']
        with open_db(self.path) as db:
            db.execute('INSERT INTO cycles(id,name,start_date,end_date,status,schema_version,account_id) VALUES(?,?,?,?,?,?,(SELECT account_id FROM cycles ORDER BY rowid LIMIT 1))',
                       (archived_id, meta['name'], meta['startDate'], meta['endDate'], 'archived', archived['schemaVersion']))
            account = db.execute('SELECT account_id FROM cycles LIMIT 1').fetchone()[0]
            db.execute('INSERT INTO plans(account_id,id,cycle_id,json,version,created_at) VALUES(?,?,?,?,?,?)',
                       (account, archived_id, archived_id, json.dumps(archived), archived['schemaVersion'], '2026-01-01T00:00:00+00:00'))
            db.execute('INSERT INTO prescription_versions(account_id,cycle_id,id,json,created_at) VALUES(?,?,?,?,?)',
                       (account, archived_id, archived_revision, json.dumps(archived), '2026-01-01T00:00:00+00:00'))
        before = database_rows(self.path)
        self.assertEqual(self.get_json('/api/prescription/version', cycle_id=archived_id,
                                      revision_id=archived_revision)['plan'], archived)
        for cycle, revision in ((archived_id, canonical_id(applied)), (self.cycle, archived_revision)):
            response = self.client.get('/api/prescription/version', params={'cycle_id': cycle, 'revision_id': revision})
            self.assertEqual(response.status_code, 404, response.text)
        archived_payload = {'cycle_id': archived_id, 'current_id': archived_revision,
                            'references': self.current()['references']}
        for endpoint, body in (
                ('preview', archived_payload),
                ('apply', {**archived_payload, 'preview_id': canonical_id(applied)}),
                ('restore', {'cycle_id': archived_id, 'current_id': archived_revision, 'revision_id': archived_revision})):
            response = self.client.post('/api/prescription/' + endpoint, json=body)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(database_rows(self.path), before)
        missing = self.client.get('/api/prescription/version',
                                  params={'cycle_id': self.cycle, 'revision_id': '0' * 64})
        self.assertEqual(missing.status_code, 404, missing.text)
        self.assertEqual(database_rows(self.path), before)
        self.assertEqual(self.get_json('/api/plan'), applied)

    def test_new_app_lifespan_preserves_applied_plan_history_and_daily_records(self):
        row = self.save_existing_records()
        applied, _, _ = self.apply()
        current = self.current()
        logs = self.get_json('/api/log')
        readiness_query = {'cycle_id': self.cycle, 'date': row['date'], 'session_id': 'daily'}
        readiness = self.get_json('/api/readiness', **readiness_query)
        metrics = self.get_json('/api/body-metrics', cycle_id=self.cycle, date=row['date'])
        before, before_backups = database_rows(self.path), backups(self.path)
        with TestClient(create_isolated_app(self.path), raise_server_exceptions=False) as restarted:
            for path, params, expected in (
                    ('/api/plan', {}, applied), ('/api/prescription', {'cycle_id': self.cycle}, current),
                    ('/api/log', {}, logs), ('/api/readiness', readiness_query, readiness),
                    ('/api/body-metrics', {'cycle_id': self.cycle, 'date': row['date']}, metrics)):
                response = restarted.get(path, params=params)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), expected)
            original = restarted.get('/api/prescription/version',
                                     params={'cycle_id': self.cycle, 'revision_id': canonical_id(self.seed)})
            self.assertEqual(original.status_code, 200, original.text)
            self.assertEqual(original.json()['plan'], self.seed)
        self.assertEqual(database_rows(self.path), before)
        self.assertEqual(backups(self.path), before_backups, 'Version-three startup must be idempotent')

    def test_system_load_uses_same_day_then_prior_weight_never_profile_or_future(self):
        from server.app.stats.variations import system_load
        pull = self.first_row('Pull-Up')
        references = self.request_payload()['references']
        # W1 Pull-Up's independently anchored 74% of 135 = 99.9 -> 100 kg total.
        references[pull['movementId']] = 135.
        applied, _, _ = self.apply(references)
        self.assertEqual(self.first_row('Pull-Up', applied)['loadKg'], 100.)
        unknown = {'total': 100., 'bodyweight': None, 'bodyweightDate': None,
                   'adjustment': None, 'kind': 'unknown'}
        self.assertEqual(self.current()['systemLoads'][row_key(pull)]['planned'], [unknown])
        log = {'cycle_id': self.cycle, 'week': pull['week'], 'day': pull['day'], 'seq': pull['seq'],
               'load': 100., 'sets': 3, 'reps': 6, 'rpe': 7., 'note': 'System mass, not added mass'}
        response = self.client.put('/api/log', json=log)
        self.assertEqual(response.status_code, 200, response.text)
        on_date = date.fromisoformat(pull['date'])
        past, future = (on_date - timedelta(days=1)).isoformat(), (on_date + timedelta(days=1)).isoformat()
        for day, weight, expected in (
                (future, 90., unknown),
                (past, 80., {'total': 100., 'bodyweight': 80., 'bodyweightDate': past,
                             'adjustment': 20., 'kind': 'weighted'}),
                (pull['date'], 85., {'total': 100., 'bodyweight': 85., 'bodyweightDate': pull['date'],
                                    'adjustment': 15., 'kind': 'weighted'})):
            response = self.client.put('/api/body-metrics', json={
                'cycle_id': self.cycle, 'date': day, 'bodyweight': weight,
                'bodyfat': None, 'measurements': {}})
            self.assertEqual(response.status_code, 200, response.text)
            before = database_rows(self.path)
            data = self.current()['systemLoads'][row_key(pull)]
            self.assertEqual(data, {'planned': [expected], 'logged': expected})
            self.assertEqual(database_rows(self.path), before)
        # The resolver also keeps assistance/self-weight/unknown distinct without touching actual sets.
        readings = [{'date': future, 'bodyweight': 90.}, {'date': pull['date'], 'bodyweight': 85.},
                    {'date': past, 'bodyweight': 80.}]
        for load, adjustment, kind in ((100., 15., 'weighted'), (85., 0., 'bodyweight'),
                                       (75., -10., 'assisted'), (None, None, 'unknown')):
            result = system_load(load, pull['date'], readings)
            self.assertEqual((result['total'], result['bodyweight'], result['bodyweightDate'],
                              result['adjustment'], result['kind']),
                             (load, 85., pull['date'], adjustment, kind))
        self.assertEqual(system_load(100., past, [{'date': future, 'bodyweight': 90.}]), unknown)
        zero = self.client.put('/api/log', json={**log, 'sets': 0, 'reps': 0, 'load': None, 'rpe': None})
        self.assertEqual(zero.status_code, 200, zero.text)
        self.assertIsNone(self.current()['systemLoads'][row_key(pull)]['logged'])

    def test_store_rechecks_stale_sha_inside_begin_immediate_without_logical_writes(self):
        from server.app.store import ReadOnlyError
        old_id = canonical_id(self.seed)
        self.apply()
        store = self.app.state.store
        before = database_rows(self.path)
        statements = []
        original_connect = store.connect

        @contextmanager
        def traced_connect():
            with original_connect() as db:
                db.set_trace_callback(statements.append)
                yield db

        with patch.object(store, 'connect', traced_connect):
            with self.assertRaisesRegex(ReadOnlyError, 'Prescription changed'):
                store.replace_prescription(self.cycle, old_id, self.seed, 'restore')
        begins = [i for i, sql in enumerate(statements) if sql.strip().upper() == 'BEGIN IMMEDIATE']
        reads = [i for i, sql in enumerate(statements) if sql.upper().startswith('SELECT JSON FROM PLANS')]
        self.assertTrue(begins, statements)
        self.assertTrue(reads, statements)
        self.assertLess(begins[0], reads[0], 'The optimistic check must follow acquisition of the write transaction')
        self.assertFalse(any(sql.lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for sql in statements))
        self.assertEqual(database_rows(self.path), before)

    def test_sabotage_recalculation_and_approved_catalogue_really_break_independent_anchors(self):
        from server.app.stats import variations as variations
        before = database_rows(self.path)
        payload = self.request_payload()
        ohp_key = row_key(self.first_row('OHP'))
        normal = {item['key']: item for item in self.preview(payload)['changes']}
        self.assertEqual(normal[ohp_key]['newLoad'], 45.)
        table = list(variations._RTS)
        table[10] = 100  # Wrong OHP percentage must not become its own expected value.
        with patch.object(variations, '_RTS', tuple(table)):
            corrupted = {item['key']: item for item in self.preview(payload)['changes']}
            self.assertEqual(corrupted[ohp_key]['newLoad'], 60., 'The fault injection must hit the real engine')
            with self.assertRaises(AssertionError):
                self.assertEqual(corrupted[ohp_key]['newLoad'], 45.)
        # Isolate transfer corruption from lift corruption so neither masks the other.
        with patch.dict(variations._FAMILIES, {'OHP': ('B', .99, 60, False)}):
            corrupted_catalogue = self.current()['catalogue']
            ohp = next(entry for entry in corrupted_catalogue if entry['name'] == 'OHP')
            self.assertEqual(ohp['transfer'], .99, 'The coefficient injection must take effect')
            with self.assertRaises(AssertionError):
                self.assertEqual(ohp['transfer'], .35)
            with self.assertRaises(AssertionError):
                self.assert_catalogue(corrupted_catalogue)
        with patch.dict(variations._FAMILIES, {'OHP': ('S', .35, 60, False)}):
            corrupted_catalogue = self.current()['catalogue']
            with self.assertRaises(AssertionError):
                self.assert_catalogue(corrupted_catalogue)
            self.assertEqual(variations.classification(self.first_row('OHP'), POLICY)[2], 'S')
            with self.assertRaises(AssertionError):
                self.assertEqual(variations.classification(self.first_row('OHP'), POLICY)[2], 'B')
        self.assert_catalogue(self.current()['catalogue'])
        self.assertEqual({item['key']: item for item in self.preview(payload)['changes']}[ohp_key]['newLoad'], 45.)
        self.assertEqual(database_rows(self.path), before)
        # Transfer is verified as catalogue metadata only; equivalent-capacity policy belongs to the next milestone.


class PrescriptionMigrationTests(unittest.TestCase):
    def test_v2_snapshot_integrity_and_original_readiness_logs_survive_separate_v3_upgrade(self):
        from server.app.store import Store
        with tempfile.TemporaryDirectory(prefix='roast-raw-prescription-migration-') as folder:
            path = Path(folder) / 'v2.sqlite3'
            seed = json.loads(PLAN_PATH.read_text(encoding='utf-8'))
            cycle, row = seed['meta']['planId'], seed['workouts'][0]
            store = Store(path)
            store.initialize(seed)
            with open_db(path) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
                db.execute('INSERT INTO readiness(cycle_id,date,session_id,fatigue,arousal,nutrition,rec,note) '
                           'VALUES(?,?,?,?,?,?,?,?)', (cycle, row['date'], 'legacy', 7, 2, 3, .25, 'Raw fatigue stays raw'))
                db.execute('INSERT INTO archives VALUES(?,?,?,?)',
                           ('legacy-review', cycle, json.dumps({'original': True}), '2026-01-01T00:00:00+00:00'))
            original_rows, original_schema = database_rows(path), database_schema(path)
            store.upgrade()
            with open_db(path) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2,
                                 'The existing upgrade remains specifically the v1-to-v2 operation')
            for table, rows in original_rows.items():
                self.assertEqual(database_rows(path)[table], rows)
            for definition in original_schema:
                self.assertIn(definition, database_schema(path))
            # Rows are written in the v2 shape: the v6 writers require account_id columns.
            with open_db(path) as db:
                db.execute('INSERT INTO logs_journal(cycle_id,key,payload,created_at) VALUES(?,?,?,?)',
                           (cycle, '1|A|1', json.dumps({'load': 101.25, 'sets': 0, 'reps': 0, 'rpe': None, 'note': 'Explicit zero'}),
                            '2026-01-01T00:00:00+00:00'))
                db.execute('INSERT INTO logs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                           (cycle, '1|A|1', row['date'], '1|A', row['movementId'], 101.25, 0, None, 0, 'Explicit zero',
                            '2026-01-01T00:00:00+00:00'))
                db.execute('INSERT INTO readiness_v2(cycle_id,date,session_id,payload,updated_at) VALUES(?,?,?,?,?)',
                           (cycle, row['date'], 'daily',
                            json.dumps({'date': row['date'], 'session_id': 'daily', 'recovery': 1,
                                        'arousal': 4, 'nutrition': 7, 'note': 'New recovery'}),
                            '2026-01-01T00:00:00+00:00'))
                db.execute('INSERT INTO body_metrics(cycle_id,date,bodyweight,bodyfat,measurements_json) VALUES(?,?,?,?,?)',
                           (cycle, row['date'], 85., 18., json.dumps({'waist': 80.})))
            before_schema = database_schema(path)
            before, prior_backups = database_rows(path), backups(path)
            store.upgrade()
            self.assertEqual(database_rows(path), before)
            self.assertEqual(backups(path), prior_backups)
            with open_db(path) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
            store.upgrade_prescriptions()
            with open_db(path) as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 3)
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
                self.assertEqual(db.execute('SELECT cycle_id,id,json FROM prescription_versions').fetchall(),
                                 [(cycle, canonical_id(seed), before['plans'][0][2])])
            after = database_rows(path)
            self.assertEqual(set(after), set(before) | {'prescription_versions'})
            for table, rows in before.items():
                self.assertEqual(after[table], rows, f'v3 must leave {table} byte-for-byte logically intact')
            for definition in before_schema:
                self.assertIn(definition, database_schema(path))
            created = backups(path) - prior_backups
            self.assertEqual(len(created), 1)
            snapshot = next(iter(created))
            with open_db(snapshot) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
                self.assertEqual(db.execute('SELECT fatigue,rec,note FROM readiness').fetchone(),
                                 (7, .25, 'Raw fatigue stays raw'))
            self.assertEqual(database_rows(snapshot), before)
            self.assertEqual(database_schema(snapshot), before_schema)
            stable_backups = backups(path)
            with TestClient(create_isolated_app(path), raise_server_exceptions=False) as client:
                response = client.get('/api/plan')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), seed)
                response = client.get('/api/prescription/version',
                                      params={'cycle_id': cycle, 'revision_id': canonical_id(seed)})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['plan'], seed)
                readiness = client.get('/api/readiness', params={'cycle_id': cycle, 'date': row['date']})
                self.assertEqual(readiness.status_code, 200, readiness.text)
                self.assertEqual(readiness.json()['legacy'][0]['fatigue'], 7)
                self.assertEqual(readiness.json()['record']['recovery'], 1)
                self.assertEqual(client.get('/api/log').json()['logs'][row_key(row)]['sets'], 0)
            store.initialize(seed)
            store.upgrade()
            store.upgrade_prescriptions()
            from server.app.store import Store as StoreClass
            expected = {table: list(rows) for table, rows in after.items()}
            for table in ('questionnaires', 'ai_calls', 'attempts', 'deletion_tokens', 'accounts', 'invites',
                          'invite_redemptions', 'sessions'):
                expected[table] = []
            # v6 prepends the account to every cycle-scoped table, seed rows included.
            for table in StoreClass.V6_TABLES:
                expected[table] = sorted(((0,) + tuple(row)) for row in after.get(table, []))
            expected['ledger_meta'] = [('open_ledger', '0')]
            expected['test_results'] = []
            self.assertEqual(database_rows(path), expected)
            migrated_backups = backups(path) - stable_backups
            self.assertEqual(len(migrated_backups), 7, 'v4 questionnaire, v5 AI, additive accounts, membership, per-account ledger, composite-key and v7 test-results migrations must each snapshot once')
            snapshot_versions = set()
            for backup in migrated_backups:
                with open_db(backup) as db:
                    snapshot_versions.add(db.execute('PRAGMA user_version').fetchone()[0])
                    self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(snapshot_versions, {3, 4, 5, 6})


if __name__ == '__main__':
    unittest.main()
