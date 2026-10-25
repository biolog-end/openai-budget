"""Каталог моделей OpenAI: цены, бесплатная группа, reasoning и температура.

Цены — Standard API, доллары за 1M токенов (обычный вход / кэшированный вход / выход),
None — цена неизвестна. Бесплатная группа берётся из core.group_for (её состав можно
переопределить в config.json → groups), поэтому здесь не дублируется.
"""

import re

PRICES_CHECKED = '2026-09-16'
DEFAULT_MODEL = 'gpt-5.4-mini'
LIGHT_MODEL = 'gpt-5-mini'

# reasoning_off — какой effort выключает размышления: 'none' у 5.1+, 'minimal' у gpt-5,
# у o-серии их не выключить ('low'); None — модель reasoning не принимает или
# поддерживает не все значения (pro), тогда параметр не передаётся.
# temperature — 'always' | 'without_reasoning' (только при effort none) | None.
_ROWS = [
    # id, label, input, cached, output, reasoning, reasoning_off, temperature, rank, note
    ('gpt-6-astra', 'GPT-6 Astra', 10, 1, 50, True, 'none', None, 1, ''),
    ('gpt-5.6-sol', 'GPT-5.6 Sol', 4, .4, 20, True, 'none', None, 2, 'Цена по акции как минимум до 21.11.2026.'),
    ('gpt-5.5-pro', 'GPT-5.5 Pro', 30, None, 180, True, None, None, 3, ''),
    ('gpt-5.5', 'GPT-5.5', 5, .5, 30, True, 'none', None, 4, ''),
    ('gpt-5.4-pro', 'GPT-5.4 Pro', 30, None, 180, True, None, None, 5, ''),
    ('gpt-5.4', 'GPT-5.4', 2.5, .25, 15, True, 'none', 'without_reasoning', 6, 'Флагман бесплатной группы 250 тыс./день.'),
    ('gpt-5.2-pro', 'GPT-5.2 Pro', 21, None, 168, True, None, None, 7, ''),
    ('gpt-5.2', 'GPT-5.2', 1.75, .175, 14, True, 'none', 'without_reasoning', 8, ''),
    ('gpt-5-pro', 'GPT-5 Pro', 15, None, 120, True, None, None, 9, ''),
    ('gpt-5.1', 'GPT-5.1', 1.25, .125, 10, True, 'none', 'without_reasoning', 10, ''),
    ('gpt-5', 'GPT-5', 1.25, .125, 10, True, 'minimal', None, 11, ''),
    ('o3-pro', 'o3-pro', 20, None, 80, True, None, None, 12, ''),
    ('o3', 'o3', 2, .5, 8, True, 'low', None, 13, 'Reasoning-модель, медленная.'),
    ('o1', 'o1', 15, 7.5, 60, True, 'low', None, 14, 'Дорогая reasoning-модель.'),
    ('gpt-4.1', 'GPT-4.1', 2, .5, 8, False, None, 'always', 15, 'Без reasoning — быстрые ответы.'),
    ('gpt-4o', 'GPT-4o', 2.5, 1.25, 10, False, None, 'always', 16, ''),
    ('gpt-5.6-terra', 'GPT-5.6 Terra', 2, .2, 12, True, 'none', None, 17, ''),
    ('gpt-5.4-mini', 'GPT-5.4 mini', .75, .075, 4.5, True, 'none', None, 18, 'Свежая mini, бесплатная группа 2,5 млн/день.'),
    ('gpt-5-mini', 'GPT-5 mini', .25, .025, 2, True, 'minimal', None, 19, 'Подходит для сводок и памяти.'),
    ('o4-mini', 'o4-mini', 1.1, .275, 4.4, True, 'low', None, 20, ''),
    ('o3-mini', 'o3-mini', 1.1, .55, 4.4, True, 'low', None, 21, ''),
    ('o1-mini', 'o1-mini', 1.1, None, 4.4, True, 'low', None, 22, ''),
    ('gpt-4.1-mini', 'GPT-4.1 mini', .4, .1, 1.6, False, None, 'always', 23, 'Без reasoning, быстрая.'),
    ('gpt-4o-mini', 'GPT-4o mini', .15, .075, .6, False, None, 'always', 24, ''),
    ('gpt-5.6-luna', 'GPT-5.6 Luna', .2, .02, 1.2, True, 'none', None, 25, ''),
    ('gpt-5.4-nano', 'GPT-5.4 nano', .2, .02, 1.25, True, 'none', None, 26, ''),
    ('gpt-5-nano', 'GPT-5 nano', .05, .005, .4, True, 'minimal', None, 27, 'Самая дешёвая.'),
    ('gpt-4.1-nano', 'GPT-4.1 nano', .1, .025, .4, False, None, 'always', 28, 'Без reasoning, самая быстрая.'),
]

