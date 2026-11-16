"""Cycle completion, in one place (owner ruling: R5, 0.35).

Policy, deliberately simple and never capped at a different place:

- The denominator is only the prescribed sets whose session date has already arrived
  in Asia/Shanghai. A future session never lowers today's completion.
- A group counts as done up to `min(actual sets, planned sets)`. Logging more sets than
  prescribed is real work but it is reported as `extra`, never as more completion.
- An explicit zero (`sets=0`) is an intentional skip: it stays in the denominator, adds
  nothing, and marks its session `reviewed` so it is distinguishable from a session
  that was never opened.
- Main, SBD/non-SBD variations and accessory work are reported separately. They are never
  blended into one weighted number here; the review's attainment owns that weighting.
"""

from datetime import datetime

from .variations import classification, policy_of

CLASS_KEYS = ('main', 'var', 'acc')
BUCKETS = ('main', 'sbdVar', 'nonSbdVar', 'accessory')


def _today(today):
    if today is None:
        from ..calendar import SHANGHAI
        return datetime.now(SHANGHAI).date().isoformat()
    return today.isoformat() if hasattr(today, 'isoformat') else str(today)


def _class_of(bucket):
    return 'main' if bucket == 'main' else 'acc' if bucket == 'accessory' else 'var'


def completion(plan, logs=None, today=None, mode='log'):
    """Return the R5 completion block. `mode='plan'` ignores logs, as the plan view does."""
    if mode not in ('plan', 'log'):
        raise ValueError('mode must be plan or log')
    logs = logs or {} if mode == 'log' else {}
    as_of = _today(today)
    policy = policy_of(plan)
    planned = dict.fromkeys(BUCKETS, 0)
    actual = dict.fromkeys(BUCKETS, 0)
    credited = dict.fromkeys(CLASS_KEYS, 0)
    planned_by_class = dict.fromkeys(CLASS_KEYS, 0)
    extra = dict.fromkeys(CLASS_KEYS, 0)
    rows = []
    sessions = {}
    for row in plan['workouts']:
        bucket = classification(row, policy)[1]
        key = f"{row['week']}|{row['day']}|{row['seq']}"
        session_id = f"{row['week']}|{row['day']}"
        elapsed = row['date'] <= as_of
        log = logs.get(key) if mode == 'log' else None
        session = sessions.setdefault(session_id, {
            'week': row['week'], 'day': row['day'], 'date': row['date'],
            'elapsed': elapsed, 'planned': 0, 'done': 0, 'zero': False, 'touched': False,
        })
        if elapsed:
            planned[bucket] += row['sets']
            planned_by_class[_class_of(bucket)] += row['sets']
            session['planned'] += row['sets']
        if log is None:
            continue
        done = max(0, int(log['sets']))
        session['touched'] = True
        if done == 0:
            session['zero'] = True
        # Recorded sets are always reported raw; only the credit respects the calendar.
        actual[bucket] += done
        if not elapsed:
            rows.append({'key': key, 'bucket': bucket, 'planned': row['sets'], 'actual': done,
                         'counted': 0, 'ahead': True})
            continue
        counted = min(done, row['sets'])
        credited[_class_of(bucket)] += counted
        extra[_class_of(bucket)] += max(0, done - row['sets'])
        session['done'] += counted
        rows.append({'key': key, 'bucket': bucket, 'planned': row['sets'], 'actual': done,
                     'counted': counted, 'ahead': False})

    pct = {key: (credited[key] / planned_by_class[key] * 100) if planned_by_class[key] else None
           for key in CLASS_KEYS}
    reviewed = sorted(session_id for session_id, item in sessions.items() if item['elapsed'] and item['zero'])
    untouched = sorted(session_id for session_id, item in sessions.items()
                       if item['elapsed'] and not item['touched'])
    return {
        'policy': 'R5: elapsed planned sets only, min(actual, planned), three classes separate',
        'asOf': as_of,
        'classes': {key: {'planned': planned_by_class[key], 'credited': credited[key],
                          'extra': extra[key], 'pct': round(pct[key], 1) if pct[key] is not None else None}
                    for key in CLASS_KEYS},
        'main': round(pct['main'], 1) if pct['main'] is not None else None,
        'var': round(pct['var'], 1) if pct['var'] is not None else None,
        'acc': round(pct['acc'], 1) if pct['acc'] is not None else None,
        'planned': planned, 'actual': actual, 'credited': credited, 'extra': extra,
        'sessions': {'elapsed': sum(1 for item in sessions.values() if item['elapsed']),
                     'reviewed': len(reviewed), 'untouched': len(untouched),
                     'ahead': sum(1 for item in sessions.values() if not item['elapsed'] and item['touched'])},
        'reviewedSessions': reviewed, 'untouchedSessions': untouched,
        'rows': rows,
    }
