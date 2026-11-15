
import copy
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import Barrier
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import ProxyHandler, build_opener

from fastapi.testclient import TestClient

import test_api as api_helpers
from test_api import (
    GeneratedPlanCase, PLAN_PATH, actual_payload,
    database_rows, fields_only, log_key, open_db,
)
from server.app.store import ReadOnlyError, Store
from server.app.validation import validate_plan
from server.tools import gen_data
from server.tools.synth_plan import build

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = '/api/plan/import/preview'
CONFIRM = '/api/plan/import/confirm'


def canonical_id(value):
    # Existing canonical-ID contract: sorted compact JSON, ASCII escaping.
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def source_sha(text):
    # The supplied text, not its decoded/re-serialized object or legacy provenance.
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def plan_text(plan):
    return json.dumps(plan, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def backups(path):
    return set((path.parent / 'backups').glob('*.sqlite3'))


def database_schema(path):
    with open_db(path) as db:
        return db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master "
                          "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()


def source_from_sql(path, cycle_id):
    with open_db(path) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        cycle = dict(db.execute('SELECT * FROM cycles WHERE id=?', (cycle_id,)).fetchone())
        cycle.pop('account_id', None)
        plan = json.loads(db.execute('SELECT json FROM plans WHERE cycle_id=?', (cycle_id,)).fetchone()[0])
        logs = {row['key']: {
            'load': row['load'], 'sets': row['set_count'], 'reps': row['reps'],
            'rpe': row['rpe'], 'note': row['note'], 'updated_at': row['updated_at'],
        } for row in db.execute('SELECT * FROM logs WHERE cycle_id=? ORDER BY key', (cycle_id,))}
        metrics = [{
            'date': row['date'], 'bodyweight': row['bodyweight'], 'bodyfat': row['bodyfat'],
            'measurements': json.loads(row['measurements_json'] or '{}'),
        } for row in db.execute('SELECT * FROM body_metrics WHERE cycle_id=? ORDER BY date', (cycle_id,))]
        readiness = [{**json.loads(row['payload']), 'updated_at': row['updated_at']}
                     for row in db.execute('SELECT * FROM readiness_v2 WHERE cycle_id=? ORDER BY date,updated_at',
                                           (cycle_id,))]
        legacy = [dict(row) for row in db.execute('SELECT * FROM readiness WHERE cycle_id=? ORDER BY date,session_id',
                                                (cycle_id,))]
        versions = [{'id': row['id'], 'plan': json.loads(row['json']), 'created_at': row['created_at']}
                    for row in db.execute('SELECT * FROM prescription_versions WHERE cycle_id=? ORDER BY created_at,id',
                                          (cycle_id,))]
        journals = {}
        for name, table in (('logs', 'logs_journal'), ('records', 'records_journal')):
            journals[name] = [{**{k: v for k, v in dict(row).items() if k != 'account_id'},
                               'payload': json.loads(row['payload'])}
                              for row in db.execute(f'SELECT * FROM {table} WHERE cycle_id=? ORDER BY id', (cycle_id,))]
        archived = db.execute('SELECT review_json FROM archives WHERE cycle_id=?', (cycle_id,)).fetchone()
        questionnaire = db.execute('SELECT payload,status,updated_at FROM questionnaires WHERE cycle_id=?',
                                   (cycle_id,)).fetchone()
    return {'cycle': cycle, 'plan': plan, 'logs': logs, 'body_metrics': metrics,
            'readiness': readiness, 'legacy_readiness': legacy,
            'prescription_versions': versions, 'journals': journals,
            'saved_review': json.loads(archived[0]) if archived else None,
            'questionnaire': {'status': questionnaire['status'], 'payload': json.loads(questionnaire['payload']),
                              'updated_at': questionnaire['updated_at']} if questionnaire else None}


def create_isolated_app(path):
    # main constructs a module-level app too: isolate its first import as well.
    with patch.dict(os.environ, {'RR_DB_PATH': str(path)}):
        from server.app.main import create_app
        return create_app(db_path=path, plan_path=PLAN_PATH)


def altered_id(value):
    return ('0' if value[0] != '0' else '1') + value[1:]


class PlanImportFixtures(GeneratedPlanCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lib, cls.mm = gen_data.build_movements()
        cls.sample_bytes = gen_data.SAMPLE.read_bytes()
        cls.envelope = json.loads(cls.sample_bytes.decode('utf-8-sig'))
        # build() only constructs in memory from the existing read-only Ref.
        cls.candidates = {count: build(count) for count in (8, 17)}
        for count, plan in cls.candidates.items():
            plan['meta']['planId'] = f'plan-import-independent-{count}w'
            validate_plan(plan, file=f'candidate-{count}.json', lib=cls.lib)


class PlanImportCase(PlanImportFixtures):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='roast-raw-plan-import-')
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'import.sqlite3'
        self.app = create_isolated_app(self.path)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.store = self.app.state.store
        self.cycle = self.seed['meta']['planId']
        self.row = self.main_row()
        # Stable, explicit fixture date; never use the live date as an expectation.
        clock = patch('server.app.calendar.datetime')
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.clock.now.return_value = datetime(2028, 1, 1, 4, tzinfo=timezone.utc)
        self.app_version = json.loads((ROOT / 'web/package.json').read_text(encoding='utf-8'))['version']

    def get_json(self, endpoint, client=None, **params):
        response = (client or self.client).get(endpoint, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def assert_summary(self, summary, plan):
        self.assertIsInstance(summary, dict)
        # Public summary identity/calendar fields, independently from the plan.
        self.assertEqual(summary['cycleId'], plan['meta']['planId'])
        for field in ('name', 'startDate', 'endDate', 'weeks', 'sessions'):
            self.assertEqual(summary[field], plan['meta'][field], field)
        self.assertEqual(summary['sets'], sum(row['sets'] for row in plan['workouts']))
        self.assertEqual(summary['workouts'], len(plan['workouts']))
        self.assertEqual(summary['tonnageKg'], plan['meta']['cycleTonnageKg'])
        self.assertEqual(summary['weeks'], len(plan['weeks']))
        self.assertEqual(summary['sessions'], len({(row['week'], row['day']) for row in plan['workouts']}))

    def request_body(self, count=8, text=None, filename='candidate.json'):
        return {'plan_json': plan_text(self.candidates[count]) if text is None else text, 'filename': filename}

    def preview(self, body=None, client=None, path=None):
        body = self.request_body() if body is None else body
        client, path = client or self.client, path or self.path
        active = source_from_sql(path, client.get('/api/cycle').json()['active_cycle_id'])
        response = client.post(PREVIEW, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue({'currentId', 'candidateId', 'current', 'candidate',
                         'currentPlan', 'candidatePlan', 'sourceSha256'} <= result.keys())
        self.assertEqual(result['currentId'], canonical_id(active))
        self.assertEqual(result['currentPlan'], active['plan'])
        self.assertEqual(result['candidateId'], canonical_id(result['candidatePlan']))
        self.assertEqual(result['sourceSha256'], source_sha(body['plan_json']))
        self.assert_summary(result['current'], result['currentPlan'])
        self.assert_summary(result['candidate'], result['candidatePlan'])
        return result

    def confirmed_body(self, body=None, preview=None):
        body = self.request_body() if body is None else body
        preview = self.preview(body) if preview is None else preview
        return {**body, 'current_id': preview['currentId'],
                'candidate_id': preview['candidateId'], 'confirm': True}

    def confirm(self, body=None):
        body = self.confirmed_body() if body is None else body
        old_id = self.get_json('/api/cycle')['active_cycle_id']
        candidate_id = json.loads(body['plan_json'])['meta']['planId']
        response = self.client.post(CONFIRM, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'saved': True, 'active_cycle_id': candidate_id,
                                           'archived_cycle_id': old_id})
        return response.json()

    def assert_errors(self, response, filename):
        self.assertEqual(response.status_code, 422, response.text)
        errors = response.json()['errors']
        self.assertTrue(errors)
        for error in errors:
            self.assertTrue({'file', 'week', 'day', 'movement', 'field', 'expected'} <= error.keys())
            self.assertEqual(error['file'], filename)
            self.assertTrue(error['field'])
            self.assertTrue(error['expected'])
        return errors

    def assert_snapshot(self, snapshot, rows, schema, version=7):
        with open_db(snapshot) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], version)
        self.assertEqual(database_rows(snapshot), rows)
        self.assertEqual(database_schema(snapshot), schema)

    def assert_counts(self, **expected):
        with open_db(self.path) as db:
            for table, count in expected.items():
                self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0], count, table)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 7)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def save_records(self, prescription=False):
        # Two versions of one real observation, plus a distinct explicit-zero row.
        for load in (101.25, 102.5):
            response = self.client.put('/api/log', json=actual_payload(
                self.seed, self.row, load=load, sets=2, reps=1, note='Keep <script> literally'))
            self.assertEqual(response.status_code, 200, response.text)
        zero_row = next(row for row in self.seed['workouts'] if row['bucket'] == 'accessory')
        response = self.client.put('/api/log', json=actual_payload(
            self.seed, zero_row, load=None, sets=0, reps=0, rpe=None, note='Explicit zero'))
        self.assertEqual(response.status_code, 200, response.text)
        for recovery in (1, 5):
            response = self.client.put('/api/readiness', json={
                'cycle_id': self.cycle, 'date': self.row['date'], 'session_id': 'daily',
                'recovery': recovery, 'arousal': 4, 'nutrition': 7, 'note': 'Positive recovery'})
            self.assertEqual(response.status_code, 200, response.text)
        for weight in (84.0, 85.0):
            response = self.client.put('/api/body-metrics', json={
                'cycle_id': self.cycle, 'date': self.row['date'], 'bodyweight': weight,
                'bodyfat': 18.0, 'measurements': {'waist': 80.0}})
            self.assertEqual(response.status_code, 200, response.text)
        with open_db(self.path) as db:
            db.execute('INSERT INTO readiness(account_id,cycle_id,date,session_id,fatigue,arousal,nutrition,rec,note) '
                       'VALUES((SELECT account_id FROM cycles WHERE id=?),?,?,?,?,?,?,?,?)',
                       (self.cycle, self.cycle, self.row['date'], 'legacy', 7, 2, 3, .25, 'Fatigue is not recovery'))
        if prescription:
            current = self.get_json('/api/prescription', cycle_id=self.cycle)
            payload = {'cycle_id': self.cycle, 'current_id': current['currentId'],
                       'references': current['references']}
            response = self.client.post('/api/prescription/preview', json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            response = self.client.post('/api/prescription/apply',
                                        json={**payload, 'preview_id': response.json()['previewId']})
            self.assertEqual(response.status_code, 200, response.text)
        self.assert_counts(cycles=1, plans=1, logs=2, logs_journal=3, readiness=1,
                           readiness_v2=1, body_metrics=1, archives=0,
                           prescription_versions=2 if prescription else 1,
                           records_journal=5 if prescription else 4)
        return zero_row

    @contextmanager
    def trace_store(self):
        statements = []
        original_connect = self.store.connect

        @contextmanager
        def traced_connect():
            with original_connect() as db:
                db.set_trace_callback(statements.append)
                yield db

        with patch.object(self.store, 'connect', traced_connect):
            yield statements


class PlanImportAPITests(PlanImportCase):
    def test_preview_raw_8_and_17_weeks_has_independent_hashes_and_no_writes_or_backup(self):
        self.save_records()
        before, schema, prior_backups = database_rows(self.path), database_schema(self.path), backups(self.path)
        for count in (8, 17):
            with self.subTest(weeks=count):
                plan = copy.deepcopy(self.candidates[count])
                plan['meta']['name'] = f'Independent {count}-week café cycle'
                text = ' \r\n' + json.dumps(plan, ensure_ascii=False, indent=2) + '\r\n '
                body = self.request_body(text=text, filename='../display-only <script>.json')
                with patch.object(self.store, 'snapshot', wraps=self.store.snapshot) as snapshot:
                    result = self.preview(body)
                    self.assertEqual(self.preview(body), result, 'Preview IDs and summaries must be deterministic')
                    snapshot.assert_not_called()
                self.assertEqual(result['candidatePlan'], plan)
                self.assertNotEqual(result['sourceSha256'], plan['source']['sha256'])
                self.assertNotEqual(result['sourceSha256'], canonical_id(plan))
                self.assertEqual(result['candidate']['weeks'], count)
                self.assertEqual(database_rows(self.path), before)
                self.assertEqual(database_schema(self.path), schema)
                self.assertEqual(backups(self.path), prior_backups)

    def test_v4_preview_hashes_original_source_bytes_and_keeps_adapter_source(self):
        # The real v4 sample has the seed's ID. Give this isolated database a
        # different active cycle, rather than weakening duplicate-ID validation.
        path = self.path.parent / 'v4.sqlite3'
        store = Store(path)
        store.initialize(self.candidates[17])
        store.upgrade()
        store.upgrade_prescriptions()
        with TestClient(create_isolated_app(path), raise_server_exceptions=False) as client:
            before, prior_backups = database_rows(path), backups(path)
            original_text = self.sample_bytes.decode('utf-8')
            for text in (original_text, ' \r\n' + json.dumps(self.envelope, ensure_ascii=False, indent=3) + '\r\n'):
                with self.subTest(original_bytes=text == original_text):
                    result = self.preview({'plan_json': text, 'filename': 'original-v4.json'}, client, path)
                    expected_sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
                    expected = gen_data.adapt(self.envelope, self.lib, self.mm,
                                              source_sha256=expected_sha, file='original-v4.json')
                    self.assertEqual(result['candidatePlan'], expected)
                    self.assertEqual(result['candidatePlan']['source']['legacyEnvelope'], self.envelope)
                    self.assertEqual(result['candidatePlan']['source']['sha256'], expected_sha)
                    self.assertEqual(result['candidatePlan']['source']['hashBasis'], 'input-bytes')
                    self.assertEqual(result['sourceSha256'], expected_sha)
                    if text == original_text:
                        self.assertEqual(expected_sha, hashlib.sha256(self.sample_bytes).hexdigest())
                    self.assertEqual(database_rows(path), before)
                    self.assertEqual(backups(path), prior_backups)
            validation = client.post('/api/plan/validate', json=self.envelope)
            self.assertEqual(validation.status_code, 422, validation.text)
            self.assertEqual(database_rows(path), before)
            schema, prior_backups = database_schema(path), backups(path)
            confirmed = client.post(CONFIRM, json={
                'plan_json': text, 'filename': 'original-v4.json', 'current_id': result['currentId'],
                'candidate_id': result['candidateId'], 'confirm': True})
            self.assertEqual(confirmed.status_code, 200, confirmed.text)
            self.assertEqual(confirmed.json(), {'saved': True, 'active_cycle_id': expected['meta']['planId'],
                                                'archived_cycle_id': self.candidates[17]['meta']['planId']})
            self.assertEqual(self.get_json('/api/plan', client), expected)
            created = backups(path) - prior_backups
            self.assertEqual(len(created), 1)
            self.assert_snapshot(next(iter(created)), before, schema)

    def test_duplicate_keys_nonfinite_truncated_and_wrong_envelopes_fail_closed(self):
        raw = self.candidates[8]
        encoded = plan_text(raw)
        first_row = plan_text(raw['workouts'][0])
        duplicate_row = first_row.replace('"movement":', '"movement":"ignored duplicate","movement":', 1)
        duplicate_meta = encoded.replace('"planId":', '"planId":"ignored duplicate","planId":', 1)
        cases = [
            ('duplicate envelope', '{"schemaVersion":"ignored duplicate",' + encoded[1:]),
            ('duplicate metadata', duplicate_meta),
            ('duplicate workout', encoded.replace(first_row, duplicate_row, 1)),
            ('truncated', encoded[:-1]), ('trailing second document', encoded + '{}'),
            ('empty', ''), ('null', 'null'), ('array', '[]'), ('string', '"plan"'),
            ('review envelope', '{"schema":"RPL-Review-v1","plan":' + encoded + '}'),
            ('unsupported v4', '{"format":"RPL-Plan","schemaVersion":"RPL-Plan-v3","plan":{}}'),
            ('unsupported Raw', encoded.replace('"schemaVersion":"RPL-Raw-v1"',
                                                 '"schemaVersion":"RPL-Raw-v99"', 1)),
        ]
        for literal in ('NaN', 'Infinity', '-Infinity', '1e999'):
            original_load = '"loadKg":' + json.dumps(raw['workouts'][0]['loadKg'])
            replacement_row = first_row.replace(original_load, '"loadKg":' + literal, 1)
            self.assertNotEqual(replacement_row, first_row, 'Nonfinite injection must hit the actual workout')
            cases.append((literal, encoded.replace(first_row, replacement_row, 1)))
            # Opaque provenance is otherwise schema-valid: no duplicate/extra
            # top-level field can mask a parser which silently accepts overflow.
            opaque = copy.deepcopy(raw)
            opaque['source']['legacyEnvelope']['nonfinite_probe'] = 0
            opaque_text = plan_text(opaque).replace('"nonfinite_probe":0', '"nonfinite_probe":' + literal, 1)
            cases.append(('opaque ' + literal, opaque_text))
        valid_body = self.request_body()
        preview = self.preview(valid_body)
        before = database_rows(self.path)
        for label, text in cases:
            for endpoint in (PREVIEW, CONFIRM):
                with self.subTest(case=label, endpoint=endpoint):
                    body = {'plan_json': text, 'filename': 'malformed.json'}
                    if endpoint == CONFIRM:
                        body.update(current_id=preview['currentId'], candidate_id=preview['candidateId'], confirm=True)
                    self.assert_errors(self.client.post(endpoint, json=body), 'malformed.json')
                    self.assertEqual(database_rows(self.path), before)

    def test_incompatible_movements_report_exact_raw_and_v4_field_context(self):
        raw = copy.deepcopy(self.candidates[8])
        row = raw['workouts'][0]
        row['movementId'] = 'S.Unknown|invented movement'
        legacy = copy.deepcopy(self.envelope)
        legacy_row = legacy['plan']['Workouts'][0]
        legacy_row['movement'] = 'Unknown Squat'
        for plan, target, field in ((raw, row, 'workouts.0.movementId'),
                                    (legacy, legacy_row, 'Workouts[0].movementId')):
            for endpoint in (PREVIEW, CONFIRM):
                with self.subTest(field=field, endpoint=endpoint):
                    body = self.request_body(text=plan_text(plan), filename='movement-context.json')
                    if endpoint == CONFIRM:
                        body.update(current_id='0' * 64, candidate_id='1' * 64, confirm=True)
                    before = database_rows(self.path)
                    errors = self.assert_errors(self.client.post(endpoint, json=body), body['filename'])
                    matching = [error for error in errors if error['field'] == field]
                    self.assertTrue(matching, errors)
                    for error in matching:
                        self.assertEqual((error['week'], error['day'], error['movement']),
                                         (target['week'], target['day'], target['movement']))
                    self.assertEqual(database_rows(self.path), before)

    def test_existing_same_id_is_never_overwritten_and_validation_route_is_unchanged(self):
        body = self.request_body(text=plan_text(self.seed))
        before = database_rows(self.path)
        for endpoint in (PREVIEW, CONFIRM):
            payload = dict(body)
            if endpoint == CONFIRM:
                payload.update(current_id=canonical_id(source_from_sql(self.path, self.cycle)),
                               candidate_id=canonical_id(self.seed), confirm=True)
            response = self.client.post(endpoint, json=payload)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(database_rows(self.path), before)
        response = self.client.post('/api/plan/validate', json=self.candidates[8])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'valid': True, 'persisted': False, 'schemaVersion': 'RPL-Raw-v1'})
        invalid = copy.deepcopy(self.candidates[8])
        invalid['workouts'][0]['sets'] += 1
        self.assertEqual(self.client.post('/api/plan/validate', json=invalid).status_code, 422)
        self.assertEqual(database_rows(self.path), before)

    def test_false_extra_missing_and_wrong_types_never_confirm_or_write(self):
        valid = self.confirmed_body()
        before = database_rows(self.path)
        cases = [('false confirmation', {**valid, 'confirm': False}),
                 ('extra field', {**valid, 'unexpected': 'must not be ignored'})]
        for field in ('plan_json', 'filename', 'current_id', 'candidate_id', 'confirm'):
            body = dict(valid)
            del body[field]
            cases.append(('missing ' + field, body))
        for field, values in (('plan_json', ({}, None, 17)), ('filename', (None, 17)),
                              ('current_id', (None, True, 'not-a-hash')),
                              ('candidate_id', (None, True, 'not-a-hash')),
                              ('confirm', (None, 0, 1, 'true'))):
            cases.extend((f'{field}={value!r}', {**valid, field: value}) for value in values)
        for label, body in cases:
            with self.subTest(case=label):
                response = self.client.post(CONFIRM, json=body)
                if label == 'false confirmation':
                    self.assertIn(response.status_code, (409, 422), response.text)
                else:
                    self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(database_rows(self.path), before)
        for field in ('plan_json', 'filename'):
            body = self.request_body()
            del body[field]
            self.assertEqual(self.client.post(PREVIEW, json=body).status_code, 422)
            self.assertEqual(database_rows(self.path), before)

    def test_forged_candidate_changed_plan_and_stale_source_are_conflicts_without_writes(self):
        valid = self.confirmed_body()
        changed = copy.deepcopy(self.candidates[8])
        changed['meta']['name'] = 'Different but valid candidate'
        validate_plan(changed, lib=self.lib)
        cases = ({**valid, 'candidate_id': altered_id(valid['candidate_id'])},
                 {**valid, 'current_id': altered_id(valid['current_id'])},
                 {**valid, 'plan_json': plan_text(changed)},
                 {**valid, 'plan_json': plan_text(self.candidates[17])})
        before = database_rows(self.path)
        for body in cases:
            response = self.client.post(CONFIRM, json=body)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(database_rows(self.path), before)

    def test_logs_readiness_and_metrics_changed_after_preview_each_invalidate_confirmation(self):
        self.save_records()
        mutations = (
            ('/api/log', actual_payload(self.seed, self.row, load=120, reps=3)),
            ('/api/readiness', {'cycle_id': self.cycle, 'date': self.row['date'],
                               'session_id': 'daily', 'recovery': 6, 'arousal': 2, 'nutrition': 3}),
            ('/api/body-metrics', {'cycle_id': self.cycle, 'date': self.row['date'],
                                  'bodyweight': 86, 'bodyfat': 17, 'measurements': {'waist': 79}}),
        )
        for endpoint, mutation in mutations:
            with self.subTest(changed=endpoint):
                body = self.confirmed_body()
                response = self.client.put(endpoint, json=mutation)
                self.assertEqual(response.status_code, 200, response.text)
                before = database_rows(self.path)
                self.assertNotEqual(canonical_id(source_from_sql(self.path, self.cycle)), body['current_id'])
                response = self.client.post(CONFIRM, json=body)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(database_rows(self.path), before)

    def test_legacy_fatigue_and_prescription_changes_invalidate_prior_preview(self):
        self.save_records()
        body = self.confirmed_body()
        with open_db(self.path) as db:
            db.execute('UPDATE readiness SET fatigue=6 WHERE cycle_id=?', (self.cycle,))
        before = database_rows(self.path)
        response = self.client.post(CONFIRM, json=body)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(database_rows(self.path), before)
        body = self.confirmed_body()
        current = self.get_json('/api/prescription', cycle_id=self.cycle)
        payload = {'cycle_id': self.cycle, 'current_id': current['currentId'], 'references': current['references']}
        response = self.client.post('/api/prescription/preview', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post('/api/prescription/apply',
                                    json={**payload, 'preview_id': response.json()['previewId']})
        self.assertEqual(response.status_code, 200, response.text)
        before = database_rows(self.path)
        response = self.client.post(CONFIRM, json=body)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(database_rows(self.path), before)

    def test_unknown_database_version_rejects_confirmation_without_mutation(self):
        body = self.confirmed_body()
        for version in (0, 1, 2, 3, 4, 5, 99):
            with self.subTest(version=version):
                with open_db(self.path) as db:
                    db.execute(f'PRAGMA user_version={version}')
                before, schema = database_rows(self.path), database_schema(self.path)
                try:
                    response = self.client.post(CONFIRM, json=body)
                    self.assertEqual(response.status_code, 500, response.text)
                    self.assertEqual(database_rows(self.path), before)
                    self.assertEqual(database_schema(self.path), schema)
                    with open_db(self.path) as db:
                        self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], version)
                finally:
                    with open_db(self.path) as db:
                        db.execute('PRAGMA user_version=7')

    def test_confirm_snapshots_and_preserves_complete_old_review_records_and_history(self):
        self.save_records(prescription=True)
        old_plan = self.get_json('/api/plan')
        old_review = self.get_json('/api/review/export', cycle_id=self.cycle)
        body = self.confirmed_body()
        before, schema, prior_backups = database_rows(self.path), database_schema(self.path), backups(self.path)
        self.confirm(body)
        candidate = self.candidates[8]
        new_cycle = candidate['meta']['planId']
        self.assert_counts(cycles=2, plans=2, logs=2, logs_journal=3, readiness=1,
                           readiness_v2=1, body_metrics=1, archives=1,
                           prescription_versions=3, records_journal=6)
        after = database_rows(self.path)
        with open_db(self.path) as db:
            status_index = [row[1] for row in db.execute('PRAGMA table_info(cycles)')].index('status')
        for table, rows in before.items():
            if table == 'cycles':
                expected = tuple('archived' if i == status_index else value for i, value in enumerate(rows[0]))
                self.assertEqual(after[table][0], expected)
            elif table in ('plans', 'prescription_versions', 'records_journal', 'archives'):
                self.assertTrue(set(rows) <= set(after[table]), table)
            else:
                self.assertEqual(after[table], rows, table)
        self.assertEqual(database_schema(self.path), schema)
        created = backups(self.path) - prior_backups
        self.assertEqual(len(created), 1)
        self.assert_snapshot(next(iter(created)), before, schema)
        self.assertEqual(self.get_json('/api/plan'), candidate)
        self.assertEqual(self.get_json('/api/plan', cycle_id=self.cycle), old_plan)
        self.assertEqual(self.get_json('/api/log'), {'cycle_id': new_cycle, 'logs': {}})
        self.assertEqual(self.get_json('/api/body-metrics', cycle_id=new_cycle)['records'], [])
        self.assertIsNone(self.get_json('/api/readiness', cycle_id=new_cycle, date=self.row['date'])['record'])
        with open_db(self.path) as db:
            saved = json.loads(db.execute('SELECT review_json FROM archives WHERE cycle_id=?',
                                          (self.cycle,)).fetchone()[0])
            initial = db.execute('SELECT id,json FROM prescription_versions WHERE cycle_id=?',
                                 (new_cycle,)).fetchall()
            journal = db.execute('SELECT cycle_id,kind,payload FROM records_journal ORDER BY id DESC LIMIT 1').fetchone()
        self.assertEqual(len(initial), 1)
        self.assertEqual(initial[0][0], canonical_id(candidate))
        self.assertEqual(json.loads(initial[0][1]), candidate)
        self.assertEqual(journal[0], self.cycle, 'The import journal belongs to the old cycle')
        self.assertIn(new_cycle, json.dumps(json.loads(journal[2])))
        self.assertEqual(self.get_json('/api/review', cycle_id=self.cycle), saved)
        self.assertEqual(self.get_json('/api/review/export', cycle_id=self.cycle), saved)
        unsigned = copy.deepcopy({key: value for key, value in saved.items() if key != 'integrity'})
        encoded = json.dumps(unsigned, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        self.assertEqual(saved['integrity'], {'algorithm': 'SHA-256',
                                             'review_sha256': hashlib.sha256(encoded.encode('utf-8')).hexdigest()})
        expected_review = copy.deepcopy(old_review)
        import_event = {'id': len(before['records_journal']) + 1, 'cycle_id': self.cycle,
                        'kind': 'import', 'key': new_cycle, 'created_at': saved['exported_at'],
                        'payload': {'action': 'import', 'from': self.cycle, 'to': new_cycle,
                                    'plan_sha256': canonical_id(candidate)}}
        self.assertEqual(saved['journals']['records'][-1], import_event)
        expected_review['journals']['records'].append(import_event)
        for value in (expected_review, unsigned):
            value.pop('exported_at', None)
            value.pop('integrity', None)
            # Status describes either the frozen pre-transition review or archive.
            value['cycle'].pop('status')
        self.assertEqual(unsigned, expected_review, 'Every old review field must survive, not just summary statistics')
        self.assertEqual(saved['plan'], old_plan)
        self.assertEqual([entry['payload']['load'] for entry in saved['journals']['logs']], [101.25, 102.5, None])
        self.assertEqual(saved['readiness']['legacy'][0]['fatigue'], 7)
        self.assertEqual(saved['readiness']['legacy'][0]['rec'], .25)
        self.assertEqual(saved['readiness']['records'][0]['recovery'], 5)
        self.assertEqual(saved['body_metrics'][0]['bodyweight'], 85)
        self.assertEqual(len(saved['prescription_versions']), 2)
        self.assertEqual(len(saved['journals']['records']), 6)
        self.assertEqual(next(log for log in saved['logs'] if log['note'] == 'Explicit zero')['sets'], 0)
        listing = self.get_json('/api/archive')
        self.assertEqual(listing['active_cycle_id'], new_cycle)
        self.assertEqual([cycle['id'] for cycle in listing['cycles']], [self.cycle])
        frozen = copy.deepcopy(saved)
        new_row = next(row for row in candidate['workouts'] if log_key(row) == log_key(self.row))
        response = self.client.put('/api/log', json=actual_payload(candidate, new_row, load=80, sets=1, reps=1))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.get_json('/api/log')['logs'][log_key(new_row)]['load'], 80)
        self.assertEqual(self.get_json('/api/log', cycle_id=self.cycle)['logs'][log_key(self.row)]['load'], 102.5)
        self.assertEqual(self.get_json('/api/review', cycle_id=self.cycle), frozen)
        self.assert_counts(logs=3, logs_journal=4)

    def test_archived_all_mutation_routes_and_direct_log_save_are_read_only(self):
        self.save_records()
        prescription = self.get_json('/api/prescription', cycle_id=self.cycle)
        self.confirm()
        before = database_rows(self.path)
        payload = {'cycle_id': self.cycle, 'current_id': prescription['currentId'],
                   'references': prescription['references']}
        mutations = (
            ('PUT', '/api/log', actual_payload(self.seed, self.row, sets=9)),
            ('PUT', '/api/readiness', {'cycle_id': self.cycle, 'date': self.row['date'], 'recovery': 7,
                                     'session_id': 'daily'}),
            ('PUT', '/api/body-metrics', {'cycle_id': self.cycle, 'date': self.row['date'], 'bodyweight': 99}),
            ('POST', '/api/prescription/preview', payload),
            ('POST', '/api/prescription/apply', {**payload, 'preview_id': prescription['currentId']}),
            ('POST', '/api/prescription/restore', {'cycle_id': self.cycle,
                                                 'current_id': prescription['currentId'],
                                                 'revision_id': prescription['currentId']}),
        )
        for method, endpoint, body in mutations:
            response = self.client.request(method, endpoint, json=body)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(database_rows(self.path), before)
        with self.assertRaises(ReadOnlyError):
            self.store.save_log(self.cycle, self.row, fields_only(actual_payload(self.seed, self.row, sets=9)))
        self.assertEqual(database_rows(self.path), before)
        # An archived ID remains reserved even when a different cycle is active.
        response = self.client.post(PREVIEW, json=self.request_body(text=plan_text(self.seed)))
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(database_rows(self.path), before)

    def test_trigger_failures_on_each_activation_table_roll_back_every_logical_write(self):
        self.save_records()
        body = self.confirmed_body()
        for table in ('archives', 'plans', 'prescription_versions', 'records_journal'):
            with self.subTest(failed_table=table):
                before, prior_backups = database_rows(self.path), backups(self.path)
                with open_db(self.path) as db:
                    db.execute(f"CREATE TRIGGER reject_import BEFORE INSERT ON {table} "
                               "BEGIN SELECT RAISE(ABORT,'injected import failure'); END")
                schema = database_schema(self.path)
                try:
                    response = self.client.post(CONFIRM, json=body)
                    self.assertEqual(response.status_code, 500, response.text)
                    self.assertEqual(database_rows(self.path), before)
                    self.assertEqual(self.get_json('/api/cycle')['active_cycle_id'], self.cycle)
                    self.assertEqual(self.get_json('/api/plan'), self.seed)
                    created = backups(self.path) - prior_backups
                    self.assertEqual(len(created), 1, 'An aborted transaction may leave only its consistent snapshot')
                    self.assert_snapshot(next(iter(created)), before, schema)
                finally:
                    with open_db(self.path) as db:
                        db.execute('DROP TRIGGER reject_import')
        # Exactly the same reviewed request succeeds after removing only faults.
        self.confirm(body)
        self.assert_counts(cycles=2, plans=2, archives=1, prescription_versions=2, records_journal=5)

    def test_competing_confirmations_have_one_success_and_no_loser_cycle(self):
        requests = [self.confirmed_body(self.request_body(count)) for count in (8, 17)]
        self.assertEqual(requests[0]['current_id'], requests[1]['current_id'])
        before = database_rows(self.path)
        barrier = Barrier(2)
        original_snapshot = self.store.snapshot

        def snapshots_before_competing_transactions():
            result = original_snapshot()
            barrier.wait(timeout=5)
            return result

        def submit(body):
            # The primary client owns lifespan; worker clients only issue requests.
            client = TestClient(self.app, raise_server_exceptions=False)
            try:
                return client.post(CONFIRM, json=body)
            finally:
                client.close()

        with patch.object(self.store, 'snapshot', side_effect=snapshots_before_competing_transactions):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(submit, body) for body in requests]
                responses = [future.result(timeout=25) for future in futures]
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409],
                         [response.text for response in responses])
        winner = next(response.json()['active_cycle_id'] for response in responses if response.status_code == 200)
        loser = next(json.loads(body['plan_json'])['meta']['planId']
                     for body, response in zip(requests, responses) if response.status_code == 409)
        self.assertEqual(self.get_json('/api/cycle')['active_cycle_id'], winner)
        self.assert_counts(cycles=2, plans=2, archives=1, prescription_versions=2, records_journal=1)
        with open_db(self.path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM cycles WHERE id=?', (loser,)).fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT id FROM cycles WHERE status='active'").fetchall(), [(winner,)])
        after = database_rows(self.path)
        for table in ('logs', 'logs_journal', 'readiness', 'readiness_v2', 'body_metrics'):
            self.assertEqual(after[table], before[table])
        for body in requests:
            response = self.client.post(CONFIRM, json=body)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(database_rows(self.path), after)

    def test_fresh_app_reads_imported_cycle_archive_and_records_without_seed_overwrite(self):
        self.save_records(prescription=True)
        self.confirm()
        selected = self.candidates[8]
        new_cycle = selected['meta']['planId']
        row = next(row for row in selected['workouts'] if log_key(row) == log_key(self.row))
        response = self.client.put('/api/log', json=actual_payload(selected, row, load=117.5, reps=1))
        self.assertEqual(response.status_code, 200, response.text)
        endpoints = (
            ('/api/cycle', {}), ('/api/plan', {}), ('/api/plan', {'cycle_id': self.cycle}),
            ('/api/archive', {}), ('/api/log', {}), ('/api/log', {'cycle_id': self.cycle}),
            ('/api/review/export', {'cycle_id': self.cycle}),
            ('/api/readiness', {'cycle_id': self.cycle, 'date': self.row['date']}),
            ('/api/body-metrics', {'cycle_id': self.cycle}),
            ('/api/prescription', {'cycle_id': self.cycle}), ('/api/prescription', {'cycle_id': new_cycle}),
            ('/api/prescription/version', {'cycle_id': self.cycle, 'revision_id': canonical_id(self.seed)}),
        )
        expected = [self.get_json(endpoint, **params) for endpoint, params in endpoints]
        before, prior_backups = database_rows(self.path), backups(self.path)
        with TestClient(create_isolated_app(self.path), raise_server_exceptions=False) as restarted:
            for (endpoint, params), value in zip(endpoints, expected):
                self.assertEqual(self.get_json(endpoint, restarted, **params), value, endpoint)
        self.assertEqual(database_rows(self.path), before)
        self.assertEqual(backups(self.path), prior_backups)
        self.assertEqual(json.loads(PLAN_PATH.read_text(encoding='utf-8')), self.seed)


class PlanImportStoreTests(PlanImportCase):
    def test_activate_plan_directly_snapshots_before_one_immediate_transaction(self):
        self.save_records()
        before, schema, prior_backups = database_rows(self.path), database_schema(self.path), backups(self.path)
        expected_source = canonical_id(source_from_sql(self.path, self.cycle))
        original = copy.deepcopy(self.candidates[17])
        with self.trace_store() as statements:
            self.store.activate_plan(original, expected_source_id=expected_source, app_version=self.app_version)
        self.assertEqual(self.get_json('/api/cycle')['active_cycle_id'], original['meta']['planId'])
        self.assertEqual(self.get_json('/api/plan'), original)
        normalized = [sql.strip().upper() for sql in statements]
        begins = [i for i, sql in enumerate(normalized) if sql == 'BEGIN IMMEDIATE']
        self.assertEqual(len(begins), 1, statements)
        writes = [i for i, sql in enumerate(normalized) if sql.startswith(('INSERT ', 'UPDATE ', 'DELETE '))]
        self.assertTrue(writes, statements)
        self.assertTrue(all(index > begins[0] for index in writes), statements)
        commits = [i for i, sql in enumerate(normalized) if sql == 'COMMIT' and i > begins[0]]
        self.assertEqual(len(commits), 1, statements)
        self.assertGreater(commits[0], max(writes))
        self.assertEqual(original, self.candidates[17], 'Activation must not mutate caller-owned plan data')
        created = backups(self.path) - prior_backups
        self.assertEqual(len(created), 1)
        self.assert_snapshot(next(iter(created)), before, schema)
        self.assert_counts(cycles=2, plans=2, archives=1, prescription_versions=2, records_journal=5)

    def test_unknown_database_versions_fail_activation_without_schema_or_row_mutation(self):
        expected_source = canonical_id(source_from_sql(self.path, self.cycle))
        for version in (0, 1, 2, 3, 4, 5, 99):
            with self.subTest(version=version):
                with open_db(self.path) as db:
                    db.execute(f'PRAGMA user_version={version}')
                before, schema = database_rows(self.path), database_schema(self.path)
                try:
                    with self.assertRaises(RuntimeError):
                        self.store.activate_plan(self.candidates[8], expected_source_id=expected_source,
                                                 app_version=self.app_version)
                    self.assertEqual(database_rows(self.path), before)
                    self.assertEqual(database_schema(self.path), schema)
                    with open_db(self.path) as db:
                        self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], version)
                finally:
                    with open_db(self.path) as db:
                        db.execute('PRAGMA user_version=5')

    def test_existing_id_direct_activation_raises_read_only_without_logical_writes(self):
        expected_source = canonical_id(source_from_sql(self.path, self.cycle))
        before = database_rows(self.path)
        with self.assertRaises(ReadOnlyError):
            self.store.activate_plan(self.seed, expected_source_id=expected_source, app_version=self.app_version)
        self.assertEqual(database_rows(self.path), before)

    def test_stale_source_rechecked_after_begin_immediate_includes_journal_only_changes(self):
        old_source = canonical_id(source_from_sql(self.path, self.cycle))
        # Current plan and current observations are unchanged; only audit history differs.
        with open_db(self.path) as db:
            db.execute('INSERT INTO records_journal(account_id,cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?,?)',
                       (db.execute('SELECT account_id FROM cycles LIMIT 1').fetchone()[0], self.cycle, 'readiness',
                        'old-history', '{"note":"preserved history"}', '2026-11-01T00:00:00+00:00'))
        self.assertNotEqual(canonical_id(source_from_sql(self.path, self.cycle)), old_source)
        before = database_rows(self.path)
        with self.trace_store() as statements:
            with self.assertRaises(ReadOnlyError):
                self.store.activate_plan(self.candidates[8], expected_source_id=old_source, app_version=self.app_version)
        normalized = [sql.strip().upper() for sql in statements]
        begin = normalized.index('BEGIN IMMEDIATE')
        reads = [i for i, sql in enumerate(normalized) if sql.startswith('SELECT ') and 'FROM RECORDS_JOURNAL' in sql]
        self.assertTrue(any(index > begin for index in reads), statements)
        self.assertFalse(any(sql.startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for sql in normalized), statements)
        self.assertEqual(database_rows(self.path), before)

    def test_actual_write_between_snapshot_and_activation_is_not_lost(self):
        expected_source = canonical_id(source_from_sql(self.path, self.cycle))
        before, schema = database_rows(self.path), database_schema(self.path)
        original_snapshot = self.store.snapshot
        observed = {}

        def snapshot_then_concurrent_log():
            observed['snapshot'] = original_snapshot()
            self.store.save_log(self.cycle, self.row, fields_only(actual_payload(self.seed, self.row, load=123.5)))
            observed['rows'] = database_rows(self.path)
            return observed['snapshot']

        with patch.object(self.store, 'snapshot', side_effect=snapshot_then_concurrent_log):
            with self.assertRaises(ReadOnlyError):
                self.store.activate_plan(self.candidates[8], expected_source_id=expected_source, app_version=self.app_version)
        self.assertTrue(observed, 'The fault injection must actually run')
        self.assert_snapshot(observed['snapshot'], before, schema)
        self.assertEqual(database_rows(self.path), observed['rows'])
        self.assertEqual(self.store.logs(self.cycle)[log_key(self.row)]['load'], 123.5)
        self.assert_counts(cycles=1, plans=1, archives=0, prescription_versions=1, logs=1, logs_journal=1,
                           records_journal=0)

    def test_failed_snapshot_prevents_activation_and_leaves_every_table_unchanged(self):
        before = database_rows(self.path)
        expected_source = canonical_id(source_from_sql(self.path, self.cycle))
        with patch.object(self.store, 'snapshot', side_effect=RuntimeError('injected backup integrity failure')):
            with self.assertRaisesRegex(RuntimeError, 'injected backup integrity failure'):
                self.store.activate_plan(self.candidates[8], expected_source_id=expected_source, app_version=self.app_version)
        self.assertEqual(database_rows(self.path), before)

    def test_save_log_acquires_write_lock_and_checks_active_before_journal_insert(self):
        with self.trace_store() as statements:
            self.store.save_log(self.cycle, self.row, fields_only(actual_payload(self.seed, self.row)))
        normalized = [sql.strip().upper() for sql in statements]
        begin = normalized.index('BEGIN IMMEDIATE')
        active_reads = [i for i, sql in enumerate(normalized)
                        if sql.startswith('SELECT ') and 'FROM CYCLES' in sql and 'ACTIVE' in sql]
        inserts = [i for i, sql in enumerate(normalized) if sql.startswith('INSERT INTO LOGS_JOURNAL')]
        self.assertTrue(active_reads, statements)
        self.assertTrue(inserts, statements)
        self.assertLess(begin, active_reads[0])
        self.assertLess(active_reads[0], inserts[0])
        self.assert_counts(logs=1, logs_journal=1)

    def test_log_route_early_active_check_cannot_bypass_transaction_local_archive_guard(self):
        original_save = self.store.save_log
        expected_source = canonical_id(source_from_sql(self.path, self.cycle))
        observed = {}

        def archive_after_http_check(cycle_id, row, payload):
            self.store.activate_plan(self.candidates[8], expected_source_id=expected_source, app_version=self.app_version)
            observed['rows'] = database_rows(self.path)
            return original_save(cycle_id, row, payload)

        with patch.object(self.store, 'save_log', side_effect=archive_after_http_check):
            response = self.client.put('/api/log', json=actual_payload(self.seed, self.row, load=150))
        self.assertTrue(observed, 'The race must occur after the route resolves its active plan')
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(database_rows(self.path), observed['rows'])
        self.assert_counts(logs=0, logs_journal=0, cycles=2, archives=1)


