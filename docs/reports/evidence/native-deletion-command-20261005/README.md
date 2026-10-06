# Native deletion command: source preparation

Status: local source candidate. No Swift package, app build, simulator, device,
provider, hosted, database or service checks have run for this candidate.

## Dependency and ownership

The immutable source base is `07f768f28be6f900b1a3d2e7b242bcdbad25d93a`, the native
Apple-name candidate. Dependency order is PR #864 (Apple session, including
`a24a` and integration `7d037`) → native Apple name → this command core → app
entry/confirmation/cleanup adapter. Root owns merge sequencing and Mac scheduling.
This candidate is not READY and must not be published as ready before its
prerequisites land and the affected checks run.

The existing SessionController and CredentialVault own the command, account
identity, epoch, proof and journal. A second deletion controller or credential
store was rejected because it would duplicate identity ownership. One token-free
vault envelope retains per-user commands, accepted acknowledgements and confirmed
local-cleanup obligations. The current SDK session remains the only proof owner.
The journal contains no JWT, refresh token or Apple code.

## Behavior

- Send one `POST /api/v1/account/delete` with `confirm: true` and, if supplied, one
  fresh ASCII Apple authorization code. Do not refresh, automatically retry,
  capture first, or sign in again to submit deletion.
- Journal uncertainty before transport. An interrupted command, lost response,
  malformed success or `503 account_deletion_incomplete` quarantines ordinary
  protected requests while keeping existing proof. Relaunch returns this state
  before any SDK refresh, profile fetch or Apple validation.
- Explicit same-command recovery uses only still-valid stored proof. Respect
  Retry-After. Expired/missing/refused proof offers support recovery, without an
  ordinary refresh. A refusal during earlier uncertainty keeps that uncertainty
  and bounded recovery metadata.
- Validate HTTP/body agreement. Only 200 `done` with an empty `pending` list proves
  completion. A 202 `in_progress` retires SDK proof and keeps a token-free per-user
  pending acknowledgement. It permits a later different account to sign in.
- Persist a confirmed exact-user cleanup obligation before retiring proof at 200.
  The initiating epoch is checked before issuing the receipt. Interruption of
  local credential removal can recover that receipt after relaunch/local removal,
  without another deletion POST. `accountDeletionStatuses()` derives readback from
  the same journal. A live SDK account suppresses confirmed-cleanup receipt
  delivery. The app acknowledges a receipt only after exact-user cleanup succeeds.

Minimal exhaustive adapter cases were required in ProfileAuthModel,
ConnectedCuadraoRoot and ProfileAccountSection. They use distinct uncertain and
pending states plus minimal EN/ES status strings. They do not add a deletion entry,
consequences, Apple UI, support action or receipt filesystem operation. Pending
copy makes no duration or automatic-operator promise. The recovered app UI owned
by Counsel must reconcile these small case additions through the root queue;
this source base still contains the earlier integration root.

## Verification prepared and performed

Synthetic test source covers validated completion, accepted proof retirement,
response loss and relaunch, protected-dispatch quarantine, request/body counts,
no refresh or capture, no Apple-code replay, Retry-After, fresh-authorization and
no-admission refusal classes, recovery refusal truth, malformed done, journal
write failure, interrupted local cleanup, account B after A acknowledgement,
stale snapshot/duplicate denial and expired proof.

`git diff --check` and Python modularity-budget checks pass on this source tree.
They do not verify Swift compilation or behavior. Swift/package/app and all
real-device/provider/hosted evidence remain unrun pending the root Mac grant.
An independent read-only source review found cleanup recovery, new-account entry
after 202, recovery refusal truth and an adoption race in the interruption
handlers. Those gaps were fixed. The final review of the moved mutation guards
and gated adoption test found no blocker. That verdict is source review only.

The settled command contract is captured in the captain's native deletion
mapping. Backend/API, server policy, migrations, obligation semantics, consent,
space policy, flags and configuration are unchanged by this candidate. No paid,
live, physical-phone, provider, database, service or hosted claim follows from it.

## Apple-name dependency reconciliation

Normal merge `e660fe9990b4a77779ba503b5cc3e3a9517dea70` reconciles current Name
head `a6efe6e3360f1c4e58c97807b91547de527b0b04` into the published deletion
source `e1a4fb2d055b6a6d06c0f360058bfb5e3878c6b2`. The original immutable
Name base remains `07f768f28be6f900b1a3d2e7b242bcdbad25d93a`. No rebase,
reset or stash was used.

The dependency delta has two affected files. Commit
`060a03f883f08fccdb613ee65343a8296a4793d7` renames the Apple XCTest fixture
property to `seedName`, avoiding the inherited XCTest property. Commit
`a6efe6e3360f1c4e58c97807b91547de527b0b04` moves Apple-name removal after
saving durable pending revocation proof in SessionController.

Semantic overlap exists in the shared session actor's retirement path, even
though Git reported no conflict. Source audit confirms that ordinary retirement
keeps pending proof before name cleanup can fail. Deletion uncertainty still
blocks that ordinary path; accepted 202 and confirmed 200 use the deletion
journal's separate fenced local retirement. The merge does not change the
CredentialVault deletion journal, deletion response parser, deletion test source,
completion receipts, minimal app case handling or localized strings. Independent
read-only affected-merge review at `e660fe999` found no concrete blocker.

The production delta against the current Name head remains this bounded deletion
slice: typed request/outcome parsing, journaled session command, protected-request
quarantine, per-user pending acknowledgements and completion cleanup receipts,
plus exhaustive app case handling and two EN/ES status strings. The dependency
merge adds no server, migration, flag, configuration or presentation expansion.

Diff and Python modularity checks pass on the merged tree. This preserves only
source/static review evidence. There was no deletion execution evidence to
retain or invalidate: package and app compilation/tests must run at the final
queued candidate head, including deletion tests and affected Apple-name/session
cases. Mac and database leases remain with the current verifier; no Swift, Mac,
Postgres, provider, hosted, activation or root environment work ran here. Root
still owns PR creation, landing order and all merge decisions.
