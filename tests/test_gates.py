"""Paired gate matrix: every gated endpoint is read open, write closed.

The table below is the contract, one row per endpoint. Each row proves both halves
in the same test run: a tier below the gate gets 403 with the capability named,
the tier at the gate gets through. Reads of an account's own data are open on
every tier; derived views and AI are locked as whole blocks.
"""

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


class GatePairTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='roast-raw-gates-')
        self.addCleanup(folder.cleanup)
        self.db_path = Path(folder.name) / 'gates.sqlite3'
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
        self.clients = {'ultra': self.owner}
        self.cycle_ids = {'ultra': SEED['meta']['planId']}

    def client(self, tier):
        if tier in self.clients:
            return self.clients[tier]
        client = TestClient(self.app)
        code = self.store.create_invite(tier)['code']
        response = client.post('/api/register', json={'username': f'Pair_{tier}', 'password': PASSWORD,
                                                      'invite_code': code})
        self.assertEqual(response.status_code, 200, response.text)
        plan = copy.deepcopy(SEED)
        plan['meta']['planId'] = f'pair-{tier}-cycle'
        plan['meta']['name'] = f'Pair {tier}'
        body = {'plan_json': json.dumps(plan), 'filename': 'plan.json'}
        preview = client.post('/api/plan/import/preview', json=body)
        self.assertEqual(preview.status_code, 200, preview.text)
        data = preview.json()
        confirmed = client.post('/api/plan/import/confirm', json={**body, 'current_id': data['currentId'],
                                                                  'candidate_id': data['candidateId'],
                                                                  'confirm': True})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.clients[tier] = client
        self.cycle_ids[tier] = plan['meta']['planId']
        return client

    def log_payload(self, tier, **changes):
        cycle = self.cycle_ids[tier]
        base = {'cycle_id': cycle, 'week': self.row['week'], 'day': self.row['day'], 'seq': self.row['seq'],
                'load': self.row['loadKg'], 'sets': self.row['sets'], 'reps': self.row['reps'],
                'rpe': None, 'note': ''}
        base.update(changes)
        return base

    def readiness_payload(self, tier):
        return {'cycle_id': self.cycle_ids[tier], 'date': self.row['date'],
                'session_id': f"{self.row['week']}|{self.row['day']}", 'recovery': 4, 'arousal': 5, 'nutrition': 6}

    def metrics_payload(self, tier):
        return {'cycle_id': self.cycle_ids[tier], 'date': self.row['date'], 'bodyweight': 82.5,
                'measurements': {}}

    def attempt_payload(self, tier):
        return {'cycle_id': self.cycle_ids[tier], 'lift': 'squat', 'number': 1, 'load': 140.0, 'result': 'good'}

    def assert_paired(self, below, at, method, path, payload=None, capability=None, params=None):
        """The row under the gate must be 403 and the row at the gate must not be 403."""
        below_response = self.clients[below].request(method, path, json=payload(below) if payload else None,
                                                     params={'cycle_id': self.cycle_ids[below]} if params else None)
        self.assertEqual(below_response.status_code, 403,
                         f'{method} {path} at {below}: {below_response.status_code} {below_response.text}')
        if capability:
            self.assertEqual(below_response.json().get('capability'), capability)
        at_response = self.clients[at].request(method, path, json=payload(at) if payload else None,
                                               params={'cycle_id': self.cycle_ids[at]} if params else None)
        self.assertNotEqual(at_response.status_code, 403,
                            f'{method} {path} at {at}: {at_response.status_code} {at_response.text}')
        return at_response

    def test_own_data_reads_are_open_on_every_tier(self):
        for tier in ('free', 'lite', 'plus', 'pro'):
            client = self.client(tier)
            cycle = self.cycle_ids[tier]
            for path, params in (('/api/plan', None),
                                 ('/api/analysis', None),
                                 ('/api/today', None),
                                 ('/api/log', None),
                                 ('/api/readiness', {'cycle_id': cycle, 'date': self.row['date'],
                                                     'session_id': f"{self.row['week']}|{self.row['day']}"}),
                                 ('/api/body-metrics', {'cycle_id': cycle}),
                                 ('/api/questionnaire', {'cycle_id': cycle})):
                response = client.get(path, params=params)
                self.assertEqual(response.status_code, 200, f'{tier} GET {path}: {response.status_code} {response.text}')

    def test_writes_are_closed_below_their_capability(self):
        self.client('free')
        self.client('lite')
        self.client('plus')
        self.client('pro')
        # Logging is the Free capability: the write stays open.
        response = self.clients['free'].put('/api/log', json=self.log_payload('free'))
        self.assertEqual(response.status_code, 200, response.text)
        # Recovery and body metrics are Plus: Free is read-open, write-closed.
        self.assert_paired('free', 'plus', 'PUT', '/api/readiness', self.readiness_payload, capability='recovery_body')
        self.assert_paired('free', 'plus', 'PUT', '/api/body-metrics', self.metrics_payload, capability='recovery_body')
        # Meet attempts are Lite.
        self.assert_paired('free', 'lite', 'PUT', '/api/attempts', self.attempt_payload, capability='test_week')

    def test_derived_views_are_locked_as_whole_blocks(self):
        self.client('free')
        self.client('lite')
        self.client('plus')
        self.client('pro')
        for below, at, path, capability in (('free', 'plus', '/api/performance', 'lift_register'),
                                            ('lite', 'plus', '/api/performance', 'lift_register'),
                                            ('free', 'plus', '/api/geometry', 'muscle_map'),
                                            ('free', 'pro', '/api/vault', 'vault_ledger'),
                                            ('free', 'pro', '/api/vault/export', 'vault_ledger')):
            self.assert_paired(below, at, 'GET', path, capability=capability, params=True)

    def test_ai_is_locked_below_pro_and_never_calls_without_a_below_tier_write(self):
        self.client('free')
        self.client('plus')
        self.client('pro')
        response = self.clients['plus'].post('/api/ai/outlook', json={'cycle_id': self.cycle_ids['plus']})
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json().get('capability'), 'oracle_ai')
        self.assertEqual(response.json().get('required_tier'), 'pro')
        # Without a key the Pro tier cannot reach DeepSeek either, but the gate already opened.
        response = self.clients['pro'].post('/api/ai/outlook', json={'cycle_id': self.cycle_ids['pro']})
        self.assertNotEqual(response.status_code, 403, response.text)

    def test_session_reports_the_capabilities_the_gates_enforce(self):
        from server.app import membership
        for tier in ('free', 'lite', 'plus', 'pro'):
            body = self.client(tier).get('/api/session').json()
            self.assertEqual(body['tier'], tier)
            for capability in body['capabilities']:
                self.assertTrue(membership.allows(tier, capability), capability)


if __name__ == '__main__':
    unittest.main()
