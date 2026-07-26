# Task 8 Run identity fixture correction report

## Scope

- Starting checkpoint:
  `49d17d0adeb5588e8c3df5290f0d918e950f3abd`.
- Owned product test:
  `tests/test_chat_turn_route_matrix.py`.
- Correction: supply the canonical `Idempotency-Key` that matches the
  `run_backtest` action's `confirmation_id`.
- No production code, assertion, API contract, schema, RLS, provider, runtime,
  frontend, or dependency change.
- No browser, service, Docker, Supabase, provider, live eval, push, PR, merge,
  deployment, or issue action.

## Red evidence

The exact affected test was first run against the unmodified starting
checkpoint with explicit hermetic memory, memory-checkpointer, synthetic market
data, mock-auth, and blank provider-key settings:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_PERSISTENCE_MODE=memory \
ARGUS_DEV_MEMORY_FALLBACK=true \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
ARGUS_CHECKPOINTER_MODE=memory \
ARGUS_MOCK_AUTH=true \
poetry run pytest \
  tests/test_chat_turn_route_matrix.py::test_run_backtest_route_uses_message_only_owner \
  -q --no-cov
```

Result: `1 failed`. The route returned HTTP `400`, while the test expected HTTP
`200`. This is the expected fixture failure: the request omitted the required
Run identity header and was correctly rejected by strict production validation
before the intended stale-confirmation path.

## Minimal correction

The test request now sends:

```python
headers={"Idempotency-Key": "confirmation-1"}
```

This exactly matches `action.payload.confirmation_id`. Comparable Run-action
tests use the same canonical request shape. The correction changes no assertion
and does not weaken the missing, mismatched, or stale identity boundaries.

## Green and verification evidence

The exact affected test was rerun with the same hermetic environment:

```text
1 passed in 0.70s
```

The full owned test file was then run with the same hermetic environment:

```text
54 passed in 1.98s
```

Static and diff gates:

```bash
poetry run ruff check tests/test_chat_turn_route_matrix.py
git diff --check
```

Result: both passed.

## Complexity reassessment

The correction is one request-header fixture line. It reuses the existing
contract identity and introduces no helper, branch, state, abstraction, mock,
or production behavior. Removing any part of the correction would recreate the
proven false failure; adding more machinery would be disproportionate.

## Browser QA, caveats, and commit readiness

- Browser QA was neither required nor authorized for this test-only correction.
- No product caveat was introduced. Integrated Task 8 acceptance remains owned
  by the release-captain workflow and is not claimed by this correction.
- The test fixture and this evidence report form one coherent, independently
  committable correction.
