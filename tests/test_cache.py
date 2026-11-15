"""Bounded scoped-store cache and the fail-closed startup gate."""

import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.main import create_app
from server.app.store import Store


class CacheTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.store = Store(Path(holder.name) / 'cache.sqlite3')

    def test_scoped_view_never_shares_the_base_cache(self):
        scoped = self.store.for_account(11)
        self.assertIsNot(scoped._scoped, self.store._scoped)
        self.assertEqual(len(scoped._scoped), 0)
        self.assertEqual(scoped.ledger, 11)
        self.assertEqual(self.store.for_account(11).ledger, 11)

    def test_eviction_keeps_the_most_recent_accounts_only(self):
        for account in range(1, 71):
            self.store.for_account(account)
        self.assertEqual(len(self.store._scoped), Store.SCOPED_MAX)
        self.assertNotIn(1, self.store._scoped)
        self.assertIn(70, self.store._scoped)
        self.assertEqual(self.store.for_account(1).ledger, 1)
        self.assertEqual(len(self.store._scoped), Store.SCOPED_MAX)

    def test_recent_use_moves_to_the_back_of_the_queue(self):
        for account in range(1, 65):
            self.store.for_account(account)
        self.store.for_account(1)
        self.store.for_account(65)
        self.assertIn(1, self.store._scoped)
        self.assertNotIn(2, self.store._scoped)

    def test_idle_views_expire_after_the_ttl(self):
        start = 1000.0
        with patch('server.app.store.time.monotonic', side_effect=[start, start + Store.SCOPED_TTL + 5]):
            self.store.for_account(7)
            self.store.for_account(8)
        self.assertNotIn(7, self.store._scoped)
        self.assertIn(8, self.store._scoped)

    def test_concurrent_accounts_are_stable(self):
        errors = []

        def worker(account):
            try:
                for _ in range(30):
                    view = self.store.for_account(account)
                    if view.ledger != account:
                        errors.append(f'ledger {view.ledger} != {account}')
            except Exception as failure:  # surfaces the real problem instead of hiding it
                errors.append(repr(failure))

        threads = [threading.Thread(target=worker, args=(account,)) for account in range(1, 9)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertLessEqual(len(self.store._scoped), Store.SCOPED_MAX)


class StartupGateTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.db_path = Path(holder.name) / 'gate.sqlite3'

    def test_refuses_to_start_without_an_access_password(self):
        environment = {key: value for key, value in os.environ.items()
                       if key not in ('RR_ACCESS_PASSWORD', 'RR_ALLOW_OPEN_FIXTURE')}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(RuntimeError):
                create_app(db_path=self.db_path)

    def test_fixture_switch_starts_without_a_password_but_the_api_stays_account_scoped(self):
        environment = {key: value for key, value in os.environ.items()
                       if key not in ('RR_ACCESS_PASSWORD', 'RR_ACCESS_USERNAME')}
        environment['RR_ALLOW_OPEN_FIXTURE'] = '1'
        with patch.dict(os.environ, environment, clear=True):
            app = create_app(db_path=self.db_path)
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/health').status_code, 200)
            session = client.get('/api/session').json()
            self.assertTrue(session['fixture'])
            self.assertTrue(session['authenticated'])
            self.assertIsNone(session['username'])
            self.assertEqual(client.get('/api/plan').status_code, 200)

    def test_a_password_still_gates_the_api_even_with_the_fixture_switch(self):
        environment = {key: value for key, value in os.environ.items()
                       if key not in ('RR_ACCESS_PASSWORD', 'RR_ACCESS_USERNAME')}
        environment.update({'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra',
                            'RR_ALLOW_OPEN_FIXTURE': '1'})
        with patch.dict(os.environ, environment, clear=True):
            app = create_app(db_path=self.db_path)
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/plan').status_code, 401)
            self.assertEqual(client.get('/api/health').status_code, 200)


if __name__ == '__main__':
    unittest.main()
