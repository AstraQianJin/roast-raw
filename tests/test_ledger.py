"""Per-account ledgers, tier gates and the zero-loss ledger migration."""

from contextlib import closing
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app import membership
from server.app.main import create_app
from server.app.stats.variations import digest
from server.app.store import AiQuotaError, Store

PASSWORD = 'barbell-2018'
GATE = {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra', 'DEEPSEEK_API_KEY': ''}
SEED = json.loads((ROOT / 'data' / 'plan.json').read_text(encoding='utf-8'))


def rows(path):
    with closing(sqlite3.connect(path)) as db:
        tables = [name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {table: sorted(db.execute(f'SELECT * FROM {table}').fetchall(), key=repr) for table in tables}


def columns(path, table):
    with closing(sqlite3.connect(path)) as db:
        return [row[1] for row in db.execute(f'PRAGMA table_info({table})')]


def other_plan(plan_id='ledger-b-cycle'):
    plan = copy.deepcopy(SEED)
    plan['meta']['planId'] = plan_id
    return plan


class LedgerTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db_path = Path(folder.name) / 'ledger.sqlite3'
        env = patch.dict(os.environ, GATE)
        env.start()
        self.addCleanup(env.stop)
        self.app = create_app(db_path=self.db_path)
        self.owner = TestClient(self.app)
        self.owner.__enter__()
        self.addCleanup(self.owner.__exit__, None, None, None)
        self.store = self.app.state.store
        self.assertEqual(self.owner.post('/api/login', json={'username': 'Astra', 'password': GATE['RR_ACCESS_PASSWORD']}).status_code, 200)
        self.cycle = SEED['meta']['planId']

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
        return client.post('/api/plan/import/confirm', json={**body, 'current_id': data['currentId'],
                                                              'candidate_id': data['candidateId'], 'confirm': True}), data

    def test_new_account_starts_with_an_empty_ledger_and_owner_keeps_the_seed(self):
        guest = self.account('Guest_one', 'free')
        self.assertEqual(guest.get('/api/cycle').json(), {'cycles': [], 'active_cycle_id': None})
        self.assertEqual(guest.get('/api/plan').status_code, 404)
        self.assertEqual(guest.get('/api/log').status_code, 404)
        self.assertEqual(self.owner.get('/api/plan').json(), SEED)
        self.assertEqual(self.owner.get('/api/cycle').json()['active_cycle_id'], self.cycle)

    def test_two_accounts_never_see_each_others_records(self):
        guest = self.account('Guest_two', 'plus')
        confirmed, preview = self.import_plan(guest, other_plan())
        self.assertEqual(preview['currentId'], Store.EMPTY_SOURCE_ID)
        self.assertIsNone(preview['current'])
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json(), {'saved': True, 'active_cycle_id': 'ledger-b-cycle', 'archived_cycle_id': None})
        row = SEED['workouts'][0]
        log = {'week': row['week'], 'day': row['day'], 'seq': row['seq'], 'load': 100.0, 'sets': 1, 'reps': 3, 'rpe': None, 'note': ''}
        self.assertEqual(guest.put('/api/log', json={**log, 'cycle_id': 'ledger-b-cycle'}).status_code, 200)
        self.assertEqual(guest.put('/api/log', json={**log, 'cycle_id': self.cycle}).status_code, 404)
        self.assertEqual(self.owner.get('/api/log').json()['logs'], {})
        self.assertEqual(len(guest.get('/api/log').json()['logs']), 1)
        for path in (f'/api/plan?cycle_id=ledger-b-cycle', f'/api/log?cycle_id=ledger-b-cycle', '/api/review?cycle_id=ledger-b-cycle'):
            self.assertEqual(self.owner.get(path).status_code, 404, path)
        for path in (f'/api/plan?cycle_id={self.cycle}', f'/api/questionnaire?cycle_id={self.cycle}', f'/api/review?cycle_id={self.cycle}'):
            self.assertEqual(guest.get(path).status_code, 404, path)
        self.assertEqual([cycle['id'] for cycle in self.owner.get('/api/cycle').json()['cycles']], [self.cycle])
        self.assertEqual(guest.post('/api/archive/delete/prepare', json={'cycle_id': self.cycle}).status_code, 404)

    def test_cycle_ids_stay_unique_across_accounts(self):
        guest = self.account('Guest_three', 'plus')
        body = {'plan_json': json.dumps(SEED), 'filename': 'plan.json'}
        response = guest.post('/api/plan/import/preview', json=body)
        self.assertEqual(response.status_code, 409)
        self.assertIn('already exists', response.json()['error'])

    def test_every_gate_is_403_below_and_open_at_its_tier(self):
        clients = {tier: self.account(f'Gate_{tier}', tier) for tier in ('free', 'lite', 'plus', 'pro')}
        day = SEED['workouts'][0]['date']
        gates = [
            ('get', '/api/performance', None, 'lift_register'),
            ('get', '/api/geometry', None, 'muscle_map'),
            ('put', '/api/readiness', {'cycle_id': self.cycle, 'date': day, 'session_id': 'daily', 'recovery': 5}, 'recovery_body'),
            ('put', '/api/body-metrics', {'cycle_id': self.cycle, 'date': day, 'bodyweight': 82.5}, 'recovery_body'),
            ('put', '/api/attempts', {'cycle_id': self.cycle, 'lift': 'squat', 'number': 1, 'load': 150.0}, 'test_week'),
            ('post', '/api/ai/outlook', {'cycle_id': self.cycle}, 'oracle_ai'),
            ('post', '/api/ai/chat', {'cycle_id': self.cycle, 'message': 'Hi'}, 'oracle_ai'),
            ('get', '/api/vault', None, 'vault_ledger'),
            ('get', '/api/vault/export', None, 'vault_ledger'),
        ]
        below = {'lite': 'free', 'plus': 'lite', 'pro': 'plus'}
        for method, path, body, capability in gates:
            need = membership.CAPABILITY_TIER[capability]
            low = getattr(clients[below[need]], method)(path, **({'json': body} if body else {}))
            self.assertEqual(low.status_code, 403, f'{path} below {need}')
            self.assertEqual(low.json()['required_tier'], need, path)
            self.assertEqual(low.json()['capability'], capability, path)
            at = getattr(clients[need], method)(path, **({'json': body} if body else {}))
            self.assertNotEqual(at.status_code, 403, f'{path} at {need}')
            owner = getattr(self.owner, method)(path, **({'json': body} if body else {}))
            self.assertNotEqual(owner.status_code, 403, f'{path} owner')
            if method == 'get' or capability in ('recovery_body', 'test_week'):
                self.assertEqual(owner.status_code, 200, f'{path} owner {owner.text[:200]}')
        self.assertEqual(self.owner.post('/api/ai/outlook', json={'cycle_id': self.cycle}).status_code, 503)

    def test_downgraded_reads_and_exports_stay_open(self):
        free = self.account('Reader_free', 'free')
        confirmed, _ = self.import_plan(free, other_plan('free-cycle'))
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        for path in ('/api/plan', '/api/log', '/api/analysis', '/api/today', '/api/review', '/api/review/export',
                     '/api/questionnaire?cycle_id=free-cycle', '/api/readiness?cycle_id=free-cycle&date=' + SEED['workouts'][0]['date'],
                     '/api/body-metrics?cycle_id=free-cycle', '/api/attempts?cycle_id=free-cycle', '/api/archive'):
            self.assertEqual(free.get(path).status_code, 200, path)

    def test_ai_quota_counts_per_account(self):
        first, second = self.store.for_account(901), self.store.for_account(902)
        for _ in range(Store.AI_DAILY_LIMIT):
            first.reserve_ai_call(self.cycle, '2026-11-15', 'outlook', 'p', [])
        with self.assertRaises(AiQuotaError):
            first.reserve_ai_call(self.cycle, '2026-11-15', 'outlook', 'p', [])
        self.assertEqual(first.ai_quota('2026-11-15')['remaining'], 0)
        self.assertEqual(second.ai_quota('2026-11-15')['remaining'], Store.AI_DAILY_LIMIT)
        second.reserve_ai_call(self.cycle, '2026-11-15', 'outlook', 'p', [])
        self.assertEqual(second.ai_quota('2026-11-15')['used'], 1)


class LedgerMigrationTests(unittest.TestCase):
    def build_legacy(self, folder, owner=None):
        path = Path(folder) / 'legacy.sqlite3'
        store = Store(path)
        store.initialize(SEED)
        for step in (store.upgrade, store.upgrade_prescriptions, store.upgrade_questionnaire, store.upgrade_ai,
                     store.upgrade_accounts, store.upgrade_membership):
            step()
        if owner:
            store.create_account('Someone', PASSWORD)
            store.create_account(owner, PASSWORD)
        row = SEED['workouts'][0]
        store.save_log(SEED['meta']['planId'], row, {'load': 120.0, 'sets': 2, 'reps': 3, 'rpe': 8.0, 'note': 'legacy'})
        store.save_metrics(SEED['meta']['planId'], {'date': row['date'], 'bodyweight': 83.0, 'bodyfat': None, 'measurements': {}})
        store.reserve_ai_call(SEED['meta']['planId'], '2026-11-01', 'outlook', 'legacy prompt', [])
        return path, store

    def test_snapshot_first_and_every_row_survives(self):
        with tempfile.TemporaryDirectory() as folder:
            path, store = self.build_legacy(folder, owner='Astra')
            before = rows(path)
            source_before = digest(store.review_source(SEED['meta']['planId']))
            existing = set((path.parent / 'backups').glob('*.sqlite3'))
            store.upgrade_ledger('Astra')
            created = set((path.parent / 'backups').glob('*.sqlite3')) - existing
            self.assertEqual(len(created), 1)
            self.assertEqual(rows(next(iter(created))), before)
            after = rows(path)
            owner = store.owner_id('Astra')
            self.assertEqual(store.open_ledger(), owner)
            self.assertNotEqual(owner, store.owner_id('Someone'))
            for table, records in before.items():
                if table in Store.LEDGER_ROOTS:
                    self.assertEqual(columns(path, table)[-1], 'account_id')
                    self.assertEqual(sorted((record[:-1] for record in after[table]), key=repr), records, table)
                    self.assertEqual({record[-1] for record in after[table]}, {owner}, table)
                else:
                    self.assertEqual(after[table], records, table)
            self.assertEqual(after['ledger_meta'], [('open_ledger', str(owner))])
            self.assertEqual(digest(store.for_account(owner).review_source(SEED['meta']['planId'])), source_before)
            self.assertIsNone(store.for_account(owner + 1000).review_source(SEED['meta']['planId']))
            store.upgrade_ledger('Astra')
            self.assertEqual(rows(path), after, 'the ledger migration runs once')

    def test_legacy_database_upgrades_through_the_app_without_changing_api_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path, store = self.build_legacy(folder)
            with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': '', 'DEEPSEEK_API_KEY': ''}):
                with TestClient(create_app(db_path=path)) as client:
                    self.assertEqual(client.get('/api/plan').json(), SEED)
                    logs = client.get('/api/log').json()['logs']
                    self.assertEqual(logs[f"{SEED['workouts'][0]['week']}|{SEED['workouts'][0]['day']}|{SEED['workouts'][0]['seq']}"]['note'], 'legacy')
                    self.assertEqual(client.get(f"/api/body-metrics?cycle_id={SEED['meta']['planId']}").json()['records'][0]['bodyweight'], 83.0)
                    self.assertEqual(client.get(f"/api/ai/status?cycle_id={SEED['meta']['planId']}").json()['quota']['limit'], Store.AI_DAILY_LIMIT)
            self.assertEqual(Store(path).open_ledger(), 0)


if __name__ == '__main__':
    unittest.main()
