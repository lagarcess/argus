# Argus private iPhone execution manifest

**Cuadrao design follow-ups, October 1:** [single disposition register](#cuadrao-design-dispositions).
The delivery-lane snapshot below is unchanged by that documentation checkpoint.

**Updated:** September 30, 2026.
**Execution state:** [connected personal savings goals](#pr-755-integration-landing) are landed through [PR #755](https://github.com/lagarcess/argus/pull/755), with the locally verified native journey and runnable demonstration preserved. The founder authorized this merge and its bounded integration landing. No next slice or deployment is authorized. [Personal spending budgets](#pr-753-integration-landing), Search (#751/#752), Plan/Home (#749/#750) and personal recording (#747/#748) are landed with their demonstrations preserved. Physical-iPhone testing belongs to a separate owner and remains outside this lane.
**Product owner:** [MVEE](argus-minimum-viable-ecosystem-experience.md).
**Authority and onboarding:** [DOCUMENTATION_AUTHORITY](../DOCUMENTATION_AUTHORITY.md).

**Original preservation authorization (historical):** The founder accepted this expanded plan for
commit and push on September 29, 2026. That grant authorized documentation preservation
only, not implementation, worker dispatch, merge, deployment or hosted changes.
Recovery branch: `codex/mvee-iphone-delivery-plan`.

## PR #755 integration landing

The founder authorized merging #755 at its verified head, completing integration
landing and the necessary bounded documentation PR, then verifying CI and
local/remote parity. No deployment, hosted configuration change, next slice,
signing or phone-environment action is authorized.

- [PR #755](https://github.com/lagarcess/argus/pull/755) squash-merged at
  **September 30, 2026, 11:32:38 a.m. America/Chicago** as
  `dc48c074b457cfb461e128aee2dcc58f9db3a342`, from verified head
  `f6dfd482a1e4dc802f0d64eba22bc91a4f01d48f` onto unchanged integration
  `6a9d0338d2b2e7106877e0e5d1f9f5aaa70d67ec` (also the original base).
  There is no intervening semantic overlap or reconciliation merge. The approved
  head and integration merge trees are identical; canonical integration
  fast-forwarded cleanly and merged-tree modularity passes.
- The [terminal readiness audit](https://github.com/lagarcess/argus/pull/755#issuecomment-5906057156)
  retains green applicable PR/push CI and smoke, clean fresh independent review
  after the bounded lifecycle/harness fixes, and zero unresolved findings.
  Four native journeys, 310 assembled financial/API/OpenAPI/Postgres passes,
  recovery/localization evidence, 13 screenshots and the 62-second recording
  remain valid across the identical merge tree. Landing changes documentation
  only and does not repeat the accepted journey.
- Exact merge [integration CI](https://github.com/lagarcess/argus/actions/runs/36744979395)
  and [local smoke](https://github.com/lagarcess/argus/actions/runs/36744979517),
  the checked documentation PR and final clean local/remote integration parity
  are recorded in the merged PR's final landing comment after terminal checks.
- There are no linked closing issues. Only this manifest and the integration
  ledger need landing updates; API/data/OpenAPI contracts already landed with
  the implementation. No current document needs archiving.
- No new production environment variable or tracked-template change is needed.
  The inherited `ARGUS_FINANCIAL_ACCOUNTS_ENABLED` remains default-off in
  `.env.example` and `render.yaml`. `ARGUS_TEST_GOAL_SUPPORTED` is a synthetic
  native-test assertion input, not hosted configuration. The additive
  `20260930170000_connected_savings_goals.sql` migration was verified locally
  and by the existing automatic PR preview; landing applies no hosted migration.
- The [savings demonstration and restart guide](../reports/evidence/connected-savings-goals/README.md)
  remain on `codex/connected-savings-goals` in its unchanged delivery checkout,
  using the dedicated simulator and 591xx services. Every prior demonstration,
  synthetic record and the separate physical-phone environment (58700–58749)
  remain preserved. Physical-iPhone internet delivery and the whole MVEE are
  still incomplete; remaining debt-plan, shared and other journeys stay mapped
  below. No further implementation is assigned.

## Connected personal savings goals lane

**Founder assignment, September 29, 2026:** deliver the connected personal goal
journey through native iPhone simulator acceptance against an isolated real local
API/Postgres, scoped independent review and a merge-ready PR. Implementation,
local verification, commits, branch and PR publication are authorized. No merge,
deployment, Render action, hosted configuration change, production data, paid
provider, real-money movement, signing or physical-phone installation. Other
MVEE work stays with its existing owners; this lane does not start another slice.

**Fresh integration base:** `6a9d0338d2b2e7106877e0e5d1f9f5aaa70d67ec`,
including the budget implementation and landing (#753/#754).
**Recovery branch:** `codex/connected-savings-goals`.
**Delivery checkout:**
`/Users/garces/.codex/worktrees/connected-savings-goals/private-alpha-next`.
**Current state:** the complete personal savings journey passes on the dedicated
native simulator against real local Auth/API/Postgres. Existing allocation,
record/link, original correction, withdrawal/shared-shortfall recovery,
lifecycle, Home/Plan/Search, relaunch and English/Spanish are connected.
Implementation owner has relinquished a clean source tree. Independent review
is clean after one confirmed lifecycle-input fix and one native harness fix.
[PR #755](https://github.com/lagarcess/argus/pull/755) is merged;
[the landing checkpoint](#pr-755-integration-landing) owns current integration
CI/parity. Its accepted source, review and demonstration remain preserved.
All existing demos, synthetic data and phone resources are preserved. Ports
58700–58749 and the phone owner's checkout, services and signing are forbidden.

### Founder-approved savings policy

**Approved September 30, 2026.** Goals use explicit allocations backed by known
recorded account balances, kept separate by currency. Allocating money does not
move it or change account balances. A shared pool prevents multiple goals from
claiming the same money. Existing savings count when explicitly allocated;
linking an already included contribution adds provenance without another credit.
Planned contributions and projections remain separate from actual savings.

Withdrawals, reversals and corrections re-evaluate backing and linked activity.
If backing becomes insufficient, show the shortfall and **Needs review**. Do not
silently redistribute money or present unsupported amounts as fully saved.
Unknown balances cannot establish supported actual savings. The person chooses
how to reduce or reassign allocations; Argus invents no priority among goals.

This settles the product gap identified in the [MVEE Plan rules][mvee-plan] and
locked design. The prototype's reported-total checkpoint, which ignored ordinary
withdrawals, is superseded for production savings truth by this explicit founder
decision. Its native visual standard and contribution/detail interactions remain
the reference. Relevant API/data contracts record the approved policy and bounded
allocation/link/lifecycle semantics alongside implementation. No new product
approval is needed for routine technical choices within this policy.

### Ownership, dependency and acceptance map

The captain owns delivery, integration, manifest and independent acceptance.
Implementation owner `goals_implementation` owns the shared contracts, Planning
goal service/storage, Recording adapters, native goal module and integration
tests in exclusive branch `codex/connected-savings-goals-core`, checkout
`/Users/garces/.codex/worktrees/connected-savings-goals-core/private-alpha-next`.
The captain integrates its ordered commits into the delivery branch and owns
the simulator, local services, evidence and independent acceptance. Recording remains the only actual-money owner; Planning
owns goal intentions, allocation/linking and projections. Clients render server
results. Existing account and activity detail/correction screens remain the
money-edit controls. A fresh independent reviewer reviews the finished diff once
and only affected fixes afterward. Codex availability is not a dependency.

| User outcome | Inherited capability | Implemented connection | Actual dependency | Observable assembled proof |
| --- | --- | --- | --- | --- |
| Create, inspect and edit a named target, currency, optional date and account setup | Native Plan Goals destination, shared money inputs, versioned Plan commands | Goal definition and real detail/form; API/data contract | Goal definition/progress contract | Native create/edit, stale-version rejection and API readback after reopen |
| Assign existing savings; record or link contributions once across multiple goals | Canonical logical activity, paired transfers, Plan receipts and owner lock | One allocation/link owner and atomic record/link commands | Shared allocation contract; known same-currency backing | Independent expected amounts across two goals; unchanged balances on allocation; duplicate retry creates no second activity or claim |
| Separate actual, planned and projected progress in Plan/Home | Shared Plan/Home snapshot, recurrence and forecast, native summaries | Goal intentions and derived occurrences/progress; explicit exclusions | Accepted goal/link contract | Planned saving leaves balances and actual progress unchanged; internal transfer has zero combined-cash/spending effect; fulfilled movement disappears once |
| Inspect/correct contributions and handle withdrawals/reversals | Original activity detail, append-only correction, account reconciliation | Goal link re-evaluation and explicit allocation recovery | Accepted backing and link rules | Original correction updates Accounts, goal and forecast; insufficient backing is visible; no invented goal-priority rule |
| Archive and restore without copying money/history | Plan/Budget reversible lifecycle and CAS/idempotency | Goal lifecycle with retained identities and explicit allocation effect | Accepted lifecycle/allocation contract | Archive/restore/retry keeps IDs, history and consistent shared claims |
| Find a goal and return with context; English/Spanish | Typed Search, persisted query/filter/anchor, native localization | Goal hit and actual detail destination; localized controls | Real goal projection/detail | Search to goal to original contribution and back retains origin and refreshes edits; relaunch preserves state |
| Recover durable writes with owner isolation | Exact command journal, replay-before-CAS, repeatable-read Postgres, auth/RLS | Goal-specific transaction, API, package and simulator cases | Implemented shared command contract; dedicated local stack | Response loss/retry and concurrent writes commit once; stale update is explicit; another identity cannot read or mutate goals/allocations |

### Selected goal contract and architecture

**Named shapes:** `GoalDefinition` stores target/setup/lifecycle and explicit
unlinked allocation residuals. `GoalContribution` points at one current canonical
transfer and optionally its own planned occurrence. `GoalPool` derives backing,
claims, available money and shortfall for one owner/account/currency.
`GoalProgress` derives assigned intention, supported actual, remaining, review
reasons and separate planned/projection data. No actual saved total or balance
copy is persisted. The existing Plan snapshot, owner lock, receipts and CAS own
both reads and commands; Recording supplies current position, activity and the
single ownership-share rounding function.

| Candidate | Independent assessment | Captain decision |
| --- | --- | --- |
| Current goal intentions and linked attribution in Plan snapshot | 5/5 money truth, 5/5 contribution correction, 5/5 existing owner reuse, 4/5 interface/storage | Selected; fewer persistence/replay stages and correct included-credit correction. |
| Append-only allocation intention events | 4/5 money truth, 1/5 included correction, 4/5 reuse, 2/5 interface/storage | Rejected; no separate allocation-history requirement justifies the extra fold, and provenance-only inclusion leaves old contribution credit in the assignment. |

The independent architecture reviewer was `goals_architecture_judge` in a fresh
context. This is design judgment, not implementation review. The captain grafted
its explicit deficit-improvement rule: reduction of existing claims remains
admissible while underfunded; new/increased claims require known sufficient
backing. No event history or partial activity split is introduced.

- Cash, checking and savings are the backing/funding/destination accounts in
  this slice, following the locked design. Capacity uses personally attributable
  current known positive position; unknown is not zero. Per-account pools prevent
  unrelated accounts or currencies silently rescuing a shortage. Account archive
  retains backing; goal archive retains claims and suspends pending goal schedule.
  Restore retains identity and derives current support, including Needs review.
- An eligible contribution is one current transfer into an allowed same-currency
  destination, assigned wholly to one goal. Income received directly can be
  allocated as existing money; it is not another goal transaction kind. Source,
  destination, currency and current revision remain reviewable.
- **Already included** partitions an existing unlinked allocation. Allocated 600,
  linked transfer 200 already included becomes residual 400 plus current transfer
  200, still 600. Correcting that transfer to 150 yields 550; to 250 yields 650.
  Accepted original amount is provenance only. Linking never posts money. A new
  transfer plus its allocation/optional fulfillment commits in one transaction.
- One shared activity claim owns attribution and optional occurrence fulfillment.
  Preserve existing expectation links, owner-qualified references and uniqueness.
  Ad hoc goal claims must not enter income/bill-only readers. Release of counting
  leaves fulfillment intact; it does not recreate a completed forecast movement.
  Changed/unavailable activity shows review, never an older fallback amount.
- A reverse-direction transfer is new canonical activity that changes backing,
  not evidence that the original transfer never happened. No amount/date matching
  invents a reversal. The lane adds no global financial-activity remove/restore
  API; acceptance uses original correction, reverse transfers and goal recovery.
- A fully backed component supports its assigned amount. A known shortfall with
  one claimant goal supports `min(assigned,backing)` and Needs review. A shared
  shortfall or unknown/ineligible backing leaves affected component support null.
  Any unresolved component leaves the goal total null; separately backed portions
  remain inspectable as partial support. Reached requires resolved support and
  no review issue. Count distinct goals, including archived goals, rather than
  contribution rows when deciding whether backing is shared.
- Goal-owned optional transfer schedules derive occurrences through the existing
  recurrence/cutover owner; no duplicate editable expectation. Two selected fully
  owned cash legs net zero. With one selected side or differing ownership shares,
  show the actual selected/personal cash effect without classifying it as income,
  bills or spending. Fulfilled or disputed linked occurrences do not silently
  create another payment. Planned contributions never become actual savings.

**Local allocation:** API 59100, Supabase 59101, Postgres 59102, synthetic CAPTCHA
59105; optional response-loss proxy 59112 and simulator mirror 59113. Dedicated
simulator `A466756C-1478-4FA9-8604-3D9FEE15A601`, iPhone 17e/iOS 27, named
`Argus Connected Savings Goals`. Ignored local users/config belong only to this
checkout. Restart existing services; never remint users or reset the database.
The read-only inherited baseline passed 236 financial/Plan/Budget/Search tests
with zero skips and native registered sign-in/relaunch/sign-out acceptance.
[Baseline evidence](../reports/evidence/connected-savings-goals/baseline.json)
records source/environment; no goal acceptance is claimed by those checks.

### Delivery workflow and throughput checkpoint

- [x] Read the Principles section of poteto-mode; frame the falsifiable local
  journey and preserve the scope/authority in this manifest.
- [x] `how` over the affected subsystem. Financial/native scouts recovered the
  canonical Recording, Plan snapshot/receipts, native detail/journal and Search
  flow without rebuilding them.
- [x] `architect` for parallel design exploration. Two bounded read-only
  candidates compared current intentions with allocation events. Independent
  cross-judgment and captain selected current intentions; synthesis below.
- [x] Write the throughput checkpoint as four todo items, below; update it at
  ownership handoff.
- [x] Delegate code-writing to one exclusive implementation writer/worktree.
- [x] Verify on the matching surface: real local API/Postgres and native simulator.
- [x] Deliver small ordered commits, verifying each unit before the next.
  Repository one-way integration merges override the playbook's rebase step.
- [x] If the design is contested, interrogate before shipping. Skip: the
  independent grounded selection resolved the invariant without a contested design.
- [x] Run Opening a PR and the approved independent review/fix loop.
  Exact-head applicable CI and the terminal audit are owned by
  [PR #755](https://github.com/lagarcess/argus/pull/755). Its terminal
  readiness audit is green with zero unresolved findings; the authorized merge
  is recorded in the landing checkpoint. No deployment or next slice.


1. **Blocking first steps:** the founder policy is settled. Select the bounded
   allocation/link/lifecycle contract before writing dependent code. Selection
   is complete; the shared contract is handed to the single writer.
2. **Independent workstreams:** read-only financial/native recovery is complete.
   Local acceptance preparation runs alongside the implementation writer
   without editing its checkout; independent review follows the finished diff.
   Backend/native changes stay with one writer because contribution attribution,
   activity claims and forecast fulfillment are one code-coupled feature.
3. **Shared mutable state:** Planning snapshot, receipts, financial owner lock,
   activity links, Swift response types, Search union and localization each have
   one writer. No parallel ledger, editable saved total, web or rebrand work.
4. **Smallest safe decomposition:** goal definitions and derived progress;
   atomic contributions and linked forecast; native lifecycle/original-activity
   continuity; assembled recovery/localization evidence and scoped review.

Acceptance uses synthetic records, explicit expected amounts independent of the
reducer under test, real local API/Postgres and a dedicated native simulator.
Screenshots and a short recording are committed with restart instructions and
exact-head provenance in the implementation PR. Component checks are reported
separately from the working local journey; physical-phone internet delivery
remains pending outside this lane. Before readiness, fetch integration, perform
one-way reconciliation when needed, assess semantic overlap, run affected
acceptance and merged-tree modularity checks, finish applicable CI and record
reviewed SHA and zero unresolved findings. Stop at merge-ready.

### Local delivery evidence and PR gates

The assembled source is `83523335d43e6f6e98ac1ddd05fb47a0531ddc83`.
[Runnable demo, short recording and restart instructions](../reports/evidence/connected-savings-goals/README.md)
retain the registered synthetic scene and its exact source provenance.
[API proof](../reports/evidence/connected-savings-goals/goal-api-proof.json)
independently checks current contribution corrections, shared pool shortages,
manual resolution, archived reservations, recurrence/fulfillment, separate
currencies, unknown backing, stale commands and owner isolation.
[Read-only SQL](../reports/evidence/connected-savings-goals/goal-database-proof.json)
confirms two retained goals, four canonical activities, two claims and one
receipt for the retried create. Unrelated native test fixtures remain preserved.

Four native cases passed with zero failures/skips: the complete manual journey;
response-lost goal creation; response-lost actual transfer; retained Home/Search,
reopen and Spanish. [Native evidence](../reports/evidence/connected-savings-goals/native-proof.json)
records their exact results, direct API restoration and the financial-only
62-second recording. 310 assembled financial/API/OpenAPI/Postgres tests passed
with zero skips. Fourteen independent tool/launcher checks and nineteen inherited
fault-helper checks passed. The unchanged Swift package retains 55 passed tests
and four inherited opt-in live-auth skips; real native auth passed separately.

The retained goal **Savings goal a 4fab425f** shows actual 400 of 1,000, planned 100
separately, conditional projected 500 and 600 remaining. Goal B claims 10 from the
same account's 410 backing. Native **Emergency 82C9D** retains allocation 600,
transfer 200, original correction 150, resulting 750, release/relink, edit to 2,500
and archive/restore. A temporary correction of the existing reverse transfer
made shared backing 390 against 410 claims: native support became unavailable,
**Needs review** and shared shortfall 20 were visible. Restoring that correction
restored 400/10 support. No allocation priority or second money activity was added.

Fresh reviewer `goals_independent_review` (`gpt-6.1-sol`, fresh context) reviewed
`756340afdd38fba9dffaba179faa13edfaf14501` once. Its confirmed P2 was explicit
`archived:null` persisting an unreadable goal. Fix
`09994ce2a01c594c0be092b207fd20cb5cdd9dad` independently preserves archive state
and date clearing, with Goal/Home/Plan/Search read regressions. The affected fix
review was clean. Final test-only delta
`4689e81ae799be67948fb0e8b54ba91a661fd231` removes an Accounts-only assertion
from goal confirmation and passed its scoped review plus real native acceptance.
[Review record](../reports/evidence/connected-savings-goals/review-proof.json)
retains coverage and limits. Zero confirmed findings remain. No exhausted Codex
review or new reviewer swarm is required.

Integration re-fetch remained `6a9d0338d2b2e7106877e0e5d1f9f5aaa70d67ec`.
There is no intervening semantic overlap or reconciliation merge. The assembled
worker already contains current integration; merged-tree modularity and lint
pass. Source acceptance remains valid when only this manifest/evidence changes;
the terminal PR audit must record the published exact head, final CI and zero
unresolved threads after review completion.

**Concrete limitations:** personal cash/checking/savings backing and whole
same-currency transfer attribution; no contribution splitting, conversion,
investment valuation or household permissions. Direct income can be explicitly
allocated as existing savings. Original source/destination/currency changes need
review, never silent retargeting. Linked fulfillment stays fulfilled on attribution
release. The inherited full-owner snapshot and surviving navigation anchors
remain the scale/continuity limits. These are recorded contract boundaries, not
new deferrals of assigned work.

**Remaining visual polish:** an Xcode transient invalid-frame diagnostic appeared
in the full native run without a visible defect in the inspected financial frames.
Retain it for the existing visual-polish work; there is no demonstrated money or
navigation failure. The unfinished Cuadrao identity and broader native polish
retain their existing owners; this lane did not rebrand or redesign navigation.
Physical-iPhone internet proof, debt-plan lifecycles and all other MVEE work
remain tracked below. The authorized merge and bounded documentation landing
are recorded above; no deployment or next slice occurs.

## PR #753 integration landing

The founder authorized the owner to merge #753 after rechecking its head and
integration, then complete the bounded landing workflow. No next slice,
deployment, hosted configuration change, signing or phone-environment action
is authorized.

- [PR #753](https://github.com/lagarcess/argus/pull/753) squash-merged at
  `2026-09-30T03:53:28Z` as `ff1d9795af50ad1566d59e7e986e2cc31be2ca82`, from
  verified head `55d211636bc187cda2fe88fba152c5724a95907c` onto unchanged
  integration `9f51912198c2c77e239f670a2b3f78da2942afed`. Approved-head and
  merge trees are identical; no reconciliation or semantic overlap arose.
- Applicable PR/push CI and smoke were green, independent review was clean
  through `ced256196c04eae6cfcd18f456f3dc00017315c7`, and zero unresolved
  findings remained. The [terminal audit](https://github.com/lagarcess/argus/pull/753#issuecomment-5903364607)
  records exact-head simulator acceptance and retained API, recovery, visual and
  review evidence. No application behavior changed during landing.
- The canonical integration checkout fast-forwarded cleanly to the merge.
  Exact post-merge [CI](https://github.com/lagarcess/argus/actions/runs/36666427091),
  [smoke](https://github.com/lagarcess/argus/actions/runs/36666427084), landing
  housekeeping and final local/remote parity are recorded in the merged PR's
  landing comment after terminal verification.
- No linked closing issues require reconciliation. There is one additive
  owner-scoped budget migration; real local Postgres and the authorized automatic
  PR preview verified it. No new production environment variable or template
  change is needed. The inherited UI-test query input remains test-only.
  Financial exposure remains default-off; landing applies no hosted migration.
- The [budget demo, recording and restart guide](../reports/evidence/connected-budgets/README.md)
  remain runnable from the existing delivery checkout, direct API 59000 and
  loopback mirror 59013. Records, journals, installed simulator and all earlier
  demos remain preserved. The separate phone-testing environment, including
  ports 58700–58749, is untouched.
- This completes the assigned personal-budget journey locally. Physical-iPhone
  internet proof, other Plan lifecycles and remaining MVEE coverage remain with
  their existing owners; no deployment, main promotion or next slice occurred.

## Connected personal spending budgets lane

**Founder authorization, September 29, 2026:** deliver personal spending budgets
through implementation, real local API/Postgres and iPhone simulator acceptance,
review fixes and a merge-ready PR. Commits, publication and existing automatic PR
previews are authorized. Merge and deployment require separate approval. No
hosted changes, production data, paid providers, signing or phone installation.
Household, goals, debt plans, imports, voice, runtime redesign, web, billing and
analytics are excluded. Those MVEE outcomes remain in the coverage map.

**Integration base:** freshly fetched
`9f51912198c2c77e239f670a2b3f78da2942afed`, including #751 and #752.
**Delivery branch:** `codex/connected-budgets`.
**Delivery checkout:**
`/Users/garces/.codex/worktrees/connected-budgets/private-alpha-next`.
**Isolation:** API 59000, Supabase 59001, Postgres 59002, synthetic CAPTCHA
59005; dedicated iPhone 17e simulator
`CC81C737-2F0A-48EA-961C-D9ECFFACA219`, named `Argus Connected Budgets`.
The optional fault proxy and mirror use 59012 and 59013. All earlier demos,
synthetic records, checkouts and services remain intact. Ports 58700-58749 and
the separate physical-phone environment are forbidden. Global simulator-tool
settings are shared and must not change.

### Budget contract and policy gate

The [MVEE Plan rules][mvee-plan] own the journey. Expenses minus received refunds
are actual spending; transfers and card payments are zero spending. A budget
limit never creates a forecast cash movement. Actual amounts remain full recorded
transaction amounts; account-share position attribution is a different result.
Negative net spending is valid. Corrections re-evaluate current activity, while a
refund never reopens a fulfilled bill. Existing Recording owns refund category,
link validity, caps and currency rules. No editable spending total is introduced.

The locked prototype demonstrates a calendar-month category/currency budget,
no rollover, contributing-entry navigation, create/edit/confirmed removal and
prevention of duplicate buckets. Its `JOURNEY-EXPANSION.md` explicitly leaves
production period/time-zone, account coverage, uncategorized and retention
contracts open. These are not approved product deferrals.

**Founder-approved policy, September 29, 2026.** The founder approved the
original question and resumed this existing lane through merge readiness. Budgets
use a calendar month in the saved Plan reporting zone, one currency, explicitly
selected accounts and categories, an explicit uncategorized option, and no rollover.
Linked refunds reduce matching spending in the month received using the current
original purchase's account/category even when received in a different account.
Unlinked refunds use their recorded account/category. The saved zone and resolved
interval remain visible. Changing that shared zone re-evaluates month boundaries
without changing recorded timestamps. The relevant existing API and data contracts
record this policy before implementation. Routine engineering choices belong to
the delivery owner; merge and deployment still require separate approvals.

Removal reuses Plan's reversible archive/restore command pattern, retaining
the definition ID, activity and receipts. The delivery owner selects this existing reversible lifecycle without introducing
a permanent-deletion or retention promise. Exact duplicate active scopes
need one storage guard as well as domain validation; restoration must report a
conflict instead of silently replacing an existing definition.

**Named data shapes:** `BudgetDefinition` stores stable ID, owner, version,
name, limit in integer minor units, currency, explicit account/category scope,
month and lifecycle. `BudgetProgress` derives the visible interval, purchases,
refunds, net spent, remaining, over-budget amount and contributing logical
activity IDs from current canonical records. None of those totals is persisted.
Budget definitions belong to Planning; actual spending rules belong to Recording.

| Architecture candidate | Decision and reason |
| --- | --- |
| Extend the existing Plan snapshot | Selected. Definitions, accounts, activity, Home and Plan share the existing repeatable-read transaction and command receipts. One Recording-owned spending reducer feeds Home and budget progress. |
| Add budget-specific indexed activity queries | Not selected for this implementation. No measured scale requirement justifies a second current-activity query and consistency boundary. The existing full-owner snapshot limitation remains explicit. |

Budget create/edit/lifecycle commands extend the existing scoped idempotency and
version-check owner. One additive owner-scoped definition table has registered
owner read isolation and service-only writes. Detail totals and contributing rows
come from the same matched collection. Existing financial activity detail and
correction screens retain money-write ownership. Search receives a typed budget
hit and live budget destination, using its existing origin/back and refresh rules.
API and data contracts change in the same implementation PR.

### Budget ownership and throughput

- **Blocking first steps.** Recover canon and locked design, record the approved
  financial policy, then commit the bounded API/data contract before code.
- **Independent workstreams.** Backend/native scouts and architecture synthesis
  are read-only. The captain prepares isolated services, simulator and acceptance.
- **Shared mutable state.** One implementation writer owns budget backend,
  native connections and tests in an exclusive branch/checkout. The captain owns
  the separate delivery/demo checkout and this manifest. No concurrent writer or
  suite runs in the implementation checkout.
- **Smallest safe decomposition.** One coherent owner keeps budget inclusion,
  summaries, detail and Search consistent. The captain verifies the assembled
  result after handoff. One fresh independent reviewer replaces unavailable
  Codex review capacity; subsequent review covers affected fixes only.

`budget_financial_scout`, `budget_native_scout` and `budget_architecture_judge`
completed read-only reports at the integration base and relinquished ownership.
The exclusive implementation checkout is
`/Users/garces/.codex/worktrees/connected-budgets-core/private-alpha-next` on
`codex/connected-budgets-implementation`. The policy gate is resolved. `budgets_implementation` owns the existing
implementation branch and commits the approved contracts before code. A bounded acceptance-setup writer prepared
canonical synthetic financial records and the reusable HTTP fixture script
without choosing budget behavior. `budget_acceptance_setup` completed that
bounded task as `4a28bfa0d`; the captain integrated it as `95d54dc7f`, verified
the real API/database and native reopening, then stopped the writer. The captain owns
scope, financial contracts, integration, acceptance, publication and readiness.
All agents have bounded outputs and are stopped after their handoffs.

### Budget acceptance and execution checklist

| User outcome | Inherited capability | Connected work | Observable acceptance |
| --- | --- | --- | --- |
| Create, inspect and edit a scoped monthly limit | Plan tabs, account/category catalog and versioned writes | Durable definition, visible scope/interval and canonical progress | Existing eligible expense 120 gives spent 120 and remaining 30 for a limit of 150; definition writes leave balances unchanged. |
| Spend, correct and refund once | Canonical recording/corrections/refunds | Shared spending reduction in Plan, Home and detail | Add 80 gives spent 200/over 50; correct it to 60 gives 180/over 30; refund 25 gives 155/over 5. Independently specified expectations, not reducer-generated values. |
| Exclude other activity and preserve cash truth | Transfer/payment, currency and forecast contracts | Scope and interval filtering | Transfers, card payments and other currencies/accounts/categories add zero; card purchases count; limit creates no forecast movement; unknown balances remain unknown. |
| Inspect contributors and return | Existing activity detail/correction and Search origin | Budget-to-activity/back and budget Search hit | Correct a contributing entry through its real screen; return to refreshed progress, same budget and preserved list/query/scroll context. |
| Reopen and recover writes | Owner-scoped write journal and receipts | Budget commands and persisted navigation | Relaunch retains definitions/current progress; interrupted committed responses replay once; stale versions fail without mutation; owner B cannot read or write owner A's budget. |
| Understand the same result in both languages | Native design, currency formatting and localization | Budget copy/controls and error states | English and Spanish screenshots and a short connected recording; month/zone boundaries, received-month negative refund and over-budget presentation verified. |

The bespoke delivery workflow follows poteto-mode Feature and figure-it-out.
These steps live here instead of a competing task board.

- [x] Read the poteto-mode principles and frame the completion predicate.
- [x] `how` over the affected subsystem.
- [x] `architect` for parallel design exploration.
- [x] Write the throughput checkpoint as four todo items.
- [x] Prepare reusable canonical-activity acceptance fixtures independently.
- [x] Resolve the financial policy gate and bind `budgets_implementation` as the
  sole contract, backend, native and test writer in its existing exclusive checkout.
- [x] Delegate code-writing to `budgets_implementation` in its exclusive worktree.
- [x] Verify on the matching surface with real API/Postgres and simulator.
  The final recorded rerun revalidates the contributor amount layout fix.
- [x] Sequence verified commits. Skip rebasing published/evidenced branches;
  repository one-way integration merges override Feature's rebase step.
- [x] Design follows the locked reference. No disputed contract requires another
  architecture round; the demonstrated contributor clipping received a focused fix.
- [x] Publish [PR #753](https://github.com/lagarcess/argus/pull/753). Full independent
  review and affected fixes are clean; terminal CI belongs to its exact-head audit.
- [x] Re-fetch integration, audit semantic overlap, reconcile one-way if needed,
  rerun affected checks and modularity budgets, then report merge readiness.

| Decision checkpoint | Evidence | State |
| --- | --- | --- |
| Preserve integration and existing demos | Fresh integration `9f51912198c2c77e239f670a2b3f78da2942afed`; prior demo guides below | New 590xx allocation and dedicated simulator created; no prior environment changed. |
| Keep one financial owner | Existing Recording/Planning contracts and the three bounded scout reports | Snapshot architecture selected; original policy approved by the founder. Contract commit `b60e416d3` precedes implementation. |
| Resume preserved local acceptance | Existing 590xx allocation and the [restart guide](../reports/evidence/connected-budgets/README.md) | Restored without reset or seed. Additive budget migration `278d94a8b` applied only to DB59002; all 15 baseline API readbacks still pass. The captain owns independent API acceptance; the sole writer owns backend/native/tests. |
| Continue independent acceptance preparation | [Fixture API/database proof](../reports/evidence/connected-budgets/fixture-api-proof.json) and [retained Home](../reports/evidence/connected-budgets/pre-implementation-home.png) | Five accounts/eight canonical activities remain after two setup runs; 15 real API readbacks and native Home reopening pass. One unknown balance remains unknown; DOP spending 140 and USD spending 50 stay separate. No budget progress is claimed. |
| Verify inherited connected access early | Isolated API `/health` returns healthy; local Postgres seeded with two synthetic users | Inherited registered sign-in, relaunch, sign-out and signed-out relaunch passed on the dedicated simulator against real local Auth/API/Postgres. Result `ui-20260930T001256Z.xcresult` is ignored local diagnostics. The inherited recording, Plan and Search baseline also passed 203 tests with zero skips against this lane's disposable Postgres. Budget implementation followed this inherited baseline; it is not budget acceptance. |

Completion requires the full assigned journey, durable visual/interaction evidence,
runnable restart instructions, green applicable CI, clean independent scoped review
and zero unresolved findings. Simulator verification is local delivery only;
physical-phone internet delivery remains pending under its separate owner.
The [budget environment restart guide](../reports/evidence/connected-budgets/README.md)
preserves the clickable mirror and synthetic records. The lane-owned local stack
is running with retained records. Backend and native implementation are integrated;
236 focused money/Plan/Search/budget checks pass against DB59002 with zero skips.
The full [independent review](../reports/evidence/connected-budgets/review-proof.json)
covered `538626c583c59aa5baa6c0fafb24aa95b779e893`; confirmed findings were fixed
at their shared causes and subsequent review covered affected deltas only. The
source review is clean through `ced256196c04eae6cfcd18f456f3dc00017315c7`.
Archive tolerates changed account eligibility while restoration validates scope;
contributor restoration waits for loaded rows. Native detail controls retain their
identifiers, contributor amounts retain all digits, and test locators address the
visible destination. The founder-approved fresh independent reviewer substitutes
for unavailable Codex capacity; no Codex-clean claim or paid review is made.

The complete native connected journey passes, including spending/correction/refund,
contributor position, budget edit/archive/restore, live Search/back, reopen and
Spanish presentation. The committed-response-loss test also passes: relaunch and
retry recover one canonical budget from the saved command. Durable images, the
short recording and [native proof](../reports/evidence/connected-budgets/native-proof.json)
record the source and scope. The recorded run revalidates the last amount
layout fix and financial lifecycle. Its preserved-query test setup was corrected;
the affected Home/Search/reopen/Spanish test then passed at `ced256196`. The ordinary demo uses direct API59000 after proxy acceptance.
[PR #753](https://github.com/lagarcess/argus/pull/753) retains publication,
applicable CI and the terminal exact-head merge-readiness audit. The first CI
attempt identified a stale generated OpenAPI artifact; regenerating it from the
canonical API passed all 23 compatibility checks. A merge-ready verdict requires
green applicable checks and zero unresolved findings at the published head.

Original base and freshly fetched integration both remain
`9f51912198c2c77e239f670a2b3f78da2942afed`; no reconciliation merge or semantic
overlap is required. The would-be merged tree passes modularity budgets. The PR
terminal audit records final fetch, exact head, retained evidence and CI state.
Personal budgets are locally assembled; physical-phone internet delivery remains
pending. The inherited full-owner snapshot is still the scaling limit. Other
Plan/MVEE outcomes remain in the coverage map; no additional slice starts here.

The [real API/database budget proof](../reports/evidence/connected-budgets/budget-api-proof.json)
records independently specified 120 → 200 → 180 → 155 spending, a limit edit to
160, four canonical contributors, scope/currency isolation, owner rejection and
accepted-response loss followed by one replay. Read-only SQL counts confirmed
one definition/activity per command. This proves backend assembly, not native
interaction or physical-phone delivery.

## PR #751 integration landing

The founder authorized merging approved head
`f753d5111876457c98be9ffe0235123dbf107eb9`, completing integration verification
and the necessary bounded landing-documentation PR. No next slice, deployment,
hosted configuration change or physical-testing environment change is authorized.

- [PR #751](https://github.com/lagarcess/argus/pull/751) squash-merged at
  `2026-09-29T22:46:19Z` as `5c143e642249872cd1d807a92dc4dd367c698671` onto
  unchanged integration `22f9c8cda8a65c74985e367d8cef68e55515e16b`.
  Approved-head and merge trees are identical. No reconciliation or semantic
  overlap arose; accepted native/API/visual evidence remains valid.
- Applicable PR CI and smoke are green; the independent affected-delta review is
  clean through `c775b0cdd1e05f4088fd9eb5d0ccf798d50882a4`, with only reviewed
  provenance documentation/media afterward. Zero unresolved threads remained.
  The [terminal audit](https://github.com/lagarcess/argus/pull/751#issuecomment-5900394900)
  records exact-head acceptance and review provenance.
- The canonical integration checkout fast-forwarded cleanly to the merge, with
  zero ahead/behind and passing modularity budgets. Exact post-merge CI, final
  landing-documentation PR and local/remote parity are recorded in the merged
  PR's final landing comment after those checks reach terminal state.
- No linked issues require closure. The configuration audit found no production
  environment variable, migration or hosted activation requirement. The added
  `ARGUS_TEST_SEARCH_QUERY` is an opt-in UI-test input; the existing local
  fault-proxy input remains test-only. Financial exposure remains default-off.
- The [Search demo, recording and restart guide](../reports/evidence/connected-search/README.md)
  remain usable from their existing checkout, API 58800 and loopback mirror
  58913. All older demos and the separate phone-testing checkout, device,
  signing, services and ports 58700–58749 remain untouched.
- This closes the assigned local Search journey, not physical-iPhone internet
  delivery or the whole MVEE. Remaining retrieval domains and the documented
  full-owner snapshot scale limit remain tracked below. No new slice starts.

## Connected Search on iPhone lane

**Founder authorization, September 29, 2026:** implement connected Search over
existing accounts, transactions and Plan expectations through a runnable local
simulator demonstration and a merge-ready PR. Local tests, commits, pushes,
publication and existing automatic Supabase PR previews are authorized. No merge,
deployment, hosted configuration change or paid-provider call. Documents,
household, web and chat-runtime work are excluded. Other MVEE retrieval types
remain in the complete coverage map; this batch does not claim to finish D10.

**Integration base:** freshly fetched
`22f9c8cda8a65c74985e367d8cef68e55515e16b`, including #749 and #750.
**Delivery branch:** `codex/connected-search`.
**Checkout:** `/Users/garces/.codex/worktrees/connected-search/private-alpha-next`.

**Goal and completion predicate:** search owned accounts, transactions and Plan
expectations; open each actual domain detail screen; inspect or edit using its
existing controls; return to the same query, filters, loaded results and scroll
position with edits reflected. Relaunch preserves the appropriate owner-scoped
search origin and reloads current records. Empty, loading, retryable failure and
unavailable/deleted destinations are explicit in English and Spanish. Completion
requires real API/Postgres and native acceptance, a short recording, restart
instructions, green applicable CI and one clean independent fresh-context review
(or an explicit pending verdict if no reviewer is available).

**Isolation:** Search owns local allocation `58800` (API), `58801` (Supabase),
`58802` (Postgres), `58805` (CAPTCHA bridge), `58913` (loopback simulator mirror)
and dedicated simulator
`01CBA853-5183-41AF-B1B8-024EF6DB8FFB` (`Argus Connected Search`). The physical-phone
owner's checkout, device, signing, certificates, services and ports 58700–58749
are untouched. Existing 584xx, 585xx and 586xx demonstrations remain intact.
Do not change global simulator-tool defaults shared with another agent.

### Search ownership and throughput

- **Blocking first steps.** Recover current source, locked Search design and
  financial/detail contracts. Record the bounded contract before implementation.
- **Independent workstreams.** Read-only backend and native scouts inspect
  distinct owners. The captain prepares the isolated local stack and simulator.
- **Shared mutable state.** One implementation writer owns the Search backend,
  native navigation and tests in the exclusive `connected-search-core` checkout
  on `codex/connected-search-implementation`. The captain owns the separate
  delivery/demo checkout and does not edit or run suites in the writer checkout. Detail editing keeps its existing domain owner.
- **Smallest safe decomposition.** One coherent implementation owner avoids
  dividing search identity, pagination and return-state behavior across agents.
  The captain takes over assembled verification after handoff. One independent
  reviewer inspects the finished diff, then affected fixes only.

The captain owns this manifest, contract decisions, integration, native acceptance,
recording, publication and readiness. `search_backend_scout` and
`search_native_scout` are read-only and finish after their bounded reports.
The implementation owner receives a consolidated scope and reports its changed
files, exact commit and focused verification before relinquishing the checkout.
No design/reviewer swarm or competing execution board is needed for this locked
surface. The existing account, activity and Plan services remain the only money
and persistence owners.

### Search acceptance

| User outcome | Existing capability | Connected work | Proof |
| --- | --- | --- | --- |
| Find existing financial records | Canonical account/activity/expectation storage; current text-search patterns | Owner-scoped typed search, bounded pages and type filters | Real Postgres and HTTP searches, corrections/current revisions, accents, literal query characters, pagination and second-owner isolation |
| Inspect and edit a result | Native account details, activity detail/correction and Plan expectation editor | Typed destination opens the existing screen with live authorization/read | Native search-to-detail/edit/back for all three types; balance rules remain domain-owned |
| Resume the same search | Native session lifetime and app navigation | Query/filter/result/scroll origin, current-request guards, refresh after detail edits | Native deep-scroll return, changed-match removal, pagination, relaunch and owner switch |
| Recover without losing context | Existing error/empty and localization controls | Loading, empty, retry and unavailable destination states | Local API failure/retry and missing-record cases; English/dark and Spanish/light recordings |

### Search execution checklist and decisions

- [x] `how` over the affected subsystem. Two bounded code scouts plus captain synthesis.
- [x] `architect` for parallel design exploration. Native and backend scouts compare reuse with domain-specific adapters; retain locked UI and existing detail owners.
- [x] Write the throughput checkpoint as four todo items.
- [x] Delegate code-writing to a subagent using your configured feature model. `search_implementation` owns the complete bounded implementation.
- [x] Verify on the matching surface. Five assembled Search journeys passed against the isolated real API/Postgres.
- [x] Preserve small, ordered commits. Skip rebasing published/evidenced work under repository policy; use ordered commits and one-way integration merge if needed.
- [x] No design contest arose; `interrogate` was not needed. Locked design and existing editors were retained.
- [x] Run **Opening a PR**. [PR #751](https://github.com/lagarcess/argus/pull/751) targets integration; no merge or deployment performed.

Model the Domain chooses typed financial destinations and one owner-scoped search
origin rather than independent booleans. Separate Before Serializing Shared State
chooses an exclusive writer, isolated stack and simulator. Prove It Works requires
the assembled native journey against real local records, beyond unit tests and
screenshots. The existing manifest is the specification and decision trail;
no additional planning board or housekeeping PR is part of this assignment.

September 29 contract checkpoint: existing `/search` returns conversation dossiers,
so financial retrieval gets a separate `/financial-search` adapter behind the
existing registered financial context. It reads canonical account, current logical
activity and expectation projections. Transfers appear once and corrected text
replaces old text. The client uses typed destinations, an owner-scoped search
origin and one shared presentation owner for existing detail/edit screens.
Category and currency filters narrow results without inventing bilingual domain
aliases or money calculations. The first implementation reuses the existing
owned financial snapshot; response pagination is bounded, but that snapshot
still reads the owner's records. No new search index or embeddings are implied.

September 29 local setup checkpoint: the Search-owned stack is seeded with two
synthetic identities, and native sign-in/relaunch/sign-out passed with Xcode exit
zero on its dedicated simulator. The local read-fault extension passed 19 focused
checks and preserves the inherited write-response-loss behavior. Its optional
proxy is 58812; normal retained builds use direct API 58800. The
[restart guide](../reports/evidence/connected-search/README.md) records commands
that preserve data. These setup checks do not claim connected Search acceptance.

September 29 backend checkpoint at `78e65a026`: 205 focused financial/Search
tests passed against the isolated local Postgres with zero skips. The real
Auth/API proof passed 15 checks covering current corrected activity, one transfer
hit, literal/accent queries, pagination, stale cursors, archived records, unknown
currency balances and cross-owner search/detail denial. Sanitized evidence is
[api-proof.json](../reports/evidence/connected-search/api-proof.json). Native
Search acceptance and independent review are recorded in the later completion checkpoint.

September 29 review checkpoint at `12ade77d98ac74864ad05ca629548be055e89452`: the
fresh-context `search_independent_review` agent returned clean after one full
diff review and affected-fix checks. Its three P2 findings are closed: retained
account navigation/read isolation, obsolete destination-request cancellation and
recovery tied to the acted-on account. Native model verification passes 20 tests.
The [review record](../reports/evidence/connected-search/independent-review.md)
records exact commits and limits. Assembled simulator gates and CI are still
in progress; this is not a merge-ready claim.

September 29 local delivery checkpoint: the complete assigned Search journey
passes in the isolated simulator against real local Auth/API/Postgres. Accounts,
current activity and Plan expectations open their existing editors; edits refresh
Search. Query, category, currency, loaded pages and exact position survive Back
and two successive relaunches. Separate Accounts/Search details and owner switching
pass. Delayed loading, 503/retry and unavailable detail states pass. The final
three-editor run at `c775b0cdd1e05f4088fd9eb5d0ccf798d50882a4` also verifies
English/dark and Spanish/light reopening. All confirmed independent findings are
closed; the final affected-delta review at that SHA is clean.

The [demo, recording, restart instructions and evidence table](../reports/evidence/connected-search/README.md)
are durable in this PR. The 49-second excerpt shows activity correction, refreshed
Search, Plan editing and reopening; the same successful test separately proves
account rename/removal from old matches. Backend evidence includes 205 focused
financial tests, 15 real HTTP checks, nine shared PostgreSQL CI scenarios,
23 generated-API compatibility checks and 22 native model tests. A missing generated
OpenAPI update found by CI was corrected. The PR's terminal readiness comment owns
its exact published head, final CI result and evidence revalidation.

Fresh integration remains `22f9c8cda8a65c74985e367d8cef68e55515e16b`, identical
to the original base: no reconciliation merge or semantic overlap arose. Final
modularity checks run on this already-reconciled tree. The local demo remains on
58800 with preserved data; all old demos and the 58700–58749 environment remain
untouched. Workers/reviewer have finished and relinquished their surfaces.

Remaining scope is explicit: physical-phone internet delivery is not proved by
this lane; Search still uses the canonical full-owner snapshot behind bounded
response pages. Other MVEE Search types and conversation continuity remain in
D09/D10 below. No new product deferral, hosted change or signing authority is
implied by this locally verified result.

Stop only for a concrete product conflict, inaccessible required tooling, or an
action beyond the grant. Routine implementation choices and local fixes proceed.

## Connected Plan and Home lane

**Original implementation authorization, September 29, 2026:** deliver commitments, recurrence,
fulfillment and the connected cash forecast as one local iPhone journey. Own
implementation, local builds/tests, commits, pushes and one reviewable PR with
existing automatic PR previews. No merge, deployment, signing changes, hosted
configuration, production data or paid-provider calls. Preserve both existing
584xx and 585xx demonstrations. Search, household, imports, web, voice and the
chat-runtime redesign are untouched. Budgets, savings goals and debt-plan
lifecycles remain assigned work in the complete MVEE map, outside this batch.

**Integration base:** freshly fetched
`21309f0832d438fd18651f47209e8c789a8fcc53`, containing #747 as `6eb057e9a`
and #748 as `21309f083`. **Delivery branch:** `codex/connected-plan-home`.

**Goal:** enter expected income and bills, including one-time and recurring
items; inspect the same dated, currency-separated forecast in Plan and Home;
record or link one canonical actual activity; inspect and correct that activity
or edit the expectation; reopen with the same durable state. A bill due before
later income must show the intervening shortfall. Expected money never changes
actual balances. The [MVEE connected-plan rules](argus-minimum-viable-ecosystem-experience.md#connected-plan-status)
and [locked design](../reports/mobile-design-lock-2026-09-28.md) own acceptance.

### Ownership and throughput

The captain owns shared contract decisions, this manifest, the delivery branch,
local simulator/backend integration, evidence, PR publication and readiness.
`plan_core` owns expected-record storage, recurrence, fulfillment/link rules,
forecast, backend routes, migrations, backend tests and canonical API/data docs.
A single native writer owns Swift types, transport, Plan/Home presentation,
localization and native model tests on a separate branch. The captain owns the
assembled UI tests and recording. Writers must not edit each other's files.

Start backend contract grounding alongside native design inspection and isolated
local verification setup. Agree the wire contract before dependent UI wiring.
Prove recurrence and canonical posting with real Postgres, integrate both
implementations, then verify the assembled journey. Keep one final independent
reviewer in a fresh context; review only affected fixes after that pass. Do not
request Codex review for this batch. If no independent reviewer is available,
publish with review pending instead of inventing a verdict.

The main risks are duplicate fulfillment, stale links after corrections, calendar
boundaries and inconsistent actual/forecast snapshots. Reuse the landed activity
service, owner locking, exact money types, revision checks, confirmation preview,
receipts, account observation coverage and native uncertain-write recovery.
No second balance or activity ledger is permitted.

### Acceptance and checkpoints

| User outcome | Inherited capability | Implementation in #749 | Responsible owner | Assembled proof |
| --- | --- | --- | --- | --- |
| Enter expected income and bills | Registered identity, account catalog, exact money input, native forms | Durable editable expectations; one-time, weekly, every two weeks, monthly and twice-monthly schedules | Core rules; native presentation; captain integration | Real API/DB and native create/edit/reopen; month-end, leap-date and zone tests |
| Understand cash before next income | Canonical account balances, unknown markers and locked Plan design | One dated forecast in Plan/Home, explicit accounts/currency, shortfall and partial-share rounding | Core projection; shared native Plan model | DOP 100 minus bill 200 before income 500 shows an interim shortfall; USD unknown stays unknown |
| Record receipt/payment or link existing activity | Landed preview/confirm and balance-check coverage | Atomic occurrence-to-activity link and matching review; no second ledger | Existing recording owner and Plan link transaction | Payment/correction plus existing-income link; duplicate/concurrent retries and rollback tests |
| Correct and continue | Append-only activity corrections and stable identity | Links re-evaluate actual revisions; expectation edits preserve fulfilled identity | Shared core link owner and native refresh | Correction 200 to 180 changes actual cash; expected 500 to 600 does not add a fulfilled receipt again; refund does not reopen bill |
| Reopen the assembled app | Keychain and owner-scoped pending-command recovery | Shared refresh, durable links and existing retry journal | Captain acceptance, native/core fixes as needed | Simulator relaunch and loaded second identity; retained demonstration, recording and API readback |

### Execution checklist and decision trail

- [x] Read the Principles section of poteto-mode.
- [x] Phase A: Frame. Recover approved rules, current integration, locked design and the bounded verification predicate.
- [x] Phase B: Design the workflow. Inspect inherited owners, settle the shared contract and assign isolated writers.
- [x] Phase C: Run the loop. Implement and verify bounded backend/native units, then integrate and exercise the whole journey.
- [x] Phase D: Keep the audit trail. Record technical decisions, ownership, evidence and limitations here as work progresses.
- [x] Phase E: Verify and hand back. Preserve a runnable simulator, short recording and restart recipe; publish one PR with applicable CI and honest independent review status.

This section is the lane specification and decision trail. It replaces separate
planning/checklist documents for this assignment. Poteto design panels and
reviewer swarms are omitted under the founder's explicit proportionality rule.
The backend owner's code-grounded proposal and captain's independent inspection
settle the contract. Final independent review is a separate fresh-context pass.

September 29 grounding: Plan is a sample destination today. Home already consumes
canonical financial position and monthly recorded activity. Keep those owners;
add expected records and derived occurrences without copying actual balances.
The new delivery checkout is isolated from the retained demos. No other MVEE
batch is activated and no new product deferral is introduced.

September 29 contract checkpoint: the [connected Plan API contract](../API_CONTRACT.md#connected-personal-plan-and-home-september-29-2026)
uses derived dated occurrences and one durable link to an existing canonical
activity. Fulfillment composes with the recording transaction under the same
owner lock. Activity amount/date corrections retain fulfillment; a changed
account or currency requires link review. Refunds never reopen a bill.
Schedule/account cutovers preserve linked occurrences; monthly dates clamp
without drifting, and duplicate month-end dates collapse to one occurrence.
Selected cash accounts and the saved IANA time zone are explicit. Forecasts
separate currencies, retain unknown balances, and order bills before income
on the same date as a conservative date-only assumption. The native app extends
its existing uncertain-command journal instead of adding another recovery owner.

The connected demonstration owns local allocation `58600` (API), `58601`
(Supabase), `58602` (Postgres), `58605` (CAPTCHA bridge), and simulator
`4E22655F-72DC-468F-AEBB-97FBDC58B514` (`Argus Connected Plan`). Synthetic
credentials remain ignored. The inherited app builds and the existing
sign-in/relaunch/sign-out UI acceptance passed with a clean Xcode exit on this
allocation. Existing `584xx` and `585xx` demos are intact.

### September 29 delivery evidence

[PR #749](https://github.com/lagarcess/argus/pull/749) contains the connected
backend, additive migration, native implementation and the
[runnable demonstration, recording and restart guide](../reports/evidence/connected-plan-home/README.md).
Plan and recorded Home derive from one repeatable-read snapshot. All actual
posting remains owned by the landed recording service. Included account shares
use that owner's minor-unit rounding; no second balance ledger exists.

- The assembled native journey passed: DOP 100 cash, a 200 bill before later
  expected income of 500, payment, correction to 180, an existing receipt of
  450 linked without duplication, expectation edit, and reopen at DOP 370.
  Weekly transport remains expected and does not change actual cash.
- Unknown USD stays unknown in Plan and Accounts. English/dark and Spanish/light
  presentation passed. Archived or retyped selected accounts remain removable.
- Real local HTTP acceptance: 16 checks passed after the clock fix, including
  refunds retaining fulfillment, changed-account link review and owner isolation.
  Financial/API/Postgres/OpenAPI matrix: 209 passed, zero skipped. Swift package:
  50 passed, four separately gated live tests skipped; native models: 12 passed.
- Interrupted-payment/relaunch acceptance passed with a clean Xcode exit:
  owner B saw neither A's records nor pending command; A retried the original
  committed payment once, with one activity and DOP 80 remaining. The
  [native acceptance record](../reports/evidence/connected-plan-home/native-acceptance.json)
  records each case and source checkpoint. Final-head CI and the terminal
  publication verdict are recorded in the PR audit.
- The independent fresh-context reviewer `plan_independent_review` reviewed
  `21309f08..196ccea2` once, found three confirmed issues, then returned clean on
  affected fixes at `ab1e3e63`. The UUID edit, proportional forecast and selected
  account fixes are recorded in the [review evidence](../reports/evidence/connected-plan-home/review-delta.md).
  The clock delta is clean at `36abc0bc`; keyboard focus is clean at `20750992`.
  This is the founder-authorized substitute, not GitHub Codex review.
- Original base and refreshed integration are both
  `21309f0832d438fd18651f47209e8c789a8fcc53`. Integration has not advanced;
  no reconciliation merge or semantic overlap invalidates retained evidence.
  Modularity passes on the would-be merged tree. Final publication head
  `a2b6ed2b` reached green applicable CI and local-smoke checks before merge.

**Remaining across the MVEE:** this delivers commitments, recurrence,
fulfillment and the connected forecast locally. Budgets, savings goals and
complete debt-plan lifecycles remain under D06. Physical-iPhone installation,
internet access, deployment and the rest of the coverage map remain incomplete.
No new deferral is introduced. Other MVEE lanes have not been activated.

**Visual follow-through:** preserve the locked quiet native hierarchy, dark/light
support, existing controls and icons. Plan chart points represent dated movements,
not equal time intervals; the readout names date/currency and the included accounts are listed below. Future polish
should tighten long occurrence lists and reduce repeated account/expectation copy
without losing the distinction between planned and actual amounts. This does not
reopen the web remake or authorize a broader redesign.

### PR #749 integration landing

The founder subsequently authorized merging the approved head and a necessary
docs-only landing PR after checks, with deployment and hosted configuration
changes still excluded. [PR #749](https://github.com/lagarcess/argus/pull/749)
squash-merged on September 29, 2026 at 19:52 UTC as
`88d513c0ef2791b4277eb571ce6b1f4f291d3a5c`, from approved head
`a2b6ed2bf849582de19aceedd61a3861d1c768e2` onto unchanged integration
`21309f0832d438fd18651f47209e8c789a8fcc53`.

- Integration had not advanced; no reconciliation merge was necessary. The
  approved-head and merge trees are identical, preserving all local acceptance
  and independent review evidence. No application behavior changed at landing.
- Applicable PR checks were green, the independent review was clean, and zero
  unresolved threads remained. The [terminal audit](https://github.com/lagarcess/argus/pull/749#issuecomment-5897315197)
  records the source checkpoints and review. Exact post-merge CI, the docs-only
  landing PR and final integration parity are recorded in the merged PR landing
  comment after their checks finish.
- There are no linked closing issues. The landing changes only this manifest
  and the integration ledger; it activates no other MVEE work.
- No production configuration was added. Financial exposure remains default-off
  in the existing environment template and Render declaration. The new
  `ARGUS_TEST_FAULT_URL` belongs only to the local recovery test launcher. The
  additive Plan migration is covered by local database and authorized automatic
  PR-preview checks; landing applies no hosted migration or configuration change.
- The 584xx financial loop, 585xx money-recording demo and 586xx connected Plan
  demo are preserved. The [recording and restart guide](../reports/evidence/connected-plan-home/README.md)
  remain the entry point for the runnable Plan simulator. Signing, physical-phone
  installation and internet delivery remain pending; budgets, savings goals and
  debt-plan lifecycles remain in D06. No deployment or main promotion occurred.

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
**Delivery branch:** `codex/personal-money-recording`; [PR #747](https://github.com/lagarcess/argus/pull/747).
**Goal:** a person uses the native app with the real local API/Postgres to receive
income, spend, move money between owned accounts, pay a card and record a refund;
Accounts and Home agree after inspection, corrections and reopening. Unknown
balances stay unknown, currencies stay separate, linked movements commit once
and together, and earlier activity respects each account's balance-check answers.

### PR #747 integration landing

The founder authorized merge of reviewed head
`5a997df3142dd9ca2d73207f8e4d8822705a646d` after green checks and zero unresolved
findings. It squash-merged on September 29, 2026 at 17:20:38 UTC as
`6eb057e9abe23ecbbfa0228b9ba0e57623d2f696`, onto unchanged integration
`b4fed10fe5cd325a7cd3e6ac21b87e9fbf5eb819`. The merge and approved-head trees are
identical; no reconciliation or intervening semantic overlap invalidates the
accepted financial, recovery, isolation or transfer-label evidence.

The [terminal PR audit](https://github.com/lagarcess/argus/pull/747#issuecomment-5895015807)
records green exact-head CI/smoke and the clean final scoped review. Exact
post-merge CI/smoke and final local/remote parity are recorded in the merged PR's
landing comment. The canonical checkout fast-forwarded cleanly to the merge.

This lands the locally verified personal recording journey, not physical-iPhone
or full MVEE delivery. The [demo and restart guide](../reports/evidence/personal-money-recording/ios/README.md)
and [transfer-label proof](../reports/evidence/personal-money-recording/ios/transfer-label-review/README.md)
remain available; local services, synthetic identities and both demos are
preserved. Existing visual-polish notes below remain open; no further MVEE
implementation is activated by this landing.

No linked issue requires closure. No new production environment variable or
tracked-template change is required: `ARGUS_TEST_RESPONSE_LOSS_PROXY` is an
explicit local UI-test switch, and the existing financial exposure flag stays
default-off. The two additive personal-money migrations are landed source only;
no hosted migration, configuration change, signing, deployment or main promotion
was performed. The original implementation grant above remains historical;
this separate founder merge authorization applies only to #747.

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

| User outcome | Inherit | Delivered locally | Owner / real dependency | Observable proof |
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
- [x] Phase C: Run the loop. Implement and verify the core and native journey in bounded units, then integrate on this branch.
- [x] Phase D: Keep the audit trail. Update this section with decisions, named owners, evidence and exact remaining work.
- [x] Phase E: Preserve the runnable simulator, recording and restart instructions. The terminal audit on [PR #747](https://github.com/lagarcess/argus/pull/747) owns exact final-head CI/review and the merge-ready verdict; this documentation does not waive those gates.

Current checkpoint: #747 is landed. All five recording kinds, inspection, corrections, balance-check
coverage and recovery passed assembled simulator acceptance against real local
Auth/API/Postgres. The [recording, retained accounts and restart guide](../reports/evidence/personal-money-recording/ios/README.md)
make the demonstration repeatable. The shared
[API contract](../API_CONTRACT.md#personal-money-activities-authorized-september-29-2026)
and additive storage contract are committed. The isolated 585xx stack and Argus
Personal Money simulator remain running; the earlier 584xx demo is preserved.
Workers have completed their bounded assignments and released the simulator to
the captain. This is local synthetic-user evidence, not physical-phone delivery.

| Named owner | Branch / exclusive surfaces | Next usable result |
| --- | --- | --- |
| `money_core` | `codex/personal-money-core`, recording domain, API, additive migration, backend tests, API/data contracts | Complete through `79032245`; five kinds, paired correction, refund rules, monthly Home, preserved legacy receipts and additive revision integrity. Final scoped core review clean |
| `money_iphone` | `codex/personal-money-iphone`, Swift feature/transport/models, localization and model tests | Complete through `3a6e5873`, integrated as `2e678d3d4`; 47 package cases with four expected environment skips and nine model tests. Scoped native review clean; simulator acceptance also verified the full-row tap fix |
| `money_demo_setup` | `codex/personal-money-acceptance`, connected UI tests, isolated launcher and new evidence; exclusive simulator owner | Complete through `5de47c00`; original seven native cases plus the strengthened isolation case passed, nine original retained accounts checked against canonical reads, recording and restart guide committed; simulator released to captain |
| Captain | `codex/personal-money-recording`, manifest, assembled source, independent proof and PR | Assembled source and independent HTTP proof complete; owns final CI/scoped review and retained local services; no merge |

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
the linked purchase without rewriting historical provenance. Changing a purchase's
category while refunds remain linked is rejected with explicit correction/unlink
instructions; historical categories are not silently rewritten. Currency conversion
and loan allocation remain outside the assigned operation set.

The captain's local response-loss proxy forwards to loopback only and drops one
successful activity response after the API accepts it. Five proxy checks pass.
Use it for assembled process-restart and same-key recovery proof, not as a substitute
for database atomicity and isolation checks. It does not change application behavior
or hosted configuration.

Backend verification includes 143 owner-run financial checks against the isolated
database, plus the captain's real Auth/API identity check. The HTTP proof covers
all five kinds, paired replay and inspection, wrong-account correction and history,
refund caps, positive card credit, unknown USD investment balance, cross-owner
refusal, durable reopening and refunds reducing received-month spending. The captain reran
[HTTP acceptance](../reports/evidence/personal-money-recording/http-proof.json)
against the assembled local API; its runtime source `062fd2aa8` is identical to
`2e678d3d4` across backend, migrations and the proof script.
The source-timezone and omitted-versus-explicit-null refund correction fixes passed
independent delta review. Reusing grouped activity reads reduced a synthetic
3,000-record projection from 2.598 seconds to 0.009 seconds without another cache.

The native review corrected terminal authentication propagation, rejected-recovery
explanations and retired-leg labels. A final delta review confirmed the Accounts
view observes the recovery state directly. The captain's combined local financial,
real Auth/API/Postgres, launcher and response-loss-proxy matrix passed 163 tests
with no skips. The canonical OpenAPI artifact has been regenerated; its 23
compatibility checks pass. The initial GitHub review at `b18050fcf` returned clean
with zero threads and CI at `2e678d3d4` passed. Final-head CI/review are recorded
in the PR terminal audit rather than duplicated as a moving SHA in this manifest.

[Native verification](../reports/evidence/personal-money-recording/ios/verification.json)
records the original seven selected cases plus a strengthened isolation case: row taps; income/spending/refund corrections;
paired transfer and wrong-account correction; card payment/refund/credit;
per-account reconciliation, currencies, unknowns and Spanish presentation;
committed-response loss with same-key recovery after process restart; and a
read-only Home relaunch; and pending-write isolation across loaded identities. The two fault-opt-in launcher tests also pass. Six long
cases logged terminal passes but Xcode stalled finalizing their result bundles;
they do not claim clean full-run exits. The final read-only run exited 0.
Screenshots and canonical readbacks independently preserve the observations.
The 2:55 recording is an explicitly edited demonstration, not the exhaustive test.

The final scoped GitHub review found the original native isolation assertion could
run before B loaded and had no pending A command. That claim is superseded by
`testPendingMoneyWriteRemainsIsolatedAcrossIdentities` (`3106f2f6`, integrated as
`b8aea0c0f`): a known B-owned account must load before absence assertions; an actual
committed-response-loss A command stays absent from B, survives the switch back,
and recovers once with the same record after reopening. This case passed in
232.846 seconds with a clean test-runner exit. The fix changes tests and evidence
only; no runtime defect was observed. Final CI and latest-delta review remain
owned by the PR terminal audit.

Application/backend source is unchanged after `2e678d3d4`; later commits add
acceptance harness, evidence and documentation. Exact source provenance is retained
in the evidence and revalidated against the final PR head. No physical phone,
founder identity, real production data, signing, deployment or paid providers were
used. Same-currency movements and chronological balance-check limits remain
explicit implementation boundaries. The full MVEE below is not complete.


### Founder acceptance and small clarity follow-up

The founder accepted the demonstrated financial behavior, then requested visible
**From / To** labels and removal of the redundant transfer-account heading before
merge. This follow-up changes only the native form presentation; recording rules,
records, API and migrations retain the accepted behavior. The existing English
and Spanish labels remain the single copy source. The focused simulator check
passed at `7a3bf64f`: English/dark and Spanish/light labels, both account menus,
reviewed transfer effects, existing correction labels and expense/card picker
regression checks. Both new-transfer previews were cancelled without confirmation.
The [clarity evidence](../reports/evidence/personal-money-recording/ios/transfer-label-review/README.md)
and final PR audit own verification. The later founder-authorized merge is recorded above.

Remaining visual polish is tracked here, not silently treated as complete or as a
new MVEE deferral. The native experience owner should review visible role labels
on the other compact selectors (card payment, income source, category and linked
purchase), plus spacing and long-account-name/larger-text presentation against the
locked design. The focused Spanish screenshot also shows the existing
`Transferencia` type chip partially clipped at the horizontal row's right edge;
review selected-chip visibility in that polish work. These are follow-up
presentation checks, not claims of financial defects or permission for a broader
redesign. This requested fix is limited to
transfer clarity; the full MVEE and physical-phone gates below remain unchanged.

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

## Cuadrao design dispositions

**Recorded October 1, 2026; founder requested consolidation and publication.**
This is the single follow-up register for the Cuadrao design session. Update
these entries here; design studies and checkpoint evidence link here instead of
maintaining competing queues. The MVEE still owns approved ecosystem scope and
technical contracts still own financial truth. These dispositions preserve future
design intent, outstanding connections and unresolved ideas; they do not assign a
new implementation lane, activate providers or change the connected delivery lane.
Existing MVEE requirements are not newly deferred because the preview is unfinished.

**Preserved preview:** branch `codex/cuadrao-design-scan-recents`, checkpoint
`72a41cb5ad6aaf4718bbce4da7bba987dd02dd99` (UI source
`91ba76c496444c07b28075303bdfcb47d8bc10fc`). The amount-entry checkpoint was signed,
installed and launched on the physical iPhone, installation sequence 3348;
[verification](../reports/evidence/cuadrao-native-design/plan-amount-input/verification.json)
records two native journeys. Installation is not full physical-interaction or
connected-financial acceptance. This section does not refresh the historical
integration/PR status elsewhere in this manifest.

Home structure/Spaces, first-use and household invitation previews, Search,
chat/temporary mode/Recents, voice interaction states and the personal/shared Plan
preview already exist. Profile remains an unfinished paused checkpoint; Novedades
remains a placeholder. [Design history](cuadrao-accounts-design-lock.md),
[Plan evidence](../reports/evidence/cuadrao-native-design/plan-social/verification.json),
[fixed currency](../reports/evidence/cuadrao-native-design/plan-currency/verification.json)
and [voice evidence](../reports/evidence/cuadrao-native-design/voice-simple/README.md)
retain what was actually built. Preview fixtures/local state are not durable
production records, real audio, real invitations or money movement.

### Follow-up ownership and disposition

C01–C10 identify this session's follow-ups under the existing D01–D15 work map,
not a parallel delivery team. Owners below are responsibility areas, not a claim
that a named worker has been dispatched. Link the assigned lane and its evidence
here when work starts. Close an entry only against its stated remaining gap.

| ID / topic | Disposition and existing baseline | Remaining work and closure evidence | Existing responsibility |
| --- | --- | --- | --- |
| **C01 — Scan and itemized bills** | **Future design locked; implementation unassigned.** Photo attachment, drafts, equal/custom amount splits and partial repayment previews exist. No receipt extraction or item selection exists. | Native capture and the receipt-review/split flow below; retain item corrections, interrupted drafts and exact share totals in Spanish/English evidence. Real extraction, storage and posting require the intake contracts. | Intake D08 + Planning/Home D06; Household D07 for shared access |
| **C02 — Shared plans and invitations** | **UI baseline preserved; connection outstanding.** Para ti / En grupo, trip estimates, recorded expenses, own share versus group total, shared savings, local invitation/guest preview and sample QR exist. Short-lived groups are distinct from durable Spaces. | Resolve group membership/guest access, link expiry/revocation, permissions and canonical expense/contribution/repayment ownership before connecting. Estimates must stay separate from actuals; repayments must not imply a bank transfer. Verify two participants, partial repayments, correction/recovery and no duplicate personal spending. | Planning/Home D06 + Household D07 + Financial core D03/D04 |
| **C03 — Forecasts and calculators** | **Preview built; canonical connection outstanding.** Spending-pace playground, low point, editable assumptions and goal/debt projections exist with illustrative data. | Reuse existing Argus forecast/calculation owners for Home, Plan and chat. Carry forward the Stake-style editable compound-interest assumptions and contribution/earnings curve as future UI work, with disclosed rate/cadence assumptions. Verify chart/readout agreement and actual versus projected values. Retain Apple Card-inspired explanations of upcoming payment and interest consequences as design input to the existing debt owner. A short contextual explanation may help; a blog/tips destination is not required. | Planning/Home D05/D06 + Conversation D09; domain series owners |
| **C04 — Voice and chat continuity** | **Interaction preview built; runtime outstanding.** Immersive/minimized voice, swipe-down, voice-choice carousel, short-message hold/lock/cancel/review, native dictation coexistence, temporary mode and Recents gestures are already previewed. | Connect xAI live voice through the existing chat brain; inherit agentic app actions only under D14 activation. Reuse existing Argus dynamic greeting logic. Resolve audio/transcript retention, Temporary context, actual provider voices/selection, interruptions and background/locked-screen policy. Verify one session across surfaces, draft recovery, mute/end, real capture and truthful progress. | Conversation/voice D09/D13/D14 + Native continuity |
| **C05 — Home, Accounts and household** | **Structure locked; detailed acceptance/connection outstanding.** Personal / Hogar / +, Movimientos / Próximamente, Ordenar Inicio, approved icons, cold starts and Personas-owned invitation status are preserved. | Finish Panorama meaning, realistic empty/unknown/loading/failure/long-content states and assembled account detail/correction/reconciliation presentation. Use existing financial semantics, including balance checks; do not invent another ledger. Connect household auth/install/acceptance/sharing/leave/remove flows under the MVEE. Inviting does not require an account first, expose private accounts or warrant a nagging Home banner. Verify relevant journeys and permission boundaries. | Planning/Home D05 + Financial core D02/D03/D04 + Household D07 |
| **C06 — Search, Files and Memory** | **Preview destinations preserved; remaining owner connections outstanding.** Keep Chats, Files and Memory alongside financial results. | Connect the authorized record owners, destination/reopen flows, filters and recovery. Respect permissions, Temporary exclusions and memory consent/retention. Search and Profile read the same owners; this is not approval for generic RAG or new memory storage. | Native continuity D10 + Conversation D09 + Intake D08 |
| **C07 — Profile and Updates** | **Profile polish paused by founder; Novedades not designed beyond placeholder.** Preserve identity/preferences and appearance/voice preview work already done. | Resume Profile hierarchy/child-page polish only when requested; connect auth/security, settings, usage, data controls, help/feedback and notification preferences through their owners. Design Updates around actual domain events with source links, avoiding duplicate invitation reminders. Verify language/accessibility and working controls, not static menus alone. | Native continuity D12 + Planning/Home D11 |
| **C08 — Identity and social discovery** | **Research/decisions outstanding.** Group covers and sample invitation QR are not profile-photo upload, live profile QR or contacts discovery. | Decide avatar/username/profile-QR scope and guest identity before implementation; validate QR legibility and scan reliability. Contacts matching needs explicit opt-in and a data/access contract. Native sharing can hand off a link to WhatsApp; no automatic contact upload or WhatsApp integration is implied. Keep this separate from required household membership and parked growth work. | Native continuity D12 + Household D07; founder for unresolved product scope |
| **C09 — Extra Plan refinements** | **Unassigned refinements/research, not promised capabilities.** Art, customization and gentle progress already inform Plan. | Exact target-date entry and personal cover photos remain refinements; group cover photos already exist. Forecast uncertainty bands require a valid model, not decorative precision. Habit/streak ideas need a helpful, non-punitive purpose. Rotating savings (“san” / Egyptian-style circles) remains research: sequence, missed contributions, custody and consent are unresolved. Existing shared savings does not implement a rotating pool or payouts. | Planning/Home D06; founder for additional scope |
| **C10 — Consistency and phone handoff** | **Ongoing acceptance/connection work.** Accounts and Plan now share typography roles and one money-editing implementation; their contextual layouts remain distinct. New plan/group amounts begin empty. A living Cuadrao guide and native reference gallery own consistency. Both plan/group currency choices are fixed at creation. | Preserve welcome/sign-in/recovery UI and connect it to the existing auth/session owner. Final branding/assistant mark remain unresolved. Verify shared styling, approved icons, navigation/edge blur, Spanish-first/English parity, long values, Dynamic Type, VoiceOver, Reduce Motion, light/dark and physical touch. Diagnose the retained unlocated keyboard invalid-frame warning before claiming it resolved. Adapt preview views to canonical owners through the existing delivery lane; retain separate identities and truthful device evidence. | Native continuity D01/D15 + Device/release; domain owners for money/input contracts |

### C01 — Native Scan and receipt split

Preserve **Escanear / Scan**, with Foto / Photo and Archivo / File as independent
entry points. The selected iOS capture component is Apple's native
[VisionKit document scanner](https://developer.apple.com/documentation/visionkit/vndocumentcameraviewcontroller).
Its page images feed the same interpretation/review path as uploaded photos;
PDF conversion is optional. Capture does not itself extract trusted financial
facts, approve a split or post an expense. The present chat Scan action is still
a sample-attachment preview.

The future receipt flow is **Scan/photo → review receipt → Por igual / Por consumo
→ select items → review each person's share**. Preserve capture-now/finish-later
drafts and the existing external repayment-tracking direction. Implementation
must account for editable receipt lines and quantities, shared items, visible
unassigned items and rounding so participant shares reconcile to the receipt.
Keep receipt tax/service charges visible and distinguish already-included amounts
from an optional added tip, avoiding double counting. Confirm corrections and
shares before recording; joining/selecting an item does not mark anyone paid.

**Currency is already locked, not new FX work:** choose DOP, USD or EUR when
creating the plan/group; it cannot change after creation. Group expenses, splits
and repayments inherit that currency. No mixed-currency reconciliation,
conversion or silent rate lookup. Receipt extraction must not silently reinterpret
a different printed currency as the group's currency; resolve that mismatch in
review before posting, with the exact interaction selected in the assigned slice.

Reference checked October 1, 2026:
[Apple's iOS 27 split-bill guide](https://support.apple.com/en-us/127565), published
September 14, 2026. It shows receipt review/editing, equal or item-based division,
shared quantities, tax/tip allocation and payment tracking through Apple Cash.
Use these interactions as a benchmark; Apple Cash's US payment rail is not part
of this UI-only preview. Do not assume Apple's receipt intelligence or Split Bill
is a public API reusable by Cuadrao. The native scanner and a future vision/OCR
provider are separate decisions. Extraction accuracy, supported receipt samples,
retention/access and canonical posting must be settled by the intake owner.

**Closure:** recording this gap closes the design-session disposition only.
It does not close C01 delivery. A later assigned slice must retain evidence for
capture/photo, corrections, equal/item/shared splits, included tax/service and tip,
rounding, draft reopen, recipient/organizer views and external repayment status.
No automatic collections, bank settlement or live sharing claim follows from
this decision.

### Cuadrao consistency pass and Home chart follow-up

**Expanded insights storytelling — UI implemented October 1:** source `e1b2a4d7`
implements the [locked design](../../.agent/designs/cuadrao/DESIGN.md#locked-home-and-expanded-insights-direction--october-1-2026):
Title-sized period headings, explicit empty/incomplete-history states, calendar-week
month buckets, a factual chart takeaway and up to two highlights below categories.
Category-change and largest-expense cards open their supporting local records and
preserve the selected period on return. A shared native gesture surface rejects
vertical chart/distribution pans before recognition, preserving page scrolling.
Comparison eligibility derives from an explicit preview history window, never the
first transaction date; unequal elapsed month lengths suppress the comparison.
47 deterministic checks and the affected native journeys pass; empty months,
missing coverage, bounded paging, inspection, highlight records, distribution
scrolling and large English text were exercised. Compact Home stays quiet.
[Evidence and phone handoff](../reports/evidence/cuadrao-native-design/home-activity/README.md#spending-highlights-follow-up)
record source revalidation and screenshots. This is UI-only preview delivery.

Connected highlights remain with Planning/Home and the financial-record/history
owner: supply coverage-aware period comparisons and traceable supporting records
from the canonical spending/position owners. Never infer complete coverage from
an earliest transaction or derive expenses from balance changes. These requirements
extend the connected disposition below, not a separate insight service or roadmap.

**Home activity refinement — October 1:** the UI preview now removes the greeting
date and space-plus background, uses accepted household avatars above the amount,
and adds Balance / Activity to expanded insights. Compact period and chart controls
share a row; visible paging chevrons and Back to today are removed. The final
founder correction places the period label left and Balance / Activity right above
the amount, with date ranges for week/month and the year for annual views.
Swipes and VoiceOver period actions remain bounded. Expenses derive from the local
activity list with typed categories, one currency and one space; category bars,
period distribution and expandable rows share those records. Historical assets use
matching recorded snapshots, not current amounts relabeled as past values.

**Connected disposition:** the financial-record/history owner must supply durable
expense category identity, original currency, coverage/provenance and dated account
snapshots before this preview becomes live insights. Exclude transfers/income,
retain archived-account spending, and compare equivalent elapsed periods only when
coverage supports the comparison. Household identity must derive avatars/counts from
accepted membership, with photos optional and invitation states excluded. These are
part of existing Financial Core / Household delivery, not a new parallel roadmap.

The populated design fixture uses one shared calendar window from the start of
the previous year through yesterday. Sparse varied spending includes recurring
bills, quiet days and occasional larger purchases; account history lists render
lazily. It supports a complete previous-year view without filling every day with
repeating category stacks, adding future observations or changing current balances.


Founder assigned the four-point native UI pass on October 1: a living
[Cuadrao guide](../../.agent/designs/cuadrao/DESIGN.md), shared typography roles,
one Accounts/Plan money editor with empty creation amounts, and a native reference
gallery. Existing account layouts, navigation, art and interaction meanings remain
preserved. This is preview work; connected root/session/model owners are unchanged.
The four pieces are implemented at `53285d59`; [verification and screenshots](../reports/evidence/cuadrao-native-design/consistency/README.md)
record the focused native checks, shared-behavior checks and phone handoff.
This does not close remaining C10 connected-delivery/accessibility work.

**Home chart UI, C05/C03:** the founder authorized the follow-up on October 1.
The native preview now shows a compact recorded-position chart (one month by default) with
separate currencies, native tap/hold-and-drag inspection, Hoy/Today reset and
Personal/Hogar scope. It shares the amount's debt/asset ownership calculation.
Example-observation provenance is retained in preview evidence; missing history
produces an empty state. No current activity is reverse-engineered into financial history.
References: [Monzo selected balance](https://mobbin.com/screens/25125eda-5e62-4166-9a68-9b25bcc349b6)
and [Apple chart selection](https://developer.apple.com/videos/play/wwdc2023/10037/).

**Home exploration follow-up (UI only):** compact neutral greeting from the shared
preview profile; Evolución / Distribución swap history and a flat asset breakdown
in one block. Native range controls cover one month, three months, this year and
all history; an expanded sheet isolates a recorded calendar month. Category rows
reveal accounts on demand. Negative contributions/debts remain separate from the
positive asset bar; currency conversion remains absent. Example history is extended
for design review, never inferred from activity. The same contribution owner powers
history, current net position and distribution. This is a review iteration, not a
connected history implementation or a promotion of the paused Profile redesign.
Source checkpoint: `73ae78ec`; [screenshots and verification](../reports/evidence/cuadrao-native-design/home-perspectives/README.md).
Physical iPhone installation and launch succeeded. This delivered iteration is
superseded by the founder-approved direction below; it is not acceptance of the
final Home/insights design.

**Founder design lock, October 1 — UI implemented:** the
[Cuadrao design guide](../../.agent/designs/cuadrao/DESIGN.md#locked-home-and-expanded-insights-direction--october-1-2026)
owns the quiet Home / expanded insights hierarchy and decomposable bar. Source
`2c5cf23b` implements available-history Home ranges, full-screen calendar paging,
short recorded-balance takeaways, proportional dimensional segments, category/account
rows and return-to-whole. Positive-assets percentages share one denominator;
negative balances remain separate. Spanish/English, larger text and Reduce Motion
are supported. Preview provenance stays in evidence rather than Home copy.
The earlier paused calendar experiment is superseded by this implementation.
[Verification and phone handoff](../reports/evidence/cuadrao-native-design/home-insights/README.md)
record checks and their limits. This is UI-only; canonical connected history,
provider/analytics integration and production promotion remain outside this delivery.
Typography follow-up `9e64509f` restores compact system distribution rows and
shared rounded money/percentage styles; [focused proof](../reports/evidence/cuadrao-native-design/home-insights/typography/README.md)
records the unchanged interaction checks and updated visual review.

**Distribution-to-account continuity, UI only:** `a01629f1` connects each expanded
account row to the existing account detail, including shared rename/record/archive
presentation. Back keeps the expanded category and scroll position, and edits read
from the same account model. [Round-trip evidence](../reports/evidence/cuadrao-native-design/home-insights/account-connectivity/README.md)
records native verification and physical-phone handoff.

**Home/Plan consistency polish — implemented, UI only:** source `034ae234` plus account-row correction `3b04bc23`
delivers the founder-approved reconciliation. The
[Cuadrao guide](../../.agent/designs/cuadrao/DESIGN.md) owns the shared rules and
component owners; [verification and phone handoff](../reports/evidence/cuadrao-native-design/consistency-polish/README.md)
retain the native checks and screenshots.

- Plan keeps Para ti / En grupo. Forecast month is quiet text, its space choice
  stays local, and a new plan defaults from the explicit plan-list scope or Personal,
  never from the forecast. Exploration is a secondary link.
- Shared current-value/chevron labels and selected checkmarks reconcile Tus planes,
  space and currency controls. Fixed currency stays static. Short native menus and
  searchable currency catalogs retain their distinct roles; no conversion is added.
- Expanded history uses icon view controls, compact localized periods, neighboring
  card edges and bounded previous/next controls. Scrubbing and paging stay distinct.
  Current distribution hides historical controls and says Activos · Hoy / Assets · Today;
  history restores its chosen period on return. Compact Home remains quiet.
- Home keeps matching trailing plus shortcuts for Cuentas and Movimientos, removes
  the accounts ellipsis, and adds reorder to the account hold action. The Cuentas
  heading opens a native management destination with visible ordering and archive
  recovery, including when every account is archived. Existing account detail actions
  remain available. The shared gallery shows the actual new controls.

Nine native checks passed; the final account-row adjustment adds a passing two-case
reorder/recovery and large-English verification. Fixed-currency creation, group
split/repayment and forecast checks are retained from the prior passing batch on
unchanged owners. iPhone build 3402 installed and launched (sequence 3412).
This checkpoint does not authorize connected history, providers, analytics or a
production release. Remaining work stays in the dispositions above and below.

**Plan and Home collection simplification — UI-only implementation, October 1:**
the Cuadrao guide supersedes the two-space-selector layout at `ebcc9760`.
Removed the standalone month, Tus planes filter, header ellipsis and duplicate
creation button in populated groups. Forecast-local space selection, all personal
plans with metadata, contextual creation and separate archive recovery now share
the existing owners. Preview tools live in the title hold menu.

`CuadraoOrderedCollection` gives Home accounts, personal plans and groups one
vocabulary: tap detail, leading Edit (including rename), trailing Archive with full
swipe disabled, hold-and-drag ordering in place. Collection context menus and the
account action tray are removed. Native iOS 27 containers own gesture arbitration;
iOS 17–26 retain native drag/drop and explicit actions. Accessibility move actions
and account management handles remain available. Order does not move records
between spaces or change financial history. Fixture account order and saved
plan/group order survive reopening locally.

Group People owns invitations and member management, reached through avatars or
the People segment. The local member scenario hides organizer controls. Removal
requires a review, blocks outstanding balances, excludes former members from new
expense defaults and retains historical participants and entries. C02 still owns
real membership/guest access, authorization, retention and invitation delivery.
The preview's role switch is not an authorization implementation.

**Verification checkpoint:** native UI tests for the ten focused journeys passed,
plus 50 group and 58 Plan state checks. See the [durable collection evidence](../reports/evidence/cuadrao-native-design/collection-gestures/README.md).
Final UI source is `0cba90ba` (implementation `a136c0af`); phone build 3404 was
installed on Sr.Garces i15, iOS 27.0.1 (installation sequence 2088). Final launch
was blocked by the locked phone; build 3403 had launched before the final icon-only
correction. Open Cuadrao Preview after unlocking to inspect build 3404. The icon-only native swipe controls preserve localized
accessibility labels and avoid truncated captions. Physical gesture/VoiceOver
acceptance remains distinct from simulator automation and installation proof.

**Connected ordering disposition:** before connection, persist personal/viewer-local
order through its canonical owner, including sync/conflict behavior. Group ordering
must not silently reorder another member's view or alter shared financial records.
Physical touch/VoiceOver acceptance and older-runtime behavior remain device
acceptance work; simulator and state evidence describe their exact tested scope.

**Future surface-connectivity pass — founder requested, not yet executed:** audit
Home, Plan, Accounts, Chat and Search for meaningful row/action destinations,
return paths, preserved space/currency/selection/scroll/draft context, and stale or
unavailable records. Reuse existing destination and state owners. Include chart
inspection consistency: Home's preview has sparse observations (3–4 days recently,
weekly further back), while Plan's example has daily points. Distinguish data
resolution from gesture feedback; do not invent recorded daily balances to make a
sparse history feel smoother. Set connected-history sampling and any explicitly
labeled interpolation through the canonical series owner. No blanket navigation
rewrite, provider work or new history store is assigned by this follow-up.

**Future beta experiment — not activated:** after the approved bar experience is
usable, consider PostHog assignment in a reviewed TestFlight build: bar baseline
versus donut, holding category rows, values and interactions constant. Define the
hypothesis, stable assignment and exposure before launch; evaluate comprehension,
account-finding success and preference, not raw taps or dwell time as success.
Use qualitative feedback for a small cohort; do not declare a statistical winner
without sufficient evidence. Do not send amounts, account names or transaction
details in experiment events. Apply existing analytics/data-control contracts,
accurate privacy disclosures and reviewer access to both bundled variants. No SDK,
event changes, flags, hosted experiment, TestFlight upload or rollout is authorized
by this design discussion. [Apple review rules](https://developer.apple.com/app-store/review/guidelines/)
and [PostHog iOS experiments](https://github.com/PostHog/posthog.com/blob/master/contents/docs/libraries/ios/usage.mdx).

**Still future:** connect canonical recorded-balance observations with clear date,
account-membership, currency, valuation and ownership semantics; distinguish
recorded position from spendable cash. Home's Plan link opens the existing Plan
surface, not a forecast derived from Home or a currency/scope-matched deep link.
A future shared forecast owner must supply forecast values before Home can draw
a dashed projection. Preview UI approval does not authorize a new financial store,
backfill, calculation engine or provider integration. Verification and phone
handoff: [chart evidence](../reports/evidence/cuadrao-native-design/home-chart/README.md).

### Handoff and upkeep

The founder reported sending the existing read-only VM reuse-map prompt; this
session has no returned handoff to accept. Treat the
[VM prompt](../reports/cuadrao-vm-handoff-prompt.md) as an assignment artifact,
not a second roadmap or permission to launch a duplicate worker. Refresh its
checkpoint and integration references when reviewing its output.

Dated reports remain evidence of their exact source/build. Their old “next” or
“remaining” statements are historical, including earlier chat/Plan placeholders,
the removed voice pill, pre-Scan labels and earlier installation limitations.
Use this register for follow-up status, link new proof here, and preserve the
original observations rather than rewriting history into a shipped claim.

## Work map

### Complete MVEE coverage

The [MVEE scope checklist](argus-minimum-viable-ecosystem-experience.md#13-complete-scope-checklist)
is the requirement index. Read each linked source for the user outcome and its
expected behavior; this table stores execution metadata only. D01-D15 are work
identifiers, not a second specification. A row's next integration task and planned
evidence are not an exhaustive scope or a substitute for the linked requirement.

**Connected-delivery phone evidence at the historical lane snapshot:** none of the assembled outcomes is verified on the
founder's physical iPhone. Reuse and gaps below include landed #745 and the
landed personal recording, Plan/Home and Search journeys. Those local batches are complete; their owners and evidence are recorded above. Connected personal spending budgets are landed through PR #753; its terminal audit and landing record retain the local evidence. Connected personal savings goals are locally verified through the complete journey and are published in [PR #755](https://github.com/lagarcess/argus/pull/755), under
the founder-approved account-backed allocation policy. Proposed owners must be bound to named
workers at dispatch. D14 follows the linked runtime
sequence rather than a separate deferral policy in this document.

| Canonical user outcome / work ID | Inspected reuse | Next integration task | Proposed owner | Execution dependencies | Evidence to collect against the linked source |
| --- | --- | --- | --- | --- | --- |
| [Access][mvee-access], D01 | Argus auth/recovery; Swift session/Keychain | Finish native/hosted auth adapter and guest conversion | Native continuity + Device/release | Identity API; signing/hosted access for phone proof | Physical-device auth recordings and session/identity test results |
| [iPhone experience][mvee-platforms], D15 | Native shell; localization; design archive | Replace sample destinations with connected modules | Native continuity | Domain reads per destination | Device navigation/accessibility recordings against [native quality][mvee-quality] |
| [Accounts and assets][mvee-accounts], D02/D04 | Landed #745 native account/opening lifecycle and real local API | Extend saved assets and ownership/space behavior; verify existing lifecycle on the phone after deployment/signing approval | Financial core | Existing account contract; D03 history; D07 for sharing | Device lifecycle recordings and persisted account/asset readbacks |
| [Activity][mvee-activity] and [refunds][mvee-refunds], D03 | #745 expense/correction core; landed #747 five-kind manual entry, paired correction/history and refunds | Local assembled acceptance and scoped review passed; authorized phone proof remains; intake, household and agentic adapters retain D08/D07/D14 owners | Financial core | Account identity; shared posting contract | Device entry/correction recordings plus atomicity, retry and concurrency tests |
| [Reconciliation][mvee-activity], D03 | #745 immutable balance checks and coverage; #747 per-account paired coverage; [handoff cases](argus-account-balance-reconciliation-handoff.md) | Paired coverage/recovery passed locally; authorized phone verification remains; checks before the latest observation remain an explicit technical limitation | Financial core | Account/activity identity | Replay the handoff cases on the candidate; retain before/after reads and relaunch evidence |
| [Home][mvee-home], D05 | #745 known/unknown positions; #747 monthly actuals; PR #749 landed locally verified commitments and dated cash forecast | Complete remaining approved Home contexts/chart/destinations through their owners; verify assembled Home on the physical phone | Planning/Home | D02/D03 position; D06 forecasts; D04/D07 contexts; D08 resume | Phone walkthrough with source-record/read-model comparisons |
| [Plan][mvee-plan], D06 | Existing calculators; locked design; PR #749 landed locally verified commitments, recurrence, fulfillment and forecast | PR #753 landed locally verified personal monthly budgets with actual progress, contributors and Search; PR #755 landed locally verified personal savings goals with approved account-backed allocations and retained native/API/database evidence; debt-plan lifecycles, shared variants and physical-phone proof remain tracked | Planning/Home | Financial posting/link contract; D07 for shared variants | Device plan lifecycle recordings and linked-record/forecast readbacks |
| [Spaces][mvee-spaces] and [account moves][mvee-moves], D04 | Personal default in account model; design reference | Implement space lifecycle and account-move service | Financial core | Account identity; affected domain links | Device move/recovery recordings and linked-record identity checks |
| [Household][mvee-household], D07 | Existing identities; selected invitation direction | Implement membership, permission adapters and invitation delivery | Household | Identities; affected domain adapters; open policy decisions | Two-user device journeys and permission readbacks across consumers |
| [Intake][mvee-intake], D08/D03/D13/D14 | Manual account entry; synthetic review/retry kit | Build production source/review pipeline and shared posting adapter | Intake | File/provider policy; D03 confirmation; D07 shared sources; D14 language actions | Authorized sample corpus runs, source-preview recordings and interrupted-import readbacks |
| [Argus][mvee-argus], D09 | Existing runtime/SSE/tools and persisted artifacts | Connect native conversation client and authorized context adapters | Conversation/voice | Existing APIs; relevant domain reads; live-provider authority | Phone conversation replay and persisted artifact/evidence comparison |
| [Voice][mvee-voice], D13 | Existing conversation services; selected provider direction | Integrate audio transport with the existing conversation path | Conversation/voice | Audio policy/provider grant; D14 only for financial actions | Device speech/cancel/recovery recordings and latency/cost receipts |
| [Search][mvee-search] and [conversation continuity][mvee-continuity], D09/D10 | Omnisearch/history and recovery contracts; locally verified account/activity/expectation Search in #751 | Deliver remaining MVEE domain retrieval and conversation lifecycle continuity; retain the connected Search origin contract | Native continuity + Conversation/voice | Authorized domain reads; Temporary policy for that behavior | Search-to-destination/back recordings, draft/history readbacks and Temporary retention evidence |
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
