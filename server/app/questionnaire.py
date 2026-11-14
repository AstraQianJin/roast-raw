import math
import re
from datetime import date

from .validation import Reject, issue

SCHEMA_VERSION = 'RR-Questionnaire-v1'
FILE = 'questionnaire'
VARIATION_IDS = (
    'S.Main|low-bar squat', 'B.Vari.Start|wide-grip bench', 'D.Main|sumo deadlift',
    'D.Vari.Power|power clean', 'B.Delts|ohp', 'D.Lats|pull-up', 'B.Triceps|dip',
    'SBD.UpperBack|bent-over barbell row',
)
STICKING = {
    'squat': ('bottom', 'midrange', 'lockout', 'forward-lean', 'knee-valgus', 'slow-ascent'),
    'bench': ('chest', 'midrange', 'lockout', 'shoulder-discomfort', 'elbow-discomfort', 'wrist-discomfort'),
    'deadlift': ('off-floor', 'below-knee', 'lockout', 'grip', 'back', 'hips'),
}
WEAK_MUSCLES = ('chest', 'shoulders', 'back', 'legs', 'arms', 'core', 'calves')
TEST_GROUPS = ('sbd', 'primary-variations', 'secondary-variations', 'five-km')
EFFORT_LEVELS = ('all-in', 'low-stress', 'moderate', 'high-stress')
RISK_LEVELS = ('aggressive', 'steady', 'conservative')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def skeleton():
    return {
        'schemaVersion': SCHEMA_VERSION,
        'goal': {'type': None},
        'schedule': {'startDate': None, 'competitionDate': None, 'testDates': [],
                     'trainingDaysPerWeek': None, 'sessionMinutes': None},
        'personal': {'age': None, 'sex': None, 'heightCm': None, 'bodyweightKg': None,
                     'trainingYears': None, 'equipment': None, 'activityLevel': None},
        'level': {'sbd1rm': {'squat': None, 'bench': None, 'deadlift': None},
                  'oneRmSource': None, 'recentPrs': None,
                  'variationPrs': {movement: None for movement in VARIATION_IDS},
                  'fiveKm': {'timeSeconds': None, 'date': None, 'conditions': None}},
        'limits': {'squat': [], 'bench': [], 'deadlift': [], 'weakMuscles': [],
                   'technique': None, 'injuries': None, 'surgeries': None,
                   'jointPain': None, 'mobility': None},
        'recovery': {'sleepHours': None, 'sleepQuality': None, 'stressLevel': None,
                     'proteinSufficient': None, 'caloriesSufficient': None,
                     'bodyFatPercent': None, 'otherSports': None},
        'outlook': {'targetBodyweightKg': None, 'weightDirection': None, 'sbdFocus': [],
                    'targets': {'squat': None, 'bench': None, 'deadlift': None, 'total': None},
                    'variationTargets': {movement: None for movement in VARIATION_IDS},
                    'fiveKmTargetSeconds': None, 'consistencyGoal': None, 'effortLevel': None,
                    'riskPreference': None, 'competitionName': None, 'weightClass': None,
                    'targetTotalKg': None, 'keepMovements': [], 'avoidMovements': [],
                    'testGroups': []},
        'notes': None,
    }


def _number(value, low, high, field, errors, integer=False):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        errors.append(issue(FILE, field, 'a finite number or null', got=value))
        return
    if integer and not isinstance(value, int):
        errors.append(issue(FILE, field, 'an integer or null', got=value))
        return
    if not low <= value <= high:
        errors.append(issue(FILE, field, f'a number between {low} and {high}', got=value))


def _text(value, limit, field, errors):
    if value is None:
        return
    if not isinstance(value, str) or len(value) > limit:
        errors.append(issue(FILE, field, f'a string of at most {limit} characters or null', got=value))


def _enum(value, choices, field, errors):
    if value is None:
        return
    if value not in choices:
        errors.append(issue(FILE, field, f'one of {list(choices)} or null', got=value))


