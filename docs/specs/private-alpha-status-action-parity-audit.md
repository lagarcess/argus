# Private Alpha Status/Action Parity Audit

Status: Implemented; locally verified
Date: 2026-06-11
Branch: `codex/private-alpha-next`
Audience: Founder, Codex, reviewers

## Purpose

This slice hardens the private-alpha chat artifact lifecycle so confirmation
cards, async backtest job cards, result cards, retry actions, feedback, and
more-menu actions behave as one coherent system across stream, polling, reload,
local QA, and live QA paths.

The work is an audit-backed tightening pass, not a redesign. It should add
coverage where the lifecycle matrix is weak, then patch only the mismatches the
tests expose.

## Source Of Truth

- Durable job lifecycle truth comes from Supabase `backtest_jobs` rows and the
  `GET /backtest-jobs/{id}` API.
- Result truth comes from immutable `backtest_runs` records and backend-provided
  result readouts.
- Confirmation and result actions live on their owning cards.
- Assistant-turn controls own feedback, structured retry affordances, copy, and
  report actions.
- The frontend renders backend-provided artifacts and action metadata. It must
  not infer retry behavior from prose or synthesize hidden runtime facts.

## Lifecycle Matrix

| Surface | State Or Action | Owner | Expected Behavior |
| --- | --- | --- | --- |
| Confirmation card | `ready_to_run` | Confirmation card | Shows run/edit/cancel actions when active. |
| Confirmation card | `request_sent` | Confirmation card | Settles after run request; progress moves to job card. |
| Confirmation card | `run_complete` | Confirmation history | Historical card is closed, actionless, and reloadable. |
| Confirmation card | `could_not_run` | Confirmation history | Historical card is closed, actionless, and points to job/result context. |
| Confirmation card | `not_completed` | Confirmation history | Used for canceled/expired jobs; no stale running copy. |
| Confirmation card | `draft_canceled` | Confirmation history | Cancel action closes the card and hides noisy action transcript rows. |
| Backtest job card | `queued` | Durable job card | Shows calm queued status and remains pollable. |
| Backtest job card | `running` | Durable job card | Shows running status and remains pollable. |
| Backtest job card | `succeeded` without run | Durable job card | Keeps polling until the linked run is available. |
| Backtest job card | `succeeded` with run | Result card | Hydrates to a result card and stops job polling. |
| Backtest job card | `failed` | Durable job card | Shows failed status; mentions retry only when the assistant turn has a structured retry action. |
| Backtest job card | `canceled` | Durable job card | Shows not-completed status and stops polling. |
| Backtest job card | `expired` | Durable job card | Shows not-completed status and stops polling. |
| Result card | Explain result | Result card | `show_breakdown` is card-scoped and never appears in the composer or footer. |
| Result card | Save strategy | Result card | Remains functional when action metadata exists, but this slice does not enable hidden strategy surfaces or new horizon scope. |
| Assistant footer | Feedback | Assistant turn | Ratings/reporting attach exact message and artifact context. |
| Assistant footer | Retry | Assistant turn | Retry appears only for `retry_last_turn`, `retry_failed_action`, or conversation-load retry actions backed by structured metadata. |
| More menu | Copy plaintext/report issue | Assistant turn | Exposes user-safe owner actions only. |
| More menu | Copy ID | None | Remove from the UI; internal ids are not a user-facing private-alpha action. |

## In Scope

- Add a small lifecycle matrix and audit spec.
- Add focused frontend tests for status/action ownership, terminal job parity,
  composer/footer filtering, feedback context, and `Copy ID` removal.
- Add focused backend tests for job status responses and terminal workflow
  reconciliation where coverage is missing.
- Patch frontend helpers/components narrowly when tests expose mismatches.
- Run local focused verification and frontend build.
- Leave live/browser QA for the batch-level readiness pass before PR or founder
  handoff.

## Out Of Scope

- Do not add direct async-job retry.
- Do not infer retry behavior from `backtest_job.retryable` alone.
- Do not enable hidden Strategies or Collections surfaces.
- Do not change Supabase schema, RLS, auth, service-role behavior, Render
  topology, env var names, or deployment automation.
- Do not implement Research Lab, Perplexity, evidence-aware idea-loop runtime,
  public excerpts, or new sharing behavior.
- Do not rewrite the result voice path or synthesize frontend Quick takes.
- Do not dispatch Jules work from this slice.

## Acceptance Criteria

