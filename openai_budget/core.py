"""Состояние бюджета: файл на пользователя, блокировка между процессами, решение «можно ли».

Учёт токенов — вход + выход, как считает OpenAI для бесплатного пула. День — по UTC
(сброс в 00:00 UTC). Использовано = снимок организации на момент последней синхронизации
+ всё, что записали через record() после неё; без Admin-ключа — только локальные записи.
"""

import json
import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from . import usage_api

# Бесплатные группы по справке OpenAI (Tier 1–2). margin — запас: запрос, переваливший
# лимит, платится целиком, а размер ответа заранее неизвестен.
DEFAULT_GROUPS = {
    'large': {
        'limit': 250_000, 'margin': 8_000, 'label': '250 тыс./день, большие модели',
        'models': {'gpt-5.6-sol', 'gpt-5.5', 'gpt-5.4', 'gpt-5.2', 'gpt-5.1', 'gpt-5',
                   'gpt-5-chat-latest', 'gpt-5-codex', 'gpt-4.1', 'gpt-4o', 'o1', 'o3'},
    },
    'small': {
        'limit': 2_500_000, 'margin': 8_000, 'label': '2,5 млн/день, mini и nano',
        'models': {'gpt-5.6-terra', 'gpt-5.6-luna', 'gpt-5.4-mini', 'gpt-5.4-nano',
                   'gpt-5-mini', 'gpt-5-nano', 'gpt-4.1-mini', 'gpt-4.1-nano',
                   'gpt-4o-mini', 'o1-mini', 'o3-mini', 'o4-mini', 'codex-mini-latest'},
    },
}

DEFAULT_SYNC_EVERY_S = 300

_lock = threading.RLock()
_config_cache = None
_SNAPSHOT_RE = re.compile(r'-\d{4}-\d{2}-\d{2}$')


# ---------------------------------------------------------------------------
# Пути и конфиг
# ---------------------------------------------------------------------------

def state_dir():
    """~/.openai_budget или OPENAI_BUDGET_DIR — общий для всех проектов пользователя."""
    path = os.environ.get('OPENAI_BUDGET_DIR') or os.path.join(os.path.expanduser('~'), '.openai_budget')
    os.makedirs(path, exist_ok=True)
    return path


def _config_path():
    return os.path.join(state_dir(), 'config.json')


def _state_path():
    return os.path.join(state_dir(), 'state.json')


def _read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else default
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_config():
    global _config_cache
    with _lock:
        if _config_cache is None:
            _config_cache = _read_json(_config_path(), {})
        return _config_cache


def configure(admin_key=None, groups=None, sync_every_s=None, persist=True):
    """Меняет настройки; persist=True пишет их в config.json (для всех проектов)."""
    with _lock:
        cfg = dict(_load_config())
        if admin_key is not None:
            cfg['admin_key'] = str(admin_key).strip()
        if groups is not None:
            cfg['groups'] = groups
        if sync_every_s is not None:
            cfg['sync_every_s'] = int(sync_every_s)
        if persist:
            _write_json(_config_path(), cfg)
        globals()['_config_cache'] = cfg
        return cfg


def set_admin_key(key):
    configure(admin_key=key or '')


def get_admin_key():
    env = os.environ.get('OPENAI_ADMIN_KEY', '').strip()
    return env or str(_load_config().get('admin_key') or '').strip()


def admin_key_masked():
    key = get_admin_key()
    if not key:
        return ''
    return key[:6] + '…' + key[-4:] if len(key) > 12 else key[:3] + '…'


def _groups():
    """DEFAULT_GROUPS c переопределениями из конфига (limit/margin/models)."""
    merged = {g: {**info, 'models': set(info['models'])} for g, info in DEFAULT_GROUPS.items()}
    for g, override in (_load_config().get('groups') or {}).items():
        if not isinstance(override, dict):
            continue
        target = merged.setdefault(g, {'limit': 0, 'margin': 0, 'label': g, 'models': set()})
        for field in ('limit', 'margin', 'label'):
            if field in override:
                target[field] = override[field]
        if 'models' in override:
            target['models'] = set(override['models'])
        for m in override.get('add_models') or []:
            target['models'].add(m)
    return merged


def _base_model(model):
    """gpt-4o-mini-2024-07-18 → gpt-4o-mini; models/… и регистр тоже нормализуем."""
    name = str(model or '').strip().lower()
    if name.startswith('models/'):
        name = name[7:]
    return _SNAPSHOT_RE.sub('', name)


def group_for(model):
    """'large' | 'small' | None — к какой бесплатной группе относится модель."""
    base = _base_model(model)
    for g, info in _groups().items():
        if base in info['models']:
            return g
    return None


# ---------------------------------------------------------------------------
# Состояние с межпроцессной блокировкой
# ---------------------------------------------------------------------------

