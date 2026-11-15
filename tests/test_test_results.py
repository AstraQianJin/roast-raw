"""Test-day results beyond SBD: v7 table, gated writes, readback and the CSV exit."""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.main import create_app

PASSWORD = 'barbell-2018'
GATE = {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra', 'DEEPSEEK_API_KEY': ''}
SEED = json.loads((ROOT / 'data' / 'plan.json').read_text(encoding='utf-8'))
TEST_CYCLE = SEED['meta']['planId']
ITEMS = {item['id']: item for item in SEED['testPlan']['items']}
HEADER = 'cycle_id,item_id,group,label,load_kg,reps,duration_s,hr,note,updated_at'


class TestResultTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='roast-raw-tests-')
        self.addCleanup(folder.cleanup)
        self.db_path = Path(folder.name) / 'tests.sqlite3'
        env = patch.dict(os.environ, GATE)
        env.start()
        self.addCleanup(env.stop)
        self.app = create_app(db_path=self.db_path)
        self.owner = TestClient(self.app)
        self.owner.__enter__()
        self.addCleanup(self.owner.__exit__, None, None, None)
        self.store = self.app.state.store
        self.assertEqual(self.owner.post('/api/login', json={'username': 'Astra',
                                                             'password': GATE['RR_ACCESS_PASSWORD']}).status_code, 200)

    def guest(self, username='Guest_one', tier='free', plan_id='tests-cycle'):
        client = TestClient(self.app)
        code = self.store.create_invite(tier)['code']
        self.assertEqual(client.post('/api/register', json={'username': username, 'password': PASSWORD,
                                                            'invite_code': code}).status_code, 200)
        plan = copy.deepcopy(SEED)
        plan['meta']['planId'] = plan_id
        body = {'plan_json': json.dumps(plan), 'filename': 'plan.json'}
        preview = client.post('/api/plan/import/preview', json=body).json()
        confirmed = client.post('/api/plan/import/confirm', json={**body, 'current_id': preview['currentId'],
                                                                  'candidate_id': preview['candidateId'],
                                                                  'confirm': True})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        return client, plan_id

    def test_read_lists_every_item_with_no_result_yet(self):
        response = self.owner.get('/api/test-results', params={'cycle_id': TEST_CYCLE})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload['cycle_id'], TEST_CYCLE)
        self.assertEqual(len(payload['items']), 9)
        self.assertEqual([item['id'] for item in payload['items']],
                         ['low_bar_squat', 'wide_grip_bench', 'sumo_deadlift', 'power_clean',
                          'ohp', 'pull_up', 'dip', 'barbell_row', 'five_km'])
        self.assertTrue(all(item['result'] is None for item in payload['items']))
        self.assertEqual(payload['dates']['fivekm'], SEED['testPlan']['dates']['sbd'])

    def test_write_is_closed_below_the_test_week_capability(self):
        client, cycle = self.guest(tier='free')
        response = client.put('/api/test-results', json={'cycle_id': cycle, 'item_id': 'low_bar_squat', 'load': 100})
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()['capability'], 'test_week')
        self.assertEqual(client.get('/api/test-results', params={'cycle_id': cycle}).status_code, 200)

    def test_lifting_item_needs_a_load_on_a_half_kilo_step(self):
        client, cycle = self.guest(tier='ultra')
        base = {'cycle_id': cycle, 'item_id': 'low_bar_squat'}
        self.assertEqual(client.put('/api/test-results', json=base).status_code, 422)
        bad = client.put('/api/test-results', json={**base, 'load': 100.7})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(bad.json()['detail'], 'Test loads must be a multiple of 0.5 kg')
        unknown = client.put('/api/test-results', json={'cycle_id': cycle, 'item_id': 'back_squat', 'load': 100})
        self.assertEqual(unknown.status_code, 422)
        self.assertEqual(unknown.json()['detail'], 'Unknown test item for this cycle')

    def test_run_needs_a_duration_and_ignores_a_load(self):
        client, cycle = self.guest(tier='ultra')
        base = {'cycle_id': cycle, 'item_id': 'five_km'}
        self.assertEqual(client.put('/api/test-results', json=base).status_code, 422)
        saved = client.put('/api/test-results', json={**base, 'duration_s': 1470, 'hr': 158, 'note': 'windy'})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['duration_s'], 1470)

    def test_saved_result_round_trips_and_upserts_with_one_journal_row(self):
        client, cycle = self.guest(tier='ultra')
        payload = {'cycle_id': cycle, 'item_id': 'sumo_deadlift', 'load': 150, 'reps': 1}
        self.assertEqual(client.put('/api/test-results', json=payload).status_code, 200)
        self.assertEqual(client.put('/api/test-results', json={**payload, 'load': 155}).status_code, 200)
        items = {item['id']: item['result'] for item in
                 client.get('/api/test-results', params={'cycle_id': cycle}).json()['items']}
        self.assertEqual(items['sumo_deadlift']['load'], 155)
        self.assertIsNone(items['ohp'])
        with self.store.connect() as db:
            journals = db.execute("SELECT payload FROM records_journal WHERE kind='test'").fetchall()
            rows = db.execute('SELECT count(*) FROM test_results').fetchone()[0]
        self.assertEqual(rows, 1)
        self.assertEqual(len(journals), 2)

    def test_csv_carries_the_recorded_rows_and_quotes_notes(self):
        client, cycle = self.guest(tier='ultra')
        note = 'felt heavy, "clean" pull'
        self.assertEqual(client.put('/api/test-results', json={'cycle_id': cycle, 'item_id': 'power_clean',
                                                               'load': 85, 'note': note}).status_code, 200)
        self.assertEqual(client.put('/api/test-results', json={'cycle_id': cycle, 'item_id': 'five_km',
                                                               'duration_s': 1560, 'hr': 150}).status_code, 200)
        response = client.get('/api/export/tests.csv')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('text/csv', response.headers['content-type'])
        self.assertIn('tests-cycle-tests.csv', response.headers['content-disposition'])
        lines = response.text.splitlines()
        self.assertEqual(lines[0], HEADER)
        self.assertEqual(len(lines), 3)
        self.assertIn('"' + note.replace('"', '""') + '"', lines[1] + lines[2])
        self.assertTrue(any('Power Clean' in line for line in lines[1:]))

    def test_two_accounts_never_see_each_others_results(self):
        first, cycle_one = self.guest('Guest_one', 'ultra')
        second, cycle_two = self.guest('Guest_two', 'ultra', 'tests-cycle-b')
        self.assertEqual(first.put('/api/test-results', json={'cycle_id': cycle_one, 'item_id': 'ohp',
                                                              'load': 55}).status_code, 200)
        self.assertEqual(second.get('/api/export/tests.csv').text.splitlines(), [HEADER])
        items = {item['id']: item['result'] for item in
                 second.get('/api/test-results', params={'cycle_id': cycle_two}).json()['items']}
        self.assertIsNone(items['ohp'])

    def test_live_database_upgrades_to_v7_without_touching_existing_rows(self):
        existing = self.owner.get('/api/plan').json()
        with self.store.connect() as db:
            before = {name: db.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
                      for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                                "AND name NOT LIKE 'sqlite_%'")}
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 7)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            columns = [row[1] for row in db.execute('PRAGMA table_info(test_results)')]
        self.assertEqual(columns, ['account_id', 'cycle_id', 'item_id', 'group_name', 'load', 'reps',
                                   'duration_s', 'hr', 'note', 'updated_at'])
        self.assertEqual(self.owner.get('/api/plan').json(), existing)
        self.assertGreater(before['plans'], 0)


if __name__ == '__main__':
    unittest.main()
