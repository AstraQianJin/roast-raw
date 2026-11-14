"""Competition/test-week attempt selection.

Opener 92.5%, second 100%, third 102.5% of the reference 1RM, each floored to
2.5 kg. A missed attempt repeats the same weight; after a good lift the next
attempt never decreases (at least +2.5 kg over the previous good attempt).
"""

import math

LIFTS = ('squat', 'bench', 'deadlift')
FACTORS = (0.925, 1.0, 1.025)
PROFILE_KEYS = {'squat': 'sq_1rm', 'bench': 'bp_1rm', 'deadlift': 'dl_1rm'}


def floor25(value):
    return math.floor(value / 2.5 + 1e-9) * 2.5


def suggested(reference):
    return [floor25(reference * factor) for factor in FACTORS]


def references(questionnaire, plan):
    sbd = ((questionnaire or {}).get('payload') or {}).get('level', {}).get('sbd1rm') or {}
    profile = (plan.get('meta') or {}).get('profile') or {}
    result = {}
    for lift in LIFTS:
        value = sbd.get(lift)
        source = 'questionnaire'
        if not isinstance(value, (int, float)) or value <= 0:
            value = profile.get(PROFILE_KEYS[lift])
            source = 'plan-profile'
        if isinstance(value, (int, float)) and value > 0:
            result[lift] = {'reference': float(value), 'source': source}
        else:
            result[lift] = {'reference': None, 'source': None}
    return result


def next_attempt(reference, previous_load, previous_result, attempt_number):
    """Suggested weight for attempt_number (1-based) given the previous attempt."""
    base = suggested(reference)[min(attempt_number, 3) - 1]
    if previous_result == 'miss':
        return float(previous_load)
    if previous_result == 'good':
        return max(base, floor25(previous_load + 2.5))
    return base


def competition_info(questionnaire, plan):
    goal = ((questionnaire or {}).get('payload') or {}).get('goal') or {}
    schedule = ((questionnaire or {}).get('payload') or {}).get('schedule') or {}
    test_plan = plan.get('testPlan') or {}
    date = schedule.get('competitionDate') or (test_plan.get('dates') or {}).get('sbd')
    is_competition = goal.get('type') == 'competition' or bool(schedule.get('competitionDate'))
    return {'competition': is_competition, 'date': date,
            'name': ((questionnaire or {}).get('payload') or {}).get('outlook', {}).get('competitionName'),
            'tests': test_plan.get('tests') or [], 'testDates': test_plan.get('dates') or {}}