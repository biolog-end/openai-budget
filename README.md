# openai_budget

**English** | [Русский](README.ru.md)

Shared daily free-tier budget tracker and model catalog for the OpenAI API: one state
file for every project of this user, org-wide truth via an Admin key, a catalog that
every app updates with one `pip install -U`.

## Install

```bat
pip install git+https://github.com/biolog-end/openai-budget.git
pip install openai             :: the SDK openai_budget records usage for
```

State lives in `~/.openai_budget/state.json`. Set `OPENAI_BUDGET_DIR` to move it.

## Catalog

```python
import openai_budget as ob

ob.models()                                 # every chat model: prices, free group, reasoning, temperature
ob.model_info('gpt-5.4-mini')               # one row
ob.DEFAULT_MODEL                            # recommended default
ob.LIGHT_MODEL                              # cheap model for memory/summaries
ob.is_openai_model(name)                    # based on the model name
ob.is_text_model('gpt-5.5-pro')             # drops audio/image/realtime/snapshots/tts
ob.group_for('gpt-5.4-mini')                # 'large' | 'small' | None
ob.supports_reasoning('gpt-5-mini')
ob.reasoning_off('gpt-5')                   # effort that turns reasoning off ('none', 'minimal', 'low', None)
ob.temperature_mode('gpt-5.4')              # 'always' | 'without_reasoning' | None
```

Each row carries `price` (`input` / `cached_input` / `output` USD per 1M tokens),
`reasoning` and the `reasoning_off` setting (what `effort` turns thinking off),
`temperature` policy and `rank`.

## Free pool

```python
estimate = ob.estimate_tokens(system + prompt, expected_output=1200)
ok, info = ob.can_spend('gpt-5.4-mini', estimate)
if not ok:
    raise RuntimeError(info['reason'])
response = client.responses.create(...)
ob.record_response('gpt-5.4-mini', response)
```

- The free pool: 250 000 tokens per day for the big group (gpt-5.x / 4.1 / 4o / o1 / o3)
  and 2 500 000 for mini/nano. Available only with "share traffic with OpenAI" enabled
  on the organization. Limits are per org, not per key, and the day resets at
  **00:00 UTC**. Group content is editable via `configure(groups={...})`.
- `can_spend()` tries to sync with the org usage report before the check (needs an
  Admin key); without the key only local writes are counted.
- `record()` / `record_response()` write the usage. The library understands both the
  Responses API and Chat Completions shapes.
- `sync(force=True)` pulls the org snapshot right now and resets the local pending
  entries (they would double otherwise).

## Admin key

```python
ob.set_admin_key('sk-admin-…')        # also: openai-budget set-key sk-admin-…
ob.admin_key_masked()
ob.get_admin_key()
```

Admin keys read `/v1/organization/usage/completions` and `/costs`; a project key gets
403. Only used to show "really spent so far today"; nothing in the request path
depends on it.

`service_tier == "incentivized-tier"` in the usage report is the proof a call was
served from the free pool.

## Command line

```bat
openai-budget status                        :: free pool, local writes, source
openai-budget sync                          :: pull org usage now
openai-budget set-key sk-admin-…
openai-budget can gpt-5.4-mini 1200         :: dry-run of can_spend
openai-budget path                          :: where state and config live
```

## Related libraries

- [`gemini-budget`](https://github.com/biolog-end/gemini-budget) — the same, for Gemini.
- [`ai-router`](https://github.com/biolog-end/ai-router) — shared key vault and
  fault-tolerant request layer that drives this budget.
