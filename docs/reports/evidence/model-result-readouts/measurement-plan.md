# Targeted result readout measurement

Status: **prepared, no paid calls authorized or made**. This document and the
free preflight are not live evidence and do not authorize a fingerprint update.

The comparison invokes each checkout's real `explain_stage_async` and
`llm_result_breakdown_message`, including their production draft validation and
complete fallback. It does not run the interpreter, fetch market data, simulate
a run, write product history, or measure browser transport. Those boundaries
remain explicit in its report.

## Cases and ordering

Three source-verified saved runs, each in `en` and `es-419`:

1. DOCN buy and hold since September 2023, benchmark SPY.
2. DCA with an explicit recurring contribution, separate starting capital,
   modeled fees/slippage and their persisted results.
3. An indicator run with sparse optional metrics or absent chart data.

Each case/language runs **baseline, candidate, candidate, baseline**. Each visit
composes Quick take, then Breakdown: 24 visits, 48 task completions, two
replicates per variant. The candidate Breakdown receives the accepted Quick
take from its own visit. A failed Quick take gives it no partial draft.

The committed harness examples in `tests/evals/result_readout_fixtures.json`
are **authored synthetic TEST ONLY data**, including their DOCN figures. None of
these example numbers may be represented as historical performance. Paid mode
rejects every synthetic source. A genuine saved DOCN/SPY run was subsequently
located through a read-only database query, with no provider call. Its sanitized
typed snapshot remains separate under `/private/tmp/`; it is not committed and
does not change the synthetic examples into empirical evidence. The DCA and
indicator empirical fixtures are still missing.

For an empirical fixture, `source.kind` is `recorded_run`; `source.artifact`
points to the approved sanitized saved-run JSON, relative to the fixture file;
`source.sha256` hashes that source file; optional `source.json_path` locates the
run inside it; `provider_mode` and `captured_at` record its origin. The runner
compares the fixture run to that exact source object. Keep the run's stored
metric precision and absent fields; do not fabricate a curve or full ledger.

## Cost and execution bounds

Updated proposed founder allowance: **$4 for the 48-completion comparison, plus
a separate $1 for browser proof, $5 total**. This supersedes the earlier $1
targeted measurement / $2 total request. No paid approval has been received.
The recorded DOCN chart makes the earlier 8,000-byte input assumption invalid;
the refreshed candidate preflight reaches 48,835 bytes. Keep all stored metrics and the optional
chart, and raise the proposed request bound to 60,000 bytes.

Verified local task settings during the free preflight:

| Task | Tier | Primary | Fallback | Output ceiling |
| --- | --- | --- | --- | --- |
| result_summary | chat | deepseek/deepseek-v4-flash | qwen/qwen3.5-9b | 700 tokens |
| result_breakdown | context | openai/gpt-oss-120b | deepseek/deepseek-v4-flash | 2,400 tokens |

Neither tier changes. The bound reserves for up to four actual HTTP attempts
per task (two configured models, each with a possible reasoning retry).
Requests are limited to 60,000 UTF-8 bytes, including their schema. Counting
bytes as the input-token upper bound is deliberately conservative. No oversized
payload is silently trimmed. Genuine long chart data can require a revised
estimate before execution.

For each task the worst-case reservation is:

`4 * max_for_configured_models((60000 * input_price_per_million + output_ceiling * output_price_per_million) / 1000000)`

Refreshed official maximum rate envelopes, USD per million input/output tokens:

