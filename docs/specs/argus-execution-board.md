# Argus private iPhone execution manifest

**Updated:** September 29, 2026.
**Execution state:** PLANNING ONLY. Implementation remains STOPPED. No worker dispatch or hosted changes are authorized.
**Product owner:** [MVEE](argus-minimum-viable-ecosystem-experience.md).
**Authority and onboarding:** [DOCUMENTATION_AUTHORITY](../DOCUMENTATION_AUTHORITY.md).

**Preservation authorization:** The founder accepted this expanded plan for
commit and push on September 29, 2026. This authorizes documentation preservation
only, not implementation, worker dispatch, merge, deployment or hosted changes.
Recovery branch: `codex/mvee-iphone-delivery-plan`.

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
Execution remains stopped until the one restart authorization. That authorization
covers continuous delivery across the full non-deferred scope below, not only the
first demonstration. Record named owners and each consumed technical contract
before implementation of that dependency. Routine progression does not require
new batch approvals. No 24-hour delivery promise has been made.

## Verified starting point

Refreshed by fetch on September 29. Current integration is
`12bccd4d6e173a5d8805e495fd30b7ead36741c6`, the #743 merge. The original
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
  broad D rows. All 17 MVEE checklist areas now have explicit delivery/proof rows.
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

**State remains stopped pending one explicit founder restart.** The first usable
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
7. Prove reconciliation against the existing
   [balance handoff](argus-account-balance-reconciliation-handoff.md). A checked
   balance and later entry of already-included activity must not subtract the
   same money twice. A genuinely later expense must change the balance. Corrections
   must preserve that distinction and history. An unknown balance must never
   become a calculated zero merely because activity exists.

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

