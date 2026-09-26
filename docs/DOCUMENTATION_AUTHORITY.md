# Argus documentation authority

**Updated:** September 26, 2026. Founder-approved documentation reconciliation.
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
| How does that relate to the existing product? | [PRODUCT.md](PRODUCT.md) | Concise overview and preserved Alpha behavior; verify actual availability against code/release evidence |
| Which founder decisions changed, and when? | [Decision log](specs/argus-decision-log.md) | Decision provenance and links; detailed requirements remain with their owner |
| What architecture, payloads, and persistence contracts apply? | Architecture, API contract, and data model docs above | Existing system contracts/technical intent; some statements describe targets, not proof of implementation |
| What visual and interaction conventions apply? | [DESIGN.md](../.agent/designs/argus/DESIGN.md) | Preserve current design system and chat detail; MVEE owns the pivot's surface structure and platform intent |
| What is an agent authorized to build now? | Explicit assignment and its scoped package/spec | MVEE approval does not assign every feature, unlock stages, or authorize provider integrations |
| How is work reviewed and released? | AGENTS.md, [CI/CD discipline](specs/private-alpha-ci-cd-sota.md), [launch runbook](PRIVATE_LAUNCH_RUNBOOK.md), [manifest template](release-manifests/TEMPLATE.md) | Existing evaluation, privacy, branch, merge, and deployment gates remain in force |
| What evidence or thinking informed a direction? | Linked research and historical strategy docs | Inputs and provenance, not independent scope authority |

## What is settled

The MVEE is the single detailed owner of the approved ecosystem. Its section 1.1 locks the audience and near-term financial emphasis; section 12 includes partner invitations and personal/household views. Sections 3–5 define surfaces and information ingestion. Sections 8–9 distinguish boundaries and open decisions. Section 11 defines pain-point coverage and the reinforcing loop.

The product remains one connected Argus experience that carries forward existing chat, calculations, research, and historical comparisons. These capabilities are not gated behind debt repayment. The design direction retains the Argus visual identity. Native iOS/Android plus web are the intended platforms; architecture and sequencing are not selected here.

“Locked” means founder-approved direction. It does not mean implemented, validated market demand, a final schema, a model instruction change, or permission to deploy.

## What remains technical or undecided

Do not infer these from a polished demo or the MVEE:

- Account onboarding, guest persistence, registration/conversion timing, and any changes to current access gates.
- Financial-record schema, balance/transaction reconciliation model, money arithmetic contracts, migrations, and historical-data conversion.
- Household membership lifecycle, permission enforcement/RLS, ownership, revocation, deletion, and retention implementation. The consent/visibility experience is settled; its technical realization is not.
- API routes, action schemas, chat-to-record integration, runtime state ownership, jobs, and event contracts for the new surfaces.
- Voice/OCR providers, supported file formats/institutions, secure bank-access design, wallet/device capabilities, and automatic-acceptance policies.
- Scheduling, external-fact monitoring, notification delivery channels, and associated data access.
- Native app architecture, shared components, delivery order, rollout flags, acceptance gates, and work packages for the full ecosystem.

Before implementing a change in these areas, define its bounded technical contract and acceptance conditions using the existing system as the starting point. Continue unrelated authorized work; escalate a concrete unresolved product choice or conflicting package instead of inventing it.

## Older documents: disposition

| Document | Status after this reconciliation | How to use it |
| --- | --- | --- |
| [Pivot strategy](specs/argus-pivot-strategy.md) | Historical strategic proposal; conflicting experience direction superseded | Preserve rationale and research; do not promote every proposal into scope |
| [Answers that stay true](specs/argus-answers-that-stay-true-roadmap.md) | Historical product board plus carried-work/release reference | Saved-answer ideas may support the MVEE; preserve unresolved issues and operational rules without treating its brainstorm as today's assignment |
| [Private Alpha Next decision memo](specs/private-alpha-next-decision-memo.md) | Historical strategic/technical rationale | Read relevant technical context for a named slice; its old product framing does not override the MVEE |
| [Wave 1](specs/wave-1/README.md) | Existing package specifications; experience conflicts require reconciliation | Preserve assigned work, dependencies, review gates, and safe completed work. Do not silently cancel, expand, or rewrite packages |
| [Private Alpha Next roadmap](specs/private-alpha-next-roadmap.md) | Superseded P2 history and technical reference | No new assignments from its old queue |
| [Old active-roadmap pointer](specs/argus-active-roadmap.md) and [grounded-finance pointer](specs/argus-grounded-finance-roadmap.md) | Historical redirects with a current authority pointer | Follow this document for current ownership instead of chaining stale active-board claims |
| [Social/market research mapping](research/2026-09-26-dr-latam-finance-painpoints-mvee.md) | Supporting research and decision history | Approved choices live in the MVEE; raw recommendations and metrics do not become requirements automatically |

Historical document bodies and issue references remain intact. Date-specific production claims are historical snapshots, not assertions about the current deployment.

## Wave 1 reconciliation boundary

No replacement execution schedule is created by this PR. Wave 1's assigned packages and stage/review gates remain the execution reference for that work. Neither the old answers board nor the MVEE automatically starts a new lane.

In particular, Wave 1's two-audience landing, limited navigation, hidden account/upload/budget surfaces, and earlier onboarding assumptions are package-era choices, not permanent limits on the ecosystem. A temporary shipping subset may still be appropriate, but the assigned spec must say so explicitly. Before implementing a conflicting experience requirement, reconcile that package with the founder-approved MVEE and record what is retained, revised, or deferred. Do not expose unfinished surfaces just because they are approved in the vision.

Safety fixes, instrumentation, and existing calculator work are not discarded by a pivot. Assess actual semantic overlap with the assignment; unchanged applicable safeguards continue to apply.

## Handoff rule

An implementation handoff should identify the MVEE section it serves, its bounded deliverable, current technical owners, unresolved decisions, allowed/no-touch files, and evidence required. It must not claim that this docs-only reconciliation selected a new architecture or completed the product pivot.
