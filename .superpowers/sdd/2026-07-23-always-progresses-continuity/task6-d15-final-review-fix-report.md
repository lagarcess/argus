# Task 6 d15 final review-fix report

## Scope

- Starting checkpoint:
  `d15dd5b1849e2f637f024d1a6b43520792e47302`.
- One final serialized Task 6 correction delta only.
- No schema, migration, RLS, provider, Render topology, public lifecycle or
  action type, queue, poller, redispatch, Retry path, orchestrator, PostHog,
  privacy/governance, or Task 7 change.
- No browser, service, shared database, live provider, paid eval, deploy, push,
  PR, or merge action.

## Corrections

1. **Internal reservation reads include workflow kind**
   - The existing owner/scope/key reservation query now selects private
     `launch_payload`, so stale classification can read `launch_payload.kind`.
   - The new page batch uses the same private projection.
   - Existing public job allowlists still remove `launch_payload`,
     `execution_metadata`, identity hashes, and other internal fields.

2. **Reload Run projection is page- and query-bounded**
   - Conversation reload computes globally represented request ids before
     pagination, so a Run action is not projected twice when its assistant job
     message is outside the current page.
   - Only Run actions on the selected page become batch candidates.
   - One owner + conversation + `chat.run_backtest` query reads the page's
     unique confirmation ids through typed `.in_`.
   - Exact conversation and request-message linkage still gates projection.
     Cursor tests prove the next page does not requery earlier ids.

3. **Stale failure cannot overwrite same-status dispatch progress**
   - Failed-job compare-and-set now accepts the stale row's `updated_at` in
     addition to its observed status.
   - If task metadata attaches while the row is still queued, the stale write
     loses on `updated_at`, reloads current owner-scoped truth, and preserves
     the task id and active status.
   - No redispatch or new recovery mechanism was added.

4. **Frontend terminal reload truth wins**
   - Raw confirmation action effects are still applied during hydration.
   - Hydrated durable job state is then reapplied to its owning confirmation.
   - Failed reloads render `could_not_run`; canceled and expired reloads render
     `not_completed`; none remain stale `Running` or enter polling.

5. **Prior report wording is dependency-accurate**
   - The earlier report now says canonical Run identity validation occurs
     before route-owned profile/conversation work after the authentication
     dependency. It no longer implies work before FastAPI authentication.

## TDD evidence

Backend reds were captured before production implementation:

```text
8 failed, 1 passed
```

They proved the missing internal query field, missing typed batch owner,
conversation and scope read, missing `updated_at` compare-and-set, sequential
all-message reload reads, page/cursor over-query, and wrong-request
misassociation.

Frontend red was captured in two steps:

```text
Missing raw hydration export: 1 module error
Behavioral rerun: 21 passed, 3 failed
```

The three behavioral failures showed failed, canceled, and expired durable jobs
all leaving their confirmation at `running`.

First focused green:

```text
Backend: 9 passed
Frontend: 24 passed, 130 assertions
```

## Final verification

- Focused Task 6 backend matrix: `236 passed`.
- Focused Task 6 frontend matrix: `73 passed, 346 assertions`.
- Hermetic LangGraph runtime and spine: `1220 passed`.
- Mocked eval and trajectory harness: `39 passed`.
- `poetry run ruff check src/argus tests` passed.
- `cd web && bun run lint` passed.
- `cd web && bun run build` passed, including TypeScript and 13 page
  generations.
- `poetry run python scripts/check_modularity_budget.py` passed with no
  violations.
- `git diff --check` passed.

Browser QA was not performed because the final delta explicitly prohibited
browser, service, live-provider, and paid-token work. Release-captain browser
QA should reload raw Run-action histories backed by failed, canceled, and
expired jobs, then verify terminal confirmation copy, no stale Running label,
and no polling.

## Complexity reassessment

- The batch path reuses the existing reservation gateway and message projector.
  It adds one bounded query per page only when unrepresented Run actions exist.
- The race fix extends the existing failed-job compare-and-set and owner reload;
  it introduces no row, state machine, timer, or external dependency.
- The frontend reuses the existing durable-job-to-confirmation settlement
  helper after action effects.
- Watched production files remain within their existing budgets:
  `backtest_jobs.py 1112/1112`, `supabase_gateway.py 2111/2111`,
  `ChatInterface.tsx 2597/2598`, and `argus-api.ts 1254/1254`.
- No API-contract or data-model documentation changed because public request,
  response, lifecycle, and persistence behavior did not change.

## Files changed

- `src/argus/domain/backtest_admission_gateway.py` — shared private reservation
  columns and typed owner/conversation/scope batch read.
- `src/argus/domain/supabase_gateway.py` — batch wrapper and `updated_at`
  failure compare-and-set.
- `src/argus/domain/backtest_message_projection.py` — page candidate discovery,
  global represented-request awareness, and supplied batch projection.
- `src/argus/api/routers/conversations.py` — pagination-before-batch Run
  projection.
- `src/argus/api/chat/backtest_jobs.py` — passes stale `updated_at` and reloads
  current truth on compare-and-set loss.
- `web/lib/chat-backtest-jobs.ts` — reapplies hydrated durable job truth to the
  owning confirmation.
- `web/components/chat/ChatInterface.tsx` — raw hydration order and focused test
  export.
- Backend and frontend tests — real query shape, batch cardinality/cursors,
  global representation, misassociation, exact dispatch race, and raw terminal
  reload coverage.
- `.superpowers/sdd/task6-complete-review-fix-report.md` — corrected
  authentication-boundary wording.

## Caveats and commit readiness

- Disposable-Postgres and production-parity browser proof remain for a
  release-captain environment; neither was authorized for this local delta.
- The slice is independently committable with
  `fix(backtest): harden durable run recovery`.
- This report is part of that commit, so its self-referential SHA cannot be
  embedded in its own contents; the exact commit SHA is recorded in the final
  handoff.
