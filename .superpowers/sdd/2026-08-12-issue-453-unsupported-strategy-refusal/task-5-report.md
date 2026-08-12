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
- Documented finite typed starting-capital bounds and fail-closed handling for
  malformed, reversed, missing, or non-finite pairs.
- Preserved the typed bar-size exception for
  `unsupported_time_granularity` without reopening generic raw-value display.
- Kept the API change additive and clarifying. No JSON shape was removed or
  changed.

## Commands and results

Verification head: `55a11cdc992eb622d98c862f171c5dc7c6d85b4b`.

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

## Concerns

The current focused suite is not fully green because 12 shared tests still
expect the model-authored refusal prose that issue #453 deliberately suppresses.
Their runtime-test owner should update the obsolete expectation before release
readiness. The release controller must refresh the focused-suite evidence after
that reconciliation. Task 5 makes no code or test changes.