def _date(value, field, errors):
    if value is None:
        return
    if not isinstance(value, str) or not DATE_RE.match(value):
        errors.append(issue(FILE, field, 'a YYYY-MM-DD date or null', got=value))
        return
    try:
        date.fromisoformat(value)
    except ValueError:
        errors.append(issue(FILE, field, 'a real calendar date', got=value))


def _choices(values, choices, field, errors, maximum=None):
    if not isinstance(values, list):
        errors.append(issue(FILE, field, 'an array', got=values))
        return
    if maximum is not None and len(values) > maximum:
        errors.append(issue(FILE, field, f'at most {maximum} entries', got=values))
    for value in values:
        if value not in choices:
            errors.append(issue(FILE, field, f'entries from {list(choices)}', got=value))
    if len(set(values)) != len(values):
        errors.append(issue(FILE, field, 'unique entries', got=values))


def _section(payload, name, keys, errors):
    section = payload.get(name)
    if not isinstance(section, dict):
        errors.append(issue(FILE, name, 'an object'))
        return {}
    for key in section:
        if key not in keys:
            errors.append(issue(FILE, f'{name}.{key}', 'a known field'))
    return section


def validate_questionnaire(payload, status, movement_ids):
    """Validate structure and values; completeness is enforced only for status='complete'."""
    errors = []
    if status not in ('draft', 'complete'):
        raise Reject([issue(FILE, 'status', "one of ['draft', 'complete']", got=status)])
    if not isinstance(payload, dict):
        raise Reject([issue(FILE, 'payload', 'an object')])
    allowed = {'schemaVersion', 'goal', 'schedule', 'personal', 'level', 'limits', 'recovery', 'outlook', 'notes'}
    for key in payload:
        if key not in allowed:
            errors.append(issue(FILE, key, 'a known section'))
    if payload.get('schemaVersion') != SCHEMA_VERSION:
        errors.append(issue(FILE, 'schemaVersion', SCHEMA_VERSION, got=payload.get('schemaVersion')))

    goal = _section(payload, 'goal', {'type'}, errors)
    _enum(goal.get('type'), ('competition', 'non-competition'), 'goal.type', errors)

    schedule = _section(payload, 'schedule',
                        {'startDate', 'competitionDate', 'testDates', 'trainingDaysPerWeek', 'sessionMinutes'}, errors)
    for field in ('startDate', 'competitionDate'):
        _date(schedule.get(field), f'schedule.{field}', errors)
    days = schedule.get('trainingDaysPerWeek')
    if days is not None and (isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 6):
        errors.append(issue(FILE, 'schedule.trainingDaysPerWeek', 'an integer from 1 to 6 or null', got=days))
    _number(schedule.get('sessionMinutes'), 15, 240, 'schedule.sessionMinutes', errors, integer=True)
    test_dates = schedule.get('testDates', [])
    if not isinstance(test_dates, list) or len(test_dates) > 4:
        errors.append(issue(FILE, 'schedule.testDates', 'an array of at most 4 dates', got=test_dates))
    else:
        for value in test_dates:
            _date(value, 'schedule.testDates', errors)
        if len(set(test_dates)) != len(test_dates):
            errors.append(issue(FILE, 'schedule.testDates', 'unique dates', got=test_dates))

    personal = _section(payload, 'personal',
                        {'age', 'sex', 'heightCm', 'bodyweightKg', 'trainingYears', 'equipment', 'activityLevel'}, errors)
    age = personal.get('age')
    if age is not None and (isinstance(age, bool) or not isinstance(age, int) or not 10 <= age <= 100):
        errors.append(issue(FILE, 'personal.age', 'an integer from 10 to 100 or null', got=age))
    _enum(personal.get('sex'), ('male', 'female', 'other'), 'personal.sex', errors)
    _number(personal.get('heightCm'), 100, 250, 'personal.heightCm', errors)
    _number(personal.get('bodyweightKg'), 30, 300, 'personal.bodyweightKg', errors)
    _number(personal.get('trainingYears'), 0, 60, 'personal.trainingYears', errors)
    _enum(personal.get('equipment'), ('classic', 'equipped'), 'personal.equipment', errors)
    _text(personal.get('activityLevel'), 200, 'personal.activityLevel', errors)

    level = _section(payload, 'level', {'sbd1rm', 'oneRmSource', 'recentPrs', 'variationPrs', 'fiveKm'}, errors)
    sbd = level.get('sbd1rm')
    if not isinstance(sbd, dict) or set(sbd) != {'squat', 'bench', 'deadlift'}:
        errors.append(issue(FILE, 'level.sbd1rm', 'an object with squat, bench and deadlift'))
    else:
        for lift, value in sbd.items():
            _number(value, 20, 600, f'level.sbd1rm.{lift}', errors)
    _enum(level.get('oneRmSource'), ('measured', 'estimated'), 'level.oneRmSource', errors)
    _text(level.get('recentPrs'), 500, 'level.recentPrs', errors)
    variation_prs = level.get('variationPrs')
    if not isinstance(variation_prs, dict) or set(variation_prs) != set(VARIATION_IDS):
        errors.append(issue(FILE, 'level.variationPrs', f'an object keyed by the eight variation IDs'))
    else:
        for movement, value in variation_prs.items():
            _number(value, 0, 600, f'level.variationPrs.{movement}', errors)
    five_km = level.get('fiveKm')
    if not isinstance(five_km, dict) or set(five_km) != {'timeSeconds', 'date', 'conditions'}:
        errors.append(issue(FILE, 'level.fiveKm', 'an object with timeSeconds, date and conditions'))
    else:
        _number(five_km.get('timeSeconds'), 600, 3600, 'level.fiveKm.timeSeconds', errors, integer=True)
        _date(five_km.get('date'), 'level.fiveKm.date', errors)
        _text(five_km.get('conditions'), 200, 'level.fiveKm.conditions', errors)

    limits = _section(payload, 'limits',
                      {'squat', 'bench', 'deadlift', 'weakMuscles', 'technique', 'injuries',
                       'surgeries', 'jointPain', 'mobility'}, errors)
    for lift in ('squat', 'bench', 'deadlift'):
        _choices(limits.get(lift, []), STICKING[lift], f'limits.{lift}', errors)
    _choices(limits.get('weakMuscles', []), WEAK_MUSCLES, 'limits.weakMuscles', errors)
    for field in ('technique', 'injuries', 'surgeries', 'jointPain', 'mobility'):
        _text(limits.get(field), 500, f'limits.{field}', errors)

    recovery = _section(payload, 'recovery',
                        {'sleepHours', 'sleepQuality', 'stressLevel', 'proteinSufficient',
                         'caloriesSufficient', 'bodyFatPercent', 'otherSports'}, errors)
    _number(recovery.get('sleepHours'), 0, 14, 'recovery.sleepHours', errors)
    for field in ('sleepQuality', 'stressLevel'):
        value = recovery.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5):
            errors.append(issue(FILE, f'recovery.{field}', 'an integer from 1 to 5 or null', got=value))
    for field in ('proteinSufficient', 'caloriesSufficient'):
        value = recovery.get(field)
        if value is not None and not isinstance(value, bool):
            errors.append(issue(FILE, f'recovery.{field}', 'a boolean or null', got=value))
    _number(recovery.get('bodyFatPercent'), 3, 60, 'recovery.bodyFatPercent', errors)
    _text(recovery.get('otherSports'), 300, 'recovery.otherSports', errors)

    outlook = _section(payload, 'outlook',
                       {'targetBodyweightKg', 'weightDirection', 'sbdFocus', 'targets', 'variationTargets',
                        'fiveKmTargetSeconds', 'consistencyGoal', 'effortLevel', 'riskPreference',
                        'competitionName', 'weightClass', 'targetTotalKg', 'keepMovements',
                        'avoidMovements', 'testGroups'}, errors)
    _number(outlook.get('targetBodyweightKg'), 30, 300, 'outlook.targetBodyweightKg', errors)
    _enum(outlook.get('weightDirection'), ('cut', 'maintain', 'bulk'), 'outlook.weightDirection', errors)
    _choices(outlook.get('sbdFocus', []), ('squat', 'bench', 'deadlift'), 'outlook.sbdFocus', errors, maximum=3)
    targets = outlook.get('targets')
    if not isinstance(targets, dict) or set(targets) != {'squat', 'bench', 'deadlift', 'total'}:
        errors.append(issue(FILE, 'outlook.targets', 'an object with squat, bench, deadlift and total'))
    else:
        for lift, value in targets.items():
            _number(value, 20, 1500, f'outlook.targets.{lift}', errors)
    variation_targets = outlook.get('variationTargets')
    if not isinstance(variation_targets, dict) or set(variation_targets) != set(VARIATION_IDS):
        errors.append(issue(FILE, 'outlook.variationTargets', 'an object keyed by the eight variation IDs'))
    else:
        for movement, value in variation_targets.items():
            _number(value, 0, 600, f'outlook.variationTargets.{movement}', errors)
    _number(outlook.get('fiveKmTargetSeconds'), 600, 3600, 'outlook.fiveKmTargetSeconds', errors, integer=True)
    _text(outlook.get('consistencyGoal'), 300, 'outlook.consistencyGoal', errors)
    _enum(outlook.get('effortLevel'), EFFORT_LEVELS, 'outlook.effortLevel', errors)
    _enum(outlook.get('riskPreference'), RISK_LEVELS, 'outlook.riskPreference', errors)
    _text(outlook.get('competitionName'), 200, 'outlook.competitionName', errors)
    _text(outlook.get('weightClass'), 50, 'outlook.weightClass', errors)
    _number(outlook.get('targetTotalKg'), 60, 1800, 'outlook.targetTotalKg', errors)
    for field in ('keepMovements', 'avoidMovements'):
        values = outlook.get(field, [])
        if not isinstance(values, list):
            errors.append(issue(FILE, f'outlook.{field}', 'an array of movement IDs', got=values))
            continue
        for value in values:
            if value not in movement_ids:
                errors.append(issue(FILE, f'outlook.{field}', 'an existing movement ID', got=value))
        if len(set(values)) != len(values):
            errors.append(issue(FILE, f'outlook.{field}', 'unique movement IDs', got=values))
    _choices(outlook.get('testGroups', []), TEST_GROUPS, 'outlook.testGroups', errors, maximum=4)
    _text(payload.get('notes'), 1000, 'notes', errors)

    if status == 'complete':
        required = (
            ('goal.type', goal.get('type')),
            ('schedule.startDate', schedule.get('startDate')),
            ('schedule.trainingDaysPerWeek', schedule.get('trainingDaysPerWeek')),
            ('personal.age', personal.get('age')),
            ('personal.sex', personal.get('sex')),
            ('personal.heightCm', personal.get('heightCm')),
            ('personal.bodyweightKg', personal.get('bodyweightKg')),
            ('outlook.targetBodyweightKg', outlook.get('targetBodyweightKg')),
            ('outlook.riskPreference', outlook.get('riskPreference')),
        )
        for field, value in required:
            if value is None:
                errors.append(issue(FILE, field, 'a value is required to complete the questionnaire'))
        if isinstance(sbd, dict):
            for lift in ('squat', 'bench', 'deadlift'):
                if sbd.get(lift) is None:
                    errors.append(issue(FILE, f'level.sbd1rm.{lift}', 'a value is required to complete the questionnaire'))
        if goal.get('type') == 'competition':
            if schedule.get('competitionDate') is None:
                errors.append(issue(FILE, 'schedule.competitionDate', 'required for a competition goal'))
            elif test_dates != [schedule['competitionDate']]:
                errors.append(issue(FILE, 'schedule.testDates', 'exactly the competition date for a competition goal',
                                    got=test_dates))
            if outlook.get('testGroups') != ['sbd']:
                errors.append(issue(FILE, 'outlook.testGroups', "exactly ['sbd'] for a competition goal",
                                    got=outlook.get('testGroups')))
        elif goal.get('type') == 'non-competition':
            if not outlook.get('testGroups'):
                errors.append(issue(FILE, 'outlook.testGroups', 'choose 1 to 4 test groups'))
            if not test_dates:
                errors.append(issue(FILE, 'schedule.testDates', 'choose 1 to 4 test dates'))
    if errors:
        raise Reject(errors)
    return payload