"""One calculation for every headline number (owner ruling 2026-11-15).

Rows are expanded row by row; main / variation / accessory are reported separately
and summed; tonnage is the row's own segment-weighted figure; the rounding chain
(cycle 0.1 t, week and block 0.01 t) reconciles.
"""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.stats.engine import analyze  # noqa: E402
from server.app.stats.totals import (  # noqa: E402
    day, display_chain, role_of, row_facts, round1, round2, session_totals, totals,
)

REAL = json.loads((ROOT / 'data' / 'plan.json').read_text(encoding='utf-8'))


def _row(bucket, week, seq, sets, load, tonnage=None, reps=3, lift='S'):
    row = copy.deepcopy(next(item for item in REAL['workouts'] if item['bucket'] == bucket))
    row.update({'week': week, 'day': 'A', 'seq': seq, 'sets': sets, 'reps': reps, 'loadKg': load, 'lift': lift})
    row['tonnageKg'] = (load or 0) * reps * sets if tonnage is None else tonnage
    return row


def _week(n, block):
    meta = copy.deepcopy(REAL['weeks'][n - 1])
    meta.update({'n': n, 'blockId': block, 'kind': 'accumulation', 'sessions': 1})
    return meta


MAIN = _row('main', 1, 1, 4, 100, tonnage=400 * 3)
VAR = _row('sbdVar', 1, 2, 3, 80, tonnage=80 * 3 * 3)
ACC = _row('accessory', 1, 3, 4, None, tonnage=0)
MAIN_W2 = _row('main', 2, 1, 5, 90, tonnage=90 * 3 * 5)

PLAN = {
    'meta': {'startDate': '2026-01-05', 'endDate': '2026-01-18', 'sessions': 2, 'tonnageBasis': 'test'},
    'blocks': [{'id': 'B1', 'nameEn': 'Block one', 'cycleType': 'hyper'}],
    'weeks': [_week(1, 'B1'), _week(2, 'B1')],
    'workouts': [MAIN, VAR, ACC, MAIN_W2],
}


class RoleTest(unittest.TestCase):
    def test_three_classes_and_raw_buckets(self):
        result = session_totals([MAIN, VAR, ACC])
        self.assertEqual(result['sets'], {'main': 4, 'variation': 3, 'accessory': 4, 'total': 11})
        self.assertEqual(result['roles'], {'main': 4, 'sbdVar': 3, 'nonSbdVar': 0, 'accessory': 4})
        self.assertEqual(result['rows'], 3)

    def test_non_sbd_variation_is_reported_as_variation(self):
        row = copy.deepcopy(VAR)
        row['bucket'] = 'nonSbdVar'
        result = session_totals([row])
        self.assertEqual(result['sets']['variation'], row['sets'])
        self.assertEqual(result['sets']['total'], row['sets'])
        self.assertEqual(result['roles']['nonSbdVar'], row['sets'])

    def test_unknown_bucket_is_named_not_guessed(self):
        row = copy.deepcopy(MAIN)
        row['bucket'] = 'conditioning'
        with self.assertRaises(ValueError) as caught:
            role_of(row)
        self.assertIn('1|A|1', str(caught.exception))

    def test_explicit_zero_set_row_stays_a_row(self):
        zero = copy.deepcopy(ACC)
        zero['sets'] = 0
        result = session_totals([zero])
        self.assertEqual(result['sets']['total'], 0)
        self.assertEqual(result['rows'], 1)


class TonnageTest(unittest.TestCase):
    def test_plan_mode_trusts_the_row_figure(self):
        problem = copy.deepcopy(MAIN)
        problem['tonnageKg'] = 1100.0  # a segment-weighted figure that load × reps × sets cannot reproduce
        self.assertEqual(row_facts(problem)[2], 1100.0)

    def test_log_mode_uses_the_logged_work(self):
        log = {'load': 105.0, 'reps': 5, 'sets': 2}
        self.assertEqual(row_facts(MAIN, log, 'log')[1:], (2, 1050.0))
        accessory_log = {'load': 10.0, 'reps': 10, 'sets': 2}
        self.assertEqual(row_facts(ACC, accessory_log, 'log')[2], 0.0)

    def test_log_mode_without_a_log_still_counts_the_prescription(self):
        result = totals(PLAN, {}, 'log')
        self.assertEqual(result['cycle']['sets']['total'], 16)


