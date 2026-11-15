"""Competition/test-week attempt selection.

Opener 92.5%, second 100%, third 102.5% of the reference 1RM, each floored to
2.5 kg. The three suggested weights must be strictly increasing: when flooring
would put the third attempt on the second, the next 2.5 kg step is used instead
(owner ruling 2026-11-15: a tie is a bug unless it is labelled). A missed attempt
repeats the same weight; after a good lift the next attempt never decreases.
"""

import math

LIFTS = ('squat', 'bench', 'deadlift')
FACTORS = (0.925, 1.0, 1.025)
PROFILE_KEYS = {'squat': 'sq_1rm', 'bench': 'bp_1rm', 'deadlift': 'dl_1rm'}


def floor25(value):
    return math.floor(value / 2.5 + 1e-9) * 2.5


def ceil25(value):
    return math.ceil(value / 2.5 - 1e-9) * 2.5


def suggested(reference):
    values = [floor25(float(reference) * factor) for factor in FACTORS]
    for index in range(1, len(values)):
        if values[index] <= values[index - 1]:
            values[index] = ceil25(values[index - 1] + 2.5)
    return values


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