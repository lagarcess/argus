# Shared local runtime

`server/platform/runtime.py` owns operational configuration, model and login
admission, and HTTP limits. `jobs_runtime.py` owns the durable queue. Both use
the application's existing SQLite Store. There is no second database, process
semaphore quota, provider polling, real trading, or production deployment here.

## Composition

The application captain composes these hooks:

1. Construct Store and call `runtime.initialize(store)` **before** deposit
   bootstrap, so startup recovery can recognize queue-owned loads.
2. Initialize identity and all existing domains. Register runtime's
   `export_data(connection, context)`, `clear_data(connection, context)` and
   `usage_data(connection, context)` callbacks before destructive lifecycle work.
3. Mount `runtime.router` and add `RuntimeMiddleware` with the same policy used
   at initialization. Ordinary construction reads process variables automatically.
4. After initialization, start `asyncio.create_task(run_worker(store, stop_event))`.
   On lifespan shutdown, set the event and await the task. The loop stops claiming
   new jobs and drains admitted local work before shutdown completes.

Each API process may host this loop: atomic shared claims enforce the same
global slots. An idle loop uses read connections, with an interruptible 250ms
poll. Claimed synchronous work uses the threadpool; the async loop checks at
most every second and renews its lease every third of the lease duration.
Use `worker_tick(store)` for one synchronous CLI or test tick; async callers use
`await run_one(store)`. Both execute through the same lease-renewal supervisor
as the lifespan loop, so an operation may safely span multiple lease periods.
Do not call the synchronous wrapper from a running async event loop. Cancellation
drains the admitted local thread while its existing supervisor continues renewing.

`initialize` persists one validated policy. A process proposing different limits
fails with `runtime_configuration_mismatch` (503), rather than silently applying
different admission rules. Policy changes require an explicit local maintenance
migration; no automatic policy overwrite is performed.

## Queue contract

`enqueue_job(store, context, kind, payload, idempotency_key, correlation_id=None)`
returns an owned job status. Public requests supply a current owner Context.
Only trusted local scheduler code may pass `context=None`; there is no public
queue submission router. Supported payloads are closed, validated models:

| Kind | Payload | Recovery |
| --- | --- | --- |
| `deposit_load` | `scenario`: baseline, same_winner, leader_changed, inflation_crossed or failure; `load_id`: 1–100 ASCII letters/digits/underscore/hyphen | Reuse the domain load ID; at most three claimed attempts |
| `fixture_price_load` | `outcome`: success or failure | Expired worker becomes failed; the existing price loader has no idempotent operation ID |
| `recurring_investments` | `date`: ISO date; optional bounded opaque `cursor` | Trusted scheduler only; existing per-plan/date receipts own replay |

Deposit submission calls `begin_load` inside the queue insertion transaction.
The HTTP deposit event must compute a stable load ID from household plus request
idempotency key, enqueue, and return its existing `load_id` plus the new job ID.
It must not independently create an unowned loading row or use BackgroundTasks.
Replay with the same kind, household scope and key returns the original job;
different validated input raises `job_idempotency_conflict` (409).

Recurring work reads at most 100 due plans through the investing helper. A
non-null cursor submits an idempotent continuation job. The helper's
`next_poll_on` remains the scheduler's next-date contract; this runtime does not
create an autonomous calendar scheduler. Full continuation admission raises a
bounded failure, leaving domain due rows available for a later scheduled run.

`GET /api/platform/jobs/{job_id}` requires the current session and household.
An absent or other-household job returns `job_not_found` (404). It exposes:

```json
{
  "id": "server-generated-id",
  "kind": "deposit_load",
  "status": "queued",
  "created_at": 1790000000.0,
  "available_at": 1790000000.0,
  "attempt_count": 0,
  "completed_at": null,
  "result_ref": null,
  "error_code": null,
  "correlation_id": "server-generated-correlation-id"
}
```

Times are Unix seconds UTC. Terminal statuses are `succeeded` and `failed`.
`result_ref` points to the domain receipt where available. Financial data,
payloads, deduplication keys, household identifiers and lease tokens are not
returned. `get_job` and bounded `list_jobs` offer the same ownership rule;
`get_job_internal` is for trusted local scheduler code only.

Atomic claims select the oldest eligible job and exclude a household already
running work. Shared public deposit/price work has one reserved running slot;
ordinary scheduler work has two. Defaults allow two queued jobs per household
scope and 500 queued globally. Enqueue rejects overload as `job_queue_full`
(429). Queue-capacity checks and insertion share a write transaction.

