# openai_budget

[English](README.md) | **Русский**

Общий дневной счётчик бесплатных токенов OpenAI и каталог моделей: один файл состояния
для всех проектов пользователя, точные цифры из отчёта организации через Admin-ключ,
каталог моделей, обновляемый одним `pip install -U`.

## Установка

```bat
pip install git+https://github.com/biolog-end/openai-budget.git
pip install openai             :: SDK, расход которого считает openai_budget
```

Состояние лежит в `~/.openai_budget/state.json`. Переменная `OPENAI_BUDGET_DIR`
переносит его.

## Каталог

```python
import openai_budget as ob

ob.models()                                 # все модели переписки: цены, бесплатная группа, reasoning
ob.model_info('gpt-5.4-mini')               # одна строка
ob.DEFAULT_MODEL                            # рекомендуемый дефолт
ob.LIGHT_MODEL                              # дешёвая модель для памяти/сводок
ob.is_openai_model(name)
ob.is_text_model('gpt-5.5-pro')             # отбрасывает audio/image/realtime/снапшоты/tts
ob.group_for('gpt-5.4-mini')                # 'large' | 'small' | None
ob.supports_reasoning('gpt-5-mini')
ob.reasoning_off('gpt-5')                   # какой effort выключает размышления ('none', 'minimal', 'low', None)
ob.temperature_mode('gpt-5.4')              # 'always' | 'without_reasoning' | None
```

В каждой строке — `price` (`input` / `cached_input` / `output` долларов за 1M токенов),
`reasoning` и `reasoning_off` (какой effort выключает размышления), `temperature`-режим
и `rank`.

## Бесплатный пул

```python
estimate = ob.estimate_tokens(system + prompt, expected_output=1200)
ok, info = ob.can_spend('gpt-5.4-mini', estimate)
if not ok:
    raise RuntimeError(info['reason'])
response = client.responses.create(...)
ob.record_response('gpt-5.4-mini', response)
```

- Бесплатный пул: 250 000 токенов в день на большую группу (gpt-5.x / 4.1 / 4o / o1 /
  o3) и 2 500 000 на mini/nano. Работает только при включённом в настройках
  организации «share traffic with OpenAI». Лимит на организацию, не на ключ; день
  сбрасывается в **00:00 UTC**. Состав групп меняется через `configure(groups={...})`.
- `can_spend()` перед проверкой пробует синхронизироваться с отчётом организации (нужен
  Admin-ключ); без ключа учитываются только локальные вызовы.
- `record()` / `record_response()` записывают расход. Библиотека понимает ответы и
  Responses API, и Chat Completions.
- `sync(force=True)` тянет снимок организации прямо сейчас и сбрасывает локальный
  журнал (иначе было бы двойной учёт).

## Admin-ключ

```python
ob.set_admin_key('sk-admin-…')        # или: openai-budget set-key sk-admin-…
ob.admin_key_masked()
ob.get_admin_key()
```

Admin-ключи читают `/v1/organization/usage/completions` и `/costs`; проектный ключ
получит 403. Используется только для «сколько реально потрачено сегодня»; ни один
запрос без него не падает.

`service_tier == "incentivized-tier"` в отчёте — доказательство бесплатного вызова.

## Командная строка

```bat
openai-budget status                        :: бесплатный пул, локальные записи, источник
openai-budget sync                          :: подтянуть отчёт организации
openai-budget set-key sk-admin-…
openai-budget can gpt-5.4-mini 1200         :: пробный вызов can_spend
openai-budget path                          :: где состояние и конфиг
```

## Соседние библиотеки

- [`gemini-budget`](https://github.com/biolog-end/gemini-budget) — то же для Gemini.
- [`ai-router`](https://github.com/biolog-end/ai-router) — общее хранилище ключей и
  устойчивый слой запросов, который использует этот бюджет.
