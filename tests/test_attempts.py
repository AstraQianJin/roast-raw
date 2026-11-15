"""Competition attempt contracts: 92.5/100/102.5% floored to 2.5 kg, sequential confirmation,
miss repeats the same load, a good lift never lowers the next suggestion."""

import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from test_api import GeneratedPlanCase, PLAN_PATH, open_db
from server.app.questionnaire import skeleton
from server.app.stats.attempts import floor25, next_attempt, suggested


class AttemptMathTests(unittest.TestCase):
    def test_factors_floor_to_2_5(self):
        self.assertEqual(floor25(141.0625), 140.0)
        self.assertEqual(floor25(156.3125), 155.0)
        self.assertEqual(suggested(152.5), [140.0, 152.5, 155.0])
        self.assertEqual(suggested(97.5), [90.0, 97.5, 97.5])
        self.assertEqual(suggested(177.5), [162.5, 177.5, 180.0])

    def test_miss_repeats_same_load(self):
        self.assertEqual(next_attempt(152.5, 140.0, 'miss', 2), 140.0)
        self.assertEqual(next_attempt(152.5, 152.5, 'miss', 3), 152.5)

    def test_good_lift_never_decreases_and_jumps_at_least_2_5(self):
        self.assertEqual(next_attempt(152.5, 140.0, 'good', 2), 152.5)
        self.assertEqual(next_attempt(152.5, 150.0, 'good', 2), 152.5)
        self.assertEqual(next_attempt(97.5, 97.5, 'good', 3), 100.0)

    def test_unconfirmed_previous_falls_back_to_base(self):
        self.assertEqual(next_attempt(152.5, 140.0, None, 2), 152.5)


