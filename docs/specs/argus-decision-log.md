# Argus Decision Log

This log records locked product decisions and links to their detailed owner.
The September 26 entries record direct founder approval in the MVEE design
conversation and the subsequent request to publish a docs-only reconciliation.
See [documentation authority](../DOCUMENTATION_AUTHORITY.md) for scope and
supersession rules. These decisions do not assert implementation completion.

## Locked

| Date | Decision | Locked by |
| --- | --- | --- |
| 2026-09-24 | The first user is people living in the Dominican Republic, not the diaspora. | Lucas |
| 2026-09-24 | Argus keeps all its existing grounded chat and calculation capability. The pivot adds features around it so Argus isn't just an AI chat, building toward an ecosystem. | Lucas |
| 2026-09-26 | Approve one connected minimum viable ecosystem carrying forward existing Argus capabilities. The earlier one-product-versus-two question is resolved for this experience. Detailed owner: [MVEE sections 1–3 and 7](argus-minimum-viable-ecosystem-experience.md). | Lucas |
| 2026-09-26 | Lock the initial audience and near-term financial emphasis, shared planning picture, and low-effort recording/return loop. Detailed owner: [MVEE section 1.1](argus-minimum-viable-ecosystem-experience.md#11-locked-audience-and-experience-emphasis). | Lucas |
| 2026-09-26 | Approve ingestion experience and its confirmation, correction, provenance, and freshness boundaries; experimental access paths are not provider commitments. Detailed owner: [MVEE sections 4–5](argus-minimum-viable-ecosystem-experience.md#4-information-ingestion-one-destination-several-entry-methods). | Lucas |
| 2026-09-26 | Preserve Argus visual identity and existing chat detail; approve ecosystem navigation and native iOS/Android plus web intent. Detailed owner: [MVEE section 2](argus-minimum-viable-ecosystem-experience.md#2-product-character-and-platforms). | Lucas |
| 2026-09-26 | Include partner invitations and personal/household views in the minimum ecosystem, superseding the earlier deferral. Detailed owner: [MVEE section 12](argus-minimum-viable-ecosystem-experience.md#12-household-collaboration-approved-minimum-capacity). | Lucas |
| 2026-09-26 | Publish approved experience and reconcile older document pointers in a docs-only PR; defer new technical design and implementation sequencing. Owner: [documentation authority](../DOCUMENTATION_AUTHORITY.md). | Lucas |
| 2026-09-26 | Carry production behavior and gates forward unless explicitly changed; distinguish current availability from approved future experience. Owner: [PRODUCT.md availability and transitions](../PRODUCT.md#current-production-availability-and-planned-changes). | Lucas |
| 2026-09-26 | Lock platform-native mobile interfaces and retain the existing web/PWA stack, sharing one Argus backend and canonical financial truth. Accept separate interface maintenance with coordinated agents and platform-specific verification. Detailed stack owner: [ARCHITECTURE.md platform decision](../ARCHITECTURE.md#approved-platform-direction). Client contracts and rollout remain to be defined. | Lucas |
| 2026-09-27 | Approve quick type-specific account setup, optional nicknames and unknown balances, and optional property, vehicle and other asset tracking. Lock the estimate, ownership and linked-debt boundaries; listing-based valuation remains a future candidate capability. Detailed owner: [MVEE quick setup and assets](argus-minimum-viable-ecosystem-experience.md#quick-account-setup-and-optional-assets). | Lucas |
| 2026-09-27 | Accept the simplified account-entry sketch and consistent money-entry treatment as the current design baseline; stop further visual refinement for this pass. Experience owner: [MVEE quick setup](argus-minimum-viable-ecosystem-experience.md#quick-account-setup-and-optional-assets). Interaction owner: [DESIGN money entry](../../.agent/designs/argus/DESIGN.md#money-entry-in-the-ecosystem-sketch). Device verification and production contracts remain separate work. | Lucas |

| 2026-09-27 | Lock distinct account setup, new activity and balance-check actions; require an explicit discrepancy review and traceable adjustment without invented income/spending. Reuse the existing destructive confirmation for removal. Experience owner: [MVEE balance checks](argus-minimum-viable-ecosystem-experience.md#account-activity-and-balance-checks); technical follow-up: [backend handoff](argus-account-balance-reconciliation-handoff.md). | Lucas |

| 2026-09-27 | Lock simplified populated Home, bounded account previews, and inherited Recents/Omnisearch growing-list behavior. Preserve currency-separated net worth; combined conversion remains undefined. Owners: [MVEE Home summary](argus-minimum-viable-ecosystem-experience.md#populated-home-summary-and-list-boundary) and [DESIGN growing lists](../../.agent/designs/argus/DESIGN.md#growing-lists-across-ecosystem-surfaces). | Lucas |

| 2026-09-27 | Lock copy-link household invitations, user-shared WhatsApp links, do-blitz as the short-link integration direction, and Resend email delivery; no incentives. Detailed owner: [MVEE invitation delivery](argus-minimum-viable-ecosystem-experience.md#invitation-delivery-founder-locked-september-27-2026). Contact discovery and implementation contracts are not implied. | Lucas |

## Open (not locked)

Voice and chart direction was subsequently locked on September 28; see the
dated entry below. Sharing growth concepts remain recommendations, not an
approved expansion of the frozen mobile baseline.

The canonical list is [MVEE section 9](argus-minimum-viable-ecosystem-experience.md#9-decisions-deliberately-left-open).
The authority map identifies technical areas still requiring contracts before
implementation. Earlier documents' open-question lists are dated history;
do not treat them as reopening the decisions above.

## September 28, 2026 — UI completion checkpoint

The founder requested closing the Home, connected-plan, household contributor/
permission and financial-recovery experience gaps, including refunds and account
adjustments. The MVEE now owns those behaviors and the private Business-space
boundary. DESIGN owns quiet space navigation versus underlined section tabs.
The account reconciliation handoff records the unresolved posting, matching and
recovery contracts. This freezes a disposable UI reference; it does not authorize
backend implementation, change production contracts or establish release readiness.

## September 28, 2026 — account space reassignment

The founder approved the bounded Manage account journey: move between private
spaces, share separately with Household, preserve financial history, and review
linked records before confirmation. Detailed behavior is owned by the MVEE's
Reassigning accounts between spaces section. Production atomicity and permissions
remain contract work; this approval implements only the disposable UI sketch.


## September 28, 2026 — complete mobile design lock

Founder: “do a full sweep and lock the design for mobile, including your html
reports of full ecosystem … lock it in.” The local template and all six current
reports are frozen as one dated reference. The MVEE now records the final
Settings ownership and single Temporary-chat experience; DESIGN owns its stable
header and composer transitions. The [handoff](../reports/mobile-design-lock-2026-09-28.md)
links the source/evidence archive, checksum and implementation boundary.
This is design acceptance, not release readiness or an assignment to implement
all visible provider-dependent concepts. No backend, API, model prompt, deployment
or production data was changed.

## September 28, 2026 — voice and chart direction

Founder: “Yes, lock it,” approving full voice with xAI and the native chart
shortlist. Detailed technical owner: [architecture direction](../ARCHITECTURE.md#voice-and-chart-direction).
The [MVEE voice experience](argus-minimum-viable-ecosystem-experience.md#43-speak-to-argus)
now explicitly includes full spoken conversation. Vico remains subject to a
representative prototype, and integrated speech-to-speech orchestration remains
subject to preserving Argus's single runtime owner. This does not modify the
frozen HTML archive or authorize provider calls, implementation or deployment.

The founder also requested applying *Contagious* to ecosystem sharing. The
[research note](../research/2026-09-28-ecosystem-sharing.md) records source-backed
principles and a proposed bounded first experience. Specific growth surfaces,
metrics and mechanics in that note are not locked product requirements.

## September 28, 2026 — publication and recording reconciliation

The founder authorized pushing this branch and opening its publication PR, with
continuation prompts to be handed back for the other lanes. The MVEE clarifies
the already-approved confirmed-record exception to historical Decision 8 and
the final template's archive behavior: archived account balances and obligations
remain in the financial picture. Unconfirmed figures in chat retain their
existing conversation policy; no personalization-memory expansion is approved.
The [recording decision response](lanes/financial-recording-decision-response.md)
separates settled experience from remaining recommendations.

The founder parked public growth sharing until there is evidence of what users
want to share. Household invitations and file ingestion remain in scope.
