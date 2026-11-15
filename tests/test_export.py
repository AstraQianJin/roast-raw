"""The CSV exit: the account's own recorded rows, quotable, and never a gated write."""

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
HEADER = 'cycle_id,week,day,date,session_id,seq,movement,bucket,prescribed_load_kg,actual_load_kg,sets,reps,rpe,note,updated_at'


class ExportTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='roast-raw-export-')
        self.addCleanup(folder.cleanup)
        self.db_path = Path(folder.name) / 'export.sqlite3'
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
        self.row = next(row for row in SEED['workouts'] if row['bucket'] == 'main' and row.get('loadKg'))

    def guest(self, username='Guest_one', tier='free', plan_id='export-cycle'):
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
        return client

    def test_empty_log_exports_a_header_only(self):
        client = self.guest()
        response = client.get('/api/export/logs.csv')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('text/csv', response.headers['content-type'])
        self.assertIn('export-cycle-logs.csv', response.headers['content-disposition'])
        self.assertEqual(response.text.splitlines(), [HEADER])

    def test_recorded_rows_round_trip_with_quoting(self):
        client = self.guest(tier='plus')
        note = 'belt on, "tight" setup'
        saved = client.put('/api/log', json={'cycle_id': 'export-cycle', 'week': self.row['week'], 'day': self.row['day'],
                                             'seq': self.row['seq'], 'load': self.row['loadKg'] + 2.5,
                                             'sets': 3, 'reps': 5, 'rpe': 8.5, 'note': note})
        self.assertEqual(saved.status_code, 200, saved.text)
        lines = client.get('/api/export/logs.csv').text.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], HEADER)
        cells = lines[1].split(',')
        self.assertEqual(cells[0], 'export-cycle')
        self.assertEqual(cells[8], str(self.row['loadKg']))
        self.assertEqual(cells[9], str(self.row['loadKg'] + 2.5))
        self.assertEqual(cells[10:13], ['3', '5', '8.5'])
        self.assertIn('"' + note.replace('"', '""') + '"', lines[1])

    def test_export_is_read_open_on_the_free_tier(self):
        client = self.guest()
        for path in ('/api/export/logs.csv', '/api/review/export'):
            self.assertEqual(client.get(path).status_code, 200, path)

    def test_two_accounts_export_their_own_rows_only(self):
        first = self.guest('Guest_one', 'free')
        second = self.guest('Guest_two', 'free', 'export-cycle-b')
        payload = {'cycle_id': 'export-cycle', 'week': self.row['week'], 'day': self.row['day'],
                   'seq': self.row['seq'], 'load': self.row['loadKg'], 'sets': 2, 'reps': 5, 'rpe': None,
                   'note': 'owner only'}
        self.assertEqual(first.put('/api/log', json=payload).status_code, 200)
        self.assertEqual(len(first.get('/api/export/logs.csv').text.splitlines()), 2)
        self.assertEqual(second.get('/api/export/logs.csv').text.splitlines(), [HEADER])


if __name__ == '__main__':
    unittest.main()