class AttemptAPITests(GeneratedPlanCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='roastraw-attempts-')
        self.addCleanup(temporary.cleanup)
        self.db_path = Path(temporary.name) / 'attempts.sqlite3'
        with patch.dict(os.environ, {'RR_DB_PATH': str(self.db_path), 'RR_ACCESS_PASSWORD': ''}):
            from server.app.main import create_app
            self.app = create_app(db_path=self.db_path, plan_path=PLAN_PATH)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.store = self.app.state.store
        self.cycle_id = self.seed['meta']['planId']

    def state(self):
        response = self.client.get('/api/attempts', params={'cycle_id': self.cycle_id})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def put(self, lift, number, load, result=None, expected=200):
        response = self.client.put('/api/attempts', json={
            'cycle_id': self.cycle_id, 'lift': lift, 'number': number, 'load': load, 'result': result})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json() if expected == 200 else None

    def test_default_state_uses_plan_profile_references(self):
        state = self.state()
        self.assertEqual(state['cycle_id'], self.cycle_id)
        self.assertFalse(state['competition']['competition'])
        squat = state['lifts']['squat']
        self.assertEqual(squat['reference'], {'reference': 152.5, 'source': 'plan-profile'})
        self.assertEqual(squat['suggested'], [140.0, 152.5, 155.0])
        self.assertEqual(squat['next'], [140.0, 152.5, 155.0])
        self.assertEqual(squat['attempts'], [None, None, None])
        self.assertEqual(state['lifts']['bench']['suggested'], [90.0, 97.5, 97.5])
        self.assertEqual(state['lifts']['deadlift']['suggested'], [162.5, 177.5, 180.0])

    def test_attempts_must_be_confirmed_in_order(self):
        self.put('squat', 2, 152.5, 'good', expected=409)
        self.put('squat', 1, 140.0)
        self.put('squat', 2, 152.5, 'good', expected=409)
        self.put('squat', 1, 140.0, 'good')
        self.put('squat', 2, 152.5, 'good')

    def test_load_must_be_a_multiple_of_2_5(self):
        self.put('squat', 1, 141.0, 'good', expected=422)
        self.put('squat', 1, 0, 'good', expected=422)
        self.put('squat', 1, 502.5, 'good', expected=422)

    def test_miss_keeps_next_suggestion_at_the_same_load(self):
        self.put('squat', 1, 140.0, 'miss')
        self.assertEqual(self.state()['lifts']['squat']['next'][1], 140.0)
        self.put('squat', 2, 140.0, 'good')
        self.assertEqual(self.state()['lifts']['squat']['next'][2], 155.0)

    def test_good_lift_raises_a_low_base_to_previous_plus_2_5(self):
        self.put('bench', 1, 90.0, 'good')
        self.put('bench', 2, 100.0, 'good')
        self.assertEqual(self.state()['lifts']['bench']['next'][2], 102.5)

    def test_questionnaire_reference_and_competition_flag_override_profile(self):
        payload = skeleton()
        payload['level']['sbd1rm'] = {'squat': 160.0, 'bench': 100.0, 'deadlift': 190.0}
        payload['goal']['type'] = 'competition'
        payload['schedule']['competitionDate'] = '2027-02-13'
        self.store.save_questionnaire(self.cycle_id, payload, 'complete')
        state = self.state()
        self.assertTrue(state['competition']['competition'])
        self.assertEqual(state['competition']['date'], '2027-02-13')
        self.assertEqual(state['lifts']['squat']['reference'], {'reference': 160.0, 'source': 'questionnaire'})
        self.assertEqual(state['lifts']['squat']['suggested'], [147.5, 160.0, 162.5])

    def test_attempt_writes_are_journalled_and_persist_across_restart(self):
        self.put('deadlift', 1, 162.5, 'good')
        with open_db(self.db_path) as db:
            rows = db.execute("SELECT kind,key,payload FROM records_journal WHERE cycle_id=?",
                              (self.cycle_id,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 'attempt')
        self.assertEqual(rows[0][1], 'deadlift|1')
        self.assertEqual(json.loads(rows[0][2])['load'], 162.5)
        with patch.dict(os.environ, {'RR_DB_PATH': str(self.db_path), 'RR_ACCESS_PASSWORD': ''}):
            from server.app.main import create_app
            restarted = TestClient(create_app(db_path=self.db_path, plan_path=PLAN_PATH))
        with restarted:
            state = restarted.get('/api/attempts', params={'cycle_id': self.cycle_id}).json()
        self.assertEqual(state['lifts']['deadlift']['attempts'][0]['result'], 'good')

    def test_archived_cycle_rejects_attempt_writes(self):
        plan = copy.deepcopy(self.seed)
        plan['meta']['planId'] = 'old-cycle'
        with open_db(self.db_path) as db:
            db.execute('INSERT INTO cycles(id,name,start_date,end_date,status,schema_version,account_id) VALUES(?,?,?,?,?,?,(SELECT account_id FROM cycles ORDER BY rowid LIMIT 1))',
                       ('old-cycle', 'Old', plan['meta']['startDate'], plan['meta']['endDate'],
                        'archived', plan['schemaVersion']))
            account = db.execute('SELECT account_id FROM cycles LIMIT 1').fetchone()[0]
            db.execute('INSERT INTO plans(account_id,id,cycle_id,json,version,created_at) VALUES(?,?,?,?,?,?)',
                       (account, 'old-cycle', 'old-cycle', json.dumps(plan), plan['schemaVersion'],
                        '2026-11-01T00:00:00+00:00'))
        response = self.client.put('/api/attempts', json={
            'cycle_id': 'old-cycle', 'lift': 'squat', 'number': 1, 'load': 140.0, 'result': 'good'})
        self.assertEqual(response.status_code, 409)

    def test_unknown_cycle_and_bad_inputs_reject(self):
        self.assertEqual(self.client.get('/api/attempts', params={'cycle_id': 'missing'}).status_code, 404)
        self.assertEqual(self.client.put('/api/attempts', json={
            'cycle_id': self.cycle_id, 'lift': 'curl', 'number': 1, 'load': 50.0}).status_code, 422)
        self.assertEqual(self.client.put('/api/attempts', json={
            'cycle_id': self.cycle_id, 'lift': 'squat', 'number': 4, 'load': 140.0}).status_code, 422)


if __name__ == '__main__':
    unittest.main()