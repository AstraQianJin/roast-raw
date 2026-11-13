"""Versioned variation prescriptions and approved experience parameters."""
import copy
import hashlib
import json
import math
from collections.abc import Mapping
from datetime import date as calendar_date

from . import classify as C
from . import engine
from . import prescription as P

POLICY = 'eight-variations-v1'
__all__ = ['POLICY', 'family', 'classification', 'catalogue', 'defaults',
           'validate_references', 'recalculate', 'digest', 'changes', 'system_load']

# name family -> lift, transfer, conservative reference kg, total-system load
_FAMILIES = {
    'Low-bar Squat': ('S', .90, 120, False),
    'Wide-grip Bench': ('B', .90, 90, False),
    'Sumo Deadlift': ('D', .85, 120, False),
    'Power Clean': ('D', .15, 70, False),
    'OHP': ('B', .35, 60, False),
    'Pull-Up': ('D', .10, 100, True),
    'Dip': ('B', .60, 105, True),
    'Bent-Over Barbell Row': ('D', .25, 90, False),
}
_ALIASES = {'Weighted Pull-Up': 'Pull-Up', 'Weighted Dip': 'Dip'}
_PRIMARY = frozenset(('Low-bar Squat', 'Wide-grip Bench', 'Sumo Deadlift'))
_RTS = (None, 100, 95.5, 92.2, 89.2, 86.3, 83.7, 81.1, 78.6, 76.2,
        74, 72, 70, 68.3, 66.7, 65.2, 63.8, 62.5, 61.2, 60, 58.8)
_PRESCRIBED = 'Prescribed percentage'
_ESTIMATED = 'Legacy RTS reps/RPE estimate'


def _name(row):
    return str(row.get('movement') or row.get('name_en') or
               row.get('nameEn') or row.get('name') or '').strip()


def family(row):
    """Return a fresh approved family descriptor, without collapsing IDs."""
    name = _name(row)
    values = _FAMILIES.get(_ALIASES.get(name, name))
    if values is None:
        return None
    return dict(zip(('lift', 'transfer', 'default', 'system'), values))


def _entry(row):
    name, category = _name(row), C.row_category(row)
    identity = row.get('movementId') or row.get('id')
    if identity is None and category and name:
        identity = f'{category}|{name.casefold()}'
    return next((entry for entry in engine.library()['movements']
                 if entry['id'] == identity), None)


def classification(row, policy=None):
    """Return (role, bucket, lift, level), retaining legacy rules by default."""
    name = _name(row)
    approved = family(row) if policy == POLICY else None
    if approved is not None:
        level = 'primary_var' if name in _PRIMARY else 'secondary_var'
        return 'variation', 'sbdVar', approved['lift'], level
    entry = _entry(row)
    evidence = {'category': C.row_category(row)}
    return (C.movement_role(name, evidence), C.movement_bucket(name, evidence),
            entry.get('lift') if entry is not None else C.movement_lift(name, evidence),
            entry.get('level') if entry is not None else C.movement_level(name))


def catalogue():
    """Group allowed, existing variation references by S/B/D; never invent IDs."""
    result = {lift: [] for lift in ('S', 'B', 'D')}
    for entry in engine.library()['movements']:
        if entry.get('plan_allowed') is not True:
            continue
        approved = family(entry)
        category = C.row_category(entry)
        if not (approved or '.Vari.' in category or
                entry.get('level') in ('primary_var', 'secondary_var')):
            continue
        lift = approved['lift'] if approved else entry.get('lift')
        if lift not in result:
            lift = category[:1]
        if lift not in result:
            continue
        result[lift].append({
            'id': entry['id'], 'name': _name(entry), 'lift': lift,
            'system': approved['system'] if approved else False,
            'default': approved['default'] if approved else None,
            'transfer': approved['transfer'] if approved else None,
        })
    for entries in result.values():
        entries.sort(key=lambda entry: (entry['name'].casefold(), entry['id']))
    return result


def defaults():
    """A distinct reference for every catalogue ID, including explicit nulls."""
    return {entry['id']: entry['default']
            for entries in catalogue().values() for entry in entries}


