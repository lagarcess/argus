# Capacity delta review

Review date: 2026-09-20. Scope: the implemented Store, storage operations,
shared runtime/jobs, session activity throttling, export reader, app composition,
and model-admission callers. Runtime worker confirmed `runtime.py` and
`jobs_runtime.py` frozen before this pass. App/caller integration remained with
the captain and assistant worker.

**Terminal scoped verdict: CLEAN. Both P2 findings are closed.** The latest
deadline/policy/test delta returned clean; no unresolved finding remains from
this bounded review. This does not expand the capacity or deployment claims.

Initial result: **two confirmed P2 findings; no P1 found in this bounded pass.** Both
findings concern the shared admission invariant: an active provider operation
must continue occupying capacity, and consumed attempts must not be refunded
by deleting product data. They require class-level fixes in the existing owner,
not special cases for individual routes.

## P2: Household reset refunds admission and frees live provider slots

Owner: `server/platform/jobs_runtime.py:499`, `clear_data`, especially lines
513–519; reached through the registered runtime lifecycle callback from
`POST /api/platform/settings/data/reset` in `settings.py:352`.

The cleanup deletes the household's active model leases and daily counters.
Deleting a lease cannot cancel the HTTP call that already holds it. A household
owner can reset while a call is in flight, then submit another call with the same
live identity. The second call bypasses both the household and global concurrent
count for the still-running first call. Reset also replenishes the same
household's daily attempt allowance. The global daily count survives, so this
does not bypass that separate cap, but it breaks the documented household
allowance and global concurrency guarantee.

Confirmed with the actual Store/runtime owner, one temporary SQLite database,
`model_global_concurrent=1`, `model_household_concurrent=1`, and
`model_household_daily=1`:

```text
first lease remains unexpired: True
second request admitted before first released: True
reported attempts after two admissions with reset: 1
```

Reproduction: initialize the Store/runtime; acquire lease A; invoke
`jobs_runtime.clear_data(connection, context)` in a write transaction; acquire
lease B before releasing A; inspect `runtime.usage`. The production-facing
model call need not be made to reproduce the broken admission transition.

Smallest safe fix: separate operational quota retention from product cleanup.
Keep live reservations until cancellation/release or their normal crash expiry;
retain consumed household/day attempts through the existing bounded retention
window. Clear household-owned job/product data as appropriate. If deletion needs
to remove identifiers, use an explicit bounded operational tombstone policy that
cannot replenish the allowance. Do not silently clear active global accounting.

Acceptance: block a fake provider call; reset its household through the actual
HTTP endpoint; a competing call must still receive 429 until the first call
finishes; daily attempts must remain consumed after reset; unrelated household
counts remain unchanged. Include deletion/clear callbacks wherever the same
owner is invoked, rather than fixing only the reset route.

## P2: HTTP inactivity timeout does not bound a model lease's live work

