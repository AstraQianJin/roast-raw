"""DeepSeek integration contracts: quota pre-reservation, failure counting, no auto-retry, export."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.main import create_app

PLAN_PATH = ROOT / 'data' / 'plan.json'
CYCLE_ID = json.loads(PLAN_PATH.read_text(encoding='utf-8'))['meta']['planId']
FAKE_KEY = 'sk-test-fake-key-000'

GOOD_OUTLOOK = {tier: {'summary': f'{tier} summary sentence.', 'adjustments': ['Squat +2.5 kg', 'Bench RPE 8']}
                for tier in ('aggressive', 'stable', 'conservative')}


def deepseek_response(content):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {'choices': [{'message': {'content': content}}]}
    return response


class AiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = patch.dict(os.environ, {'DEEPSEEK_API_KEY': FAKE_KEY, 'RR_ACCESS_PASSWORD': ''})
        self.env.start()
        self.addCleanup(self.env.stop)
        app = create_app(db_path=Path(self.folder.name) / 'ai.sqlite3', plan_path=PLAN_PATH)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.store = app.state.store

    def test_unconfigured_outlook_503_without_quota(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': ''}):
            result = self.client.post('/api/ai/outlook', json={'cycle_id': CYCLE_ID})
            self.assertEqual(result.status_code, 503)
            self.assertIn('external AI', result.json()['detail'])
            status = self.client.get('/api/ai/status', params={'cycle_id': CYCLE_ID}).json()
            self.assertFalse(status['configured'])
            self.assertEqual(status['quota']['used'], 0)

    def test_outlook_success_counts_once_and_parses_tiers(self):
        with patch('server.app.ai.httpx.post', return_value=deepseek_response(json.dumps(GOOD_OUTLOOK))) as post:
            result = self.client.post('/api/ai/outlook', json={'cycle_id': CYCLE_ID})
            self.assertEqual(result.status_code, 200, result.text)
            body = result.json()
            self.assertEqual(set(body['result']), {'aggressive', 'stable', 'conservative'})
            self.assertEqual(body['quota']['used'], 1)
            self.assertEqual(post.call_count, 1)
            self.assertNotIn(FAKE_KEY, result.text)
            record = self.client.get(f"/api/ai/call/{body['id']}").json()
            self.assertEqual(record['status'], 'ok')
            self.assertEqual(record['kind'], 'outlook')
            self.assertIn('CYCLE REVIEW JSON', record['prompt'])

    def test_failure_counts_and_never_auto_retries(self):
        import httpx
        with patch('server.app.ai.httpx.post', side_effect=httpx.ConnectError('boom')) as post:
            result = self.client.post('/api/ai/outlook', json={'cycle_id': CYCLE_ID})
            self.assertEqual(result.status_code, 502)
            self.assertEqual(post.call_count, 1)
            status = self.client.get('/api/ai/status', params={'cycle_id': CYCLE_ID}).json()
            self.assertEqual(status['quota']['used'], 1)
            self.assertEqual(status['calls'][0]['status'], 'error')
            self.assertNotIn(FAKE_KEY, result.text)

    def test_malformed_outlook_is_a_counted_failure(self):
        with patch('server.app.ai.httpx.post', return_value=deepseek_response('{"aggressive":{}}')):
            result = self.client.post('/api/ai/outlook', json={'cycle_id': CYCLE_ID})
            self.assertEqual(result.status_code, 502)
            self.assertEqual(self.client.get('/api/ai/status', params={'cycle_id': CYCLE_ID}).json()['quota']['used'], 1)

    def test_daily_quota_blocks_21st_call_site_wide(self):
        from server.app import ai
        day = ai.beijing_day()
        for index in range(20):
            self.store.reserve_ai_call(CYCLE_ID, day, 'chat', 'p', [])
        with patch('server.app.ai.httpx.post') as post:
            result = self.client.post('/api/ai/outlook', json={'cycle_id': CYCLE_ID})
            self.assertEqual(result.status_code, 429)
            post.assert_not_called()
        quota = self.client.get('/api/ai/status', params={'cycle_id': CYCLE_ID}).json()['quota']
        self.assertEqual(quota['used'], 20)
        self.assertEqual(quota['remaining'], 0)
        self.assertEqual(quota['date'], day)

    def test_chat_keeps_conversation_and_counts(self):
        with patch('server.app.ai.httpx.post', return_value=deepseek_response('Add 2.5 kg to squat.')) as post:
            result = self.client.post('/api/ai/chat', json={
                'cycle_id': CYCLE_ID, 'message': 'Make stable tier heavier',
                'conversation': [{'role': 'user', 'content': 'hi'}, {'role': 'assistant', 'content': 'hello'}]})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['result'], 'Add 2.5 kg to squat.')
            sent = post.call_args.kwargs['json']['messages']
            self.assertEqual(sent[0]['role'], 'system')
            self.assertEqual(sent[-1], {'role': 'user', 'content': 'Make stable tier heavier'})
            self.assertEqual(post.call_args.kwargs['json']['model'], 'deepseek-chat')

    def test_export_without_key_bundles_review_questionnaire_prompt(self):
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': ''}):
            result = self.client.get('/api/ai/export', params={'cycle_id': CYCLE_ID})
            self.assertEqual(result.status_code, 200)
            self.assertIn('attachment', result.headers['content-disposition'])
            bundle = result.json()
            self.assertIn('plan', bundle['review'])
            self.assertEqual(bundle['questionnaire']['status'], 'empty')
            self.assertIn('aggressive', bundle['prompt'])
            self.assertNotIn(FAKE_KEY, result.text)

    def test_ai_writes_rejected_for_unknown_cycle(self):
        result = self.client.post('/api/ai/outlook', json={'cycle_id': 'missing'})
        self.assertEqual(result.status_code, 404)

    def test_upgrade_ai_idempotent_and_versioned(self):
        self.store.upgrade_ai()
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.store.path)) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 6)


if __name__ == '__main__':
    unittest.main()