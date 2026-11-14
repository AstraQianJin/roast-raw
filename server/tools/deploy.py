"""Deploy Roast Raw to the new server as an HTML preview or formal service.

Secrets come only from the local process environment (RR_ACCESS_PASSWORD,
optionally DEEPSEEK_API_KEY); they are piped over ssh stdin into a root-owned
env file and never printed, committed or bundled. Run from the project root:

    server/.venv/Scripts/python.exe server/tools/deploy.py

Requires: node/npm on PATH, ssh alias `roast-raw` (key-based), sudo on remote.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
REMOTE_HOST = 'roast-raw'
PUBLIC_HOST = '82.157.146.30'


def fail(message):
    print(f'FAIL deploy: {message}')
    sys.exit(1)


def run(args, **kwargs):
    executable = shutil.which(args[0])
    if executable is None:
        fail(f'command not found on PATH: {args[0]}')
    if not isinstance(kwargs.get('input'), bytes):
        kwargs.update(encoding='utf-8', errors='replace')
    result = subprocess.run([executable, *args[1:]], cwd=ROOT, **kwargs)
    if result.returncode != 0:
        output = result.stdout
        if isinstance(output, bytes):
            output = output.decode('utf-8', 'replace')
        if output:
            print(output[-3000:])
        fail(f'command exited {result.returncode}: {args[0]} ...')
    return result


def remote(script, input_text=None):
    # Bytes input: Windows text mode would rewrite \n to \r\n and break the remote shell.
    return run(['ssh', '-o', 'BatchMode=yes', REMOTE_HOST, 'bash -s'],
               input=script.encode('utf-8'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode('utf-8', 'replace')


def build_payload(folder):
    run(['npm', '--prefix', 'web', 'run', 'build'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    dist = ROOT / 'web' / 'dist'
    if not (dist / 'index.html').exists():
        fail('web/dist/index.html missing after build')
    payload = Path(folder) / 'payload.tar.gz'
    with tarfile.open(payload, 'w:gz') as tar:
        tar.add(ROOT / 'server' / 'app', arcname='server/app',
                filter=lambda info: None if '__pycache__' in info.name else info)
        tar.add(ROOT / 'server' / 'requirements.txt', arcname='server/requirements.txt')
        tar.add(dist, arcname='web/dist')
        tar.add(ROOT / 'web' / 'package.json', arcname='web/package.json')
        for path in sorted((ROOT / 'data').glob('*.json')):
            tar.add(path, arcname=f'data/{path.name}')
        tar.add(ROOT / 'data' / 'schema', arcname='data/schema')
    return payload


REMOTE_SETUP = r'''
set -euo pipefail
sudo mkdir -p /opt/roast-raw
sudo chown ubuntu:ubuntu /opt/roast-raw
if [ -d /opt/roast-raw/server ]; then
  sudo systemctl stop roast-raw 2>/dev/null || true
  if [ -f /opt/roast-raw/data/roastraw.sqlite3 ]; then
    python3 -c "import sqlite3; c=sqlite3.connect('/opt/roast-raw/data/roastraw.sqlite3'); c.execute('PRAGMA wal_checkpoint(TRUNCATE)'); c.close()"
  fi
  stamp=$(date +%Y%m%d-%H%M%S)
  sudo mkdir -p /opt/roast-raw-backups
  sudo tar -czf /opt/roast-raw-backups/roast-raw-$stamp.tar.gz -C /opt/roast-raw server web data
fi
rm -rf /opt/roast-raw/web/dist
tar -xzf /tmp/rr-payload.tar.gz -C /opt/roast-raw
rm /tmp/rr-payload.tar.gz
cd /opt/roast-raw
python3 -m venv server/.venv 2>/dev/null || sudo apt-get install -y python3-venv >/dev/null
server/.venv/bin/pip install -q -r server/requirements.txt
sudo tee /etc/systemd/system/roast-raw.service >/dev/null <<'UNIT'
[Unit]
Description=Roast Raw single-user training journal
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/roast-raw
EnvironmentFile=/etc/roast-raw.env
ExecStart=/opt/roast-raw/server/.venv/bin/uvicorn server.app.main:create_app --factory --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable roast-raw >/dev/null 2>&1
sudo systemctl restart roast-raw
if command -v caddy >/dev/null; then
  stamp=$(date +%Y%m%d-%H%M%S)
  sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-$stamp
  sudo tee /etc/caddy/Caddyfile >/dev/null <<'CADDY'
:80 {
	encode zstd gzip
	@assets path /assets/*
	header @assets Cache-Control "public, max-age=31536000, immutable"
	reverse_proxy 127.0.0.1:8000
}
CADDY
  sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
  sudo systemctl reload caddy
fi
'''


def write_env(password, deepseek_key):
    lines = [
        f'RR_ACCESS_PASSWORD={password}',
        f'RR_ALLOWED_HOSTS={PUBLIC_HOST}',
        'RR_DB_PATH=/opt/roast-raw/data/roastraw.sqlite3',
        'TZ=Asia/Shanghai',
    ]
    if deepseek_key:
        lines.append(f'DEEPSEEK_API_KEY={deepseek_key}')
    content = '\n'.join(lines) + '\n'
    run(['ssh', '-o', 'BatchMode=yes', REMOTE_HOST,
         'sudo tee /etc/roast-raw.env >/dev/null && sudo chmod 600 /etc/roast-raw.env'],
        input=content.encode('utf-8'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def health_check(password, expected_version):
    import base64
    auth = base64.b64encode(f'user:{password}'.encode()).decode()
    deadline = time.time() + 60
    last = ''
    while time.time() < deadline:
        try:
            request = urllib.request.Request(f'http://{PUBLIC_HOST}/api/health',
                                             headers={'Authorization': 'Basic ' + auth})
            with urllib.request.urlopen(request, timeout=10) as response:
                body = json.loads(response.read())
            if body.get('status') == 'ok':
                if body.get('version') != expected_version:
                    fail(f'deployed version {body.get("version")} != expected {expected_version}')
                unauth = urllib.request.Request(f'http://{PUBLIC_HOST}/api/health')
                try:
                    urllib.request.urlopen(unauth, timeout=10)
                    fail('gate not active: unauthenticated health check succeeded')
                except urllib.error.HTTPError as exc:
                    if exc.code != 401:
                        fail(f'unauthenticated health returned {exc.code}, expected 401')
                print(f'PASS deploy: health ok, version {body.get("version")}, gate 401 without password')
                print(f'Preview: http://{PUBLIC_HOST}/ (password prompt in browser)')
                return
        except Exception as exc:
            last = str(exc)
        time.sleep(3)
    print(f'Public http://{PUBLIC_HOST}/ unreachable from here ({last}); verifying on the server itself.')
    check = remote(
        'set -euo pipefail\n'
        f'code=$(curl -s -m 10 -o /tmp/rr-health.json -w "%{{http_code}}" -u "user:{password}" http://127.0.0.1/api/health)\n'
        '[ "$code" = 200 ] || { echo "authenticated health returned $code"; exit 1; }\n'
        'cat /tmp/rr-health.json; rm /tmp/rr-health.json\n'
        'unauth=$(curl -s -m 10 -o /dev/null -w "%{http_code}" http://127.0.0.1/api/health)\n'
        '[ "$unauth" = 401 ] || { echo "gate not active: unauthenticated returned $unauth"; exit 1; }\n'
        'echo GATE-401-OK\n')
    if f'"version": "{expected_version}"' not in check and f'"version":"{expected_version}"' not in check:
        fail(f'on-server health check missing expected version {expected_version}: {check[-400:]}')
    if 'GATE-401-OK' not in check:
        fail(f'on-server health check failed: {check[-400:]}')
    print(f'PASS deploy (on-server): health ok, version {expected_version}, gate 401 without password')
    print(f'BLOCKED public access: open TCP 80 for 0.0.0.0/0 in the Tencent Lighthouse console firewall, then http://{PUBLIC_HOST}/ works.')


def main():
    password = os.environ.get('RR_ACCESS_PASSWORD', '')
    if not password:
        fail('RR_ACCESS_PASSWORD is not set in the process environment')
    deepseek_key = os.environ.get('DEEPSEEK_API_KEY', '')
    with tempfile.TemporaryDirectory() as folder:
        payload = build_payload(folder)
        print(f'Payload built: {payload.stat().st_size} bytes')
        run(['scp', '-o', 'BatchMode=yes', str(payload), f'{REMOTE_HOST}:/tmp/rr-payload.tar.gz'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        write_env(password, deepseek_key)
        output = remote(REMOTE_SETUP)
        tail = '\n'.join(output.splitlines()[-5:])
        print(f'Remote setup done. Tail:\n{tail}')
        version = json.loads((ROOT / 'web' / 'package.json').read_text(encoding='utf-8'))['version']
        parts = version.split('.')
        health_check(password, f'{parts[0]}.{int(parts[2]):02d}')


if __name__ == '__main__':
    main()