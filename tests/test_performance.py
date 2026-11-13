import copy
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.stats.performance import estimate, performance


SQUAT = 'S.Main|high-bar squat'
OHP = 'B.Delts|ohp'
PULL_UP = 'D.Lats|pull-up'
WEIGHTED_PULL_UP = 'D.Lats|weighted pull-up'
POWER_CLEAN = 'D.Vari.Power|power clean'
WEEK_FIELDS = {'n', 'value', 'estimated', 'method', 'date', 'key', 'load', 'reps', 'rpe'}


def workout(movement='High-bar Squat', category='S.Main', *, identity=None,
            week=1, day='A', seq=1, when=None, unit='', lift=None,
            system=False):
    """A small source row with deliberately different prescription values."""
    when = when or (date(2026, 2, 2) + timedelta(weeks=week - 1)).isoformat()
    return {
        'week': week, 'day': day, 'date': when, 'seq': seq,
        'movementId': identity or f'{category}|{movement.casefold()}',
        'movement': movement, 'nameEn': movement, 'category': category,
        'lift': lift, 'systemLoad': system,
        'sets': 5, 'reps': 5, 'loadRaw': 150, 'loadKg': 150, 'targetRpe': 10,
        'segments': [{'kind': 'work', 'label': 'WORK', 'sets': 5, 'reps': 5,
                      'unit': unit, 'load': 150, 'pct': None, 'delta': None,
                      'amrap': False}],
        'notes': 'Preserve the original prescription.',
    }


def row_key(row):
    return f"{row['week']}|{row['day']}|{row['seq']}"


def actual(load=100, reps=3, *, sets=2, rpe=None):
    return {'sets': sets, 'reps': reps, 'load': load, 'rpe': rpe}


def plan(rows, *, weeks=8, cycle='cycle-a'):
    start = date(2026, 2, 2)
    return {
        'schemaVersion': 'RPL-Raw-v1',
        'meta': {'planId': cycle, 'weeks': weeks, 'startDate': start.isoformat(),
                 'endDate': (start + timedelta(weeks=weeks, days=-1)).isoformat(),
                 'profile': {'bodyweight': 85}},
        'weeks': [
            {'n': n, 'dateStart': (start + timedelta(weeks=n - 1)).isoformat(),
             'dateEnd': (start + timedelta(weeks=n - 1, days=6)).isoformat()}
            for n in range(1, weeks + 1)
        ],
        'workouts': rows,
        'source': {'legacyEnvelope': {'notes': ['Keep the historical source.']}},
    }


