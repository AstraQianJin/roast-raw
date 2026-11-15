"""Archive the current cycle and seed the regenerated plan into a live database.

Moving the cycle start date changes meta.planId, so the old cycle cannot be
re-dated in place: its logs, readiness and body metrics belong to the old
calendar. This tool uses the same path as a plan import — it snapshots the
database, archives the active cycle with a review record and a journal event,
then inserts the new cycle, plan and prescription version.

usage:
  server/.venv/Scripts/python.exe server/tools/roll_cycle.py --plan data/plan.json
  server/.venv/Scripts/python.exe server/tools/roll_cycle.py --db other.sqlite3 --plan data/plan.json --expect rpl-raw-2026-11-16
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from server.app.store import Store
from server.app.stats.variations import digest
from server.app.validation import validate_plan


def bring_current(base: Store, owner_username: str) -> None:
    """Run the same unconditional upgrade chain the app runs at startup."""
    for step in (base.upgrade, base.upgrade_prescriptions, base.upgrade_questionnaire,
                 base.upgrade_ai, base.upgrade_accounts, base.upgrade_membership):
        step()
    base.upgrade_ledger(owner_username)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=str(ROOT / 'data' / 'roastraw.sqlite3'))
    parser.add_argument('--plan', default=str(ROOT / 'data' / 'plan.json'))
    parser.add_argument('--expect', help='refuse to run unless the active cycle has this planId')
    parser.add_argument('--owner', default=os.environ.get('RR_ACCESS_USERNAME', ''))
    parser.add_argument('--app-version', default='0.30')
    args = parser.parse_args(argv)

    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    validate_plan(plan, file=str(args.plan))
    new_id = plan['meta']['planId']
    base = Store(args.db)
    bring_current(base, args.owner)
    scoped = base.for_account(base.open_ledger())
    cycles = scoped.cycles()
    active = cycles['active_cycle_id']
    if args.expect and active != args.expect:
        print('refused: active cycle is %r, expected %r' % (active, args.expect), file=sys.stderr)
        return 2
    if active and active == new_id:
        print('nothing to do: %s is already active' % new_id)
        return 0
    expected_source = digest(scoped.review_source(active)) if active else scoped.EMPTY_SOURCE_ID
    result = scoped.activate_plan(plan, expected_source, args.app_version)
    print('roll: active %s -> %s' % (active, result['active_cycle_id']))
    print('roll: archived %s (plan, logs, readiness and body metrics stay readable)' % result['archived_cycle_id'])
    # Readback proves the old data survived and the new cycle is serving.
    old = scoped.cycles()['cycles']
    rows = {row['id']: row['status'] for row in old}
    print('readback: cycles=%s' % json.dumps(rows, ensure_ascii=False))
    print('readback: new start=%s plan=%s' % (
        scoped.cycles()["cycles"] and plan['meta']['startDate'],
        scoped.plan()['meta']['planId']))
    print('readback: old logs=%d new logs=%d' % (
        len(scoped.logs(result['archived_cycle_id'])), len(scoped.logs(result['active_cycle_id']))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
