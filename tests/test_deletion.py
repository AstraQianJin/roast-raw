"""Archive deletion three-piece contract: forced export token, exact-ID confirmation,
full child-table removal with a pre-deletion snapshot; the active cycle is never deletable."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from test_api import GeneratedPlanCase, PLAN_PATH, database_rows, open_db


class DeletionTests(GeneratedPlanCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='roastraw-deletion-')
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.db_path = self.folder / 'deletion.sqlite3'
        with patch.dict(os.environ, {'RR_DB_PATH': str(self.db_path), 'RR_ACCESS_PASSWORD': ''}):
            from server.app.main import create_app
            self.app = create_app(db_path=self.db_path, plan_path=PLAN_PATH)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.active = self.seed['meta']['planId']
        self.app.state.store.save_log(self.active, self.seed['workouts'][0],
                                      {'load': 100.0, 'sets': 3, 'reps': 5, 'rpe': 8, 'note': 'pre-import'})
        plan = copy.deepcopy(self.seed)
        plan['meta']['planId'] = 'cycle-next'
        body = {'plan_json': json.dumps(plan), 'filename': 'candidate.json'}
        preview = self.client.post('/api/plan/import/preview', json=body)
        self.assertEqual(preview.status_code, 200, preview.text)
        preview = preview.json()
        confirmed = self.client.post('/api/plan/import/confirm',
                                     json={**body, 'current_id': preview['currentId'],
                                           'candidate_id': preview['candidateId'], 'confirm': True})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.archived = confirmed.json()['archived_cycle_id']
        self.assertEqual(self.archived, self.active)
        self.active = 'cycle-next'

    def delete(self, cycle_id, token, confirm=None, expected=200):
        response = self.client.request('DELETE', f'/api/archive/{cycle_id}',
                                       json={'token': token, 'confirm': confirm if confirm is not None else cycle_id})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json() if expected == 200 else None

    def prepare(self, cycle_id, expected=200):
        response = self.client.post('/api/archive/delete/prepare', json={'cycle_id': cycle_id})
        self.assertEqual(response.status_code, expected, response.text)
        return response

    def test_active_cycle_cannot_be_prepared_or_deleted(self):
        self.prepare(self.active, expected=409)
        self.delete(self.active, 'anything', expected=409)
        self.assertEqual(self.client.get('/api/plan').json()['meta']['planId'], self.active)

    def test_unknown_cycle_rejects(self):
        self.prepare('missing', expected=404)
        self.delete('missing', 'token', expected=404)

    def test_delete_requires_prepared_token_and_exact_confirmation(self):
        before = database_rows(self.db_path)
        self.assertTrue(any(self.archived in row for row in before['logs']))
        self.delete(self.archived, 'forged', expected=409)
        self.assertEqual(database_rows(self.db_path), before)
        export = self.prepare(self.archived)
        self.assertIn('attachment', export.headers['content-disposition'])
        body = export.json()
        self.assertEqual(body['cycle_id'], self.archived)
        self.assertEqual(body['review']['cycle']['id'], self.archived)
        self.assertIn('plan', body['review'])
        prepared_rows = database_rows(self.db_path)
        self.delete(self.archived, body['token'], confirm='typo', expected=422)
        self.assertEqual(database_rows(self.db_path), prepared_rows)
        self.delete(self.archived, body['token'])
        after = database_rows(self.db_path)
        for table, rows in after.items():
            self.assertFalse(any(self.archived in row for row in rows), f'{table} still holds deleted cycle rows')
        self.assertEqual(self.client.get('/api/review', params={'cycle_id': self.archived}).status_code, 404)
        self.delete(self.archived, body['token'], expected=404)
        self.assertEqual(self.client.get('/api/plan').json()['meta']['planId'], 'cycle-next')
        with open_db(self.db_path) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
        snapshots = sorted((self.db_path.parent / 'backups').glob('*.sqlite3'))
        self.assertTrue(snapshots, 'deletion must snapshot the database first')
        with open_db(snapshots[-1]) as db:
            self.assertTrue(db.execute('SELECT 1 FROM cycles WHERE id=?', (self.archived,)).fetchone(),
                            'pre-deletion snapshot must still contain the deleted cycle')

    def test_prepare_refresh_invalidates_the_older_token(self):
        first = self.prepare(self.archived).json()['token']
        second = self.prepare(self.archived).json()['token']
        self.assertNotEqual(first, second)
        self.delete(self.archived, first, expected=409)
        self.delete(self.archived, second)


if __name__ == '__main__':
    unittest.main()