def _today():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def reset_in_s():
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds())


def _blank_state():
    return {'day': _today(), 'org': None, 'local': {}}


@contextmanager
def _locked(timeout_s=3.0):
    """Файловая блокировка через O_EXCL — работает и на Windows, и на POSIX."""
    lock_path = os.path.join(state_dir(), 'state.lock')
    deadline = time.time() + timeout_s
    fd = None
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            # Брошенный lock от упавшего процесса — старше 30 с считаем мусором.
            try:
                if time.time() - os.path.getmtime(lock_path) > 30:
                    os.remove(lock_path)
                    continue
            except OSError:
                pass
            if time.time() > deadline:
                raise TimeoutError('openai_budget: не дождались блокировки state.lock')
            time.sleep(0.05)
    try:
        with _lock:
            yield
    finally:
        try:
            os.close(fd)
            os.remove(lock_path)
        except OSError:
            pass


def _load_state():
    st = _read_json(_state_path(), None) or _blank_state()
    if st.get('day') != _today():
        st = _blank_state()
    st.setdefault('local', {})
    return st


def _save_state(st):
    _write_json(_state_path(), st)


# ---------------------------------------------------------------------------
# Запись использования
# ---------------------------------------------------------------------------

def record(model, input_tokens=0, output_tokens=0, cached_tokens=0, requests=1):
    """Учитывает один вызов. Вызывать после каждого успешного запроса к OpenAI."""
    with _locked():
        st = _load_state()
        entry = st['local'].setdefault(str(model), {'input': 0, 'output': 0, 'cached': 0, 'requests': 0})
        entry['input'] += int(input_tokens or 0)
        entry['output'] += int(output_tokens or 0)
        entry['cached'] += int(cached_tokens or 0)
        entry['requests'] += int(requests or 0)
        _save_state(st)


def record_response(model, response):
    """Достаёт usage из ответа SDK: Responses API (input_tokens/output_tokens,
    input_tokens_details.cached_tokens) или Chat Completions (prompt_/completion_tokens)."""
    usage = getattr(response, 'usage', None)
    if usage is None and isinstance(response, dict):
        usage = response.get('usage')
    if usage is None:
        return

    def _get(obj, *names):
        for name in names:
            val = obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
            if val is not None:
                return val
        return None

    inp = _get(usage, 'input_tokens', 'prompt_tokens') or 0
    out = _get(usage, 'output_tokens', 'completion_tokens') or 0
    details = _get(usage, 'input_tokens_details', 'prompt_tokens_details')
    cached = (_get(details, 'cached_tokens') if details is not None else 0) or 0
    record(model, inp, out, cached)


# ---------------------------------------------------------------------------
# Синхронизация с отчётом организации
# ---------------------------------------------------------------------------

def sync(force=False):
    """Тянет usage/costs за сегодня (UTC) через Admin-ключ и сбрасывает локальный счёт.

    Returns:
        tuple: (org_snapshot | None, error | None). Без Admin-ключа — (None, сообщение).
    """
    key = get_admin_key()
    if not key:
        return None, 'Admin-ключ OpenAI не задан.'
    every = int(_load_config().get('sync_every_s') or DEFAULT_SYNC_EVERY_S)
    with _locked():
        st = _load_state()
        org = st.get('org')
        if not force and org and time.time() - org.get('fetched_at', 0) < every:
            return org, None
    snapshot, err = usage_api.fetch_today(key)
    if err:
        return None, err
    with _locked():
        st = _load_state()
        st['org'] = snapshot
        # После синка локальные записи считаются «до снимка» — иначе посчитаем дважды.
        st['local'] = {}
        _save_state(st)
    return snapshot, None


# ---------------------------------------------------------------------------
# Оценка и решение
# ---------------------------------------------------------------------------

_CYRILLIC_RE = re.compile(r'[Ѐ-ӿ]')


def estimate_tokens(text='', images=0, expected_output=0):
    """Грубая оценка токенов запроса: tiktoken если есть, иначе по символам.

    Кириллица у GPT-токенизаторов дорогая (~2,5 символа на токен), латиница ~4.
    Картинка — примерно 800–1100 токенов при detail=auto; берём 1000.
    """
    text = text or ''
    try:
        import tiktoken
        enc = tiktoken.get_encoding('o200k_base')
        n = len(enc.encode(text, disallowed_special=()))
    except Exception:
        cyr = len(_CYRILLIC_RE.findall(text))
        n = int(cyr / 2.5 + (len(text) - cyr) / 4.0)
    return n + int(images) * 1000 + int(expected_output)


