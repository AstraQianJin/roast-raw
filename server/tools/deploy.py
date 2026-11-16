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
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

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


def write_env(password, deepseek_key, username=''):
    lines = [
        f'RR_ACCESS_PASSWORD={password}',
        f'RR_ALLOWED_HOSTS={PUBLIC_HOST}',
        'RR_DB_PATH=/opt/roast-raw/data/roastraw.sqlite3',
        'TZ=Asia/Shanghai',
    ]
    if username:
        lines.append(f'RR_ACCESS_USERNAME={username}')
    if deepseek_key:
        lines.append(f'DEEPSEEK_API_KEY={deepseek_key}')
    content = '\n'.join(lines) + '\n'
    run(['ssh', '-o', 'BatchMode=yes', REMOTE_HOST,
         'sudo tee /etc/roast-raw.env >/dev/null && sudo chmod 600 /etc/roast-raw.env'],
        input=content.encode('utf-8'), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


ACCESS_CHECK = r'''
import json, os, re, sys, urllib.error, urllib.request

base, expected = sys.argv[1], sys.argv[2]
if "--from-env-file" in sys.argv[3:]:
    for line in open("/etc/roast-raw.env", encoding="utf-8"):
        key, _, value = line.rstrip("\n").partition("=")
        if key in ("RR_ACCESS_USERNAME", "RR_ACCESS_PASSWORD"):
            os.environ[key] = value
username = os.environ.get("RR_ACCESS_USERNAME") or "Astra"
password = os.environ.get("RR_ACCESS_PASSWORD", "")
if not password:
    print("FAIL checker has no owner password"); sys.exit(1)

# http.cookiejar drops host-only cookies for IP literals, and both the fixture and
# the deployed host are IPs, so the session cookie is carried explicitly.
def fetch(path, payload=None, cookie=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    request = urllib.request.Request(base + path, data=data, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=15)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {k.lower(): v for k, v in exc.headers.items()}
    except (urllib.error.URLError, OSError) as exc:
        print("UNREACHABLE " + base + path + ": " + str(exc)); sys.exit(2)
    with response:
        return response.status, response.read(), {k.lower(): v for k, v in response.headers.items()}

def check(label, ok, detail=""):
    if not ok:
        print(("FAIL " + label + " " + str(detail)).rstrip()); sys.exit(1)
    print("PASS " + label)

code, body, headers = fetch("/")
check("landing / is public 200", code == 200, code)
check("landing / serves the SPA shell", b"id=\"app\"" in body)
check("landing / sends no Basic challenge", "www-authenticate" not in headers, headers.get("www-authenticate"))
check("landing shell is not cached", "no-store" in headers.get("cache-control", ""), headers.get("cache-control"))
assets = re.findall(rb'(?:src|href)="(/assets/[^"]+)"', body)
check("landing references built assets", len(assets) >= 2, assets)
for asset in assets:
    code, _, _ = fetch(asset.decode())
    check("asset is public " + asset.decode(), code == 200, code)
for path in ("/welcome", "/login", "/register"):
    code, _, headers = fetch(path)
    check(path + " is public 200", code == 200 and "www-authenticate" not in headers, code)

code, body, _ = fetch("/api/health")
health = json.loads(body) if code == 200 else {}
check("health is public and ok", code == 200 and health.get("status") == "ok", code)
check("health reports version " + expected, health.get("version") == expected, health.get("version"))

code, body, _ = fetch("/api/session")
session = json.loads(body) if code == 200 else {}
check("anonymous session reports gate on", code == 200 and session == {"authenticated": False, "username": None, "gate": True}, session)
for path in ("/api/cycle", "/api/plan", "/api/analysis?mode=plan"):
    code, _, _ = fetch(path)
    check("anonymous " + path + " is 401", code == 401, code)

code, _, _ = fetch("/api/login", {"username": username, "password": password + "-wrong"})
check("wrong password is 401", code == 401, code)
code, body, headers = fetch("/api/login", {"username": username.swapcase(), "password": password})
check("owner signs in with any username casing", code == 200 and json.loads(body).get("ok") is True, code)
issued = headers.get("set-cookie", "")
token = re.search(r"rr_session=([^;]+)", issued)
check("sign-in issues rr_session cookie", bool(token), issued[:40])
check("cookie is HttpOnly and SameSite=Lax", "httponly" in issued.lower() and "samesite=lax" in issued.lower(), issued[:80])
cookie = "rr_session=" + token.group(1)
for path in ("/api/cycle", "/api/plan"):
    code, _, _ = fetch(path, cookie=cookie)
    check("signed-in " + path + " is 200", code == 200, code)
code, body, _ = fetch("/api/session", cookie=cookie)
check("signed-in session reports the owner", code == 200 and json.loads(body).get("authenticated") is True, body[:120])
code, _, headers = fetch("/api/logout", {}, cookie=cookie)
cleared = headers.get("set-cookie", "")
check("logout is 200", code == 200, code)
check("logout tells the browser to drop the cookie",
      "rr_session=" in cleared and ("max-age=0" in cleared.lower() or "expires=" in cleared.lower()), cleared[:80])
code, _, _ = fetch("/api/cycle")
check("journal is locked again without the cookie", code == 401, code)
print("ACCESS-CONTRACT-OK")
'''


def health_check(password, expected_version, username=''):
    """Prove the public-landing / account-gate contract, not just that health answers."""
    base = f'http://{PUBLIC_HOST}'
    environment = {**os.environ, 'RR_ACCESS_USERNAME': username or 'Astra', 'RR_ACCESS_PASSWORD': password}
    deadline = time.time() + 90
    last = ''
    while time.time() < deadline:
        result = subprocess.run([sys.executable, '-c', ACCESS_CHECK, base, expected_version],
                                cwd=ROOT, env=environment, capture_output=True, text=True, errors='replace')
        if result.returncode == 0:
            print(result.stdout.strip())
            print(f'PASS deploy: public landing + account gate verified from {base}, version {expected_version}')
            print(f'Preview: {base}/ (public landing; sign in for the journal)')
            return
        # A restart in flight answers 502/503/504 through Caddy for a few seconds; that is
        # a transient, not a contract violation. Only a real mismatch fails immediately.
        transient = any(code in result.stdout for code in (' 502', ' 503', ' 504'))
        if result.returncode != 2 and not transient:
            print(result.stdout.strip())
            fail(f'access contract violated: {result.stderr.strip()[-400:]}')
        last = result.stdout.strip()[-200:]
        time.sleep(3)
    print(f'Public {base}/ unreachable from here ({last}); verifying on the server itself.')
    # The remote checker reads the root-owned env file, so the secret never travels in argv.
    output = remote('set -euo pipefail\nsudo python3 -c ' + shlex.quote(ACCESS_CHECK)
                    + f' http://127.0.0.1 {expected_version} --from-env-file\n')
    print(output.strip())
    print(f'PASS deploy (on-server): public landing + account gate verified, version {expected_version}')
    print(f'BLOCKED public access: open TCP 80 for 0.0.0.0/0 in the Tencent Lighthouse console firewall, then {base}/ works.')


def main():
    password = os.environ.get('RR_ACCESS_PASSWORD', '')
    if not password:
        fail('RR_ACCESS_PASSWORD is not set in the process environment')
    username = os.environ.get('RR_ACCESS_USERNAME', '')
    deepseek_key = os.environ.get('DEEPSEEK_API_KEY', '')
    with tempfile.TemporaryDirectory() as folder:
        payload = build_payload(folder)
        print(f'Payload built: {payload.stat().st_size} bytes')
        # scp is refused by this host's sshd (sftp subsystem), so stream the bytes over
        # the same ssh channel the rest of the deployment already uses.
        run(['ssh', '-o', 'BatchMode=yes', REMOTE_HOST, 'cat > /tmp/rr-payload.tar.gz'],
            input=payload.read_bytes(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        write_env(password, deepseek_key, username)
        output = remote(REMOTE_SETUP)
        tail = '\n'.join(output.splitlines()[-5:])
        print(f'Remote setup done. Tail:\n{tail}')
        version = json.loads((ROOT / 'web' / 'package.json').read_text(encoding='utf-8'))['version']
        parts = version.split('.')
        health_check(password, f'{parts[0]}.{int(parts[2]):02d}', username)


if __name__ == '__main__':
    main()