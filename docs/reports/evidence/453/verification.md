# Issue 453 Task 5 verification

## Provenance

- Historical RED base: `8025672924d1c74eb80cc926c72b5d8574b613d7`.
- Task 5 documentation diff base: `55a11cdc992eb622d98c862f171c5dc7c6d85b4b`.
- Prior command execution head: `55a11cdc992eb622d98c862f171c5dc7c6d85b4b`.
- First Task 5 documentation and evidence commit:
  `82e6e59350b07290d9e8ef7cdc070781e4c81cf9`.
- Refreshed command execution head:
  `53e35890ae3173a9a5eedb13d7afd6e14ef10f1c`.

The original RED proof remains in `baseline.md`: the untouched base recorded
`10 failed, 197 deselected` for the issue-specific regression subset. The
documentation change here is additive and does not change any API JSON shape.

## Prior intermediate focused backend suite

Process-local provider and execution guardrails were set without creating or
reading an environment file:

```bash
ARGUS_RUN_LIVE_EVALS=0 \
ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest --no-cov \
  tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py \
  tests/agent_runtime/test_options_semantic_admission.py \
  tests/agent_runtime/test_validation_failure_copy.py \
  tests/agent_runtime/test_conversation_stages.py -q
```

At the prior command execution head, the result was `205 passed, 12 failed in
7.50s`. This was intermediate evidence, not a terminal readiness claim.

All 12 failures are the same pre-existing shared assertion family:
`test_prose_bearing_contradiction_keeps_verdict_through_readiness_and_admission`
in `test_options_semantic_admission.py`. It expects a model-authored refusal in
`assistant_response`; the locked issue behavior suppresses that field so the
typed clarification stage owns the visible response. The issue-specific
regressions in this command passed. This is a test-expectation mismatch outside
the Task 5 documentation scope, not a documentation regression. Task 3 later
reconciled the 12 now-stale prose-preservation expectations; the refreshed
command below is the current result.

## Refreshed focused backend suite

The exact same command and process-local provider and execution guardrails were
rerun at `53e35890ae3173a9a5eedb13d7afd6e14ef10f1c`.

Result: `217 passed in 6.18s`.

This green deterministic result does not make a terminal readiness claim.
Later branch reconciliation, browser proof, and release gates remain separate
evidence surfaces.

## Refreshed free mocked interpreter evaluation

```bash
ARGUS_RUN_LIVE_EVALS=0 \
ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=false \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py -q
```

The exact command ran at `53e35890ae3173a9a5eedb13d7afd6e14ef10f1c` and
returned `72 passed in 18.83s`. It is the free mocked command from
`tests/evals/README.md`; it did not request live evals or provider execution.

## Contract boundary audit

The current `### Research Responses` section and every byte after it hash to
`d5d1193f1af725bd8aad1b9ab352942affc8ddff1768f5c03c3c18f59ff39d80`.
The same extraction from base SHA
`8025672924d1c74eb80cc926c72b5d8574b613d7` has the identical hash. Task 5
changed only the clarification contract text before that heading.

## Classification

- Baseline: the original issue-specific controls were RED on the untouched
  base, as recorded in `baseline.md`.
- Refreshed fix evidence: the current focused run is green and the free mocked
  interpreter suite is green at the refreshed command execution head.
- Remaining boundary: these deterministic checks do not replace later branch
  reconciliation, browser proof, or release-gate evidence.
