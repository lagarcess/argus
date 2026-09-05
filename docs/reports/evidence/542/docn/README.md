# DOCN refusal: production 7d8ace45

Incident: conversation `623011f3-7b89-4b1d-b6c3-cd7a99300c8c`,
2026-09-04 23:16 UTC. Investigation used SELECT-only hosted queries and
isolated local PostgreSQL/PostgREST execution. No production writes or provider
calls were made.

## Finding

The evidence supports `conversion_required`, caused by the preserved guest
workspace simulation allowance. It does not support a reservation collision.
The earlier five-symbol incident's spent-confirmation diagnosis does not
explain this distinct DOCN incident.

The claim "zero jobs/runs, ever" does not follow from the current tables:
`replace_guest_conversation` deletes those rows during Start over while
deliberately preserving `usage_counters`, guest identity, and fixed expiry.

Read-only hosted evidence (queries in [readback.sql](readback.sql)):

| Fact | Readback |
| --- | --- |
| Verified anonymous Auth identity | true |
| Workspace created | 2026-09-03 03:34:06.293312 UTC |
| Current conversation created / workspace updated | 2026-09-04 23:04:06.665235 UTC |
| Workspace expiry | 2026-09-10 03:34:06.293312 UTC |
| Surviving jobs / runs | 0 / 0 |
| `backtest_runs` guest-session counter | used 2, limit 2 |
| Counter first charge | 2026-09-03 03:38:35.030751 UTC |
| Counter last charge | 2026-09-03 03:50:44.648603 UTC |
| Counter window | exactly matches workspace creation and expiry |
| Earlier successful `result_summary` receipts for this same owner | 2026-09-03 03:39:07.022678 and 03:51:02.119656 UTC |
| Reservations for the DOCN confirmation, across all users/scopes | 0 |

The retained counter, earlier result receipts with cleared conversation
attribution, replacement conversation, and live deletion function establish
the Start-over explanation. There is no retained click audit, so the exact
UI gesture is inferred from those records, not independently logged.

The live admission RPC checks `(user_id, operation_scope, idempotency_key)`.
Only a matching existing job with a mismatched identity (or mismatched legacy
payload hash) returns `conflict`. Another user's identical key cannot claim
this reservation. The advisory lock serializes admission; its hash does not
own reservation identity. With no reservation and this exhausted, valid
guest-session counter, the RPC returns `conversion_required`.

The absence of a `guest_funnel_milestones` row cannot eliminate that branch.
`guest_limit_reached` is repeatable telemetry, excluded from
`MILESTONE_EVENT_KINDS`; it never claims a row in that table.
`allowance_exhausted` also does not call the funnel emitter on this production
line. Missing analytics is not authoritative admission evidence.

## Local proof and #543 coverage

The unmodified production source archive at
`7d8ace45e4ac717ffbfaf222cf66544c3355df6f` and #543 follow-up were each exercised
through the real `ShadowBacktestJobTool`, `SupabaseGateway`, PostgREST, and
`execute_stage`, on isolated PostgreSQL 17.6. The replay seeds two admissions,
clears the conversation through the actual Start-over RPC, then presses the
equivalent DOCN Run action. No decision is mocked.

The local and hosted `pg_get_functiondef` values match exactly:

| Function | MD5 of definition |
| --- | --- |
| `admit_backtest_job` | `4864ae113274ac0b1e21f3a0258f997f` |
| `validated_usage_windows` | `8f15ae8cadbad35818de3b11fef7328d` |
| `replace_guest_conversation` | `9865b35765c311423acd5ab7f02e4244` |

The database uses all repository migrations. Local Auth bootstrap supplies
`auth.jwt()` and `auth.users.is_anonymous`; this is not an Auth-login or
browser canary. The three incident-owning functions above are unmodified.

| Outcome | Production source | #543 with logging follow-up |
| --- | --- | --- |
| Jobs before attempted launch | 0 | 0 |
| Guest simulations already charged | 2 | 2 |
| New receipt | none | one failed job |
| Failure code | none persisted | `account_conversion_required` |
| Failure detail | none persisted | `guest_simulation_allowance_exhausted` |
| Assistant prompt | generic "could not complete" | explains exhausted guest allowance and account creation |
| Workflow dispatch | no | no |
| Additional allowance charge | none | none |
| Repeat of refused request | no receipt | same receipt id |

See [production replay](production.json), [candidate replay](candidate.json),
[before log](production-log.txt), [after log](candidate-log.txt), and
[replay program](replay.py). These are local reproductions, not recovered
hidden Loguru extras from the historical production request.

The durable-receipt and reason-specific recovery in #543 therefore cover this
case. Spent-confirmation rotation is unrelated to its cause. The logging
follow-up renders the decision and correlation ids as escaped JSON at the
shared rejection boundary, including visitor and capacity refusals. It does
not change allowance policy or refund prior admissions.

## Verification

- Six rendered-log cases failed before the logging change and passed after it.
  Tests inspect the default sink text and cover privacy and newline escaping.
- 82 focused admission/receipt/guest/observability checks passed.
- 100 mocked runtime/eval checks passed.
- Five real-PostgreSQL cases passed: zero, one, and two historical admissions
  followed by Start over, plus existing guest charge/replay/exhaustion and complete-graph Start-over proofs.
  A guest with unused allowance is admitted; an exhausted guest receives
  `conversion_required`. Clearing history does not create a conflict.
- Production-source and candidate gateway/stage replays passed, including
  real receipt insertion, readback, and repeat convergence.
- Bounded independent Codex review: clean; reviewer reran all six rendered-log
  cases and verified the evidence claims and links. Lint and modularity pass.
- Follow-up base: PR #543 at `82c103fbb145d2e8431408c26f57ccacd12d0b03`.
  Integration at start and final fetch: `4c8e80639adbe1fe7bbe9c384a30e0ad81f17357`,
  already an ancestor of that PR head. No reconciliation or new semantic
  overlap; this follow-up changes service logging only, plus tests/evidence.

Issue #542 remains open. This evidence proves local coverage, not deployment
or hosted acceptance of #543. The production behavior remains unchanged until
the founder promotes the fix.
