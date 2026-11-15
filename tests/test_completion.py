"""R5 completion policy: elapsed denominator, credit capped at the plan, three classes separate."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.stats.completion import completion  # noqa: E402
from server.app.stats.engine import analyze  # noqa: E402

REAL = json.loads((ROOT / 'data' / 'plan.json').read_text(encoding='utf-8'))


def _row(bucket, week, seq, date, sets, load):
    row = copy.deepcopy(next(item for item in REAL['workouts']
                             if item['bucket'] == bucket and (item.get('loadKg') is not None or bucket == 'accessory')))
    row.update({'week': week, 'day': 'A' if week == 1 else 'B', 'seq': seq, 'date': date,
                'sets': sets, 'reps': 3, 'loadKg': load})
    return row


MAIN = _row('main', 1, 1, '2026-01-05', 5, 100)
VAR = _row('sbdVar', 1, 2, '2026-01-05', 3, 80)
ACC = _row('accessory', 1, 3, '2026-01-05', 4, None)
MAIN_W2 = _row('main', 2, 1, '2026-01-12', 5, 110)

def _week(n, start, end):
    meta = copy.deepcopy(REAL['weeks'][n - 1])
    meta.update({'n': n, 'kind': 'accumulation', 'dateStart': start, 'dateEnd': end})
    return meta


PLAN = {
    'meta': {'startDate': '2026-01-05', 'endDate': '2026-01-18', 'sessions': 2, 'tonnageBasis': 'test'},
    'prescription': copy.deepcopy(REAL.get('prescription', {})),
    'weeks': [_week(1, '2026-01-05', '2026-01-11'), _week(2, '2026-01-12', '2026-01-18')],
    'workouts': [MAIN, VAR, ACC, MAIN_W2],
}
KEY = lambda week, day, seq: f'{week}|{day}|{seq}'  # noqa: E731


class CompletionPolicyTests(unittest.TestCase):
    def test_future_sessions_never_enter_the_denominator(self):
        early = completion(PLAN, {}, today='2026-01-05')
        self.assertEqual(early['classes']['main']['planned'], 5)
        self.assertEqual(early['classes']['var']['planned'], 3)
        self.assertEqual(early['classes']['acc']['planned'], 4)
        self.assertEqual(early['sessions'], {'elapsed': 1, 'reviewed': 0, 'untouched': 1, 'ahead': 0})
        later = completion(PLAN, {}, today='2026-01-12')
        self.assertEqual(later['classes']['main']['planned'], 10, 'the week-2 main sets arrive with week 2')

    def test_no_arrived_session_reports_unknown_not_zero(self):
        before = completion(PLAN, {}, today='2025-12-31')
        self.assertEqual(before['sessions']['elapsed'], 0)
        for key in ('main', 'var', 'acc'):
            self.assertIsNone(before[key])
        self.assertIsNone(before['classes']['main']['pct'])

    def test_over_prescription_is_capped_and_the_surplus_is_extra(self):
        logs = {KEY(1, 'A', 1): {'sets': 8, 'reps': 3, 'load': 100},
                KEY(1, 'A', 2): {'sets': 3, 'reps': 5, 'load': 80},
                KEY(1, 'A', 3): {'sets': 2, 'reps': 10, 'load': None}}
        result = completion(PLAN, logs, today='2026-01-05')
        self.assertEqual(result['credited'], {'main': 5, 'var': 3, 'acc': 2})
        self.assertEqual(result['extra'], {'main': 3, 'var': 0, 'acc': 0})
        self.assertEqual(result['actual'], {'main': 8, 'sbdVar': 3, 'nonSbdVar': 0, 'accessory': 2})
        # 5/5 main, 3/3 variation, 2/4 accessory — computed by hand, not by the engine.
        self.assertEqual([result['main'], result['var'], result['acc']], [100.0, 100.0, 50.0])

    def test_explicit_zero_is_reviewed_and_never_a_completion(self):
        logs = {KEY(1, 'A', 3): {'sets': 0, 'reps': 0, 'load': None}}
        result = completion(PLAN, logs, today='2026-01-05')
        self.assertEqual(result['reviewedSessions'], ['1|A'])
        self.assertEqual(result['untouchedSessions'], [])
        self.assertEqual(result['classes']['acc'], {'planned': 4, 'credited': 0, 'extra': 0, 'pct': 0.0})
        self.assertEqual(result['sessions']['reviewed'], 1)

    def test_untouched_session_stays_out_of_the_reviewed_list(self):
        result = completion(PLAN, {}, today='2026-01-05')
        self.assertEqual(result['untouchedSessions'], ['1|A'])
        self.assertEqual(result['reviewedSessions'], [])

    def test_work_logged_ahead_is_visible_but_uncounted(self):
        logs = {KEY(2, 'B', 1): {'sets': 5, 'reps': 2, 'load': 110}}
        result = completion(PLAN, logs, today='2026-01-05')
        self.assertEqual(result['actual']['main'], 5)
        self.assertEqual(result['credited']['main'], 0)
        self.assertEqual(result['sessions']['ahead'], 1)
        self.assertEqual(result['main'], 0.0, 'the only elapsed main work is unlogged')
        ahead_row = next(row for row in result['rows'] if row['ahead'])
        self.assertEqual(ahead_row['counted'], 0)

    def test_three_classes_stay_separate(self):
        logs = {KEY(1, 'A', 1): {'sets': 5, 'reps': 3, 'load': 100}}
        result = completion(PLAN, logs, today='2026-01-05')
        self.assertEqual(result['main'], 100.0)
        self.assertEqual(result['var'], 0.0)
        self.assertEqual(result['acc'], 0.0)
        self.assertNotIn('overall', result, 'no blended total is produced here')

    def test_analysis_mode_plan_ignores_logs_and_log_mode_counts_them(self):
        logs = {KEY(1, 'A', 1): {'sets': 3, 'reps': 3, 'load': 100}}
        plan_only = analyze(copy.deepcopy(PLAN), logs, 'plan', today='2026-01-05')
        logged = analyze(copy.deepcopy(PLAN), logs, 'log', today='2026-01-05')
        self.assertEqual(plan_only['completion']['actual'],
                         dict.fromkeys(['main', 'sbdVar', 'nonSbdVar', 'accessory'], 0))
        self.assertEqual(logged['completion']['main'], 60.0, '3 of 5 prescribed main sets')


if __name__ == '__main__':
    unittest.main()
