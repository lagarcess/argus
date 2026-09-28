# Argus documentation authority

**Updated:** September 28, 2026. Founder-approved documentation reconciliation,
plus the September 28 implementation-batch ownership and deferral handoff.
**Purpose:** Help an agent distinguish approved product direction, existing technical contracts, historical rationale, and authorized implementation work.

## Start here

1. Read [AGENTS.md](../AGENTS.md) for repository, safety, review, and delivery rules.
2. Read [PRODUCT.md](PRODUCT.md) for the product overview and the boundary between the existing Alpha and the approved pivot.
3. Read the [minimum viable ecosystem experience (MVEE)](specs/argus-minimum-viable-ecosystem-experience.md) for the approved audience, surfaces, ingestion, loop, household collaboration, and open decisions.
4. Read [ARCHITECTURE.md](ARCHITECTURE.md), [API_CONTRACT.md](API_CONTRACT.md), [DATA_MODEL.md](DATA_MODEL.md), and [DESIGN.md](../.agent/designs/argus/DESIGN.md) before relevant technical or UI work. Their existing contracts are not replaced by experience prose.
5. Read the explicitly assigned package or slice. For a Wave 1 assignment, start with [its README](specs/wave-1/README.md) and the package's existing gates. A roadmap or brainstorm does not assign work by itself.

## One owner per kind of decision

