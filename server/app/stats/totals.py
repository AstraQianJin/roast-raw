"""One calculation for every set and tonnage figure the product shows.

Owner ruling (2026-11-15): a training total is expanded row by row from the
prescription — one plan row contributes its own ``sets`` — and the three buckets
main / variation / accessory are reported separately *and* summed into ``total``.
No page, component or endpoint may add these up a second time.

Tonnage in plan mode is the sum of the per-row ``tonnageKg`` carried by the plan.
The row is already the unit of arithmetic: a row with ``segments`` (a top set plus
back-off sets on different loads) stores the segment-weighted total there, so
recomputing ``load × reps × sets`` here would be a different, wrong number (27 rows
in the current cycle differ). Log mode keeps the logged meaning it already had:
logged sets and, for loaded non-accessory work, ``load × reps × sets`` from the log.

Rounding has one rule: this module keeps every value raw. The cycle headline is
rounded once to 0.1 t; week and block sub-totals are shown to 0.01 t so that
adding them lands on the headline. ``display_chain`` proves that chain.
"""

from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP

# Prescription buckets as they appear on a row, mapped to the three reported classes.
ROW_ROLE = {
    'main': 'main',
    'sbdVar': 'variation',
    'nonSbdVar': 'variation',
    'accessory': 'accessory',
}
ROLES = ('main', 'variation', 'accessory')
LIFT_ORDER = ('S', 'B', 'D')
T_SETS = 'One plan row contributes its own sets; main, variation and accessory are reported separately and also summed as total.'
T_TONNAGE = 'Sum of per-row tonnageKg (segment-weighted) in plan mode; logged load × reps × sets in log mode.'
T_DISPLAY = 'Cycle rounded to 0.1 t; week and block sub-totals shown to 0.01 t so the parts add to the headline.'