class PlanImportRestartTests(PlanImportFixtures):
    # Reuse process ownership/deadline conventions, not the inherited old test.
    running_server = api_helpers.UvicornRestartTests.running_server
    request_json = api_helpers.UvicornRestartTests.request_json
    stop_owned_process = staticmethod(api_helpers.UvicornRestartTests.stop_owned_process)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='roast-raw-import-restart-')
        self.addCleanup(temporary.cleanup)
        self.db_path = Path(temporary.name) / 'restart.sqlite3'
        self.http = build_opener(ProxyHandler({}))

    def test_import_archive_and_new_actual_survive_real_uvicorn_process_restart(self):
        candidate = self.candidates[17]
        body = {'plan_json': plan_text(candidate), 'filename': 'restart-17.json'}
        row = self.main_row()
        with self.running_server() as (base_url, first_process):
            self.request_json(base_url, '/api/log', method='PUT',
                              payload=actual_payload(self.seed, row, load=101.25, reps=1))
            preview = self.request_json(base_url, PREVIEW, method='POST', payload=body)
            self.assertEqual(preview['candidateId'], canonical_id(candidate))
            self.assertEqual(preview['sourceSha256'], source_sha(body['plan_json']))
            self.assertEqual(preview['currentId'], canonical_id(source_from_sql(self.db_path, self.seed['meta']['planId'])))
            saved = self.request_json(base_url, CONFIRM, method='POST', payload={
                **body, 'current_id': preview['currentId'], 'candidate_id': preview['candidateId'], 'confirm': True})
            self.assertEqual(saved, {'saved': True, 'active_cycle_id': candidate['meta']['planId'],
                                     'archived_cycle_id': self.seed['meta']['planId']})
            new_row = next(value for value in candidate['workouts'] if log_key(value) == log_key(row))
            self.request_json(base_url, '/api/log', method='PUT',
                              payload=actual_payload(candidate, new_row, load=117.5, reps=1))
            old_query = '?cycle_id=' + self.seed['meta']['planId']
            paths = ('/api/plan', '/api/cycle', '/api/archive', '/api/log',
                     '/api/plan' + old_query, '/api/log' + old_query, '/api/review/export' + old_query)
            expected = {path: self.request_json(base_url, path) for path in paths}
        self.assertIsNotNone(first_process.poll())
        persisted, prior_backups = database_rows(self.db_path), backups(self.db_path)
        self.assertEqual(len(persisted['cycles']), 2)
        self.assertEqual(len(persisted['archives']), 1)
        self.assertEqual(len(persisted['prescription_versions']), 2)
        self.assertEqual(len(persisted['logs']), 2)
        self.assertEqual(len(persisted['logs_journal']), 2)
        with self.running_server() as (base_url, second_process):
            self.assertIsNot(first_process, second_process)
            for path, value in expected.items():
                self.assertEqual(self.request_json(base_url, path), value, path)
            self.assertEqual(self.request_json(base_url, '/api/plan'), candidate)
        self.assertIsNotNone(second_process.poll())
        self.assertEqual(database_rows(self.db_path), persisted)
        self.assertEqual(backups(self.db_path), prior_backups)
        self.assertEqual(json.loads(PLAN_PATH.read_text(encoding='utf-8')), self.seed)


if __name__ == '__main__':
    unittest.main()