| Question | Owner | Boundary |
| --- | --- | --- |
| What is Argus becoming, for whom, and how should it feel and work? | [MVEE](specs/argus-minimum-viable-ecosystem-experience.md) | Approved experience, not a shipped-feature inventory or technical implementation specification |
| How does that relate to the existing product? | [PRODUCT.md](PRODUCT.md) | Current product overview and explicit existing-capability contracts; verify actual availability against code/release evidence |
| Which founder decisions changed, and when? | [Decision log](specs/argus-decision-log.md) | Decision provenance and links; detailed requirements remain with their owner |
| What architecture, payloads, and persistence contracts apply? | Architecture, API contract, and data model docs above | Existing system contracts/technical intent and the [locked interface stacks](ARCHITECTURE.md#approved-platform-direction); some statements describe targets, not proof of implementation |
| What visual and interaction conventions apply? | [DESIGN.md](../.agent/designs/argus/DESIGN.md) | Preserve current design system and chat detail; MVEE owns the pivot's surface structure and platform intent |
| What is an agent authorized to build now? | Explicit assignment and its scoped package/spec | MVEE approval does not assign every feature, unlock stages, or authorize provider integrations |
| How is work reviewed and released? | AGENTS.md, [CI/CD discipline](specs/private-alpha-ci-cd-sota.md), [launch runbook](PRIVATE_LAUNCH_RUNBOOK.md), [manifest template](release-manifests/TEMPLATE.md) | Existing evaluation, privacy, branch, merge, and deployment gates remain in force |
| What evidence or thinking informed a direction? | Linked research and historical strategy docs | Inputs and provenance, not independent scope authority |

## What is settled

The MVEE is the single detailed owner of the approved ecosystem. Its section 1.1 locks the audience and near-term financial emphasis; section 12 includes partner invitations and personal/household views. Sections 3–5 define surfaces and information ingestion. Sections 8–9 distinguish boundaries and open decisions. Section 11 defines pain-point coverage and the reinforcing loop.

The product remains one connected Argus experience that carries forward existing chat, calculations, research, and historical comparisons. These capabilities are not gated behind debt repayment. The design direction retains the Argus visual identity. Native iOS/Android plus web and their [interface stacks](ARCHITECTURE.md#approved-platform-direction) are approved. Detailed client architecture and sequencing remain open.

“Locked” means founder-approved direction. It does not mean implemented, validated market demand, a final schema, a model instruction change, or permission to deploy.

The current mobile reference is the [September 28 design lock](reports/mobile-design-lock-2026-09-28.md).
It succeeds the earlier September 27 sketch carried by PR #714. Read its archive
and current MVEE/DESIGN together; historical screenshots do not reopen later
decisions. The [recording response](specs/lanes/financial-recording-decision-response.md)
distinguishes settled experience from remaining recommendations for PR #724.

## Carry forward, change explicitly

Argus has one evolving product and one set of technical owners. The MVEE
defines approved experience changes; it does not reset the production feature
inventory. Existing behavior and gates remain valid unless a specific approved
change replaces them. A feature omitted from the MVEE is not implicitly retired.

Distinguish a contradictory product mandate from a temporal difference:
“this feature is hidden today” can coexist with “enable it in the next push.”
Keep current availability and its approved transition together in
[PRODUCT.md](PRODUCT.md#current-production-availability-and-planned-changes),
and link there from other documents. Do not delete accurate production truth
merely to make an experience specification read as if it has shipped.

## What remains technical or undecided

Do not infer these from a polished demo or the MVEE:

- Registration/conversion mechanics and enforcement of the [locked guest access boundary](specs/argus-minimum-viable-ecosystem-experience.md#guest-access-and-registration); guest financial persistence is no longer an open product choice.
- Financial-record schema, balance/transaction reconciliation model, money arithmetic contracts, migrations, and historical-data conversion.
- Household membership lifecycle, permission enforcement/RLS, ownership, revocation, deletion, and retention implementation. The consent/visibility experience is settled; its technical realization is not.
- API routes, action schemas, chat-to-record integration, runtime state ownership, jobs, and event contracts for the new surfaces.
- Voice integration contracts under the [selected voice/chart direction](ARCHITECTURE.md#voice-and-chart-direction), OCR providers, supported file formats/institutions, secure bank-access design, wallet/device capabilities, and automatic-acceptance policies.
- Scheduling, external-fact monitoring, notification delivery channels, and associated data access.
- Native client architecture beyond the locked interface stacks: shared contracts/components, authentication, local storage/offline synchronization, supported OS/device ranges, delivery order, rollout flags, acceptance gates, and work packages for the full ecosystem.

Before implementing a change in these areas, define its bounded technical contract and acceptance conditions using the existing system as the starting point. Continue unrelated authorized work; escalate a concrete unresolved product choice or conflicting package instead of inventing it.

## Older documents: disposition

| Document | Status after this reconciliation | How to use it |
| --- | --- | --- |
| [Pivot strategy](specs/argus-pivot-strategy.md) | Historical strategic proposal; conflicting experience direction superseded | Preserve rationale and research; do not promote every proposal into scope |
| [Answers that stay true](specs/argus-answers-that-stay-true-roadmap.md) | Historical product board plus carried-work/release reference | Saved-answer ideas may support the MVEE; preserve unresolved issues and operational rules without treating its brainstorm as today's assignment |
| [Private Alpha Next decision memo](specs/private-alpha-next-decision-memo.md) | Historical strategic/technical rationale | Follow its compatibility pointer to archived technical context for a named slice; its old product framing does not override the MVEE |
| [Wave 1](specs/wave-1/README.md) | Existing package specifications; experience conflicts require reconciliation | Preserve assigned work, dependencies, review gates, and safe completed work. Do not silently cancel, expand, or rewrite packages |
| [Private Alpha Next roadmap](specs/private-alpha-next-roadmap.md) | Superseded P2 history and technical reference | No new assignments from its old queue |
| [Old active-roadmap pointer](specs/argus-active-roadmap.md) and [grounded-finance pointer](specs/argus-grounded-finance-roadmap.md) | Historical redirects with a current authority pointer | Follow this document for current ownership instead of chaining stale active-board claims |
| [Social/market research mapping](research/2026-09-26-dr-latam-finance-painpoints-mvee.md) | Supporting research and decision history | Approved choices live in the MVEE; raw recommendations and metrics do not become requirements automatically |

Retired strategy narratives now live in `docs/archive/`, with compatibility pointers at their former paths. Their issue references and dated reasoning are preserved. Active product and design statements are rewritten in place; current readers need not mentally override a second product identity. Technical endpoint, entity, and runtime contract sections remain unchanged. Date-specific production claims in archives are historical snapshots.

## Wave 1 reconciliation boundary

No replacement execution schedule is created by this PR. Wave 1's assigned packages and stage/review gates remain the execution reference for that work. Neither the old answers board nor the MVEE automatically starts a new lane.

In particular, Wave 1's two-audience landing, limited navigation, hidden account/upload/budget surfaces, and earlier onboarding assumptions are package-era choices, not permanent limits on the ecosystem. A temporary shipping subset may still be appropriate, but the assigned spec must say so explicitly. Before implementing a conflicting experience requirement, reconcile that package with the founder-approved MVEE and record what is retained, revised, or deferred. Do not expose unfinished surfaces just because they are approved in the vision.

Safety fixes, instrumentation, and existing calculator work are not discarded by a pivot. Assess actual semantic overlap with the assignment; unchanged applicable safeguards continue to apply.

## Current implementation batch (September 28, 2026)

Founder-authorized coordination while the founder steps away. Source handoff:
[PR #727 comment](https://github.com/lagarcess/argus/pull/727#issuecomment-5878051744).
Target: a real local create/reopen/edit financial-account journey on iPhone,
Android, and web by reusing and connecting existing Argus capabilities, not by
replacing production auth or the chat runtime.

### Ownership

After the current foundations land, the **Project delivery lead** and the **VM
serial captain** jointly own create/reopen/edit financial-account journey
coordination across iPhone, Android, and web. They coordinate owners and
sequencing; they do not take exclusive write away from the foundation lanes
below, and they do not replace production auth or the chat runtime.

| Surface | Owner | Boundary |
| --- | --- | --- |
| Integration landing / merges to `codex/private-alpha-next` | VM serial captain (integration orchestrator) | Only landing executor under the founder's existing bounded merge authorization. The Project delivery lead coordinates but does not push to integration or edit branches another lane already owns. |
| Account domain, API, persistence; `API_CONTRACT` / `DATA_MODEL` amendments | Existing VM account-backend worker | Sole backend owner for this batch. No competing backend worker. Clients bind to its accepted first-slice payload contract once published. |
| `ios/` continuation | Existing iPhone owner (Build iPhone iOS foundation) | Maps real sessions; continuation after foundations. [#729](https://github.com/lagarcess/argus/pull/729) landed as `f61e47f1`. |
| `mobile/android/` continuation and pending #726 probe validation | Existing Android owner (Android phone foundation) | Same continuation rules as iPhone. [#729](https://github.com/lagarcess/argus/pull/729) landed as `f61e47f1`; [#730](https://github.com/lagarcess/argus/pull/730) landed as `a8e09b72`. |
| Isolated responsive preview, then later account API wiring | Existing web owner (Build responsive Argus preview) | Finishes the isolated preview first; wires to the accepted backend contract afterward. No production-auth rewrite. |
| Chart validation | Existing chart owner under `prototypes/chart-validation` | Remains isolated. Not a prerequisite for the account journey. |

**Exclusive write ownership:** original lanes retain exclusive write on
[#723](https://github.com/lagarcess/argus/pull/723),
[#725](https://github.com/lagarcess/argus/pull/725),
[#726](https://github.com/lagarcess/argus/pull/726), and
[#724](https://github.com/lagarcess/argus/pull/724). Do not push concurrent
fixes to those branches. [#729](https://github.com/lagarcess/argus/pull/729)
landed as `f61e47f1`; [#730](https://github.com/lagarcess/argus/pull/730)
landed as `a8e09b72`. Continue gated landing of #724 as its applicable
gates close. Do not hold independent ready foundations for unrelated
research.

**#725 hold:** Landing of [#725](https://github.com/lagarcess/argus/pull/725)
is held for a narrowed research / selected-file-import scope. That hold does
not block account creation, native auth, or client wiring to the accepted
account contract. Do not expand #725 scope from this note.

**Shared rules for this batch:** fetch current integration at start and before
readiness; one-way reconciliation only (no rebase); one canonical server
financial-rule owner; reuse existing Argus login/signup/resend/recovery/guest/
profile behavior as the baseline; check browser recovery/PKCE/app return
technically before any callback change; no new production app identities,
hosted settings, paid calls, or deployments from this coordination; new
continuation PRs are not implicitly added to the earlier bounded merge list.

### Founder deferral

Revenue, pricing, paywalls, billing integrations, and user trials are parked
while core journeys become functional. Existing usage and cost safeguards
remain in force. Do not open a separate status-only documentation PR for this
handoff; record it here and in the [decision log](specs/argus-decision-log.md).

## Handoff rule

An implementation handoff should identify the MVEE section it serves, its bounded deliverable, current technical owners, unresolved decisions, allowed/no-touch files, and evidence required. It must not claim that this docs-only reconciliation selected a new architecture or completed the product pivot.
