# Finalizer configuration audit, issue #437

Audit of every write that can attach a result to a backtest job or move a
job's lifecycle, traced through each finalizer configuration, at lane base
`87fa44c2` and fixed at this lane's head. Enforced going forward by
`tests/test_backtest_job_write_invariant.py` (write-site enumeration) and
`tests/test_backtest_job_link_postgres.py` (real-Postgres interleavings).

## The writer inventory

Every site that writes `public.backtest_jobs`, with its gate:

| Writer | Gate at lane base | Disposition |
| --- | --- | --- |
| `SupabaseGateway.link_backtest_job_result` (PostgREST) | lifecycle filter only when `mark_succeeded` | **Hole, fixed**: attach filter applied unconditionally |
| `PostgresBacktestJobGateway.link_backtest_job_result` (worker SQL) | `%(status)s is distinct from 'succeeded' or <predicate>` bypassed the statement when not marking succeeded | **Hole, fixed**: attach predicate ANDed unconditionally |
| `routers/agent.py` publication after the link | none; published unconditionally | **Hole, fixed**: publishes only on a `ResultLinkOutcome` that attached |
| `PostgresProofJobGateway.update_job_status` (proof task) | pre-check read only; the write itself was unconditional, so a canceled job could be flipped back to running or succeeded, re-opening the attach window | **Hole, fixed**: success predicate in the write; refused transitions report the standing row |
| `SupabaseGateway.mark_backtest_job_failed` / worker `mark_backtest_job_failed` | CAS via `expected_status`/`expected_updated_at` where reconcilers race; nulls `result_run_id` | Clean |
| `SupabaseGateway.mark_backtest_job_running` / worker `_try_mark_backtest_job_running` | strict CAS (queued or finalization retry); worker adds `for update` + advisory lock | Clean |
| `SupabaseGateway.complete_research_job` | scope CAS `chat.research` + status in queued/running; never touches `result_run_id` | Clean |
| `finalize_direct_backtest_job` (PostgREST) and `finalize_direct_backtest_success` (DB function) | status `running` CAS; the DB function also takes `for update` | Clean; direct scope carries no card |
| Admission RPC (`admit_backtest_job` migrations) | advisory lock; inserts queued; stale direct running flips to failed retryable only | Clean |
| Guest handoff migrations | ownership (`user_id`) only | Clean |
| `create_backtest_job`, `create_proof_job`, metadata merges | no lifecycle columns, `result_run_id` untouched | Clean |

## Per-configuration trace

### api-safe-off (`SHADOW=true, DISPATCH=false, EXECUTION=false`)

Run admission creates the durable job and stamps the card; no dispatch, so
the in-process run links with `mark_succeeded=True`. That write has carried
the success predicate since round 6, so the database was already refusing
the late success. The remaining hole was the publisher: `agent.py` ignored
the refusal and published anyway. Fixed by deriving publication from the
link outcome. With the whole surface dark (`SHADOW=false`, the local dev
shape), no job exists, the link is a no-op, and publication proceeds; the
consumption stamp also never lands in that shape, which is the audit
finding filed as #439 (registered users, local configurations only; every
hosted configuration runs shadow admission).

### api-proof-shadow-on (`SHADOW=true, DISPATCH=true, EXECUTION=false`)

The configuration the issue names, and the dirtiest at base. The proof
task owns job status while the API's in-process run owns the result link,
which arrives with `mark_succeeded=False` and therefore bypassed the
lifecycle statement entirely: a job the reconciler had killed (canceled
proof task run, `workflow_task_canceled`, retryable false) had its card
restored, then still received `result_run_id`, and the result published
beside the active card. No user edit and no tight race required, only a
terminal reconciliation landing before the in-process run finished.

Three fixes close it: the attach guard on both link writes (a dead job
refuses the link), publication derived from the outcome (a refused link
publishes nothing and settles the turn with `run_result_withheld`), and
the proof task's own transitions gated (a dead job cannot be flipped back
to running or succeeded, so the attach window cannot be re-opened).
`succeeded` remains attachable by design: the proof task legitimately
finishes first in this configuration, and a succeeded job's card is
consumed for good, so the attach cannot split card and result.

### api-real-workflow-on (`SHADOW=true, DISPATCH=true, EXECUTION=true`)

The current production shape in `render.yaml`. Clean at base for the
running path: the API returns the async envelope without executing, the
worker links with `mark_succeeded=True` under the round-6 predicate, and
the conversation hydrates the result from the job row, so publication
already derived from the link. Worker failures restore the card through
the same classification. Two base-state caveats the lane closes anyway:
the emergency rollback for this configuration is flipping
`EXECUTION=false`, which lands exactly in proof-shadow above, and the
API-side branch that merges metadata when a dispatched job replays under
`EXECUTION=true` publishes an in-process result without a link. That
branch is unreachable from the current admission flow (replays return the
async envelope before the delegate runs); it is enumerated by the
invariant suite so it cannot quietly become reachable ungated.

## What the interleaving proofs pin on real Postgres

`tests/test_backtest_job_link_postgres.py`, running under the CI
`tests/test_*_postgres.py` glob:

- the attach predicate and the classifier agree on every state row;
- a restored card cannot gain a result through either link encoding;
- the proof transitions cannot revive a dead job;
- the legitimate proof-shadow and real-workflow success paths still land.
