import copy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from server.app.stats.review import bodyweight_progress, build_review
from server.app.validation import validate_plan
from server.tools.synth_plan import build as build_synthetic_plan


EXPORTED_AT = '2027-04-01T12:00:00Z'
APP_VERSION = '0.0.6'
REQUIRED = {
    'schema', 'exported_at', 'plan_id', 'profile_start', 'profile_end', 'plan',
    'logs', 'readiness', 'planned_vs_actual', 'completion', 'attainment',
    'e1rm', 'end_state', 'next_outlook',
}
OPTIONAL = {
    'app_version', 'as_of', 'cycle', 'body_metrics', 'prescription_versions',
    'journals', 'integrity',
}
BUCKETS = ('main', 'sbdVar', 'nonSbdVar', 'accessory')


def row_key(row):
    return f"{row['week']}|{row['day']}|{row['seq']}"


def objects(value):
    """Visit JSON objects without imposing an unspecified nested report layout."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


def canonical_digest(document):
    # Deliberately independent of every production digest/helper.
    payload = {key: value for key, value in document.items() if key != 'integrity'}
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def metric(when, weight, *, bodyfat=None, measurements=None):
    return {'date': when, 'bodyweight': weight, 'bodyfat': bodyfat,
            'measurements': {} if measurements is None else measurements}


def actual(*, sets=2, reps=3, load=100, rpe=8.5, note='Recorded, not prescribed'):
    return {'sets': sets, 'reps': reps, 'load': load, 'rpe': rpe,
            'note': note, 'updated_at': EXPORTED_AT}


class BodyweightProgressTests(unittest.TestCase):
    def test_literal_cut_and_bulk_progress_is_not_capped(self):
        for start, target, current, expected in (
                (100, 90, 95, 50), (100, 90, 88, 120), (100, 90, 102, -20),
                (80, 90, 85, 50), (80, 90, 92, 120), (80, 90, 78, -20)):
            with self.subTest(start=start, target=target, current=current):
                self.assertEqual(bodyweight_progress(start, target, current), expected)

    def test_literal_maintenance_tolerance_and_penalty(self):
        for current, expected in ((100, 100), (99, 100), (101, 100),
                                  (98, 90), (102, 90), (90, 10), (89, 0),
                                  (110, 10), (111, 0)):
            with self.subTest(current=current):
                self.assertAlmostEqual(bodyweight_progress(100, 100, current), expected)

    def test_invalid_inputs_are_null_in_every_argument(self):
        invalid = (None, 0, -1, True, False, float('nan'), float('inf'), float('-inf'))
        for baseline in ((100, 90, 95), (80, 90, 85), (100, 100, 99)):
            for index in range(3):
                for value in invalid:
                    values = list(baseline)
                    values[index] = value
                    with self.subTest(baseline=baseline, argument=index, value=value):
                        self.assertIsNone(bodyweight_progress(*values))


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT / 'data/plan.json').read_text(encoding='utf-8'))
        validate_plan(cls.plan, file='review-generated-baseline.json')
        schema = json.loads((ROOT / 'data/schema/RPL-Review-v1.json').read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def source(self, plan=None):
        plan = copy.deepcopy(self.plan if plan is None else plan)
        meta = plan['meta']
        return {
            'cycle': {'id': meta['planId'], 'name': meta['name'],
                      'start_date': meta['startDate'], 'end_date': meta['endDate'],
                      'status': 'active', 'schema_version': plan['schemaVersion']},
            'plan': plan, 'logs': {}, 'body_metrics': [], 'readiness': [],
            'legacy_readiness': [], 'prescription_versions': [],
            'journals': {'logs': [], 'records': []},
        }

    def review(self, source, as_of=None):
        before = copy.deepcopy(source)
        as_of = source['cycle']['end_date'] if as_of is None else as_of
        result = build_review(source, exported_at=EXPORTED_AT,
                              app_version=APP_VERSION, as_of=as_of)
        self.assertEqual(source, before, 'The complete nested source must be immutable')
        self.assertIsInstance(result, dict)
        self.assertTrue(REQUIRED <= result.keys())
        self.assertTrue(result.keys() <= REQUIRED | OPTIONAL)
        self.validator.validate(result)
        validate_plan(result['plan'], file='review-embedded-plan.json')
        self.assertEqual(result['schema'], 'RPL-Review-v1')
        self.assertEqual(result['exported_at'], EXPORTED_AT)
        self.assertEqual(result['plan_id'], source['cycle']['id'])
        self.assertEqual(result['app_version'], APP_VERSION)
        self.assertEqual(result['as_of'], as_of)
        self.assertEqual(result['cycle'], source['cycle'])
        self.assertEqual(result['plan'], source['plan'])
        self.assertEqual(result['profile_start'], source['plan']['meta']['profile'])
        self.assertIsInstance(result['logs'], list)
        self.assertEqual(result['integrity']['algorithm'], 'SHA-256')
        self.assertEqual(result['integrity']['review_sha256'], canonical_digest(result))
        # A real JSON round trip, with non-finite numbers forbidden.
        self.assertEqual(json.loads(json.dumps(result, ensure_ascii=False, allow_nan=False)), result)
        return result

    def assert_payload_present(self, container, payload):
        self.assertTrue(any(all(key in node and node[key] == value
                                for key, value in payload.items())
                            for node in objects(container)),
                        f'Stored payload not preserved: {payload!r}')

    def assert_unknown_goal(self, review):
        self.assertIsNone(review['attainment']['goal'])
        self.assertIsNone(review['attainment']['composite'])
        self.assertEqual(review['attainment']['weights'],
                         {'goal': .40, 'bodyweight': .40, 'completion': .20})
        self.assertEqual(review['attainment']['completion_weights'],
                         {'main': .60, 'var': .25, 'acc': .15})
        self.assertIs(review['attainment']['capped'], False)
        for lift in ('S', 'B', 'D'):
            self.assertEqual(review['end_state']['sbd'][lift],
                             {'value': None, 'date': None, 'status': 'not_tested'})

    def test_mandatory_shape_generated_plan_and_unknown_actuals(self):
        source = self.source()
        review = self.review(source)
        self.assertEqual(review['logs'], [])
        self.assertIsNone(review['profile_end'])
        self.assertIsNone(review['attainment']['bodyweight'])
        self.assert_unknown_goal(review)
        self.assertEqual(review['completion']['actual'], dict.fromkeys(BUCKETS, 0))
        self.assertEqual([review['completion'][key] for key in ('main', 'var', 'acc')],
                         [0, 0, 0])
        self.assertIsNone(review['next_outlook'])
        # An e1RM value may not be borrowed from the profile or prescription.
        self.assertFalse(any(node.get('value') is not None for node in objects(review['e1rm'])))

    def test_independent_schema_rejects_bad_format_and_missing_mandatory_field(self):
        review = self.review(self.source())
        invalid = copy.deepcopy(review)
        invalid['exported_at'] = '2027-02-30T12:00:00Z'
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)
        invalid = copy.deepcopy(review)
        del invalid['profile_end']
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)
        invalid = copy.deepcopy(review)
        invalid['schema'] = 'RPL-Raw-v1'
        with self.assertRaises(ValidationError):
            self.validator.validate(invalid)

    def test_digest_covers_unicode_and_every_stored_history_payload(self):
        source = self.source()
        row = source['plan']['workouts'][0]
        key = row_key(row)
        source['logs'][key] = actual(load=101.25, note='原始记录 · do not round')
        source['body_metrics'] = [metric(row['date'], 95, measurements={'waist': 81.25})]
        source['prescription_versions'] = [
            {'id': 'original-version', 'plan': copy.deepcopy(source['plan']), 'created_at': EXPORTED_AT},
            {'id': 'stored-version', 'plan': copy.deepcopy(source['plan']), 'created_at': EXPORTED_AT},
        ]
        source['prescription_versions'][1]['plan']['meta']['name'] = 'Historical prescription · preserve'
        source['prescription_versions'][1]['plan']['meta']['profile']['target_bw_kg'] = 89
        source['journals'] = {
            'logs': [{'id': 1, 'cycle_id': source['cycle']['id'], 'key': key,
                      'payload': actual(sets=0, reps=0, load=None, rpe=None, note='Earlier explicit zero'),
                      'created_at': EXPORTED_AT}],
            'records': [{'id': 2, 'cycle_id': source['cycle']['id'], 'kind': 'body_metrics',
                         'key': row['date'], 'payload': metric(row['date'], 96),
                         'created_at': EXPORTED_AT}],
        }
        review = self.review(source)
        self.assertEqual(review['prescription_versions'], source['prescription_versions'])
        self.assertEqual(review['journals'], source['journals'])
        self.assertEqual(review['body_metrics'], source['body_metrics'])
        original = canonical_digest(review)
        reordered = dict(reversed(list(review.items())))
        self.assertEqual(canonical_digest(reordered), original)
        integrity_only = copy.deepcopy(review)
        integrity_only['integrity']['review_sha256'] = '0' * 64
        self.assertEqual(canonical_digest(integrity_only), original)
        for field in ('plan', 'logs', 'prescription_versions', 'journals', 'body_metrics'):
            changed = copy.deepcopy(review)
            if field == 'plan':
                changed[field]['meta']['name'] += ' altered'
            elif field == 'journals':
                changed[field]['logs'][0]['payload']['note'] += ' altered'
            elif field == 'prescription_versions':
                changed[field][0]['plan']['meta']['name'] += ' altered'
            elif field == 'body_metrics':
                changed[field][0]['bodyweight'] = 94
            else:
                changed[field][0]['note'] += ' altered'
            with self.subTest(field=field):
                self.assertNotEqual(canonical_digest(changed), original)
                self.assertNotEqual(changed['integrity']['review_sha256'], canonical_digest(changed))

    def test_bodyweight_latest_same_or_prior_date_inside_cycle_not_future(self):
        source = self.source()
        source['plan']['meta']['profile'].update(init_bw_kg=100, target_bw_kg=90)
        start = date.fromisoformat(source['cycle']['start_date'])
        end = date.fromisoformat(source['cycle']['end_date'])
        same_day = (start + timedelta(days=3)).isoformat()
        future = (start + timedelta(days=4)).isoformat()
        # Deliberately unsorted: chronological selection must not use array order.
        source['body_metrics'] = [
            metric(future, 88), metric(same_day, 95),
            metric((start - timedelta(days=1)).isoformat(), 89),
            metric(start.isoformat(), 96), metric((end + timedelta(days=1)).isoformat(), 87),
        ]
        for when, expected in ((start.isoformat(), 40), (same_day, 50),
                               ((start + timedelta(days=2)).isoformat(), 40),
                               (future, 120), ((end + timedelta(days=2)).isoformat(), 120)):
            with self.subTest(as_of=when):
                review = self.review(source, when)
                self.assertEqual(review['attainment']['bodyweight'], expected)
                self.assert_unknown_goal(review)
        # Only out-of-cycle and future readings remain; none may supply a score.
        source['body_metrics'] = [source['body_metrics'][0], source['body_metrics'][2], source['body_metrics'][4]]
        review = self.review(source, same_day)
        self.assertIsNone(review['attainment']['bodyweight'])
        self.assertIsNone(review['profile_end'])

    def test_missing_start_or_target_never_falls_back_to_profile_bodyweight(self):
        for missing in ('init_bw_kg', 'target_bw_kg'):
            source = self.source()
            profile = source['plan']['meta']['profile']
            profile.update(init_bw_kg=100, target_bw_kg=90, bw_kg=100)
            del profile[missing]
            source['body_metrics'] = [metric(source['cycle']['start_date'], 95)]
            with self.subTest(missing=missing):
                review = self.review(source)
                self.assertIsNone(review['attainment']['bodyweight'])
                self.assert_unknown_goal(review)

    def test_profile_end_is_explicit_actual_not_inferred_personal_status(self):
        source = self.source()
        source['plan']['meta']['profile']['age'] = 42
        recorded = metric(source['cycle']['start_date'], 95, bodyfat=17.5,
                          measurements={'waist': 81.25})
        source['body_metrics'] = [recorded]
        review = self.review(source)
        self.assertEqual(review['profile_end'], recorded)
        self.assertNotIn('age', review['profile_end'])
        source['body_metrics'] = [metric(source['cycle']['start_date'], None)]
        self.assertIsNone(self.review(source)['profile_end'])

    def test_invalid_dates_and_nonpositive_actual_weights_cannot_score(self):
        for weight in (None, 0, -1, True, False):
            source = self.source()
            source['plan']['meta']['profile'].update(init_bw_kg=100, target_bw_kg=90)
            source['body_metrics'] = [metric(source['cycle']['start_date'], weight)]
            with self.subTest(weight=weight):
                review = self.review(source)
                self.assertIsNone(review['profile_end'])
                self.assertIsNone(review['attainment']['bodyweight'])
        for when in ('2027-02-30', 'not-a-date'):
            source = self.source()
            source['plan']['meta']['profile'].update(init_bw_kg=100, target_bw_kg=90)
            source['body_metrics'] = [metric(when, 95)]
            with self.subTest(date=when):
                review = self.review(source)
                self.assertIsNone(review['profile_end'])
                self.assertIsNone(review['attainment']['bodyweight'])

    def test_bodyfat_and_measurements_are_explicit_actuals_not_weight_defaults(self):
        for recorded in (metric(self.plan['meta']['startDate'], None, bodyfat=0),
                         metric(self.plan['meta']['startDate'], None,
                                measurements={'waist': 81.25})):
            source = self.source()
            source['plan']['meta']['profile'].update(init_bw_kg=100, target_bw_kg=90, bw_kg=100)
            source['body_metrics'] = [recorded]
            with self.subTest(metric=recorded):
                review = self.review(source)
                self.assertEqual(review['profile_end'], recorded)
                self.assertIsNone(review['attainment']['bodyweight'])
                self.assertEqual(review['end_state']['bodyweight'], {'value': None, 'date': None})

    def test_every_recorded_row_keeps_raw_load_rpe_note_even_when_future(self):
        source = self.source()
        first, last = source['plan']['workouts'][0], source['plan']['workouts'][-1]
        records = {
            row_key(first): actual(sets=0, reps=0, load=None, rpe=None, note='Explicit zero · skipped'),
            row_key(last): actual(sets=3, reps=1, load=101.25, rpe=9.5, note='Future stored row · retain'),
        }
        source['logs'] = records
        review = self.review(source, source['cycle']['start_date'])
        self.assertGreater(last['date'], source['cycle']['start_date'])
        self.assertEqual(len(review['logs']), len(records))
        exported = {entry['key']: {field: entry[field] for field in records[entry['key']]}
                    for entry in review['logs']}
        self.assertEqual(exported, records)

    def test_planned_vs_actual_has_every_prescription_and_null_unlogged_rows(self):
        source = self.source()
        review = self.review(source)
        comparisons = review['planned_vs_actual']
        rows = {entry['key']: entry for entry in comparisons['rows']}
        self.assertEqual(len(comparisons['rows']), len(source['plan']['workouts']))
        self.assertEqual(set(rows), {row_key(row) for row in source['plan']['workouts']})
        for row in source['plan']['workouts']:
            entry = rows[row_key(row)]
            with self.subTest(row=row_key(row)):
                self.assertEqual({key: entry[key] for key in
                                  ('week', 'day', 'seq', 'date', 'movementId')},
                                 {key: row[key] for key in
                                  ('week', 'day', 'seq', 'date', 'movementId')})
                self.assertEqual(entry['planned'], {
                    'sets': row['sets'], 'reps': row['reps'], 'loadKg': row['loadKg'],
                    'rpe': row['targetRpe'], 'segments': row['segments'],
                    'tonnageKg': row['tonnageKg'],
                })
                self.assertIsNone(entry['actual'])
        weeks = comparisons['weeks']
        self.assertEqual([week['n'] for week in weeks],
                         [week['n'] for week in source['plan']['weeks']])
        for week, prescribed in zip(weeks, source['plan']['weeks']):
            with self.subTest(week=week['n']):
                self.assertEqual(week['kind'], prescribed['kind'])
                self.assertEqual(week['dateStart'], prescribed['dateStart'])
                self.assertEqual(week['dateEnd'], prescribed['dateEnd'])
                self.assertEqual(week['planned']['total'], prescribed['sets'])
                self.assertEqual(week['planned']['tonnageKg'], prescribed['tonnageKg'])
                self.assertEqual(week['actual']['total'], 0)
                self.assertEqual(week['actual']['tonnageKg'], 0)
                self.assertEqual(week['actual']['roles'], dict.fromkeys(BUCKETS, 0))
                self.assertEqual(week['actual']['lifts'],
                                 {lift: {'main': 0, 'var': 0} for lift in ('S', 'B', 'D')})
        # Labels come from the generated plan, including every deload/test week.
        for kind in ('deload', 'test'):
            expected = [week['n'] for week in source['plan']['weeks'] if week['kind'] == kind]
            self.assertTrue(expected, f'The generated baseline must exercise {kind}')
            self.assertEqual([week['n'] for week in weeks if week['kind'] == kind], expected)

    def test_weekly_actuals_are_only_recorded_rows_and_zero_is_not_missing(self):
        source = self.source()
        rows = [next(row for row in source['plan']['workouts']
                     if row['week'] == 1 and row['bucket'] == bucket)
                for bucket in ('main', 'sbdVar', 'accessory')]
        source['logs'] = {
            row_key(rows[0]): actual(sets=2, reps=3, load=100),
            row_key(rows[1]): actual(sets=2, reps=3, load=101.25),
            row_key(rows[2]): actual(sets=4, reps=12, load=20),
        }
        zero_row = next(row for row in source['plan']['workouts'] if row['week'] == 2)
        source['logs'][row_key(zero_row)] = actual(sets=0, reps=0, load=None, rpe=None)
        review = self.review(source)
        entries = {entry['key']: entry for entry in review['planned_vs_actual']['rows']}
        for row in source['plan']['workouts']:
            key = row_key(row)
            self.assertEqual(entries[key]['actual'], source['logs'].get(key), key)
        self.assertEqual(entries[row_key(zero_row)]['actual']['sets'], 0)
        weeks = review['planned_vs_actual']['weeks']
        # 2 main + 2 variation + 4 accessory sets = 8 raw sets.
        # 2*3*100 + 2*3*101.25 = 1207.5 kg; accessory weight is not SBD tonnage.
        self.assertEqual(weeks[0]['actual']['total'], 8)
        self.assertEqual(weeks[0]['actual']['tonnageKg'], 1207.5)
        self.assertEqual(weeks[0]['actual']['roles'],
                         {'main': 2, 'sbdVar': 2, 'nonSbdVar': 0, 'accessory': 4})
        for week in weeks[1:]:
            self.assertEqual(week['actual']['total'], 0)
            self.assertEqual(week['actual']['tonnageKg'], 0)
            self.assertEqual(week['actual']['roles'], dict.fromkeys(BUCKETS, 0))

    def test_completion_raw_buckets_actual_only_zero_and_uncapped(self):
        source = self.source()
        # Every row is recorded: 2x main, 3x variation, 1x accessory.
        # The independent literal percentages are 200 / 300 / 100, not
        # transferred SBD-equivalent capacity or muscle-weighted volume.
        factors = {'main': 2, 'sbdVar': 3, 'nonSbdVar': 3, 'accessory': 1}
        planned = dict.fromkeys(BUCKETS, 0)
        for row in source['plan']['workouts']:
            planned[row['bucket']] += row['sets']
            source['logs'][row_key(row)] = actual(
                sets=row['sets'] * factors[row['bucket']], reps=1, load=101.25,
                note='Actual single, not an actual SBD test')
        source['plan']['meta']['profile'].update(init_bw_kg=100, target_bw_kg=90)
        source['body_metrics'] = [metric(source['cycle']['start_date'], 95)]
        review = self.review(source)
        completion = review['completion']
        self.assertEqual(completion['planned'], planned)
        self.assertEqual(completion['actual'],
                         {bucket: planned[bucket] * factors[bucket] for bucket in BUCKETS})
        self.assertEqual([completion[key] for key in ('main', 'var', 'acc')], [200, 300, 100])
        self.assertEqual(review['attainment']['completion'], 210)
        self.assertEqual(review['attainment']['bodyweight'], 50)
        self.assert_unknown_goal(review)
        for key in source['logs']:
            source['logs'][key] = actual(sets=0, reps=0, load=None, rpe=None, note='Explicit zero')
        zero = self.review(source)
        self.assertEqual(zero['completion']['actual'], dict.fromkeys(BUCKETS, 0))
        self.assertEqual([zero['completion'][key] for key in ('main', 'var', 'acc')], [0, 0, 0])
        self.assertEqual(len(zero['logs']), len(source['plan']['workouts']))
        self.assertEqual(zero['attainment']['completion'], 0)

    def test_epley_comes_only_from_recorded_work_not_plan_baseline(self):
        source = self.source()
        row = next(row for row in source['plan']['workouts']
                   if row['movementId'] == 'S.Main|high-bar squat')
        source['logs'][row_key(row)] = actual(sets=2, reps=3, load=100, rpe=None)
        review = self.review(source)
        self.assert_payload_present(review['e1rm'],
                                    {'value': 110, 'estimated': True, 'load': 100,
                                     'reps': 3, 'date': row['date'], 'rpe': None})
        source['logs'][row_key(row)] = actual(sets=1, reps=1, load=101.25, rpe=9.5)
        single = self.review(source)
        self.assert_payload_present(single['e1rm'],
                                    {'value': 101.25, 'estimated': False,
                                     'load': 101.25, 'reps': 1, 'date': row['date']})
        self.assert_unknown_goal(single)
        source['logs'][row_key(row)]['sets'] = 0
        zero = self.review(source)
        self.assertFalse(any(node.get('value') is not None for node in objects(zero['e1rm'])))

    def test_positive_readiness_and_legacy_fatigue_are_separate(self):
        source = self.source()
        row = source['plan']['workouts'][0]
        positive = {
            'cycle_id': source['cycle']['id'], 'date': row['date'],
            'session_id': f"{row['week']}|{row['day']}",
            'recovery': 1, 'arousal': 4, 'nutrition': 7,
            'hrv': None, 'rhr': None, 'sleep_score': 80,
            'session_time': '06:00', 'joint_pain': False,
            'note': 'Positive recovery, not fatigue', 'updated_at': EXPORTED_AT,
        }
        unknown = {**positive, 'session_id': 'daily', 'recovery': None,
                   'arousal': None, 'nutrition': None, 'sleep_score': None,
                   'note': 'Unknown positive readiness'}
        legacy = {
            'cycle_id': source['cycle']['id'], 'date': row['date'], 'session_id': 'legacy',
            'fatigue': 7, 'arousal': 4, 'nutrition': 7, 'hrv': None,
            'sleep_score': 80, 'rhr': None, 'session_time': '06:00',
            'rec': .75, 'note': 'Original high fatigue meaning',
        }
        source['readiness'] = [positive, unknown]
        source['legacy_readiness'] = [legacy]
        review = self.review(source)
        self.assert_payload_present(review['readiness'], positive)
        self.assert_payload_present(review['readiness'], unknown)
        self.assert_payload_present(review['readiness'], legacy)
        # Literal scorer anchors: (0 + 50 + 100 + 80) / 4 = 57.5;
        # REC = .75 + .5 * .575 = 1.0375. No production scorer supplies these.
        self.assert_payload_present(review['readiness'],
                                    {'score': 57.5, 'validInputs': 4, 'rec': 1.0375})
        self.assert_payload_present(review['readiness'],
                                    {'score': None, 'validInputs': 0, 'rec': None})
        legacy_nodes = [node for node in objects(review['readiness']) if 'fatigue' in node]
        self.assertEqual(len(legacy_nodes), 1)
        self.assertEqual(legacy_nodes[0]['fatigue'], 7)
        self.assertNotIn('recovery', legacy_nodes[0])
        # Old fatigue cannot create positive-v2 observations or an end profile.
        source['readiness'] = []
        legacy_only = self.review(source)
        self.assert_payload_present(legacy_only['readiness'], legacy)
        self.assertFalse(any('scores' in node for node in objects(legacy_only['readiness'])))
        self.assertIsNone(legacy_only['profile_end'])

    def test_eight_and_seventeen_week_synthetic_plans_remain_complete(self):
        for count in (8, 17):
            source = self.source(build_synthetic_plan(count))
            last = source['plan']['workouts'][-1]
            source['logs'][row_key(last)] = actual(load=101.25, note='Final synthetic week actual')
            with self.subTest(weeks=count):
                review = self.review(source)
                self.assertEqual(len(review['plan']['weeks']), count)
                self.assertEqual([week['n'] for week in review['plan']['weeks']],
                                 list(range(1, count + 1)))
                self.assertEqual(len(review['plan']['workouts']), len(source['plan']['workouts']))
                self.assertEqual(len(review['planned_vs_actual']['rows']), len(source['plan']['workouts']))
                self.assertEqual([week['n'] for week in review['planned_vs_actual']['weeks']],
                                 list(range(1, count + 1)))
                self.assertEqual([week['actual']['total'] for week in review['planned_vs_actual']['weeks']],
                                 [0] * (count - 1) + [2])
                for movement in review['e1rm']['movements']:
                    self.assertEqual([point['n'] for point in movement['weekly']],
                                     list(range(1, count + 1)))
                self.assertEqual(len(review['logs']), 1)
                self.assert_payload_present(review['logs'], source['logs'][row_key(last)])
                self.assert_unknown_goal(review)

    def test_supplied_cycles_are_isolated_without_cross_call_state(self):
        first_source = self.source()
        second_source = self.source()
        second_source['cycle']['id'] = 'independent-second-cycle'
        second_source['plan']['meta']['planId'] = second_source['cycle']['id']
        row = first_source['plan']['workouts'][0]
        first_source['logs'][row_key(row)] = actual(load=100, note='First cycle only')
        first = self.review(first_source)
        second = self.review(second_source)
        self.assertEqual(second['logs'], [])
        self.assertEqual(second['completion']['actual'], dict.fromkeys(BUCKETS, 0))
        self.assertIsNone(second['profile_end'])
        self.assertNotEqual(first['plan_id'], second['plan_id'])
        self.assertEqual(self.review(first_source), first)


if __name__ == '__main__':
    unittest.main()