Each claim issues a fresh token and lease. Heartbeat and terminal writes require
the current unexpired token. Expired deposit/recurring jobs requeue until the
attempt cap, while an interrupted price job fails explicitly. Current ownership
and user liveness are checked immediately before household-requested work.
Household clearing removes owned queue records and cancels associated loading
attempts in the same transaction. It does not clear model admission: reset cannot
cancel an in-flight provider or refund an already spent attempt. Model leases
retain an opaque household key until ordinary release/expiry; numeric daily
aggregates retain that key for the existing 31-day period, including after
account deletion. They contain no user messages or financial records.
Queue failure/exhaustion finalizes its deposit
attempt through the domain's public failure owner; last good data remains usable.

## Model and login admission

`async with model_admission(store, context)` wraps each actual configured model
HTTP call, including parsing. Prepared actions and keyless paths never enter
this context. Acquisition and release use the threadpool. Cancellation during
acquisition waits for its result and releases any acquired lease; cancellation,
timeout, failure and completion each release admission and record the outcome.
No transaction spans a provider await. The shared context enforces a ten-second
whole-call wall-clock deadline with AnyIO. Regularly arriving response chunks
cannot prolong it. Expiry becomes the existing typed HTTPX timeout boundary and
records `timeout`; an external task cancellation records `cancelled`.

The lower-level synchronous APIs are `acquire_model(store, context) -> ModelLease`
and `release_model(store, lease, outcome="completed")`. Release is idempotent.
Atomic household/global daily limits count admitted attempts, including failures;
they are not refunded by retry. Concurrent leases expire after 30 seconds, longer
than the whole-call deadline. `RuntimePolicy` rejects a `model_call_seconds`
value equal to or greater than `model_lease_seconds`. The lease carries its
admitted `call_timeout_seconds`, derived from that policy. Admission rejects with
`model_concurrency_exceeded` or `model_daily_limit_exceeded` (429).

`GET /api/platform/runtime/usage` returns only the current household's UTC-day
attempts, outcomes, active leases and limits, plus `pricing: "unknown"` and
`mode: "local_only"`. Daily aggregates retain 31 UTC days. There is no per-request
database event ledger. Do not interpret an admitted attempt count as token cost.

Login admission runs before password verification on
`POST /api/platform/session/login`. Shared counters cap actual socket-address
and global attempts per UTC minute; forwarded-address headers are ignored.
Only a window-scoped address digest is stored, and older windows are removed.
The global cap also bounds cardinality. Excess login attempts return
`login_rate_exceeded` (429).

## HTTP and configuration

Every `/api/` response receives a fresh server-owned `X-Request-ID`. Request logs
contain only that ID, normalized route template, bounded method, status and elapsed
milliseconds. Job logs contain correlation ID, fixed kind/state and an allowlisted
error code. No body, raw route ID, query, cookie, address, credential or financial
amount is logged. Unmatched paths use the literal `unmatched` route label.

Default request limits are 64KiB and 16KiB of headers. The two exact existing CSV
preview paths accept 2MiB. Bytes are counted while receiving, including chunked
bodies without Content-Length, before JSON parsing; complete-body arrival has a
ten-second deadline. Errors are `request_body_too_large` (413),
`request_headers_too_large` (431), `invalid_request_length` (400), and
`request_body_timeout` (408). Database busy/locked exhaustion becomes
`database_busy` (503). All 429/503 responses include `Retry-After: 1`; this is a
minimum delay, not a promise that a daily quota has reset. Do not automatically
retry mutations without their idempotency key.

All policy values have one typed owner, `RuntimePolicy`. Each field can be set
through `CLARA_RUNTIME_<UPPERCASE_FIELD_NAME>` in the process environment. No .env
file is read or written. Additional defaults are: `model_household_daily=50`,
`model_global_daily=1000`, `model_household_concurrent=1`,
`model_global_concurrent=4`, `login_ip_per_minute=10`,
`login_global_per_minute=100`, `job_lease_seconds=30`, `job_max_attempts=3`,
`model_call_seconds=10` and `model_lease_seconds=30`.
The model limits are conservative local spend guards, not a production traffic
allocation. The app's existing localhost host boundary remains in force.

Focused tests exercise independent-process claims, concurrent model admission,
household fairness, restart replay, recovery exhaustion, token fencing, failed
load retention, cleanup, bounded login storage, chunked bodies, correlations,
busy SQLite responses, and async worker responsiveness. These tests establish
the stated local behavior; measured capacity evidence belongs to SCALE_DESIGN
and the separate HTTP harness.
