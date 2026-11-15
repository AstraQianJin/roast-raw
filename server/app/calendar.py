from datetime import datetime
from zoneinfo import ZoneInfo

from .stats.totals import session_totals

SHANGHAI = ZoneInfo('Asia/Shanghai')


def calendar_state(plan, logs, now=None):
    instant = now or datetime.now(SHANGHAI)
    if instant.tzinfo is None:
        raise ValueError('Calendar requires a timezone-aware datetime')
    today = instant.astimezone(SHANGHAI).date().isoformat()
    sessions = sorted({(row['date'], row['week'], row['day']) for row in plan['workouts']})
    current = next((session for session in sessions if session[0] == today), None)
    following = next((session for session in sessions if session[0] > today), None)
    week = next((week['n'] for week in plan['weeks'] if week['dateStart'] <= today <= week['dateEnd']), None)
    rows = [row for row in plan['workouts'] if row['date'] == today]
    if today < plan['meta']['startDate']:
        status = 'upcoming'
    elif today > plan['meta']['endDate']:
        status = 'ended'
    elif current:
        status = 'training'
    else:
        status = 'rest'
    states = {}
    for date, week_number, day in sessions:
        planned = [row for row in plan['workouts'] if row['week'] == week_number and row['day'] == day]
        done = all((logs.get(f"{row['week']}|{row['day']}|{row['seq']}") or {}).get('sets', 0) >= row['sets'] for row in planned)
        states[f'{week_number}|{day}'] = 'completed' if done else 'incomplete' if date < today else 'scheduled'
    return {'date': today, 'timezone': 'Asia/Shanghai', 'status': status, 'week': week,
            'day': current[2] if current else None, 'rows': rows, 'sessionStates': states,
            'nextSession': {'date': following[0], 'week': following[1], 'day': following[2]} if following else None}


def _session_status(planned, session_logs, date, today):
    """One session, one fact: actual sets decide, then whether the day has arrived.

    A logged set counts only when its actual sets are above zero; an explicit zero is a
    deliberate skip and is kept apart from a day nobody opened.
    """
    prescribed = session_totals(planned)['sets']['total']
    actual = 0
    touched = False
    for row in planned:
        entry = session_logs.get(f"{row['week']}|{row['day']}|{row['seq']}") or {}
        if 'sets' in entry and entry.get('sets') is not None:
            actual += max(0, int(entry['sets']))
            if int(entry['sets']) == 0:
                touched = True
            elif int(entry['sets']) > 0:
                touched = True
    if actual > 0:
        return 'completed', prescribed, actual
    if touched:
        return 'skipped', prescribed, actual
    return ('missed' if date < today else 'planned'), prescribed, actual


def calendar_days(plans, logs_by_cycle, date_from, date_to, today=None):
    """Sessions in a half-open date range, across archived and active cycles.

    `plans` is a list of plan documents, `logs_by_cycle` maps planId to its log dict.
    The range is inclusive of `date_from` and exclusive of `date_to`, so adjacent
    requests never show the same day twice. `today` is an ISO date in Asia/Shanghai.
    """
    today = today or datetime.now(SHANGHAI).date().isoformat()
    if date_from >= date_to:
        raise ValueError('The range end must come after its start')
    by_cycle = {plan['meta']['planId']: plan for plan in plans}
    picked = {}
    for plan in plans:
        cycle = plan['meta']['planId']
        for row in plan['workouts']:
            date = row['date']
            if not (date_from <= date < date_to):
                continue
            picked.setdefault((date, cycle, row['week'], row['day']), []).append(row)
    days = []
    for (date, cycle, week_number, day), rows in sorted(picked.items()):
        plan = by_cycle[cycle]
        day_meta = next((item for item in plan.get('days', []) if item['id'] == day), {})
        week_meta = next((item for item in plan['weeks'] if item['n'] == week_number), {})
        block = next((item for item in plan.get('blocks', []) if item['id'] == week_meta.get('blockId')), {})
        status, prescribed, actual = _session_status(rows, logs_by_cycle.get(cycle) or {}, date, today)
        main = [row for row in rows if row.get('bucket') == 'main' or row.get('role') == 'main']
        top = max((row.get('loadKg') or 0) for row in rows) if rows else 0
        days.append({
            'date': date,
            'cycleId': cycle,
            'week': week_number,
            'day': day,
            'title': day_meta.get('titleEn') or f'DAY {day}',
            'block': block.get('nameEn') or week_meta.get('blockName') or '',
            'kind': week_meta.get('kind') or 'training',
            'prescribedSets': prescribed,
            'loggedSets': actual,
            'rowCount': len(rows),
            'lifts': sorted({row.get('lift') for row in main if row.get('lift')}),
            'topLoadKg': top if top else None,
            'status': status,
            'rows': [{
                'seq': row['seq'],
                'movement': row.get('nameEn') or row.get('movement') or '',
                'movementId': row.get('movementId'),
                'sets': row.get('sets'),
                'reps': row.get('reps'),
                'loadKg': row.get('loadKg'),
                'bucket': row.get('bucket'),
            } for row in rows],
        })
    return {'from': date_from, 'to': date_to, 'timezone': 'Asia/Shanghai',
            'today': today, 'sessions': len(days), 'days': days,
            # The client needs the covered spans to tell a gap inside a cycle (REST) from a
            # date no cycle reaches (blank). Without them every empty cell would read as rest.
            'cycles': [{'id': plan['meta']['planId'], 'start': plan['meta']['startDate'],
                        'end': plan['meta']['endDate']} for plan in plans]}

