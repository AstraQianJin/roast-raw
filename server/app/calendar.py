from datetime import datetime
from zoneinfo import ZoneInfo

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
