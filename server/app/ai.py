"""DeepSeek outlook/chat integration: server-side only, quota pre-reserved, no auto-retry."""

import json
import os
from datetime import datetime, timedelta, timezone

import httpx

API_URL = 'https://api.deepseek.com/chat/completions'
MODEL = 'deepseek-chat'
TIERS = ('aggressive', 'stable', 'conservative')

OUTLOOK_INSTRUCTIONS = (
    'You are a powerlifting programming assistant for a single athlete. '
    'Given the cycle review JSON and the athlete questionnaire, propose next-cycle outlooks in three tiers. '
    'Reply with STRICT JSON only, no markdown fences, shaped exactly as: '
    '{"aggressive":{"summary":"...","adjustments":["..."]},'
    '"stable":{"summary":"...","adjustments":["..."]},'
    '"conservative":{"summary":"...","adjustments":["..."]}}. '
    'Each summary is 2-4 sentences in English; adjustments are 3-6 concrete bullet strings '
    '(loads in kg, sets, reps, RPE). Base every claim on the provided data; do not invent history.')

CHAT_SYSTEM = (
    'You are a powerlifting programming assistant refining a next-cycle outlook for one athlete. '
    'Answer in English, concise and concrete (kg, sets, reps, RPE). '
    'You advise only; the final plan JSON is generated externally and imported by the athlete.')


def beijing_day():
    return datetime.now(timezone(timedelta(hours=8))).date().isoformat()


def configured():
    return bool(os.environ.get('DEEPSEEK_API_KEY', ''))


def build_outlook_prompt(review, questionnaire):
    parts = [OUTLOOK_INSTRUCTIONS, '', 'CYCLE REVIEW JSON:',
             json.dumps(review, ensure_ascii=False, separators=(',', ':'))]
    if questionnaire and questionnaire.get('status') != 'empty':
        parts += ['', f"QUESTIONNAIRE ({questionnaire['status']}):",
                  json.dumps(questionnaire['payload'], ensure_ascii=False, separators=(',', ':'))]
    else:
        parts += ['', 'QUESTIONNAIRE: not filled in; note the uncertainty in each summary.']
    return '\n'.join(parts)


def call_deepseek(messages):
    key = os.environ.get('DEEPSEEK_API_KEY', '')
    response = httpx.post(API_URL, timeout=90, trust_env=False,
                          headers={'Authorization': f'Bearer {key}'},
                          json={'model': MODEL, 'messages': messages, 'temperature': 0.4,
                                'max_tokens': 2000, 'stream': False})
    response.raise_for_status()
    body = response.json()
    content = body['choices'][0]['message']['content']
    if not isinstance(content, str) or not content.strip():
        raise ValueError('DeepSeek returned an empty completion')
    return content


def parse_outlook(content):
    text = content.strip()
    if text.startswith('```'):
        text = text.strip('`')
        if text.startswith('json'):
            text = text[4:]
    data = json.loads(text)
    if not isinstance(data, dict) or set(data) != set(TIERS):
        raise ValueError('Outlook must contain exactly aggressive/stable/conservative tiers')
    for tier in TIERS:
        entry = data[tier]
        if (not isinstance(entry, dict) or not isinstance(entry.get('summary'), str)
                or not entry['summary'].strip()
                or not isinstance(entry.get('adjustments'), list)
                or not all(isinstance(item, str) and item.strip() for item in entry['adjustments'])):
            raise ValueError(f'Tier {tier} needs a summary string and adjustment strings')
    return data