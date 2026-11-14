"""Membership tiers, invite codes, redemption and the five-device session limit."""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app import membership
from server.app.main import create_app
from server.app.store import InviteError

PASSWORD = 'barbell-2018'
GATE = {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra'}


class MembershipTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db_path = Path(folder.name) / 'm.sqlite3'
        env = patch.dict(os.environ, GATE)
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(create_app(db_path=self.db_path))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.store = self.client.app.state.store

    def register(self, username, code, client=None):
        return (client or self.client).post('/api/register', json={'username': username, 'password': PASSWORD, 'invite_code': code})

    def code(self, tier, **options):
        return self.store.create_invite(tier, **options)['code']

    def test_code_format_and_hash_only_storage(self):
        created = self.store.create_invite('plus', note='friend')
        self.assertRegex(created['code'], r'^RR-PLUS-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$')
        with closing(sqlite3.connect(self.db_path)) as db:
            dump = '\n'.join(db.iterdump())
        self.assertNotIn(created['code'], dump)
        self.assertNotIn(created['code'][8:], dump)
        self.assertNotIn('code', self.store.list_invites()[0])

    def test_all_five_tiers_register_to_their_tier(self):
        expected = {'free': ('free', None), 'lite': ('lite', None), 'plus': ('plus', None), 'pro': ('free', 'pro'), 'ultra': ('ultra', None)}
        for tier, (base, timed) in expected.items():
            response = self.register(f'Tier_{tier}', self.code(tier), TestClient(self.client.app))
            self.assertEqual(response.status_code, 200, tier)
            body = response.json()
            self.assertEqual(body['tier'], tier, tier)
            self.assertEqual((body['base_tier'], body['timed_tier']), (base, timed), tier)
            self.assertEqual(body['capabilities'], membership.capabilities(tier), tier)
        pro = self.store.account(self.store.verify_account('Tier_pro', PASSWORD)['id'])
        days = (datetime.fromisoformat(pro['timed_until']) - datetime.now(timezone.utc)).total_seconds() / 86400
        self.assertAlmostEqual(days, membership.PRO_GRANT_DAYS, delta=0.01)

    def test_capabilities_are_cumulative(self):
        previous = []
        for tier in membership.TIERS:
            current = membership.capabilities(tier)
            self.assertTrue(set(previous) <= set(current), tier)
            previous = current
        self.assertEqual(membership.capabilities('ultra'), [entry['id'] for entry in membership.CAPABILITIES])
        self.assertEqual(membership.capabilities('free'), ['logging', 'cycle_views', 'plan_io', 'basic_stats', 'share_card'])

    def test_register_without_code_is_rejected(self):
        self.assertEqual(self.client.post('/api/register', json={'username': 'NoCode', 'password': PASSWORD}).status_code, 422)
        self.assertEqual(self.register('NoCode', '').status_code, 422)
        self.assertIsNone(self.store.account_by_username('NoCode'))

    def test_bad_codes_share_one_message(self):
        used = self.code('lite')
        self.assertEqual(self.register('First', used, TestClient(self.client.app)).status_code, 200)
        revoked = self.store.create_invite('lite')
        self.assertTrue(self.store.revoke_invite(revoked['id']))
        expired = self.code('lite', expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat())
        messages = set()
        for code in ('RR-LITE-AAAA-BBBB', used, revoked['code'], expired):
            response = self.register('Second', code)
            self.assertEqual(response.status_code, 422, code)
            messages.add(response.json()['error'])
        self.assertEqual(messages, {InviteError().args[0]})
        self.assertIsNone(self.store.account_by_username('Second'))

    def test_code_reuse_honours_max_uses(self):
        code = self.code('plus', max_uses=2)
        self.assertEqual(self.register('UserOne', f'  {code.lower()} ', TestClient(self.client.app)).status_code, 200, 'codes are trimmed and case-insensitive')
        self.assertEqual(self.register('UserTwo', code, TestClient(self.client.app)).status_code, 200)
        self.assertEqual(self.register('UserThree', code).status_code, 422)
        self.assertEqual(self.store.list_invites()[0]['uses'], 2)

    def test_taken_username_does_not_consume_code(self):
        code = self.code('plus')
        self.assertEqual(self.register('astra', code).status_code, 409)
        self.assertEqual(self.store.list_invites()[0]['uses'], 0)

    def test_revoked_code_cannot_redeem(self):
        self.register('Holder', self.code('free'))
        revoked = self.store.create_invite('plus')
        self.store.revoke_invite(revoked['id'])
        self.assertFalse(self.store.revoke_invite(revoked['id']), 'revoking twice reports nothing changed')
        response = self.client.post('/api/membership/redeem', json={'code': revoked['code']})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get('/api/session').json()['tier'], 'free')

    def test_redeem_upgrades_and_lower_code_is_not_consumed(self):
        self.register('Climber', self.code('free'))
        self.assertEqual(self.client.post('/api/membership/redeem', json={'code': self.code('lite')}).json()['tier'], 'lite')
        upgraded = self.client.post('/api/membership/redeem', json={'code': self.code('plus')}).json()
        self.assertEqual((upgraded['changed'], upgraded['tier'], upgraded['base_tier']), (True, 'plus', 'plus'))
        lower = self.store.create_invite('lite')
        response = self.client.post('/api/membership/redeem', json={'code': lower['code']})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['changed'])
        self.assertIn('already', response.json()['message'])
        self.assertEqual(next(row for row in self.store.list_invites() if row['id'] == lower['id'])['uses'], 0)
        self.assertEqual(self.client.get('/api/session').json()['tier'], 'plus')

    def test_pro_extends_from_current_expiry_and_expiry_drops_tier(self):
        self.register('Monthly', self.code('plus'))
        first = self.client.post('/api/membership/redeem', json={'code': self.code('pro')}).json()
        second = self.client.post('/api/membership/redeem', json={'code': self.code('pro', grant_days=10)}).json()
        self.assertEqual(second['tier'], 'pro')
        gap = datetime.fromisoformat(second['timed_until']) - datetime.fromisoformat(first['timed_until'])
        self.assertEqual(gap, timedelta(days=10))
        account_id = self.store.verify_account('Monthly', PASSWORD)['id']
        with self.store.connect() as db:
            db.execute('UPDATE accounts SET timed_until=? WHERE id=?', ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), account_id))
        session = self.client.get('/api/session').json()
        self.assertEqual((session['tier'], session['base_tier']), ('plus', 'plus'), 'expired Pro falls back to the permanent tier')
        renewed = self.client.post('/api/membership/redeem', json={'code': self.code('pro', grant_days=5)}).json()
        days = (datetime.fromisoformat(renewed['timed_until']) - datetime.now(timezone.utc)).total_seconds() / 86400
        self.assertAlmostEqual(days, 5, delta=0.01, msg='a lapsed Pro restarts from now, not from the old expiry')

    def test_ultra_owner_does_not_consume_pro(self):
        self.client.post('/api/login', json={'username': 'Astra', 'password': GATE['RR_ACCESS_PASSWORD']})
        self.assertEqual(self.client.get('/api/session').json()['tier'], 'ultra')
        response = self.client.post('/api/membership/redeem', json={'code': self.code('pro')}).json()
        self.assertFalse(response['changed'])
        self.assertEqual(self.store.list_invites()[0]['uses'], 0)

    def test_expired_code_with_offset_is_compared_in_utc(self):
        future = self.code('lite', expires_at='2999-01-01T08:00:00+08:00')
        self.assertTrue(self.store.list_invites()[0]['expires_at'].endswith('+00:00'))
        self.assertEqual(self.register('Later', future).status_code, 200)

    def test_five_device_limit_evicts_oldest(self):
        self.register('Devices', self.code('free'), TestClient(self.client.app))
        clients = []
        for index in range(6):
            client = TestClient(self.client.app)
            self.assertEqual(client.post('/api/login', json={'username': 'Devices', 'password': PASSWORD},
                                         headers={'User-Agent': f'device-{index}'}).status_code, 200)
            clients.append(client)
        account_id = self.store.verify_account('Devices', PASSWORD)['id']
        sessions = self.store.sessions(account_id)
        self.assertEqual(len(sessions), membership.DEVICE_LIMIT)
        self.assertEqual([row['user_agent'] for row in sessions], [f'device-{index}' for index in range(1, 6)])
        self.assertEqual(clients[0].get('/api/plan').status_code, 401, 'the oldest device is signed out')
        self.assertEqual(clients[5].get('/api/plan').status_code, 200)
        listed = clients[5].get('/api/membership/sessions').json()
        self.assertEqual((listed['limit'], len(listed['sessions'])), (5, 5))
        self.assertEqual(clients[5].delete(f"/api/membership/sessions/{listed['sessions'][0]['id']}").status_code, 200)
        self.assertEqual(clients[1].get('/api/plan').status_code, 401, 'a device signed out from another device is locked')
        self.assertEqual(clients[5].delete(f"/api/membership/sessions/{listed['sessions'][0]['id']}").status_code, 404)

    def test_logout_deletes_server_session(self):
        self.register('Leaver', self.code('free'))
        token = self.client.cookies.get('rr_session')
        self.client.post('/api/logout')
        stale = TestClient(self.client.app)
        stale.cookies.set('rr_session', token)
        self.assertEqual(stale.get('/api/plan').status_code, 401, 'a copied cookie is dead after logout')

    def test_owner_password_change_ends_owner_sessions(self):
        self.client.post('/api/login', json={'username': 'Astra', 'password': GATE['RR_ACCESS_PASSWORD']})
        token = self.client.cookies.get('rr_session')
        self.client.__exit__(None, None, None)
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': 'rotated-secret-2026'}):
            with TestClient(create_app(db_path=self.db_path)) as restarted:
                restarted.cookies.set('rr_session', token)
                self.assertEqual(restarted.get('/api/plan').status_code, 401)
                self.assertEqual(restarted.post('/api/login', json={'username': 'Astra', 'password': 'rotated-secret-2026'}).status_code, 200)
                self.assertEqual(restarted.post('/api/login', json={'username': 'Astra', 'password': GATE['RR_ACCESS_PASSWORD']}).status_code, 401)
        self.client.__enter__()

    def test_session_expires_after_thirty_days(self):
        self.register('Stale', self.code('free'))
        with self.store.connect() as db:
            db.execute('UPDATE sessions SET created_at=?', ((datetime.now(timezone.utc) - timedelta(days=30, seconds=1)).isoformat(),))
        self.assertEqual(self.client.get('/api/plan').status_code, 401)
        self.assertEqual(self.store.sessions(self.store.verify_account('Stale', PASSWORD)['id']), [])

    def test_anonymous_session_shape_is_unchanged(self):
        self.assertEqual(TestClient(self.client.app).get('/api/session').json(), {'authenticated': False, 'username': None, 'gate': True})

    def test_redeem_requires_sign_in(self):
        self.assertEqual(TestClient(self.client.app).post('/api/membership/redeem', json={'code': self.code('plus')}).status_code, 401)