class EstimateTests(unittest.TestCase):
    def assert_estimate(self, row, log, value, *, estimated=True):
        before = copy.deepcopy((row, log))
        result = estimate(row, log)
        self.assertEqual((row, log), before)
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result), {'value', 'estimated', 'method'})
        self.assertEqual(result['value'], value)
        self.assertIs(result['estimated'], estimated)
        if estimated:
            # Only the single's exact label is specified by the contract.
            self.assertIsInstance(result['method'], str)
            self.assertIn('Epley', result['method'])
        else:
            self.assertEqual(result['method'], 'Actual single')
        return result

    def test_explicit_epley_anchors_cover_every_supported_multi_rep_count(self):
        for reps, expected in (
                (2, 106.7), (3, 110), (4, 113.3), (5, 116.7), (6, 120),
                (7, 123.3), (8, 126.7), (9, 130), (10, 133.3)):
            with self.subTest(reps=reps):
                self.assert_estimate(workout(), actual(100, reps), expected)

    def test_epley_uses_half_up_tenths(self):
        # 31.5 x 3 gives 34.65: half-up is 34.7, not half-even 34.6.
        self.assert_estimate(workout(), actual(31.5, 3), 34.7)
        self.assert_estimate(workout(), actual(30.5, 3), 33.6)

    def test_actual_single_retains_unrounded_recorded_load(self):
        self.assert_estimate(workout(), actual(101.25, 1), 101.25, estimated=False)
        self.assert_estimate(workout(), actual(100, 1), 100, estimated=False)

    def test_ohp_and_pull_up_use_actual_and_total_system_load(self):
        self.assert_estimate(workout('OHP', 'B.Delts'), actual(60, 5), 70)
        for name, identity in (('Pull-Up', PULL_UP),
                               ('Weighted Pull-Up', WEIGHTED_PULL_UP)):
            with self.subTest(movement=name):
                row = workout(name, 'D.Lats', identity=identity, system=True)
                self.assert_estimate(row, actual(100, 3), 110)

    def test_missing_and_zero_logs_never_use_the_prescription(self):
        for log in (None, {}, actual(100, 3, sets=0), actual(None, 3)):
            row = workout()
            before = copy.deepcopy((row, log))
            with self.subTest(log=log):
                self.assertIsNone(estimate(row, log))
                self.assertEqual((row, log), before)
        log = actual()
        del log['load']
        self.assertIsNone(estimate(workout(), log))

    def test_reps_outside_one_to_ten_have_no_estimate(self):
        for reps in (None, -1, 0, 11, 30):
            with self.subTest(reps=reps):
                self.assertIsNone(estimate(workout(), actual(100, reps)))

    def test_any_unit_segment_excludes_singles_and_multi_rep_estimates(self):
        for unit in ('s', 's/side', 'reps/side', 'reps/arm', 'reps/leg'):
            for reps in (1, 3):
                with self.subTest(unit=unit, reps=reps):
                    row = workout('Plank', 'X.Core', unit=unit)
                    before = copy.deepcopy(row)
                    self.assertIsNone(estimate(row, actual(100, reps)))
                    self.assertEqual(row, before)

    def test_unit_on_any_segment_excludes_the_whole_row(self):
        for unit_first in (False, True):
            row = workout()
            timed = copy.deepcopy(row['segments'][0])
            timed['unit'] = 's'
            row['segments'].insert(0 if unit_first else 1, timed)
            before = copy.deepcopy(row)
            with self.subTest(unit_first=unit_first):
                self.assertIsNone(estimate(row, actual()))
                self.assertEqual(row, before)

    def test_only_exact_power_clean_excludes_multi_rep_extrapolation(self):
        row = workout('Power Clean', 'D.Vari.Power')
        self.assertIsNone(estimate(row, actual(70, 3)))
        self.assert_estimate(row, actual(70, 1), 70, estimated=False)
        self.assert_estimate(workout('Hang Power Clean', 'D.Vari.Power'),
                             actual(70, 3), 77)

    def test_missing_rpe_does_not_guess_rir_or_add_reps(self):
        row = workout()
        for rpe in (None, 6, 8, 10):
            with self.subTest(rpe=rpe):
                self.assert_estimate(row, actual(100, 3, rpe=rpe), 110)
        log = actual(100, 3)
        del log['rpe']
        self.assert_estimate(row, log, 110)


