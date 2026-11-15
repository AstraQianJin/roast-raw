"""Table-level isolation and the orphan audit.

Two properties are proven here:

1. Every table that hangs off a cycle is reachable by the orphan audit, and a
   database written through the real API has no orphans. A planted orphan must
   be reported, otherwise the audit is vacuous.
2. A second account cannot read a single row written by the first, table by
   table, even when the row keys are identical. Same `planId` in two accounts is
   blocked by the global cycles primary key until 0.32 rebuilds it, so this
   account pair uses distinct plan ids and identical week/day/seq keys.
"""

import copy
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.main import create_app
from server.app.questionnaire import skeleton
from server.tools import audit_orphans

PASSWORD = 'barbell-2018'
GATE = {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra', 'DEEPSEEK_API_KEY': ''}
SEED = json.loads((ROOT / 'data' / 'plan.json').read_text(encoding='utf-8'))


def plan_copy(plan_id):
    plan = copy.deepcopy(SEED)
    plan['meta']['planId'] = plan_id
    plan['meta']['name'] = f'Isolation {plan_id}'
    return plan


class IsolationCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='roast-raw-iso-')
        self.addCleanup(folder.cleanup)
        self.db_path = Path(folder.name) / 'isolation.sqlite3'
        env = patch.dict(os.environ, GATE)
        env.start()
        self.addCleanup(env.stop)
        self.app = create_app(db_path=self.db_path)
        self.owner = TestClient(self.app)
        self.owner.__enter__()
        self.addCleanup(self.owner.__exit__, None, None, None)
        self.store = self.app.state.store
        response = self.owner.post('/api/login', json={'username': 'Astra', 'password': GATE['RR_ACCESS_PASSWORD']})
        self.assertEqual(response.status_code, 200, response.text)
        self.row = self.main_row(SEED)

    @staticmethod
    def main_row(plan):
        for row in plan['workouts']:
            if row['bucket'] == 'main' and row.get('loadKg'):
                return row
        raise AssertionError('the plan carries no loaded main row')

    def account(self, username, tier):
        client = TestClient(self.app)
        code = self.store.create_invite(tier)['code']
        response = client.post('/api/register', json={'username': username, 'password': PASSWORD, 'invite_code': code})
        self.assertEqual(response.status_code, 200, response.text)
        return client

    def import_plan(self, client, plan):
        body = {'plan_json': json.dumps(plan), 'filename': 'plan.json'}
        preview = client.post('/api/plan/import/preview', json=body)
        self.assertEqual(preview.status_code, 200, preview.text)
        data = preview.json()
        return client.post('/api/plan/import/confirm', json={
            **body, 'current_id': data['currentId'], 'candidate_id': data['candidateId'], 'confirm': True}), data

    def write_every_table(self, client, cycle_id):
        """One write per cycle-scoped table through the routes that own them."""
        row = self.main_row(SEED)
        self.assertEqual(client.put('/api/log', json={'cycle_id': cycle_id, 'week': row['week'], 'day': row['day'],
                                                      'seq': row['seq'], 'load': row['loadKg'], 'sets': row['sets'],
                                                      'reps': row['reps'], 'rpe': None, 'note': 'isolation'}).status_code, 200)
        self.assertEqual(client.put('/api/readiness', json={'cycle_id': cycle_id, 'date': row['date'],
                                                            'session_id': f"{row['week']}|{row['day']}",
                                                            'recovery': 4, 'arousal': 5, 'nutrition': 6}).status_code, 200)
        self.assertEqual(client.put('/api/body-metrics', json={'cycle_id': cycle_id, 'date': row['date'],
                                                              'bodyweight': 82.5,
                                                              'measurements': {'waist': 80.0}}).status_code, 200)
        self.assertEqual(client.put('/api/questionnaire', json={'cycle_id': cycle_id, 'status': 'draft',
                                                                'payload': skeleton()}).status_code, 200)
        self.assertEqual(client.put('/api/attempts', json={'cycle_id': cycle_id, 'lift': 'squat', 'number': 1,
                                                           'load': 140.0, 'result': 'good'}).status_code, 200)

    def orphans(self):
        return audit_orphans.audit(self.db_path)


