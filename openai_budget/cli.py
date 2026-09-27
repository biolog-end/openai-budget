"""openai-budget status | sync | set-key KEY | can MODEL [TOKENS] | record MODEL IN OUT"""

import json
import sys

from . import core


def _fmt(n):
    return f'{int(n):,}'.replace(',', ' ')


def _print_status(st):
    src = st['source'] + (f" (синк {st['synced_ago_s']} с назад)" if st['synced_ago_s'] is not None else '')
    print(f"День {st['day']} UTC, сброс через {st['reset_in_s'] // 3600} ч {st['reset_in_s'] % 3600 // 60} мин, источник: {src}")
    for g, info in st['groups'].items():
        print(f"  {info['label']}: {_fmt(info['used'])} / {_fmt(info['limit'])} ({info['pct']}%), "
              f"можно ещё ~{_fmt(info['left'])} (запас {_fmt(info['margin'])})")
    if st['models']:
        print('  по моделям:')
        for m in st['models']:
            tier = ' бесплатно' if m['free'] else (f" {m['service_tier']}" if m['service_tier'] else '')
            pend = ' (локально, до синка)' if m.get('local_pending') else ''
            print(f"    {m['model']}: {_fmt(m['total_tokens'])} ток. (вход {_fmt(m['input_tokens'])}, "
                  f"выход {_fmt(m['output_tokens'])}, запросов {m['requests']}){tier}{pend}")
    print(f"  списано сегодня: ${st['cost_today_usd']:.4f}")
    if not st['admin_key_set']:
        print('  Admin-ключ не задан — считаются только вызовы через эту библиотеку. '
              'Задать: openai-budget set-key sk-admin-…')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else 'status'
    if cmd == 'status':
        if '--json' in argv:
            print(json.dumps(core.status(), ensure_ascii=False, indent=2))
        else:
            _print_status(core.status())
    elif cmd == 'sync':
        snap, err = core.sync(force=True)
        if err:
            print('Ошибка:', err)
            return 1
        _print_status(core.status())
    elif cmd == 'set-key':
        if len(argv) < 2:
            print('Использование: openai-budget set-key sk-admin-…')
            return 2
        core.set_admin_key(argv[1])
        print('Admin-ключ сохранён:', core.admin_key_masked(), 'в', core.state_dir())
    elif cmd == 'can':
        if len(argv) < 2:
            print('Использование: openai-budget can MODEL [TOKENS]')
            return 2
        ok, info = core.can_spend(argv[1], int(argv[2]) if len(argv) > 2 else 0)
        print('OK' if ok else 'НЕТ', json.dumps(info, ensure_ascii=False))
        return 0 if ok else 1
    elif cmd == 'record':
        if len(argv) < 4:
            print('Использование: openai-budget record MODEL INPUT_TOKENS OUTPUT_TOKENS')
            return 2
        core.record(argv[1], int(argv[2]), int(argv[3]))
        print('записано')
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
