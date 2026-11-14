"""Owner-only invite codes: create, list, revoke.

Run on the host that owns the database, e.g.
  python -m server.tools.invite create --tier plus --note "for Lin"
The plain code is printed once at creation; the database keeps only its sha256.
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.app.membership import TIERS
from server.app.store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description='Manage Roast Raw invite codes.')
    parser.add_argument('--db', default=os.environ.get('RR_DB_PATH', str(ROOT / 'data' / 'roastraw.sqlite3')))
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('create', help='Create a code and print it once.')
    create.add_argument('--tier', required=True, choices=TIERS)
    create.add_argument('--uses', type=int, default=1, help='How many accounts may use the code (default 1).')
    create.add_argument('--expires', help='Code expiry as an ISO date-time with offset, e.g. 2026-12-31T23:59:59+08:00.')
    create.add_argument('--days', type=int, help='Pro only: days granted per use (default 30).')
    create.add_argument('--note', default='')
    commands.add_parser('list', help='List codes without their plain text.')
    revoke = commands.add_parser('revoke', help='Revoke a code by id.')
    revoke.add_argument('id', type=int)
    args = parser.parse_args(argv)

    if not Path(args.db).exists():
        parser.error(f'database not found: {args.db}')
    store = Store(args.db)
    try:
        if args.command == 'create':
            if args.expires and '+' not in args.expires[10:] and not args.expires.endswith('Z'):
                parser.error('--expires needs an explicit offset, e.g. +08:00')
            result = store.create_invite(args.tier, args.uses, args.expires.replace('Z', '+00:00') if args.expires else None,
                                         args.days, args.note)
            print(json.dumps(result, ensure_ascii=False))
        elif args.command == 'list':
            for row in store.list_invites():
                print(json.dumps(row, ensure_ascii=False))
        else:
            if not store.revoke_invite(args.id):
                print(f'No active invite with id {args.id}.', file=sys.stderr)
                return 1
            print(f'Revoked invite {args.id}.')
    except sqlite3.OperationalError as exc:
        print(f'Database is not ready for invites ({exc}). Start the service once so the membership migration runs.', file=sys.stderr)
        return 1
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == '__main__':
    sys.exit(main())