This is the single coverage table for all 17 areas of the
[MVEE scope checklist](argus-minimum-viable-ecosystem-experience.md#13-complete-scope-checklist),
its detailed sections and the explicit runtime exception. Each row includes the
full behavior of its linked requirement, not only the examples in the cells.
D01-D15 remain stable work identifiers. Split rows share their existing ID;
they do not create competing requirements or plans.

**Current phone evidence:** no assembled outcome is verified on the founder's
physical iPhone. Inheritance below means landed code, existing product contracts
or explicitly labeled preserved/prototype work. It does not imply native or
current hosted acceptance. Every implementation row is stopped until restart;
D14 alone carries the explicit runtime deferral. Owners below are accountable
roles to bind to named workers at dispatch, not a claim of running agents. The
captain owns delivery of every row; domain leads own the complete connected
outcome with native implementation support.

| Complete user outcome and MVEE owner | Existing capability to inherit | Remaining implementation and connection | Proposed owner | Actual dependencies | Proof in the assembled app |
| --- | --- | --- | --- | --- | --- |
| **Access, D01.** Use existing identity; sign in, register, confirm/resend, recover/reset, refresh/relaunch, switch/logout; use guest chat and register with return to action. [Guest boundary](argus-minimum-viable-ecosystem-experience.md#guest-access-and-registration) | Existing Argus/Supabase auth and recovery; landed Swift session/Keychain package | Hosted CAPTCHA and callbacks, complete native access flows, guest transfer and registered-only financial enforcement | Native continuity + Device/release | Existing identity/API; signing and hosted grants for phone proof. Core finance does not wait for every access case | Complete each access path on phone; relaunch/expiry/offline recovery; account switch reveals no prior user's facts; guest cannot persist finances |
| **iPhone experience, D15.** Navigate Home, Accounts, Argus, Plan, Search, Updates and Profile with locked design, English/es-419, persistent themes and accessibility. [Platforms/design](argus-minimum-viable-ecosystem-experience.md#2-product-character-and-platforms) | Native shell, localization/session foundations; September 28 design archive | Connected navigation/state, concise copy and activity icons; keyboard, safe areas, glass/motion and accessible controls; no sample values masquerading as real data | Native continuity | Domain reads per destination, not completion of all destinations | Demonstrate all destinations, correct Back paths, theme/relaunch, enlarged text, VoiceOver, reduced motion and keyboard behavior on phone |
| **Accounts and assets, D02/D04.** Maintain cash/bank/investment/card/debt accounts and optional property/vehicle/other assets with dates, terms, estimates, ownership shares and linked debt. [Accounts](argus-minimum-viable-ecosystem-experience.md#accounts-organize-the-financial-facts) | Landed account/opening contract with exact money, unknowns, revisions, retries and owner isolation; unfinished iOS client | Finish simple setup/detail/edit/archive/restore and appropriate debt metadata; value updates, shares, linked debt and canonical totals; archive retains money/history | Financial core | Existing account identity; activity history from D03; D07 only for shared variants | Create known/zero/unknown values; change estimates/share; archive/restore without changing totals; debt counted once; relaunch retains identity and history |
| **Activity, D03.** Record expense, income, transfer, payment and refund; categorize, annotate, correct, remove, undo and restore linked movements. [Activity/refunds](argus-minimum-viable-ecosystem-experience.md#account-activity-and-balance-checks) | Shared recording domain, money precision/sign conversion, opening revisions and concurrency safeguards | Durable atomic activity and linked legs; fixed category identities/localized renamed labels; 200-character notes; partial/unlinked refunds, card credit and principal/interest distinctions | Financial core | Existing account contract; native feature client consumes its shared posting API | Exercise every activity type, partial refunds and both transfer legs; retries/stale edits cannot duplicate or overwrite; corrections/restoration update all dependent views |
| **Reconciliation, D03.** Compare recorded/observed balances, resolve gaps and earlier activity or statement overlap without invented income or double money. [Balance handoff](argus-account-balance-reconciliation-handoff.md) | Opening-balance history and exact arithmetic; approved behavior cases | Observation/adjustment lineage, per-account inclusion review, preview/concurrency, missing activity and incomplete-coverage reads | Financial core | Account/activity identity and authoritative observation/inclusion contract | Check balance, add already-included earlier expense, add later expense, correct/remove/restore; verify correct balances/history after relaunch; unknown prior value never yields a fabricated difference |
| **Home, D05.** Understand position, change and upcoming cash needs; record or resume review. [Home](argus-minimum-viable-ecosystem-experience.md#home-understand-where-i-stand) | Locked populated design; account facts; chart prototype only | Canonical assets/debt/net worth by currency, freshness/unknowns, recent activity, account preview, commitments, expected/received income, forecast and dated shortfalls | Planning/Home | D02/D03 for position; D06 for future cash; D04/D07 for applicable contexts; D08 for import resume | Expense/correction changes Home and Accounts together; show incomplete data honestly; detect earlier shortfall despite positive period end; drill into source and resume interrupted review |
| **Plan, D06.** Maintain budgets, goals, debt plans, recurring/occasional commitments and variable income; record actual progress. [Plan](argus-minimum-viable-ecosystem-experience.md#plan-decide-what-i-want-to-change) | Existing grounded calculators and locked plan design | Durable plans, funding/dates, recurrence, allocation and expectation-to-actual matching; manual scenario-to-plan flow and correction propagation | Planning/Home | Financial actual-posting/link contract; Household only for shared plans | Create each plan type, fulfill/link activity, refund/correct/remove/restore; no duplicate allocation or cash subtraction; projected and actual progress remain distinct |
| **Spaces, D04.** Organize Personal, private Business/Custom and Household contexts; manage lifecycle and account moves without lost history. [Spaces/moves](argus-minimum-viable-ecosystem-experience.md#financial-spaces) | Personal default in landed account model; locked UI behavior | Private-space persistence, unique recoverable names, archive/restore, empty-only delete/undo, permanent Personal, account moves and linked-record review | Financial core | Account identity/history; affected plan/document/household link contracts for moves | Move and move back with original IDs/history; preview affected links; preserve archived search and obligations; reject nonempty deletion; no move changes money or grants sharing |
| **Household, D07.** Invite a partner, explicitly share/edit/jointly own records and plans, contribute privately, revoke or leave safely. [Household](argus-minimum-viable-ecosystem-experience.md#12-household-collaboration-approved-minimum-capacity) | Existing independent user identities; selected do-blitz link and Resend email direction, not a working integration | Invitation expiry/accept/revoke; membership/edit/visibility contracts; joint facts, shared plans and source-document visibility; leave/remove/retention behavior | Household | Existing identities; affected domain adapters. Editing/departure/retention decisions remain required | Two authorized people invite/accept/share/edit/revoke/leave; shared records update both; no duplicate joint money or private-source disclosure in totals, chat, files, search, updates or export |
| **Intake, D08 plus D03/D13/D14.** Capture manually or through supported statements/files/images/photos/scans; review, correct, confirm and resume. [Ingestion](argus-minimum-viable-ecosystem-experience.md#4-information-ingestion-one-destination-several-entry-methods) | Manual account entry; synthetic review/retry kit only | Production PDF/structured-file/image paths, extraction, actual previews, destination/date/currency review, uncertainty/duplicates, batch confirmation and resume; evaluate native scanning/share-to-app/preprocessing. Typed/spoken financial proposals map to D14 | Intake | File/OCR/size/password/retention decisions; D03 for confirmation only; D07 for shared sources; D14 for financial language actions | Authorized samples traverse actual preview/extraction/review/confirmation; interrupt/resume/reconfirm without duplicates; reject unsupported/unreadable files clearly; retain manual fallback and hide unshared pages |
| **Argus, D09.** Ask finance questions, research, calculate, compare, simulate and revisit evidence; use permitted recorded context. [Argus](argus-minimum-viable-ecosystem-experience.md#argus-ask-understand-and-get-things-done) | Existing single runtime, SSE, calculators/research/backtests, persisted artifacts and assumptions | Native streaming/cards/actions/history; authorized personal/shared context through existing runtime; inherited capabilities and error recovery; manually save selected plans during D14 deferral | Conversation/voice | Existing conversation API; financial/household reads only for contextual answers; paid live evidence grant | Stream and reopen supported answers/calculations/research/simulations, including a non-buy-and-hold strategy; retain evidence and assumptions; hypothetical questions never write finances or reveal private context |
| **Voice, D13.** Dictate/edit text and hold spoken conversations with interruption, cancellation and text handoff. [Voice](argus-minimum-viable-ecosystem-experience.md#43-speak-to-argus) | Existing conversation services; selected xAI direction, not an implemented voice service | Capture/transcription/playback, interruption, context handoff, permission/consent/retention, recovery and latency/cost measurement | Conversation/voice | Existing conversation path, audio/privacy policy and provider grant; financial actions alone depend on D14 | On phone dictate, edit, converse, interrupt/cancel, deny permission and return to text; preserve context and never save finances implicitly; measure latency/cost |
| **Search and continuity, D09/D10.** Find all authorized records/files/analyses, preview them and return to the same search; preserve drafts, recents, archive/recovery and defined Temporary chat. [Search](argus-minimum-viable-ecosystem-experience.md#search-find-what-i-already-know), [Temporary chat](argus-minimum-viable-ecosystem-experience.md#temporary-chat-and-conversation-recovery) | Existing Omnisearch/history and conversation recovery contracts | Financial/file/plan coverage, actual previews and origin-preserving native navigation; unsent drafts; Temporary context defaults/lock/discard/no-history/no-new-memory enforcement | Native continuity + Conversation/voice | Each domain supplies authorized reads; conversation owner supplies lifecycle; Temporary policy blocks that behavior only | Open chat/file from filtered scrolled results and return intact; restore original archived/deleted identity; test recents states, draft restoration and both Temporary variants without history/memory creation |
| **Updates, D11.** Receive persistent, useful deadlines, thresholds, milestones, scheduled summaries, freshness/review notices and relevant changed conditions; act on their source. [Updates](argus-minimum-viable-ecosystem-experience.md#updates-tell-me-when-something-deserves-attention) | Existing notification contracts/hidden capability and operational infrastructure, not a connected ecosystem inbox | Durable inbox, domain-triggered updates, schedules/delivery/preferences and sourced external-condition monitoring; explanations and deep links | Planning/Home | Each trigger fact independently; household visibility; channel/schedule decisions and any provider authority | Trigger each category; open source and correct it; verify persistence, schedules, preferences and permission revocation; notification previews expose no amounts or private details |
| **Profile and control, D12.** Manage personal details/avatar/photo, App/Account/Support settings, language/theme, response preferences, controlled personalization, security/usage/help and data lifecycle. [Profile](argus-minimum-viable-ecosystem-experience.md#profile-control-argus) | Existing profile/settings/security/usage/help/data-control contracts; role-restricted memory with existing controls | Native controls and persistence; domain-aware export/delete/recovery/retention; earned opt-in and inspect/edit/delete/reset/disable/why controls for any widened personalization | Native continuity | Existing identity/settings first; each domain supplies lifecycle/access; explicit retention and personalization rollout | Relaunch preferences; inspect real sessions/usage; exercise authorized export/removal/recovery; private facts stay private; financial records never become arbitrary chat memory |
| **Charts, D05/D06/D09/D15.** Understand canonical financial summaries through polished accessible charts. [Native quality](argus-minimum-viable-ecosystem-experience.md#native-quality-and-tester-feedback) | Selected chart direction and prototype; existing result chart semantics | Real series, useful icons/summaries, touch scrubbing, correct dates/units/currencies, gaps/unknowns, themes/accessibility and measured phone performance | Native continuity with domain series owners | Canonical series per chart; financial arithmetic remains backend-owned | Scrub actual data while scrolling; inspect missing points and both themes; compare plotted values to source; use accessible alternative and measure physical-device responsiveness |
| **Operational delivery, D01/D15.** Use and update the same signed app away from the Mac with durable data and recoverable service operation. [Infrastructure/acceptance](argus-minimum-viable-ecosystem-experience.md#14-infrastructure-and-cost-constraints) | Existing Render/Supabase project/current plan, release gates, CI and operational/cost safeguards | Signing/install/update route, HTTPS/native auth, compatible migrations/configuration, required jobs/integrations, monitoring, safe backup/restore and rollback, complete phone acceptance | Device/release + Captain + independent acceptance | Exact candidate, signing/access, merge/hosted/deployment grants, existing project/plan; no upgrade assumed | Cellular/away-from-Mac journeys on exact app/backend versions, relaunch/interrupted requests, two-user isolation; restore/rollback in safe environment; preserve production web; demonstrate all five MVEE connected journeys |
| **Agentic financial actions, D14. Founder-approved deferral for first private delivery.** Perform supported actions through text/voice with shared permissions and confirmation. [Runtime sequence](argus-minimum-viable-ecosystem-experience.md#agentic-ecosystem-direction-and-sequence) | Existing single conversational runtime and services; current chat does not provide this outcome | Later assigned runtime/action integration, ambiguity and hypothetical/actual handling, shared editable proposals, confirmation/correction/recovery and full action parity | Conversation/voice when separately activated | Founder-approved D14 runtime sequence; stable manual contracts/UI and model-facing gates | After activation repeat every supported manual action through text/voice; test ambiguity, interruption, permissions and no unconfirmed writes. Until then report the named gap, never full agentic completion |

### Shared acceptance and explicit disposition

Every active row inherits [MVEE trust requirements](argus-minimum-viable-ecosystem-experience.md#5-shared-ingestion-and-trust-requirements):
exact arithmetic; separate currencies; actual/expected/estimated/hypothetical and
unknown/zero distinctions; provenance and separate activity/as-of/capture dates;
no draft effects; idempotent retries and concurrency; source matching and
linked corrections; authorized recovery; and no sensitive data in ordinary
logs/analytics. The financial owner supplies one record/projection contract,
the household owner one permission contract, and every consumer enforces them.
The native lead owns shared navigation/session/UI conventions. Domain workers
may own disjoint native feature files; the lead does not become a queue for all
screen implementation. The delivery captain serializes shared integration.

The [existing holds register](argus-minimum-viable-ecosystem-experience.md#16-holds-later-work-and-unresolved-decisions)
is the only source of additional dispositions. Web remake is frozen and Android
is preserved pending its explicit assignment. Plaid, bank/browser access,
wallet automation, automated valuations and product discovery are exploratory,
not promised private-delivery integrations. Watchlist remains queued. Investment
holdings beyond recorded value are a later extension under the scope checklist.
Billing/monetization, growth sharing and new ecosystem analytics remain parked;
existing safeguards remain. Public App Store publication is not required.
MVEE sections 8 and 11.2 also exclude financial execution, guaranteed outcomes
and broader family/adviser/business-accounting capabilities. None of those
boundaries removes household collaboration or manual/document/voice delivery.

File/OCR/retention, household edits/departure/recovery, notifications/schedules,
Temporary chat/audio context, and distribution/hosted decisions are **open
requirements with owners**, not approved deferrals. The owner proposes a concrete
policy or implementation and escalates only genuine product/access/spending
choices. A blocked decision delays only its dependent work. No owner may replace
an in-scope path with unsupported copy or mark it deferred without founder approval.

### Acceptance for each work item

Acceptance derives from the [complete MVEE scope](argus-minimum-viable-ecosystem-experience.md#13-complete-scope-checklist).
These checks define the user result, not new endpoints or schema decisions.

- **D01:** the physical phone works away from the Mac with the existing identity.
  Verify login/relaunch/logout, registration/confirmation/resend, recovery/reset,
  account switching and guest return-to-action. No secrets in the build.
- **D02:** known/zero/unknown create, stable retry, list/reopen, metadata edit,
  opening correction with current concurrency tokens, archive/restore, restart
  persistence and owner isolation all work through the actual iPhone UI.
- **D03:** expense/income/transfer/payment/refund and notes/categories work with
  exact amounts. Exercise partial refunds, two-sided movements, earlier activity,
  balance gaps, stale edits, duplicate retries and correction/removal/restoration.
  Verify dependent records after every change. Do not manufacture balancing income.
- **D04:** private-space creation and lifecycle, account moves and link conflicts,
  unknown asset estimates, ownership shares and linked debt preserve identity and
  history. Personal/household totals do not double-count a joint asset or loan.
- **D05:** Home derives canonical values by currency with dates, source/freshness
  and missing information. Expected income is not current cash. Exercise a
  shortfall before an earlier bill even when end-period cash is positive.
- **D06:** create/edit a budget, savings goal and debt plan; link an actual entry;
  correct, refund, remove and restore it. Progress and forecasts update without
  allocating or subtracting the same money twice. Recurring/occasional expectations
  and variable income show dates and uncertainty.
- **D07:** two real authorized users exercise link/email invitation, acceptance,
  explicit sharing, contributions, joint records, editing, revocation and leaving.
  Private facts remain absent from totals, chat, documents, search and updates.
- **D08:** a declared supported sample passes file/photo intake, actual preview,
  extraction, uncertainty/duplicate review, batch confirmation and interrupted
  resume. Confirm again without duplicate records. Unsupported or unreadable files
  fail clearly. Apply approved retention and source visibility; use consenting
  real samples only under a specific data-handling authorization.
- **D09:** existing supported questions, calculations, research and historical
  simulations stream and reopen on the phone with the same evidence/assumptions.
  Preserve conversation drafts, history, archive/recovery and defined Temporary
  chat. Do not suggest unsupported financial actions are connected.
- **D10:** query/filter results include authorized financial records, plans, files
  and existing analyses. A result opens its real content. Back restores the query,
  filters and scroll position; no detour through Settings.
- **D11:** exercise a deadline, threshold, milestone, stale record and selected
  changed condition. An update explains its basis, persists, opens its owner and
  respects preferences, household access and private notification previews.
- **D12:** preferences persist; security and usage reflect actual service state.
  Export/delete/recovery and personalization follow their explicit permissions
  and retention rules. Financial records never become arbitrary chat memory.
- **D13:** verify dictation, transcription, spoken replies, interruption/cancel,
  editable interpretation and return to text. Document permission, retention,
  failure recovery, measured latency and cost. D14-dependent actions stay visibly
  incomplete until tested; voice must not save without confirmation.
- **D14:** every supported manual action is available through text and voice with
  the same permission checks and confirmation. Test hypothetical/quoted/actual
  distinctions, correction, ambiguity, interruption and recovery. Reuse the one
  Argus runtime; satisfy the existing model-facing evaluation gates.
- **D15:** run all [connected acceptance journeys](argus-minimum-viable-ecosystem-experience.md#15-connected-acceptance-and-delivery-discipline)
  against the assembled deployed candidate and physical phone. Check English,
  Spanish, themes, enlarged text, accessibility, charts/icons, file previews,
  permissions, failed requests and relaunch. Verify backup restoration and rollback
  in a safe environment. State the deferred-runtime gap explicitly.

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

On the single restart authorization, activate full-scope ownership from the
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
| Financial/private-space recovery window, purge/export behavior and production limits | Financial core + Native continuity; lifecycle controls | Preserve record identity and linked restoration; propose explicit recovery/retention limits before release. Keep permanent Personal and empty-only space deletion. Never infer financial retention from chat policy. Ordinary posting can progress |
| Household editing, departure, joint-record custody and recovery | Household; shared writes and revocation | Recommend view-only sharing unless edit rights are explicitly granted; revoke future access promptly without silently deleting another person's records. Present joint custody/export/retention choices for approval. Private journeys and invitation mechanics can progress |
| File formats/institutions, OCR, upload/page limits, encrypted files and retention | Intake; extraction/storage | Cover declared PDFs, structured exports and images/photos; select concrete supported samples. Recommend local type/readability checks, private source access and explicit sharing; do not accept unreviewed OCR as fact. Determine limits/provider from bounded synthetic evaluation, then seek any paid/data-handling grant. Do not drop photo/PDF intake because selection is unfinished |
| Notifications, schedule defaults, time zones and monitored external conditions | Planning/Home; delivery and scheduled updates | Recommend a persistent inbox and opt-in private push previews; no financial details outside the authenticated app. Founder selects external channels/defaults. Use existing jobs and sourced conditions; trigger/inbox implementation can progress independently |
| Audio and Temporary chat context/provider retention | Conversation/voice; Temporary behavior and live audio | Recommend no retained raw audio by default; Temporary has context off initially, locked after first message, no history or new memories and explicit discard. Verify provider retention feasibility before promising it; get policy approval. Regular native chat can progress |
| Provider credentials, spend caps and consenting data/test identities | Relevant domain + Device/release; live voice/OCR/research/backtest/invite acceptance | Use existing approved providers, server-held secrets and bounded cases/caps. Request credentials via secure configuration, not chat. Use synthetic documents/accounts until real samples and second-user participation are authorized; no broad production data copies |
| VM access and direct coordination | Captain; remote workers | Verify secure connectivity, exact checkout, exclusive writer and pushed checkpoints before remote assignment. Use local agents for ready work until then; do not make additional machines a prerequisite |
| D14 activation | Captain + Conversation/voice | Respect the founder-approved runtime sequence. Keep its unmet action parity visible and request the separate runtime assignment when its prerequisites are satisfied; do not use it to defer ordinary voice, manual workflows or financial read-context |


Web remake, billing, new growth sharing and new ecosystem analytics are not
current work. Android remains preserved pending explicit assignment. Plaid,
wallet automation, bank access, valuations and watchlist ideas follow the
[MVEE holds and later-work register](argus-minimum-viable-ecosystem-experience.md#16-holds-later-work-and-unresolved-decisions).
Do not turn them into prerequisites for private iPhone delivery.
