import json
import math
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path

from . import classify as C

DATA = Path(__file__).resolve().parents[3] / 'data'
TIER_PRIMARY = 0.8
TIER_SECONDARY = 0.3


@lru_cache(maxsize=1)
def library():
    return json.loads((DATA / 'movements.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def ranges():
    return json.loads((DATA / 'ranges.json').read_text(encoding='utf-8'))


def r1(value):
    # Four-decimal cleanup preserves legacy half-up boundaries after float summation.
    return float(Decimal(str(round(float(value), 4))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def resolve(movement, category):
    key = f'{category}|{movement.casefold()}'
    hit = next((entry for entry in library()['movements'] if entry['id'] == key), None)
    if hit is not None and hit['plan_allowed'] and hit['coef16']:
        return hit, 'exact'
    return None, 'unmapped'


def leaf_tiers(leaf):
    maximum = max(leaf.values(), default=0)
    return {key: (0 if not maximum or value <= 0 else
                  1 if value >= maximum * TIER_PRIMARY - 1e-9 else
                  2 if value >= maximum * TIER_SECONDARY - 1e-9 else 0)
            for key, value in leaf.items()}, maximum


def _blank():
    return {
        'kg': 0.0, 'sets': 0,
        'roles': {key: 0 for key in ('main', 'sbdVar', 'nonSbdVar', 'accessory')},
        'lifts': {key: {'main': 0, 'var': 0} for key in ('S', 'B', 'D')},
        'equivalent': {key: {'main': 0.0, 'var': 0.0, 'unknown': 0} for key in ('S', 'B', 'D')},
        'groups': {key: 0 for key in C.MUSCLE_GROUPS},
        'groupsWeighted': {key: 0.0 for key in C.MUSCLE_GROUPS},
        **{field: {key: 0.0 for key in library()['leaf_order']}
           for field in ('leaves', 'leavesWeighted', 'primaryWeighted', 'secondaryWeighted')},
    }


def _add(target, source):
    for key in ('kg', 'sets'):
        target[key] += source[key]
    for field in ('roles', 'groups', 'groupsWeighted', 'leaves', 'leavesWeighted', 'primaryWeighted', 'secondaryWeighted'):
        for key in target[field]:
            target[field][key] += source[field][key]
    for code in target['lifts']:
        for kind in ('main', 'var'):
            target['lifts'][code][kind] += source['lifts'][code][kind]
        for kind in ('main', 'var', 'unknown'):
            target['equivalent'][code][kind] += source['equivalent'][code][kind]


def row_volume(row, log=None, policy=None):
    result = _blank()
    movement, category = row['movement'], row['category']
    from .variations import POLICY, classification, family
    _, bucket, lift, _ = classification(row, policy)
    entry, status = resolve(movement, category)
    if entry is None:
        return result, [f'{movement} ({status})']
    sets = log['sets'] if log is not None else row['sets']
    result['sets'] = sets
    result['roles'][bucket] = sets
    if bucket in ('main', 'sbdVar'):
        code = lift
        if code in result['lifts']:
            result['lifts'][code]['main' if bucket == 'main' else 'var'] = sets
            approved = family(row)
            if bucket == 'main':
                result['equivalent'][code]['main'] = sets
            elif policy != POLICY:
                result['equivalent'][code]['var'] = sets
            elif approved is not None:
                result['equivalent'][code]['var'] = sets * approved['transfer']
            else:
                result['equivalent'][code]['unknown'] = sets
    group = row['group']
    if group is not None:
        result['groups'][group] = sets
    for key in C.MUSCLE_GROUPS:
        result['groupsWeighted'][key] = sets * entry['coef6'][key]
    tiers, _ = leaf_tiers(entry['coef16'])
    for key, coef in entry['coef16'].items():
        result['leavesWeighted'][key] = sets * coef
        if tiers[key] == 1:
            result['leaves'][key] = sets
            result['primaryWeighted'][key] = sets * coef
        elif tiers[key] == 2:
            result['secondaryWeighted'][key] = sets * coef
    if log is None:
        result['kg'] = row['tonnageKg']
    elif bucket != 'accessory' and log['load'] is not None:
        result['kg'] = log['load'] * log['reps'] * sets
    return result, []


def _equivalent(volume):
    return {code: {**lift, 'total': r1(lift['main'] + lift['var'])}
            for code, lift in volume['equivalent'].items()}


def _leaves(volume):
    return {key: {'w': r1(volume['leavesWeighted'][key]), 'd': int(volume['leaves'][key]),
                  'raw': volume['leavesWeighted'][key],
                  'primaryWeighted': volume['primaryWeighted'][key],
                  'secondaryWeighted': volume['secondaryWeighted'][key]}
            for key in volume['leaves']}


def analyze(plan, logs=None, mode='plan'):
    if mode not in ('plan', 'log'):
        raise ValueError('mode must be plan or log')
    logs = logs or {}
    policy = plan.get('prescription', {}).get('version')
    from .variations import classification
    cycle = _blank()
    per_week = []
    unresolved = set()
    actual = dict(cycle['roles'])
    planned = dict(cycle['roles'])
    planned_peak = 0.0
    for meta in plan['weeks']:
        volume = _blank()
        planned_volume = _blank()
        for row in (row for row in plan['workouts'] if row['week'] == meta['n']):
            key = f"{row['week']}|{row['day']}|{row['seq']}"
            log = logs.get(key)
            contribution, errors = row_volume(row, log if mode == 'log' else None, policy)
            unresolved.update(errors)
            _add(volume, contribution)
            _add(planned_volume, contribution if mode == 'plan' else row_volume(row, policy=policy)[0])
            _, bucket, _, _ = classification(row, policy)
            planned[bucket] += row['sets']
            if log is not None:
                actual[bucket] += log['sets']
        _add(cycle, volume)
        planned_peak = max(planned_peak, *planned_volume['leavesWeighted'].values())
        per_week.append({
            **{key: meta[key] for key in ('n', 'kind', 'blockId', 'dateStart', 'dateEnd', 'days', 'sessions')},
            'total': volume['sets'], 'roles': volume['roles'], 'lifts': volume['lifts'], 'equivalent': _equivalent(volume),
            'groups': {key: {'d': volume['groups'][key], 'w': volume['groupsWeighted'][key]}
                       for key in C.MUSCLE_GROUPS},
            'leaves': _leaves(volume), 'tonnageKg': r1(volume['kg']),
            'topPct': meta.get('topPct'), 'topPctByLift': meta.get('topPctByLift'),
        })
    for week in per_week:
        for leaf in week['leaves'].values():
            leaf['heat'] = {}
            for label, field in (('Both', 'raw'), ('Primary', 'primaryWeighted'), ('Secondary', 'secondaryWeighted')):
                share = leaf[field] / planned_peak if planned_peak else 0
                leaf['heat'][label] = {
                    'band': min(4, math.ceil(share * 4)) if share > 0 else 0,
                    'percent': min(100, max(0, share * 100)),
                }
    completion = {
        'planned': planned, 'actual': actual,
        'main': _pct(actual['main'], planned['main']),
        'var': _pct(actual['sbdVar'] + actual['nonSbdVar'], planned['sbdVar'] + planned['nonSbdVar']),
        'acc': _pct(actual['accessory'], planned['accessory']),
    }
    return {
        'schema': 'RPL-Analysis-v1', 'mode': mode, 'weeks': len(plan['weeks']),
        'deload': [week['n'] for week in plan['weeks'] if week['kind'] == 'deload'],
        'test': [week['n'] for week in plan['weeks'] if week['kind'] == 'test'],
        'perWeek': per_week,
        'heatScale': {'maximum': planned_peak, 'basis': 'Highest planned weekly muscle-weighted volume across this cycle'},
        'cycle': {
            'total': cycle['sets'], 'roles': cycle['roles'], 'lifts': cycle['lifts'], 'equivalent': _equivalent(cycle),
            'groups': {key: {'d': cycle['groups'][key], 'w': r1(cycle['groupsWeighted'][key])}
                       for key in C.MUSCLE_GROUPS},
            'leaves': _leaves(cycle), 'tonnageKg': r1(cycle['kg']),
            'auxSets': cycle['roles']['accessory'], 'sessions': plan['meta']['sessions'],
        },
        'completion': completion, 'ranges': ranges(), 'leafOrder': library()['leaf_order'],
        'groups': C.MUSCLE_GROUPS, 'unresolved': sorted(unresolved),
        'tonnageBasis': 'Prescribed segment loads; logged rows estimate tonnage from the last working set.' if mode == 'log' else plan['meta']['tonnageBasis'],
    }


def _pct(actual, planned):
    return r1(actual / planned * 100) if planned else None


def attainment(completion, goal=None, bodyweight=None):
    comp = None
    if all(completion.get(key) is not None for key in ('main', 'var', 'acc')):
        comp = 0.60 * completion['main'] + 0.25 * completion['var'] + 0.15 * completion['acc']
    composite = None if any(value is None for value in (goal, bodyweight, comp)) else 0.40 * goal + 0.40 * bodyweight + 0.20 * comp
    return {'goal': goal, 'bodyweight': bodyweight, 'completion': comp,
            'composite': r1(composite) if composite is not None else None,
            'weights': {'goal': 0.40, 'bodyweight': 0.40, 'completion': 0.20},
            'completion_weights': {'main': 0.60, 'var': 0.25, 'acc': 0.15}, 'capped': False}
