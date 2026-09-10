# Targeted result readout measurement: executed plan

**Completed and stopped:** 48 logical tasks, 80 HTTP attempts, all cases reviewed.
The [reviewed scorecard](targeted/scorecard.json) reports candidate quality 1/24,
baseline 0/24. The approved targeted comparison and bounded browser proof are
finished. No full live eval or fingerprint regeneration may run without a new,
explicit founder go. This document records the executed plan, not permission
to run it again.

## Scope and entry points

The comparison invokes each checkout's real completed-result entry point and
`llm_result_breakdown_message`, including production validation and complete
fallback. It does not run the interpreter, fetch market data, simulate a run,
write product history or measure browser transport.

Quick take receives the production execution envelope and sibling result card,
reconstructed from saved canonical fields. It receives all stored metrics and
reads the optional chart from that card. Breakdown receives the saved run's
optional chart. An earlier free sizing probe incorrectly passed the entire run
as the execution envelope; the production projection and harness were both
corrected before paid comparison.

## Cases and ordering

The final [recorded fixtures](recorded-fixtures.json) contain three exact,
source-verified saved runs, each composed in `en` and `es-419`:

1. DOCN buy and hold since September 2023, benchmark SPY.
2. DOCN DCA with distinct starting capital and recurring contribution, modeled
   fees/slippage and persisted outcomes.
3. SPY RSI with the run's full metrics and optional chart.

Each case/language runs baseline, candidate, candidate, baseline. Each visit
composes Quick take then Breakdown: 24 visits / 48 tasks, two replicates per
variant. Candidate Breakdown receives only the accepted Quick take from its
own visit; a failed Quick take supplies no partial draft.

The synthetic examples in `tests/evals/result_readout_fixtures.json` are TEST
ONLY and were never used as empirical performance. Paid mode rejects synthetic
sources. Each genuine fixture hashes the complete saved source object and
retains its metric precision, canonical configuration and optional chart.
Sampled trade markers are not a complete ledger. The DCA fixture came through
the direct typed engine after chat setup failed; it does not prove a successful
DCA browser journey.

## Approval, estimate and final cost

Founder authority: up to $5 for the targeted 48-task comparison and at most four
fresh simulations. The comparison cap was $3.50; the browser's $1 guard remained
unchanged. Three UI backtests and one direct DCA simulation used all four slots.
There is no authorization for extra trials, a full suite or a fingerprint update.

All stored metrics and actual chart data were retained. The 60,000-byte input
bound superseded an early 8,000-byte sizing assumption. Every HTTP attempt
reserved its worst-case cost before sending; unknown rates, oversized inputs,
excess retries or missing reservations failed closed. No payload was trimmed
to fit an estimate. The final free preflight is retained in
[targeted/preflight.json](targeted/preflight.json).

Verified task settings during execution:

| Task | Tier | Primary | Fallback | Output ceiling |
| --- | --- | --- | --- | ---: |
| result_summary | chat | deepseek/deepseek-v4-flash | qwen/qwen3.5-9b | 700 tokens |
| result_breakdown | context | openai/gpt-oss-120b | deepseek/deepseek-v4-flash | 2,400 tokens |

Neither tier changed. Up to four actual HTTP attempts were reserved per task:
two configured models, each with a possible reasoning retry. Input bytes were
used as a conservative token upper bound. The refreshed
[price snapshot](targeted/prices.json) records the rates and sources used.

For each task the reservation was:

`4 * max_for_configured_models((60000 * input_price_per_million + output_ceiling * output_price_per_million) / 1000000)`

The total worst-case reservation was $3.482112, within the $3.50 comparison cap.
Final provider-reported comparison cost was $0.0392605438; full reservations for
33 unreported attempts add $0.685936, giving an accounted bound of $0.7251965438.
Browser proof adds $0.1573110822 reported and $0.47132656 unreported reservations.
**Combined: $0.196571626 reported, $1.353834186 conservative bound.** The bound
is not an exact invoice; no unknown-cost attempt is treated as free.

## Execution and continuation

The comparison ran against clean baseline
`d0884c3de81f8c53d454ac4f68f461d3b5dd77e3` and clean candidate
`847cdd5e54e9e6256483ee2987a3f59bb79b8ebb`. The baseline used an isolated clone
at `/private/tmp/model-result-readouts-baseline-d088`. No environment file was
created or edited. The normal runtime inherited existing credentials; no secret
value is retained in evidence.

The executed command was equivalent to:

```bash
poetry run python -m tests.evals.result_readout_eval \
  --baseline /private/tmp/model-result-readouts-baseline-d088 \
  --candidate /Users/garces/.codex/worktrees/7c2d/private-alpha-next \
  --fixtures docs/reports/evidence/model-result-readouts/recorded-fixtures.json \
  --pricing /private/tmp/model-result-readouts-refreshed-prices.json \
  --budget-usd 3.5 --live \
  --output /private/tmp/model-result-readouts-live.json
```

The original process stopped after 21 visits because one provider worker still
had not settled after the composition deadline plus 105 seconds of receipt
waiting. Its probe exited and its pending request remained fully reserved.
Only the original three never-attempted visits continued, after process absence,
source hashes, unchanged code and remaining budget were verified. The
[continuation script](targeted/resume-remaining.py) and immutable original report
are preserved. No attempted case was retried; all first 21 outcomes are unchanged.
Live output stayed outside both measured checkouts until every call finished.

## Evidence and review

The [raw report](targeted/raw-completed.json) preserves fixture/source hashes;
clean checkout SHAs; runner/probe hashes; runtime/model/tier/timeout settings;
recorded-run provider mode; request hashes/sizes; raw model drafts; complete
accepted or backend-fallback text; source/fallback/failure fields; receipts;
reported costs; and latency. It does not contain authorization headers or
credential values.

Baseline model text was private, so it is not baseline browser evidence.
Candidate backend fallback text is diagnostic; the web renders its own current
localized template. Browser proof is separately bound to capture SHAs in
[live-browser/README.md](live-browser/README.md).

Codex reviewed all 48 texts against their run and paired Quick take for correct
language, grounded figures/comparisons, meaning beyond the card, complementary
short/deep roles and absence of causes, forecasts, advice, schema leakage or em
dashes. No fixed word cap or paid prose judge was added. Complete fallback fails
the model-writing bar even when safe. Deterministic acceptance is not a quality
pass. The [original language reviews](targeted/README.md) distinguish accepted
text errors from suppressed raw-draft observations.

The previous full scorecard named by the baseline fingerprint is retained by
hash, original totals (61 passed / 1 failed) and case disposition as historical
reference only. Its prior full-turn cases were not remeasured. The targeted
report has explicit `fingerprint_authority.eligible: false`. Never point
`last_measured` at it or claim it satisfies the full prompt-surface gate.

## Deterministic verification

The mocked harness and focused composer/transport/runner tests passed. The
extractor covers inline readout message dictionaries, the Breakdown API owner
and shared readout instructions/schema. The fingerprint remains unchanged and
its CI check remains red. Full live measurement and regeneration require a
separate explicit go. The founder alone merges and deploys.