def round1(value):
    """Round half-up to one decimal, after a four-decimal cleanup for float noise."""
    return float(Decimal(str(round(float(value), 4))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def round2(value):
    return float(Decimal(str(round(float(value), 4))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def role_of(row):
    bucket = row.get('bucket')
    try:
        return ROW_ROLE[bucket]
    except KeyError:
        raise ValueError(f"row {row.get('week')}|{row.get('day')}|{row.get('seq')} has unknown bucket {bucket!r}")


def row_facts(row, log=None, mode='plan'):
    """The only place a row becomes (role, sets, tonnage)."""
    role = role_of(row)
    if mode == 'log' and log is not None:
        count = int(row.get('sets') or 0) if log.get('sets') is None else int(log['sets'])
        if role != 'accessory' and log.get('load') is not None and log.get('reps') is not None:
            tonnage = float(log['load']) * float(log['reps']) * count
        else:
            tonnage = 0.0
    else:
        count = int(row.get('sets') or 0)
        tonnage = float(row.get('tonnageKg') or 0)
    return role, count, tonnage


def session_totals(rows, logs=None, mode='plan'):
    """One session: sets per class, the summed total, the row count and its tonnage."""
    sets = {key: 0 for key in ROLES}
    raw_roles = {key: 0 for key in ('main', 'sbdVar', 'nonSbdVar', 'accessory')}
    tonnage = 0.0
    for row in rows:
        key = f"{row.get('week')}|{row.get('day')}|{row.get('seq')}"
        log = (logs or {}).get(key) if mode == 'log' else None
        role, count, row_tonnage = row_facts(row, log, mode)
        sets[role] += count
        raw_roles[row.get('bucket')] = raw_roles.get(row.get('bucket'), 0) + count
        tonnage += row_tonnage
    return {
        'sets': {**sets, 'total': sets['main'] + sets['variation'] + sets['accessory']},
        'roles': raw_roles,
        'rows': len(rows),
        'tonnageKg': round(tonnage, 4),
    }


def totals(plan, logs=None, mode='plan'):
    """Per-day, per-week, per-block, per-lift and whole-cycle totals from plan rows."""
    rows = plan['workouts']
    week_meta = {week['n']: week for week in plan['weeks']}
    block_meta = {block['id']: block for block in plan.get('blocks', [])}

    per_day = {}
    per_week = {}
    per_block = {}
    per_lift = {code: {'main': 0, 'variation': 0, 'tonnageKg': 0.0} for code in LIFT_ORDER}
    cycle_sets = {key: 0 for key in ROLES}
    cycle_raw_roles = {key: 0 for key in ('main', 'sbdVar', 'nonSbdVar', 'accessory')}
    cycle_tonnage = 0.0

    for row in rows:
        week_number, day = row['week'], row['day']
        block_id = week_meta[week_number]['blockId']
        week = week_meta[week_number]
        day_entry = per_day.setdefault((week_number, day), {
            'week': week_number, 'day': day, 'date': row.get('date'), 'blockId': block_id,
            'sets': {key: 0 for key in ROLES}, 'rows': 0, 'tonnageKg': 0.0,
            'roles': {key: 0 for key in ('main', 'sbdVar', 'nonSbdVar', 'accessory')},
        })
        week_entry = per_week.setdefault(week_number, {
            'n': week_number, 'blockId': block_id,
            'kind': week.get('kind'), 'sessions': week.get('sessions'),
            'dateStart': week.get('dateStart'), 'dateEnd': week.get('dateEnd'),
            'topPct': week.get('topPct'), 'topPctByLift': week.get('topPctByLift'),
            'sets': {key: 0 for key in ROLES}, 'rows': 0, 'tonnageKg': 0.0,
            'roles': {key: 0 for key in ('main', 'sbdVar', 'nonSbdVar', 'accessory')},
        })
        block_entry = per_block.setdefault(block_id, {
            'id': block_id,
            'name': (block_meta.get(block_id) or {}).get('nameEn'),
            'cycleType': (block_meta.get(block_id) or {}).get('cycleType'),
            'weeks': 0, 'sets': {key: 0 for key in ROLES}, 'rows': 0, 'tonnageKg': 0.0,
        })

        key = f"{row.get('week')}|{row.get('day')}|{row.get('seq')}"
        log = (logs or {}).get(key) if mode == 'log' else None
        role, count, tonnage = row_facts(row, log, mode)

        for bucket in (day_entry, week_entry, block_entry):
            bucket['sets'][role] += count
            bucket['rows'] += 1
            bucket['tonnageKg'] += tonnage
        day_entry['roles'][row.get('bucket')] += count
        week_entry['roles'][row.get('bucket')] += count
        cycle_sets[role] += count
        cycle_raw_roles[row.get('bucket')] = cycle_raw_roles.get(row.get('bucket'), 0) + count
        cycle_tonnage += tonnage

        code = row.get('lift')
        if code in per_lift:
            if role == 'main':
                per_lift[code]['main'] += count
            elif role == 'variation':
                per_lift[code]['variation'] += count
            per_lift[code]['tonnageKg'] += tonnage

    for entry in per_day.values():
        entry['sets']['total'] = sum(entry['sets'][key] for key in ROLES)
        entry['tonnageKg'] = round(entry['tonnageKg'], 4)
    for number, entry in per_week.items():
        entry['sets']['total'] = sum(entry['sets'][key] for key in ROLES)
        entry['tonnageKg'] = round(entry['tonnageKg'], 4)
        entry['sessionsWithRows'] = sum(1 for key in per_day if key[0] == number)
    for block_id, entry in per_block.items():
        entry['sets']['total'] = sum(entry['sets'][key] for key in ROLES)
        entry['tonnageKg'] = round(entry['tonnageKg'], 4)
        entry['weeks'] = sum(1 for week in plan['weeks'] if week['blockId'] == block_id)
        entry['sessions'] = sum(week.get('sessions') or 0 for week in plan['weeks'] if week['blockId'] == block_id)
    for code, entry in per_lift.items():
        entry['tonnageKg'] = round(entry['tonnageKg'], 4)

    return {
        'basis': {'sets': T_SETS, 'tonnage': T_TONNAGE, 'display': T_DISPLAY},
        'cycle': {
            'sets': {**cycle_sets, 'total': sum(cycle_sets[key] for key in ROLES)},
            'roles': cycle_raw_roles,
            'rows': len(rows),
            'tonnageKg': round(cycle_tonnage, 4),
            'sessions': plan['meta'].get('sessions'),
        },
        'perWeek': [per_week[number] for number in sorted(per_week)],
        'perDay': [per_day[key] for key in sorted(per_day)],
        'perBlock': [per_block[key] for key in sorted(per_block)],
        'perLift': per_lift,
    }


def day(plan, week, session_day, logs=None, mode='plan'):
    """One session's totals, or None when the plan has no rows there."""
    rows = [row for row in plan['workouts'] if row['week'] == week and row['day'] == session_day]
    if not rows:
        return None
    result = session_totals(rows, logs, mode)
    result.update({'week': week, 'day': session_day, 'date': rows[0].get('date')})
    return result


def display_chain(plan):
    """Prove the rounding chain: the headline and its parts are the same number."""
    data = totals(plan)
    cycle_t = round1(data['cycle']['tonnageKg'] / 1000)
    block_ts = [round2(entry['tonnageKg'] / 1000) for entry in data['perBlock']]
    week_ts = [round2(entry['tonnageKg'] / 1000) for entry in data['perWeek']]
    block_sum = round1(math.fsum(block_ts))
    week_sum = round1(math.fsum(week_ts))
    return {
        'cycleT': cycle_t,
        'blockT': block_ts,
        'weekT': week_ts,
        'blockSum': block_sum,
        'weekSum': week_sum,
        'blocksReconcile': block_sum == cycle_t,
        'weeksReconcile': week_sum == cycle_t,
    }
