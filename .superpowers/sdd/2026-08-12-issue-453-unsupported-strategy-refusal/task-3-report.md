# Task 3 report: admission and launch validation

## Scope

- `src/argus/agent_runtime/interpreter/unsupported_admission.py`
- `src/argus/agent_runtime/stages/launch_validation_recovery.py`
- `src/argus/agent_runtime/stages/confirm.py`

No test files required modification because the task-owned issue #453 tests were
already present and failed on the requested behavior.

## RED

Command:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_options_semantic_admission.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or unsupported_request_turn_act_contradiction'
```

Result: 2 failed, 115 deselected.

- `test_issue_453_unsupported_request_turn_act_contradiction_blocks_without_prose`
  found the model-authored refusal still in `assistant_response`.
- `test_issue_453_starting_capital_bounds_recover_without_confirmation_card`
  found `unsupported_starting_capital` missing `minimum` and `maximum`.

## Change and reasoning

- The unsupported-admission boundary now always sets `assistant_response` to
  `None`; clarification remains responsible for user-visible recovery text.
- The capital recovery constraint carries `minimum` and `maximum` from the
  canonical backtesting constants, without restating their values.
- Confirm-stage recovery now selects raw evidence by failure cause: capital
  amount for `invalid_starting_capital`, timeframe for other launch errors.
  This keeps the typed capital constraint from inheriting an unrelated `1D`
  value.
- The existing DCA confirmation regression uses a `$200`
  `dca_accumulation` contribution and reaches `await_approval`, proving the
  recurring-contribution exemption remains intact.

## GREEN and verification

Focused issue command:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_options_semantic_admission.py tests/agent_runtime/test_conversation_stages.py -q -k 'issue_453 or unsupported_request_turn_act_contradiction'
```

Result: 1 passed, 1 failed, 115 deselected. All Task 3 structural assertions
pass. The remaining assertion expects the clarification fallback to include
`$1,000`; the current fallback is owned by the separate clarification/projection
task and is outside this task's permitted surface.

DCA regression command:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_conversation_stages.py::test_confirm_stage_resolves_structured_month_range_into_launch_payload tests/agent_runtime/test_conversation_stages.py::test_confirm_stage_blocks_carried_dca_cap_before_ready_card -q
```

Result: 2 passed.

Quality commands:

```bash
poetry run ruff format --check src/argus/agent_runtime/interpreter/unsupported_admission.py src/argus/agent_runtime/stages/launch_validation_recovery.py src/argus/agent_runtime/stages/confirm.py
poetry run ruff check src/argus/agent_runtime/interpreter/unsupported_admission.py src/argus/agent_runtime/stages/launch_validation_recovery.py src/argus/agent_runtime/stages/confirm.py
git diff --check
```

Result: all passed.

## Self-review

- The admission change is at the shared fail-closed boundary, so no
  unsupported verdict can preserve model-authored acknowledgment prose.
- Bounds are typed numeric facts sourced from engine constants.
- DCA still uses its existing zero-floor, positive-only envelope rule.
- Scope audit includes only the three assigned production files and this
  report.

## Concern

The final clarification-copy assertion in the focused command remains RED
until the Task 4 clarification/projection work teaches its fallback to render
the typed capital bounds. No clarification or projection code was changed here.
