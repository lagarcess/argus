# Task 6 final Layer 1 correction report

## Scope

- Starting checkpoint: `07b1301d2eae990d65d28a528ee58d48a65c8468`.
- One bounded Task 6 correction slice only.
- No schema, migration, RLS, provider, Render topology, public lifecycle,
  PostHog, privacy/governance, or Task 7 change.
- No browser, live provider, shared database, service, deploy, push, PR, or
  merge action.

## Corrections

1. **Durable dispatch liveness**
   - A dispatch exception or timeout now conditionally moves the admitted,
     still-queued job to retryable `failed`.
   - The update uses an expected-status compare-and-set. If a remote worker has
     already moved the job to `running` or `succeeded`, the failed write loses
     and the current durable row is reloaded and projected.
   - A stale real `run_backtest_job` that remains queued without dispatch/task
     proof is terminalized after the existing 15-minute threshold.
   - Replay restores existing dispatch context but never dispatches or delegates.
     The concurrency regression proves one allowance, one job, one dispatch,
     zero delegate calls, and the same durable job for both callers.

2. **Private full launch identity**
   - `canonical_launch_payload_hash` remains persisted in the confirmation card
     and active artifact reference for by-action validation and job identity.
   - Final SSE and conversation-message GET projections recursively remove that
     private full hash.
   - The short `launch_payload_hash` remains public for action continuity.
   - Tests prove the persisted full hash equals the admitted payload hash used
     to derive the job identity, while public final/reload JSON contains neither
     the private key nor any full `sha256:` identity.

3. **Replay-only HTTP-200 SSE error recovery**
   - An SSE `error` frame throws transport ambiguity only inside the one special
     Run replay.
   - The existing finite lookup-only continuation then runs at 250 ms and
     750 ms, with no second replay.
   - Exhaustion uses the existing typed conversation-reload recovery and never
     leaves a permanent checking or transport-derived `could_not_run` state.
   - Ordinary text/action SSE error handling is unchanged.

4. **Database-only owner reads**
   - Owner job-id and by-action tests now spy on the real
     `RenderTaskRunClient.get_task_run` boundary.
   - Both reads make zero Render control-plane calls even when durable task-run
     metadata is present.

## TDD evidence

Backend red:

```text
7 failed, 111 passed
```

The failures were exactly the dispatch exception/race projection, real stale
queued recovery, expected-status gateway CAS, and private public-projection
contracts.

Frontend red:

```text
2 failed, 10 passed
```

Both failures were the missing replay-only SSE error classifier.

First focused green:

```text
Backend: 118 passed
Frontend: 32 passed, 170 assertions
```

## Final verification

- Task 6 backend adjacency: `223 passed, 15 skipped`.
  - The 15 skips are the disposable-Postgres cases; `DATABASE_URL` was
    intentionally blank and no shared database was touched.
- Hermetic LangGraph runtime and spine: `1220 passed`.
- Focused frontend reconciliation/artifact matrix: `76 passed`.
- Mocked eval and trajectory harness: `39 passed`.
- `poetry run ruff check src/argus tests` — passed.
- `cd web && bun run lint` — passed.
- `cd web && bun run build` — passed, including TypeScript and 13 page
  generations.
- `poetry run python scripts/check_modularity_budget.py` — passed with no
  violations.
- `git diff --check` — passed.

Browser QA was not performed because this slice explicitly prohibited browser,
live-provider, service, and paid-token work. Release-captain QA should fault
inject the one ambiguous Run replay and verify:

```text
Running -> Checking -> queued/running durable job or retry-load recovery
```

It should also verify that the replay issues at most one POST.

## Files changed

- `src/argus/api/chat/backtest_jobs.py` — dispatch-loss terminalization, stale
  real-job recovery, CAS-loss reload, and replay context restoration.
- `src/argus/domain/supabase_gateway.py` — optional expected-status CAS for
  failed job transitions.
- `src/argus/api/chat/confirmation.py` — public confirmation evidence
  projection.
- `src/argus/api/routers/agent.py` — sanitized final SSE projection.
- `src/argus/api/routers/conversations.py` — sanitized message GET projection.
- `web/lib/chat-run-reconciliation.ts` — replay-only SSE error classification.
- `web/components/chat/ChatInterface.tsx` — marks only the bounded replay stream
  as ambiguity-sensitive.
- Backend and frontend tests — focused liveness, identity, no-Render, bounded
  recovery, and exact-replay regressions.

## Caveats and commit readiness

- Disposable-Postgres proof remains for a database-enabled release-captain
  environment.
- No live eval or browser QA was run under this local-only boundary.
- The slice is independently committable with
  `fix(backtest): finish durable ambiguity recovery`.
- This report is part of that commit, so its self-referential SHA cannot be
  embedded in its own contents; the exact commit SHA is recorded in the final
  handoff.
