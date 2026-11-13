import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from test_api import GeneratedPlanCase, PLAN_PATH, actual_payload, database_rows, fields_only, log_key, open_db
from server.app.stats.variations import digest


class ReviewAPITests(GeneratedPlanCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='roastraw-review-')
        self.addCleanup(temporary.cleanup)
        self.db_path = Path(temporary.name) / 'review.sqlite3'
        with patch.dict(os.environ, {'RR_DB_PATH': str(self.db_path)}):
            from server.app.main import create_app
            self.app = create_app(db_path=self.db_path, plan_path=PLAN_PATH)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.store = self.app.state.store
        self.cycle_id = self.seed['meta']['planId']
        self.params = {'cycle_id': self.cycle_id}

    def assert_integrity(self, review):
        unsigned = {key: value for key, value in review.items() if key != 'integrity'}
        encoded = json.dumps(unsigned, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.assertEqual(review['integrity'], {'algorithm': 'SHA-256', 'review_sha256': hashlib.sha256(encoded).hexdigest()})

    def historical(self, cycle_id, status='archived'):
        plan = copy.deepcopy(self.seed)
        plan['meta']['planId'] = cycle_id
        plan['meta']['name'] = f'Historical {cycle_id}'
        with open_db(self.db_path) as db:
            db.execute('INSERT INTO cycles VALUES(?,?,?,?,?,?)',
                       (cycle_id, plan['meta']['name'], plan['meta']['startDate'], plan['meta']['endDate'], status, plan['schemaVersion']))
            db.execute('INSERT INTO plans VALUES(?,?,?,?,?)',
                       (cycle_id, cycle_id, json.dumps(plan), plan['schemaVersion'], '2026-11-01T00:00:00+00:00'))
            db.execute('INSERT INTO prescription_versions VALUES(?,?,?,?)',
                       (cycle_id, digest(plan), json.dumps(plan), '2026-11-01T00:00:00+00:00'))
        return plan

    def test_empty_review_export_does_not_archive_or_write_and_unknown_actuals_are_null(self):
        before = database_rows(self.db_path)
        response = self.client.get('/api/review')
        self.assertEqual(response.status_code, 200)
        review = response.json()
        self.assertEqual(review['schema'], 'RPL-Review-v1')
        self.assertEqual(review['plan_id'], self.cycle_id)
        self.assertEqual(review['cycle']['status'], 'active')
        self.assertEqual(review['logs'], [])
        self.assertIsNone(review['profile_end'])
        self.assertIsNone(review['attainment']['goal'])
        self.assertIsNone(review['attainment']['bodyweight'])
        self.assertIsNone(review['attainment']['composite'])
        self.assertEqual(review['completion']['main'], 0)
        self.assertEqual(review['completion']['var'], 0)
        self.assertEqual(review['completion']['acc'], 0)
        self.assert_integrity(review)
        exported = self.client.get('/api/review/export', params=self.params)
        self.assertEqual(exported.status_code, 200)
        self.assertIn('attachment;', exported.headers['content-disposition'])
        self.assertEqual(exported.headers['cache-control'], 'no-store')
        self.assert_integrity(exported.json())
        self.assertEqual(self.client.get('/api/archive').json(), {'cycles': [], 'active_cycle_id': self.cycle_id})
        self.assertEqual(database_rows(self.db_path), before)

    def test_export_preserves_actuals_daily_data_and_all_journal_versions(self):
        row = self.main_row()
        payload = actual_payload(self.seed, row, load=101.25, sets=2, reps=1, note='literal <script> is data')
        self.assertEqual(self.client.put('/api/log', json=payload).status_code, 200)
        payload['load'] = 102.5
        self.assertEqual(self.client.put('/api/log', json=payload).status_code, 200)
        self.assertEqual(self.client.put('/api/body-metrics', json={**self.params, 'date': row['date'],
                         'bodyweight': 85.0, 'measurements': {'waist': 90.0}}).status_code, 200)
        self.assertEqual(self.client.put('/api/readiness', json={**self.params, 'date': row['date'],
                         'session_id': 'daily', 'recovery': 5, 'arousal': 4, 'nutrition': 6}).status_code, 200)
        with open_db(self.db_path) as db:
            db.execute('INSERT INTO readiness(cycle_id,date,session_id,fatigue,note) VALUES(?,?,?,?,?)',
                       (self.cycle_id, row['date'], 'daily', 6, 'Original negative fatigue'))
        before = database_rows(self.db_path)
        review = self.client.get('/api/review/export', params=self.params).json()
        self.assertEqual(review['logs'][0]['key'], log_key(row))
        self.assertEqual(review['logs'][0]['load'], 102.5)
        self.assertEqual(review['logs'][0]['note'], payload['note'])
        self.assertEqual(review['body_metrics'][0]['bodyweight'], 85)
        self.assertEqual(review['readiness']['legacy'][0]['fatigue'], 6)
        self.assertEqual(review['readiness']['records'][0]['recovery'], 5)
        self.assertEqual([entry['payload']['load'] for entry in review['journals']['logs']], [101.25, 102.5])
        self.assertEqual(len(review['journals']['records']), 2)
        self.assertEqual(review['prescription_versions'][0]['plan'], self.seed)
        self.assertIsNone(review['attainment']['goal'])
        self.assert_integrity(review)
        self.assertEqual(database_rows(self.db_path), before)

    def test_historical_same_keys_are_isolated_and_read_only(self):
        old_plan = self.historical('old-cycle')
        self.historical('completed-cycle', 'completed')
        row = self.main_row()
        self.store.save_log(self.cycle_id, row, fields_only(actual_payload(self.seed, row, load=100, reps=3)))
        self.store.save_log('old-cycle', row, fields_only(actual_payload(old_plan, row, load=70, reps=1)))
        before = database_rows(self.db_path)
        old = self.client.get('/api/review', params={'cycle_id': 'old-cycle'}).json()
        current = self.client.get('/api/review', params=self.params).json()
        self.assertEqual(old['plan']['meta']['planId'], 'old-cycle')
        self.assertEqual(old['logs'][0]['load'], 70)
        self.assertEqual(current['logs'][0]['load'], 100)
        listing = self.client.get('/api/archive').json()
        self.assertEqual({cycle['id'] for cycle in listing['cycles']}, {'old-cycle', 'completed-cycle'})
        self.assertTrue(all(cycle['weeks'] == len(self.seed['weeks']) for cycle in listing['cycles']))
        self.assertEqual(self.client.put('/api/log', json=actual_payload(old_plan, row)).status_code, 409)
        self.assertEqual(database_rows(self.db_path), before)

    def test_unknown_and_write_methods_rejected_without_changes(self):
        before = database_rows(self.db_path)
        for path in ('/api/review', '/api/review/export'):
            self.assertEqual(self.client.get(path, params={'cycle_id': 'missing'}).status_code, 404)
        for path in ('/api/review', '/api/review/export', '/api/archive'):
            for method in ('post', 'put', 'patch', 'delete'):
                self.assertEqual(self.client.request(method.upper(), path, json={}).status_code, 405)
        self.assertEqual(database_rows(self.db_path), before)

    def test_fresh_app_readback_preserves_export_and_logical_records(self):
        row = self.main_row()
        self.store.save_log(self.cycle_id, row, fields_only(actual_payload(self.seed, row, load=101.25, reps=1)))
        first = self.client.get('/api/review', params=self.params).json()
        from server.app.main import create_app
        with TestClient(create_app(db_path=self.db_path, plan_path=PLAN_PATH)) as restarted:
            second = restarted.get('/api/review', params=self.params).json()
        for value in (first, second):
            value.pop('exported_at')
            value.pop('integrity')
        self.assertEqual(second, first)

    def test_consistent_read_transaction_never_mixes_new_log_with_old_journal(self):
        row = self.main_row()
        self.store.save_log(self.cycle_id, row, fields_only(actual_payload(self.seed, row, load=100)))
        original_loads = json.loads
        changed = False

        def write_between_reads(value, *args, **kwargs):
            nonlocal changed
            parsed = original_loads(value, *args, **kwargs)
            if not changed and isinstance(parsed, dict) and parsed.get('schemaVersion') == 'RPL-Raw-v1':
                changed = True
                self.store.save_log(self.cycle_id, row, fields_only(actual_payload(self.seed, row, load=120)))
            return parsed

        with patch('server.app.store.json.loads', side_effect=write_between_reads):
            source = self.store.review_source(self.cycle_id)
        self.assertTrue(changed)
        self.assertEqual(source['logs'][log_key(row)]['load'], 100)
        self.assertEqual([entry['payload']['load'] for entry in source['journals']['logs']], [100])
        self.assertEqual(self.store.logs(self.cycle_id)[log_key(row)]['load'], 120)


if __name__ == '__main__':
    unittest.main()
