"""Отчёт организации OpenAI за сегодня: /v1/organization/usage/completions и /costs.

Нужен Admin-ключ (sk-admin-…, scope api.usage.read) — проектный ключ получает 403.
service_tier «incentivized-tier» в usage — это и есть бесплатные (data sharing) токены.
"""

import time
from datetime import datetime, timezone

import httpx

USAGE_URL = 'https://api.openai.com/v1/organization/usage/completions'
COSTS_URL = 'https://api.openai.com/v1/organization/costs'


def _utc_day_start():
    now = datetime.now(timezone.utc)
    return int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def _get(url, params, key, timeout=20):
    try:
        r = httpx.get(url, params=params, headers={'Authorization': f'Bearer {key}'}, timeout=timeout)
    except Exception as e:
        return None, f'Не удалось связаться с OpenAI: {e}'
    if r.status_code != 200:
        try:
            body = r.json()
            err = body.get('error')
            msg = err.get('message') if isinstance(err, dict) else (err or body)
        except Exception:
            msg = r.text[:200]
        return None, f'OpenAI {r.status_code}: {msg}'
    try:
        return r.json(), None
    except Exception as e:
        return None, f'Неожиданный ответ OpenAI: {e}'


def _is_free_tier(tier):
    return 'incentiv' in str(tier or '').lower() or 'sharing' in str(tier or '').lower()


def summarize(usage_json, costs_json):
    """Снимок дня: {'fetched_at', 'models': {model: {...}}, 'cost_usd', 'cost_lines'}."""
    models = {}
    for bucket in (usage_json or {}).get('data') or []:
        for row in bucket.get('results') or []:
            model = str(row.get('model') or '?')
            tier = str(row.get('service_tier') or '')
            entry = models.setdefault(model, {'input': 0, 'output': 0, 'cached': 0, 'requests': 0,
                                              'tier': tier, 'free': _is_free_tier(tier), 'billed_tokens': 0})
            inp = int(row.get('input_tokens') or 0)
            out = int(row.get('output_tokens') or 0)
            entry['input'] += inp
            entry['output'] += out
            entry['cached'] += int(row.get('input_cached_tokens') or 0)
            entry['requests'] += int(row.get('num_model_requests') or 0)
            # Одна модель может прийти двумя строками (бесплатный тир и платный) — запоминаем оба.
            if not _is_free_tier(tier):
                entry['billed_tokens'] += inp + out
            elif not entry['tier']:
                entry['tier'] = tier
            if _is_free_tier(tier):
                entry['free'] = True

    lines = {}
    for bucket in (costs_json or {}).get('data') or []:
        for row in bucket.get('results') or []:
            amount = row.get('amount') or {}
            value = float(amount.get('value') or 0)
            if value:
                line = str(row.get('line_item') or 'прочее')
                lines[line] = lines.get(line, 0.0) + value

    return {
        'fetched_at': time.time(),
        'models': models,
        'cost_usd': round(sum(lines.values()), 4),
        'cost_lines': [{'line_item': k, 'usd': round(v, 4)} for k, v in sorted(lines.items(), key=lambda kv: -kv[1])],
    }


def fetch_today(admin_key):
    """(snapshot, error) — usage по model+service_tier (с откатом на model) и costs по line_item."""
    start = _utc_day_start()
    usage, err = _get(USAGE_URL, [('start_time', start), ('bucket_width', '1d'),
                                  ('group_by', 'model'), ('group_by', 'service_tier')], admin_key)
    if err and ' 400' in err:
        usage, err = _get(USAGE_URL, [('start_time', start), ('bucket_width', '1d'),
                                      ('group_by', 'model')], admin_key)
    if err:
        return None, err
    costs, err = _get(COSTS_URL, [('start_time', start), ('bucket_width', '1d'),
                                  ('group_by', 'line_item')], admin_key)
    if err:
        return None, err
    return summarize(usage, costs), None
