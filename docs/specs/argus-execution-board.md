# Argus private iPhone execution manifest

**Updated:** September 29, 2026.
**Execution state:** STOPPED. Documentation publication only is authorized.
**Product owner:** [MVEE](argus-minimum-viable-ecosystem-experience.md).
**Authority and onboarding:** [DOCUMENTATION_AUTHORITY](../DOCUMENTATION_AUTHORITY.md).

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

No item below is a new assignment. Restart, owner acceptance and technical
contracts must be recorded before implementation. No 24-hour delivery promise
has been made. Everything previously stopped remains stopped.

## Verified starting point

Read-only snapshot on September 29. Integration base is
`de8729843b726a3fd03210cebcedede5e44227c8`, the #742 landing documentation commit.
The account product commit is `296195e86c972e846c251d256b3cc211975bfd57`.
GitHub merge/closure state and the linked repository documents were inspected.
Existing production behavior is documented, not freshly exercised on a hosted
service in this publication. No private iPhone completion is claimed.

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
assigned. These are local recovery pointers, not portable delivery artifacts:

| Branch | Last inspected commit | State at stop |
| --- | --- | --- |
| `codex/ios-financial-accounts` | `a0424297e5559af641bfc4b8181fced662d428e2` | Spec commit plus uncommitted client work. Native UI acceptance incomplete; prior build approval rejection remains unresolved |
| `codex/android-financial-accounts` | `3aed3d2266f8ed5a31c87b8083ef114a33d905cd` | Implementation committed locally; owner reported local UI/API acceptance, but final restart proof, durable publication and PR delivery incomplete |
| `codex/web-financial-accounts` | `1b0c80d208ad6e73409c72ccba13407fbfb2ee34` | Spec commit plus uncommitted client work. Preserve only; no continuation now |

A replacement coordinator must locate the branches and working changes before
using those pointers. Missing local artifacts are a recovery issue, not evidence
that their work landed. Do not copy secrets or real user data into handoffs.

## Work map

Every row is currently unassigned and stopped. Owner columns name the required
responsibility, not a dispatched person. Inspect existing owners before assigning
someone new. Dependencies are accepted behavior/contracts, not a requirement to
wait for every feature in an upstream row before any useful work can begin.

| ID | User outcome | Reuse and dependency | Responsible role after restart | Initial disposition |
| --- | --- | --- | --- | --- |
| D01 | Open the installed app on the physical iPhone, log in with the existing account and reopen it over the internet | Native shells/auth; existing Render/Supabase; explicit signing and hosted-change approvals | iPhone owner with deployment owner | First integration checkpoint; setup and hosted verification missing |
| D02 | Create, reopen, correct, archive and restore real financial accounts | Landed #735 contract; salvage stopped iPhone work; D01 for hosted/device proof | Account journey owner, coordinating iPhone and existing backend owner | API implemented; full device journey incomplete |
| D03 | Record and correct activity, reconcile balances, recover mistakes | D02 account identity; technical recording contract from approved MVEE and selected prior proof cases | One financial-domain owner with iPhone implementation partner | Production activity/reconciliation missing |
| D04 | Organize private spaces and optional assets without losing history or links | D02; D03 semantics for linked activity; explicit space/asset contracts | Financial-domain owner delegates bounded space work | Complete private-space and asset lifecycle missing |
| D05 | Understand real position, changes and upcoming cash needs on Home | D02/D03 accepted projections; D06 expectations; D04 ownership; chart prototype | Home journey owner consuming canonical projections | Sample experience; connected result missing |
| D06 | Create budgets, goals and debt plans, then link actual progress | D03 activity; inherited calculators; one allocation/expectation contract | Plan journey owner | Production planning missing |
| D07 | Invite a partner and use shared finances without exposing private data | Auth identities; explicit membership/permissions contract; D02-D06 shared queries/actions | Household owner with shared permission-contract ownership | Membership and shared journeys missing |
| D08 | Import a supported document/photo, preview, review, confirm and resume | Synthetic ingestion kit; D03 confirmed-record boundary; file policy decisions | Intake owner | Production intake missing |
| D09 | Ask existing finance questions and revisit answers/analyses on iPhone | Existing chat/runtime/SSE/search contracts; D01 session; preserve supported behavior | Native conversation owner | Backend reuse exists; native connected journey incomplete |
| D10 | Find a record or document and return to the same search context | Existing Omnisearch; D02-D09 authorized records; native preview/navigation | Retrieval journey owner | Financial/native coverage and tester defects incomplete |
| D11 | Receive useful updates and open their source | D03/D06 facts; D07 permissions; selected scheduling/delivery contract | Updates owner | Ecosystem inbox and delivery incomplete |
| D12 | Control preferences, security, privacy and financial data | Existing settings; D01 identity; each domain's export/delete/recovery rules | Native controls owner with domain/security owners | Partial reuse; complete native controls missing |
| D13 | Dictate and converse by voice without losing context or saving accidentally | D09; selected xAI direction; consent/retention; D14 for financial actions | Voice owner | Integration missing; financial-action completion waits for D14 |
| D14 | Perform supported app actions through text/voice using the same rules | Stable manual D02-D12 services; explicit single-runtime redesign assignment | Conversational-runtime owner | Explicitly deferred from first private delivery |
| D15 | Complete all private-delivery journeys on one reliable phone build | D01-D13 applicable scope; full household and document journeys; D14 gap stated | Delivery captain with independent acceptance owner | Not achieved |

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

