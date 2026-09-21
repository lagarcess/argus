# Services backend review

Reviewed the frozen `services-review.diff` against `money-view/docs/PLATFORM_PLAN.md` and `money-view/docs/platform-api/services.md`. Read-only inspection; the reported 22 focused tests and clean Ruff result were not rerun. No application code, Git state, environment, providers, or services were changed.

**Spec compliance: changes requested. Code quality: changes requested.** Four reachable issues remain. The first is an integration-level data-owner collision that makes the membership workflow unusable and can delete identity authority during reset.

## Findings

### [P1] Give service subscriptions their own table instead of reusing identity membership authority

- **Location:** `money-view/server/platform/service_contracts.py:169-183`, especially the new `p_memberships` entry at line 180. Call sites are `money-view/server/platform/services.py:378-440` and the lifecycle loop at `money-view/server/platform/services.py:512-538`. The existing identity owner defines a different `p_memberships` schema at `money-view/server/platform/identity.py:44-49`.
- **Trigger:** Start the composed app. Composition initializes identity before services, so `p_memberships` already contains `(household_id,user_id,role)`. Then call `GET /api/platform/membership`, `POST /api/platform/membership`, household export, or household reset.
- **Actual result:** Membership reads select a nonexistent `document` column and membership writes target nonexistent `id` and `document` columns, producing SQLite errors instead of the documented response. Export fails for the same reason. More seriously, `services.clear_data` executes `DELETE FROM p_memberships WHERE household_id=?` against the identity table, so household reset removes every user's authorization membership even though the reset response promises `requires_login: false`; the next context lookup cannot authenticate the household session. `services.usage_data` also counts identity memberships as service records.
- **Why the focused tests miss it:** `test_platform_services.py:16-34` initializes only `Store` and `services`, so services creates its private document-shaped table before identity is present. The real composition order exposes the collision.
- **Requested change:** Rename the service subscription table to a domain-owned name such as `p_service_memberships` everywhere in initialization, CRUD, export, clear, and usage. Add one composed-boundary regression that initializes identity then services, exercises the membership API, and proves reset clears subscription data while preserving identity membership/session authority.

### [P1] Replenish the fixed appointment catalog after its September 2026 slots expire

- **Location:** `money-view/server/platform/services.py:87-104` seeds twelve fixed slots starting September 21, 2026 and permanently short-circuits on the `services-v1` manifest. `services.py:230-241` and `services.py:245-258` reject or hide expired slots.
- **Trigger:** Open the demo after the last seeded slot has started, or restart the persisted database after that date.
- **Actual result:** Every slot is returned with `available: false`, every reservation attempt returns `slot_expired`, and initialization refuses to create a future catalog because the manifest already exists. The human-session acceptance journey therefore becomes permanently unusable through ordinary passage of time.
- **Requested change:** Give the local catalog one bounded owner that ensures a future set of demo slots exists without changing or deleting historical reservations. Cover a restart after all prior slots expire and prove a new reservation can be saved while the global one-active-reservation-per-slot constraint remains intact.

### [P2] Return a coherent result when an older membership request key is replayed

- **Location:** `money-view/server/platform/services.py:395-423`.
- **Trigger:** Subscribe to the annual plan with request key A, change to the monthly plan with request key B, then retry the original annual request with key A.
- **Actual result:** The idempotency branch returns the original annual receipt together with the current monthly membership. The response differs from the original response and its two records disagree about the plan, even though the API contract declares the request-key operation idempotent.
- **Requested change:** Persist or reconstruct the response owned by each request key so replay returns one internally consistent operation result without overwriting the newer current membership. Add the three-request sequence above as the behavioral regression.

### [P2] Attach dated source evidence to the tax scenario figures

- **Location:** `money-view/server/platform/tax_estate.py:137-169`; the response contains totals, rate, formula, and legal status but no source IDs or dates.
- **Trigger:** Calculate any tax worksheet scenario, especially one whose income and expense items have different effective dates.
- **Actual result:** The endpoint emits financial figures without exposing the dated records used to calculate them. A caller cannot determine the observation date or inputs from the result, which conflicts with `PLATFORM_PLAN.md:22` (no financial figure without dated evidence). The `worksheet_only` label and explicit rate correctly limit the legal claim, but they do not supply provenance.
- **Requested change:** Extend the service API handoff and response with calculated evidence that references the organizer/item IDs and their effective dates, following the payoff result's existing calculated-evidence pattern. Do not invent a publication date.

## Verified design and limits

- Payoff math uses Decimal, currency precision, half-up monthly interest, capped final payment, the documented 1,200-month horizon, and the correct non-amortizing boundary `payment <= monthly interest`. No confirmed payoff-formula defect was found.
- Tax scenarios use only the user's explicit rate and are labelled `worksheet_only`; no national tax calculation is implied. Organizer completion gates document/checklist items as documented.
- Beneficiary shares validate total allocation and duplicate contacts before one atomic replacement; contact and asset lookups are household-scoped.
- Appointment writes run under `BEGIN IMMEDIATE`, and the partial unique index enforces one active reservation per slot globally. Reservation request-key conflict, reschedule, cancellation, and calendar behavior otherwise match the handoff.
- Credit, tax, estate, appointment, membership, and employer mutations enforce viewer restrictions. Record lookups are household-scoped. The table collision above is the exception that crosses domain ownership.
- The reviewed service code performs no network, payment, invitation, booking, filing, legal, employer, or other external action. Downloads are local responses, and CSV cells receive formula-injection protection.

The domain-model skill led the table-ownership check, boundary discipline focused the API and persistence transitions, and behavior-test review exposed why the service-only fixture stays green despite the composed failure. Review complete; no active follow-up retained.

## Fix delta re-review

Reviewed `services-review-fix.diff` and `services-fix-report.md`, limited to the four findings above and regressions introduced by their fixes. The reported 54 combined service/identity tests, four parent composed tests, and clean Ruff result were not rerun.

**Spec compliance: pass. Code quality: pass.** All four findings are resolved, and no new actionable issue was found in the fix delta.

- Service subscriptions now use the domain-owned `p_service_memberships` table throughout CRUD and lifecycle callbacks. The composed regression initializes identity first, then proves membership, export, reset, retained session access, authority-row preservation, and restart behavior.
- One `ensure_future_slots` owner creates six future UTC days at initialization and catalog reads, removes only expired unreferenced catalog rows, and preserves both current and original slots for every reservation. The regression covers clock advance, restart/read renewal, reservation history, and global slot uniqueness.
- Membership replay reconstructs its historical membership and receipt from the immutable receipt while leaving the newer current subscription or cancellation unchanged. The annual A, monthly B, replay A, cancel, replay A sequence is covered.
- Tax scenarios now expose calculated evidence, all financial input IDs, each source's effective and recording dates, source kind, and separate user-rate evidence without inventing publication dates. Beneficiary replacement also records its actual write timestamp and updates the API handoff.

The delta adds only local SQLite/catalog maintenance and response provenance. It introduces no payment, booking, invitation, filing, employer, provider, or other external action. Fix re-review complete; no follow-up finding remains.