def _finite(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_references(references):
    """Return an independent map; invalid/missing/unknown IDs are ValueError(key)."""
    if not isinstance(references, Mapping):
        raise ValueError('references')
    known = defaults()
    for key in references:
        if key not in known:
            raise ValueError(key)
    for key in known:
        if key not in references:
            raise ValueError(key)
        value = references[key]
        if value is not None and (not _finite(value) or value <= 0):
            raise ValueError(key)
    return copy.deepcopy(dict(references))


def _base(plan):
    if not isinstance(plan, dict):
        raise ValueError('plan')
    if 'prescription' not in plan:
        return plan
    prior = plan['prescription']
    if not isinstance(prior, dict) or prior.get('version') != POLICY:
        raise ValueError('prescription.version')
    base = prior.get('basePlan')
    if not isinstance(base, dict) or 'prescription' in base:
        raise ValueError('prescription.basePlan')
    return base


def _key(row):
    return f"{row['week']}|{row['day']}|{row['seq']}"


def _reject(row, reason):
    raise ValueError(f"{_key(row)} ({_name(row)}, {row.get('date')}): {reason}")


def _segment(row):
    segments = row.get('segments')
    if not isinstance(segments, list) or len(segments) != 1:
        _reject(row, 'exactly one segment is supported for approved families')
    segment = segments[0]
    if (not isinstance(segment, dict) or segment.get('unit') or
            segment.get('sets') != row['sets'] or segment.get('reps') != row['reps']):
        _reject(row, 'segment must preserve integral row sets/reps without timed units')
    if (not isinstance(row['sets'], int) or isinstance(row['sets'], bool) or row['sets'] < 0 or
            not isinstance(row['reps'], int) or isinstance(row['reps'], bool) or row['reps'] <= 0):
        _reject(row, 'invalid sets/reps')
    return segment


def _percentage(row):
    segment = _segment(row)
    if segment.get('pct') is not None:
        percent = segment['pct']
    elif row.get('pct') is not None:
        value = row['pct']
        if not _finite(value) or value <= 0:
            _reject(row, 'invalid row percentage')
        percent = value * 100
    else:
        rpe = row.get('targetRpe')
        if not _finite(rpe):
            _reject(row, 'missing or invalid percentage/RPE for legacy RTS estimate')
        index = int(round(row['reps'] + (10.0 - rpe)))
        if index < 1:
            _reject(row, 'reps/RPE is outside the legacy RTS estimate')
        return int(round(_RTS[min(index, 20)])), _ESTIMATED
    if not _finite(percent) or percent <= 0:
        _reject(row, 'invalid segment percentage')
    return percent, _PRESCRIBED


def _display(value):
    return str(value)[:-2] if str(value).endswith('.0') else str(value)


def recalculate(plan, references):
    """Rebuild approved single-segment rows from the immutable legacy base."""
    refs = validate_references(references)
    base = _base(plan)
    revised = copy.deepcopy(base)
    for row in revised['workouts']:
        approved = family(row)
        if approved is None:
            continue
        identity = row.get('movementId')
        entry = _entry(row)
        if (identity not in refs or entry is None or entry.get('plan_allowed') is not True or
                entry['name_en'] != _name(row) or entry['category'] != C.row_category(row)):
            _reject(row, f'unknown or mismatched movementId {identity}')
        reference = refs[identity]
        if reference is None:
            _reject(row, f'missing reference {identity}')
        original = _segment(row)
        percent, _ = _percentage(row)
        try:
            raw_load = reference * (percent / 100)
            if not _finite(raw_load):
                _reject(row, 'non-finite recalculated load')
            load = P.mround(raw_load, 2.5)
        except OverflowError:
            _reject(row, 'non-finite recalculated load')
        technique = ' technique' if original.get('label') == 'TECH' else ''
        amrap = '+' if original.get('amrap') else ''
        rx = (f"{row['sets']}×{row['reps']} @ {_display(percent)}% @ "
              f'{_display(load)} kg{technique}{amrap}')
        row['role'], row['bucket'], row['lift'], row['level'] = classification(row, POLICY)
        row.update(pct=percent / 100, loadRaw=raw_load, loadKg=load,
                   rxRaw=rx, rxEn=rx, systemLoad=approved['system'])
        segments = P.parse_segments({
            'rxRaw': rx, 'load': load, 'pct': row['pct'],
            'sets': row['sets'], 'reps': row['reps'], 'notes': row.get('notes', ''),
            'bucket': row['bucket'], 'bwAnchor': False, 'systemLoad': approved['system'],
        })
        if len(segments) != 1 or segments[0].get('load') != load:
            _reject(row, 'system-load parser must retain prescribed total load')
        # Keep the prescribed percent, never infer it backwards from rounded kg.
        segments[0]['pct'] = percent
        row['segments'] = segments
        row['tonnageKg'] = round(sum((P.row_load(s, row['role']) or 0) * s['sets'] * s['reps']
                                     for s in segments), 1)
    for week in revised['weeks']:
        week['tonnageKg'] = round(sum(row['tonnageKg'] for row in revised['workouts']
                                      if row['week'] == week['n']), 1)
    revised['meta']['cycleTonnageKg'] = round(sum(row['tonnageKg'] for row in revised['workouts']), 1)
    revised['meta']['auxSets'] = sum(row['sets'] for row in revised['workouts']
                                     if row['bucket'] == 'accessory')
    revised['meta']['tonnageBasis'] = (
        'Prescribed segment loads rounded to 0.5 kg (main) / 2.5 kg (variation); '
        'pull-ups and dips include bodyweight in total system load; accessories excluded.')
    revised['prescription'] = {'version': POLICY, 'references': refs, 'basePlan': copy.deepcopy(base)}
    return revised


def digest(plan):
    """Canonical JSON SHA256, rejecting NaN and infinity."""
    payload = json.dumps(plan, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _rows(plan):
    result = {}
    for row in plan['workouts']:
        key = _key(row)
        if key in result:
            _reject(row, 'duplicate row key')
        result[key] = row
    return result


def changes(before, after):
    """Changed rows, with percentage provenance from the original base plan."""
    old, new = _rows(before), _rows(after)
    if old.keys() != new.keys():
        raise ValueError(next(iter(old.keys() ^ new.keys())))
    base = _rows(_base(after))
    policy_plan = after if 'prescription' in after else before
    refs = policy_plan.get('prescription', {}).get('references', {})
    result = []
    for key, row in new.items():
        previous = old[key]
        approved = family(row)
        if previous == row or approved is None:
            continue
        if key not in base:
            _reject(row, 'missing base row')
        percent, basis = _percentage(base[key])
        result.append({
            'key': key, 'movement': row['movement'], 'date': row['date'],
            'sets': row['sets'], 'reps': row['reps'], 'targetRpe': row.get('targetRpe'),
            'oldLoad': previous.get('loadKg'), 'newLoad': row.get('loadKg'),
            'oldRx': previous['rxRaw'], 'newRx': row['rxRaw'],
            'basis': basis if 'prescription' in after else 'Original legacy prescription',
            'reference': refs.get(row['movementId']) if 'prescription' in after else None,
            'percent': percent, 'system': approved['system'],
        })
    return result


def system_load(load, date, metrics):
    """Resolve total mass versus same-day/closest-past bodyweight, never future."""
    if load is not None and (not _finite(load) or load < 0):
        raise ValueError('load')
    on_date = calendar_date.fromisoformat(date)
    prior = []
    for record in metrics or []:
        recorded = calendar_date.fromisoformat(record['date'])
        if recorded > on_date or record.get('bodyweight') is None:
            continue
        bodyweight = record['bodyweight']
        if not _finite(bodyweight) or bodyweight <= 0:
            raise ValueError('bodyweight')
        prior.append((recorded, record))
    record = max(prior, key=lambda item: item[0])[1] if prior else None
    bodyweight = record['bodyweight'] if record is not None else None
    adjustment = load - bodyweight if load is not None and bodyweight is not None else None
    kind = ('unknown' if adjustment is None else 'assisted' if adjustment < 0 else
            'weighted' if adjustment > 0 else 'bodyweight')
    return {'total': load, 'bodyweight': bodyweight,
            'bodyweightDate': record['date'] if record is not None else None,
            'adjustment': adjustment, 'kind': kind}