class PerformanceTests(unittest.TestCase):
    def entries(self, source_plan, logs):
        before = copy.deepcopy((source_plan, logs))
        result = performance(source_plan, logs)
        self.assertEqual((source_plan, logs), before, 'Inputs must remain unchanged')
        self.assertEqual(set(result), {'movements'})
        self.assertIsInstance(result['movements'], list)
        expected_ids = {row['movementId'] for row in source_plan['workouts']}
        self.assertEqual(len(result['movements']), len(expected_ids))
        entries = {entry['id']: entry for entry in result['movements']}
        self.assertEqual(set(entries), expected_ids)
        for entry in entries.values():
            self.assertEqual(set(entry), {'id', 'name', 'lift', 'system', 'weekly'})
            self.assertIsInstance(entry['system'], bool)
            self.assertEqual([point['n'] for point in entry['weekly']],
                             [week['n'] for week in source_plan['weeks']])
            for point in entry['weekly']:
                self.assertEqual(set(point), WEEK_FIELDS)
        return entries

    def assert_null_week(self, point, n):
        self.assertEqual(point, {field: n if field == 'n' else None
                                 for field in WEEK_FIELDS})

    def assert_observation(self, point, *, n, value, estimated, when, key,
                           load, reps, rpe):
        self.assertEqual({field: point[field] for field in WEEK_FIELDS - {'method'}},
                         {'n': n, 'value': value, 'estimated': estimated,
                          'date': when, 'key': key, 'load': load,
                          'reps': reps, 'rpe': rpe})
        self.assertIs(point['estimated'], estimated)
        if estimated:
            self.assertIsInstance(point['method'], str)
            self.assertIn('Epley', point['method'])
        else:
            self.assertEqual(point['method'], 'Actual single')

    def test_no_logs_include_all_movements_and_all_eight_or_seventeen_weeks(self):
        for count in (8, 17):
            rows = [workout(week=count, seq=3),
                    workout('OHP', 'B.Delts', seq=2), workout(seq=1)]
            for logs in ({}, None):
                with self.subTest(weeks=count, logs=logs):
                    entries = self.entries(plan(rows, weeks=count), logs)
                    self.assertEqual(entries[SQUAT]['name'], 'High-bar Squat')
                    for entry in entries.values():
                        for n, point in enumerate(entry['weekly'], 1):
                            self.assert_null_week(point, n)

    def test_partial_weeks_and_invalid_observations_leave_explicit_nulls(self):
        for count in (8, 17):
            rows = [workout(week=n) for n in (count, 4, 1, 5, 2, 3, 6)]
            logs = {
                '1|A|1': actual(100, 3),
                '2|A|1': actual(200, 3, sets=0, rpe=9),
                '3|A|1': actual(None, 3, rpe=8),
                # Week 4 is scheduled but not logged.
                '5|A|1': actual(200, 11, rpe=8),
                '6|A|1': {},
                f'{count}|A|1': actual(101.25, 1, rpe=9),
                '99|Z|99': actual(1000, 1, rpe=10),
            }
            with self.subTest(weeks=count):
                weekly = self.entries(plan(rows, weeks=count), logs)[SQUAT]['weekly']
                self.assert_observation(weekly[0], n=1, value=110, estimated=True,
                                        when='2026-02-02', key='1|A|1',
                                        load=100, reps=3, rpe=None)
                self.assert_observation(weekly[-1], n=count, value=101.25,
                                        estimated=False, when=rows[0]['date'],
                                        key=f'{count}|A|1', load=101.25, reps=1, rpe=9)
                for n in range(2, count):
                    self.assert_null_week(weekly[n - 1], n)

    def test_highest_estimate_wins_not_latest_or_highest_raw_load(self):
        rows = [
            workout(day='D', seq=4, when='2026-02-07'),
            workout(day='B', seq=2, when='2026-02-03'),
            workout(day='C', seq=3, when='2026-02-06'),
            workout(day='A', seq=1, when='2026-02-02'),
        ]
        logs = {'1|A|1': actual(100, 3, rpe=9),
                '1|B|2': actual(100, 10, rpe=8),
                '1|C|3': actual(125, 1, rpe=10),
                '1|D|4': actual(500, 1, sets=0, rpe=10)}
        for ordered in (rows, list(reversed(rows)), rows[1:] + rows[:1]):
            with self.subTest(order=[row_key(row) for row in ordered]):
                point = self.entries(plan(ordered), logs)[SQUAT]['weekly'][0]
                self.assert_observation(point, n=1, value=133.3, estimated=True,
                                        when='2026-02-03', key='1|B|2',
                                        load=100, reps=10, rpe=8)

    def test_equal_values_choose_latest_date_then_numeric_seq(self):
        rows = [
            workout(week=2, day='B', seq=2, when='2026-02-10'),
            workout(week=2, day='B', seq=10, when='2026-02-10'),
            workout(week=2, day='A', seq=99, when='2026-02-09'),
        ]
        logs = {'2|A|99': actual(100, 3, rpe=6),
                '2|B|2': actual(110, 1, rpe=9),
                '2|B|10': actual(100, 3)}
        del logs['2|B|10']['rpe']
        for ordered in (rows, list(reversed(rows)), rows[1:] + rows[:1]):
            with self.subTest(order=[row_key(row) for row in ordered]):
                point = self.entries(plan(ordered), logs)[SQUAT]['weekly'][1]
                self.assert_observation(point, n=2, value=110, estimated=True,
                                        when='2026-02-10', key='2|B|10',
                                        load=100, reps=3, rpe=None)

    def test_aliases_and_identical_names_keep_distinct_source_ids(self):
        rows = [
            workout('Pull-Up', 'D.Lats', seq=1, system=True),
            workout('Weighted Pull-Up', 'D.Lats', seq=2, system=True),
            workout('Low-bar Squat', 'S.Main', seq=3),
            workout('Low-bar Squat', 'S.Vari.End', seq=4),
            workout('Pull-Up', 'D.Lats', week=2, seq=1, system=True),
        ]
        logs = {'1|A|1': actual(100, 3), '1|A|2': actual(120, 1),
                '1|A|3': actual(100, 1), '1|A|4': actual(150, 1),
                '2|A|1': actual(105, 1)}
        entries = self.entries(plan(rows), logs)
        for identity, name, lift, system, expected in (
                (PULL_UP, 'Pull-Up', 'D', True, 110),
                (WEIGHTED_PULL_UP, 'Weighted Pull-Up', 'D', True, 120),
                ('S.Main|low-bar squat', 'Low-bar Squat', 'S', False, 100),
                ('S.Vari.End|low-bar squat', 'Low-bar Squat', 'S', False, 150)):
            with self.subTest(identity=identity):
                entry = entries[identity]
                self.assertEqual((entry['name'], entry['lift'], entry['system']),
                                 (name, lift, system))
                self.assertEqual(entry['weekly'][0]['value'], expected)
        self.assertEqual(entries[PULL_UP]['weekly'][1]['value'], 105)
        self.assert_null_week(entries[WEIGHTED_PULL_UP]['weekly'][1], 2)

    def test_lift_uses_family_before_library_and_can_remain_null(self):
        rows = [
            workout('OHP', 'B.Delts', seq=1, lift='S'),
            workout(seq=2, lift='D'),
            workout('Front Squat', 'S.Vari.Mid', seq=3, lift='S'),
            workout('Uncatalogued Movement', 'X.Other', seq=4),
        ]
        entries = self.entries(plan(rows), {row_key(row): actual(60, 5) for row in rows})
        self.assertEqual(entries[OHP]['lift'], 'B')
        self.assertEqual(entries[SQUAT]['lift'], 'S')
        # The existing Front Squat library entry has null lift; category is not
        # permission to invent a lift when the contract says family then library.
        self.assertIsNone(entries['S.Vari.Mid|front squat']['lift'])
        self.assertIsNone(entries['X.Other|uncatalogued movement']['lift'])
        self.assertEqual(entries[OHP]['weekly'][0]['value'], 70)

    def test_power_clean_and_timed_rows_keep_null_weeks_without_disappearing(self):
        rows = [
            workout('Power Clean', 'D.Vari.Power', seq=1),
            workout('Power Clean', 'D.Vari.Power', week=2, seq=1),
            workout('Plank', 'X.Core', seq=2, unit='s'),
        ]
        logs = {'1|A|1': actual(70, 3), '2|A|1': actual(70, 1, rpe=8),
                '1|A|2': actual(100, 3, rpe=9)}
        entries = self.entries(plan(rows), logs)
        self.assert_null_week(entries[POWER_CLEAN]['weekly'][0], 1)
        self.assert_observation(entries[POWER_CLEAN]['weekly'][1], n=2,
                                value=70, estimated=False, when='2026-02-09',
                                key='2|A|1', load=70, reps=1, rpe=8)
        for n, point in enumerate(entries['X.Core|plank']['weekly'], 1):
            self.assert_null_week(point, n)

    def test_cycles_are_isolated_by_supplied_plan_and_logs(self):
        cycle_a = plan([workout()], cycle='cycle-a')
        cycle_b = plan([workout()], cycle='cycle-b')
        logs_a = {'1|A|1': actual(100, 3)}
        logs_b = {'1|A|1': actual(80, 1)}
        original = copy.deepcopy((cycle_a, cycle_b, logs_a, logs_b))
        first = self.entries(cycle_a, logs_a)
        second = self.entries(cycle_b, logs_b)
        self.assertEqual(first[SQUAT]['weekly'][0]['value'], 110)
        self.assertEqual(second[SQUAT]['weekly'][0]['value'], 80)
        empty = self.entries(cycle_b, {})
        for n, point in enumerate(empty[SQUAT]['weekly'], 1):
            self.assert_null_week(point, n)
        self.assertEqual(self.entries(cycle_a, logs_a), first)
        self.assertEqual((cycle_a, cycle_b, logs_a, logs_b), original)

    def test_full_nested_inputs_are_immutable(self):
        rows = [workout(week=17), workout('Pull-Up', 'D.Lats', seq=2, system=True),
                workout('Power Clean', 'D.Vari.Power', seq=3), workout(seq=1)]
        source_plan = plan(rows, weeks=17)
        logs = {'1|A|1': actual(31.5, 3), '1|A|2': actual(100, 3),
                '1|A|3': actual(70, 3), '17|A|1': actual(101.25, 1)}
        logs['1|A|2']['notes'] = {'tags': ['Keep the recorded system load.']}
        original_plan = copy.deepcopy(source_plan)
        original_logs = copy.deepcopy(logs)
        self.entries(source_plan, logs)
        self.assertEqual(source_plan, original_plan)
        self.assertEqual(logs, original_logs)


if __name__ == '__main__':
    unittest.main()
