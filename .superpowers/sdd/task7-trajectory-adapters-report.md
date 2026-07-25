# Task 7 — Concrete session-trajectory adapters

## Boundary

- Base: `1ea97afd7fa132d8022c4d0d5ef6f5ddedfdb8d7`
- Production source changed: none
- Runtime services, browser, providers, and databases used: none
- The adapter uses the real FastAPI application with the in-memory test owners.

## Red-before-green evidence

The inherited exact-final test was run before the adapter existed:

```text
ModuleNotFoundError: No module named tests.evals.chat_runtime_trajectory_adapters
```

The first concrete run then exposed:

- four trajectories whose issue masks were stale because every hard check passed;
- the two still-owned `#241` capability-route gaps;
- the seven still-owned `#251` effective-window/persistence gaps; and
- one `#238` stale-action fallback mismatch: the production fallback emits the
  final before a canonical `stage_outcome` and reports `needs_clarification`
  instead of the fixture's approved `ready_to_respond`.

No production behavior was changed to make the trajectory harness pass.

## Concrete adapter contract

`ConcreteTrajectoryRuntime`:

- creates a real conversation per sanitized trajectory through the FastAPI app;
- submits ordinary turns and structured actions to `/api/v1/chat/stream`;
- parses the canonical SSE returned by that route;
- reads persisted messages, lifecycle rows, job admission, usage counters, and
  route receipts from their real in-memory owners;
- performs reload through the conversation messages and by-action routes;
- performs Run admission through the canonical `admit_backtest_job_memory`
  owner rather than writing job or usage state directly;
- uses a named clock advance to exercise stale-turn reconciliation;
- replaces only the external LangGraph event source with deterministic typed
  payloads and records one typed provider receipt per interpreted turn; and
- emits only sanitized aliases in observations and scorecards.

The repeated HTTP/SSE submission and observation paths were collapsed into
shared helpers. The remaining trajectory-specific branches correspond to
distinct production owners: stale confirmation admission, response-option
authority, Run admission/replay, by-action reconciliation, and durable
ordinary-turn reconciliation. The final adapter is 1,062 lines; no general
attempt graph, alternate orchestrator, or fixture-only state repair was added.

## Mask disposition

| Trajectory | Status | Mask |
| --- | --- | --- |
| `alpha_session_01` | `expected_failed` | `#238`: step 3 `stage_outcome:` and `sse:` only |
| `alpha_session_02` | `passed` | removed |
| `alpha_session_03` | `expected_failed` | `#241`: steps 1–2 `capability_route:` only |
| `alpha_session_04` | `expected_failed` | `#251`: effective-window checks and step 3 persistence only |
| `alpha_session_05` | `passed` | removed |
| `alpha_session_06` | `passed` | removed |
| `alpha_session_07` | `passed` | removed |

The completed `#239`, `#242`, `#230`, and `#240` masks were removed because
their concrete trajectories pass every hard check.

## Verification

Exact free gate:

```text
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  -q --no-cov

40 passed in 1.45s
```

Static checks:

```text
poetry run ruff check \
  tests/evals/chat_runtime_trajectory_adapters.py \
  tests/evals/test_chat_runtime_trajectory_harness.py

All checks passed!

git diff --check

passed
```

## Files

- `tests/evals/chat_runtime_trajectory_adapters.py`: concrete FastAPI/memory
  journey adapters.
- `tests/evals/test_chat_runtime_trajectory_harness.py`: exact integrated
  status assertion plus mask-aware fixture/harness regression maintenance.
- `tests/evals/alpha_session_trajectories.json`: removed four completed masks
  and narrowed the three remaining masks to observed failures.
- `.superpowers/sdd/task7-trajectory-adapters-report.md`: durable Task 7
  evidence.

## Remaining boundary

The `#238`, `#241`, and `#251` failures remain explicit evidence. Task 7 does
not own their production corrections. The tests-only slice is coherent and
independently reversible.