def _usage_by_group(st):
    """{group: {'used': tokens, 'models': {model: tokens}}} из снимка org + локального счёта."""
    groups = _groups()
    used = {g: {'used': 0, 'models': {}} for g in groups}
    org = st.get('org') or {}
    for model, entry in (org.get('models') or {}).items():
        g = group_for(model)
        if g:
            tokens = int(entry.get('input', 0)) + int(entry.get('output', 0))
            used[g]['used'] += tokens
            used[g]['models'][model] = used[g]['models'].get(model, 0) + tokens
    for model, entry in (st.get('local') or {}).items():
        g = group_for(model)
        if g:
            tokens = int(entry.get('input', 0)) + int(entry.get('output', 0))
            used[g]['used'] += tokens
            used[g]['models'][model] = used[g]['models'].get(model, 0) + tokens
    return used


def can_spend(model, estimated_tokens=0, auto_sync=True):
    """Влезет ли запрос на `model` в бесплатный лимит группы с учётом запаса.

    auto_sync: подтянуть отчёт организации, если он устарел (сетевой вызов раз в
    sync_every_s; ошибки сети не мешают — считаем по тому, что есть).

    Returns:
        tuple: (ok, info) — info: group, used, limit, margin, left, estimated, source,
        synced_ago_s, reason. Для модели вне бесплатных групп ok=True, group=None.
    """
    group = group_for(model)
    if group is None:
        return True, {'group': None, 'reason': 'модель не входит в бесплатные группы', 'estimated': int(estimated_tokens)}
    if auto_sync and get_admin_key():
        sync()
    st = _load_state()
    info = _groups()[group]
    used = _usage_by_group(st)[group]['used']
    left = info['limit'] - info['margin'] - used
    org = st.get('org') or {}
    result = {
        'group': group, 'label': info['label'],
        'used': used, 'limit': info['limit'], 'margin': info['margin'],
        'left': max(left, 0), 'estimated': int(estimated_tokens),
        'source': 'org+local' if org else 'local',
        'synced_ago_s': int(time.time() - org['fetched_at']) if org else None,
        'reset_in_s': reset_in_s(),
    }
    ok = int(estimated_tokens) <= left
    result['reason'] = '' if ok else (
        f"бесплатный лимит OpenAI ({info['label']}) почти исчерпан: использовано "
        f"{used:,} из {info['limit']:,}, запас {info['margin']:,}, запрос ~{int(estimated_tokens):,} не влезает; "
        f"сброс через {reset_in_s() // 3600} ч {reset_in_s() % 3600 // 60} мин (00:00 UTC)").replace(',', ' ')
    return ok, result


def status():
    """Сводка для интерфейсов: группы, модели, стоимость, источник, таймер сброса."""
    st = _load_state()
    groups = _groups()
    by_group = _usage_by_group(st)
    org = st.get('org') or {}
    org_models = org.get('models') or {}
    local = st.get('local') or {}

    models = {}
    for model, entry in org_models.items():
        models[model] = {
            'model': model, 'service_tier': entry.get('tier', ''),
            'free': bool(entry.get('free')), 'requests': int(entry.get('requests', 0)),
            'input_tokens': int(entry.get('input', 0)), 'output_tokens': int(entry.get('output', 0)),
            'cached_tokens': int(entry.get('cached', 0)),
        }
    for model, entry in local.items():
        row = models.setdefault(model, {'model': model, 'service_tier': '', 'free': False, 'requests': 0,
                                        'input_tokens': 0, 'output_tokens': 0, 'cached_tokens': 0})
        row['requests'] += int(entry.get('requests', 0))
        row['input_tokens'] += int(entry.get('input', 0))
        row['output_tokens'] += int(entry.get('output', 0))
        row['cached_tokens'] += int(entry.get('cached', 0))
        row['local_pending'] = True
    rows = list(models.values())
    for row in rows:
        row['total_tokens'] = row['input_tokens'] + row['output_tokens']
        row['group'] = group_for(row['model'])
    rows.sort(key=lambda r: -r['total_tokens'])

    return {
        'day': st.get('day'),
        'reset_in_s': reset_in_s(),
        'source': 'org+local' if org else 'local',
        'synced_ago_s': int(time.time() - org['fetched_at']) if org else None,
        'admin_key_set': bool(get_admin_key()),
        'groups': {
            g: {
                'used': by_group[g]['used'], 'limit': info['limit'], 'margin': info['margin'],
                'left': max(info['limit'] - info['margin'] - by_group[g]['used'], 0),
                'label': info['label'],
                'pct': int(round(by_group[g]['used'] / info['limit'] * 100)) if info['limit'] else 0,
            } for g, info in groups.items()
        },
        'models': rows,
        'cost_today_usd': float(org.get('cost_usd', 0.0)),
        'cost_lines': org.get('cost_lines') or [],
        'has_service_tier': any(r['service_tier'] for r in rows),
    }