- Stream final, polling update, and reload hydration paths produce the same
  artifact ownership model.
- Terminal job states do not leave confirmation cards in running/request-sent
  limbo.
- Retry copy/action visibility is structured-action backed.
- Result/confirmation card-scoped actions do not leak to composer or assistant
  footer surfaces.
- Feedback/report contexts include exact artifact identifiers where available.
- `Copy ID` is hidden from the assistant more menu.
- Save remains functional when action metadata is present, with no feature flag
  enablement or new product surface.
- Local focused tests pass.
- `cd web && bun run build` passes.
- Live/browser QA remains a batch-level readiness step: verify
  queued/running/succeeded and at least one failed or not-completed path, with
  notes captured before PR or founder handoff.

## Implementation Closeout

Implemented commits on `codex/private-alpha-next`:

- `e545235 fix(chat): attach feedback to artifact context`
- `220953b fix(chat): keep card actions on artifact surfaces`
- `f60158d test(chat): cover async job lifecycle parity`
- `aa9ca68 test(api): cover terminal workflow job parity`
- `b0c2562 fix(chat): hide internal message id action`
- `cf6662d fix(chat): normalize artifact status tones`
- `b211eb6 test(chat): refresh alpha frontend guardrails`

What changed:

- Feedback/report actions now attach message, conversation, and artifact context
  through a shared helper.
- Card-scoped artifact actions remain on confirmation/result surfaces instead of
  leaking to composer or assistant footer controls.
- Async job lifecycle tests cover queued/running/terminal parity and terminal
  workflow reconciliation.
- The assistant more menu no longer exposes the internal `Copy ID` action.
- Confirmation, job, result, and saved-state pills now use shared artifact
  status tones so lifecycle color is consistent and calm.
- Alpha frontend source guardrails now match the current feature-flag and
  feedback-context ownership model.

Known closeout boundary:

- This slice did not enable Strategies, Collections, async-job retry, public
  sharing, or Research Lab runtime work.
- Browser/live QA is intentionally deferred to the batch readiness pass because
  the final patch was test-only and the visual status-tone change is narrow.

## Verification

Local focused checks:

```bash
cd web && bun test __tests__/chat-backtest-jobs.test.ts __tests__/backtest-job-card-copy.test.ts __tests__/chat-turn-artifact-ux.test.ts __tests__/chat-retry-actions.test.ts __tests__/chat-artifact-history.test.ts __tests__/chat-message-feedback-context.test.ts __tests__/artifact-status-tones.test.ts __tests__/alpha-frontend.test.ts
poetry run pytest tests/test_backtest_jobs_async.py::test_backtest_job_status_endpoint_returns_job_and_result tests/test_backtest_jobs_async.py::test_backtest_job_status_endpoint_reconciles_terminal_workflow_run tests/test_chat_stream_contract.py::test_chat_stream_runtime_failure_persists_retry_last_turn_metadata -q
cd web && bun run build
```

Fresh closeout run, 2026-06-11:

- `cd web && bun test __tests__/chat-backtest-jobs.test.ts
  __tests__/backtest-job-card-copy.test.ts
  __tests__/chat-turn-artifact-ux.test.ts __tests__/chat-retry-actions.test.ts
  __tests__/chat-artifact-history.test.ts
  __tests__/chat-message-feedback-context.test.ts
  __tests__/artifact-status-tones.test.ts __tests__/alpha-frontend.test.ts`
  passed: 125 tests, 815 expects.
- `poetry run pytest
  tests/test_backtest_jobs_async.py::test_backtest_job_status_endpoint_returns_job_and_result
  tests/test_backtest_jobs_async.py::test_backtest_job_status_endpoint_reconciles_terminal_workflow_run
  tests/test_chat_stream_contract.py::test_chat_stream_runtime_failure_persists_retry_last_turn_metadata
  -q` passed: 3 tests. The run emitted existing dependency deprecation warnings
  from Python 3.14 / asyncio compatibility.
- `cd web && bun run build` passed. The run emitted the existing Node
  `module.register()` deprecation warning.

Live QA:

- Run QA mode with real backend credentials via `.github/qa.sh`.
- Run the frontend with `NEXT_PUBLIC_MOCK_AUTH=false` and
  `NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1`.
- At batch readiness, use browser QA to run a real private-alpha conversation
  through confirmation, queued/running job state, result hydration, Explain
  result, feedback/report, and a failure/not-completed path when available.
- Confirm the assistant more menu no longer exposes `Copy ID`.
