import copy
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


if __name__ == '__main__':
    unittest.main()
