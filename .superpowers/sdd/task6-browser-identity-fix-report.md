# Task 6 Browser Identity Correction

## Scope

- Base: `ed176ee626a980189c029120089c0f59dc66e1a8`
- Owned production file:
  `src/argus/agent_runtime/confirmation_artifacts.py`
- Owned test file: `tests/test_backtest_job_by_action.py`
- No route, public API, lifecycle vocabulary, schema, migration, provider,
  environment, service, browser, or database change.

## Reproduced failure and root cause

The lane-exclusive browser checkpoint completed one accepted daily Run exactly
once, but the owner-scoped by-action lookup returned `409`.

The persisted confirmation card and artifact reference hashed the result of
`LaunchBacktestRequest.model_dump(mode="python")`. That serialization used the
model field name and included every default, so it invented
`execution_realism: null`. The execute/admission path instead hashed the actual
embedded launch request, which correctly omitted the absent
`_execution_realism` alias. Their full hashes therefore disagreed even though
the validated Run itself was the same.

## Exact-final red

Updated
`test_real_confirmation_persists_full_launch_identity_used_by_job_lookup` to
derive the admitted identity from the real execute-stage embedded request, not
from the validation result on both sides.

The production-shaped payload explicitly includes the null `position_size` and
`cadence` fields but omits `_execution_realism`.

Command:

```text
poetry run pytest \
  tests/test_backtest_job_by_action.py::test_real_confirmation_persists_full_launch_identity_used_by_job_lookup \
  -q --no-cov
```

Observed before the production correction:

```text
Left contains 1 more item:
{'execution_realism': None}
1 failed
```

## Minimal correction

The already validated `LaunchBacktestRequest` now serializes:

- with declared aliases;
- with unset defaults excluded; and
- with explicitly supplied null fields retained.

The regression also proves an explicitly supplied `_execution_realism` object
remains present under its canonical alias. Validation and action admission are
unchanged. No identity hash is exposed publicly.

## Green verification

```text
poetry run pytest tests/test_backtest_job_by_action.py -q --no-cov

20 passed
```

```text
poetry run ruff check \
  src/argus/agent_runtime/confirmation_artifacts.py \
  tests/test_backtest_job_by_action.py

All checks passed!
```

```text
git diff --check

exit 0
```

## Complexity reassessment

The production delta is one typed Pydantic serialization option change. It adds
no helper, branch, state, parser, fallback, or public surface. The test now
compares the confirmation identity to the request actually passed toward
admission, so reintroducing an unset default or field-name alias would fail.

The slice is independently committable. Its resulting commit SHA is recorded in
the release-captain handoff because a commit cannot include its own hash.
