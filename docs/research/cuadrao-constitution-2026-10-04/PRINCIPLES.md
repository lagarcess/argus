# Proposed Cuadrao principles

**Status:** Draft for founder review. These are distilled from the three
[originals](README.md). Existing locks continue to govern where they differ.
The [reconciliation table](RECONCILIATION.md) states those differences.

These principles guide how we write the canon. They do not declare all described
capabilities built or required for the consumer launch.

| Principle | What it means in practice | Source | Canonical destination |
| --- | --- | --- | --- |
| Complete the user's job | Capture, correct, understand the effect, retrieve evidence and continue. A finished screen is not proof of a finished journey. | Quality §§3–7, 12; GTM launch tracks | [MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md) for journeys; assigned issue for acceptance |
| One identity, explicit access | Personal, household and business membership do not merge data. Billing, a job title or an AI conversation cannot grant access. | Architecture §2; Quality §1 | [MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md) for experience; [data model](../../DATA_MODEL.md) for approved ownership and grants |
| One owner for each durable fact | Chat, screens, jobs and integrations read the same record and action rules. Models propose and explain; validated services control durable writes. | Architecture §§6–9; Quality §§2, 8–9 | [Architecture](../../ARCHITECTURE.md), [API contract](../../API_CONTRACT.md), [data model](../../DATA_MODEL.md), each within its scope |
| Money stays exact and attributable | Preserve amount, currency, source and corrections. Apply the locked no-conversion rule. Metrics identify what they count and can be traced to records. | Quality §§2, 4, 7; October 4 currency lock | [Data model](../../DATA_MODEL.md) for values; [MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md) for presentation |
| Keep evidence and correction connected | A processed document remains findable with its source and accepted corrections, subject to the agreed deletion and retention policy. Reprocessing cannot silently replace a correction. | Quality §§3, 6 | [Data model](../../DATA_MODEL.md), [API contract](../../API_CONTRACT.md) |
| Separate states that mean different things | Drafted, approved, issued, fiscally accepted, paid and deposited require different evidence. An upload is not a confirmed expense; a deposit is not a second sale. | Architecture sales/fiscal modules; Quality §§4–5 | [Data model](../../DATA_MODEL.md) and each assigned workflow contract |
| Approval applies to the actual action | An action uses the approved revision, recipient and permissions. Recheck authority when it executes. Duplicate delivery must not repeat a financial effect; uncertain outcomes need reconciliation. | Quality §§5, 8–9 | [Architecture](../../ARCHITECTURE.md), [API contract](../../API_CONTRACT.md) |
| Keep basic work useful when a connector fails | Manual records and capture remain useful. Show stale or failed sources, preserve drafts, and provide a recovery path without duplicate records. | GTM product focus; Quality §§3–4, 9 | [MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md), assigned connector contract |
| Show the truth of the current state | Distinguish loading, missing data, known zero, partial results and confirmed success. Labels and highlights explain the evidence without invented precision. | Quality §§7, 10–12; existing zero-month lock | [Cuadrao design guide](../../../.agent/designs/cuadrao/DESIGN.md), [MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md) |
| Prove the experience at the boundary where it runs | Mock tests, connected device journeys and live-provider checks prove different things. Measure recovery, privacy, correctness, latency and cost where relevant. Apply checks to the selected capability. | Quality §§11–14 | [Launch runbook](../../PRIVATE_LAUNCH_RUNBOOK.md) and assigned acceptance issues |

## Applying a principle

Write the user outcome, actor and space first. Name the canonical record, the
state transition, the failure path and the evidence needed to show it works.
Reference the existing owner instead of restating its rule. If a proposal changes
a founder lock, record the decision request before implementation.

For example, the quality guide's invoice case has a DOP 12,000 invoice, DOP 5,000
in cash and DOP 7,000 through a payment provider. The provider deposits DOP 6,900
and retains a DOP 100 fee. A future business contract must represent a fully
collected invoice, its separate fee and its settlement evidence without counting
three revenues. This is a business acceptance example, not new consumer scope.

Consumer and business can share these principles while keeping different
interfaces. Consumer work favors quick capture and return. Business review may
need more detail. Visual tokens, accessibility and motion remain owned by the
platform design guides.
