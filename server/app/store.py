import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import membership


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class ReadOnlyError(ValueError):
    pass


class InviteError(ValueError):
    def __init__(self):
        super().__init__('That invite code cannot be used. Check the code or ask for a new one.')


class AiQuotaError(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self, plan):
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1, 2, 3, 4, 5):
                raise RuntimeError('Unsupported database version; no data was changed')
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS cycles (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','completed','archived')),
                    schema_version TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_cycle ON cycles(status) WHERE status='active';
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL UNIQUE REFERENCES cycles(id),
                    json TEXT NOT NULL, version TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS logs (
                    cycle_id TEXT NOT NULL REFERENCES cycles(id), key TEXT NOT NULL,
                    date TEXT NOT NULL, session_id TEXT NOT NULL, exercise_id TEXT NOT NULL,
                    load REAL, reps INTEGER NOT NULL CHECK(reps>=0), rpe REAL CHECK(rpe>=5.5 AND rpe<=10),
                    set_count INTEGER NOT NULL CHECK(set_count>=0), note TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(cycle_id,key));
                CREATE TABLE IF NOT EXISTS logs_journal (
                    id INTEGER PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES cycles(id),
                    key TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS readiness (
                    cycle_id TEXT NOT NULL REFERENCES cycles(id), date TEXT NOT NULL, session_id TEXT NOT NULL,
                    fatigue INTEGER, arousal INTEGER, nutrition INTEGER, hrv REAL,
                    sleep_score REAL, rhr REAL, session_time TEXT, rec REAL, note TEXT,
                    PRIMARY KEY(cycle_id,date,session_id));
                CREATE TABLE IF NOT EXISTS archives (
                    id TEXT PRIMARY KEY, cycle_id TEXT NOT NULL UNIQUE REFERENCES cycles(id),
                    review_json TEXT NOT NULL, exported_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS body_metrics (
                    id INTEGER PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES cycles(id),
                    date TEXT NOT NULL, bodyweight REAL, bodyfat REAL, measurements_json TEXT,
                    UNIQUE(cycle_id,date));
            ''')
            if version == 0:
                db.execute('PRAGMA user_version=1')
            if db.execute('SELECT count(*) FROM cycles').fetchone()[0] == 0:
                meta = plan['meta']
                db.execute('INSERT INTO cycles VALUES(?,?,?,?,?,?)',
                           (meta['planId'], meta['name'], meta['startDate'], meta['endDate'], 'active', plan['schemaVersion']))
                db.execute('INSERT INTO plans VALUES(?,?,?,?,?)',
                           (meta['planId'], meta['planId'], json.dumps(plan, ensure_ascii=False), plan['schemaVersion'], timestamp()))

    def snapshot(self):
        folder = self.path.parent / 'backups'
        folder.mkdir(exist_ok=True)
        target = folder / f"{self.path.stem}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.sqlite3"
        with self.connect() as source, closing(sqlite3.connect(target)) as backup:
            source.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed')
        return target

    def upgrade(self):
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
        if version in (2, 3, 4, 5):
            return
        if version != 1:
            raise RuntimeError('Unsupported database version; no data was changed')
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE readiness_v2 (
                cycle_id TEXT NOT NULL REFERENCES cycles(id), date TEXT NOT NULL,
                session_id TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY(cycle_id,date,session_id))''')
            db.execute('''CREATE TABLE records_journal (
                id INTEGER PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES cycles(id),
                kind TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)''')
            db.execute('PRAGMA user_version=2')

    def upgrade_prescriptions(self):
        from .stats.variations import digest
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
        if version in (3, 4, 5):
            return
        if version != 2:
            raise RuntimeError('Unsupported database version; no data was changed')
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE prescription_versions (
                cycle_id TEXT NOT NULL REFERENCES cycles(id), id TEXT NOT NULL,
                json TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(cycle_id,id))''')
            for row in db.execute('SELECT cycle_id,json FROM plans').fetchall():
                db.execute('INSERT INTO prescription_versions VALUES(?,?,?,?)',
                           (row['cycle_id'], digest(json.loads(row['json'])), row['json'], timestamp()))
            db.execute('PRAGMA user_version=3')

    def upgrade_questionnaire(self):
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
        if version in (4, 5):
            return
        if version != 3:
            raise RuntimeError('Unsupported database version; no data was changed')
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE questionnaires (
                cycle_id TEXT PRIMARY KEY REFERENCES cycles(id),
                payload TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('draft','complete')),
                updated_at TEXT NOT NULL)''')
            db.execute('PRAGMA user_version=4')

    def upgrade_ai(self):
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
        if version == 5:
            return
        if version != 4:
            raise RuntimeError('Unsupported database version; no data was changed')
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE ai_calls (
                id INTEGER PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES cycles(id),
                day TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('outlook','chat')),
                status TEXT NOT NULL CHECK(status IN ('reserved','ok','error')),
                prompt TEXT NOT NULL, conversation TEXT NOT NULL DEFAULT '[]',
                response TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
            db.execute('CREATE INDEX ai_calls_day ON ai_calls(day)')
            db.execute('''CREATE TABLE attempts (
                cycle_id TEXT NOT NULL REFERENCES cycles(id),
                lift TEXT NOT NULL CHECK(lift IN ('squat','bench','deadlift')),
                number INTEGER NOT NULL CHECK(number IN (1,2,3)),
                load REAL NOT NULL, result TEXT CHECK(result IN ('good','miss')),
                updated_at TEXT NOT NULL, PRIMARY KEY(cycle_id,lift,number))''')
            db.execute('''CREATE TABLE deletion_tokens (
                token TEXT PRIMARY KEY, cycle_id TEXT NOT NULL REFERENCES cycles(id),
                created_at TEXT NOT NULL)''')
            db.execute('PRAGMA user_version=5')

    def upgrade_accounts(self):
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts'").fetchone()
        if exists:
            return
        self.snapshot()
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY, username TEXT NOT NULL,
                username_lower TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, salt TEXT NOT NULL,
                created_at TEXT NOT NULL)''')

    @staticmethod
    def _hash_password(password, salt):
        return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), 200000).hex()

    def account_count(self):
        with self.connect() as db:
            return db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]

    def upgrade_membership(self):
        with self.connect() as db:
            columns = {row['name'] for row in db.execute('PRAGMA table_info(accounts)')}
            sessions = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sessions'").fetchone()
        if 'base_tier' in columns and sessions:
            return
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if 'base_tier' not in columns:
                db.execute("ALTER TABLE accounts ADD COLUMN base_tier TEXT NOT NULL DEFAULT 'free'")
                db.execute('ALTER TABLE accounts ADD COLUMN timed_tier TEXT')
                db.execute('ALTER TABLE accounts ADD COLUMN timed_until TEXT')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS invites (
                    id INTEGER PRIMARY KEY, code_hash TEXT NOT NULL UNIQUE,
                    tier TEXT NOT NULL CHECK(tier IN ('free','lite','plus','pro','ultra')),
                    max_uses INTEGER NOT NULL DEFAULT 1 CHECK(max_uses>=1), uses INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT, grant_days INTEGER, revoked_at TEXT, note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS invite_redemptions (
                    id INTEGER PRIMARY KEY, invite_id INTEGER NOT NULL REFERENCES invites(id),
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    kind TEXT NOT NULL CHECK(kind IN ('register','redeem')), created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, user_agent TEXT NOT NULL DEFAULT '');
                CREATE INDEX IF NOT EXISTS sessions_account ON sessions(account_id);
            ''')

    def seed_owner(self, username, password):
        if not password:
            return
        username = (username or 'Astra').strip()
        if not self.account_by_username(username):
            self.create_account(username, password)
        salt = secrets.token_hex(16)
        with self.connect() as db:
            row = db.execute('SELECT id, password_hash, salt FROM accounts WHERE username_lower=?', (username.lower(),)).fetchone()
            db.execute("UPDATE accounts SET base_tier='ultra' WHERE id=?", (row['id'],))
            if not hmac.compare_digest(self._hash_password(password, row['salt']), row['password_hash']):
                db.execute('UPDATE accounts SET password_hash=?, salt=? WHERE id=?',
                           (self._hash_password(password, salt), salt, row['id']))
                db.execute('DELETE FROM sessions WHERE account_id=?', (row['id'],))

    def owner_id(self, username):
        with self.connect() as db:
            row = db.execute('SELECT id FROM accounts WHERE username_lower=?', ((username or 'Astra').strip().lower(),)).fetchone() \
                or db.execute('SELECT id FROM accounts ORDER BY id LIMIT 1').fetchone()
        return row['id'] if row else None

    @staticmethod
    def _insert_account(db, username, password, base_tier='free', timed_tier=None, timed_until=None):
        if db.execute('SELECT 1 FROM accounts WHERE username_lower=?', (username.lower(),)).fetchone():
            raise ValueError('That username is already taken.')
        salt = secrets.token_hex(16)
        try:
            cursor = db.execute('''INSERT INTO accounts(username, username_lower, password_hash, salt, created_at,
                                   base_tier, timed_tier, timed_until) VALUES(?,?,?,?,?,?,?,?)''',
                                (username, username.lower(), Store._hash_password(password, salt), salt, timestamp(),
                                 base_tier, timed_tier, timed_until))
        except sqlite3.IntegrityError:
            raise ValueError('That username is already taken.')
        return cursor.lastrowid

    def create_account(self, username, password):
        username = username.strip()
        with self.connect() as db:
            self._insert_account(db, username, password)
        return self.account_by_username(username)

    def account_by_username(self, username):
        with self.connect() as db:
            row = db.execute('SELECT username, created_at FROM accounts WHERE username_lower=?', (username.strip().lower(),)).fetchone()
        return dict(row) if row else None

    def verify_account(self, username, password):
        with self.connect() as db:
            row = db.execute('SELECT id, username, password_hash, salt FROM accounts WHERE username_lower=?', (username.strip().lower(),)).fetchone()
        if row is None:
            return None
        if hmac.compare_digest(self._hash_password(password, row['salt']), row['password_hash']):
            return {'id': row['id'], 'username': row['username']}
        return None

    def account(self, account_id):
        with self.connect() as db:
            row = db.execute('SELECT id, username, created_at, base_tier, timed_tier, timed_until FROM accounts WHERE id=?',
                             (account_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result['tier'] = membership.effective_tier(row['base_tier'], row['timed_tier'], row['timed_until'])
        return result

    INVITE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    SESSION_DAYS = 30

    @staticmethod
    def _code_hash(code):
        return hashlib.sha256(str(code).strip().upper().encode('utf-8')).hexdigest()

    def create_invite(self, tier, max_uses=1, expires_at=None, grant_days=None, note=''):
        if tier not in membership.RANK:
            raise ValueError(f'Unknown tier {tier!r}')
        if max_uses < 1:
            raise ValueError('max_uses must be at least 1')
        if tier == 'pro':
            grant_days = grant_days or membership.PRO_GRANT_DAYS
            if grant_days < 1:
                raise ValueError('grant_days must be at least 1')
        else:
            grant_days = None
        if expires_at:
            expires_at = datetime.fromisoformat(expires_at).astimezone(timezone.utc).isoformat()
        group = lambda: ''.join(secrets.choice(self.INVITE_ALPHABET) for _ in range(4))
        code = f'RR-{tier.upper()}-{group()}-{group()}'
        with self.connect() as db:
            cursor = db.execute('''INSERT INTO invites(code_hash, tier, max_uses, expires_at, grant_days, note, created_at)
                                   VALUES(?,?,?,?,?,?,?)''',
                                (self._code_hash(code), tier, max_uses, expires_at, grant_days, note or '', timestamp()))
        return {'id': cursor.lastrowid, 'code': code, 'tier': tier, 'max_uses': max_uses,
                'expires_at': expires_at, 'grant_days': grant_days}

    def list_invites(self):
        with self.connect() as db:
            rows = db.execute('''SELECT id, tier, max_uses, uses, expires_at, grant_days, revoked_at, note, created_at
                                 FROM invites ORDER BY id''').fetchall()
        return [dict(row) for row in rows]

    def revoke_invite(self, invite_id):
        with self.connect() as db:
            changed = db.execute('UPDATE invites SET revoked_at=? WHERE id=? AND revoked_at IS NULL',
                                 (timestamp(), invite_id)).rowcount
        return bool(changed)

    @classmethod
    def _claim(cls, db, code, now):
        row = db.execute('SELECT * FROM invites WHERE code_hash=?', (cls._code_hash(code),)).fetchone()
        if row is None or row['revoked_at'] or row['uses'] >= row['max_uses']:
            raise InviteError()
        if row['expires_at'] and datetime.fromisoformat(row['expires_at']) <= now:
            raise InviteError()
        return row

    @staticmethod
    def _consume(db, invite, account_id, kind):
        db.execute('UPDATE invites SET uses=uses+1 WHERE id=?', (invite['id'],))
        db.execute('INSERT INTO invite_redemptions(invite_id, account_id, kind, created_at) VALUES(?,?,?,?)',
                   (invite['id'], account_id, kind, timestamp()))

    def register_with_invite(self, username, password, code, now=None):
        now = now or membership.now_utc()
        username = username.strip()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            invite = self._claim(db, code, now)
            base, timed, until = 'free', None, None
            if invite['tier'] == 'pro':
                timed, until = 'pro', membership.extend_timed(None, invite['grant_days'] or membership.PRO_GRANT_DAYS, now)
            else:
                base = invite['tier']
            account_id = self._insert_account(db, username, password, base, timed, until)
            self._consume(db, invite, account_id, 'register')
        return self.account(account_id)

    def redeem(self, account_id, code, now=None):
        now = now or membership.now_utc()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            invite = self._claim(db, code, now)
            row = db.execute('SELECT base_tier, timed_tier, timed_until FROM accounts WHERE id=?', (account_id,)).fetchone()
            rank = membership.RANK
            if invite['tier'] == 'pro':
                if rank[row['base_tier']] >= rank['pro']:
                    return {'changed': False, 'account': self.account(account_id)}
                current = row['timed_until'] if row['timed_tier'] == 'pro' else None
                until = membership.extend_timed(current, invite['grant_days'] or membership.PRO_GRANT_DAYS, now)
                db.execute("UPDATE accounts SET timed_tier='pro', timed_until=? WHERE id=?", (until, account_id))
            else:
                if rank[invite['tier']] <= rank[row['base_tier']]:
                    return {'changed': False, 'account': self.account(account_id)}
                db.execute('UPDATE accounts SET base_tier=? WHERE id=?', (invite['tier'], account_id))
            self._consume(db, invite, account_id, 'redeem')
        return {'changed': True, 'account': self.account(account_id)}

    @staticmethod
    def _token_hash(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def create_session(self, account_id, user_agent=''):
        token = secrets.token_urlsafe(32)
        now = timestamp()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO sessions(token_hash, account_id, created_at, last_seen_at, user_agent) VALUES(?,?,?,?,?)',
                       (self._token_hash(token), account_id, now, now, (user_agent or '')[:200]))
            db.execute('''DELETE FROM sessions WHERE account_id=? AND id NOT IN (
                              SELECT id FROM sessions WHERE account_id=? ORDER BY created_at DESC, id DESC LIMIT ?)''',
                       (account_id, account_id, membership.DEVICE_LIMIT))
        return token

    def session_account(self, token, now=None):
        if not token:
            return None
        now = now or membership.now_utc()
        with self.connect() as db:
            row = db.execute('SELECT id, account_id, created_at FROM sessions WHERE token_hash=?', (self._token_hash(token),)).fetchone()
            if row is None:
                return None
            if datetime.fromisoformat(row['created_at']) + timedelta(days=self.SESSION_DAYS) <= now:
                db.execute('DELETE FROM sessions WHERE id=?', (row['id'],))
                return None
            db.execute('UPDATE sessions SET last_seen_at=? WHERE id=?', (now.isoformat(), row['id']))
        account = self.account(row['account_id'])
        if account:
            account['session_id'] = row['id']
        return account

    def delete_session(self, token):
        if token:
            with self.connect() as db:
                db.execute('DELETE FROM sessions WHERE token_hash=?', (self._token_hash(token),))

    def sessions(self, account_id):
        with self.connect() as db:
            rows = db.execute('SELECT id, created_at, last_seen_at, user_agent FROM sessions WHERE account_id=? ORDER BY created_at, id',
                              (account_id,)).fetchall()
        return [dict(row) for row in rows]

    def revoke_session(self, account_id, session_id):
        with self.connect() as db:
            return bool(db.execute('DELETE FROM sessions WHERE account_id=? AND id=?', (account_id, session_id)).rowcount)

    AI_DAILY_LIMIT = 20

    def ai_quota(self, day):
        with self.connect() as db:
            used = db.execute('SELECT COUNT(*) FROM ai_calls WHERE day=?', (day,)).fetchone()[0]
        return {'date': day, 'used': used, 'limit': self.AI_DAILY_LIMIT,
                'remaining': max(0, self.AI_DAILY_LIMIT - used)}

    def reserve_ai_call(self, cycle_id, day, kind, prompt, conversation):
        stamp = timestamp()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            used = db.execute('SELECT COUNT(*) FROM ai_calls WHERE day=?', (day,)).fetchone()[0]
            if used >= self.AI_DAILY_LIMIT:
                raise AiQuotaError('Daily AI quota reached (20 calls, Beijing time). Try again tomorrow or export for an external AI.')
            cursor = db.execute('''INSERT INTO ai_calls(cycle_id,day,kind,status,prompt,conversation,created_at,updated_at)
                VALUES(?,?,?,'reserved',?,?,?,?)''',
                (cycle_id, day, kind, prompt, json.dumps(conversation, ensure_ascii=False), stamp, stamp))
            return cursor.lastrowid

    def finish_ai_call(self, call_id, status, response=None, error=None):
        with self.connect() as db:
            db.execute('UPDATE ai_calls SET status=?,response=?,error=?,updated_at=? WHERE id=?',
                       (status, response, error, timestamp(), call_id))

    def ai_calls(self, cycle_id):
        with self.connect() as db:
            rows = db.execute('''SELECT id,day,kind,status,error,created_at,updated_at FROM ai_calls
                WHERE cycle_id=? ORDER BY id DESC LIMIT 100''', (cycle_id,)).fetchall()
        return [dict(row) for row in rows]

    def ai_call(self, call_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM ai_calls WHERE id=?', (call_id,)).fetchone()
        if row is None:
            return None
        record = dict(row)
        record['conversation'] = json.loads(record['conversation'])
        return record

    def attempts(self, cycle_id):
        with self.connect() as db:
            rows = db.execute('SELECT lift,number,load,result,updated_at FROM attempts WHERE cycle_id=? ORDER BY lift,number',
                              (cycle_id,)).fetchall()
        return [dict(row) for row in rows]

    def save_attempt(self, cycle_id, lift, number, load, result):
        stamp = timestamp()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_active(db, cycle_id)
            if number > 1:
                previous = db.execute('SELECT result FROM attempts WHERE cycle_id=? AND lift=? AND number=?',
                                      (cycle_id, lift, number - 1)).fetchone()
                if previous is None or previous['result'] is None:
                    raise ReadOnlyError(f'Confirm {lift} attempt {number - 1} before attempt {number}.')
            db.execute('''INSERT INTO attempts VALUES(?,?,?,?,?,?)
                ON CONFLICT(cycle_id,lift,number) DO UPDATE SET load=excluded.load,
                result=excluded.result,updated_at=excluded.updated_at''',
                (cycle_id, lift, number, load, result, stamp))
            db.execute('INSERT INTO records_journal(cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?)',
                       (cycle_id, 'attempt', f'{lift}|{number}',
                        json.dumps({'lift': lift, 'number': number, 'load': load, 'result': result}), stamp))
        return {'lift': lift, 'number': number, 'load': load, 'result': result, 'updated_at': stamp}

    def prepare_deletion(self, cycle_id):
        token = secrets.token_urlsafe(24)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            cycle = db.execute('SELECT status FROM cycles WHERE id=?', (cycle_id,)).fetchone()
            if cycle is None:
                raise KeyError(cycle_id)
            if cycle['status'] == 'active':
                raise ReadOnlyError('The active cycle cannot be deleted. Import a new plan first.')
            db.execute('DELETE FROM deletion_tokens WHERE cycle_id=?', (cycle_id,))
            db.execute('INSERT INTO deletion_tokens VALUES(?,?,?)', (token, cycle_id, timestamp()))
        return token

    def delete_cycle(self, cycle_id, token):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            cycle = db.execute('SELECT status FROM cycles WHERE id=?', (cycle_id,)).fetchone()
            if cycle is None:
                raise KeyError(cycle_id)
            if cycle['status'] == 'active':
                raise ReadOnlyError('The active cycle cannot be deleted. Import a new plan first.')
            issued = db.execute('SELECT token FROM deletion_tokens WHERE cycle_id=?', (cycle_id,)).fetchone()
            if issued is None or not secrets.compare_digest(issued['token'], token):
                raise ReadOnlyError('Export this cycle before deleting it. Request a fresh deletion export first.')
            # Snapshot only validated deletions, before any row is removed.
            self.snapshot()
            for table in ('attempts', 'ai_calls', 'questionnaires', 'prescription_versions', 'body_metrics',
                          'archives', 'records_journal', 'readiness_v2', 'readiness', 'logs_journal', 'logs',
                          'plans', 'deletion_tokens'):
                db.execute(f'DELETE FROM {table} WHERE cycle_id=?', (cycle_id,))
            db.execute('DELETE FROM cycles WHERE id=?', (cycle_id,))
        return {'deleted': cycle_id}

    def questionnaire(self, cycle_id):
        with self.connect() as db:
            row = db.execute('SELECT payload,status,updated_at FROM questionnaires WHERE cycle_id=?',
                             (cycle_id,)).fetchone()
        if row is None:
            return None
        return {'status': row['status'], 'payload': json.loads(row['payload']), 'updated_at': row['updated_at']}

    def save_questionnaire(self, cycle_id, payload, status):
        stamp = timestamp()
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_active(db, cycle_id)
            db.execute('INSERT INTO records_journal(cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?)',
                       (cycle_id, 'questionnaire', status, json.dumps({'status': status, 'payload': payload}), stamp))
            db.execute('''INSERT INTO questionnaires VALUES(?,?,?,?)
                ON CONFLICT(cycle_id) DO UPDATE SET payload=excluded.payload,status=excluded.status,
                updated_at=excluded.updated_at''', (cycle_id, encoded, status, stamp))
        return {'status': status, 'payload': payload, 'updated_at': stamp}

    def prescription_versions(self, cycle_id):
        from .stats.variations import digest
        current = digest(self.plan(cycle_id))
        with self.connect() as db:
            rows = db.execute('SELECT * FROM prescription_versions WHERE cycle_id=? ORDER BY created_at DESC', (cycle_id,)).fetchall()
        return [{'id': row['id'], 'created_at': row['created_at'], 'current': row['id'] == current,
                 'policy': json.loads(row['json']).get('prescription', {}).get('version', 'legacy')}
                for row in rows]

    def prescription_version(self, cycle_id, revision_id):
        with self.connect() as db:
            row = db.execute('SELECT json FROM prescription_versions WHERE cycle_id=? AND id=?', (cycle_id, revision_id)).fetchone()
        return json.loads(row['json']) if row else None

    def replace_prescription(self, cycle_id, expected_id, plan, action):
        from .stats.variations import digest
        revision_id = digest(plan)
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_active(db, cycle_id)
            current = json.loads(db.execute('SELECT json FROM plans WHERE cycle_id=?', (cycle_id,)).fetchone()['json'])
            if digest(current) != expected_id:
                raise ReadOnlyError('Prescription changed. Refresh and review the new version before saving.')
            if revision_id != expected_id:
                encoded = json.dumps(plan, ensure_ascii=False, allow_nan=False)
                stamp = timestamp()
                db.execute('INSERT OR IGNORE INTO prescription_versions VALUES(?,?,?,?)', (cycle_id, revision_id, encoded, stamp))
                db.execute('INSERT INTO records_journal(cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?)',
                           (cycle_id, 'prescription', revision_id, json.dumps({'action': action, 'from': expected_id, 'to': revision_id}), stamp))
                db.execute('UPDATE plans SET json=? WHERE cycle_id=?', (encoded, cycle_id))
        return revision_id

    def readiness_records(self, cycle_id):
        with self.connect() as db:
            records = db.execute('SELECT payload,updated_at FROM readiness_v2 WHERE cycle_id=? ORDER BY date,updated_at', (cycle_id,)).fetchall()
        return [{**json.loads(row['payload']), 'updated_at': row['updated_at']} for row in records]

    def legacy_readiness(self, cycle_id):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM readiness WHERE cycle_id=? ORDER BY date,session_id', (cycle_id,))]

    def metrics(self, cycle_id):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM body_metrics WHERE cycle_id=? ORDER BY date', (cycle_id,)).fetchall()
        return [{'date': row['date'], 'bodyweight': row['bodyweight'], 'bodyfat': row['bodyfat'],
                 'measurements': json.loads(row['measurements_json'] or '{}')} for row in rows]

    def save_readiness(self, cycle_id, payload):
        stamp = timestamp()
        key = f"{payload['date']}|{payload['session_id']}"
        encoded = json.dumps(payload, ensure_ascii=False)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_active(db, cycle_id)
            db.execute('INSERT INTO records_journal(cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?)',
                       (cycle_id, 'readiness', key, encoded, stamp))
            db.execute('''INSERT INTO readiness_v2 VALUES(?,?,?,?,?)
                ON CONFLICT(cycle_id,date,session_id) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at''',
                       (cycle_id, payload['date'], payload['session_id'], encoded, stamp))

    def save_metrics(self, cycle_id, payload):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_active(db, cycle_id)
            db.execute('INSERT INTO records_journal(cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?)',
                       (cycle_id, 'body_metrics', payload['date'], json.dumps(payload), timestamp()))
            db.execute('''INSERT INTO body_metrics(cycle_id,date,bodyweight,bodyfat,measurements_json) VALUES(?,?,?,?,?)
                ON CONFLICT(cycle_id,date) DO UPDATE SET bodyweight=excluded.bodyweight,
                bodyfat=excluded.bodyfat,measurements_json=excluded.measurements_json''',
                       (cycle_id, payload['date'], payload['bodyweight'], payload['bodyfat'], json.dumps(payload['measurements'])))

    @staticmethod
    def require_active(db, cycle_id):
        if db.execute("SELECT 1 FROM cycles WHERE id=? AND status='active'", (cycle_id,)).fetchone() is None:
            raise ReadOnlyError('Archived cycles are read-only')

    def cycles(self):
        with self.connect() as db:
            cycles = [dict(row) for row in db.execute('SELECT * FROM cycles ORDER BY start_date DESC')]
        return {'cycles': cycles, 'active_cycle_id': next((row['id'] for row in cycles if row['status'] == 'active'), None)}

    def plan(self, cycle_id=None):
        with self.connect() as db:
            if cycle_id is None:
                row = db.execute("SELECT p.json FROM plans p JOIN cycles c ON c.id=p.cycle_id WHERE c.status='active'").fetchone()
            else:
                row = db.execute('SELECT json FROM plans WHERE cycle_id=?', (cycle_id,)).fetchone()
        return json.loads(row['json']) if row else None

    def logs(self, cycle_id):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM logs WHERE cycle_id=? ORDER BY key', (cycle_id,)).fetchall()
        return {row['key']: {'load': row['load'], 'sets': row['set_count'], 'reps': row['reps'],
                             'rpe': row['rpe'], 'note': row['note'], 'updated_at': row['updated_at']}
                for row in rows}

    def review_source(self, cycle_id):
        with self.connect() as db:
            db.execute('BEGIN')
            return self._review_source(db, cycle_id)

    @staticmethod
    def _review_source(db, cycle_id):
        cycle = db.execute('SELECT * FROM cycles WHERE id=?', (cycle_id,)).fetchone()
        if cycle is None:
            return None
        plan = json.loads(db.execute('SELECT json FROM plans WHERE cycle_id=?', (cycle_id,)).fetchone()['json'])
        logs = {row['key']: {'load': row['load'], 'sets': row['set_count'], 'reps': row['reps'],
                            'rpe': row['rpe'], 'note': row['note'], 'updated_at': row['updated_at']}
                for row in db.execute('SELECT * FROM logs WHERE cycle_id=? ORDER BY key', (cycle_id,))}
        metrics = [{'date': row['date'], 'bodyweight': row['bodyweight'], 'bodyfat': row['bodyfat'],
                    'measurements': json.loads(row['measurements_json'] or '{}')}
                   for row in db.execute('SELECT * FROM body_metrics WHERE cycle_id=? ORDER BY date', (cycle_id,))]
        readiness = [{**json.loads(row['payload']), 'updated_at': row['updated_at']}
                     for row in db.execute('SELECT * FROM readiness_v2 WHERE cycle_id=? ORDER BY date,updated_at', (cycle_id,))]
        legacy = [dict(row) for row in db.execute('SELECT * FROM readiness WHERE cycle_id=? ORDER BY date,session_id', (cycle_id,))]
        versions = [{'id': row['id'], 'plan': json.loads(row['json']), 'created_at': row['created_at']}
                    for row in db.execute('SELECT * FROM prescription_versions WHERE cycle_id=? ORDER BY created_at,id', (cycle_id,))]
        journals = {}
        for name, table in (('logs', 'logs_journal'), ('records', 'records_journal')):
            journals[name] = [{**dict(row), 'payload': json.loads(row['payload'])}
                              for row in db.execute(f'SELECT * FROM {table} WHERE cycle_id=? ORDER BY id', (cycle_id,))]
        archived = db.execute('SELECT review_json FROM archives WHERE cycle_id=?', (cycle_id,)).fetchone()
        questionnaire = db.execute('SELECT payload,status,updated_at FROM questionnaires WHERE cycle_id=?',
                                   (cycle_id,)).fetchone()
        return {'cycle': dict(cycle), 'plan': plan, 'logs': logs, 'body_metrics': metrics,
                'readiness': readiness, 'legacy_readiness': legacy, 'prescription_versions': versions,
                'journals': journals, 'saved_review': json.loads(archived['review_json']) if archived else None,
                'questionnaire': {'status': questionnaire['status'], 'payload': json.loads(questionnaire['payload']),
                                  'updated_at': questionnaire['updated_at']} if questionnaire else None}

    def activate_plan(self, plan, expected_source_id, app_version):
        from .calendar import calendar_state
        from .stats.review import build_review
        from .stats.variations import digest
        from .validation import validate_plan
        validate_plan(plan, file='import.json')
        with self.connect() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] != 5:
                raise RuntimeError('Unsupported database version. No data was changed.')
        self.snapshot()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('PRAGMA user_version').fetchone()[0] != 5:
                raise RuntimeError('Unsupported database version. No data was changed.')
            active = db.execute("SELECT id FROM cycles WHERE status='active'").fetchone()
            source = self._review_source(db, active['id']) if active else None
            if source is None or digest(source) != expected_source_id:
                raise ReadOnlyError('Current cycle or records changed. Preview again before importing.')
            meta = plan['meta']
            if db.execute('SELECT 1 FROM cycles WHERE id=?', (meta['planId'],)).fetchone():
                raise ReadOnlyError('Cycle ID already exists. Existing cycles cannot be overwritten.')
            old_id = source['cycle']['id']
            stamp = timestamp()
            event = {'action': 'import', 'from': old_id, 'to': meta['planId'], 'plan_sha256': digest(plan)}
            db.execute('INSERT INTO records_journal(cycle_id,kind,key,payload,created_at) VALUES(?,?,?,?,?)',
                       (old_id, 'import', meta['planId'], json.dumps(event), stamp))
            db.execute("UPDATE cycles SET status='archived' WHERE id=?", (old_id,))
            archived_source = self._review_source(db, old_id)
            as_of = calendar_state(source['plan'], source['logs'])['date']
            review = build_review(archived_source, stamp, app_version, as_of)
            db.execute('INSERT INTO archives VALUES(?,?,?,?)',
                       (old_id, old_id, json.dumps(review, ensure_ascii=False, allow_nan=False), stamp))
            encoded = json.dumps(plan, ensure_ascii=False, allow_nan=False)
            db.execute('INSERT INTO cycles VALUES(?,?,?,?,?,?)',
                       (meta['planId'], meta['name'], meta['startDate'], meta['endDate'], 'active', plan['schemaVersion']))
            db.execute('INSERT INTO plans VALUES(?,?,?,?,?)',
                       (meta['planId'], meta['planId'], encoded, plan['schemaVersion'], stamp))
            db.execute('INSERT INTO prescription_versions VALUES(?,?,?,?)',
                       (meta['planId'], digest(plan), encoded, stamp))
        return {'saved': True, 'active_cycle_id': meta['planId'], 'archived_cycle_id': old_id}

    def save_log(self, cycle_id, row, payload):
        key = f"{row['week']}|{row['day']}|{row['seq']}"
        stamp = timestamp()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.require_active(db, cycle_id)
            db.execute('INSERT INTO logs_journal(cycle_id,key,payload,created_at) VALUES(?,?,?,?)',
                       (cycle_id, key, json.dumps(payload), stamp))
            db.execute('''INSERT INTO logs VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(cycle_id,key) DO UPDATE SET
                load=excluded.load,reps=excluded.reps,rpe=excluded.rpe,set_count=excluded.set_count,
                note=excluded.note,updated_at=excluded.updated_at''',
                (cycle_id, key, row['date'], f"{row['week']}|{row['day']}", row['movementId'],
                 payload['load'], payload['reps'], payload['rpe'], payload['sets'], payload['note'], stamp))
        return {'key': key, **payload, 'updated_at': stamp}