## Proposed order and safe parallel work

After an explicit restart, inspect and assign D01 and D02 first. In parallel,
prepare D03's accepted financial contract using the actual account backend. D01
must expose signing/network/auth problems early, not at the end of development.

Once their consumed contracts are accepted, D06 planning, D07 membership and D08
intake can have separate owners. One financial owner controls posting, money,
reconciliation and account history. Household owns permission semantics; each
consumer enforces that same contract. Extraction can advance independently,
but intake is not done until it writes through D03's review/confirmation path.

D05, D10 and D11 consume the shared records/projections. D09 inherits existing
conversation contracts without starting D14. D12 accompanies the records it
controls. D13 can validate capture and existing conversation separately; its
financial-action dependency stays explicit. D15 acceptance runs incrementally
as features arrive, not only after all branches finish.

Parallel capacity is limited by clear ownership and accepted dependencies, not
available agent count. Do not split one domain's API, migration and money rules
among competing writers. Reconcile shared contracts before dependent work.
One accepted schema or endpoint change must reach every affected consumer.

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

At each meaningful checkpoint, update the row and link its PR plus durable
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
hosted/deployment permissions. Routine testing, scoped bug fixes and review
triage do not need repeated founder prompts once their assignment is authorized.
Current VM communication still goes through the founder until a direct channel
is explicitly established. Do not claim autonomous VM coordination exists.

No stop instruction, denied approval or missing contract may be bypassed through
another agent. Batch genuine decisions and continue independent authorized work.
Stop affected work for duplicate writers, contradictory contracts, repeated
unproductive failures or scope expansion. Review genuine reachable defects at
their shared cause; stop the review loop at the repository's clean-delta rule.

### Decision gates

| Gate | Needed by | Current disposition |
| --- | --- | --- |
| Restart and named ownership | Any implementation | Founder stopped all work; docs-only PR authorized |
| Physical device/signing and hosted configuration | D01 | Inspect existing setup, then obtain necessary explicit authorization |
| On-device deployment using current Supabase project/plan | D01 | Project reuse settled; exact Render configuration/capacity unverified |
| File size, password handling, retention, supported formats/OCR | D08 | Unresolved; no experimental assumption becomes approval |
| Household edits, departure, retention and recovery | D07 | Approved experience; technical policy details unresolved |
| Notifications and schedules | D11 | Channels/defaults unresolved |
| Audio/context/Temporary chat retention | D09/D13 | Explicit contracts required |
| Agentic-runtime implementation | D14 | Deferred; requires a separate assignment |

Web remake, billing, new growth sharing and new ecosystem analytics are not
current work. Android remains preserved pending explicit assignment. Plaid,
wallet automation, bank access, valuations and watchlist ideas follow the
[MVEE holds and later-work register](argus-minimum-viable-ecosystem-experience.md#16-holds-later-work-and-unresolved-decisions).
Do not turn them into prerequisites for private iPhone delivery.
