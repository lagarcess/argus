# Clara personal finance platform

Approved scope: the founder's September 20 expansion to a broader finance platform plus Argus settings. This supersedes the deposit-only product scope in BUILD_PLAN.md. The deposit calculation and change-receipt path remains part of Clara.

## Product and architecture decisions

Clara opens on an account-first overview. Direct pages own ordinary tasks; a contextual assistant drawer explains the same records. Preserve cream, forest green and Georgia, and adapt Argus's focus handling, responsive panels, clear states, small controls and spacing.

Two designs were evaluated: a central financial ledger and federated domain modules with an outbox and projections. Choose one SQLite transaction owner with a canonical account/transaction ledger for financial totals, and natural typed records for goals, scenarios, identity and service workflows. Query bounded summaries directly rather than duplicating them in an outbox/projection system. The local volume does not justify a second consistency mechanism.

All modules use Store.connection. Platform tables are prefixed p_. Context carries user, household, session, role and the captured household data generation. Private writes check current membership and generation inside their transaction. Every household-owned query is scoped. Ledger amounts use integer minor units; external money and calculations use bounded Decimal strings. Currency totals remain separate without a dated FX quote. Sources distinguish publication, observation and recording dates. Saved scenario inputs and results are immutable.

Python Faker seeds 24 months and 13,680 transactions across 14 accounts and four currencies with deterministic identities, repeated merchants, salaries, refunds, transfers, multiple currencies and pending entries. Seed only an empty fixture manifest. Lists are paged on the server; summary queries cover the full filter. A failed connector refresh keeps its last data. No browser or request-time vendor polling.

## Global constraints

- Worktree and codex/clara-platform only; PR target and authorized merge destination only codex/money-placement-pilot.
- No deployment, production changes, main or codex/private-alpha-next writes, .env writes, or Supabase migrations.
- All unavailable vendors are explicit local simulations. No real orders, money movement, invitations, payments, bookings, tax filings or legal submissions.
- Alpaca may supply read-only data through a separately invoked local load job only after safe configuration verification. No broker execution capability.
- Spanish first and English parity. No em dashes in user copy. No investment-adviser or recommendation claims. Deposit rates remain published averages, with source/date and the branch-quote limitation.
- No financial figure without dated evidence. Synthetic observations are visibly synthetic. User records show recording/effective dates rather than invented publication dates.
- Normal language is interpreted by a model. The keyless demo uses explicit typed question/actions, never keyword, regex or language routing.
- Independent workers own disjoint files; captain owns composition, shared contracts, Git, CI and integration. No worker reverts another's work or starts production services.

## Integration contract

Shared Python helpers live in server/platform/common.py. Each domain exports initialize(store), an APIRouter named router with /api/platform prefix, and domain functions/classes used by the router. Routers obtain Store and Context through common.get_store/get_context. Identity sets app.state.identity and exposes context(request). All initialization is local SQLite and idempotent. Module seeds reference household-demo and household-other and user-demo/user-partner/user-viewer fixtures.

Domain workers write a concise API handoff in docs/platform-api/<domain>.md before finishing implementation so UI workers consume exact contracts. All errors use PlatformError(code,status); UI owns localized error prose. Sources use Evidence. All frontend feature modules export a page component accepting PlatformPageProps from platform/types.ts. Shared api/client, primitives and CSS belong to the shell worker. Each feature owns its own translation catalog and optional scoped CSS.

## Delivery checklist and owners

