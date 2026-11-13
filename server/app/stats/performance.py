from . import engine
from .variations import family


def estimate(row, log):
    if log is None or log.get('sets', 0) <= 0 or log.get('load') is None:
        return None
    if any(segment.get('unit') for segment in row.get('segments', [])):
        return None
    reps, load = log.get('reps'), log['load']
    if reps is None or not 1 <= reps <= 10:
        return None
    if reps == 1:
        return {'value': load, 'estimated': False, 'method': 'Actual single'}
    if row['movement'] == 'Power Clean':
        return None
    return {'value': engine.r1(load * (1 + reps / 30)),
            'estimated': True, 'method': 'Epley estimate'}


def performance(plan, logs):
    logs = logs or {}
    library = {entry['id']: entry for entry in engine.library()['movements']}
    movements, best = {}, {}
    for row in plan['workouts']:
        identity = row['movementId']
        if identity not in movements:
            approved = family(row)
            entry = library.get(identity, {})
            movements[identity] = {
                'id': identity, 'name': row['movement'],
                'lift': approved['lift'] if approved else entry.get('lift'),
                'system': approved['system'] if approved else False,
                'weekly': [],
            }
        key = f"{row['week']}|{row['day']}|{row['seq']}"
        log = logs.get(key)
        observation = estimate(row, log)
        if observation is None:
            continue
        slot = (identity, row['week'])
        rank = (observation['value'], row['date'], row['seq'])
        if slot not in best or rank > best[slot][0]:
            best[slot] = (rank, {
                **observation, 'date': row['date'], 'key': key,
                'load': log['load'], 'reps': log['reps'], 'rpe': log.get('rpe'),
            })
    for movement in movements.values():
        for week in plan['weeks']:
            chosen = best.get((movement['id'], week['n']))
            fields = chosen[1] if chosen else dict.fromkeys(
                ('value', 'estimated', 'method', 'date', 'key', 'load', 'reps', 'rpe'))
            movement['weekly'].append({'n': week['n'], **fields})
    return {'movements': list(movements.values())}