| Configured model | Input | Output | Source |
| --- | --- | --- | --- |
| deepseek/deepseek-v4-flash | 0.21 | 0.56 | [OpenRouter DeepSeek](https://openrouter.ai/deepseek/deepseek-v4-flash) |
| qwen/qwen3.5-9b | 0.17 | 0.25 | [OpenRouter Qwen](https://openrouter.ai/qwen/qwen3.5-9b) |
| openai/gpt-oss-120b | 0.35 | 0.95 | [OpenRouter GPT-OSS](https://openrouter.ai/openai/gpt-oss-120b) |

Including all configured primary/fallback models, four attempts per completion
and the 60,000-byte bound, the 48-completion worst-case reservation is
**$3.482112**. The proposed $4 measurement allowance covers that bound. Browser
spending is separate and capped by the proposed $1 browser allowance.

Sum that for all 48 task completions. Prices may be supplied in a small JSON
file with `verified_at`, `source`, and `models`, where each configured model has
`input_per_million` and `output_per_million`. Refresh those public prices before
seeking approval; do not infer them from model names. The caller's approved
dollar cap must cover this bound. Every actual HTTP attempt reserves against
the remaining cap before it is sent; unknown prices, excess retries and excess
payload/output sizes fail closed. Missing response-cost evidence stops further
visits and preserves the observations already collected.

## Ready commands

Free preflight, with the lane's prepared fixture examples:

```bash
poetry run python -m tests.evals.result_readout_eval \
  --baseline /Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next \
  --candidate /Users/garces/.codex/worktrees/7c2d/private-alpha-next \
  --output /private/tmp/model-result-readouts-preflight.json
```

The selected baseline was verified at `d0884c3de81f8c53d454ac4f68f461d3b5dd77e3`
and clean. Do not rely on that path remaining at the same commit; the runner
records both current SHAs. The free check tolerates dirty development code and
labels it explicitly. The separate recorded DOCN size preflight observed
7,601 bytes on baseline and 48,835 bytes on candidate, exposing why synthetic
fixture sizing was insufficient. The other two cases in that partial fixture
set are still synthetic; this is free size/configuration evidence, not paid
measurement or committed-head acceptance.

After approval, recorded fixtures and final clean candidate code exist, the
paid command is:

```bash
poetry run python -m tests.evals.result_readout_eval \
  --baseline /Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next \
  --candidate /Users/garces/.codex/worktrees/7c2d/private-alpha-next \
  --fixtures docs/reports/evidence/model-result-readouts/recorded-fixtures.json \
  --pricing /private/tmp/model-result-readouts-prices.json \
  --budget-usd 4 --live \
  --output /private/tmp/model-result-readouts-live.json
```

Do not run this command now. No environment file is created or edited. The
provider credential is inherited/read using the normal runtime; only its
presence is reported. Both worktrees must stay clean at their recorded SHAs
through every visit. Live output must stay outside both checkouts so writing
evidence cannot dirty the measured code. Existing output files are not replaced.

## Evidence and review

The raw report preserves fixture/source hashes; checkout SHAs and cleanliness;
runner/probe hashes; Python version; model/task/tier/timeout/temperature;
explicit recorded-run/no-fetch provider modes; request hashes/sizes; raw model
drafts; complete accepted or backend-fallback text; source/fallback/failure
fields; route receipts; provider response costs; and latency. It never records
authorization headers or environment values.

Baseline model drafts were private. `complete_text` on the baseline is the
private composer's output, **not what the baseline reader showed**. Candidate
generator output also needs separate browser proof for the language-aware
reader. Backend fallback text is retained for generator diagnosis; the browser
must independently prove today's template inside each unchanged frame.

The raw targeted scorecard starts with all 48 texts pending review and no new
passes. Review both repetitions of every case/language/surface against its run:
correct language, grounded figures and benchmark direction, meaning beyond the
card, short Quick take versus deeper distinct Breakdown, no invented causes,
forecast, advice, internal field names or em dash. Record reviewer and
case-by-case dispositions. A complete fallback remains a model-quality failure,
even when it is safe product behavior. Do not turn acceptance by a deterministic
validator into a claim of good prose. No separate paid prose judge is included.

The manifest's previous full scorecard is retained by exact file hash, original
totals and every original case; none are counted as freshly run. Its recorded
totals are 61 passed and 1 failed. One prior case,
`asset_discovery_not_result_followup_issue_244`, has a result_summary receipt;
its full-turn result is historical evidence, not remeasured by this targeted
composer probe. Cases without observed readout calls are explicitly retained
without new-pass claims. Compare candidate and baseline per case, language,
surface and replicate; explain any regression rather than waiving it.

Only after the approved live comparison and its qualitative disposition may
the captain commit a targeted scorecard and point the fingerprint at it. The
targeted totals must agree with `last_measured`; do not claim the 62-case full
suite was rerun. Preserve the prior full evidence and existing failure in the
comparison report. After integration changes, compare the measured prompt
surface and remeasure this lane's affected cases when required.

## Free verification

```bash
poetry run pytest tests/test_interpreter_prompt_surface.py \
  tests/evals/test_result_readout_eval.py -q --no-cov
```

The extractor now covers inline readout message dictionaries, the Breakdown
API owner and the shared readout instruction constant/schema. It deliberately
does not sweep unrelated API prose into this lane. The unchanged fingerprint
is expected to fail until genuine approved measurement exists.
