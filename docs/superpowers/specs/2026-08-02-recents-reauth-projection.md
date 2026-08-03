# Recents reauthentication projection repair

Restore Recents visibility for an account's durable conversations after account
conversion or sign-in, without changing Omnisearch's already-correct retrieval
path.

Founder-locked 2026-08-02, after the locked S-01 checkpoint evidence found
durable conversations through Omnisearch that were absent from Recents.

## 1. Why

`docs/PRODUCT.md` names Recents/history as a supporting surface and requires
users to revisit prior conversations. A conversation that remains durable but
disappears from the primary continuity surface creates a "did I lose my work?"
moment and breaks that promise.

## 2. Locked decisions

1. Fix only the Recents projection, filtering, hydration, or ownership boundary
   proven responsible for the reauthentication/conversion failure.
2. Omnisearch remains unchanged as the confirmed safe retrieval path.
3. The repair must use canonical durable conversation ownership; it must not
   rebuild, migrate, duplicate, or mutate existing conversation records.
4. Add a regression test for the reauthentication/conversion scenario that
   proves a conversation discoverable by the account is also returned to
   Recents.
5. Keep the API and frontend contract aligned if diagnosis proves the boundary
   crosses it; do not introduce a client-only synthesized Recents row.

## 3. Reserved / parked scope

- Repairing historical accounts or running a production data reconciliation --
  excluded because the issue authorizes an isolated code fix, not a live-data
  mutation. Escalate if code-only behavior cannot restore visibility.
- Omnisearch ranking, retrieval, and UI -- excluded because it is the verified
  safe path and outside issue #342's no-touch boundary.
- Broader Guest conversion UX -- excluded unless the precise canonical owner
  mapping is necessary to make Recents correct.

## 4. Contract gates

- No contract-document, schema, or OpenAPI update is expected for a
  behavior-preserving projection repair.
- If diagnosis requires an endpoint shape, DTO, persistence-model, or migration
  change, stop and report before implementing it.

## 5. Execution contract

- **PR shape:** one focused PR, starting with this committed spec and followed
  by the smallest diagnosis-backed repair and regression test.
- **Proof required before the PR counts as ready:** focused backend and/or web
  regression tests covering the account conversion/reauth case; relevant type,
  lint, and contract checks; independent diff review; and browser QA if the
  repair changes visible client behavior beyond receiving corrected Recents
  data.
- **Where it stops:** a Draft PR targeting `codex/private-alpha-next`; the
  founder merges.

## 6. Stop conditions

- If visibility requires mutating, rebuilding, or reconciling live durable
  conversations, stop and report to the founder.
- If the smallest safe fix requires a migration, shared API redesign, or a
  change to Omnisearch, stop and report to the founder.
- If the reauthentication/conversion behavior cannot be reproduced with the
  existing deterministic test seams, report the missing proof boundary before
  broadening the lane.

## Sources

### Argus authority

- `docs/PRODUCT.md` -- Recents/history supports revisiting prior work.
- `docs/ARCHITECTURE.md` -- durable product records remain canonical.
- `docs/reports/2026-08-01-current-checkpoint-experience-feedback.md` -- locked
  S-01 observed Recents absence and successful Omnisearch retrieval.
- GitHub issue #342 -- accepted scope, no-touch Omnisearch boundary, and
  regression requirement.

### Inference

- The actual failing layer (API projection, client filter, hydration, or
  conversion ownership) is intentionally unproven until current-head diagnosis.
