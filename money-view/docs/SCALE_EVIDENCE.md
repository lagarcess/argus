# Clara local capacity evidence

This is a bounded development workload on an Apple M5 Pro laptop (18 CPU
cores, 48 GiB RAM), not a deployment or 24-month retention qualification.
The run uses an isolated database in `/private/tmp`, two real Uvicorn API
workers sharing SQLite WAL, and real authenticated loopback HTTP. Ports 8012
and 8022 and the ordinary local demo database are untouched.

## Dataset and reproducibility

The generated population contains 10,000 identities, 8,000 households and
5,000,000 ledger rows. The existing built-in demo adds four identities, two
households and 13,680 ledger rows; JSON evidence reports actual database
counts separately. The heavy tail replaces part of the five-million total:
100 households have 20,000 rows each, one has 50,000, and the remaining 7,899
have 373 or 374. Each household has eight accounts, or 40 for heavy/stress
households. Currencies remain separate. Posted/pending entries, income,
refunds, matched transfers and split categories span 730 days ending
September 20, 2026.

The deterministic generator uses seed `20260920`, stable UUIDs, a seeded
Faker merchant catalog reused across rows, and batches of at most 2,000
rows. It resumes completed households and uses idempotent inserts within an
interrupted household. It rejects an existing database it does not own.
Passwords use one explicitly synthetic shared scrypt fixture hash; normal
identity hashing is unchanged. Traffic uses actual session cookies checked
against hashed, persisted sessions and current memberships.

Run from `money-view/`:

```sh
.venv/bin/python scripts/scale_check.py \
  --database /private/tmp/clara-capacity-new/fixture.sqlite3 \
  --output docs/evidence/scale/capacity-new.json \
  --identities 10000 --households 8000 --transactions 5000000 \
  --heavy-households 100 --heavy-transactions 20000 \
  --stress-transactions 50000 --seconds 600 --burst-seconds 60 \
  --rps 20 --burst-rps 40
```

The generator refuses estimated disk consumption above 10 GiB, above 20%
of available disk, or leaving less than 10 GiB free. The driver stops when
40 in-flight slots are exhausted, server RSS exceeds 4 GiB, a checked read
p99 exceeds one second, or a privacy/integrity/unexpected-HTTP check fails.
It never reduces the offered rate to hide latency. Full-retention generation
is not implicit and is not authorized by this command.

## Checks and measurement boundaries

Traffic uses fixed arrivals: 40% transaction lists, 25% overview, 15%
spending, 10% settings/history, 5% ledger writes, 3% prepared assistant, and
2% deterministic semantic fixtures. Ordinary application HTTP responses are
not mocked. Only interpretation is a test seam. The full run's seam acquired
and released real shared leases around ten-second calls. The final-source
probe uses the subsequently shared `model_admission` context and eight-second
calls, safely inside its ten-second deadline. Four delayed calls exercise
admission while ordinary reads compete; a fifth must receive a typed 429
and `Retry-After`.

Checks include real-password login, immediate session revocation, household
ownership, the 100-row limit, heavy-household count truth, use of the ledger
date index, write replay/conflict behavior, SQLite integrity and foreign keys.
The evidence stores counts, source-code hashes, status/route latency summaries
and resource totals, without cookies, identities or financial records.

RSS includes the Uvicorn supervisor and descendant API processes, sampled
every five seconds. CPU is the maximum observed sum of `ps %cpu` values,
which are process-lifetime averages, not an interval CPU utilization trace.
Client queue lag is included in route latency and reported separately. The
generator has its own peak-RSS measurement. No deployment network, browser
rendering, real provider latency, model quality or provider cost is measured.

## Results

- [Seed evidence](evidence/scale/seed-5m.json): 5,000,000 generated rows in
  66.77 seconds; database 2,744,434,688 bytes; generator peak RSS 95,109,120
  bytes on macOS.
- [Small HTTP smoke](evidence/scale/smoke.json): 180 requests, ten distinct
  authenticated fixture identities, all measured targets passed. Includes
  the delayed semantic and ownership/idempotency/revocation checks.
- [Five-million HTTP run](evidence/scale/capacity-5m.json): **14,400 of 14,400
  requests returned HTTP 200**, exercising all 10,000 fixture identities.
  The sustained phase offered 20 requests/second for 599.98 seconds; the
  burst offered 40 requests/second for 60.01 seconds. The largest observed
  in-flight count was three, within the 40-client cap.
- Peak combined supervisor/API RSS was **231,604,224 bytes (220.9 MiB)**.
  The startup-to-ready time was 0.45 seconds. No normal-load backpressure,
  client-cap rejection, uncaught HTTP failure or integrity failure occurred.
  The deliberate fifth semantic request was correctly rejected separately.
- Ledger count after load was **5,014,401**, exactly the initial 5,013,680
  plus 720 successful load writes and one deduplicated precheck write.
- With four ten-second semantic fixtures in flight, 40 competing ordinary
  reads had p95 30.57 ms and p99 49.83 ms.
- [Backup and restore](evidence/scale/backup-5m.json): online backup 10.83
  seconds, restore to a new file 11.66 seconds, identical row counts,
  integrity/foreign-key checks, source-reference preservation, and zero
  account/transaction household mismatches. The source, backup and restore
  total 8,233,304,064 bytes. The concurrent probe committed 396 no-op activity
  updates; changed financial records and immutable-receipt preservation are
  covered by focused storage tests, not claimed by this large-file probe.

