"""Public landing, account auth and allowed-host contracts.

The release page and SPA shell are public; only journal API data is gated.
Accounts authenticate by cookie session (login/register) or Basic auth.
Usernames are case-insensitive; passwords are case-sensitive.
"""

import base64
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.main import create_app


def basic(user, pwd):
    return {'Authorization': 'Basic ' + base64.b64encode(f'{user}:{pwd}'.encode()).decode()}


class AccessGateTests(unittest.TestCase):
    def test_gate_off_without_password(self):
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': '', 'RR_ACCESS_USERNAME': ''}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    self.assertEqual(client.get('/api/health').status_code, 200)
                    self.assertEqual(client.get('/').status_code, 200)
                    self.assertEqual(client.get('/api/plan').status_code, 200)
                    session = client.get('/api/session').json()
                    self.assertTrue(session['authenticated'])
                    self.assertFalse(session['gate'])

    def test_public_shell_and_health_but_gated_data(self):
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra'}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    for path in ('/', '/welcome', '/login', '/register', '/today', '/api/health'):
                        self.assertEqual(client.get(path).status_code, 200, path)
                    for path in ('/', '/welcome', '/login', '/register', '/today'):
                        shell = client.get(path)
                        self.assertEqual(shell.headers['cache-control'], 'no-store', path)
                        self.assertNotIn('www-authenticate', shell.headers, path)
                    session = client.get('/api/session').json()
                    self.assertFalse(session['authenticated'])
                    self.assertTrue(session['gate'])
                    blocked = client.get('/api/plan')
                    self.assertEqual(blocked.status_code, 401)
                    self.assertEqual(blocked.headers['www-authenticate'], 'Basic realm="Roast Raw"')
                    self.assertEqual(client.get('/api/cycle').status_code, 401)

    def test_basic_auth_username_case_insensitive(self):
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra'}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    for user in ('Astra', 'astra', 'ASTRA', 'aStRa'):
                        ok = client.get('/api/plan', headers=basic(user, 'gate-secret-917'))
                        self.assertEqual(ok.status_code, 200, user)
                    self.assertEqual(client.get('/api/plan', headers=basic('wrong', 'gate-secret-917')).status_code, 401)
                    self.assertEqual(client.get('/api/plan', headers=basic('Astra', 'wrong')).status_code, 401)
                    self.assertEqual(client.get('/api/plan', headers=basic('Astra', 'GATE-SECRET-917')).status_code, 401)
                    self.assertEqual(client.get('/api/plan', headers={'Authorization': 'Basic garbage!!'}).status_code, 401)

    def test_owner_seeded_from_env(self):
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra'}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    ok = client.post('/api/login', json={'username': 'astra', 'password': 'gate-secret-917'})
                    self.assertEqual(ok.status_code, 200)
                    self.assertEqual(ok.json()['username'], 'Astra')
                    self.assertIn('rr_session', ok.cookies)

    def test_register_login_logout_cookie_flow(self):
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra'}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    self.assertEqual(client.get('/api/plan').status_code, 401)
                    reg = client.post('/api/register', json={'username': 'Lifter_2', 'password': 'barbell-2018'})
                    self.assertEqual(reg.status_code, 200)
                    self.assertEqual(reg.json()['username'], 'Lifter_2')
                    self.assertTrue(client.get('/api/session').json()['authenticated'])
                    self.assertEqual(client.get('/api/plan').status_code, 200)
                    out = client.post('/api/logout')
                    self.assertEqual(out.status_code, 200)
                    self.assertFalse(client.get('/api/session').json()['authenticated'])
                    self.assertEqual(client.get('/api/plan').status_code, 401)
                    ok = client.post('/api/login', json={'username': 'lifter_2', 'password': 'barbell-2018'})
                    self.assertEqual(ok.status_code, 200)
                    self.assertEqual(client.get('/api/plan').status_code, 200)
                    self.assertEqual(client.post('/api/login', json={'username': 'Lifter_2', 'password': 'nope'}).status_code, 401)

    def test_register_validation_and_conflict(self):
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra'}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    self.assertEqual(client.post('/api/register', json={'username': 'Astra', 'password': 'another-2018'}).status_code, 409)
                    self.assertEqual(client.post('/api/register', json={'username': 'astra', 'password': 'another-2018'}).status_code, 409)
                    self.assertEqual(client.post('/api/register', json={'username': '1bad', 'password': 'barbell-2018'}).status_code, 422)
                    self.assertEqual(client.post('/api/register', json={'username': 'ok', 'password': 'short'}).status_code, 422)
                    self.assertEqual(client.post('/api/register', json={'username': 'ok', 'password': 'barbell-2018', 'extra': 1}).status_code, 422)
                    self.assertEqual(client.post('/api/login', json={'username': '', 'password': 'x'}).status_code, 422)

    def test_session_survives_restart(self):
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': 'gate-secret-917', 'RR_ACCESS_USERNAME': 'Astra'}):
            with tempfile.TemporaryDirectory() as folder:
                db = Path(folder) / 'g.sqlite3'
                with TestClient(create_app(db_path=db)) as client:
                    client.post('/api/login', json={'username': 'Astra', 'password': 'gate-secret-917'})
                    token = client.cookies.get('rr_session')
                with TestClient(create_app(db_path=db)) as restarted:
                    restarted.cookies.set('rr_session', token)
                    self.assertTrue(restarted.get('/api/session').json()['authenticated'])
                    self.assertEqual(restarted.get('/api/plan').status_code, 200)

    def test_allowed_hosts_env(self):
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': '', 'RR_ALLOWED_HOSTS': '82.157.146.30, preview.example'}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    self.assertEqual(client.get('/api/health', headers={'Host': '82.157.146.30'}).status_code, 200)
                    self.assertEqual(client.get('/api/health', headers={'Host': 'preview.example'}).status_code, 200)
                    self.assertEqual(client.get('/api/health', headers={'Host': 'evil.example'}).status_code, 400)


if __name__ == '__main__':
    unittest.main()