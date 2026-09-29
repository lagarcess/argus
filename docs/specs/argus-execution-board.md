# Argus private iPhone execution manifest

**Updated:** September 29, 2026.
**Execution state:** ACTIVE for the [personal money-recording batch](#personal-money-recording-batch). #745 and its #746 landing are complete. Signing, physical-phone installation, deployment and other MVEE implementation remain outside this authorization.
**Product owner:** [MVEE](argus-minimum-viable-ecosystem-experience.md).
**Authority and onboarding:** [DOCUMENTATION_AUTHORITY](../DOCUMENTATION_AUTHORITY.md).

**Original preservation authorization (historical):** The founder accepted this expanded plan for
commit and push on September 29, 2026. That grant authorized documentation preservation
only, not implementation, worker dispatch, merge, deployment or hosted changes.
Recovery branch: `codex/mvee-iphone-delivery-plan`.

## Personal money-recording batch

**Founder authorization, September 29, 2026:** Deliver received income, spending,
transfers between owned accounts, credit-card payments and purchase refunds as
one personal journey, including inspection, corrections and reconciliation with
existing balance checks. Own backend, database and iPhone through a runnable
simulator demonstration and a merge-ready PR. Publication and existing automatic
PR previews are authorized. Merge, deployment, signing, production changes,
paid-provider calls, web, imports, household and chat-runtime work are not.
Do not invent exchange rates or unresolved loan rules. The earlier loop's scoped
stop statements below are historical; this grant activates only the work here.

**Integration base:** freshly fetched
`b4fed10fe5cd325a7cd3e6ac21b87e9fbf5eb819` (#745 plus #746).
**Delivery branch:** `codex/personal-money-recording`.
**Goal:** a person uses the native app with the real local API/Postgres to receive
income, spend, move money between owned accounts, pay a card and record a refund;
Accounts and Home agree after inspection, corrections and reopening. Unknown
balances stay unknown, currencies stay separate, linked movements commit once
and together, and earlier activity respects each account's balance-check answers.

### Delivery ownership and throughput

The captain owns the shared contract decision, this manifest, assembled branch,
independent acceptance, publication and scoped review. One backend writer owns
recording domain/API/storage/migrations and API/data documentation. One native
writer owns Swift features, localized presentation and native tests. Writers use
separate branches; neither duplicates money rules or edits the other's surface.
A bounded design comparison precedes the shared contract. Native presentation
planning and local harness preparation can proceed alongside backend grounding;
wire-dependent implementation consumes the accepted contract. Integration and
simulator ownership are serialized by the captain.

The main risk is atomic paired corrections and purchase/refund limits under
concurrent writes, not account setup. Prove those with real Postgres before
calling the assembled journey complete. Reuse existing auth, preview tokens,
version checks, durable receipts and observation coverage. Preserve the previous
runnable demo and its synthetic database while preparing this slice.

### Acceptance and checkpoints

| User outcome | Inherit | Remaining delivery | Owner / real dependency | Observable proof |
| --- | --- | --- | --- | --- |
| Receive income and record spending | Account CRUD, expense preview/confirm, append-only correction/history | Typed income with optional source; connected recording and Home reads | Core and native; canonical activity contract | Native create/inspect/correct/reopen against real local DB; income does not become expense |
| Move money between owned accounts, including cash withdrawal | Signed balances, versioning, coverage | One atomic movement with linked legs and per-account review; same-currency validation | Core owns linked mutation; native consumes preview | Both accounts and Home agree; no spending/income; one-sided failure writes neither leg; duplicate retry writes once |
| Pay a credit card | Liability sign and credit-balance presentation | Payment from owned cash/bank to card, both sides correctable together | Same paired movement owner | Cash and debt change once; purchases remain the spending event; credit in favor stays explicit |
| Record money returned | Stable expense identity and category catalog | Linked partial/multiple refunds, actual destination, absent-purchase path and received-month reporting | Core owns purchase/refund cap and category; native review | Refund is separate from purchase and income; cumulative cap survives concurrent corrections; negative net spending remains visible |
| Reconcile and recover every supported activity | Immutable observations, explicit coverage, idempotency and session recovery | Multi-account coverage, revision consistency and native uncertain-write recovery | Shared core then assembled app | Existing check remains authoritative only for explicitly included activity; reopen, interrupted response and retry preserve one result; another identity sees nothing |
| Click through a complete local demo | Installed prior build, local stack and capture harness | Integrated build, short recording, restart recipe, durable evidence, CI and scoped review | Captain after component integration | Real simulator actions and DB readbacks; exact source provenance; merge-ready PR with zero unresolved findings |

Currency conversion and loan principal/interest allocation are not authorized.
The recorded peso/dollar transfer boundary remains blocked; a foreign-currency
refund uses the actual received amount with an explicitly unlinked purchase.
Existing technical limitations must remain visible and must not be relabeled as
founder-approved MVEE deferrals. The full MVEE coverage below remains the broader
assignment, not a claim that this slice completes the ecosystem.

### Execution checklist and decision trail

- [x] Read the Principles section of poteto-mode.
- [x] Phase A: Frame. Recover approved rules and the freshly fetched base; bind this bounded authorization and verification predicate.
- [x] Phase B: Design the workflow. Trace the inherited owners, compare contract shapes, record one accepted contract and isolated writers.
- [ ] Phase C: Run the loop. Implement and verify the core and native journey in bounded units, then integrate on this branch.
- [ ] Phase D: Keep the audit trail. Update this section with decisions, named owners, evidence and exact remaining work.
- [ ] Phase E: Verify and hand back. Deliver the runnable simulator, recording, restart instructions and merge-ready PR after CI and scoped review.

Current checkpoint: implementation is active in isolated core/native/demo branches.
The captain ran the inherited financial suite before changes: 71 passed, 18
Postgres-dependent cases skipped pending the new disposable database. These are
baseline component results, not acceptance of the new journey.

| Named owner | Branch / exclusive surfaces | Next usable result |
| --- | --- | --- |
| `money_core` | `codex/personal-money-core`, recording domain, API, additive migration, backend tests, API/data contracts | Commit exact shared wire contract first; implement all activity kinds and atomic correction/reconciliation |
| `money_iphone` | `codex/personal-money-iphone`, Swift feature/transport/models, localization and native tests | Durable uncertain-write recovery first; consume accepted contract for the complete recording editor/detail/Home |
| `money_demo_setup` | `codex/personal-money-demo`, isolated local launchers and restart setup | Separate synthetic stack on 585xx and dedicated simulator; preserve prior 584xx demo |
| Captain | `codex/personal-money-recording`, manifest, assembled source, independent proof and PR | Integrate verified components, click through and record the real local app, finish CI/review without merging |

Design decision, September 29: two code-grounded alternatives and an independent
cross-judge favored extending existing account records and exact-revision coverage
with an atomic activity group. Replacing the ledger or rebuilding coverage foreign
keys adds migration risk without a user benefit. Preserve old expense IDs and retry
receipts. Correcting an account selection retires the old leg with retained history
and applies the new leg in the same operation; do not edit one side independently.
A single owner-scoped activity transaction lock, taken before sorted account locks
by every new and legacy activity writer, serializes refund/correction invariants.
Account-only check/opening/metadata writers retain their existing account lock.
No SQL or native layer becomes a second financial rule owner.

The canonical native contract exposes one operation, all affected account effects,
per-account observation questions and a normalized reviewed request. Confirmation
binds the complete affected versions and exact request; idempotent replay precedes
stale-version rejection. A protected owner-scoped pending command survives native
process death and supports explicit same-key recovery. Monthly Home reporting uses
one explicit reporting zone and period, gross purchases/refunds/net spending and
received income; negative net spending remains visible. Refund categories follow
the linked purchase without rewriting historical provenance. Currency conversion
and loan allocation remain outside the assigned operation set.

Model the Domain shaped the typed activity group. Separate Before Serializing
Shared State shaped the isolated writers. Prove It Works requires both real
Postgres invariants and assembled simulator acceptance; passing component tests
alone will not close this batch. The exact wire and storage amendments live in
API_CONTRACT and DATA_MODEL, owned by the core writer, rather than another board.

## Landed financial-loop batch (historical authorization)

The founder authorized this batch on September 29, 2026 after PR #744 merged.
The restart covers implementation, local verification, simulator builds, device
preparation and coordination for the first financial loop only. The full MVEE
map below remains the recovery map; no other journey is activated by this grant.
Merges, signing/account actions, deployment, hosted mutations and spending still
require specific approval. Local implementation and simulator proof exist; signed
installation, hosted rollout and physical-phone proof remain outstanding.

**GitHub publication authorized:** The founder explicitly approved pushing
`codex/financial-loop-delivery`, opening its review PR, and completing CI and
scoped review, including its existing automatic Supabase preview. Physical-device
signing, installation, Render login and deployment are deferred. Keep the simulator/local-backend
demonstration runnable with retained synthetic data and restart instructions.

**Accepted local deliverable:** The founder made the complete loop
working in the simulator against the real local API/database the acceptance target
for PR #745, with a short recording, restart instructions and honest limitations.
That deliverable passed CI and scoped review, then merged under the later explicit
grant recorded below. Keep its demo runnable. Physical signing, installation and
deployment are deferred; this completion does not activate another MVEE journey.

**Overall delivery goal:** Deliver the loop defined under [full-scope execution and early demonstration](#full-scope-execution-and-early-demonstration)
on the founder's physical iPhone over the internet using the existing user when
those deferred actions are authorized.
Preserve the [locked design](../reports/mobile-design-lock-2026-09-28.md).
Simulator acceptance closes the current local deliverable, not the full MVEE or
physical-phone outcome. Unknown balances, corrections, reconciliation, retry, persistence and
identity isolation follow the linked canonical requirements and technical handoff.

**Base:** freshly fetched `fcbb70cc2899ca6a05c03c49316e9a4e4cbf5333`.
**Captain:** main delivery agent on `codex/financial-loop-delivery`.
**No-touch:** production web/remake, Android implementation, new MVEE pillars,
agentic runtime, billing/growth, hosted records/settings and unapproved providers.

| Responsibility | Exclusive implementation ownership | Checkout | Current action |
| --- | --- | --- | --- |
| Financial core (`loop_core`) | Recording domain, financial routers/repositories, financial migrations/tests, relevant API/data contract sections | `codex/financial-loop-core` in `financial-loop-core` | Source `c2425f2e2` includes reviewed timezone/type-lock corrections; 126 focused checks, including real local Postgres, pass on published delivery source; earlier exact HTTP/Home proof retained |
| iPhone (`loop_iphone`) | Native feature/session/navigation code, native tests and localized copy; excludes project/signing configuration | `codex/financial-loop-iphone` in `financial-loop-iphone`, recovered from preserved iOS checkpoint | Source `bbfb3bff` with archive evidence in `129d2c876`: three original actual API/Postgres journeys plus focused archive/restore pass; six model tests and 39 session tests pass; four environment-gated session tests explicitly skipped |
| Device preparation (`loop_device`) | iOS project/signing/configuration, local release setup, narrow existing-web CAPTCHA adapter and approval evidence; no feature Swift files | `codex/financial-loop-device` in `financial-loop-device` | Checkpoint `ea3370606` independently reviewed clean and assembled as `78ec38464` on delivery branch; signing and hosted approval remain pending |
| Captain and independent acceptance | This manifest, contract synthesis, integration candidate and cross-owner verification | `5a42` | PR #745 landed; [landing result](https://github.com/lagarcess/argus/pull/745#issuecomment-5889046424) owns final integration verification status; retain runnable local demonstration; signing, Render login and deployment deferred |

### PR #745 integration landing

The founder authorized merging only approved head
`944b2cb70ab008aa2ed9385b5d81555bad84f7fd` while its checks remained green.
[PR #745](https://github.com/lagarcess/argus/pull/745) squash-merged on September
29, 2026 at 10:57:30 UTC as `afc3db5ae679a32676fae94ed7c5e9c9ef68b633`, onto
`fcbb70cc2899ca6a05c03c49316e9a4e4cbf5333`. Integration had not advanced; no
reconciliation merge or intervening semantic overlap existed. The merge tree
exactly matches the approved PR tree, preserving accepted evidence.

The [terminal PR audit](https://github.com/lagarcess/argus/pull/745#issuecomment-5888571700)
records green PR/push CI and smoke, the final clean scoped Codex review, zero
unresolved threads, source equivalence, runnable demo and limitations. Post-merge
[integration CI](https://github.com/lagarcess/argus/actions/runs/36558771357) and
[smoke](https://github.com/lagarcess/argus/actions/runs/36558771345) passed at the
exact merge SHA. The [landing comment](https://github.com/lagarcess/argus/pull/745#issuecomment-5889046424)
records final documentation publication and integration parity after #746.

No linked issues require closure. The configuration audit found no new production
environment variable: the existing financial flag stays default-off in
`.env.example`; the CAPTCHA adapter reuses the existing public Turnstile key;
device signing has its checked-in, unpopulated `Device.local.xcconfig.example`;
local XCTest controls come from the private fixture launcher. No ignored env file,
hosted configuration, production data, or deployment was changed. Existing core
and native worktrees remain owned by the runnable local demo and are preserved.

The local simulator deliverable is complete. The physical-iPhone internet outcome
and remaining MVEE coverage below are not completed or activated by this landing.

### PR #745 review checkpoint (pre-merge evidence)

[Review PR #745](https://github.com/lagarcess/argus/pull/745) was reviewed against
`codex/private-alpha-next`. Original reviewed head `b5cfedef998079f3978f9282e60bc287afa7dc25`
passed [CI](https://github.com/lagarcess/argus/actions/runs/36549243112) and
[local smoke](https://github.com/lagarcess/argus/actions/runs/36549243153).
At review time the original and freshly fetched integration base was `fcbb70cc2`;
no reconciliation merge or intervening integration overlap existed.

The first Codex review found three confirmed defects. Each has a thumbs-up and
an evidence-backed reply. All fixes below were published in `6d3f8e066`; this
documentation follow-up changes no product/test source. The linked terminal audit
records final green CI, resolution of all three threads and the clean scoped
review on approved head `944b2cb70`. Those publication/review steps are complete.

| Finding | Published correction and verification | Delivery commit |
| --- | --- | --- |
| Balance timestamps used the opening's timezone regardless of source | Canonical position retains its source revision's IANA zone; Home orders freshness by UTC instant, including repeated DST hours. Memory and real-Postgres regressions cover preview/save/reopen | `71ea905a7` from core `c2425f2e2` |
| Account type remained editable after a check without expenses | Existing type lock includes balance checks/value updates; opening-only behavior preserved | `71ea905a7` |
| Archived accounts remained in the active list | Active list filters archived rows; Manage accounts retains Active/Archived groups and existing Restore. Six model checks and one real-API simulator archive/restore journey passed, with unchanged Home and same record ID | `632ea5f49`, `08254e668`; [visual/behavior evidence](../reports/evidence/financial-loop/ios/archive-review.md) in `abd955f3c` |

The assembled local correction candidate `08254e668` passed 126 focused backend
checks including real Postgres, full Ruff and modularity checks. The original
financial-loop evidence remains historical at its recorded sources; the changed
timezone/type-lock and account-list surfaces have the focused replacement proof
above. At published head `6d3f8e066`, all 126 backend checks and all six native model
tests passed again. Modularity passed against the current integration descendant;
product/test source is unchanged from `08254e668`. Native sources match `bbfb3bff`
and financial sources match `c2425f2e2`, explicitly revalidating the focused
simulator and source-timezone/type-lock evidence for the published candidate.

**Preview cleanup and publication authorization:** the founder authorized
verification, removal of only PR #745's disposable preview, and disabling
automatic previews only for this PR. CLI and connected Supabase branch inventories
confirmed a real environment, not a skipped-preview notice: branch
`4d58c555-c26d-4a51-bdfb-c1765042aca3`, preview project
`yjuknxqpmgddgswvtgwk`, git branch `codex/financial-loop-delivery`, PR `745`,
non-default, non-persistent, and created without production data.

The existing integration checkout's environment credential authenticated CLI
reads, but CLI deletion lacked `branching_development_delete`. The connected
Supabase tool successfully deleted that exact branch. A fresh inventory confirmed
only the unchanged default branch remains on existing project
`lgdhvepyrzbnscqssgqq`. No new token, other branch deletion, main-project mutation,
or integration-setting change was made.

After reviewing the expected cost and isolation, the founder explicitly authorized
PR #745's existing automatic Supabase preview as a side effect of publishing its
fixes. The publication blocker is resolved. Preserve Automatic branching and all
other integration settings. No further infrastructure investigation, production
changes or application deployment is authorized. No new token is needed.

The fixes were published, exact-head CI passed, the addressed threads were
resolved and the scoped recheck returned clean before the founder approved the
merge. Do not repeat those completed steps. Preview status is automation evidence,
not application delivery or physical-phone acceptance. The broader MVEE and
deferred physical-phone work retain their existing authority boundaries.

**Runnable local demonstration:** the retained database and synthetic identities
are running again. Native `bbfb3bff` and core `c2425f2e2` are the locally verified
review corrections. Keep the owned API 58400, CAPTCHA 58405 and Supabase/Postgres
58401/58402 alive for founder use; restart instructions are in the
[evidence README](../reports/evidence/financial-loop/ios/README.md#reproduce-and-resume).
No physical-iPhone, signing, Render login or deployment work is active.

Throughput checkpoint: three implementation responsibilities, one financial
contract owner and one integration owner. Device access must not block local
financial/native work. CPU-heavy Xcode and database suites use separate owners;
shared simulator control is exclusive to the native owner until handed to QA.
The first stop requiring the founder is a concrete signing or hosted action,
not a routine engineering decision. Physical-phone completion remains unverified;
it is deferred beyond this explicitly authorized local review deliverable.

The execution checklist adapts poteto's figure-it-out workflow into this existing
manifest rather than creating another board.

- [x] Read the Principles section of the poteto-mode skill.
- [x] Phase A: Frame. Scope and authority recorded above.
- [x] Phase B: Design the workflow. Trace existing owners and settle the consumed contract.
- [x] Phase C: Run the loop. Implement and verify the complete authorized local simulator loop.
- [x] Recover the native baseline and capture locked-reference comparisons.
- [x] Implement durable activity, corrections, reconciliation and shared reads.
- [x] Connect the native loop and verify it against a local API/database.
- [ ] Prepare signing/install and exact hosted rollout actions for approval.
- [ ] Verify the approved installed candidate on the physical phone over the internet.
- [x] Phase D: Keep the audit trail. Record decisions and evidence here as work advances.
- [x] Phase E: Verify and hand back the authorized local simulator deliverable, recording, restart instructions and limitations. Phone acceptance remains deferred above.

### Historical implementation checkpoints

The following records describe intermediate states before #745 landed. Their
publication, process and integration statuses are historical, not current work
instructions; the landing checkpoint above owns current status.

- Restart uses three isolated writers and recovers the preserved iOS lineage.
  The fetched base and recovery checkpoint above identify their source. The
  native baseline builds and runs but still shows fixtures.
- Financial design extends the existing record/revision graph and one domain
  projection. Explicit inclusion decisions cover opening/check boundaries;
  immutable check confirmation facts remain separate from current residuals.
  The financial owner records the consumed wire contract in API_CONTRACT and
  data shape in DATA_MODEL before client integration.
- A dedicated existing-web `/auth/native-captcha` adapter may reuse the current
  challenge owner for native login. It contains no password or session state.
  This is a required auth connection, not web remake work. Its deployment still
  requires approval.
- Read-only access inventory found no valid local signing identity, a known
  but unavailable iPhone 15, and an expired Render CLI session. The existing
  Supabase project is healthy on its current Free plan; its applied migration
  inventory does not yet include the financial-account migration. Founder
  access work is now explicitly deferred. No hosted mutation or provisioning occurred.
- The consumed API contract is committed on the financial branch in
  `ee77772c9` and amended in `0de85dca`. Home aggregates use exact decimal-integer
  strings; one backend projection owns totals and ownership-share rounding.
  Native clients format those values without recomputing financial rules.
- Device checkpoint `ea3370606` is published for review. Its proof uses an
  unsigned build and synthetic local CAPTCHA responses. It does not establish
  production login, a signed installation, or physical-phone acceptance.
- Captain independently ran the core's local HTTP verification script against
  synthetic Auth and Postgres: expense, correction, check, late included expense,
  retry after intervening writes, unknown balance, second-owner refusal and
  reopened read passed. That provisional run was superseded by the final-source
  HTTP/Home proof and native simulator evidence recorded below.
- Automatic approval review blocked the native worker's combined commit/push
  because remote publication was treated as a reserved hosted change. Neither
  command ran. The worker subsequently committed locally. The founder later
  explicitly approved publication of the assembled delivery branch and its
  review PR, resolving that publication blocker only. Previously published
  device and captain checkpoints were preserved; no PR/integration merge had
  occurred at that checkpoint. The subsequent #745 merge is recorded above.
- Financial checkpoint `92020058d` passed independent review after fixes for
  stale metadata planning and native uppercase UUIDs. The captain reran the
  complete HTTP loop on a separate synthetic identity, including exact Home
  position/spending deltas after each write and replay. The five core commits
  are assembled locally; [component evidence](../reports/evidence/financial-loop/core-verification.json)
  records the source and limits. The owned local API/database supported native
  acceptance and were then stopped with their data retained. Integration was
  fetched again and remains `fcbb70cc2`.
- Native checkpoint `d5299f65` passed three real local API/Postgres simulator
  journeys: unknown balance through spending and an explicitly reviewed opening;
  known balance through expense, correction, check, included late expense and
  reopen; and Spanish Home/check review. Numeric Home deltas and foreground
  recovery are asserted. Session tests executed 39 passes with four explicit
  environment skips; five tests compile and exercise the actual native models.
  Independent review is clean after fixing expired-session recovery, editable
  inclusion review, and the foreground auth race that blocked Home refreshes.
- The captain assembled device, core and native source at `ba69fecd6`, reran
  108 backend checks and the modularity budget (all pass), and compiled the full
  app for generic physical iOS with signing disabled. The temporary unsigned
  device override was removed. Native feature/test sources match `d5299f65`;
  only the reviewed opt-in device configuration and setup documentation differ.
  Home, entry, check-review and reopened-account captures were compared with
  the locked visual reference. This supports local visual acceptance, not
  physical-device fidelity or internet completion.
- Post-merge integration CI and release smoke are green for exact integration
  `fcbb70cc2899ca6a05c03c49316e9a4e4cbf5333`:
  [CI](https://github.com/lagarcess/argus/actions/runs/36537496516) and
  [smoke](https://github.com/lagarcess/argus/actions/runs/36537496519).
  These results do not cover the unpublished implementation candidate.
- [Simulator demonstration and acceptance evidence](../reports/evidence/financial-loop/ios/README.md)
  were assembled in evidence-only commit `9b94c65c3`, preserving the tested
  application source. The recording, seven captures and sanitized XCTest results
  are committed locally and included in the authorized review publication.
  The evidence README records the exact existing-stack restart commands. All
  worker-owned build/recording/API/database processes are stopped; synthetic data,
  fixtures, worktrees and the installed simulator app are preserved. Writers and
  independent reviewers have completed their assigned local work. The captain
  retains signing, hosted compatibility, publication and physical acceptance.

### Financial-loop landing handoff

The locally verified loop is merged through #745. Keep its
simulator/local-backend demonstration runnable. PR #746 carries the
founder-authorized landing documentation; the [landing result](https://github.com/lagarcess/argus/pull/745#issuecomment-5889046424)
records its publication and final verification. This record does not assign a
repeat landing or another implementation batch. Physical-device signing,
Render login and deployment are explicitly deferred. No functionality on the
founder's phone is yet proved by this batch. When those actions are resumed, the
[device preparation evidence](../reports/financial-loop-device-preparation.md)
identifies the access needed; actual deployed API/web SHAs are required before fixing
the minimal deployment candidate. Account and loop migrations are
`20260928200000_financial_accounts_first_slice.sql` and
`20260929090000_financial_loop.sql`; neither is approved for application to the
production project. The earlier isolated automatic-preview grant is recorded above.


## Outcome and completion

The founder can use the agreed financial ecosystem on a physical iPhone, with
an existing account and real persistent data over the internet, away from the
Mac, and hand the phone to someone to demonstrate it. Public App Store release
is not required. The [MVEE private-delivery boundary](argus-minimum-viable-ecosystem-experience.md#12-private-iphone-delivery-the-immediate-finish-line)
explicitly defers the agentic runtime. That exception does not remove household,
planning, document intake, recovery or other agreed financial capabilities.
Full agent-first completion later adds every supported action through text and
voice. Capture/playback alone does not prove voice actions.

This is the single execution map and progress board. It replaces the unpublished
September 28 weekly-board draft. Do not create parallel manifest, roadmap and
status documents with copied requirements. The MVEE owns requirements; this file
owns sequencing and checkpoints; PRs, CI and acceptance artifacts own evidence.
A release manifest under `docs/release-manifests/` remains the evidence for one
specific deployment, not a competing product plan.

The founder assigns the full MVEE private iPhone outcome to this delivery captain.
The full-scope execution proposal below remains recorded. The completed restart
covered only the first local financial loop; additional MVEE work remains stopped. Record named owners and each consumed technical contract
before implementation of that dependency. Routine progression does not require
new batch approvals. No 24-hour delivery promise has been made.

## Verified starting point

This is the historical baseline before #745; current landed status is above.
The financial-loop batch started from integration
`fcbb70cc2899ca6a05c03c49316e9a4e4cbf5333`, the #744 merge. Its exact-commit
[CI](https://github.com/lagarcess/argus/actions/runs/36537496516) and
[Private Alpha Local Smoke](https://github.com/lagarcess/argus/actions/runs/36537496519)
were refreshed on September 29 and both succeeded. The earlier planning snapshot
used `12bccd4d6e173a5d8805e495fd30b7ead36741c6`, the #743 merge. The original
publication inspected `de8729843b726a3fd03210cebcedede5e44227c8`.
The account product commit is `296195e86c972e846c251d256b3cc211975bfd57`.
GitHub merge/closure state and the linked repository documents were inspected.
Existing production behavior is documented, not freshly exercised on a hosted
service in this publication. No private iPhone completion is claimed.

Post-merge [CI](https://github.com/lagarcess/argus/actions/runs/36528607001)
and [Private Alpha Local Smoke](https://github.com/lagarcess/argus/actions/runs/36528606830)
both completed successfully at `12bccd4d6`. These checks do not establish hosted
or physical-phone acceptance. Local commit `44dd019f908024ff0a7733091ca1d37edf6d529f`
remains preserved by `codex/preserved-pr743-landing`; its landing-ledger entry is
carried into this documentation change without restarting its publication work.

| Existing work | Evidence and scope | What it does not establish |
| --- | --- | --- |
| Existing Argus | [PRODUCT](../PRODUCT.md), [ARCHITECTURE](../ARCHITECTURE.md), [API_CONTRACT](../API_CONTRACT.md) describe chat, auth, calculations, research, simulations, history, search and settings to inherit | Native feature parity or current hosted acceptance of the pivot |
| Design lock | [#727](https://github.com/lagarcess/argus/pull/727) merged; [mobile reference](../reports/mobile-design-lock-2026-09-28.md) | Implemented financial flows; newer MVEE tester corrections take precedence |
| Native shells | [#729](https://github.com/lagarcess/argus/pull/729), [#730](https://github.com/lagarcess/argus/pull/730) merged; [iPhone setup](../../ios/README.md), [Android setup](../../mobile/android/README.md) | Real finances, production app identity or installation on the founder's iPhone |
| Native auth | [#738](https://github.com/lagarcess/argus/pull/738), [#739](https://github.com/lagarcess/argus/pull/739) and their landing records merged; [iPhone auth](../../ios/AUTH_SETUP.md) | Complete hosted registration, recovery links or private device distribution |
| Financial accounts | [#735](https://github.com/lagarcess/argus/pull/735) and [#742](https://github.com/lagarcess/argus/pull/742) merged; [scope](lanes/financial-accounts-first-slice.md), [API/Postgres evidence](../reports/evidence/financial-accounts-first-slice/README.md) | Full financial activity, plans, totals or completed client delivery. Feature remains default-off in its contract |
| Charts | [#733](https://github.com/lagarcess/argus/pull/733) merged as a prototype | Connected financial charts or resolved Android performance/dependency limitations |
| Web preview | [#732](https://github.com/lagarcess/argus/pull/732) open on visual hold | Adoption. All remake work is frozen |
| Research/proofs | [#723](https://github.com/lagarcess/argus/pull/723), [#724](https://github.com/lagarcess/argus/pull/724), [#725](https://github.com/lagarcess/argus/pull/725), [#726](https://github.com/lagarcess/argus/pull/726) closed unmerged | Live work queues. Carry useful evidence selectively; do not restart their review loops |

Stopped client work must be inspected and salvaged before replacement work is
assigned. These recovery checkpoints are not accepted deliveries. Remote
preservation is identified per row; retain worktrees and local-only artifacts.

| Branch | Last inspected commit | State at stop |
| --- | --- | --- |
| `codex/ios-financial-accounts` | `671ee6b0ff24115232eaac9204fd03da3b5cd55d` (remote checkpoint) | Unfinished client source and [recovery note with verification limits](https://github.com/lagarcess/argus/blob/671ee6b0ff24115232eaac9204fd03da3b5cd55d/docs/reports/evidence/ios-financial-accounts/README.md) preserved remotely; worktree and ignored local state retained. Native build/UI acceptance unverified; known form defects, missing setup guide and prior build approval rejection remain unresolved. No implementation PR; implementation stopped |
| `codex/android-financial-accounts` | `fb6e4d9455aec7abbf0d16d74e00be896804d472` (remote checkpoint) | Implementation remains `3aed3d2266f8ed5a31c87b8083ef114a33d905cd`; preservation commit publishes [recovery note and 16 synthetic screenshots](https://github.com/lagarcess/argus/blob/fb6e4d9455aec7abbf0d16d74e00be896804d472/docs/reports/evidence/android-financial-accounts/README.md). Worktree retained. Final restart proof, integration reconciliation, PR delivery, CI and terminal review incomplete; implementation stopped |
| `codex/web-financial-accounts` | `1b0c80d208ad6e73409c72ccba13407fbfb2ee34` | Spec commit plus uncommitted client work. Preserve only; no continuation now |

A replacement coordinator must locate the branches and working changes before
using those pointers. Missing local artifacts are a recovery issue, not evidence
that their work landed. Do not copy secrets or real user data into handoffs.

### Recovery refresh for the proposed restart

Both mobile remote branches were fetched again on September 29 and still point
to the checkpoints above. Read-only source inspection found the following.

- The iPhone checkpoint contains account creation, list/detail, metadata editing,
  opening corrections/history, archive/restore, localization and typed API calls
  through the existing session owner. Preserve this implementation. Its recorded
  worktree at `/Users/garces/.codex/worktrees/8be2/private-alpha-next` is now absent.
  Committed source remains recoverable; ignored local state has not been located.
- The iPhone source has concrete draft-freeze, local-validation/error handling and
  signed-amount entry gaps. Its historical package/API checks do not prove that
  the native app builds or works. The account setup guide is missing.
- The Android worktree at `/Users/garces/.codex/worktrees/611c/private-alpha-next`
  exists and is clean at `fb6e4d945`. Its retry/reconciliation implementation and
  synthetic evidence are useful references. Android implementation stays stopped.
- [iPhone configuration](../../ios/Config/Development.xcconfig) is simulator-only,
  uses a placeholder bundle identity and disables auth. Xcode is installed, but
  local inspection found zero valid signing identities. Apple membership, team
  access and a usable private installation route have not been established.
- [Existing auth](../../ios/AUTH_SETUP.md) provides reusable registered sessions,
  refresh and Keychain storage. Production CAPTCHA bridging and remaining access
  flows need work. Existing browser recovery is reusable. A successful first
  login cannot close the full D01 acceptance list.
- Hosted API revision, applied financial-account migration, feature flag and
  available capacity remain unverified. Checked-in Render configuration is not
  a hosted readback. No hosted settings, real account records or providers were
  changed during this recovery.

The recovery agents were read-only investigators, not implementation owners.
Confirm prior worker ownership and process state before assigning a writer.

## Reconciliation findings for founder review

The planning update corrects these omissions without changing MVEE scope.

- The published manifest proposed D01/D02 first and D03 contract preparation.
  That is too narrow for this assignment. The full coverage map now governs;
  D01-D05's first financial loop is only the first demonstration.
- Earlier dependencies could read as requiring completed upstream pillars.
  The plan now identifies the specific consumed contracts so independent work
  can proceed. Signing does not block finance; posting does not block previews.
- Native quality, charts, Temporary chat and profile controls were implicit in
  broad D rows. The work map now links these source areas to delivery owners and evidence.
- Native auth is reusable, but the current shell's financial destinations are
  samples. No source claim, old screenshot or merged PR is phone acceptance.
- The iOS recovery row describes the historical stop. Its once-retained worktree
  is now missing; the recovery refresh above is the current observation.
- MVEE section 1.2 explicitly defers the ecosystem runtime despite sections 4
  and 6 describing typed/spoken financial actions. D14 preserves that named
  exception only. Dictation/spoken conversation, permitted financial questions,
  household, ingestion and manual planning remain delivery work.
- Technical policy gaps are not deferrals. File, audio and recovery retention,
  household departure and notification choices now have owners and decisions
  below. The captain may not silently move them outside private delivery.

### Current code inheritance anchors

These sources support the coverage table's reuse claims. They are code/contract
inspection, not a new hosted verification.

- [Native shell](../../ios/ArgusFoundation/FoundationShell.swift) selects
  [sample destinations](../../ios/ArgusFoundation/SampleDestinations.swift).
  [SessionController](../../ios/Packages/ArgusSession/Sources/ArgusSession/SessionController.swift)
  and [auth setup](../../ios/AUTH_SETUP.md) own the reusable session boundary.
- [Financial service](../../src/argus/domain/recording/service.py),
  [balance read](../../src/argus/domain/recording/records.py) and
  [account router](../../src/argus/api/routers/financial_accounts.py) implement
  openings/accounts only. The database migration is
  [the landed first slice](../../supabase/migrations/20260928200000_financial_accounts_first_slice.sql).
  It is not an activity ledger, household or planning implementation.
- [Agent API](../../src/argus/api/routers/agent.py),
  [conversation API](../../src/argus/api/routers/conversations.py),
  [search API](../../src/argus/api/routers/search.py),
  [profile API](../../src/argus/api/routers/profile.py) and
  [personalization API](../../src/argus/api/routers/personalization_memory.py)
  anchor inherited services. Existing web settings are behavioral references,
  not permission to resume the web remake.
- [Architecture voice/chart direction](../ARCHITECTURE.md#voice-and-chart-direction)
  selects xAI and Swift Charts. It does not supply implemented production voice,
  financial chart series or provider/spending authority. Existing notification
  availability in PRODUCT is not proof of an ecosystem inbox or scheduler.

## Full-scope execution and early demonstration

**The local first-loop deliverable landed through #745; the current handoff above
owns the remaining authorization.** The full-scope proposal's first usable
outcome is a complete financial loop on the physical iPhone over the internet,
using the founder's existing user. Establish an account balance, record an
expense, see Accounts and Home reflect it, correct it, reconcile a checked
balance without double-counting, and reopen the app with everything preserved.
Unknown balances remain unknown. This spans D01/D02, D03 and D05; account CRUD
and installed login are intermediate checkpoints. This loop is an early
demonstration within the full assignment, not the ecosystem finish line.

Run three connected responsibilities in parallel. Names, exclusive paths,
branch/worktree and owner acceptance are filled at dispatch after restart.
The roles below are not live assignments. Independent acceptance accompanies
the assembled loop throughout implementation.

| Responsibility | First demonstration contribution | Ownership boundary |
| --- | --- | --- |
| Device and hosted access owner | Signing, installation, existing-user authentication integration and the minimum compatible deployment, including backup/restore verification and rollback | Own signing/project configuration, deployment files and the narrow hosted auth bridge. The iPhone owner writes session/UI code against the agreed auth contract. No replacement web work or new paid infrastructure |
| Financial backend owner | Implement durable expense activity, corrections, balance reconciliation and canonical account/Home reads; resolve API/data contracts and additive migrations within this implementation | One owner for financial contracts, posting, money rules, reconciliation and their backend tests/migrations. No competing ledger or standalone research/proof deliverable |
| iPhone experience owner | Recover the preserved client and connect Accounts, recording, corrections, balance checks and Home to the shared contracts; preserve the locked design | Own native feature, session and navigation code; exclude signing/project files assigned to the device owner. Reconcile current integration by merge, never rebase the evidenced branch |

The delivery captain owns this manifest, cross-owner decisions and integration
sequencing. Domain owners remain accountable until their assigned journey is
verified in the assembled app; a component handoff does not close the outcome.
An independent acceptance owner exercises each integrated increment and returns
defects to its writer. Separate test/evidence files prevent competing edits.

### Deliver the early demonstration while full-scope work progresses

1. Recover iPhone source and locate or account for missing local configuration.
   Inspect previous worker/process ownership. Record the fresh integration base,
   exclusive worktree, allowed files, commands and stop conditions before dispatch.
2. Start device access, backend implementation and native experience together.
   Resolve signing/team access and the shortest supported private installation
   route while the financial owner defines and implements the shared write/read
   contract. Agree each consumed contract before wiring its client; do not wait
   for a separate research project or all financial contracts to finish.
3. Install the connected shell as soon as its auth path is ready, with a stable
   app identity and update path. Demonstrate existing-user login and reopening
   away from the Mac. Backend and native financial work continue while device
   access is blocked. Simulator/local evidence is intermediate, not acceptance.
4. Integrate balance establishment, expense recording, Home/account reads,
   correction and reconciliation as working increments of the same loop. The
   backend owns arithmetic and financial facts. Clients render canonical reads.
   Verify exact money, unknown/zero distinction, atomic writes, identity isolation,
   retry idempotency, stale-edit handling and persistence as each increment lands.
5. Prepare one concrete hosted approval packet. Name the candidate SHA, current
   deployed revision, existing Supabase project, migration status, exact settings,
   production-web compatibility, backup/restore evidence and rollback. Prefer
   existing compatible Render capacity; justify any alternative and its cost.
   Use an auth-only release first if it speeds installation, without pausing
   backend or native financial implementation behind that release.
6. After the required signing/install and hosted grants, exercise the full loop
   using deliberate founder-entered records on the physical phone. Close and
   reopen the app, interrupt a write and retry, and verify Accounts/Home agreement.
   Use authorized test identities for isolation; redact committed evidence.
7. Replay the existing [balance handoff](argus-account-balance-reconciliation-handoff.md)
   cases on the assembled candidate. Compare observed results to that source and
   record the source revision with the phone/database evidence.

Do not wait for every registration, confirmation/resend, recovery/reset, guest
return-to-action or account-management case before advancing this loop. Keep
security and money correctness necessary for the connected path mandatory.
Sequence remaining access/account completeness and other D03/D05 acceptance in
the work map; accepting this loop does not mark those entire rows accepted.

Prepare builds, tests, source changes, draft PRs and the deployment packet under
the restart grant. Merges, deployment, hosted mutations, signing/account access
and paid-provider use require explicit authority. A routine build or scoped bug
fix does not need a repeated restart question. No paid model run is needed for
this manual financial loop. Do not bypass an earlier denied action through a VM
or another agent; request the correctly scoped access when needed.

### Allocate resources to accepted dependencies

Keep the iPhone writer and physical-device verification on an authorized Mac.
Use available VMs for isolated backend/Postgres tests and contract verification
when an assignment benefits from them. Direct VM coordination is not configured;
establish an authorized channel before promising unattended remote ownership.
Additional capacity earns a lane only when it has independent files, accepted
inputs and an observable user outcome. Keep one writer for each shared iPhone file and one financial-domain owner even
when more machines are available. Independent feature modules can have separate
writers under the team allocation below.

During execution, inspect active agents at completion, dependency changes and
at least every 30 minutes. Check actual process/build/commit/test evidence.
Re-scope stalled work, preserve unique changes and stop the old writer before
replacement. Do not retry an unchanged failure indefinitely. Publish useful
branch checkpoints so a lost VM does not erase work. No scheduler is armed by
this proposal.

Show a short interaction recording or live demonstration at first installation,
first recorded expense reflected on Home, correction/reconciliation and each
added connected journey. Include relaunch and a
failure/recovery case, not screenshots alone. Record build number, app SHA,
backend revision, environment, evidence and remaining gaps in this manifest.
Check concise copy, icons, locked navigation and native interaction quality
before repeating a pattern across screens.

## Work map

### Complete MVEE coverage

The [MVEE scope checklist](argus-minimum-viable-ecosystem-experience.md#13-complete-scope-checklist)
is the requirement index. Read each linked source for the user outcome and its
expected behavior; this table stores execution metadata only. D01-D15 are work
identifiers, not a second specification. A row's next integration task and planned
evidence are not an exhaustive scope or a substitute for the linked requirement.

**Current phone evidence:** none of the assembled outcomes is verified on the
founder's physical iPhone. Reuse and gaps below are the September 29 inspection
snapshot. Only work required by the active financial-loop batch is restarted. Proposed owners
must be bound to named workers at dispatch. D14 follows the linked runtime
sequence rather than a separate deferral policy in this document.

| Canonical user outcome / work ID | Inspected reuse | Next integration task | Proposed owner | Execution dependencies | Evidence to collect against the linked source |
| --- | --- | --- | --- | --- | --- |
| [Access][mvee-access], D01 | Argus auth/recovery; Swift session/Keychain | Finish native/hosted auth adapter and guest conversion | Native continuity + Device/release | Identity API; signing/hosted access for phone proof | Physical-device auth recordings and session/identity test results |
| [iPhone experience][mvee-platforms], D15 | Native shell; localization; design archive | Replace sample destinations with connected modules | Native continuity | Domain reads per destination | Device navigation/accessibility recordings against [native quality][mvee-quality] |
| [Accounts and assets][mvee-accounts], D02/D04 | Landed account/opening backend; unfinished iOS client | Recover account client and extend saved-item data model | Financial core | Existing account contract; D03 history; D07 for sharing | Device lifecycle recordings and persisted account/asset readbacks |
| [Activity][mvee-activity] and [refunds][mvee-refunds], D03 | Recording domain currently supports openings only | Implement posting and connect native entry/history clients | Financial core | Account identity; shared posting contract | Device entry/correction recordings plus atomicity, retry and concurrency tests |
| [Reconciliation][mvee-activity], D03 | Opening revisions; [handoff cases](argus-account-balance-reconciliation-handoff.md) | Implement observation lineage and balance reads with posting | Financial core | Account/activity identity | Replay the handoff cases on the candidate; retain before/after reads and relaunch evidence |
| [Home][mvee-home], D05 | Locked design; account facts; chart prototype | Connect Home's read model and domain destinations | Planning/Home | D02/D03 position; D06 forecasts; D04/D07 contexts; D08 resume | Phone walkthrough with source-record/read-model comparisons |
| [Plan][mvee-plan], D06 | Existing calculators; locked plan design | Implement plan persistence and actual-activity adapters | Planning/Home | Financial posting/link contract; D07 for shared variants | Device plan lifecycle recordings and linked-record/forecast readbacks |
| [Spaces][mvee-spaces] and [account moves][mvee-moves], D04 | Personal default in account model; design reference | Implement space lifecycle and account-move service | Financial core | Account identity; affected domain links | Device move/recovery recordings and linked-record identity checks |
| [Household][mvee-household], D07 | Existing identities; selected invitation direction | Implement membership, permission adapters and invitation delivery | Household | Identities; affected domain adapters; open policy decisions | Two-user device journeys and permission readbacks across consumers |
| [Intake][mvee-intake], D08/D03/D13/D14 | Manual account entry; synthetic review/retry kit | Build production source/review pipeline and shared posting adapter | Intake | File/provider policy; D03 confirmation; D07 shared sources; D14 language actions | Authorized sample corpus runs, source-preview recordings and interrupted-import readbacks |
| [Argus][mvee-argus], D09 | Existing runtime/SSE/tools and persisted artifacts | Connect native conversation client and authorized context adapters | Conversation/voice | Existing APIs; relevant domain reads; live-provider authority | Phone conversation replay and persisted artifact/evidence comparison |
| [Voice][mvee-voice], D13 | Existing conversation services; selected provider direction | Integrate audio transport with the existing conversation path | Conversation/voice | Audio policy/provider grant; D14 only for financial actions | Device speech/cancel/recovery recordings and latency/cost receipts |
| [Search][mvee-search] and [conversation continuity][mvee-continuity], D09/D10 | Omnisearch/history and recovery contracts | Add domain search adapters and native destination/lifecycle wiring | Native continuity + Conversation/voice | Authorized domain reads; Temporary policy for that behavior | Search-to-destination/back recordings, draft/history readbacks and Temporary retention evidence |
| [Updates][mvee-updates], D11 | Existing operational infrastructure; notification contracts | Implement inbox, domain triggers and delivery jobs | Planning/Home | Trigger facts; permissions; channel/schedule decisions | Trigger/job receipts paired with phone inbox/source recordings |
| [Profile and control][mvee-profile], D12 | Existing profile/usage/data-control contracts | Connect native controls to existing and new domain adapters | Native continuity | Identity/settings; domain lifecycle policy; approved personalization rollout | Phone settings/control recordings and authorized export/recovery readbacks |
| [Charts][mvee-quality], D05/D06/D09/D15 | Selected chart direction and prototype | Connect canonical series to native chart components | Native continuity + domain series owners | Each domain's canonical series | Series-to-display checks, gesture/accessibility recordings and device performance receipts |
| [Operational delivery][mvee-infrastructure], D01/D15 | Existing hosting, CI and release safeguards | Prepare and execute authorized signed candidate rollout | Device/release + Captain + independent acceptance | Candidate and explicit access/merge/hosted grants | Exact app/backend release manifest and [connected-journey][mvee-acceptance] evidence |
| [Agentic financial actions / runtime sequence][mvee-runtime], D14 | Existing single runtime; no ecosystem action integration | Await the separate activation required by the source | Conversation/voice when activated | Manual contracts/UI; runtime assignment and eval gates | Source-linked action acceptance evidence after activation; no completion claim before it |

[mvee-access]: argus-minimum-viable-ecosystem-experience.md#guest-access-and-registration
[mvee-platforms]: argus-minimum-viable-ecosystem-experience.md#2-product-character-and-platforms
[mvee-quality]: argus-minimum-viable-ecosystem-experience.md#native-quality-and-tester-feedback
[mvee-accounts]: argus-minimum-viable-ecosystem-experience.md#accounts-organize-the-financial-facts
[mvee-activity]: argus-minimum-viable-ecosystem-experience.md#account-activity-and-balance-checks
[mvee-refunds]: argus-minimum-viable-ecosystem-experience.md#refunds-corrections-and-adjustments
[mvee-home]: argus-minimum-viable-ecosystem-experience.md#home-understand-where-i-stand
[mvee-plan]: argus-minimum-viable-ecosystem-experience.md#plan-decide-what-i-want-to-change
[mvee-spaces]: argus-minimum-viable-ecosystem-experience.md#financial-spaces
[mvee-moves]: argus-minimum-viable-ecosystem-experience.md#reassigning-accounts-between-spaces
[mvee-household]: argus-minimum-viable-ecosystem-experience.md#12-household-collaboration-approved-minimum-capacity
[mvee-intake]: argus-minimum-viable-ecosystem-experience.md#4-information-ingestion-one-destination-several-entry-methods
[mvee-argus]: argus-minimum-viable-ecosystem-experience.md#argus-ask-understand-and-get-things-done
[mvee-voice]: argus-minimum-viable-ecosystem-experience.md#43-speak-to-argus
[mvee-search]: argus-minimum-viable-ecosystem-experience.md#search-find-what-i-already-know
[mvee-continuity]: argus-minimum-viable-ecosystem-experience.md#temporary-chat-and-conversation-recovery
[mvee-updates]: argus-minimum-viable-ecosystem-experience.md#updates-tell-me-when-something-deserves-attention
[mvee-profile]: argus-minimum-viable-ecosystem-experience.md#profile-control-argus
[mvee-infrastructure]: argus-minimum-viable-ecosystem-experience.md#14-infrastructure-and-cost-constraints
[mvee-acceptance]: argus-minimum-viable-ecosystem-experience.md#15-connected-acceptance-and-delivery-discipline
[mvee-runtime]: argus-minimum-viable-ecosystem-experience.md#agentic-ecosystem-direction-and-sequence

### Acceptance source and evidence ownership

Derive expected results from the linked MVEE sections, including their linked
technical contracts, [shared trust requirements](argus-minimum-viable-ecosystem-experience.md#5-shared-ingestion-and-trust-requirements)
and [connected acceptance journeys][mvee-acceptance]. This manifest owns who
collects the evidence, when it is collected and where it is recorded. It does
not own another editable list of expected product behavior. The table's evidence
column selects verification methods, not a replacement acceptance specification.

At dispatch and acceptance, read the current MVEE source and record its commit
and section anchors with the task/evidence. If the source changes, assess the
affected assignment and evidence against that source; do not update a copied
requirement list here. A missing or renamed source anchor is a coverage gap to
resolve before accepting that work, never permission to infer its behavior.

The financial owner supplies the record/projection contract, the household
owner the permission contract, and the native lead the shared navigation/session
contract. Domain workers can own disjoint native files. The captain serializes
shared integration and compares the work map to the current canonical scope
index when allocating work; row count alone is not a completeness claim.

Dispositions derive from the [MVEE holds register](argus-minimum-viable-ecosystem-experience.md#16-holds-later-work-and-unresolved-decisions),
[runtime sequence][mvee-runtime] and [product boundaries](argus-minimum-viable-ecosystem-experience.md#8-differentiation-and-boundaries).
The decision register below tracks unresolved delivery inputs and owners; it
cannot convert them into approved deferrals. Any new disposition requires a
founder decision in the canonical product source before execution metadata changes.

## Proposed team and shared ownership

Use seven coherent delivery responsibilities plus the captain and independent
acceptance. These are proposed assignments for review, not dispatched workers.
Each lead owns a journey through native UI, service, persistence and integration,
using the shared owners below. Pair a bounded native or backend implementer only
when it shortens a ready task with exclusive files; do not create duplicate leads.

- **Financial core** owns accounts/assets/spaces, posting, reconciliation, all
  actual-money reads, their API/data contracts and migrations. The recovered
  iPhone Accounts module belongs here. Other teams request changes to these
  owners rather than writing balances or alternate storage.
- **Planning/Home** owns budgets/goals/debt plans, recurrence, allocations,
  expected-to-actual links, Home composition and Updates. This team consumes
  financial position; it never maintains another actual balance. Its native
  views, domain services and tests can progress together.
- **Household** owns invitations, membership, consent, editing rights and
  revocation, including do-blitz/Resend integration and household UI. Domain
  owners implement adapters to this one permission contract.
- **Intake** owns capture, sources, extraction/review, preview/resume and source
  visibility through native UI and backend/storage. Confirmation calls the
  financial owner. It does not implement its own transaction writer.
- **Conversation/voice** owns inherited chat/cards/history/Temporary chat,
  authorized context and spoken interaction. It preserves the single runtime
  and existing eval gates. D14 redesign is held under its explicit sequence.
- **Native continuity** owns access UI/session, shared navigation/design/chart
  components, Search and Profile/data controls with their existing API owners.
  It owns shared Swift types and localization files, not every feature screen.
  Teams above own their separate feature modules after explicit file allocation.
- **Device/release** owns signing/project configuration, private installation,
  hosted inventory, compatible rollout/migrations execution, secret delivery,
  jobs/operations and rollback. Financial schema design stays with Financial
  core; applying a reviewed migration requires the hosted grant.

The **captain** owns this manifest, dependency handoffs, integration order,
review proportionality, usable builds and founder reporting. An **independent
acceptance owner** runs cross-domain journeys and privacy/recovery checks against
the assembled candidate, including physical-phone demonstrations. Verifiers
return defects to writers. No team is complete merely because its PR merged.

Start available independent work with bounded agents on separate branches.
Use the Mac for Xcode/device work and available VMs for isolated backend/database
work. A VM needs a verified communication channel and checkpoint persistence
before autonomous assignment. Keep shared branches, migration execution and
shared Swift files single-writer. Publish exact branch heads and durable evidence
for handoff; stale chat status is not proof a writer is alive.

## Parallel delivery across the full scope

This is the proposed full-scope sequence, not the current batch authorization.
When separately authorized, activate full-scope ownership from the
coverage table. Begin the device/hosted, financial backend and native core-loop
responsibilities together. Also start independent household membership/invitation,
intake capture/preview, inherited conversation, existing profile/settings and
native navigation/chart work where ownership and inputs permit. These outcomes
do not depend on a completed expense loop. Provider-dependent work proceeds only
within its explicit authority; local implementation/testing continues separately.

The financial owner defines and implements each posting/read contract with its
first consumer. The planning owner can build plan lifecycle and expectations
alongside that work, then connect actual progress when posting/link contracts
are accepted. Household permission design proceeds before shared consumers;
it does not wait for every personal feature. Intake extraction/review proceeds
before financial posting is ready; confirmation must use that shared posting
contract. Search adds one authorized record type at a time; Updates adds one
accepted trigger at a time; controls accompany each domain's lifecycle. Voice
can connect to existing conversation independently of deferred financial actions.

A dependency applies to a specific read, write, permission or acceptance case,
not an entire department. Signing gates phone installation, not backend work.
Posting gates real financial confirmation, not document preview. Household rules
gate sharing, not private records. Plans gate forecasts, not recorded net worth.
No broad pillar-complete gate or new batch authorization is introduced.

Each domain has one accountable owner, a separate writer branch/worktree and
exclusive files. Backend API/data/migration ownership stays with the domain;
consumers do not invent alternate contracts. Native feature writers may work in
parallel on disjoint modules; the native lead alone changes shared session,
navigation and common UI models, while device configuration has its named owner.
Resolve overlapping writes by reassignment before dispatch. Integrate small
working increments continuously through the existing review/merge boundaries.

Independent acceptance starts with the first assembled behavior. Demonstrate
installation, then the financial loop, while other scope continues. Subsequent
builds add linked planning, imports, household and other completed journeys as
their actual dependencies clear, not in a fixed pillar order. Each demo reports
both the exact phone-proven behavior and remaining full-scope coverage. The
captain continues until all non-deferred rows and all five MVEE connected journeys
are accepted on the physical phone. The D14 gap stays visible at that milestone.

## Demonstration checkpoints

These are observable builds, not scope gates or successive authorization batches.
After the early phone connection, order subsequent demonstrations by ready
journeys. Other teams continue while a candidate awaits hosted access or review.

1. **Connected installation.** Existing-user login, reopen and logout work on
   the physical phone away from the Mac. Financial/backend and other independent
   teams continue. This proves access only.
2. **First financial loop.** Establish balance, expense, Account/Home change,
   correction, reconciliation and persistent reopen. Demonstrate known/unknown,
   retry and earlier-activity handling. Plans, household, intake, chat and controls
   continue independently. This does not close the full D03/D05 rows.
3. **Useful connected increments, in parallel.** Show a budget/goal/debt plan
   with recorded progress and forecast; a statement/photo with actual preview,
   reviewed import and resume; a two-person household with explicit sharing and
   revocation; and inherited chat with evidence, Search return and voice. Each
   reaches the same app when verified, without waiting for the other increments.
4. **Complete private candidate.** Demonstrate all five MVEE journeys and all
   non-deferred coverage rows together, including Updates, spaces/assets,
   access completeness, Profile/data controls, Temporary chat, localization,
   accessibility, charts, error recovery and safe app updates.

For every demonstration, identify the app build/commit, backend revision and
configured environment. Record a short live interaction or video showing the
successful action, a failure/recovery and relaunch; use synthetic/redacted
committed evidence. Real founder records are deliberate/authorized only.
Phone acceptance uses the physical iPhone over HTTPS on cellular or another
network with the Mac unavailable. Component tests, simulator runs and screenshots
remain supporting evidence. Backup restoration/rollback are verified in a safe
environment and linked to the deployment candidate, never exercised destructively
on the founder's data. Full private completion requires every applicable row's
acceptance, not merely completion of these demonstrations.

## Status, evidence and handoffs

Use these states on each assigned row: `stopped`, `queued`, `building`,
`verification`, `ready-to-land`, `landed`, `deployed`, `accepted`, `blocked`,
`deferred`. Record a date and reason for a block or deferral. A merged PR is
`landed`, not `accepted`. A deployed backend without phone proof is `deployed`.
`accepted` means the assigned user outcome works in the integrated iPhone build.
No current work row is accepted.

Before dispatch, record these fields in the assigned item or its linked bounded
spec: named owner, exclusive branch/worktree, fetched integration base, MVEE
anchors, reuse pointers, allowed/no-touch files, accepted API/data dependencies,
acceptance checks/commands, timebox, stop conditions and cleanup/handoff duty.
Unfilled fields mean the item is not ready to dispatch. Later changes need a
recorded reason; they must not silently shrink the MVEE outcome.

At each meaningful checkpoint, report two views: what the founder can actually
do on the phone, and what remains across every coverage row, including blocked
decisions and approved deferrals. The first loop never closes the ecosystem.
Update the assigned row and link its PR plus durable
acceptance artifact. Record the commit, app build, backend/environment revision,
checks actually run, reviewer outcome, unresolved findings, next action and any
required founder decision. Keep credentials and real personal documents out.
Use synthetic/redacted evidence for committed acceptance artifacts. Exact-head
and one-way reconciliation rules remain in AGENTS.md.

On restart, read the authority map, MVEE and this manifest. Inspect current GitHub
state, commits and actual process handles. Locate preserved local work. Confirm
one writer per branch before dispatch. A stale conversation, old report or
expired observation is not proof an agent is alive or a feature is complete.
Stop duplicate owners and preserve their unique work before replacement.

Poteto-mode is an available workflow aid, not required undocumented machinery.
Use its Orchestrate/session-recovery routines when available while keeping these
repository-visible pointers sufficient for another coordinator. Runtime work
records must survive the session and be reachable by their assigned local/VM
owners. Do not create a second handwritten product-status board. A scheduler,
store or automated phone acceptance runner has not been installed by this PR.
Their setup is future authorized work, not a claimed current capability.

## Authority and founder involvement

The delivery captain coordinates and verifies; domain owners implement; one
integration owner lands only within the founder's explicit grant. The founder
reviews usable builds and decides product choices, spending, credentials and
hosted/deployment permissions. One execution authorization covers the full assignment. Routine sequencing,
implementation, testing, scoped bug fixes and review triage do not need repeated
founder prompts or successive batch approvals. Merges, hosted changes, deployment
and spending still require the explicit grants recorded for those actions.
Current VM communication still goes through the founder until a direct channel
is explicitly established. Do not claim autonomous VM coordination exists.

No stop instruction, denied approval or missing contract may be bypassed through
another agent. Batch genuine decisions and continue independent authorized work.
Stop affected work for duplicate writers, contradictory contracts, repeated
unproductive failures or scope expansion. Review genuine reachable defects at
their shared cause; stop the review loop at the repository's clean-delta rule.

### Decisions and access that materially affect delivery

These are unresolved inputs, not requests for all answers before work starts.
Recommendations are proposals for review, not approved policy. Owners resolve
routine API/schema/locking choices themselves. They prepare a concrete decision
only when a product choice, access grant or spending authority is necessary.

| Decision or access | Owner and affected work | Recommendation for review; what can continue |
| --- | --- | --- |
| Single execution restart and action authority | Captain; entire assignment | Authorize continuous implementation/build/test/review/branch publication across all non-deferred coverage once the plan is accepted. Merge, signing/install access, hosted mutation/deployment and paid-provider grants remain explicit; no per-pillar restart prompts |
| Apple account/team, physical phone access, stable app identity, supported device/OS and private updates | Device/release; installation and phone acceptance | Inspect existing entitlement/team/device access and choose the shortest supported signed route with a stable identity and repeatable update path. Public App Store release is unnecessary. Device specifics remain unverified; backend and native implementation continue |
| Existing Render/Supabase access, deployed revisions/migrations/capacity and production-compatible rollout | Device/release; hosted proof | Reuse existing project/current plan and compatible Render capacity. Prepare exact migration/settings/candidate, production-web regression evidence, backup/restore and rollback before the hosted grant. No new project or spending by default |
| Financial/private-space recovery window, purge/export behavior and production limits | Financial core + Native continuity; lifecycle controls | Propose the unresolved limits under [account recovery][mvee-activity] and [space lifecycle][mvee-spaces] before release. Ordinary posting can progress |
| Household editing, departure, joint-record custody and recovery | Household; shared writes and revocation | Recommend view-only sharing unless edit rights are explicitly granted; revoke future access promptly without silently deleting another person's records. Present joint custody/export/retention choices for approval. Private journeys and invitation mechanics can progress |
| File formats/institutions, OCR, upload/page limits, encrypted files and retention | Intake; extraction/storage | Cover declared PDFs, structured exports and images/photos; select concrete supported samples. Recommend local type/readability checks, private source access and explicit sharing; do not accept unreviewed OCR as fact. Determine limits/provider from bounded synthetic evaluation, then seek any paid/data-handling grant. Do not drop photo/PDF intake because selection is unfinished |
| Notifications, schedule defaults, time zones and monitored external conditions | Planning/Home; delivery and scheduled updates | Recommend a persistent inbox and opt-in private push previews; no financial details outside the authenticated app. Founder selects external channels/defaults. Use existing jobs and sourced conditions; trigger/inbox implementation can progress independently |
| Audio and Temporary chat context/provider retention | Conversation/voice; Temporary behavior and live audio | Recommend no retained raw audio by default; verify provider feasibility and seek approval for unresolved retention under [voice][mvee-voice] and [Temporary chat][mvee-continuity]. Regular native chat can progress |
| Provider credentials, spend caps and consenting data/test identities | Relevant domain + Device/release; live voice/OCR/research/backtest/invite acceptance | Use existing approved providers, server-held secrets and bounded cases/caps. Request credentials via secure configuration, not chat. Use synthetic documents/accounts until real samples and second-user participation are authorized; no broad production data copies |
| VM access and direct coordination | Captain; remote workers | Verify secure connectivity, exact checkout, exclusive writer and pushed checkpoints before remote assignment. Use local agents for ready work until then; do not make additional machines a prerequisite |
| D14 activation | Captain + Conversation/voice | Respect the founder-approved runtime sequence. Keep its unmet action parity visible and request the separate runtime assignment when its prerequisites are satisfied; do not use it to defer ordinary voice, manual workflows or financial read-context |


Use the canonical disposition links above when assigning work. This documentation
change does not activate implementation or any held integration.
