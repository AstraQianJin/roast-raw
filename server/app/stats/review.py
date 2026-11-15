import copy
import hashlib
import json
import math
from datetime import date
from decimal import Decimal, localcontext

from . import engine
from .performance import performance
from .readiness import score_readiness
from .variations import classification


__all__ = ['build_review', 'bodyweight_progress']


def _finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _positive(value):
    return _finite(value) and value > 0


def bodyweight_progress(start, target, current):
    if not all(_positive(value) for value in (start, target, current)):
        return None
    # Decimal arithmetic keeps literal +/-1% maintenance boundaries inclusive.
    with localcontext() as context:
        context.prec = 40
        start, target, current = (Decimal(str(value)) for value in (start, target, current))
        if start == target:
            deviation = abs(current / start - 1) * 100
            score = Decimal(100) if deviation <= 1 else max(Decimal(0), 100 - 10 * (deviation - 1))
        else:
            score = (current - start) / (target - start) * 100
        result = float(score)
    return result if math.isfinite(result) else None


def _day(value):
    if type(value) is date:
        return value
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _key(row):
    return f"{row['week']}|{row['day']}|{row['seq']}"


def _identity(row):
    return {field: row.get(field) if row is not None else None
            for field in ('week', 'day', 'seq', 'date', 'movementId')}


def _logs(plan, logs):
    rows = {_key(row): row for row in plan['workouts']}
    order = {key: index for index, key in enumerate(rows)}
    return [{'key': key, **_identity(rows.get(key)), **copy.deepcopy(logs[key])}
            for key in sorted(logs, key=lambda key: (order.get(key, len(order)), key))]


def _weekly_totals(week):
    return copy.deepcopy({field: week[field]
                          for field in ('total', 'tonnageKg', 'roles', 'lifts', 'equivalent')})


def _planned_actual(plan, logs):
    policy = plan.get('prescription', {}).get('version')
    rows = []
    actual_logs = {}
    for row in plan['workouts']:
        key = _key(row)
        log = logs.get(key)
        rows.append({
            'key': key, **_identity(row),
            'movement': row['movement'], 'category': row['category'],
            'bucket': classification(row, policy)[1],
            'planned': {
                'sets': row['sets'], 'reps': row['reps'], 'loadKg': row['loadKg'],
                'rpe': row['targetRpe'], 'segments': copy.deepcopy(row['segments']),
                'tonnageKg': row['tonnageKg'],
            },
            'actual': copy.deepcopy(log),
        })
        # Only volume analysis receives zero logs: its missing-log default is planned volume.
        actual_logs[key] = log if log is not None else {'sets': 0, 'reps': 0, 'load': None}
    planned = engine.analyze(plan, mode='plan')['perWeek']
    actual = engine.analyze(plan, actual_logs, 'log')['perWeek']
    return {
        'rows': rows,
        'weeks': [{'n': prescribed['n'], 'kind': prescribed['kind'],
                   'dateStart': prescribed['dateStart'], 'dateEnd': prescribed['dateEnd'],
                   'planned': _weekly_totals(prescribed), 'actual': _weekly_totals(recorded)}
                  for prescribed, recorded in zip(planned, actual)],
    }


def _metrics(records, start, score_date):
    eligible = []
    bodyweights = []
    for index, record in enumerate(records):
        recorded = _day(record.get('date'))
        if recorded is None or not start <= recorded <= score_date:
            continue
        bodyweight = _positive(record.get('bodyweight'))
        bodyfat = record.get('bodyfat')
        measurements = record.get('measurements', {})
        measured = isinstance(measurements, dict) and any(_positive(value) for value in measurements.values())
        if bodyweight or (_finite(bodyfat) and 0 <= bodyfat <= 100) or measured:
            eligible.append((recorded, index, record))
        if bodyweight:
            bodyweights.append((recorded, index, record))
    profile_end = max(eligible, key=lambda item: item[:2])[2] if eligible else None
    latest = max(bodyweights, key=lambda item: item[:2])[2] if bodyweights else None
    current = {'value': latest['bodyweight'], 'date': latest['date']} if latest is not None else {'value': None, 'date': None}
    return copy.deepcopy(profile_end), current


def _readiness(records, score_date):
    eligible = []
    for index, record in enumerate(records):
        recorded = _day(record.get('date'))
        if recorded is not None and recorded <= score_date:
            eligible.append((recorded, record.get('updated_at') or '', index, record))
    eligible.sort(key=lambda item: item[:3])
    history = [item[3] for item in eligible]
    evaluations = {item[2]: score_readiness(item[3], history) for item in eligible}
    exported = [{**copy.deepcopy(record), 'evaluation': copy.deepcopy(evaluations.get(index))}
                for index, record in enumerate(records)]
    latest = copy.deepcopy(exported[eligible[-1][2]]) if eligible else None
    return exported, latest


