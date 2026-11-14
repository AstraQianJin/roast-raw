"""Single source for membership tiers, pricing and the capability matrix.

The server gates on this table; /api/session hands the caller's capability list to
the app, and server/tools/export_membership.py writes the landing-page JSON from it.
"""
from datetime import datetime, timedelta, timezone

TIERS = ('free', 'lite', 'plus', 'pro', 'ultra')
RANK = {tier: index for index, tier in enumerate(TIERS)}
PERMANENT = ('free', 'lite', 'plus', 'ultra')
DEVICE_LIMIT = 5
PRO_GRANT_DAYS = 30

PRICING = {
    'free': {'usd': '0', 'cny': '0', 'billing': 'FREE', 'billing_text': 'Free forever', 'period': ''},
    'lite': {'usd': '19.9', 'cny': '68', 'billing': 'ONE-TIME', 'billing_text': 'One-time, no renewal', 'period': ''},
    'plus': {'usd': '69.9', 'cny': '198', 'billing': 'ONE-TIME', 'billing_text': 'One-time, no renewal', 'period': ''},
    'pro': {'usd': '19.9', 'cny': '98', 'billing': 'MONTHLY', 'billing_text': 'Billed monthly', 'period': '/mo'},
    'ultra': {'usd': None, 'cny': None, 'billing': 'INVITE', 'billing_text': 'Invite only', 'period': ''},
}

# Order is the display order on the landing comparison; min_tier is the gate.
CAPABILITIES = (
    {'id': 'logging', 'label': 'Logging & daily prescription', 'min_tier': 'free'},
    {'id': 'cycle_views', 'label': 'Cycle, block & week views', 'min_tier': 'free'},
    {'id': 'plan_io', 'label': 'Plan import & export', 'min_tier': 'free'},
    {'id': 'basic_stats', 'label': 'Basic stats', 'min_tier': 'free'},
    {'id': 'share_card', 'label': 'Share card', 'min_tier': 'free'},
    {'id': 'gear_warmups', 'label': 'Gear & Sheiko warm-ups', 'min_tier': 'lite'},
    {'id': 'test_week', 'label': 'Test week & meet attempts', 'min_tier': 'lite'},
    {'id': 'muscle_map', 'label': 'Muscle-group map', 'min_tier': 'plus'},
    {'id': 'lift_register', 'label': 'Lift register & trends', 'min_tier': 'plus'},
    {'id': 'recovery_body', 'label': 'Recovery & body metrics', 'min_tier': 'plus'},
    {'id': 'oracle_ai', 'label': 'ORACLE AI brief', 'min_tier': 'pro', 'note': '20 calls per Beijing day'},
    {'id': 'vault_ledger', 'label': 'VAULT cloud ledger', 'min_tier': 'pro'},
)
CAPABILITY_TIER = {entry['id']: entry['min_tier'] for entry in CAPABILITIES}


class TierError(Exception):
    def __init__(self, capability):
        self.capability = capability
        self.required_tier = CAPABILITY_TIER[capability]
        label = next(entry['label'] for entry in CAPABILITIES if entry['id'] == capability)
        super().__init__(f'{label} needs the {self.required_tier.capitalize()} tier or higher. Redeem a code to unlock it.')


def now_utc():
    return datetime.now(timezone.utc)


def effective_tier(base_tier, timed_tier, timed_until, now=None):
    base = base_tier if base_tier in RANK else 'free'
    if timed_tier in RANK and timed_until:
        if datetime.fromisoformat(timed_until) > (now or now_utc()) and RANK[timed_tier] > RANK[base]:
            return timed_tier
    return base


def allows(tier, capability):
    return RANK[tier] >= RANK[CAPABILITY_TIER[capability]]


def capabilities(tier):
    return [entry['id'] for entry in CAPABILITIES if allows(tier, entry['id'])]


def require(tier, capability):
    if not allows(tier, capability):
        raise TierError(capability)


def extend_timed(current_until, days, now=None):
    now = now or now_utc()
    start = max(now, datetime.fromisoformat(current_until)) if current_until else now
    return (start + timedelta(days=days)).isoformat()


def public_table():
    return {
        'tiers': list(TIERS),
        'columns': ['free', 'lite', 'plus', 'pro'],
        'pricing': PRICING,
        'device_limit': DEVICE_LIMIT,
        'pro_grant_days': PRO_GRANT_DAYS,
        'capabilities': [dict(entry) for entry in CAPABILITIES],
    }
