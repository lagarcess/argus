# Issue 151 Repro Notes

Base: `origin/codex/private-alpha-next` at `eca0b7eb0bc10c27e02559850a855fb6cba48e86`.

Scope: read-only repro scout. Runtime source was not edited. The only repo writes are:

- `tests/agent_runtime/test_post_result_edit_routing.py`
- `NOTES-151.md`

## Baseline

Command:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_post_result_edit_routing.py -q
```

Result at HEAD before the repro test:

```text
11 passed in 1.80s
```

## Repro Test

Added strict expected-fail:

```text
tests/agent_runtime/test_post_result_edit_routing.py::test_post_result_readiness_prose_materializes_confirmation_payload
```

Marker:

```python
@pytest.mark.xfail(strict=True, reason="#151 — remove when fixed")
```

The mocked shape follows the post-result variant path:

- latest completed result is AAPL/MSFT DCA from `2020-02-01` to `2026-07-02`
- follow-up asks to try NVDA at the same monthly contribution and same window
- interpreter returns a runnable typed draft plus model readiness prose
- reason codes include `latest_result_window_bound` and `result_followup_target_inferred`
- draft includes `sizing_mode="capital_amount"`, matching the executable-complete shape that currently falls through the inferred non-patch guard

## Red Evidence Before Xfail

Command:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_post_result_edit_routing.py::test_post_result_readiness_prose_materializes_confirmation_payload -q
```

Observed failure before adding `xfail`:

```text
AssertionError: assert 'ready_to_respond' == 'ready_for_confirmation'
```

That is the issue: typed facts are present, but the stage chooses a prose response instead of the confirmation materialization path.

## Expected Typed Contract

The test asserts typed outcomes only:

- post-result executable draft returns `ready_for_confirmation`
- confirmation stage returns `await_approval`
- `confirmation_payload` exists and is for `NVDA`
- the confirmation card's structured `run_backtest` action returns `approved_for_execution`
- the approval result carries `confirmation_payload`

## Current Xfail Check

Command:

```bash
poetry run pytest --no-cov tests/agent_runtime/test_post_result_edit_routing.py::test_post_result_readiness_prose_materializes_confirmation_payload -q
```

Result after adding strict xfail:

```text
1 xfailed in 0.39s
```
