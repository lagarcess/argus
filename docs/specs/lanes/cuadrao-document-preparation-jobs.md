# Cuadrao document preparation jobs

Status: implemented default-off on `claude/business-pilot-jobs` for #823. Not
enabled anywhere. No hosted service, flag or paid run changed.

## Problem

`POST /financial-documents` and `/prepare` or `/resume` run preparation as a
FastAPI background task. When that task dies, the draft stays `queued` or
`preparing` until the person explicitly calls `/prepare` or `/resume`. Nothing
detects a dead worker while the API is up.

## Flag

`ARGUS_DOCUMENT_JOBS_ENABLED` (default off, shared true values). Off, the routes
add `background_prepare` to FastAPI background tasks and a read marks an expired
attempt `needs_attention` (`document_preparation_interrupted`), exactly as before.
`test_flag_off_prepares_through_background_tasks_only` and the existing
`test_interrupted_attempt_needs_attention_without_automatic_retry` pin this.

## Dispatch

With the flag on, the route calls `PreparationJobs.start` before responding. It
records the attempt on the draft's checkpoint row, then hands it to a worker. A
closed client therefore cannot lose accepted intake: the draft and the attempt
are durable before the response, and a failed hand-off is re-dispatched by the
sweep. `start` does nothing while an attempt is in flight.

## Execution

- Hosted. A `prepare_document(connection_id, attempt_id)` task in the existing
  workflows service (`workflows/main.py`), dispatched through the existing
  `RenderWorkflowDispatcher` when `ARGUS_DOCUMENT_JOBS_WORKFLOW_TASK` (for
  example `argus-backtests/prepare_document`) is set in durable mode. The worker
  reads the owner from the stored row, never from the task input. Render retries
  are off: one task run is one attempt.
- Local. The same task under `render workflows dev` with `RENDER_USE_LOCAL_DEV`
  and `RENDER_LOCAL_DEV_URL`, as the backtest workflow already does. Without a
  task name (or in memory mode) the attempt runs as a task on the API's event
  loop. Both paths run the same `run_attempt`.

## Dead-worker detection

The reconciler sweep (`PreparationJobs.sweep`) runs inside the API process: once
at startup, then every `ARGUS_DOCUMENT_JOBS_SWEEP_SECONDS` (default 30). It does
not depend on a read, a restart, an operator or a cron. It reads drafts that are
`queued`, `preparing`, or `needs_attention` with a retry request, through a
partial index.

One oracle, `in_flight`, decides liveness:

- a live connection lease means a worker is running;
- a `queued` draft whose dispatch is younger than the window is waiting for a
  worker to claim it;
- anything else is dead.

The window is the existing connection lease (5 minutes). Extraction makes one
provider call with a 90 second timeout and no retries, so a live worker always
finishes or fails inside its lease. A dead worker is detected at most one window
plus one sweep interval after its last claim or dispatch. A worker that dies
after releasing its lease, such as a cancelled task, is detected on the next
sweep.

The existing backtest reconciliation (`scan_stale_backtest_jobs`) runs only on
owner reads, at admission backpressure, and in the operator-run
`scheduled_maintenance.py`; nothing schedules it. Documents reuse its dispatch
and local-dev plumbing but not its cadence, because a closed app produces no
reads.

## Attempt and lease model

`financial_document_extractions.preparation_job` holds the current attempt:
`attempt`, `attempt_id`, `draft_version` (the queued draft it was dispatched
for), `dispatched_at` and `retry`. One store call, `advance`, replaces it, and
optionally the draft, in one transaction. It refuses while a lease is live,
when the current attempt is not the expected one, or when the draft version
moved. A worker leases the connection and then checks that its `attempt_id`
is still current; a superseded attempt releases and exits before any provider
call. Because `advance` refuses a live lease, a reconciler cannot supersede an
attempt that has already claimed.

## Retry and spend bounds

`MAX_ATTEMPTS = 3` per user-authorized preparation. An attempt is re-dispatched
when its worker died (`unclaimed` or `interrupted`) or it reported a retryable
failure, such as a provider failure or timeout, a delivery failure or a lost
lease. Each
attempt makes at most one provider call, so one preparation costs at most three
vision calls, including attempts whose outcome was uncertain. Past the bound
the draft is `needs_attention`, keeping the last real error code, or
`document_preparation_interrupted` when the worker died. That state is
recoverable: `/prepare` or `/resume` starts a fresh preparation at attempt 1.
Explicit restarts stay limited by the existing document POST rate limits (5 per
minute, 30 per day per person).

## Stale-result rejection

Unchanged and reused. Saving a preparation, updating the draft and delivering
candidates all require the worker's own live lease. A worker whose lease expired
or was taken by a newer attempt cannot save, deliver or mark the draft. Saved
preparation is first-writer-wins, so a late result cannot replace it.

## Consumer compatibility

Routes, request headers, response bodies, statuses and error codes are
unchanged. With the flag on, an attempt that would previously stop at
`needs_attention` may first return to `queued`. `/resume` on a dead
`preparing` draft answers 409 `document_busy` until the next sweep.

## Hosted cost (stated only, not activated)

- One Render Workflow task run per attempt, at most three per preparation, on
  the workflows service's default plan with a 240 second timeout.
- Up to three vision calls per preparation through the existing OpenRouter key.
- One indexed query per API instance every 30 seconds. No new service.
- The workflows service would need `ARGUS_WORKFLOW_DATABASE_URL`,
  `ARGUS_DOCUMENT_EXTRACTION_ENABLED`, `ARGUS_VISION_MODEL`, the OpenRouter key,
  and `SUPABASE_URL` with `SUPABASE_SERVICE_ROLE_KEY` to read sources from the
  private Storage bucket (#778);
  the API would need `ARGUS_DOCUMENT_JOBS_WORKFLOW_TASK` and `RENDER_API_KEY`.

## Evidence

- `tests/ingestion/test_document_jobs_api.py`: dead worker re-dispatched once
  inside the window with one prepared draft and one import event; late result
  refused; cancelled worker recovered; retries stop at the bound and stay
  recoverable; dead attempts exhaust; flag off unchanged.
- `tests/test_document_jobs_postgres.py`: the same recovery and refusal on real
  Postgres, `advance` fencing, and the workflow worker end to end.
