"""openai_budget — общий дневной бюджет бесплатных токенов OpenAI для всех проектов на машине.

Зачем: OpenAI даёт бесплатные токены в день (data sharing incentive) на организацию,
двумя группами моделей. Запрос, который переваливает лимит, платится целиком. Несколько
проектов / инстансов на одном аккаунте считают каждый своё и в сумме промахиваются.
Здесь — один файл состояния на пользователя (~/.openai_budget/), синхронизация с отчётом
организации через Admin-ключ и проверка «влезет ли ещё этот запрос» перед вызовом.

Типичное использование:

    import openai_budget as ob

    ok, info = ob.can_spend('gpt-5.4-mini', ob.estimate_tokens(prompt_text, expected_output=800))
    if not ok:
        raise RuntimeError(info['reason'])
    response = client.responses.create(...)
    ob.record_response('gpt-5.4-mini', response)

Admin-ключ (sk-admin-…) задаётся один раз: `openai-budget set-key sk-admin-…`,
переменной OPENAI_ADMIN_KEY или ob.set_admin_key(). Без него считаются только
локальные вызовы через эту библиотеку.
"""

from .core import (
    DEFAULT_GROUPS,
    admin_key_masked,
    can_spend,
    configure,
    estimate_tokens,
    get_admin_key,
    group_for,
    record,
    record_response,
    reset_in_s,
    set_admin_key,
    state_dir,
    status,
    sync,
)

__all__ = [
    'DEFAULT_GROUPS', 'admin_key_masked', 'can_spend', 'configure', 'estimate_tokens',
    'get_admin_key', 'group_for', 'record', 'record_response', 'reset_in_s', 'set_admin_key',
    'state_dir', 'status', 'sync',
]
__version__ = '0.1.0'
