# Lifecycle fence review

Date: 2026-09-21. Scope: the captain-designated lifecycle delta after
`f45609ee`, including the final frozen investing changes. This review inspected
the changed owners and their current callers directly; it performed no Git
operations, network calls or runtime edits.

**Terminal scoped verdict: CLEAN. No confirmed P1/P2 remains in this delta.**
The delayed assistant/deposit persistence defect is closed by the shared
transactional context fence. This is an explicit independent review closure for
the lifecycle change, not a new production or capacity qualification.

## Shared ownership and transaction boundary

- `common.active_context` is the owner of current user liveness, membership,
  role and household generation. `assert_active_context` compares the captured
  generation/authority and enforces the required role in the caller's existing
  transaction. HTTP authentication captures the fresh context; default
  generation zero is not used to reconstruct authenticated write authority
  after a reset.
- `identity_lifecycle.advance_household_generation` advances the monotonic
  household generation in the same write transaction as reset/private-household
  deletion. A failed clear rolls back both data and generation. The generation
  table is outside cleared product domains and survives reinitialization.
- Ordinary private mutation entry points in ledger, planning, services, credit,
  tax/estate, assistant, settings and identity check before writing or replaying
  a private receipt under `BEGIN IMMEDIATE`. The connection-level ledger helper
  is called through guarded ledger/planning write owners. Internal clear
  callbacks derive authorization from the guarded lifecycle transaction.

## Delayed operations and remaining call paths

- The assistant's final conversation/message/answer transaction checks the
  original request context after interpretation and fact gathering. A completed
  reset or deletion cannot be followed by reinsertion of the pending private
  question or answer. Notice, conversation and bulk-trash writes use the same
  fence with their existing viewer/editor/owner policies.
- HTTP deposit construction passes the captured context into
  `PlacementService`; confirmation, computation, save and notice writes check
  it inside their final transaction. Context-free service construction remains
  limited to the existing trusted local bootstrap/load/check workflow. Its
  decision rechecks read and write the still-existing records under one write
  transaction, so a reset cannot leave a later recheck recreating cleared rows.
- Job enqueue and model admission check the current context before reserving
  new work. Product clearing still preserves admitted model leases and spent
  attempts. The provider operation can finish, but the subsequent private
  domain write is rejected when its captured generation is stale.
- Final investing changes guard holding creation/edit/deletion, CSV preview
  and commit, order preview/confirmation, recurring-plan creation/edit and the
  manual recurring reservation. Checks precede receipt replay as well as new
  writes. Scheduled recurring work derives fresh authority through
  `active_context` in its reservation transaction and carries that generation
  through guarded preview/confirmation. Operational reconciliation updates
  existing run/plan rows; it does not recreate a plan or run removed by reset.

## Proportionality disposition

Current authority at commit is the permission contract. A temporary role change
followed by explicit restoration before commit does not require permanent
cancellation of every earlier command: the same user is currently authorized
and no reset/deletion generation was crossed. The captain explicitly clarified
this boundary. No additional authority-history revision or per-route machinery
is requested. A different current role, removed membership or deleted user
still rejects the captured write.

Ordinary logout deliberately does not cancel an already accepted private
write. Session revocation is not conflated with reset/deletion. This behavior
is covered by a focused test and matches the requested boundary.

## Verification

**46 focused tests passed** in two bounded runs:

- 41 lifecycle/generation/paused-write cases across common domain creation,
  identity, assistant, deposits and investing; 110 unrelated cases deselected.
- Five admission/reset/logout cases; 74 unrelated cases deselected.

The HTTP race tests pause a semantic assistant or deposit operation, acknowledge
reset/deletion/member removal/role change through another client, resume the
operation, and verify fixed 401/409 results with no reinserted private rows or
leaked model leases. Fresh requests after reset succeed. Other tests cover
generation rollback/persistence, minimum-role enforcement, ten stale investing
write/replay actions, and a scheduled recurring run using a fresh generation.
Only the existing Starlette/AnyIO test deprecation warning was emitted.

No broad financial-math review, provider measurement, capacity generation or
unrelated module review was performed. Only this report was written. The
reviewed lifecycle delta is closed with no further requested changes.
