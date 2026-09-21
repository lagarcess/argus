# Clara personal finance platform

Approved scope: the founder's September 20 expansion to a broader finance platform plus Argus settings. This supersedes the deposit-only product scope in BUILD_PLAN.md. The deposit calculation and change-receipt path remains part of Clara.

## Product and architecture decisions

Clara opens on an account-first overview. Direct pages own ordinary tasks; a contextual assistant drawer explains the same records. Preserve cream, forest green and Georgia, and adapt Argus's focus handling, responsive panels, clear states, small controls and spacing.

Two designs were evaluated: a central financial ledger and federated domain modules with an outbox and projections. Choose one SQLite transaction owner with a canonical account/transaction ledger for financial totals, and natural typed records for goals, scenarios, identity and service workflows. Query bounded summaries directly rather than duplicating them in an outbox/projection system. The local volume does not justify a second consistency mechanism.

All modules use Store.connection. Platform tables are prefixed p_. Context carries user, household, session and role. Every household-owned query is scoped. Ledger amounts use integer minor units; external money and calculations use bounded Decimal strings. Currency totals remain separate without a dated FX quote. Sources distinguish publication, observation and recording dates. Saved scenario inputs and results are immutable.

Python Faker seeds 24 months and at least 12,000 transactions with deterministic identities, repeated merchants, salaries, refunds, transfers, multiple currencies and pending entries. Seed only an empty fixture manifest. Lists are paged on the server; summary queries cover the full filter. A failed connector refresh keeps its last data. No browser or request-time vendor polling.

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
- [ ] Foundation: shared contracts, composition, CI isolation (captain).
- [ ] Ledger: accounts, connections/sync failure, transactions/edit/split/search/filter/page, CSV preview/import, net worth/spending, Faker volume (ledger worker).
- [ ] Planning: budgets, recurring bills, goals/allocation, life-event and retirement scenario receipts (planning worker).
- [ ] Identity/settings: local sessions/passwords, profile/avatar/preferences, household roles, security, memory, archive/trash, export/reset/deletion, usage/help/feedback (identity worker).
- [ ] Investing: holdings/allocation/performance, separate simulated cash book, preview/confirm orders, recurring simulation, bundles, read-only price adapter (investments worker).
- [ ] Services: credit/report/history/payoff, tax organizer/export, estate inventory/beneficiaries/export, human-session reservations, membership/billing, employer benefits (services worker).
- [ ] Assistant: computed grounded question actions, optional semantic interpretation, conversations/save/archive, transparent health checks and navigable notices (assistant worker).
- [ ] Shell: responsive navigation, home, shared controls/evidence/dialogs, loading/error states, theme (shell worker).
- [ ] Feature views: ledger, planning, investing/services, settings, deposit integration (assigned UI workers/captain).
- [ ] Verification: focused domain tests, cross-module lifecycle/currency/isolation tests, 12k-row latency and pagination, desktop/mobile/bilingual browser flows, screenshots.
- [ ] Independent task reviews, whole-diff review, Codex review and required CI; merge only private branch.

## Acceptance journeys

1. Open the seeded household, inspect dated net worth/accounts, filter thousands of transactions, edit a category, import a validated CSV, and see account/spending/budget totals agree after reload.
2. Save a budget and recurring bill; record payment once; create and allocate a goal; calculate and save a scenario, then compare a changed assumption while preserving the original receipt.
3. Inspect portfolio, preview a simulated order, confirm once, and see fictional cash/positions change. Reject insufficient funds and preserve linked-account net worth.
4. Complete and reload credit, tax, estate, membership, employer and appointment demo workflows with honest local receipts/downloads.
5. Change profile/language/theme, enforce viewer and household isolation, revoke sessions, manage confirmed memories, archive/restore, export and delete/reset only local data.
6. Ask a typed grounded question, inspect its source records, save/reopen; no key means free-text interpretation is explicitly unavailable. Complete deposit compare/save/change-notice path through direct controls.
7. Verify 1440/1024/768/390/320 layouts, keyboard/escape/focus restoration, reduced motion, long text/amounts, empty/error states, Spanish/English and no horizontal overflow.

## Progress and evidence

Private base: d48249dc8f0fd955fa6ee16c11d99d4eb111aedb. Prior deposit delivery: PR #657. Expanded implementation has not yet passed verification. Record measured evidence and review results here as work completes.

### Capacity and review amendment

The founder additionally requested an audit of scoped reviews on prior merged PRs, fixes at the bug-class owner, and architecture supporting 10,000 monthly users. PR_REVIEW_AUDIT.md will record the verified prior review history and still-relevant deferred work. SCALE_DESIGN.md owns explicit workload assumptions, selected capacity mechanisms and local load evidence. Monthly active users are not simultaneous connections. No deployment or external database changes are authorized by this amendment.

### Implementation checkpoint

The ledger, identity/settings, planning, services, investing, assistant and direct frontend modules are implemented. Focused suites cover each domain; composed HTTP and browser verification are in progress. Local fixture has 13,680 transactions over 24 months, 14 accounts and four currencies. Initial read-only query measurements: paged transactions 12ms, spending 0.82ms, overview 11ms (not a hosted capacity claim).

Independent ledger review is clean. Identity final-membership cleanup and planning category/paginated scenario fixes passed scoped re-review. Service review found a subscription/authorization table-name collision, calendar expiry, historical membership replay and tax provenance gaps; fixes and regression tests are complete, awaiting scoped re-review. These changes address their shared domain owners rather than individual UI symptoms.
