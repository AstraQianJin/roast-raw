"""Deployment access gate and allowed-host contracts."""

import base64
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.main import create_app


class AccessGateTests(unittest.TestCase):
    def test_gate_off_without_password(self):
        import os
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': ''}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    self.assertEqual(client.get('/api/health').status_code, 200)
                    self.assertEqual(client.get('/').status_code, 200)

    def test_gate_blocks_and_admits(self):
        import os
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': 'gate-secret-917'}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    for path in ('/api/health', '/', '/api/plan'):
                        blocked = client.get(path)
                        self.assertEqual(blocked.status_code, 401, path)
                        self.assertEqual(blocked.headers['www-authenticate'], 'Basic realm="Roast Raw"')
                    wrong = base64.b64encode(b'user:incorrect').decode()
                    self.assertEqual(client.get('/api/health', headers={'Authorization': 'Basic ' + wrong}).status_code, 401)
                    self.assertEqual(client.get('/api/health', headers={'Authorization': 'Basic garbage!!'}).status_code, 401)
                    good = base64.b64encode(b'user:gate-secret-917').decode()
                    ok = client.get('/api/health', headers={'Authorization': 'Basic ' + good})
                    self.assertEqual(ok.status_code, 200)
                    self.assertEqual(ok.json()['status'], 'ok')
                    self.assertEqual(client.get('/', headers={'Authorization': 'Basic ' + good}).status_code, 200)

    def test_allowed_hosts_env(self):
        import os
        with patch.dict(os.environ, {'RR_ACCESS_PASSWORD': '', 'RR_ALLOWED_HOSTS': '82.157.146.30, preview.example'}):
            with tempfile.TemporaryDirectory() as folder:
                with TestClient(create_app(db_path=Path(folder) / 'g.sqlite3')) as client:
                    ok = client.get('/api/health', headers={'Host': '82.157.146.30'})
                    self.assertEqual(ok.status_code, 200)
                    self.assertEqual(client.get('/api/health', headers={'Host': 'preview.example'}).status_code, 200)
                    self.assertEqual(client.get('/api/health', headers={'Host': 'evil.example'}).status_code, 400)


if __name__ == '__main__':
    unittest.main()