# Task 6 Run Transport Ambiguity Report

## Outcome

Task 6 implements the approved durable reconciliation path for a lost
`run_backtest` response.

- The backend exposes owner-scoped
  `GET /api/v1/backtest-jobs/by-action/{confirmation_id}`.
- The lookup is restricted to `chat.run_backtest`, verifies the linked
  assistant confirmation artifact and full-width launch identity, returns
  `404` for no reservation, `409` without job disclosure for an identity
  collision, and safe JSON `500` for inconsistent or unavailable durable
  state.
- A fresh by-action lookup never calls Render reconciliation.
- The frontend treats a status-zero/fetch exception as presentation-only
  checking, reads durable truth, and never turns transport ambiguity alone
  into `could_not_run`.
- `queued` and `running` responses replace the temporary assistant placeholder
  with a pollable job artifact. `succeeded` projects the one canonical result.
  Only durable `failed`, `canceled`, or `expired` state settles unsuccessfully.
- Only an owner-scoped `404` permits one exact replay. If that replay is also
  ambiguous, the client performs one final lookup and never a second replay.
- Existing definite HTTP rejection and persisted queued/running reload polling
  remain intact.

## Files changed

- `src/argus/api/routers/backtest.py`
  - Added the by-action route, immutable confirmation identity checks, safe
    error shaping, and shared job-response projection.
- `src/argus/domain/backtest_admission_gateway.py`
  - Expanded the already owner/scope/key-filtered reservation projection with
    only the fields required to verify and return the durable job.
- `docs/api/openapi.yaml`
  - Declared the already-approved public by-action contract and response codes.
- `web/lib/chat-run-reconciliation.ts`
  - Added the bounded lookup/replay state machine, placeholder-to-job
    projection, and extracted the pre-existing job polling effect.
- `web/components/chat/ChatInterface.tsx`
  - Wired status-zero Run ambiguity to durable reconciliation and guarded
    updates by active conversation ownership.
- `web/components/chat/artifact-history.ts`
  - Kept confirmation state nonterminal while durable Run state is unknown.
- `web/lib/argus-api.ts`
  - Exported the existing authenticated fetch helper for the focused
    reconciliation module; line count did not grow.
- `tests/test_backtest_job_by_action.py`
  - Added route, ownership, collision, artifact-integrity, canonical-result,
    no-Render, and safe-error coverage.
- `tests/test_alpha_artifacts.py`
  - Added OpenAPI structural coverage for the by-action route.
- `web/__tests__/chat-run-reconciliation.test.ts`
  - Added lookup/replay cardinality, status classification, and missing-local-
    job-message projection coverage.
- `web/__tests__/chat-artifact-history.test.ts`
  - Added the transport-only nonterminal confirmation regression.
- `web/__tests__/chat-backtest-jobs.test.ts`
  - Kept the existing polling structural assertion aligned with its focused
    extraction.

## TDD evidence

Backend red:

```text
9 failed in 0.66s
```

All failures were the missing by-action route contract.

Frontend red:

```text
30 passed, 6 failed
```

Five failures were the absent reconciliation module. The sixth proved that the
existing transport path incorrectly changed `running` to `could_not_run`.
Additional focused reds pinned the missing pollable placeholder projection,
OpenAPI omission, persistence-read error shaping, malformed durable-row error
shaping, and ambiguity classifier.

## Verification

- Focused backend route/state matrix:
  - `54 passed`
- Required backend reload/accounting matrix with live keys and shared
  `DATABASE_URL` blank:
  - `121 passed, 15 skipped`
  - The 15 skips are the intentionally unavailable disposable-Postgres cases.
- API/OpenAPI structure:
  - `27 passed`
- Full frontend unit/integration suite:
  - `476 passed`
- Focused final frontend reconciliation/lifecycle matrix:
  - `57 passed`
- Frontend production build:
  - Next.js compile, TypeScript, and 13 static/dynamic page generations passed.
- Changed frontend ESLint surfaces:
  - no errors.
- Mocked eval harness:
  - `39 passed`
- Modularity:
  - no violations;
  - `ChatInterface.tsx` is `2594 / 2598`;
  - `argus-api.ts` remains `1254 / 1254`.
- Python Ruff on changed Python files:
  - no errors.
- `git diff --check`:
  - no whitespace errors.

The repository-wide backend sweep reached:

```text
2533 passed, 55 skipped, 1 failed
```

The one failure is
`tests/test_backtest_state_machine.py::test_text_approval_uses_llm_turn_act_but_defers_to_card_action`.
It reproduces in isolation and exercises an untouched interpreter path; Task 6
does not change or waive it.

## Browser QA

Not performed. The task boundary explicitly prohibited browser/live-provider
work. Release-captain browser proof should fault-inject a lost Run response and
verify the visible sequence:

```text
Running -> Checking -> queued/running job -> one canonical result
```

It should also prove that a second ambiguous response does not issue a second
Run replay. No Browser Control, Render control plane, paid eval, shared
database, or live provider was used in this slice.

## Known caveats

- Disposable Postgres proof is still required because the local environment
  intentionally had no `DATABASE_URL`; the release captain owns that gate.
- The unrelated isolated interpreter assertion above keeps the repository-wide
  backend suite from being wholly green on this exact base.
- Raw `tsc --noEmit` includes the repository's existing Bun-test typing
  collisions. The production Next.js build's TypeScript phase passed.

## Commit readiness

The slice is independently committable. It changes no schema, migration,
provider, interpreter, Render topology, PostHog, privacy, or Task 7+ surface.
