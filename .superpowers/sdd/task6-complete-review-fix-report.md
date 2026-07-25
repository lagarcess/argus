# Task 6 complete review-fix report

## Scope

- Starting checkpoint:
  `2f941362d25cfcd9d7e5c5f9d071b419218209fe`.
- One serialized Task 6 correction delta only.
- No schema, migration, RLS, provider, Render topology, dependency, public
  lifecycle, PostHog, privacy/governance, Task 7, queue, poller, or
  orchestrator change.
- No browser, service, shared database, live provider, paid eval, deploy, push,
  PR, or merge action.

## Corrections

1. **Exact Run action identity at the route boundary**
   - After the authentication dependency, `run_backtest` requires the canonical
     `Idempotency-Key` before route-owned profile/conversation, message, usage,
     lifecycle, persistence, provider, delegate, dispatch, or compute work.
   - Missing or blank headers return `400 idempotency_key_required`.
   - Missing action `confirmation_id` returns `422 validation_error`.
   - Header/action mismatch returns `409 idempotency_conflict`.
   - Alternate headers do not satisfy or bypass the canonical header.
   - Ordinary text and non-Run action behavior remains unchanged.

2. **Failure reconciliation cannot overwrite worker progress**
   - Terminal Render task failure now writes with the observed queued/running
     status as an expected-status compare-and-set.
   - A lost compare-and-set reloads the current owner-scoped durable job and
     preserves concurrent `running` or `succeeded` truth and its Run identity.

3. **Admitted-but-undispatched work eventually progresses**
   - Existing owner job-id and by-action reads reuse the existing stale queued
     age predicate and retryable `workflow_dispatch_missing` terminalization.
   - The transition uses the existing status compare-and-set. It never
     redispatches, delegates, calls Render, or executes a Run.
   - If process loss skipped the assistant job message, conversation reload
     projects the existing owner/scope/key reservation over the persisted Run
     action. The existing frontend job poll then reaches the owner job read and
     its terminal durable state.
   - Task 5 lifecycle projection could not supply this recovery: Run admission
     intentionally uses `message_only`, so no chat-turn lifecycle row exists.

4. **Initial HTTP-200 Run ambiguity uses durable truth**
   - Initial Run SSE `error` frames now enter the same bounded owner-scoped
     by-action reconciliation as status-zero transport errors.
   - A Run stream that ends without a final frame is treated as transport
     ambiguity and looked up before any replay or terminal UI.
   - Queued, running, and succeeded durable truth is restored. Only the existing
     first owner-scoped `404` may trigger one exact replay; lookup continuation
     remains fixed at 250 ms and 750 ms with no second replay.
   - Definite typed 4xx/stale failures and ordinary text/action SSE behavior are
     preserved. Transport ambiguity alone never produces `could_not_run`.

## TDD evidence

Backend reds were captured before production edits:

```text
Run identity matrix: 5 failed
Terminal failure race: 1 failed with missing expected_status
Stale owner reconciliation: 1 failed import
Missing-message projection: 1 collection error
```

The identity failures reached downstream profile/conversation work. The race
failed at the absent compare-and-set argument. The final two failures proved
the missing stale owner-read and by-action reload seams.

Frontend red:

```text
33 passed, 4 failed
```

The failures were the missing empty-200 guard, initial SSE still being
replay-only, rejection of the owner-scoped user-action projection, and
chat-action hydration winning before the projected durable job.

First focused green:

```text
Backend: 8 passed
Frontend: 39 passed, 198 assertions
```

## Final verification

- Focused Task 6 backend matrix:
  `143 passed, 15 skipped`.
  - The 15 skips are disposable-Postgres cases; `DATABASE_URL` was explicitly
    blank and no shared database was touched.
- Focused Task 6 frontend matrix:
  `83 passed, 421 assertions`.
- Hermetic LangGraph runtime and spine:
  `1220 passed`.
- Mocked eval and trajectory harness:
  `39 passed`.
- `poetry run ruff check src/argus tests` passed.
- `cd web && bun run lint` passed.
- `cd web && bun run build` passed, including TypeScript and 13 page
  generations.
- `poetry run python scripts/check_modularity_budget.py` passed with no
  violations.
- `git diff --check` passed.

Browser QA was not performed because this slice explicitly prohibited browser,
live-provider, service, and paid-token work. Release-captain browser proof
should fault-inject both an initial Run SSE error and an empty HTTP-200 Run
response, then verify:

```text
Running -> Checking -> queued/running durable job -> one canonical result
```

It should also verify at most one Run replay POST and reload recovery when the
assistant job message is absent.

## Complexity reassessment

- The change reuses the existing atomic reservation, owner-scoped by-action
  lookup, stale age predicate, status compare-and-set, job response, and
  frontend job poller.
- No new state, action type, lifecycle vocabulary, queue, poller, timer loop,
  or public metadata key was introduced.
- Missing-message projection is bounded to the current owner/conversation
  message page, caches one read per confirmation id, skips requests already
  represented by an assistant job message, and validates exact conversation
  and request-message linkage.
- The public API contract already specifies these status codes and ambiguity
  rules, so no contract-doc edit was required.
- Watched production files remain within budget:
  `ChatInterface.tsx 2597/2598`, `agent.py 1458/1468`,
  `backtest_jobs.py 1112/1112`, and `supabase_gateway.py 2111/2111`.

## Files changed

- `src/argus/api/chat/run_action_identity.py` — focused route-boundary Run
  identity validation.
- `src/argus/api/routers/agent.py` — invokes identity validation before route
  work.
- `src/argus/api/chat/backtest_jobs.py` — failure CAS/reload and named reuse of
  existing stale terminalization helpers.
- `src/argus/api/routers/backtest.py` — owner reads terminalize stale,
  undispatched queued jobs without Render.
- `src/argus/domain/backtest_message_projection.py` — bounded missing assistant
  job-message projection.
- `src/argus/api/routers/conversations.py` — owner/conversation-scoped by-action
  hydration on reload.
- `web/lib/chat-run-reconciliation.ts` — initial SSE and empty-stream ambiguity
  classification.
- `web/components/chat/ChatInterface.tsx` — Run-aware SSE handling and final
  frame tracking.
- `web/lib/chat-backtest-jobs.ts` — renders the backend-projected Run action as
  the existing job artifact.
- Backend and frontend tests — exact boundary, race, stale owner read, reload,
  bounded lookup/replay, and regression coverage.

## Caveats and commit readiness

- Disposable PostgreSQL proof remains for a database-enabled release-captain
  environment.
- Production-parity browser QA remains for the release captain under the
  explicit task boundary.
- The slice is independently committable with
  `fix(backtest): close final ambiguity gaps`.
- This report is part of that commit, so its self-referential SHA cannot be
  embedded in its own contents; the exact commit SHA is recorded in the final
  handoff.
