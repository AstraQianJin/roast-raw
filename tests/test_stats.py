import copy
from datetime import date, timedelta
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.stats import classify as C
from server.app.stats.engine import analyze, attainment, leaf_tiers, r1, row_volume
from server.app.stats.prescription import mround, parse_segments, row_load


class StatisticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT / 'data/plan.json').read_text(encoding='utf-8'))

    def test_ordered_classification(self):
        for name in C.MAIN_MOVES:
            self.assertEqual(C.movement_bucket(name, {'category': 'D.Vari.Power'}), 'main')
        for name in C.POWER_CLEAN_NAMES:
            self.assertEqual(C.movement_bucket(name), 'sbdVar')
            self.assertEqual(C.movement_lift(name), 'D')
        for name in C.SNATCH_NAMES:
            self.assertEqual(C.movement_bucket(name, {'category': 'D.Vari.Power'}), 'accessory')
            self.assertIsNone(C.movement_lift(name, {'category': 'D.Vari.Power'}))
        self.assertEqual(C.movement_bucket('Romanian Deadlift'), 'nonSbdVar')
        self.assertEqual(C.movement_bucket('Face Pull'), 'accessory')
        self.assertEqual(C.movement_level('Bent-Over Barbell Row'), 'secondary_var')

    def test_tier_boundaries(self):
        tiers, maximum = leaf_tiers({'a': 1, 'b': .8, 'c': .3, 'd': .299, 'e': 0})
        self.assertEqual(maximum, 1)
        self.assertEqual(tiers, {'a': 1, 'b': 1, 'c': 2, 'd': 0, 'e': 0})
        self.assertEqual(leaf_tiers({'a': 0})[0], {'a': 0})

    def test_rounding_and_bilingual_segments(self):
        self.assertEqual(r1(170.14999999999998), 170.2)
        self.assertEqual(mround(100.25, .5), 100.5)
        self.assertEqual(row_load({'load': 101}, 'variation'), 100)
        self.assertIsNone(row_load({'load': 101}, 'accessory'))
        template = {'load': 100, 'pct': .8, 'sets': 4, 'reps': 5, 'bucket': 'main'}
        chinese = parse_segments({**template, 'rxRaw': '1×5 顶组 + 3×5 减 3% 补组'})
        english = parse_segments({**template, 'rxRaw': '1×5 top + 3×5 −3% back-off'})
        self.assertEqual(chinese, english)
        self.assertEqual(sum(s['sets'] for s in chinese), 4)
        self.assertEqual(chinese[1]['load'], 97)
        side = parse_segments({'rxRaw': '3×30s/side', 'bucket': 'accessory'})[0]
        self.assertEqual((side['reps'], side['unit']), (30, 's/side'))
        non_sbd = parse_segments({'rxRaw': '3×5 @70%', 'pct': .7, 'bucket': 'nonSbdVar'})[0]
        self.assertIsNone(non_sbd['pct'])

    def test_missing_log_falls_back_but_is_not_completed(self):
        planned = analyze(self.plan)
        logged = analyze(self.plan, mode='log')
        self.assertEqual(logged['cycle'], planned['cycle'])
        self.assertEqual(logged['completion']['actual'], dict.fromkeys(planned['completion']['planned'], 0))
        self.assertEqual(logged['completion']['main'], 0)

    def test_zero_sets_replaces_plan_instead_of_falling_back(self):
        row = self.plan['workouts'][0]
        key = f"{row['week']}|{row['day']}|{row['seq']}"
        logs = {key: {'sets': 0, 'reps': 0, 'load': None, 'rpe': None}}
        planned = analyze(self.plan)
        actual = analyze(self.plan, logs, 'log')
        self.assertEqual(actual['cycle']['total'], planned['cycle']['total'] - row['sets'])
        self.assertAlmostEqual(actual['cycle']['tonnageKg'], planned['cycle']['tonnageKg'] - row['tonnageKg'], places=1)
        self.assertEqual(analyze(self.plan, logs, 'plan')['cycle'], planned['cycle'])

    def test_actual_load_is_not_prescription_rounded(self):
        row = next(row for row in self.plan['workouts'] if row['role'] == 'variation')
        actual, errors = row_volume(row, {'sets': 2, 'reps': 3, 'load': 101.25})
        self.assertEqual(errors, [])
        self.assertEqual(actual['kg'], 607.5)
        self.assertEqual(actual['sets'], 2)

    def test_completion_uncapped_and_null_components(self):
        row = self.plan['workouts'][0]
        logs = {f"{row['week']}|{row['day']}|{row['seq']}": {'sets': 1000, 'reps': 1, 'load': 1}}
        self.assertGreater(analyze(self.plan, logs, 'log')['completion']['main'], 100)
        self.assertIsNone(attainment({'main': 100, 'var': 100, 'acc': 100})['composite'])
        self.assertEqual(attainment({'main': 120, 'var': 120, 'acc': 120}, 120, 120)['composite'], 120)

    def test_unresolved_is_explicit(self):
        row = copy.deepcopy(self.plan['workouts'][0])
        row['movement'] = 'Unknown Movement'
        volume, errors = row_volume(row)
        self.assertEqual(volume['sets'], 0)
        self.assertTrue(errors)

    def test_mode_rejects_unknown(self):
        with self.assertRaises(ValueError):
            analyze(self.plan, mode='anything')

    def _heat_plan(self, counts):
        """Copy fixture identity/calendar; prescribe one known squat per week."""
        source = next(row for row in self.plan['workouts']
                      if row['movementId'] == 'S.Main|high-bar squat')
        plan = {'schemaVersion': self.plan['schemaVersion'],
                'meta': copy.deepcopy(self.plan['meta']), 'weeks': [], 'workouts': []}
        start = date.fromisoformat(self.plan['weeks'][0]['dateStart'])
        for index, count in enumerate(counts):
            week = copy.deepcopy(self.plan['weeks'][index % len(self.plan['weeks'])])
            day = start + timedelta(weeks=index)
            week.update(n=index + 1, dateStart=day.isoformat(),
                        dateEnd=(day + timedelta(days=6)).isoformat(),
                        days=['A'], sessions=1, sets=count,
                        tonnageKg=count * 500, mainTonnageKg=count * 500,
                        topPct=80, topPctByLift={'S': 80, 'B': None, 'D': None})
            row = copy.deepcopy(source)
            rx = f'{count}×5 @ 80% @ 100 kg'
            segment = copy.deepcopy(source['segments'][0])
            segment.update(sets=count, reps=5, load=100, pct=80, text=rx)
            row.update(week=week['n'], day='A', date=day.isoformat(), seq=1,
                       sets=count, reps=5, loadKg=100, loadRaw=100, pct=.8,
                       notes='', rxRaw=rx, rxEn=rx, segments=[segment],
                       tonnageKg=count * 500)
            plan['weeks'].append(week)
            plan['workouts'].append(row)
        plan['meta'].update(weeks=len(counts), sessions=len(counts), auxSets=0,
                            startDate=plan['weeks'][0]['dateStart'],
                            endDate=plan['weeks'][-1]['dateEnd'],
                            cycleTonnageKg=sum(counts) * 500)
        return plan

    def _assert_heat_contract(self, result, maximum):
        self.assertEqual(result['heatScale'], {
            'maximum': maximum,
            'basis': 'Highest planned weekly muscle-weighted volume across this cycle',
        })
        self.assertTrue(result['perWeek'])
        for week in result['perWeek']:
            self.assertEqual(set(week['leaves']), set(result['leafOrder']))
            for identity, leaf in week['leaves'].items():
                with self.subTest(week=week['n'], leaf=identity):
                    self.assertEqual(set(leaf['heat']), {'Both', 'Primary', 'Secondary'})
                    for heat in leaf['heat'].values():
                        self.assertEqual(set(heat), {'band', 'percent'})
                        self.assertIs(type(heat['band']), int)
                        self.assertGreaterEqual(heat['band'], 0)
                        self.assertLessEqual(heat['band'], 4)
                        self.assertIn(type(heat['percent']), (int, float))
                        self.assertGreaterEqual(heat['percent'], 0)
                        self.assertLessEqual(heat['percent'], 100)

    def _assert_heat_leaf(self, leaf, amounts, heat):
        # All expectations come from literal source coefficients and set counts.
        for field, expected in zip(('raw', 'w', 'd', 'primaryWeighted', 'secondaryWeighted'), amounts):
            self.assertAlmostEqual(leaf[field], expected, msg=field)
        for selection, (band, percent) in zip(('Both', 'Primary', 'Secondary'), heat):
            self.assertEqual(leaf['heat'][selection]['band'], band, selection)
            self.assertAlmostEqual(leaf['heat'][selection]['percent'], percent, msg=selection)

    def test_heat_fixture_has_literal_known_library_coefficients(self):
        library = json.loads((ROOT / 'data/movements.json').read_text(encoding='utf-8'))
        squat = next(row for row in library['movements']
                     if row['id'] == 'S.Main|high-bar squat')
        self.assertEqual(squat['name_en'], 'High-bar Squat')
        self.assertTrue(squat['plan_allowed'])
        self.assertEqual(squat['coef16'], {
            'chest': 0, 'delts_ant': 0, 'delts_lat': 0, 'delts_post': 0,
            'triceps': 0, 'upper_back': 0, 'lats': 0, 'erectors': .2,
            'quads': 1, 'hamstrings': .1, 'glutes': .6, 'adductors': .4,
            'biceps': 0, 'forearms': 0, 'core': .15, 'calves': .05,
        })

    def test_heat_shares_planned_weekly_maximum_across_weeks_modes_and_filters(self):
        plan = self._heat_plan((2, 8))
        snapshot = copy.deepcopy(plan)
        # Independent anchors: max = 8 sets × quads 1.0, not cycle total 10.
        expected = (
            {
                'quads': ((2, 2, 2, 2, 0), ((1, 25), (1, 25), (0, 0))),
                'glutes': ((1.2, 1.2, 0, 0, 1.2), ((1, 15), (0, 0), (1, 15))),
                'adductors': ((.8, .8, 0, 0, .8), ((1, 10), (0, 0), (1, 10))),
                'erectors': ((.4, .4, 0, 0, 0), ((1, 5), (0, 0), (0, 0))),
                'chest': ((0, 0, 0, 0, 0), ((0, 0), (0, 0), (0, 0))),
            },
            {
                'quads': ((8, 8, 8, 8, 0), ((4, 100), (4, 100), (0, 0))),
                'glutes': ((4.8, 4.8, 0, 0, 4.8), ((3, 60), (0, 0), (3, 60))),
                'adductors': ((3.2, 3.2, 0, 0, 3.2), ((2, 40), (0, 0), (2, 40))),
                'erectors': ((1.6, 1.6, 0, 0, 0), ((1, 20), (0, 0), (0, 0))),
                'chest': ((0, 0, 0, 0, 0), ((0, 0), (0, 0), (0, 0))),
            },
        )
        ignored_logs = {'1|A|1': {'sets': 20, 'reps': 5, 'load': 100}}
        for mode, logs in (('plan', {}), ('log', {}), ('plan', ignored_logs)):
            with self.subTest(mode=mode, logs=bool(logs)):
                result = analyze(plan, logs, mode)
                self._assert_heat_contract(result, 8)
                self.assertEqual([week['n'] for week in result['perWeek']], [1, 2])
                self.assertEqual(result['cycle']['total'], 10)
                for week, anchors in zip(result['perWeek'], expected):
                    for identity, (amounts, heat) in anchors.items():
                        with self.subTest(week=week['n'], leaf=identity):
                            self._assert_heat_leaf(week['leaves'][identity], amounts, heat)
        self.assertEqual(plan, snapshot)

    def test_heat_logged_primary_secondary_use_the_same_planned_denominator(self):
        plan = self._heat_plan((2, 8))
        logs = {'1|A|1': {'sets': 4, 'reps': 5, 'load': 100}}
        result = analyze(plan, logs, 'log')
        self._assert_heat_contract(result, 8)
        leaves = result['perWeek'][0]['leaves']
        self._assert_heat_leaf(leaves['quads'], (4, 4, 4, 4, 0),
                               ((2, 50), (2, 50), (0, 0)))
        self._assert_heat_leaf(leaves['glutes'], (2.4, 2.4, 0, 0, 2.4),
                               ((2, 30), (0, 0), (2, 30)))
        self._assert_heat_leaf(leaves['adductors'], (1.6, 1.6, 0, 0, 1.6),
                               ((1, 20), (0, 0), (1, 20)))
        self._assert_heat_leaf(leaves['erectors'], (.8, .8, 0, 0, 0),
                               ((1, 10), (0, 0), (0, 0)))

    def test_heat_saturates_only_visualization_not_actual_volume_or_planned_maximum(self):
        plan = self._heat_plan((2, 8))
        logs = {'1|A|1': {'sets': 20, 'reps': 5, 'load': 100}}
        snapshot, log_snapshot = copy.deepcopy(plan), copy.deepcopy(logs)
        result = analyze(plan, logs, 'log')
        self._assert_heat_contract(result, 8)
        self.assertEqual(result['perWeek'][0]['total'], 20)
        self.assertEqual(result['cycle']['total'], 28)
        leaves = result['perWeek'][0]['leaves']
        self._assert_heat_leaf(leaves['quads'], (20, 20, 20, 20, 0),
                               ((4, 100), (4, 100), (0, 0)))
        self._assert_heat_leaf(leaves['glutes'], (12, 12, 0, 0, 12),
                               ((4, 100), (0, 0), (4, 100)))
        self._assert_heat_leaf(leaves['adductors'], (8, 8, 0, 0, 8),
                               ((4, 100), (0, 0), (4, 100)))
        self._assert_heat_leaf(leaves['erectors'], (4, 4, 0, 0, 0),
                               ((2, 50), (0, 0), (0, 0)))
        for identity, amounts in (('quads', (28, 28, 28, 28, 0)),
                                  ('glutes', (16.8, 16.8, 0, 0, 16.8))):
            for field, expected in zip(('raw', 'w', 'd', 'primaryWeighted', 'secondaryWeighted'), amounts):
                self.assertAlmostEqual(result['cycle']['leaves'][identity][field], expected)
        self.assertEqual(plan, snapshot)
        self.assertEqual(logs, log_snapshot)

    def test_heat_zero_planned_maximum_stays_zero_even_with_nonzero_actuals(self):
        plan = self._heat_plan((0, 0))
        logs = {'1|A|1': {'sets': 20, 'reps': 5, 'load': 100}}
        for mode, records, total in (('plan', {}, 0), ('log', {}, 0),
                                      ('plan', logs, 0), ('log', logs, 20)):
            with self.subTest(mode=mode, logs=bool(records)):
                result = analyze(plan, records, mode)
                self._assert_heat_contract(result, 0)
                self.assertEqual(result['cycle']['total'], total)
                for week in result['perWeek']:
                    for leaf in week['leaves'].values():
                        self.assertEqual(leaf['heat'], {
                            'Both': {'band': 0, 'percent': 0},
                            'Primary': {'band': 0, 'percent': 0},
                            'Secondary': {'band': 0, 'percent': 0},
                        })
                self._assert_heat_leaf(result['perWeek'][0]['leaves']['quads'],
                                       (total, total, total, total, 0),
                                       ((0, 0), (0, 0), (0, 0)))

    def test_heat_ceil_band_boundaries_and_both_uses_unrounded_raw(self):
        plan = self._heat_plan((0, 1, 2, 3, 4, 5, 6, 7, 8))
        result = analyze(plan)
        self._assert_heat_contract(result, 8)
        expected = ((0, 0), (1, 12.5), (1, 25), (2, 37.5), (2, 50),
                    (3, 62.5), (3, 75), (4, 87.5), (4, 100))
        self.assertEqual(len(result['perWeek']), 9)
        for count, (week, heat) in enumerate(zip(result['perWeek'], expected)):
            with self.subTest(sets=count):
                self._assert_heat_leaf(week['leaves']['quads'], (count, count, count, count, 0),
                                       (heat, heat, (0, 0)))
        # 1 set × calves .05 / 8 = .625%; rounded display w=.1 is not the numerator.
        self._assert_heat_leaf(result['perWeek'][1]['leaves']['calves'], (.05, .1, 0, 0, 0),
                               ((1, .625), (0, 0), (0, 0)))

    def test_heat_supports_eight_and_seventeen_weeks_with_peak_in_the_last_week(self):
        for count, planned_total, actual_total in ((8, 22, 40), (17, 40, 58)):
            plan = self._heat_plan((2,) * (count - 1) + (8,))
            logs = {'1|A|1': {'sets': 20, 'reps': 5, 'load': 100}}
            for mode, records, total in (('plan', {}, planned_total), ('log', logs, actual_total)):
                with self.subTest(weeks=count, mode=mode):
                    result = analyze(plan, records, mode)
                    self._assert_heat_contract(result, 8)
                    self.assertEqual([week['n'] for week in result['perWeek']], list(range(1, count + 1)))
                    self.assertEqual(result['cycle']['total'], total)
                    self._assert_heat_leaf(result['perWeek'][-1]['leaves']['quads'], (8, 8, 8, 8, 0),
                                           ((4, 100), (4, 100), (0, 0)))
                    for index, week in enumerate(result['perWeek'][:-1]):
                        amount, heat = (20, (4, 100)) if mode == 'log' and index == 0 else (2, (1, 25))
                        self._assert_heat_leaf(week['leaves']['quads'], (amount, amount, amount, amount, 0),
                                               (heat, heat, (0, 0)))


if __name__ == '__main__':
    unittest.main()
