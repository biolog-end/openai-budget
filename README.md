# openai_budget

**English** | [Русский](README.ru.md)

One shared daily budget of free OpenAI tokens for every project on the machine.

With **Share inputs and outputs** enabled (Settings → Data controls), OpenAI gives free
tokens every day. On usage tiers 1–2 that is **250,000 tokens/day** for large models
(gpt-5.x, gpt-4.1, gpt-4o, o1, o3) and **2.5 million tokens/day** for mini and nano
models. The limit is shared by the whole organisation and resets at **00:00 UTC**, and
a request that crosses the limit is billed in full. Several projects on one account
each count only their own calls; this library keeps one state file per user and
reconciles it with the organisation usage report through an Admin key.

## Installation

```bat
pip install git+https://github.com/biolog-end/openai-budget.git
openai-budget set-key sk-admin-...      :: Settings → Organization → Admin keys
openai-budget status
```

For more accurate token estimates, install the `accurate` extra, which adds `tiktoken`:

```bat
pip install "openai-budget[accurate] @ git+https://github.com/biolog-end/openai-budget.git"
```

State and the Admin key live in `~/.openai_budget/` (`%USERPROFILE%\.openai_budget` on
Windows); `OPENAI_BUDGET_DIR` overrides the location. The Admin key can also come from
the `OPENAI_ADMIN_KEY` environment variable.

## Usage

```python
import openai_budget as ob

estimate = ob.estimate_tokens(prompt_text, images=0, expected_output=800)
ok, info = ob.can_spend('gpt-5.4-mini', estimate)   # syncs with the usage report every 5 minutes
if not ok:
    raise RuntimeError(info['reason'])              # "the free limit is almost used up…"

response = client.responses.create(model='gpt-5.4-mini', input=...)
ob.record_response('gpt-5.4-mini', response)       # Responses API or Chat Completions
```

- `can_spend()` treats *used* as the organisation snapshot plus everything recorded
  locally after it. Both groups keep an 8,000-token margin. Override it in
  `config.json`: `"groups": {"large": {"margin": 5000, "add_models": ["gpt-6"]}}`.
- Without an Admin key, only calls recorded through `record*()` by any project count.
- `ob.status()` returns a summary for user interfaces; `openai-budget status --json`
  prints the same in the console (or `python -m openai_budget.cli status` if the
  script is not on `PATH`).

### Chat Completions and streaming

`record_response()` also understands `chat.completions.create()` (`prompt_tokens` and
`completion_tokens`). When streaming, usage arrives only at the end: for Chat
Completions pass `stream_options={"include_usage": True}` and record the last chunk; for
the Responses API use the final response (`stream.get_final_response()` or the
`response.completed` event).

### What it adds on top of an Admin key

An Admin key alone shows what has already been spent, with a delay of a few minutes.
The library adds a decision *before* the request (will it fit, with a margin),
accounting between syncs (several apps cannot jump over the limit together) and one
place for the key and the limits. If you only want to look, `openai-budget sync` or the
usage dashboard at platform.openai.com/usage (grouped by service tier) is enough.

Token estimates use `tiktoken` when it is installed, otherwise a character count
(about 2.5 characters per token for Cyrillic, 4 for Latin text).

## Command line

```bat
openai-budget status [--json]          :: today's usage by group and model
openai-budget sync                     :: pull the organisation report now
openai-budget set-key sk-admin-...     :: save the Admin key
openai-budget can MODEL [TOKENS]       :: would a request of this size fit
openai-budget record MODEL IN OUT      :: record a call manually
```
