"""Write web/src/landing-facts.json from data/plan.json.

The landing page must never carry hand-typed numbers. This generator reads one
sample training day (W01 / DAY A) out of the committed plan and writes the small
subset the front end needs: the badge label, the main-lift cards, the day set
count, the day tonnage and the cycle tonnage.

Contracts (owner ruling 2026-11-15):
- day_total_kg covers that one day only and never includes warm-ups.
- cycle_total_kg is the whole cycle and must equal meta.cycleTonnageKg. One
   field never carries both meanings.
- pct is only emitted when the lift's movement has a 1RM anchor in meta.anchors;
   without a same-source anchor the field is dropped and the landing hides it.
- The sample day is W01 / DAY A. Changing the sample day means re-running this
   script, never editing the JSON by hand.

usage:
  server/.venv/Scripts/python.exe server/tools/landing_facts.py            # write the artifact
  server/.venv/Scripts/python.exe server/tools/landing_facts.py --check    # compare without writing
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN_PATH = ROOT / 'data' / 'plan.json'
OUT_PATH = ROOT / 'web' / 'src' / 'landing-facts.json'
SAMPLE_WEEK = 1
SAMPLE_DAY = 'A'
LIFT_ORDER = ('S', 'B', 'D')


def _number(value):
    """Integral floats print as ints so the JSON stays compact and diff-friendly."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def build_facts(plan: dict) -> dict:
    meta = plan['meta']
    rows = [row for row in plan['workouts'] if row['week'] == SAMPLE_WEEK and row['day'] == SAMPLE_DAY]
    if not rows:
        raise SystemExit('plan has no rows for the sample day W01 / DAY A')
    anchors = {
        entry['movement']: entry['value']
        for entry in (meta.get('anchors') or {}).values()
        if entry.get('unit') == 'kg' and entry.get('value') is not None
    }
    lifts = []
    for code in LIFT_ORDER:
        candidates = [
            row for row in rows
            if row['bucket'] == 'main' and row['lift'] == code and row.get('loadKg') is not None
        ]
        if not candidates:
            continue
        top = max(candidates, key=lambda row: (row.get('tonnageKg') or 0, row['loadKg']))
        entry = {
            'lift': code,
            'movement': top['movement'],
            'top_kg': _number(top['loadKg']),
        }
        if top.get('pct') is not None and top['movement'] in anchors:
            entry['pct'] = round(top['pct'] * 100, 1)
        entry['sets'] = int(top['sets'])
        entry['reps'] = int(top['reps'])
        lifts.append(entry)
    day_total = round(sum(row.get('tonnageKg') or 0 for row in rows), 1)
    facts = {
        'planId': meta['planId'],
        'startDate': meta['startDate'],
        'week': SAMPLE_WEEK,
        'day': SAMPLE_DAY,
        'date': rows[0]['date'],
        'label': 'W{0:02d} · DAY {1}'.format(SAMPLE_WEEK, SAMPLE_DAY),
        'lifts': lifts,
        'set_count': int(sum(row['sets'] for row in rows)),
        'day_total_kg': _number(day_total),
        'cycle_total_kg': float(meta['cycleTonnageKg']),
        'tonnage_basis': meta['tonnageBasis'],
    }
    return facts


def serialise(facts: dict) -> str:
    return json.dumps(facts, ensure_ascii=False, separators=(',', ':'))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', default=str(PLAN_PATH))
    parser.add_argument('--out', default=str(OUT_PATH))
    parser.add_argument('--check', action='store_true', help='compare the artifact instead of writing it')
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    text = serialise(build_facts(plan))
    target = Path(args.out)
    if args.check:
        current = target.read_text(encoding='utf-8') if target.is_file() else None
        if current != text:
            print('landing-facts.json drifted from data/plan.json: re-run server/tools/landing_facts.py', flush=True)
            return 1
        print('landing-facts.json matches data/plan.json')
        return 0
    target.write_text(text, encoding='utf-8')
    print('wrote {0}'.format(target))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