Owner: `server/platform/runtime.py:209`, `model_admission`, and its caller
contract. Active admission expires after 30 seconds by default, but the context
manager imposes no total operation deadline. Both current provider callers use
HTTPX's ten-second timeout. HTTPX defines its read timeout per received chunk,
not as a total request deadline. A provider that keeps sending chunks can remain
active beyond the lease, at which point `_expire_models` removes its reservation
and another call is admitted. This is an ordinary slow-response condition, not
a need for an enterprise-scale threat model.
[HTTPX timeout semantics](https://www.python-httpx.org/advanced/timeouts/).

Confirmed at the actual shared wrapper with an event-blocked async operation
and a controlled clock advanced just beyond its stored lease:

```text
first model operation is still running: True
new model request admitted after lease expired: True
```

Reproduction: run an async operation inside `model_admission`; keep it awaiting
an event; advance the test clock past its stored expiry; call `acquire_model`
again with global/household concurrency one. The new call succeeds while the
original task is still running. No provider or network calls were used.

Smallest safe fix: one canonical whole-operation deadline, enforced by the
shared async owner and strictly shorter than its lease, including cancellation
and response parsing. Keep provider-specific inactivity timeouts as transport
guards. Validate the deadline/lease relationship in `RuntimePolicy` rather than
placing matching literals in both adapters. An alternative is lease renewal
plus a separate bounded total operation deadline; simple cancellation is more
proportionate for the current ten-second model calls.

Acceptance: a delayed/dripping fake response is cancelled at the whole-call
deadline, records one timeout, releases admission once, and never permits two
live operations when the shared concurrency limit is one. The caller must
translate that deadline to its existing fixed unavailable/error code. Exercise
both assistant and deposit callers because they share this admission owner.

## Inspected without a new finding

- WAL and bounded busy waits; explicit write rollback; pinned, read-only,
  path/thread-scoped snapshots. Portfolio composition now uses the snapshot
  owner. The already coherent ledger overview was not reopened.
- Online SQLite backup into private staged files, manifest hash/integrity/FK
  checks, no-replace publication and restore to a new file. Existing tests cover
  committed WAL data, ownership, credentials, receipts and tamper rejection.
  This is local recovery evidence, not off-host backup availability.
- Read-mostly session validation still reads membership and revocation from
  SQLite on every request. Activity touches use a conditional timestamp update.
- ExportReader's single cumulative source-row/source-byte budget across domain
  callbacks, fixed 413 failure before returning any partial download, and
  credential exclusion. Its source budget does not claim an exact final JSON
  byte limit.
- Durable queue insert/dedupe, cross-process claims, shared configured caps,
  household-owned status, current-owner check before dispatch, token-fenced
  heartbeat/completion, bounded recovery attempts, and explicit failure for a
  nonreplayable price load. Scheduler submission remains a trusted local API.
- Request/header/chunked-body caps, body receipt deadline, fixed API errors,
  server correlation IDs and normalized route logs without financial content.

## Verification and limits

Read the current focused storage, identity, runtime and composition tests.
Ran the two small admission regressions above against actual implementation
functions in disposable temporary databases. Did not rerun the broad test
suite, capacity fixture generator, UI acceptance, provider calls or financial
math. No runtime files, Git state, production resources or persistent demo
data were changed. Only this review report is owned by the reviewer.

Implementation workers received both findings for fixes. Review closure remains
pending a delta-only pass over those fixes and their caller/test evidence.

## Scoped fix review: household reset admission

**Finding 1 closed.** Inspected the final `jobs_runtime.clear_data` delta: it
still clears the household's operational jobs but leaves active model leases
and spent attempts to the existing runtime release/expiry/retention owner.
The same callback is used for reset and deletion, so the fix applies at the
class boundary rather than only one HTTP route. Documentation explicitly
describes bounded retention of opaque household keys and numeric counters.

Ran the focused runtime reset/cleanup cases: **2 passed, 24 deselected**.
The new test proves reset cannot acquire another slot while the first is live,
and cannot replenish the daily allowance after the first is released. Existing
cross-household cleanup coverage passes. No new issue found in this fix delta.

Finding 2 remains open pending the shared total-deadline fix and caller review.

## Scoped fix review: total model deadline

**Finding 2 closed.** Inspected only the latest shared deadline, policy,
typed-lease and test delta, plus the two callers' existing timeout handling.
`RuntimePolicy` owns `model_call_seconds` and requires it to be shorter than
`model_lease_seconds`. Admission copies the selected duration into `ModelLease`;
the shared `model_admission` context enforces it through `anyio.fail_after`.
Timeout is recorded once and translated to `httpx.ReadTimeout`, preserving the
assistant's fixed `model_unavailable` result and deposit interpreter's fixed
`model_timeout` result. External cancellation remains separately counted.

Ran the focused runtime deadline, cancellation and reset tests:
**6 passed, 23 deselected**. The progressing fake provider is interrupted at
the short whole-call deadline despite repeated async progress; its reservation
is released, attempts/timeout equal one, active/cancelled equal zero. Policy
tests reject deadlines equal to or beyond the lease. Previously closed reset
protection remains green. No live model/network call was used.

No new reachable defect found in this fix delta. Both original admission
findings are resolved at their shared owners. Review is closed; unchanged
financial math and unrelated modules were not reopened. Only this report was
edited during the scoped review.
