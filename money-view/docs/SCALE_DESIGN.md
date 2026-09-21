# Clara capacity and integration design

Design date: 2026-09-20. Scope: the isolated Clara platform under `money-view/`.
This is an implementation handoff, not a production readiness or measured
10,000-user capacity claim. It extends `PLATFORM_PLAN.md`; it does not change
the authorized Git destinations, vendor modes, or deployment restrictions.

## Decision

Keep one modular application and one transaction owner. Harden SQLite on one
host first, then qualify that exact implementation with HTTP traffic and a
realistic ledger. Keep the existing domain modules and contracts. A monthly
audience does not require one server per feature or 10,000 concurrent clients.

The current local app is not yet qualified for this workload. Its most urgent
capacity problems are unnecessary authentication writes, missing shared work
admission/recovery, and unbounded work at several request boundaries. Changing
database vendors does not fix those problems.

SQLite allows one writer at a time. WAL allows readers and a writer to proceed
concurrently, but it does not add parallel writers and is a same-host design.
These are engine properties, not capacity measurements for Clara.
[SQLite concurrency guidance](https://www.sqlite.org/whentouse.html) and
[WAL documentation](https://www.sqlite.org/wal.html).

## Workload to qualify

These are explicit planning assumptions. Measure and revise them when actual
usage exists. Do not relabel the values below as observed customer behavior.

| Quantity | Assumption and derivation |
| --- | --- |
| Monthly active identities | 10,000 |
| Households | 8,000; 1.25 active identities per household |
| Visits | 8 per identity per month: 80,000 visits |
| Dynamic requests | 30 per visit: 2,400,000 per month; static assets excluded |
| Mean arrival rate | 2,400,000 / 30 / 86,400 = 0.93 requests/second |
| Daily activity | Approximately 2,667 visits/day; five-minute visits imply 9.3 simultaneously active visits on average |
| Qualification traffic | 20 requests/second for 30 minutes; 40 requests/second for a five-minute burst |
| In-flight requests | At 250 ms average latency, 20 requests/second implies about 5 in flight; use up to 40 client slots, and report actual queueing |
| HTTP mix | 40% transaction list, 25% overview, 15% spending, 10% settings/history, 5% ledger writes, 3% prepared assistant, 2% mocked semantic assistant |
| Accounts | Typical 8; heavy household 40; 100 is an explicit proposed creation cap |
| Ledger history | 200 transactions/household/month, 24 months online: 38,400,000 transaction rows |
| Ledger growth | 1,600,000 new rows/month; include split children, refunds, transfers, pending entries and multiple separate currencies |
| Heavy households | At least 100 with 50,000 transactions each; include these in addition to the baseline volume or explicitly report the replacement distribution |
| Assistant activity | 2 questions/visit: 160,000 answers/month; 12 months yields 1.92 million answers and at least 3.84 million message records |
| Confirmed memories | Typical 10; proposed cap 100 per identity and household; send a bounded subset to interpretation |
| Refresh work | Two connections/household, one refresh/day: 16,000 jobs/day, spread over the day with deterministic jitter |

The 2% semantic mix assumes most assistant interactions use prepared controls.
Also run a separate semantic burst test: four concurrent fake 10-second calls
plus competing ordinary reads. This qualifies admission and responsiveness,
not provider quality, cost, or uptime.

Online history is a capacity assumption, not authorization to delete financial
records. Retention, export and deletion require a documented product policy
before public onboarding. Keep durable decisions and source receipts intact.
Expire only clearly temporary artifacts under an explicit policy: suggested
24 hours for unused import previews, 24 hours for completed export downloads,
30 days for detailed operational events, and seven days after expiry for old
session rows. Preserve aggregate operational counts without user content.

## Evidence available now

The ledger API handoff records 13,680 demo transactions across 24 months,
14 demo accounts and a separate household. The release captain reported local
measurements of approximately 12 ms for a transaction page, 0.82 ms for
spending, and 11 ms for the combined overview, with 22 focused ledger tests.
Those numbers are useful small-fixture evidence. They are not an authenticated
HTTP load test, a measured deployment result, or evidence at 38.4 million rows.

This review inspected `store.py`, `app.py`, `jobs.py`, and the platform common,
composition, identity, settings, ledger, assistant, investing and market-data
owners. It did not rerun business-math reviews, call paid providers, change
runtime code, or start a database service. Docker's executable is available;
the captain reported its local daemon was not running. No Docker or PostgreSQL
capacity evidence exists from this review.

## Two viable designs

| Design | Benefit | Constraint | Decision |
| --- | --- | --- | --- |
| Hardened SQLite on local SSD; one app deployment, initially one API worker and one separate job worker on the same host | Preserves the existing transaction owner and tested domain SQL; lowest operational complexity | One writer; one host failure domain; local disk, WAL/checkpoint and backup operations must be managed; cannot share a file across application hosts | Implement and measure now |
| PostgreSQL with a connection pool; same app/domains, multiple API/job processes | Concurrent row-level writes, multiple application hosts, managed backup/availability options | Real schema and SQL migration needed; the current `?` parameters, `executescript`, `rowid`, SQLite triggers and transaction assumptions are not portable | Implement when measured write contention fails the target or multi-host availability is a real requirement |

A configurable database URL alone is not a working PostgreSQL adapter. If the
second design is selected, add explicit PostgreSQL schema migrations, supported
query implementations and backend-parity contract tests. Keep the same domain
services and public API. Do not pretend a textual replacement of placeholders
makes SQLite SQL portable. A local Docker database can prove that adapter, but
cannot prove managed-service operations or production performance.

## Exact implementation handoff

The slices below change capacity ownership, not financial math. Keep existing
ledger, planning and simulation transaction boundaries and receipts.

### 1. Transaction and request foundation

Owners: `server/store.py`, `server/app.py`,
`server/platform/identity.py`, new `server/platform/runtime.py`.

- Configure WAL once during initialization, outside a transaction. Retain
  foreign keys and explicit transactions. Use durable synchronization settings;
  do not trade away acknowledged-write durability to improve a benchmark.
- Make session validation a read transaction. Update `last_seen_at` only when
  older than five minutes, with a conditional update that remains correct
  across API processes. Live membership and revocation checks still happen
  on every request. Cached identity must never override revoked access.
- Verify a password outside the write lock; recheck that the user and hash
  still match before creating the session. Likewise keep CSV parsing, HTTP
  fetches and model calls outside write transactions.
- Replace the current 30-second SQLite busy wait with a bounded measured
  request budget. Map exhausted contention to a typed 503 and `Retry-After`;
  do not retry an arbitrary mutation without its existing idempotency key.
- Ensure async assistant routes dispatch blocking domain work through the
  framework threadpool. Today `assistant.ask` performs synchronous reads and
  writes directly in its async handler. Provider awaits can remain async.
- Add a streamed request-body cap before JSON parsing: 64 KiB normally and
  2 MiB on the two existing CSV preview routes. Preserve their stricter
  character/row validations; count received bytes even without Content-Length.
- Return `X-Request-ID` for every API response. Generate server-owned IDs;
  incoming identifiers must be bounded and validated before optional reuse.

Tests: two independent Store instances, concurrent authenticated reads,
revocation on the next request, long fake model calls alongside ledger reads,
over-limit chunked bodies, and lock exhaustion returning a typed response.

### 2. One shared work and admission owner

Owners: new `server/platform/runtime.py`, `server/jobs.py`, `server/app.py`,
`server/platform/composition.py`, `server/platform/assistant.py`,
`server/platform/investing.py` and `server/platform/settings.py`.

Use the same database for operational admission and jobs. Do not use a process
dictionary, per-worker semaphore or a second service as global quota truth.

Minimal durable job record:

```text
Job(id, household_id, requested_by, kind, resource_id, dedupe_key,
    payload_hash, status, created_at, available_at, lease_owner,
    lease_until, attempt_count, completed_at, result_ref, error_code,
    correlation_id)
status = queued | running | succeeded | failed
unique(kind, household_id, dedupe_key)
index(status, available_at, created_at)
index(household_id, status, created_at)
```

The service exposes `submit`, `claim`, `heartbeat`, `complete`, `fail`,
`get_owned` and bounded `list_owned`. Submit atomically checks queue limits and
deduplicates the logical request; a reused key with changed input is 409.
Jobs contain references to authorized domain records, not arbitrary callable
names or raw request bodies. Shared market refreshes use an explicit global
scope rather than pretending they belong to whichever household clicked first.

Initial policy: at most two queued jobs and one running job per household,
500 globally queued jobs, and two worker slots. Among eligible households,
claim the oldest queued job, excluding households already running. The per-
household queue cap bounds how far one household can get ahead. Reject excess
admission with 429 and `Retry-After`; expose waiting state to the UI. A global
market refresh has a separate bounded slot so household saturation cannot
stop freshness work. Actual limits have one typed configuration owner.

Claim and terminal writes are short atomic transactions. Work runs outside
the lock. Use a lease longer than the bounded operation and periodic renewal;
completion checks the lease token, so an expired worker cannot overwrite its
replacement. On restart, recover expired work only where the operation is
idempotent. A recurring simulation uses its existing `(plan, scheduled date)`
receipt. Schedule from an indexed, paged due query; do not load every due plan
into memory or grant a fabricated editor role. Recheck active membership and
permission before executing household work.

Replace `/api/demo/events` process-local BackgroundTasks with durable submission,
preserving the existing `load_id` response and adding `job_id`. Add authenticated
`GET /api/platform/jobs/{id}` returning `{id,kind,status,created_at,completed_at,
result_ref,error_code}`. Enforce household ownership on status and download
reads. Keep provider refresh last-good data until a complete new batch commits.

Semantic calls can remain request/response but must reserve durable admission
before calling the provider: proposed two concurrent calls per household,
four globally, ten calls/household/minute and 500 calls/global/hour. Reserve
atomically, release the concurrency lease in `finally`, and expire abandoned
leases. Count an admitted attempt even on provider failure. This is a request
count budget, not a dollar budget; live spending remains disabled until pricing
and an explicit spending limit exist. Never automatically retry a charged call.

Tests: concurrent submission from two service instances; dedupe conflict;
queue saturation; one noisy household alongside another; worker termination
after claim; stale-worker completion; bounded retries; permission revocation;
exactly one durable recurring receipt; provider failure keeps last-good data.

### 3. Bound retained data and composed views

Owners: `server/platform/assistant.py`, `identity.py`, `settings.py`,
`investing.py`, `ledger.py`, their contract modules and corresponding UI clients.

- Keep ledger page size 100 and complete filtered aggregates. Add an opaque
  keyset cursor for date ordering if deep-page measurements justify it;
  preserve current offset clients while migrating them. A cursor includes the
  sort/filter identity and stable tie-breaker; validation cannot widen scope.
- Add paged assistant history/detail. Preserve existing fields and add
  `next_cursor`/`has_more`; the UI must follow pages rather than silently stop
  at the current 200-conversation cap. Index messages and answers on
  `(household_id, conversation_id, created_at, id)`.
- Use `COUNT(*)` for settings counts. Bound memory creation to 100 records per
  user and household; select at most 20 for a model request and at most 8 KiB
  serialized. Return a truncation indicator. User confirmation and opt-in
  remain required. Do not hide arbitrary truncation or turn memories into
  instructions.
- Keep household export coherent but move large exports into the durable job
  path. Write records in bounded batches to a temporary local artifact and
  atomically publish after success; do not assemble the whole household in a
  Python dict. Add `POST /settings/exports` with idempotency key, and an owned
  completed-download route. Keep the existing synchronous download only below
  an explicit row/byte threshold, with a typed route to the export workflow.
- Reuse a short database read snapshot for a composed portfolio or assistant
  assessment. Pass connection-level read helpers through the composition;
  never snapshot the full database into memory or keep a read transaction
  open during a model call. Ledger overview already does this correctly.
- Avoid a second household balance cache. First measure the indexed SQL.
  If cache is justified, its key must include household, permissions, query
  parameters and a transactionally owned revision; invalidation belongs to
  the same owner as mutations. Public market observations are a separate
  dated, shared dataset and never contain household information.
- Parse bounded CSV outside write transactions. Preserve commit-time dedupe
  under the original atomic write. If large-account scans dominate, add a
  persisted normalized import fingerprint/index owned by ledger and migrate
  existing rows; do not add a second approximate duplicate detector.

Tests: 50,000-row household, deep history, maximum memories, oversized export,
two simultaneous data revisions, and imported duplicates before/after restart.

### 4. Measurement and operational evidence

Owners: new `scripts/measure_capacity.py`,
`tests/test_platform_runtime.py`, `tests/test_platform_capacity.py`, and
`docs/evidence/capacity-<run-id>.json` plus a short Markdown readout.

Build a deterministic, restartable local fixture generator. Seed the 10,000
identities and 8,000 memberships/households explicitly. Record the seed,
per-household distribution, row counts, date range, currency mix, database size,
indexes and SQLite version. Batch inserts; never construct tens of millions
of Faker objects in memory. Use seeded Faker for incidental text and canonical
builders for valid financial shapes. Use fixture session tokens for most
traffic and test real password hashing in a separate bounded login burst.

Run two named dataset profiles. `development` uses at least three million
transactions and 100 heavy households for rapid feedback. `full-retention`
uses the stated 38.4-million-row baseline plus the documented heavy tail and
assistant history. Both have 10,000 identities. The first profile proves the
tested workload only; it does not close the full-retention claim.

For the current isolated build, the required executable path is
`scripts/measure_capacity.py --identities 10000 --households 8000 --transactions
5000000 --heavy-households 100 --heavy-transactions 20000 --rps 20 --burst-rps
40 --output docs/evidence/capacity-<run-id>.json` (proposed CLI contract).
The heavy rows are part of the five-million-row total, and remaining rows are
spread across all other households. Include one separate 50,000-row household
stress case and report it. This is the bounded acceptance profile to implement
and run now; full-retention generation remains optional until runtime/disk
budgets are known. The run must report actual counts rather than trusting its
command-line arguments. Do not start a 38.4-million-row run implicitly.

A passing bounded run supports the statement: "The isolated implementation
met the specified 10,000-MAU traffic model at 20 requests/second and a 40
requests/second burst on the recorded hardware, with five million ledger rows."
It cannot establish the 24-month retention estimate, deployment availability,
or provider behavior. Continued qualification requires keeping measured active
data within that tested envelope or running the full-retention profile before
claiming capacity beyond it. This is a capacity condition, not a silent data-
deletion rule.

Drive real localhost HTTP with fixed arrivals, timeouts, the stated route mix,
household variety and concurrent writes. Do not substitute direct function
timing, an in-memory database, or a closed-loop benchmark that reduces offered
load when the server slows. Include warm and cold starts, a second API process
on the same database, live queue work, import/export, and failure injection.
Record peak resident memory across API and workers, CPU, disk/WAL growth,
checkpoint duration, lock wait/rejections, offered versus completed requests,
request sizes and response sizes. Histogram by normalized route and status;
never by raw URL, household ID or query text.

Proposed acceptance targets, to be measured rather than asserted:

- Ordinary reads: p95 under 250 ms, p99 under one second at 20 requests/second.
- Small writes: p95 under 500 ms; no lost, duplicated or cross-household effects.
- 40 requests/second burst: bounded queue/memory; typed overload responses;
  no uncaught 5xx or unbounded database lock waits.
- Below admitted capacity: at least 99.9% requests succeed, excluding deliberate
  negative fixtures. Report overload rejections separately, not as successes.
- A quiet household's queued short job starts within 30 seconds while another
  household saturates its own admission; failed workers release leases within
  the documented recovery window.
- Four delayed mocked model requests do not break ordinary read targets.
- Target resource envelope: one 4-vCPU, 8-GiB host with local SSD; no more than
  2 GiB combined API/worker resident memory during ordinary load. A developer
  laptop result must report its actual hardware and is not evidence on this host.

Operational events contain only server-generated correlation ID, normalized
route, method, status, duration, job kind/state, error code and numeric usage.
Do not log request/response bodies, cookies, credentials, SQL parameters,
financial amounts, user messages or confirmed memories. Record provider
attempts/failures/timeouts separately from completed logical questions.
Unknown token pricing stays unknown. Keep metrics cardinality bounded.

### 5. Backup and restore qualification

Owners: `server/store.py`, `server/jobs.py`, new
`scripts/check_backup_restore.py`, and the capacity evidence directory.

Add an explicit offline maintenance CLI for SQLite's online backup API. The
source remains the application database; write to a new temporary backup file,
complete the backup, run integrity checks, then atomically rename the output.
Never copy only the live main database file while WAL writes are active. Keep
backup files outside publicly served directories, with owner-only permissions.
Do not expose a public backup endpoint. Do not log exported financial records.

The local verification script must perform writes during backup, restore into
a separate temporary directory, check foreign keys/integrity and domain record
counts, and prove household isolation plus one existing immutable receipt.
Verify that original input hashes/source references remain available after
restore. The test may remove only its own temporary outputs. Never replace the
running local demo or a production database as part of a test.

Proposed operating targets: recovery point within one hour; restore within one
hour for the qualified dataset. These are objectives, not current guarantees.
Record backup duration, byte size, restored counts and elapsed restore time.
An eventual deployment requires encrypted off-host backup storage, scheduled
backup delivery, retention, an alert for missed backups and a restore drill on
the actual target host. Local restore evidence alone cannot prove the off-host
or disaster-recovery requirements.

Stop the run and retain its partial evidence if the fixture would exceed 20 GiB
or available disk would fall below 10 GiB, peak combined process memory exceeds
4 GiB, a test contacts any remote provider, any cross-household effect appears,
or a workload hangs beyond its declared total timeout. A resource stop is an
incomplete measurement, not a pass or evidence of corruption. If ordinary
traffic exceeds latency/error targets after the identified lock fixes, inspect
query/lock evidence before changing architecture; do not compensate by reducing
the offered load while reporting the original target.

## Pillars and current truth

| Pillar | Implemented basis | Must implement/verify for this workload | Still externally unverified |
| --- | --- | --- | --- |
| Intelligence | Typed read-only interpretation; ledger/domain owners calculate facts; dated evidence; immutable answers; opt-in confirmed memories | Bounded memory/context, coherent composed snapshots, visible partial/stale facts, model admission | Real model quality, cost and full-turn behavior; no live provider run establishes these yet |
| Evaluation | Focused domain/isolation/receipt tests and a substantial local ledger fixture | Reproducible capacity artifact, multi-instance contention/recovery tests, HTTP mix, heavy households, bilingual UI under waiting/failure states | Public traffic, actual browser/network latency and real institution integrations |
| Platform | Single Store transaction owner, household Context, domain lifecycle callbacks, idempotent financial receipts, read-only market adapter seam | WAL, read-mostly auth, shared jobs/quotas, input limits, correlation IDs, retention and backup/restore evidence | Managed hosting, disaster recovery, multi-host failover, production identity and secure vendor credential lifecycle |
| User experience | Account-first pages, contextual assistant, dated sources, explicit simulated capabilities | Honest queued/failed/overloaded/stale states, navigable pagination, export progress and responsive reads during slow work | Customer usability and accessibility under real assistive technologies/networks beyond the local acceptance matrix |

The public-onboarding boundary remains closed. Local passwords and demo
personas are not production identity; trusted localhost hosts remain in place.
Bank connections, credit data, tax/legal workflows, memberships, bookings,
broker orders and money movement remain visibly simulated. Real authentication,
credential storage, consent, vendor approval and delivery mechanisms require
separate implementation and verification. None of those external capabilities
is implied by passing a local load test.

Revisit PostgreSQL when a full-retention run fails because of measured write
serialization after short-lock fixes, when backup/restore objectives cannot be
met on one host, or when the availability requirement demands multiple hosts.
Preserve exact counts, failure evidence and the tested commit when making that
decision. No SOTA or 10,000-user-ready claim is earned by this design document.
