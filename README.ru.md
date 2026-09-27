# openai_budget

[English](README.md) | **Русский**

Общий дневной бюджет бесплатных токенов OpenAI для всех проектов на этой машине.

При включённом **Share inputs and outputs** (Settings → Data controls) OpenAI каждый
день даёт бесплатные токены. На Tier 1–2 это **250 тыс./день** для больших моделей
(gpt-5.x, gpt-4.1, gpt-4o, o1, o3) и **2,5 млн/день** для mini и nano. Лимит общий на
организацию, сбрасывается в **00:00 UTC**, а запрос, который переваливает лимит,
оплачивается целиком. Несколько проектов на одном аккаунте считают каждый своё — эта
библиотека держит один файл состояния на пользователя и сверяется с отчётом организации
через Admin-ключ.

## Установка

```bat
pip install git+https://github.com/biolog-end/openai-budget.git
openai-budget set-key sk-admin-...      :: Settings → Organization → Admin keys
openai-budget status
```

Для более точной оценки токенов поставьте вариант `accurate`, он добавляет `tiktoken`:

```bat
pip install "openai-budget[accurate] @ git+https://github.com/biolog-end/openai-budget.git"
```

Состояние и Admin-ключ лежат в `~/.openai_budget/` (`%USERPROFILE%\.openai_budget` в
Windows), `OPENAI_BUDGET_DIR` меняет расположение. Admin-ключ можно задать и переменной
`OPENAI_ADMIN_KEY`.

## Использование

```python
import openai_budget as ob

estimate = ob.estimate_tokens(prompt_text, images=0, expected_output=800)
ok, info = ob.can_spend('gpt-5.4-mini', estimate)   # сверяется с отчётом раз в 5 минут
if not ok:
    raise RuntimeError(info['reason'])              # «лимит почти исчерпан…»

response = client.responses.create(model='gpt-5.4-mini', input=...)
ob.record_response('gpt-5.4-mini', response)       # Responses API или Chat Completions
```

- `can_spend()` считает использованным снимок организации плюс всё, что записано
  локально после него. В обеих группах запас 8 тыс. токенов. Переопределяется в
  `config.json`: `"groups": {"large": {"margin": 5000, "add_models": ["gpt-6"]}}`.
- Без Admin-ключа учитываются только вызовы, записанные через `record*()` из любых
  проектов.
- `ob.status()` — сводка для интерфейсов; `openai-budget status --json` — то же в
  консоли (или `python -m openai_budget.cli status`, если скрипта нет в `PATH`).

### Chat Completions и стриминг

`record_response()` понимает и `chat.completions.create()` (`prompt_tokens` и
`completion_tokens`). При стриминге usage приходит только в конце: для Chat Completions
передайте `stream_options={"include_usage": True}` и запишите последний чанк; для
Responses API — итоговый ответ (`stream.get_final_response()` или событие
`response.completed`).

### Что это даёт сверх Admin-ключа

Admin-ключ сам по себе показывает, сколько уже потрачено, с задержкой в несколько
минут. Библиотека добавляет решение *до* запроса (влезет ли он с запасом), учёт вызовов
между синхронизациями (несколько приложений не проскочат лимит хором) и одно место для
ключа и лимитов. Если нужно только смотреть — хватит `openai-budget sync` или дашборда
platform.openai.com/usage с группировкой по service tier.

Токены оцениваются через `tiktoken`, если он установлен, иначе по числу символов
(около 2,5 символа на токен для кириллицы и 4 для латиницы).

## Командная строка

```bat
openai-budget status [--json]          :: расход за сегодня по группам и моделям
openai-budget sync                     :: сразу подтянуть отчёт организации
openai-budget set-key sk-admin-...     :: сохранить Admin-ключ
openai-budget can MODEL [TOKENS]       :: влезет ли запрос такого размера
openai-budget record MODEL IN OUT      :: записать вызов вручную
```