Seven focused harness tests verify the acceptance distribution, restart
idempotency, valid transfer/split/account-currency shapes, and omission of
provider credentials from the worker environment, and refusal to change an
unowned database with a nonzero CLI exit, including low-disk hosts. Ownership
validation precedes capacity checks; eligible new paths still stop before
creating a database when disk capacity is insufficient. The worker environment is
an allowlist with empty Clara LLM settings; socket DNS/connect/connect-ex
guards permit loopback only.

| Normalized route | Sustained p95 / p99 (ms) | Burst p95 / p99 (ms) |
| --- | --- | --- |
| Transaction list | 17.57 / 39.39 | 9.53 / 25.60 |
| Overview | 12.40 / 34.53 | 8.44 / 9.71 |
| Spending | 11.20 / 13.02 | 8.19 / 9.40 |
| Settings/history | 11.22 / 12.63 | 8.70 / 9.49 |
| Ledger write | 11.38 / 13.96 | 9.05 / 13.99 |
| Prepared assistant | 12.48 / 16.48 | 10.45 / 12.82 |
| Synthetic semantic assistant | 37.80 / 40.55 | 55.69 / 55.90 |

Code changed during the long run in app composition, Store, assistant,
investing, durable jobs and shared model admission. Each artifact records
source hashes. The long run describes the imported implementation at its
start; the separate [final-source probe](evidence/scale/final-source-probe-5m.json)
checks the subsequent implementation with fresh processes and the same
five-million-row database. It must not be described as a second ten-minute run.

The final probe passed **400 of 400 requests**. Its eight-second shared-admission
check kept competing reads at p95 **35.42 ms**, p99 **42.31 ms** and returned
the expected fifth-call 429. A final hash comparison found **zero changed
source files** after that probe. An earlier 400-request probe is retained
separately because route typing/import formatting and the job CLI lease
supervisor changed during it. The release captain confirmed that the long
run's financial query behavior was preserved by those changes.

[Final validation](evidence/scale/final-validation.json) reconciles all three
large-dataset traffic runs: **5,014,441 ledger rows**, exactly 5,013,680 initial
rows plus 760 successful load writes and one deduplicated fixture write;
761 command receipts match that growth. The final harness also asserts row
growth and fails on any false integrity check or delayed-read SLO failure.
The final idle checkpoint reported no busy reader or pending WAL pages; this
does not measure checkpoint contention during traffic.

The complementary small-dataset tests in `tests/test_platform_storage.py`
are `test_online_backup_copies_committed_wal_and_restores_new_private_file`
and `test_backup_restore_preserves_credentials_sessions_and_household_ownership`.
They cover an uncommitted changed-value writer and preservation of an
immutable simulation receipt, credentials and household ownership.

After final validation, the owned API workers were confirmed stopped and
the generator database, backup, restore and smoke files were removed.
[Cleanup evidence](evidence/scale/cleanup.json) records **8,248,168,887 bytes
reclaimed**. Only reproducible tooling and compact evidence remain; the
ordinary local demo database was never used.

The initial post-smoke startup refusal is retained in
[startup evidence](evidence/scale/startup-port-reuse.json). Its bind preflight
encountered TCP TIME_WAIT, not a live listener; matching Uvicorn's
`SO_REUSEADDR` behavior fixed the harness before measured traffic began.

The 38.4-million-row retention model, 30-minute sustained/5-minute burst
design duration, and 4-vCPU/8-GiB target machine remain unqualified by this
shorter laptop run. Local backup success does not establish encrypted
off-host backups, availability, scheduled recovery points or disaster recovery.
Concurrent import/export jobs and worker-crash recovery are covered by focused
domain/runtime tests, not included in this HTTP traffic mix. WAL size was
observed at approximately 4 MiB during the soak and zero after it; no claim
of continuously sampled peak WAL or under-load checkpoint timing is made.


## Revalidation after PR review fixes

Commit `919cc0f4` adds current membership and household-generation checks to
private writes and semantic/job admission, and corrects portfolio dates and
recurring schedules. The earlier longer run remains historical evidence.
A fresh five-million-row fixture and new worker processes revalidated these
changes; this is a shorter follow-up, not another ten-minute qualification.

- [Fresh seed](evidence/scale/lifecycle-seed-5m.json): 5,000,000 generated
  transactions, 10,000 identities and 8,000 households, plus the explicitly
  reported built-in demo overhead. Seed time 67.25 seconds.
- [Follow-up traffic](evidence/scale/lifecycle-capacity-5m.json): **2,400 of
  2,400 HTTP requests succeeded**, across **2,400 distinct authenticated
  identities**. Offered load was 20 RPS for 60 seconds, then 40 RPS for
  30 seconds, with at most two ordinary requests in flight.
- Transaction-list p95 was **33.49 ms** sustained and **8.47 ms** burst;
  ledger-write p95 was **10.44 ms** and **7.21 ms**. Peak combined API RSS
  was **212.6 MiB**. Four eight-second semantic fixtures kept competing-read
  p95 at **34.71 ms** and p99 at **50.05 ms**; the fifth call received the
  expected 429.
- Isolation, pagination, heavy/stress-household counts, real local login and
  revocation, write replay/conflict, foreign keys and integrity passed.
  Final rows were **5,013,801**, exactly the seed plus 120 load writes and
  one deduplicated precheck write.

The [source manifest](evidence/scale/lifecycle-source-manifest.json) records
before/after application and harness hashes. This revalidation preserves
all the target-host, retention, provider and hosted-operation limitations
above. It does not turn local measurements into a production SLA.

The [follow-up cleanup receipt](evidence/scale/lifecycle-cleanup.json) confirms
that owned workers stopped and only the fresh fixture database and its
sidecars were removed, reclaiming 2,745,200,640 bytes. The captain rechecked
all 116 browser and 36 capacity source hashes before packaging; all matched.