MODELS = [
    {'id': row[0], 'label': row[1], 'task': 'chat',
     'price': {'input': row[2], 'cached_input': row[3], 'output': row[4]},
     'reasoning': row[5], 'reasoning_off': row[6], 'temperature': row[7], 'rank': row[8], 'note': row[9]}
    for row in _ROWS
]
MODELS_BY_ID = {model['id']: model for model in MODELS}

_SNAPSHOT_RE = re.compile(r'-(\d{4}-\d{2}-\d{2}|\d{4})$')
_TEXT_PREFIXES = ('gpt-', 'o1', 'o3', 'o4', 'o5')
# Не для переписки или дубли базового имени (снапшоты, *-chat-latest).
_NON_TEXT_MARKERS = (
    'audio', 'realtime', 'transcribe', 'tts', 'search', 'image', 'embedding', 'moderation',
    'instruct', 'codex', 'whisper', 'dall-e', 'davinci', 'babbage', 'computer-use', 'preview',
    'chatgpt-', 'sora', 'deep-research', 'chat-latest', 'gpt-3.5', 'gpt-4-', 'turbo',
)


def base_model(model):
    """'models/GPT-4o-mini-2024-07-18' → 'gpt-4o-mini'."""
    name = str(model or '').strip().lower().removeprefix('models/')
    return re.sub(r'-\d{4}-\d{2}-\d{2}$', '', name)


def model_info(model):
    info = MODELS_BY_ID.get(base_model(model))
    return {**info, 'price': dict(info['price'])} if info else None


def is_openai_model(model):
    return base_model(model).startswith(('gpt-', 'o1', 'o3', 'o4', 'o5', 'chatgpt-'))


def supports_reasoning(model):
    """Принимает ли модель reasoning.effort. Незнакомые — по имени: o-серия и gpt-5+."""
    info = MODELS_BY_ID.get(base_model(model))
    if info is not None:
        return info['reasoning']
    name = base_model(model)
    generation = re.match(r'gpt-(\d+)', name)
    return name.startswith(('o1', 'o3', 'o4', 'o5')) or bool(generation and int(generation.group(1)) >= 5)


def reasoning_off(model):
    """effort, который выключает размышления, или None, если его не передавать."""
    info = MODELS_BY_ID.get(base_model(model))
    if info is not None:
        return info['reasoning_off']
    return 'none' if supports_reasoning(model) and '-pro' not in base_model(model) else None


def temperature_mode(model):
    """'always' | 'without_reasoning' | None — подтверждённая поддержка temperature/top_p."""
    info = MODELS_BY_ID.get(base_model(model))
    if info is not None:
        return info['temperature']
    return 'always' if base_model(model).startswith(('gpt-4.1', 'gpt-4o')) else None


def is_text_model(model):
    name = str(model or '').strip().lower().removeprefix('models/')
    if not name.startswith(_TEXT_PREFIXES) or name == 'gpt-4':
        return False
    if any(marker in name for marker in _NON_TEXT_MARKERS) or re.search(r'-pro\b', name) and name not in MODELS_BY_ID:
        return False
    return not _SNAPSHOT_RE.search(name)
