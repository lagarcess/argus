# Task 6 Layer 1 correction report

## Scope

- Starting Task 6 checkpoint: `0f41b41610aefacdb27858ecb30670aea9f373a6`
- Task 6 branch base: `cbed1790e63fff43de03fb1782c0a4e5e4c0b076`
- No Task 7 work, schema, migration, RLS, provider, dependency, or lifecycle
  vocabulary changes.
- No service, database, container, browser, paid-eval, push, PR, or deployment
  action.

## Confirmed findings and corrections

1. **Exact-once workflow dispatch**
   - `ShadowBacktestJobTool` now records the atomic admission decision.
   - Only `admitted` owns workflow dispatch.
   - `replay` returns the existing durable job envelope without dispatcher or
     delegate work.
   - The race regression gates the admitted request inside dispatch, starts a
     same-key replay before dispatch metadata exists, and proves one allowance,
     one job, one dispatcher call, zero delegate calls, and the same job
     identity for both callers.

2. **Finite frontend ambiguity recovery**
   - The initial Run lookup is still keyed by persisted `confirmation_id`.
   - Only a first `404` permits the one exact same-key Run replay.
   - `409` stops automatic replay immediately.
   - `500`, transport ambiguity, and post-replay absence receive exactly two
     lookup-only continuation attempts at fixed 250 ms and 750 ms delays.
   - An `idempotency_in_progress` replay response re-looks up the racing durable
     job.
   - Exhausted lookup and definite stale/conflict responses use existing
     localized typed recovery plus the existing conversation-reload Retry
     action. They do not create a public action type, lifecycle state, second
     poller, unbounded timer, or transport-derived `could_not_run`.

3. **Database-owned browser polling**
   - Owner-facing `GET /api/v1/backtest-jobs/{job_id}` now projects the
     Supabase row directly.
   - Render task-run reconciliation remains available to existing worker/ops
     owners but is absent from both fresh owner job GET routes.
   - Fail-fast Render spies cover both job-id and by-action lookup.

4. **Full immutable launch identity**
   - The 16-character `launch_payload_hash` remains the action-admission
     fingerprint.
   - Confirmation cards and artifact references now also persist
     `canonical_launch_payload_hash`, the full `sha256:` hash of the validated
     canonical launch payload.
   - By-action lookup requires the full hash on both the persisted card and
     active confirmation reference, requires equality between them, and
     compares that exact value to the job payload/identity hashes.
   - No validator recomputation fallback remains. Missing, malformed, legacy
     short-only, or mismatched evidence returns the existing safe `500`.

## Red evidence

Backend:

```text
poetry run pytest tests/test_backtest_jobs_async.py \
  tests/test_backtest_job_by_action.py -q --no-cov

4 failed, 23 passed
```

The failures were:

- two same-key requests dispatched twice (`dispatcher.calls == 2`);
- owner GET called the Render reconciliation hook;
- a legacy-only full hash was accepted instead of requiring the new immutable
  full-width field;
- the real confirmation card lacked `canonical_launch_payload_hash`.

A focused reference-integrity red also proved the old route accepted both
missing canonical evidence and a card/reference hash mismatch (`2 failed,
5 passed`).

Frontend:

```text
cd web
bun test __tests__/chat-run-reconciliation.test.ts \
  __tests__/chat-backtest-jobs.test.ts

7 failed, 23 passed
```

The old code returned permanent `checking`/`rejected`, had no bounded lookup
continuation, did not re-look up `idempotency_in_progress`, and had no
caller-visible typed recovery path.

## Green verification

Focused backend and directly adjacent confirmation/action coverage:

```text
167 passed in 4.11s
```

Focused frontend reconciliation/job/artifact/recovery/UX coverage:

```text
89 passed, 0 failed, 418 assertions
```

Hermetic agent runtime and spine:

```text
1220 passed in 16.28s
```

Mocked eval and trajectory harness:

```text
39 passed in 1.28s
```

Static and build gates:

- `poetry run ruff check src/argus tests` — passed.
- `cd web && bun run lint` — passed.
- `cd web && bun run build` — passed.
- `poetry run python scripts/check_modularity_budget.py` — passed.
- `git diff --check` — passed.

`ChatInterface.tsx` is exactly at its existing modularity ceiling
(`2598/2598`). A five-line shared `clearActiveStreamState()` replaces five
identical setter triplets; no new frontend subsystem was added.

## Files changed

- `src/argus/api/chat/backtest_jobs.py` — admission decision owns dispatch.
- `src/argus/api/routers/backtest.py` — database-only owner reads and required
  immutable full hash.
- `src/argus/api/chat/confirmation.py` — persist card-level full hash.
- `src/argus/agent_runtime/confirmation_artifacts.py` — persist reference-level
  full hash while retaining the short action fingerprint.
- `web/lib/chat-run-reconciliation.ts` — finite lookup continuation and typed
  recovery projection.
- `web/components/chat/ChatInterface.tsx` — render the recoverable outcome and
  share stream-state clearing.
- `tests/test_backtest_jobs_async.py` — exact-once race and Render-free polling.
- `tests/test_backtest_job_by_action.py` — real confirmation identity and
  fail-closed artifact integrity.
- `web/__tests__/chat-run-reconciliation.test.ts` — bounded branch matrix and
  visible recovery.
- `web/__tests__/chat-backtest-jobs.test.ts` — caller wiring.

## Complexity and remaining gates

- The production correction adds one internal admission-decision field, one
  full hash helper/field, one finite two-delay continuation, and one recovery
  renderer. No speculative claim/queue framework was introduced.
- During the line-budget refactor, one source-wiring assertion still named the
  direct setter. It failed while all behavior tests passed; the assertion now
  follows the shared state-clear helper, and the final focused frontend rerun is
  green.
- PostgreSQL proof and production-parity browser QA were intentionally not run
  here; the release captain owns those Task 6 gates.
- The slice is independently committable with the approved message
  `fix(backtest): close ambiguity review gaps`.
