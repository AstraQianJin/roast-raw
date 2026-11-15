"""The calendar projection is a read of canonical sessions: no copies, no rewrites."""

import copy
import json
import unittest
from pathlib import Path

from server.app.calendar import calendar_days

ROOT = Path(__file__).resolve().parents[1]
REAL = json.loads((ROOT / 'data' / 'plan.json').read_text(encoding='utf-8'))


def plan_doc():
    return copy.deepcopy(REAL)


class CalendarProjectionTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_doc()

    def test_half_open_range_covers_start_and_never_the_end(self):
        days = calendar_days([self.plan], {}, '2026-11-23', '2026-11-30', today='2027-06-01')
        self.assertEqual({day['date'] for day in days['days']}, {'2026-11-23', '2026-11-25', '2026-11-27', '2026-11-28'})
        short = calendar_days([self.plan], {}, '2026-11-23', '2026-11-29', today='2027-06-01')
        self.assertNotIn('2026-11-29', {day['date'] for day in short['days']})

    def test_every_day_carries_its_session_facts(self):
        days = calendar_days([self.plan], {}, '2026-11-23', '2026-11-24', today='2027-06-01')['days']
        day = days[0]
        self.assertEqual(day['day'], 'A')
        self.assertEqual(day['week'], 1)
        self.assertIn('SQUAT', day['title'])
        self.assertEqual(sorted(day['rows'], key=lambda row: row['seq'])[0]['seq'], 1)
        self.assertEqual(len(day['rows']), day['rowCount'])
        self.assertEqual(day['prescribedSets'], sum(row['sets'] for row in day['rows']))

    def test_status_is_decided_by_actual_sets_then_arrival(self):
        day = calendar_days([self.plan], {}, '2026-11-23', '2026-11-24', today='2027-06-01')['days'][0]
        self.assertEqual(day['status'], 'missed', 'a past day with no log is missed, not planned')
        future_date = self.plan['workouts'][-1]['date']
        future = calendar_days([self.plan], {}, future_date, future_date[:8] + '31', today='2026-11-15')['days']
        self.assertTrue(future, 'the chosen day carries a session')
        self.assertEqual(future[0]['status'], 'planned')
        partial = {f"1|A|{row['seq']}": {'sets': 1} for row in day['rows']}
        logged = calendar_days([self.plan], {'rpl-raw-2026-11-23': partial}, '2026-11-23', '2026-11-24', today='2027-06-01')['days'][0]
        self.assertEqual(logged['status'], 'completed')
        self.assertEqual(logged['loggedSets'], day['rowCount'])
        zeros = {f"1|A|{row['seq']}": {'sets': 0} for row in day['rows']}
        skipped = calendar_days([self.plan], {'rpl-raw-2026-11-23': zeros}, '2026-11-23', '2026-11-24', today='2027-06-01')['days'][0]
        self.assertEqual(skipped['status'], 'skipped', 'an explicit zero is a skip, not a missed day')
        self.assertEqual(skipped['loggedSets'], 0)

    def test_two_cycles_project_into_one_range(self):
        archived = plan_doc()
        archived['meta']['planId'] = 'rpl-old'
        for week in archived['weeks']:
            for key in ('dateStart', 'dateEnd'):
                week[key] = week[key].replace('2026', '2025').replace('2027', '2026')
        for row in archived['workouts']:
            row['date'] = row['date'].replace('2026', '2025').replace('2027', '2026')
        days = calendar_days([archived, self.plan], {'rpl-old': {}}, '2025-11-24', '2026-11-26', today='2026-11-15')
        cycles = {day['cycleId'] for day in days['days']}
        self.assertEqual(cycles, {'rpl-old', 'rpl-raw-2026-11-23'})
        self.assertEqual({day['cycleId'] for day in days['days'] if day['date'].startswith('2026-11-23')}, {'rpl-raw-2026-11-23'})

    def test_cycles_carry_their_spans_for_rest_and_blank_days(self):
        payload = calendar_days([self.plan], {}, '2026-11-01', '2026-12-01', today='2026-11-15')
        self.assertEqual(payload['cycles'], [{'id': 'rpl-raw-2026-11-23',
                                              'start': self.plan['meta']['startDate'],
                                              'end': self.plan['meta']['endDate']}])

    def test_empty_range_and_bad_range(self):
        empty = calendar_days([self.plan], {}, '2026-12-01', '2026-12-02', today='2026-11-15')
        self.assertEqual(empty['days'], [])
        self.assertEqual(empty['sessions'], 0)
        with self.assertRaises(ValueError):
            calendar_days([self.plan], {}, '2026-12-02', '2026-12-01', today='2026-11-15')


if __name__ == '__main__':
    unittest.main()