class OrphanAuditTests(IsolationCase):
    def test_every_cycle_scoped_table_has_a_link(self):
        """A new child table cannot enter the schema without an audited link."""
        linked = {f'{table}.{column}' for table, column, *_ in audit_orphans.LINKS}
        with closing(sqlite3.connect(f'file:{self.db_path.as_posix()}?mode=ro', uri=True)) as db:
            for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                info = [row[1] for row in db.execute(f'PRAGMA table_info({table})')]
                for column in ('cycle_id', 'account_id'):
                    if column in info:
                        self.assertIn(f'{table}.{column}', linked,
                                      f'{table}.{column} exists but no orphan link covers it')

    def test_api_written_database_has_no_orphans(self):
        self.write_every_table(self.owner, SEED['meta']['planId'])
        guest = self.account('Guest_one', 'plus')
        self.import_plan(guest, plan_copy('iso-b-cycle'))
        self.write_every_table(guest, 'iso-b-cycle')
        result = self.orphans()
        self.assertEqual(result['total'], 0, result['orphans'])
        self.assertEqual(result['skipped'], [], result['skipped'])
        self.assertGreaterEqual(len(result['checked']), 17)

    def test_planted_orphan_is_reported(self):
        self.write_every_table(self.owner, SEED['meta']['planId'])
        with closing(sqlite3.connect(self.db_path)) as db:
            account = db.execute('SELECT account_id FROM cycles LIMIT 1').fetchone()[0]
            db.execute("INSERT INTO logs(account_id, cycle_id, key, date, session_id, exercise_id, load, reps, rpe,"
                       " set_count, note, updated_at)"
                       " VALUES(?, 'ghost-cycle', '1|A|1', '2026-11-23', '1|A', 'hb-squat', 100.0, 5, NULL, 3,"
                       " 'orphan', '2026-11-23T00:00:00+00:00')", (account,))
            db.commit()
        result = self.orphans()
        self.assertEqual(result['orphans'], {'logs.cycle_id->cycles.id': 1}, result['orphans'])
        self.assertNotEqual(audit_orphans.main(['--db', str(self.db_path)]), 0)

    def test_clean_database_exits_zero(self):
        self.assertEqual(audit_orphans.main(['--db', str(self.db_path)]), 0)


class TableIsolationTests(IsolationCase):
    def test_second_account_reads_none_of_the_first_account_rows(self):
        guest = self.account('Guest_one', 'plus')
        _, data = self.import_plan(guest, plan_copy('iso-b-cycle'))
        self.assertTrue(data['candidateId'])
        self.write_every_table(self.owner, SEED['meta']['planId'])
        row = self.main_row(SEED)

        # B has its own cycle with the same week/day/seq keys and no rows at all.
        self.assertEqual(guest.get('/api/log').json()['logs'], {})
        readiness = guest.get('/api/readiness', params={'cycle_id': 'iso-b-cycle', 'date': row['date'],
                                                        'session_id': f"{row['week']}|{row['day']}"}).json()
        self.assertIsNone(readiness['record'])
        self.assertEqual(guest.get('/api/body-metrics', params={'cycle_id': 'iso-b-cycle'}).json()['records'], [])
        self.assertEqual(guest.get('/api/questionnaire', params={'cycle_id': 'iso-b-cycle'}).json()['status'], 'empty')
        attempts = guest.get('/api/attempts', params={'cycle_id': 'iso-b-cycle'}).json()
        self.assertTrue(all(item is None for lift in attempts['lifts'].values() for item in lift['attempts']))

        # The owner's rows survive untouched after B writes its own copies.
        self.write_every_table(guest, 'iso-b-cycle')
        owner_logs = self.owner.get('/api/log').json()['logs']
        key = f"{row['week']}|{row['day']}|{row['seq']}"
        self.assertEqual(owner_logs[key]['note'], 'isolation')
        self.assertEqual(guest.get('/api/log').json()['logs'][key]['note'], 'isolation')
        with closing(sqlite3.connect(self.db_path)) as db:
            owners = {name for (name,) in db.execute('SELECT account_id FROM cycles')}
        self.assertEqual(len(owners), 2, owners)

    def test_foreign_cycle_is_invisible_even_when_the_id_is_guessed(self):
        guest = self.account('Guest_one', 'free')
        for path in ('/api/plan', '/api/log', '/api/questionnaire', '/api/attempts'):
            response = guest.get(path, params={'cycle_id': SEED['meta']['planId']})
            self.assertIn(response.status_code, (404, 403), f'{path} leaked {response.status_code}')
        self.assertEqual(guest.get('/api/cycle').json(), {'cycles': [], 'active_cycle_id': None})


if __name__ == '__main__':
    unittest.main()