class MembershipMigrationTests(unittest.TestCase):
    def test_existing_accounts_migrate_to_free_with_snapshot_and_owner_ultra(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / 'old.sqlite3'
            with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': '', 'RR_ACCESS_USERNAME': ''}):
                with TestClient(create_app(db_path=db_path)):
                    pass
            with closing(sqlite3.connect(db_path)) as db, db:
                db.execute('DROP TABLE sessions')
                db.execute('DROP TABLE invite_redemptions')
                db.execute('DROP TABLE invites')
                db.execute('ALTER TABLE accounts DROP COLUMN timed_until')
                db.execute('ALTER TABLE accounts DROP COLUMN timed_tier')
                db.execute('ALTER TABLE accounts DROP COLUMN base_tier')
                for name in ('Astra', 'Friend'):
                    db.execute("INSERT INTO accounts(username, username_lower, password_hash, salt, created_at) VALUES(?,?,?,?,?)",
                               (name, name.lower(), 'x', '00', '2026-11-01T00:00:00+00:00'))
            before = {path.name for path in (Path(folder) / 'backups').glob('*.sqlite3')}
            with patch.dict(os.environ, GATE):
                with TestClient(create_app(db_path=db_path)) as client:
                    store = client.app.state.store
                    after = {path.name for path in (Path(folder) / 'backups').glob('*.sqlite3')}
                    self.assertTrue(after - before, 'migration takes a snapshot first')
                    self.assertEqual(store.account(store.owner_id('Astra'))['base_tier'], 'ultra')
                    friend = store.account_by_username('Friend')
                    self.assertIsNotNone(friend)
                    with store.connect() as db:
                        self.assertEqual(db.execute("SELECT base_tier FROM accounts WHERE username='Friend'").fetchone()[0], 'free')
                    self.assertEqual(client.post('/api/login', json={'username': 'Astra', 'password': GATE['RR_ACCESS_PASSWORD']}).status_code, 200)


class InviteToolTests(unittest.TestCase):
    def test_create_list_revoke(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / 'tool.sqlite3'
            with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': ''}):
                with TestClient(create_app(db_path=db_path)):
                    pass
            run = lambda *args: subprocess.run([sys.executable, '-m', 'server.tools.invite', '--db', str(db_path), *args],
                                               cwd=ROOT, capture_output=True, text=True)
            created = run('create', '--tier', 'pro', '--days', '14', '--note', 'trial')
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertIn('"grant_days": 14', created.stdout)
            self.assertRegex(created.stdout, r'RR-PRO-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}')
            listed = run('list')
            self.assertIn('"tier": "pro"', listed.stdout)
            self.assertNotIn('RR-PRO-', listed.stdout)
            self.assertEqual(run('revoke', '1').returncode, 0)
            self.assertEqual(run('revoke', '1').returncode, 1)
            self.assertNotEqual(run('create', '--tier', 'lite', '--expires', '2026-12-31T00:00:00').returncode, 0)


if __name__ == '__main__':
    unittest.main()