class AggregateTest(unittest.TestCase):
    def test_week_block_cycle_add_up(self):
        result = totals(PLAN)
        self.assertEqual(result['cycle']['sets']['total'], 16)
        self.assertEqual([week['sets']['total'] for week in result['perWeek']], [11, 5])
        self.assertEqual(result['perBlock'][0]['sets']['total'], 16)
        self.assertEqual(result['cycle']['tonnageKg'], 400 * 3 + 80 * 3 * 3 + 0 + 90 * 3 * 5)

    def test_empty_week_is_not_invented(self):
        sparse = copy.deepcopy(PLAN)
        sparse['workouts'] = [MAIN_W2]
        result = totals(sparse)
        self.assertEqual([week['n'] for week in result['perWeek']], [2])
        self.assertIsNone(day(sparse, 1, 'A'))
        self.assertEqual(day(sparse, 2, 'A')['sets']['total'], 5)

    def test_lift_split_matches_the_register(self):
        result = totals(PLAN)
        self.assertEqual(result['perLift']['S'], {'main': 9, 'variation': 3, 'tonnageKg': 400 * 3 + 80 * 3 * 3 + 90 * 3 * 5})

    def test_analysis_reads_the_same_numbers(self):
        analysis = analyze(PLAN, {}, 'plan')
        result = totals(PLAN)
        self.assertEqual(analysis['cycle']['total'], result['cycle']['sets']['total'])
        self.assertEqual(analysis['cycle']['tonnageKg'], round1(result['cycle']['tonnageKg']))
        self.assertEqual(analysis['cycle']['auxSets'], result['cycle']['sets']['accessory'])
        self.assertEqual([week['total'] for week in analysis['perWeek']], [week['sets']['total'] for week in result['perWeek']])
        self.assertEqual(analysis['perDay'], result['perDay'])

    def test_rounding(self):
        self.assertEqual(round1(139.55), 139.6)
        self.assertEqual(round1(139.45), 139.5)
        self.assertEqual(round2(16.234), 16.23)


class RealCycleTest(unittest.TestCase):
    """The committed plan, checked against hand sums of its own rows."""

    def test_every_headline_matches_the_rows(self):
        rows = REAL['workouts']
        hand_total = sum(row['sets'] for row in rows)
        hand_tonnage = sum(row['tonnageKg'] for row in rows)
        result = totals(REAL)
        self.assertEqual(result['cycle']['sets']['total'], hand_total)
        self.assertEqual(result['cycle']['tonnageKg'], round(hand_tonnage, 4))
        for week in REAL['weeks']:
            week_rows = [row for row in rows if row['week'] == week['n']]
            entry = next(item for item in result['perWeek'] if item['n'] == week['n'])
            self.assertEqual(entry['sets']['total'], sum(row['sets'] for row in week_rows))
            self.assertEqual(entry['tonnageKg'], round(sum(row['tonnageKg'] for row in week_rows), 4))

    def test_rounding_chain_reconciles(self):
        chain = display_chain(REAL)
        self.assertTrue(chain['blocksReconcile'])
        self.assertTrue(chain['weeksReconcile'])
        self.assertEqual(chain['cycleT'], 139.6)
        self.assertEqual(sum(chain['blockT']), 139.57)

    def test_log_mode_agrees_with_the_engine(self):
        logs = {'1|A|2': {'sets': 2, 'load': 110.5, 'reps': 6}}
        analysis = analyze(REAL, logs, 'log')
        result = totals(REAL, logs, 'log')
        self.assertEqual(analysis['cycle']['total'], result['cycle']['sets']['total'])
        self.assertEqual(analysis['cycle']['tonnageKg'], round1(result['cycle']['tonnageKg']))


if __name__ == '__main__':
    unittest.main()
