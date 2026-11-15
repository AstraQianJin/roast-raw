"""Read-only orphan audit for the journal database.

Every child row must point at a parent that exists. A row whose parent is gone is
an orphan: it is invisible to the UI but still counted by queries that walk the
child table, so it silently inflates volume, readiness history or AI quota.

The link list is explicit rather than reflected from the SQL text, so adding a
table without adding a link here is a visible omission in review, not a silent
zero. `cycles.account_id = 0` is the open ledger written before accounts existed
and is not an orphan.
"""
import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / 'data' / 'roastraw.sqlite3'

# (child table, child column, parent table, parent column, value that means "no parent")
LINKS = (
    ('plans', 'cycle_id', 'cycles', 'id', None),
    ('logs', 'cycle_id', 'cycles', 'id', None),
    ('logs_journal', 'cycle_id', 'cycles', 'id', None),
    ('readiness', 'cycle_id', 'cycles', 'id', None),
    ('readiness_v2', 'cycle_id', 'cycles', 'id', None),
    ('archives', 'cycle_id', 'cycles', 'id', None),
    ('body_metrics', 'cycle_id', 'cycles', 'id', None),
    ('records_journal', 'cycle_id', 'cycles', 'id', None),
    ('prescription_versions', 'cycle_id', 'cycles', 'id', None),
    ('questionnaires', 'cycle_id', 'cycles', 'id', None),
    ('ai_calls', 'cycle_id', 'cycles', 'id', None),
    ('attempts', 'cycle_id', 'cycles', 'id', None),
    ('deletion_tokens', 'cycle_id', 'cycles', 'id', None),
    ('cycles', 'account_id', 'accounts', 'id', 0),
    ('ai_calls', 'account_id', 'accounts', 'id', 0),
    ('sessions', 'account_id', 'accounts', 'id', None),
    ('invite_redemptions', 'account_id', 'accounts', 'id', None),
)


def columns(db, table):
    return [row[1] for row in db.execute(f'PRAGMA table_info({table})')]


def tables(db):
    return {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def audit(db_path=DEFAULT_DB):
    """Return {'checked': [...], 'skipped': [...], 'orphans': {table: count}, 'total': int}."""
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f'No database at {path}')
    with closing(sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)) as db:
        present = tables(db)
        checked, skipped, orphans = [], [], {}
        for table, column, parent, parent_column, neutral in LINKS:
            link = f'{table}.{column}->{parent}.{parent_column}'
            if table not in present or parent not in present:
                skipped.append({'link': link, 'reason': 'table missing'})
                continue
            if column not in columns(db, table) or parent_column not in columns(db, parent):
                skipped.append({'link': link, 'reason': 'column missing'})
                continue
            clause = f'SELECT count(*) FROM {table} AS c WHERE NOT EXISTS (SELECT 1 FROM {parent} AS p WHERE p.{parent_column} = c.{column})'
            if neutral is not None:
                clause += f' AND c.{column} <> {neutral:d}'
            count = db.execute(clause).fetchone()[0]
            checked.append(link)
            if count:
                orphans[link] = count
        return {'checked': checked, 'skipped': skipped, 'orphans': orphans,
                'total': sum(orphans.values()), 'tables': len(present)}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Report orphan rows in the Roast Raw database.')
    parser.add_argument('--db', default=str(DEFAULT_DB))
    parser.add_argument('--json', action='store_true', help='print one JSON object instead of a summary')
    args = parser.parse_args(argv)
    result = audit(args.db)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f'{len(result["checked"])} links checked across {result["tables"]} tables; '
              f'{result["total"]} orphan rows' + (f' {result["orphans"]}' if result['orphans'] else ''))
    return 0 if result['total'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