- [x] Scope/design alternatives, feature checklist, isolation branch.
- [x] Foundation: shared contracts, composition, CI isolation (captain).
- [x] Ledger: accounts, connections/sync failure, transactions/edit/split/search/filter/page, CSV preview/import, net worth/spending, Faker volume (ledger worker).
- [x] Planning: budgets, recurring bills, goals/allocation, life-event and retirement scenario receipts (planning worker).
- [x] Identity/settings: local sessions/passwords, profile/avatar/preferences, household roles, security, memory, archive/trash, export/reset/deletion, usage/help/feedback (identity worker).
- [x] Investing: holdings/allocation/performance, separate simulated cash book, preview/confirm orders, recurring simulation, bundles, read-only price adapter (investments worker).
- [x] Services: credit/report/history/payoff, tax organizer/export, estate inventory/beneficiaries/export, human-session reservations, membership/billing, employer benefits (services worker).
- [x] Assistant: computed grounded question actions, optional semantic interpretation, conversations/save/archive, transparent health checks and navigable notices (assistant worker).
- [x] Shell: responsive navigation, home, shared controls/evidence/dialogs, loading/error states, theme (shell worker).
- [x] Feature views: ledger, planning, investing/services, settings, deposit integration (assigned UI workers/captain).
- [x] Independent implementation reviews and scoped re-reviews closed clean for the implemented domains.
- [x] Local verification: 419 backend tests, lint/build, and 26 browser journeys with 116 unchanged source hashes and durable screenshots. See the [verification checkpoint](evidence/platform/verification.md).
- [x] Bounded local capacity acceptance: 10,000 identities, five million generated rows, 20 RPS for ten minutes and 40 RPS for one minute, followed by a fresh-source probe. Full retention and target-host qualification remain explicitly unverified in [SCALE_EVIDENCE.md](SCALE_EVIDENCE.md).
- Final GitHub review, CI and private integration: the terminal audit on [PR #658](https://github.com/lagarcess/argus/pull/658) is the authoritative record. Only `codex/money-placement-pilot` may receive the merge.

## Acceptance journeys

1. Open the seeded household, inspect dated net worth/accounts, filter thousands of transactions, edit a category, import a validated CSV, and see account/spending/budget totals agree after reload.
2. Save a budget and recurring bill; record payment once; create and allocate a goal; calculate and save a scenario, then compare a changed assumption while preserving the original receipt.
3. Inspect portfolio, preview a simulated order, confirm once, and see fictional cash/positions change. Reject insufficient funds and preserve linked-account net worth.
4. Complete and reload credit, tax, estate, membership, employer and appointment demo workflows with honest local receipts/downloads.
5. Change profile/language/theme, enforce viewer and household isolation, revoke sessions, manage confirmed memories, archive/restore, export and delete/reset only local data.
6. Ask a typed grounded question, inspect its source records, save/reopen; no key means free-text interpretation is explicitly unavailable. Complete deposit compare/save/change-notice path through direct controls.
7. Verify 1440/1024/768/390/320 layouts, keyboard/escape/focus restoration, reduced motion, long text/amounts, empty/error states, Spanish/English and no horizontal overflow.

## Progress and evidence

Private base: d48249dc8f0fd955fa6ee16c11d99d4eb111aedb. Prior deposit delivery: PR #657. The expanded modules are implemented. The verification checkpoint and PR terminal audit distinguish local acceptance, review closure and the authorized private merge. This is not a deployment or hosted-capacity claim.

### Capacity and review amendment

The founder additionally requested an audit of prior merged PR review loops, fixes at the bug-class owner, and architecture supporting 10,000 monthly users. The completed [prior PR audit](PR_REVIEW_AUDIT.md) verifies PR #657's clean latest-delta acknowledgment and zero unresolved threads before its private merge. The [scale design](SCALE_DESIGN.md) owns workload assumptions and capacity decisions. [Scale evidence](SCALE_EVIDENCE.md) records measurements and their limits. Monthly active users are not simultaneous connections. No deployment or external database changes are authorized.

One SQLite Store remains the transaction owner. The implementation now supports local authenticated households and multiple API processes on one host, with WAL, shared job claims, leases and admission counters. This does not establish hosted authentication, multi-host availability or production readiness. The [runtime contract](platform-api/runtime.md) owns exact request, queue, login and semantic-admission behavior and configuration. Semantic limits count calls and concurrent attempts, not dollars; pricing remains unknown.

Household export shares a 50,000-source-row and 32-MiB serialized-source-byte budget across all registered domains. Overflow fails with HTTP 413 and no partial download. The [identity contract](platform-api/identity.md) owns export and lifecycle details. The local backup/restore CLI uses SQLite's backup API and validates a manifest when restoring to a new file; commands are in the [README](../README.md). Neither local backups nor laptop measurements establish off-host recovery or hosted capacity.

### Implementation checkpoint

Ledger, identity/settings, planning, services, investing, assistant, deposits and direct frontend pages are implemented. Independent implementation reviews and their scoped follow-ups have closed clean. Fixes addressed domain ownership, including identity cleanup, planning category/page consistency, service membership authority, calendar expiry, historical replay and tax provenance. The account/transaction ledger remains the single owner of financial totals. The platform preserves deposit confirmation inputs, source-owned synthetic country labels and immutable saved receipts from PR #657.

The deterministic fixture contains 13,680 transactions over 24 months, 14 accounts and four currencies. Combined verification, browser evidence and bounded capacity measurements are linked above. Follow-up review fixes and their checks are recorded in the verification checkpoint and PR audit. Current measurements belong in [SCALE_EVIDENCE.md](SCALE_EVIDENCE.md). The 10,000-monthly-user target still requires the declared sustained workload, full retention/heavy-household tests and target-host qualification.

### Capability truth

The app has account-first pages and a contextual assistant, local passwords/sessions/household roles, planning and service records, simulated investment execution, and the direct deposit compare/save/change-notice path. Vendors, account activity, investment prices, bank rates, inflation and service actions in the ordinary demo remain visibly simulated. No external order, money movement, email, invitation, booking, tax filing or legal submission occurs. Public hosting and outbound email are absent.

On September 21, 2026, one explicit Alpaca adapter GET for SPY on the IEX feed succeeded in an isolated local verification database. Its observation date was September 18. The [receipt](evidence/scale/alpaca-readonly.json) verifies only that bounded read; the ordinary demo database stays on fixtures. The [investing contract](platform-api/investing.md) owns the explicit read-only adapter and CLI configuration.

Live SB/BCRD loading, calculation-ready bank-data semantics and data reuse permission remain unverified. Deposit rates remain published averages with the branch-quote limitation, simple ACT/365 calculation and dated source receipts. No live LLM evaluation has run. Keyless prepared actions remain deterministic; configured free text requires semantic interpretation. Do not read a mocked semantic path or attempt counter as model-quality or cost evidence.
