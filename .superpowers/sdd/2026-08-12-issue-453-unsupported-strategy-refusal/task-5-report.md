# Task 5 report: contract and deterministic evidence

## Files

- `docs/API_CONTRACT.md`
- `docs/reports/evidence/453/baseline.md` preserved without modification
- `docs/reports/evidence/453/verification.md`

## Contract decisions

- Replaced the generic unsupported-recovery example that displayed
  `raw_value` with a typed strategy and options payload.
- Clarified that `raw_value` remains opaque runtime evidence and is never a
  generic display subject, generic clarifier voice input, assistant prompt, or
  deterministic fallback copy.
- Documented separate routes for unsupported strategy capability, incomplete or
  unparseable extraction, and starting-capital bounds.
- Documented finite typed starting-capital bounds: a finite minimum alone is a
  valid floor, while a present maximum requires a finite ordered pair.
- Preserved the typed bar-size exception for
  `unsupported_time_granularity` without reopening generic raw-value display.
- Kept the API change additive and clarifying. No JSON shape was removed or
  changed.

## Prior intermediate commands and results

Prior command execution head: `55a11cdc992eb622d98c862f171c5dc7c6d85b4b`.

```bash
ARGUS_RUN_LIVE_EVALS=0 ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture poetry run pytest --no-cov \
tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py \
tests/agent_runtime/test_options_semantic_admission.py \
tests/agent_runtime/test_validation_failure_copy.py \
tests/agent_runtime/test_conversation_stages.py -q
```

Result: `205 passed, 12 failed in 7.50s`. This is intermediate evidence, not a
terminal readiness claim. Every failure is the shared stale assertion that
expects model-authored refusal prose despite the locked suppression rule. No
issue-specific test failed.

```bash
ARGUS_RUN_LIVE_EVALS=0 ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture poetry run pytest \
tests/evals/test_measurement_eval_harness.py \
tests/evals/test_chat_runtime_eval_manifest.py \
tests/evals/test_chat_runtime_trajectory_harness.py -q
```

Result: `72 passed in 24.50s`.

## Research Responses byte-preservation proof

The section beginning at `### Research Responses` and all following content
was extracted from the working tree and the exact base
`8025672924d1c74eb80cc926c72b5d8574b613d7`. Both SHA-256 values are
`d5d1193f1af725bd8aad1b9ab352942affc8ddff1768f5c03c3c18f59ff39d80`.

## Self-review

- Reviewed the diff to confirm it touches only the allowed clarification text
  before `### Research Responses`, verification evidence, and this report.
- Kept `baseline.md` intact so Task 1's original RED evidence remains durable.
- Did not create an environment file, run a live eval, or expose credentials.

## Historical concern

The prior focused-suite run was not fully green because 12 shared tests still
expect the model-authored refusal prose that issue #453 deliberately suppresses.
Task 3 later reconciled the obsolete expectations. This concern is retained as
historical intermediate evidence. Task 5 makes no code or test changes.

## Fix round 1

Provenance roles are explicit in `docs/reports/evidence/453/verification.md`:
the historical RED base is `8025672924d1c74eb80cc926c72b5d8574b613d7`, the
Task 5 diff and prior execution base is
`55a11cdc992eb622d98c862f171c5dc7c6d85b4b`, the first Task 5 evidence commit
is `82e6e59350b07290d9e8ef7cdc070781e4c81cf9`, and the refreshed execution
head is `53e35890ae3173a9a5eedb13d7afd6e14ef10f1c`.

The refreshed focused backend command passed `217` tests in `6.18s`. The exact
free mocked eval command passed `72` tests in `18.83s`. Both runs used
process-local `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture` with
live evals and workflow execution disabled.

The starting-capital contract now states the actual projection rule: a finite
minimum can provide floor copy by itself; a present maximum is accepted only as
a finite ordered pair. Missing minimum, malformed, non-finite, or reversed
values fail closed.

The `### Research Responses` section and all following bytes still hash to
`d5d1193f1af725bd8aad1b9ab352942affc8ddff1768f5c03c3c18f59ff39d80` against
the historical RED base. The refreshed deterministic checks remain
non-terminal: branch reconciliation, browser proof, and release gates are
separate evidence surfaces.
