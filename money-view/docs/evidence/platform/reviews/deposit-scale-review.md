# Deposit scaling review

Reviewed the immutable `deposit-scale-review.diff` against base `d1c622d9`, current deposit service/store/jobs paths, the added service/API tests, and the runtime queue's claim, renewal, completion, and terminal domain callbacks. No Git operations or external calls were made.

**Verdict: one P2 issue. No P1 issue found.**

## P2: Renew the lease while the scheduled CLI executes long rechecks

Location: `money-view/server/jobs.py:46-49`.

The CLI now executes queued jobs with `worker_tick`, which synchronously calls `_execute_and_finish` without a heartbeat (`platform/jobs_runtime.py:437-447`). Lease renewal exists only in the async worker slot. A valid recheck that lasts longer than `job_lease_seconds` therefore loses completion authority even while its process is healthy: `_finish` requires `lease_until > now` and rejects its terminal write.

Exact reproduction condition: use the supported policy of a 3-second lease and one maximum attempt, then execute a successful scheduled deposit job whose committed rechecks take 4 seconds. The load and all checks finish successfully, but the job remains `running` because its completion CAS fails. The CLI's next `worker_tick` treats the lease as exhausted, marks the job `failed` with `job_attempts_exhausted`, and the CLI exits 1 despite successful domain work. With the default 30-second lease/three attempts, exceeding the lease consumes an unnecessary replay; another active worker can also reclaim the still-running job. This is directly relevant to the newly admitted large saved-decision workload.

Shared owner: the runtime's leased execution lifecycle. Have the scheduled CLI use the same heartbeat-managed execution path as the lifespan worker, rather than maintaining a second execution path without renewal. Keep the existing completion fence. Add a focused fake-clock or shortened-lease CLI regression that spans a lease and verifies one attempt, successful terminal state, and one check per decision.

Evidence: complete static trace through the changed CLI, `worker_tick`, `_finish`, and expired-lease claim handling. This reviewer did not run the reproduction or rerun existing tests under the read-only scope.

## Accepted paths and verification limits

- Dataset publication, load status, and high-water checkpoint are committed atomically. Provider failure and rejected older publication retain the last good complete bundle. Existing publication-date checks remain in force.
- Each batch writes immutable decision checks and advances its durable cursor in the same transaction. A process exit before commit rolls both back; resumption after commit starts after that cursor. Published data are read from the load's pinned datasets without refetch.
- A newer successful publication fences older successful rechecks inside the write transaction. A newer publish cannot interleave midway through one batch. Household ownership is inherited from each original comparison when creating recheck results.
- Terminal queue failures preserve an already-published bundle and completed batches while marking unfinished rechecks failed. Source/load responses expose recheck status separately from publication status.
- The notice summary limits result hydration to the requested page, preserves household ownership and full-filter counts, and reports actual publication dates from published/synthetic sources without inventing a publication date for user inputs.
- Inspected the crash/resume, newer-publication, save-during-recheck, terminal-failure, competing-writer, bootstrap ownership, and notice-pagination tests. The save-during-recheck case constructs a new confirmation on the published bundle; it does not prove freshness for a previously pinned comparison saved later. That older save/confirmation behavior is unchanged by this diff and is not raised as a new finding.
- Captain-reported verification: 69 focused service/API/runtime tests green. This review did not rerun those tests, the capacity workload, or unchanged financial calculations. The passing CLI cases complete inside a lease and do not cover the finding above.

Only this report was written. Review complete; no active follow-up retained.

## Scoped CLI lease fix re-review

**Verdict: clean. The P2 CLI lease finding is closed. No actionable defect found in this fix delta.**

`worker_tick` now calls the async `run_one` entry point through `asyncio.run`; `run_one` and the lifespan slot both delegate execution to `_execute_with_lease`. That shared supervisor renews every third of the lease interval while execution remains in flight. The existing token/expiry completion fence stays intact. Cancellation shields and drains the supervisor, retaining renewal while its local thread finishes.

Inspected the new parameterized regression for `worker_tick`, `run_one`, and actual `jobs.main`. Each uses a three-second lease and one allowed attempt, holds execution beyond the initial expiry, verifies competing claims cannot reclaim it and the lease advances, then verifies one execution, one attempt, successful terminal status, and CLI exit 0. Existing synchronous call sites remain compatible; async callers have the explicit `run_one` API. The handoff documentation describes the shared ownership.

Worker-reported evidence: 32 runtime tests pass. This reviewer inspected source, call sites, and regression assertions without rerunning unchanged tests. Financial domains and earlier accepted deposit paths were not reopened. Only this report was changed; review complete.