def _main_performance(plan, logs):
    policy = plan.get('prescription', {}).get('version')
    rows = {}
    lifts = {}
    for row in plan['workouts']:
        _, bucket, lift, _ = classification(row, policy)
        if bucket == 'main' and lift in ('S', 'B', 'D'):
            rows[_key(row)] = row
            lifts[row['movementId']] = lift
    main_plan = {**plan, 'workouts': list(rows.values())}
    movements = performance(main_plan, logs)['movements']
    weekly = {lift: {} for lift in ('S', 'B', 'D')}
    for movement in movements:
        lift = lifts[movement['id']]
        for point in movement['weekly']:
            if point['value'] is None:
                continue
            row = rows[point['key']]
            rank = (point['value'], point['date'], row['seq'])
            previous = weekly[lift].get(point['n'])
            if previous is None or rank > previous[0]:
                weekly[lift][point['n']] = (rank, {**point, 'movementId': movement['id']})
    result = {}
    for lift in ('S', 'B', 'D'):
        points = [weekly[lift][week['n']][1] for week in plan['weeks'] if week['n'] in weekly[lift]]
        result[lift] = {
            'start': copy.deepcopy(points[0]) if points else None,
            'end': copy.deepcopy(points[-1]) if points else None,
            'change': engine.r1(points[-1]['value'] - points[0]['value']) if points else None,
        }
    return result


def build_review(source, exported_at, app_version, as_of):
    source = copy.deepcopy(source)
    plan, cycle = source['plan'], source['cycle']
    logs = source.get('logs', {})
    start, end, requested = (_day(value) for value in (cycle['start_date'], cycle['end_date'], as_of))
    if start is None or end is None or requested is None or end < start:
        raise ValueError('cycle dates and as_of must be valid YYYY-MM-DD dates with start_date <= end_date')
    score_date = min(requested, end)
    profile = plan['meta'].get('profile')
    metrics = source.get('body_metrics', [])
    profile_end, bodyweight = _metrics(metrics, start, score_date)
    baseline = profile.get('init_bw_kg') if isinstance(profile, dict) else None
    target = profile.get('target_bw_kg') if isinstance(profile, dict) else None
    progress = bodyweight_progress(baseline, target, bodyweight['value'])
    # A review judges the whole cycle, not today: the as-of date is the cycle end, so
    # every prescribed session is inside the R5 denominator even on an empty cycle.
    completion = copy.deepcopy(engine.analyze(plan, logs, 'log', today=plan['meta']['endDate'])['completion'])
    attained = engine.attainment(completion, goal=None, bodyweight=progress)
    attained['version'] = 'goal-bw-completion-v1'
    mode = None
    if _positive(baseline) and _positive(target):
        mode = 'maintenance' if baseline == target else 'cut' if target < baseline else 'bulk'
    attained['bodyweight_detail'] = {'start': baseline, 'target': target, 'current': bodyweight['value'],
                                    'date': bodyweight['date'], 'percent': progress, 'mode': mode}
    readiness, latest_readiness = _readiness(source.get('readiness', []), score_date)
    main = _main_performance(plan, logs)
    review = {
        'schema': 'RPL-Review-v1', 'exported_at': copy.deepcopy(exported_at),
        'app_version': copy.deepcopy(app_version), 'as_of': requested.isoformat(),
        'plan_id': plan['meta']['planId'], 'cycle': copy.deepcopy(cycle),
        'profile_start': copy.deepcopy(profile), 'profile_end': profile_end,
        'plan': copy.deepcopy(plan), 'logs': _logs(plan, logs),
        'body_metrics': copy.deepcopy(metrics),
        'readiness': {'records': readiness, 'legacy': copy.deepcopy(source.get('legacy_readiness', []))},
        'prescription_versions': copy.deepcopy(source.get('prescription_versions', [])),
        'journals': copy.deepcopy(source.get('journals', {'logs': [], 'records': []})),
        'questionnaire': copy.deepcopy(source.get('questionnaire')),
        'planned_vs_actual': _planned_actual(plan, logs),
        'completion': completion, 'attainment': attained,
        'e1rm': {'movements': copy.deepcopy(performance(plan, logs)['movements']), 'main': main},
        'end_state': {
            'score_date': score_date.isoformat(),
            'sbd': {lift: {'value': None, 'date': None, 'status': 'not_tested'} for lift in ('S', 'B', 'D')},
            'bodyweight': copy.deepcopy(bodyweight), 'readiness': latest_readiness,
            'e1rm': copy.deepcopy(main),
        },
        'next_outlook': None,
    }
    payload = json.dumps(review, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
    review['integrity'] = {'algorithm': 'SHA-256', 'review_sha256': hashlib.sha256(payload.encode('utf-8')).hexdigest()}
    return review
