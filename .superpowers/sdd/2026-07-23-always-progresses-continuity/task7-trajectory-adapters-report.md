# Task 7 — Concrete session-trajectory adapters

## Boundary and checkpoints

- Task base: `1ea97afd7fa132d8022c4d0d5ef6f5ddedfdb8d7`
- Initial adapter checkpoint: `78d5b7f56f57f11a0bff656dee1857967d72db40`
- Layer 1 correction parent: `3a82579a7d6ec5340fdf7f36e1da5f6da8ce78d1`
- Final correction: the commit containing this report; obtain its exact SHA
  from `git log -1`.
- External services, live providers, browser automation, and databases: not
  used by Task 7.

The complete Task 7 range changed the concrete eval adapter and fixtures, the
stale-card backend redirect, its reload guardrail, and the frontend stale-card
composition path. It did not change the interpreter, schema, RLS, lifecycle
vocabulary, provider configuration, or public action contract.

## Red-before-green evidence

The initial adapter red was:

```text
ModuleNotFoundError: No module named tests.evals.chat_runtime_trajectory_adapters
```

The first real-route implementation exposed stale masks and false evidence
derived from adapter constants rather than production owners. The final review
correction added adversarial reds that reproduced:

- a stale Run job hidden by a persisted-execution constant;
- a repeated private terminal fingerprint hidden by a constant;
- duplicate lifecycle identity hidden by a durable-count constant;
- a mismatched fixture Retry identity accepted without projected authority;
- nine stale `#239` mask pairs; and
- missing ChatInterface final-payload composition coverage.

The backend private stale-card summary assertion was already green at the
correction parent and confirmed both `progress_outcome` and `terminal` are
`redirected`.

## Concrete owner evidence

`ConcreteTrajectoryRuntime` uses the real FastAPI application, real LangGraph
workflow, canonical SSE parsing, actual message reload projection, structured
actions, memory lifecycle rows, memory backtest jobs, usage counters, and
private persisted execution summaries.

The final adapter is 1,562 lines. Its four former evidence constants now read:

- stale execution from the conversation job owner keyed by the stale action;
- repeated terminal fingerprints from private persisted execution summaries;
- durable ordinary-turn identity from paired lifecycle and user-message
  owners; and
- duplicate Retry attempts from adjacent lifecycle rows with canonical
  persisted content.

The abandoned-turn Retry remains the founder-approved ordinary-text Retry. The
adapter derives its request identity and canonical text from the persisted
reload projection, submits once through `/chat/stream`, proves one new
lifecycle in the normal case, and derives its terminal artifact from persisted
messages. A proposed backend `retry_last_turn` action was rejected because that
UI-only control is intentionally unwrapped by the frontend; adding it to the
public backend action vocabulary would change product ownership.

## Mask disposition

| Trajectory | Status | Disposition |
| --- | --- | --- |
| `alpha_session_01` / `#238` | passed | stale-card correction is proven |
| `alpha_session_02` / `#239` | expected failed | exact eight observed pairs remain |
| `alpha_session_03` / `#241` | expected failed | exact capability-route failures remain |
| `alpha_session_04` / `#251` | expected failed | exact window/persistence failures remain |
| `alpha_session_05` / `#242` | passed | one admitted Run reconciles by action |
| `alpha_session_06` / `#230` | passed | retry preserves one job and allowance |
| `alpha_session_07` / `#240` | passed | abandoned recovery and one Retry are durable |

The harness now asserts each expected-fail mask set exactly equals its observed
`(step_id, prefix)` set. No unused mask can silently remain.

## Current verification

```text
Exact free gate: 51 passed
Focused reload guardrails: 66 passed
Focused frontend composition/retry/hydration/jobs: 106 passed
Hermetic agent-runtime and spine: 1220 passed
Ruff: passed
ESLint: passed
Next.js production build: passed
Modularity budget: passed; ChatInterface 2597 lines, limit 2598
git diff --check: passed
```

No paid eval, browser QA, push, PR, hosted mutation, or Task 8 work occurred in
this correction. A fresh independent delta review still owns the final Task 7
review verdict.
