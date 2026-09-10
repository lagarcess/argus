# Targeted result readout measurement

Status: **founder approved up to $5 for the targeted 48-completion comparison
and at most four fresh browser backtests**. Execution requires genuine fixtures,
the final clean code SHA and the price/budget guard. This targeted comparison
does **not** authorize a fingerprint update, even after successful live results.
Finish this lane's approved targeted proof, then stop and report. No full live
eval or fingerprint regeneration may run without a new, explicit founder go.

The comparison invokes each checkout's real completed-result entry point and
`llm_result_breakdown_message`, including their production draft validation and
complete fallback. It does not run the interpreter, fetch market data, simulate
a run, write product history, or measure browser transport. Those boundaries
remain explicit in its report.

Quick take receives the execution envelope and sibling result card used by
production, reconstructed from the saved canonical fields. It receives every
stored metric and now reads the optional chart from that card. Breakdown
receives the saved run's optional chart. The earlier free sizing probe passed
the whole stored run as the Quick take envelope, which concealed a production
projection gap: the chart is on the sibling card, not the execution envelope.
Both the projection and harness were corrected before any paid comparison.

## Cases and ordering

Three source-verified saved runs, each in `en` and `es-419`:

1. DOCN buy and hold since September 2023, benchmark SPY.
2. DCA with an explicit recurring contribution, separate starting capital,
   modeled fees/slippage and their persisted results.
3. An indicator run, preserving whichever optional metrics and chart the run stored.

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
does not change the synthetic examples into empirical evidence. Fresh DOCN and RSI fixtures are now retained under `live-browser/stored-runs/`.
The DCA chat setup hit an unrelated capital-interpretation failure. The fourth
simulation allowance supplied its genuine fixture through the typed engine
path; that fixture does not represent a successful DCA browser journey.

For an empirical fixture, `source.kind` is `recorded_run`; `source.artifact`
points to the approved sanitized saved-run JSON, relative to the fixture file;
`source.sha256` hashes that source file; optional `source.json_path` locates the
run inside it; `provider_mode` and `captured_at` record its origin. The runner
compares the fixture run to that exact source object. Keep the run's stored
metric precision and absent fields; do not fabricate a curve or full ledger.

## Cost and execution bounds

Founder-approved total allowance: **up to $5**, using **$3.50 for the 48-completion
comparison and at most $1.50 for browser proof**, with at most four fresh
simulations. Final usage is three UI-completed backtests and one direct typed
DCA engine fixture after its chat setup failed. This supersedes the earlier $1 targeted measurement / $2 total
request. No full live suite or fingerprint regeneration is included in this
authorization.
The recorded DOCN chart makes the earlier 8,000-byte input assumption invalid;
the refreshed candidate preflight reaches 48,835 bytes. Keep all stored metrics and the optional
chart, with a 60,000-byte request bound.

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
**$3.482112**. The $3.50 measurement allocation covers that bound. Browser spending
is tracked separately; its original $1 guard remains in force unless explicitly
raised within the combined $5 allowance. The four-backtest limit is unchanged.

Sum that for all 48 task completions. Prices may be supplied in a small JSON
file with `verified_at`, `source`, and `models`, where each configured model has
`input_per_million` and `output_per_million`. Refresh those public prices before
execution; do not infer them from model names. The caller's approved
dollar cap must cover this bound. Every actual HTTP attempt reserves against
the remaining cap before it is sent; unknown prices, excess retries and excess
payload/output sizes fail closed. Missing response-cost evidence retains the
entire pre-request reservation as a conservative charge. Reports separate
observed costs from unknown charges and never describe that bound as an exact
bill. Cancellation and ordinary provider retries remain visible; a missing
reservation, unpriced model, or cost exceeding its reservation stops further
visits and preserves the observations already collected.

## Ready commands

Free preflight, with the lane's prepared fixture examples:

```bash
poetry run python -m tests.evals.result_readout_eval \
  --baseline /private/tmp/model-result-readouts-baseline-d088 \
  --candidate /Users/garces/.codex/worktrees/7c2d/private-alpha-next \
  --output /private/tmp/model-result-readouts-preflight.json
```

An isolated baseline clone was created after the shared checkout advanced.
The selected immutable baseline was verified at `d0884c3de81f8c53d454ac4f68f461d3b5dd77e3`
and clean. Do not rely on that path remaining at the same commit; the runner
records both current SHAs. The free check tolerates dirty development code and
labels it explicitly. The separate recorded DOCN size preflight observed
7,601 bytes on baseline and 48,835 bytes on candidate, exposing why synthetic
fixture sizing was insufficient. The two other cases in that earlier partial fixture set were synthetic.
The final `recorded-fixtures.json` uses three complete genuine saved runs and
verified source hashes; its free preflight is sizing/configuration evidence.

Once three genuine source-verified fixtures and final clean candidate code
exist, the authorized targeted command is:

```bash
poetry run python -m tests.evals.result_readout_eval \
  --baseline /private/tmp/model-result-readouts-baseline-d088 \
  --candidate /Users/garces/.codex/worktrees/7c2d/private-alpha-next \
  --fixtures docs/reports/evidence/model-result-readouts/recorded-fixtures.json \
  --pricing /private/tmp/model-result-readouts-refreshed-prices.json \
  --budget-usd 3.5 --live \
  --output /private/tmp/model-result-readouts-live.json
```

The preparation subtask does not execute this command. No environment file is
created or edited. The provider credential is inherited/read using the normal runtime; only its
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

The baseline manifest's previous full scorecard is retained as a **historical
reference only**, by exact file hash, original totals and every original case;
none are counted as freshly run. At initial preflight its recorded totals were
61 passed and 1 failed. One prior case,
`asset_discovery_not_result_followup_issue_244`, has a result_summary receipt;
its full-turn result is historical evidence, not remeasured by this targeted
composer probe. Cases without observed readout calls are explicitly retained
without new-pass claims. Compare candidate and baseline per case, language,
surface and replicate; explain any regression rather than waiving it.

The captain may retain the targeted scorecard and qualitative review as
readout evidence. **Never point the prompt fingerprint or `last_measured` at
this targeted scorecard. Do not regenerate the fingerprint.** A clean targeted
result is not full-suite evidence or fingerprint authority.

Finish this lane's scope and the approved targeted/browser proof, then stop and
report the results. **No full live eval and no fingerprint regeneration until
an explicit founder go.** There is no automatic follow-on measurement. Preserve
the targeted comparison and prior
full scorecard as historical references. Founder authority for merging this
lane and deploying remains unchanged.

## Free verification

```bash
poetry run pytest tests/test_interpreter_prompt_surface.py \
  tests/evals/test_result_readout_eval.py -q --no-cov
```

The extractor now covers inline readout message dictionaries, the Breakdown
API owner and the shared readout instruction constant/schema. It deliberately
does not sweep unrelated API prose into this lane. The unchanged fingerprint
may remain red at the targeted-proof handoff. That does not authorize changing
it: report the outstanding fingerprint gate and wait for explicit founder go.
