# Issue #483 Deterministic Verification

## Candidate contract

- Original integration base: `bd96746f6f4c8d7948b6b6e5cec6d1113450847b`
- Base contains merged PR #479.
- Worker: `codex/issue-483-resolved-state`
- Runtime owner changed: `asset_resolution_context.py`
- No frontend, locale, API, database, DCA card, deployment, or environment file changed.
- Issue #455 remains separate because its canonical facts belong to the DCA domain/card/calendar surface, not the current-turn asset preflight.

The implementation gives a successful asset extraction one meaning: it owns the result even when the valid result contains zero current-turn assets. `None` now means only disabled preflight, exhausted exceptions, or invalid schema candidates. Explicit incomplete extraction remains a typed blocker for unsupported, partial, ambiguous, and overflowed baskets.

## Focused proof

The dedicated invariant covers:

- valid empty extraction stops fallback;
- actual primary failure still uses fallback;
- English and es-419 pending-amount turns retain KO and reach confirmation;
- asset, recurring amount, date range, and cadence questions derive from canonical missing fields;
- response-intent facts and requested fields cannot overlap on a resolved field;
- a genuinely missing asset is requested exactly once.

Focused owner command:

```bash
poetry run pytest \
  tests/agent_runtime/test_provider_asset_ownership.py \
  tests/agent_runtime/test_issue_483_resolved_state.py \
  -q --no-cov
```

Result: PASS, `35 passed in 0.82s`.

Expanded interpreter corridor:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/agent_runtime/test_provider_asset_ownership.py \
  tests/agent_runtime/test_issue_483_resolved_state.py \
  tests/agent_runtime/test_turn_execution.py \
  tests/agent_runtime/test_conversation_stages.py \
  tests/agent_runtime/test_llm_interpreter_artifact_capability_repairs.py \
  tests/agent_runtime/test_llm_interpreter_semantic_contracts.py \
  -q --no-cov
```

Result: PASS, `284 passed in 7.28s`.

## Hermetic runtime and mocked evaluation

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov
```

Result: PASS, `1668 passed in 17.26s`.

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  -q --no-cov
```

Result: PASS, `72 passed in 4.35s`. No paid provider path ran.

## Full backend classification

The sandboxed full backend command collected 5,601 tests and returned:

```text
6 failed, 5100 passed, 495 skipped, 5 warnings in 80.57s
```

All six failures reproduced unchanged in a temporary detached worktree at integration SHA `bd96746f6f4c8d7948b6b6e5cec6d1113450847b`: `6 failed, 2 passed in 1.68s` for the affected subset.

Five failures were sandbox-only permissions: process-tree inspection and loopback test-server binding. The complete permission-sensitive subset ran outside the sandbox and passed: `7 passed in 4.56s`.

The remaining failure is the existing `test_openrouter_failure_log_reports_raising_origin` assertion. Both candidate and untouched integration produce `error_origin=<unknown>`. It is unrelated to the asset preflight diff.

## Static and structural checks

- `poetry run ruff check .`: PASS.
- `git diff --check`: PASS.
- `poetry run python scripts/check_modularity_budget.py`: PASS, zero violations.
- The calibrated seven-call worst-case test still reaches the allowance and blocks call N+1. Its primary asset preflight now fails genuinely before the fallback instead of treating a valid empty result as failure.
- No environment file was read into the repository, written, or changed.

## Live acceptance boundary

The accepted real-interpreter Guest replay is intentionally captured after the candidate is committed so its receipt can name an exact source SHA. It will be posted as durable PR evidence with English and es-419 outcomes, route receipts, and provider-reported cost. This deterministic file does not claim that live gate yet.
