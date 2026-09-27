# Canon map for listing-assisted asset values

Read-only audit of `origin/codex/private-alpha-next` at `f0a90763b79e5625ac0a4789cdfa171cda023963`, 2026-09-27. The question is whether Dominican vehicle and residential-property classified listings could help a user review and update the estimated value of a vehicle or property recorded in Accounts. This file maps canon and code. It changes no product decision.

## Legend

- (A) Approved. Founder-locked direction and rules that bind all work: MVEE, decision log, PRODUCT.md direction, DESIGN.md conventions, AGENTS.md rules.
- (A-pkg) Wave 1 package rule. It binds assigned Wave 1 work only. The authority map calls these "package-era choices, not permanent limits on the ecosystem." (DA:81)
- (B) Implemented at this commit, with the code path. (B-doc) is a technical-contract statement, followed by my grep spot-check result.
- (C) Unresolved. An explicit open decision, or a silent gap that no document answers.
- (R) Research input or archived history. It holds no scope authority: "Inputs and provenance, not independent scope authority" (DA:25). I added this label because forcing research into A, B, or C would misstate its standing.
- *Inference* marks my reading. Text inside straight double quotes is verbatim source text with a line reference; terms I name are in italics. Section 6 holds the script that checked every quote against its cited lines.

| Alias | Path |
| --- | --- |
| MVEE | `docs/specs/argus-minimum-viable-ecosystem-experience.md` |
| DA | `docs/DOCUMENTATION_AUTHORITY.md` |
| DL | `docs/specs/argus-decision-log.md` |
| PRODUCT | `docs/PRODUCT.md` |
| DESIGN | `.agent/designs/argus/DESIGN.md` |
| AGENTS | `AGENTS.md` |
| RULES | `.agent/rules/coding-standards.md` |
| ARCH | `docs/ARCHITECTURE.md` |
| API | `docs/API_CONTRACT.md` |
| DM | `docs/DATA_MODEL.md` |
| W1R | `docs/specs/wave-1/00-shared-rules.md` |
| W1S0 | `docs/specs/wave-1/01-stage-0-safety-and-analytics.md` |
| W1S1 | `docs/specs/wave-1/02-stage-1-layout-ai-landing-card-payoff.md` |
| W1RD | `docs/specs/wave-1/README.md` |
| MAP | `docs/research/2026-09-26-dr-latam-finance-painpoints-mvee.md` |
| SRC | `docs/research/2026-09-26-dr-latam-finance-social-research-source.md` |
| EXEC | `docs/research/2026-09-26-dr-latam-finance-executive-summary-source.md` |
| ATST | `docs/archive/2026-09-26-argus-answers-that-stay-true-roadmap.md` |
| GF | `docs/archive/2026-09-17-argus-grounded-finance-roadmap.md` |
| PIVOT | `docs/archive/2026-09-26-argus-pivot-strategy.md` |
| LEDGER | `docs/reports/payment-ledger-reuse-assessment.md` |
| HSPEC | `docs/superpowers/specs/2026-09-26-synthetic-ingestion-harness.md` |

`docs/specs/argus-answers-that-stay-true-roadmap.md` and `docs/specs/argus-pivot-strategy.md` are compatibility pointers only. Their full text is archived as ATST and PIVOT. The MVEE names the chat destination *Argus* in the primary bar (MVEE:70) and places Updates in the header: "Updates and profile live in the header, outside the primary bar." (MVEE:76)

## 0. Bottom line

This section is my synthesis (inference); sections 1 to 5 carry the evidence.

1. No canon document names vehicles or residential property as account types. The MVEE minimum list stops at cash, checking, savings, investments, credit cards, and other debts (MVEE:101). PRODUCT.md only says engine limits "do not prohibit users from recording diverse personal assets" (PRODUCT:343).
2. No canon document mentions classified listings, comparables, SuperCarros, SuperCasas, Corotos, market value, or asking price (section 3). The nearest statement is (R) research warning against "Net-worth vanity with Zillow-style home values." (SRC:329)
3. No financial-record code exists. The 81 migrations in `supabase/migrations/` create 43 distinct tables, and none holds accounts, assets, transactions, households, notifications, or exchange rates. No API route or web route serves Home, Accounts, Plan, or Updates. The disposable financial UI sketch is not in this tree.
4. Approved canon already describes a propose-then-confirm shape. New proposed records need confirmation (MVEE:129), drafts change no totals (MVEE:261), and automatic acceptance needs an explicit policy (MVEE:254). No (A) statement forbids a listing-derived proposal that the user confirms.
5. The closest implemented mechanism is the chat computed-answer card. Its inputs carry a provenance kind, a page input carries title and date, and an on-demand refresh re-reads page inputs without rewriting the stored answer (API:5710-5720). It lives in chat messages, not in financial records.
6. The feature depends on open items: record schema, chat-to-record integration, monitoring and scheduling, notification channels, automatic-acceptance policy, market inventory and commercial relationships, household ownership mechanics, and an FX source that Wave 1 leaves to the founder (section 2).

## 1. Topics

### 1.1 Vehicles and real estate as account types

- (A) "Minimum account types include cash, checking, savings, investments, credit cards, and other debts. Cash is first-class." (MVEE:101)
- (A) PRODUCT.md says the backtest engine limits "do not prohibit users from recording diverse personal assets" (PRODUCT:343). Inference: this permits the idea but approves no asset record type.
- (A) "A feature omitted from the MVEE is not implicitly retired." (DA:40) Inference: this protects existing features. It does not approve new account types.
- (A) The boundary test for any capability: "does it help someone understand, maintain, or improve the same financial picture?" (MVEE:312)
- (A) Housing is scenario-only in the minimum: "Supported payment scenarios and savings goals can help exploration." (MVEE:355) "Mortgage underwriting, preapproval, access to a lender, and dedicated qualification workflows are not minimum capabilities promised here." (MVEE:355)
- (A-pkg) Hidden in Wave 1: "net worth, accounts, Discover, uploads, budgets, debt goals, Pro+/Rewards, WhatsApp." (W1R:34)
- (B) Not found. `grep -rliE 'veh[ií]cul|real[_ ]?estate|inmueble|net[_ ]?worth|patrimonio|bienes ra[ií]ces'` over the worktree outside `docs/`, `node_modules`, `.next`, and `.git` returns nothing.
- (R) "That matches how Dominican households think about wealth: a house first, markets later (if ever)." (SRC:48)
- (R) "Housing and investing can be aspirations supported by the same record and scenario tools." (MAP:230)
- (C) Whether a vehicle or home is an account, a holding, or a new record kind is open under "Financial-record schema, balance/transaction reconciliation model, money arithmetic contracts, migrations, and historical-data conversion." (DA:54)

### 1.2 Other assets

- (A) "Track investments initially through recorded balances or holdings without requiring a portfolio terminal." (MVEE:110)
- (A) "Users can add accounts, opening balances, transactions, debts, holdings, goals, and corrections without AI." (MVEE:183)
- (A) "Someone who only knows their current balance can record that fact without inventing a complete transaction history." (MVEE:185) Inference: this is the nearest approved pattern for a value-only asset.
- (B) In code, *valuation* means securities scenarios: "Valuation scenarios from typed inputs, as labeled low-to-high ranges." (src/argus/domain/finance/valuation.py:1) `src/argus/domain/calculations/` holds bond value, debt-to-income, discounted cash flow, effective rate, expense ratio, growth projection, income yield, price multiple, ranked comparison, time value, and valuation scenarios. A grep for `depreciat` in `src/` finds no depreciation or appraisal calculator.
- (R) Informal lenders belong "in the same debt list as the bank." (EXEC:76)

### 1.3 Asset fields (nickname, currency, estimated value, ownership share, related debt)

- (A) Accounts minimum: "Inspect balance, currency, activity, source, and last-updated date." (MVEE:106)
- (A) Currency: "preserve source currency; ask when ambiguous. Do not infer dollars or pesos from an unqualified amount." (MVEE:260)
- (A) "Account ownership, visibility, and permission to edit are distinct." (MVEE:402)
- (C) No canon names nickname, estimated value, ownership share, or related debt as fields. The schema is open (DA:54). DM says the MVEE's "financial records and household permissions still need explicit schema and access-control design." (DM:7)
- (B) Test-only fields exist in `tests/synthetic_ingestion/factories.py:10-19`: source_id, date, description, amount, currency, kind, account, destination. The module states it is "Provisional local lifecycle scaffolding, not a product API or permission model." (tests/synthetic_ingestion/harness.py:1) Its spec says "No canonical API/data contract changes. All formats are provisional scaffolding." (HSPEC:26)
- (B) `Money` holds `amount: float` (src/argus/domain/finance/money.py:14).
- (R) A 2026-09-27 report advises "Store minor units as integers." (LEDGER:17)

### 1.4 Ownership share and personal versus household views

- (A) "The personal view contains the person's own financial picture and any joint accounts they are authorized to see, with ownership clearly labeled." (MVEE:394)
- (A) "The household view combines explicitly shared information, rather than summing two personal dashboards." (MVEE:394)
- (A) "One joint account can appear in both personal and household contexts without becoming two accounts or being counted twice." (MVEE:111)
- (A) "Make contribution responsibilities understandable without requiring a 50/50 split." (MVEE:411)
- (A) "Describe totals as based on shared records, not as everything either partner owns." (MVEE:407)
- (A) "Information that was not shared must not be silently included in shared calculations" (MVEE:425)
- (A) "Label individual versus joint ownership and who can see or edit the record." (MVEE:409)
- (C) "Household membership lifecycle, permission enforcement/RLS, ownership, revocation, deletion, and retention implementation." (DA:55) "Exact retention and ownership mechanics remain implementation decisions." (MVEE:403)
- (C) Silent gap. The canon knows individual and joint ownership only. A grep for `ownership share|co-own|coown|copropie|percent(age)? (of|owned)|share of ownership` over MVEE, PRODUCT, DA, DL, DESIGN, ARCH, API, DM, Wave 1, MAP, and AGENTS returns one unrelated hit (a card minimum payment at W1R:423), so fractional shares have no rule.
- (B) Not implemented. "Argus household permissions are not implemented." (LEDGER:57) No household table exists among the 43.

### 1.5 A related loan counted once

- (A) "Transfers between owned accounts are not spending. A credit-card payment must not count purchases twice." (MVEE:113)
- (A) Transfers and repayments: "link the two sides where known and avoid double-counting spending or income." (MVEE:263)
- (A) "A shared bill appears once in the household obligation total" (MVEE:423)
- (A) "Do not silently guess an account, currency, debt, or transfer relationship when the choice changes the financial picture." (MVEE:195)
- (C) Silent gap. No rule links a debt to the asset it financed (car loan, mortgage), nets equity, or keeps the debt counted once when the asset shows in two contexts.

### 1.6 Asset value versus spendable cash

- (A) "An account balance is not the same as money remaining after commitments." (MVEE:54)
- (A) "When information is missing, make that visible instead of presenting an unconditional “safe to spend” number." (MVEE:54)
- (A) "A planned contribution is not actual available cash." (MVEE:423)
- (A) The pain-point table says "Home relates dated commitments to recorded money and explicit income assumptions" (MVEE:341). Inference: *recorded money* reads as cash and balances, not an illiquid estimate.
- (R) "Illiquid housing + informal assets will produce fake richness." (SRC:329)
- (C) Silent gap. Nothing says whether an estimated asset value stays out of the remaining-money estimate, or how illiquidity is labeled.

### 1.7 A valuation change as income or spending

- (A) "Changes to a balance must not silently manufacture income or spending." (MVEE:113)
- (A) Reconciliation must "distinguish a balance correction from a new transaction. Explain discrepancies; never invent missing activity to force agreement." (MVEE:264)
- (A) Accounts minimum: "Record spending, income, transfers, payments, and balance corrections." (MVEE:107)
- (C) Gap. Whether a revaluation appears under Home's "What changed?" (MVEE:85) and in activity history is unspecified. Inference: canon treats it as a balance update, never income or spending.

### 1.8 Who owns durable financial facts

- (A) "The confirmed record is the durable financial fact." (MVEE:177) Of chat messages, uploaded files, notifications, and extracted text, the MVEE says "they are not independent competing ledgers." (MVEE:177)
- (A) "Home, Accounts, Plan, Search, and Updates derive from the same confirmed records." (MVEE:177)
- (A) "Capture → interpret/extract → review and resolve → confirm → save the canonical record → update dependent surfaces." (MVEE:175)
- (A) "Input methods converge on confirmed financial records; guesses and hypothetical scenarios must not silently change actual balances." (PRODUCT:44-45)
- (A) "Treat Supabase as the canonical persistence layer." (AGENTS:966) "Persistent user and product state must live in one canonical system." (ARCH:36)
- (A) External data: "Argus can observe what its sources provide" (MVEE:161), and transparency "it does not certify every external source as correct" (MVEE:349).
- (A) "research turns never write strategy/confirmation/execution state, and the shared research cache is public-market data only, never reusable for anything user-scoped." (AGENTS:434)
- (A) "new financial records and chat integration still require explicit technical contracts" (PRODUCT:184-185)
- (B) Personalization memory cannot hold financial facts. `MemoryCategory` has four values (src/argus/memory/contracts.py:27-31), and `RESTRICTED_FINANCIAL` is a suppressed context (src/argus/memory/policy.py:37-42).
- (R) Decision 8, 2026-09-08: "Stated personal figures are ephemeral facts." (GF:1791) "No new storage, no new retention surface" (GF:1796)
- (B-doc) Current contracts still cite decision 8 for the country field (API:1048): "inferred from conversation, IP or behavior (decision 8)" (DM:192).
- (R) The 2026-09-27 ledger report says decision 8 "remains the storage rule" (LEDGER:67). "A salary, an expense, or a debt the user types stays in the conversation and is not stored as a ledger balance." (LEDGER:67)
- (C) Decision 8 and MVEE:177 need explicit reconciliation before chat can create or update an asset record (inference).

### 1.9 Corrections, revision history, and source dates

- (A) Corrections: "let users edit, undo, or remove mistakes and see the resulting changes across surfaces. Keep enough history to explain changes." (MVEE:265)
- (A) "Manual corrections should be available for every imported or interpreted record." (MVEE:187)
- (A) Dates: "distinguish activity date, statement/as-of date, and capture/refresh time." (MVEE:259)
- (A) "Make it possible to identify who recorded or corrected an entry" (MVEE:424)
- (A) "Approve ingestion experience and its confirmation, correction, provenance, and freshness boundaries; experimental access paths are not provider commitments." (DL:17)
- (B) Test-only. The harness appends before, after, and reason on each correction (tests/synthetic_ingestion/harness.py:204-205) and rejects "Correction requires a reason and known fields" (tests/synthetic_ingestion/harness.py:199).
- (B) Computed answers keep history by never mutating: "the stored result never moves." (DESIGN:303) "The stored answer, its card and its marker are never rewritten." (API:5719-5720)
- (C) Revision storage, retention length, and who-changed metadata for records are unspecified (DA:54, DA:55).

### 1.10 Currency and exchange rates

- (A) "Treat DOP and USD separately. Do not silently combine currencies. Any future conversion must expose its rate, date, and source." (MVEE:66)
- (A) Home shows "A clear summary of recorded assets and debts, separated by currency." (MVEE:90)
- (A) Among AI responsibilities, adapt "and to the currency of the user's locale" (PRODUCT:248).
- (A-pkg) "pesos are `RD$`, dollars are `US$`." (W1R:30) "Wave 1 has no exchange-rate source, and the money code refuses to add two currencies" (W1R:30)
- (A-pkg) "A combined total waits for a dated rate source." (W1R:30) "When it exists, every conversion shows the rate and its date." (W1R:30)
- (C) FX source: "Which source to use is Lucas's call" (W1R:30).
- (B) Found. `Money` refuses to mix: "Money combines only within one currency" (src/argus/domain/finance/money.py:42).
- (B-doc) Profile currency: "`currency` is read-only: `currency_override` when the user chose one, otherwise the currency the country implies" (API:1049-1050). Found in `src/argus/api/schemas.py` and `supabase/migrations/20260911120000_add_profile_home_country.sql`. "Country and currency are registered-account preferences. Guests cannot update a profile" (API:3116-3117).
- (B-doc) Comparing two answers: "so money in another currency has none." (API:5694)
- (B) No FX source. A grep for `exchange[_ ]?rate|fx_rate` in `src/` finds only interpreter prompt text. It sends a figure the user did not state, including "local inflation or exchange rates" (src/argus/agent_runtime/interpreter/unsupported_admission.py:105), to research.
- (B) Computed cards print money with `currencyDisplay: "code"` (web/lib/tool-result-card.ts:172). Inference: that differs from the Wave 1 RD$ rule, and it is outside this audit.
- (R) The archived pilot showed "explicit currency provenance with no silent conversion, provider data loaded by jobs with the last good publication preserved" (PIVOT:292-294).
- Inference: a USD-priced comparable cannot inform a DOP record until an FX source exists.

### 1.11 Evidence and provenance display

- (A) Provenance must "distinguish user-entered, extracted, connected, and calculated information." (MVEE:258)
- (A) "Retain enough source context to explain a record without spreading sensitive raw content everywhere." (MVEE:258)
- (A) "Explain assumptions, currency, source coverage, and freshness." (PRODUCT:51)
- (A) "Context should carry sources and freshness, acknowledge uncertainty, and remain informational." (PRODUCT:415-417)
- (A) "General-knowledge responses must be distinguishable from current research; assumptions and source freshness stay visible." (PRODUCT:76-77)
- (A) Computed cards show "one quiet provenance line: stated by you, the page title and date it was read from" (DESIGN:301).
- (A) "Each grounded discovery row carries one muted domain chip" (DESIGN:259), and the footer avoids an as-of date "because the search date is not the articles' date" (DESIGN:263). "each source shows its own date in the drawer" (DESIGN:263-264)
- (A) With no sources, "the ungrounded signal, derived, never asserted." (DESIGN:266-267)
- (B) `ToolFactSourceKind` is user, page, market_data, assumption, computed, not_found (src/argus/domain/tool_contracts.py:34-36). "A page names its title and date, market data names the date of its bar, and nothing else carries a citation." (src/argus/domain/tool_contracts.py:92-93)
- (B) The research drawer "keeps one page per publisher, then applies the drawer cap." (src/argus/domain/research/source_selection.py:5-6) The cap is `MAX_SOURCES = 5` (src/argus/domain/research/contracts.py:36). Inference: several comparables from one classifieds site collapse to one cited page.
- (C) The four MVEE provenance classes have no external-estimate class. Whether a listing-derived value is *extracted* or *calculated* is undecided (inference).

### 1.12 Stale or unavailable evidence

- (A) Freshness: "an old known balance remains old, even if Argus opens the screen today." (MVEE:266) "The app must not imply continuous awareness beyond available data." (MVEE:266)
- (A) "A failed refresh must preserve existing records and their old freshness timestamp." (MVEE:252)
- (A) "Incomplete information should still be useful: say “Based on your recorded accounts” and show freshness" (MVEE:97)
- (A) Household Home must "Identify missing or stale information." (MVEE:407)
- (A) "A lookup that fails answers from Argus market data and stated assumptions and says what it could not look up" (DESIGN:304)
- (A) Reopened decisions "show the stored result and today's side by side" (DESIGN:303).
- (B-doc) "Stated inputs keep their values, and a cited input no page states today keeps its stored value and date." (API:5713-5714) Found. The route is at src/argus/api/routers/computations.py:105, and the page filter is at src/argus/api/chat/computed_answers.py:483.
- (B) "A source with no publisher date remains eligible because a live page can plausibly be current." (src/argus/domain/research/source_selection.py:70-71) Inference: undated listing pages would pass this filter.
- (C) No staleness threshold exists for any record or estimate.

### 1.13 Updates, reminders, notifications, external-fact monitoring

- (A) Update categories include "changed conditions relevant to saved answers/plans, and records needing review or refresh." (MVEE:157)
- (A) "Every update should explain what changed, why it matters, and where to act." (MVEE:159)
- (A) "Distinguish changes in user records from external market changes." (MVEE:161)
- (A) "Notifications should invite a return without exposing financial amounts in push/email previews." (MVEE:163)
- (A) Journey: "A relevant recorded or external fact changes → Argus creates an explainable update" (MVEE:288)
- (A) Notifications are "Hidden/flagged for Alpha" (PRODUCT:99). Approved change: "Enable as part of the next product push; behavior follows the MVEE Updates experience." (PRODUCT:99)
- (A-pkg) "No amounts leave the app." (W1R:32) "Not in emails, push, analytics events or logs." (W1R:32)
- (A-pkg) Reminder events: "property is the channel (`email` / `push`). Fires in stage 3." (W1S0:50)
- (B) The reminder event models exist (src/argus/observability/analytics_events.py:178, 184). No reminder feature exists.
- (B-doc) API section 19 documents a `flags.notifications` value (API:6436-6442). Not found. A grep for `notifications` in `src/`, `web/lib`, `web/app`, and `web/components` finds no such flag. Outbound mail exists only for feedback to support (src/argus/api/feedback_notification.py) and access-approval email (src/argus/domain/access_approval_email.py, sent through src/argus/domain/resend_email.py). No user-facing update, reminder, or push path exists.
- (B) No scheduler re-checks external facts. The only re-check is the user-triggered refresh: "Look the answer's cited inputs up again" (API:5683). It "is claimed under the research allowance before any provider work and recorded in the cost ledger." (API:5711-5713)
- (C) "Scheduling, external-fact monitoring, notification delivery channels, and associated data access." (DA:58) "Notification delivery channels and scheduling defaults." (MVEE:321)
- (R) The archived board wanted "any answer can be saved, and Argus keeps it true" (ATST:41-42), where "Checks run on data and code; the model is called only when an answer actually changed" (ATST:54-55). It also said "The channel is undecided." (ATST:57)

### 1.14 Search scope

- (A) Search is "unified retrieval across transactions, accounts, plans, goals, conversations, saved answers, and prior analyses" (MVEE:149).
- (A) Of market-product discovery, the MVEE says "It becomes useful when there is maintained, sourced inventory." (MVEE:153) "Do not fill the minimum ecosystem with fictional offers or imply shopping/execution capabilities that do not exist." (MVEE:153) Inference: listing inventory is market inventory of this kind.
- (A) "private activity must not leak through search results, totals, notifications, exports, or suggested actions." (MVEE:415)
- (B-doc) "Omnisearch covers the current Conversation, Backtest, Computed answer, Evidence, Decision, and Idea record types." (PRODUCT:306-307) "Deterministic omni-search over a conversation-shaped memory read model." (API:5839) Found. `/api/v1/search` is in `docs/api/openapi.yaml`, and results are typed `Literal["conversation"]` at src/argus/api/schemas.py:672.
- (C) Whether listing evidence or past estimates become searchable is unspecified.

### 1.15 Chat's role with records

- (A) "Conversational answers and financial writes are distinct." (MVEE:129) "New proposed financial records require confirmation." (MVEE:129)
- (A) "The assistant can help across the app; it is not necessary to visit chat for every edit." (MVEE:129)
- (A) "hypothetical scenarios never silently become actual financial activity." (MVEE:50)
- (A) "Saving a manual form is the user's confirmation; do not add redundant AI approval steps." (MVEE:187)
- (A) "A proposed entry must identify the relevant account or household commitment before confirmation." (MVEE:413)
- (A) Chat may "Ask about recorded accounts, activity, and plans when available and permitted." (MVEE:122)
- (A) Prompt and schema text is frozen: "Changing any of it requires a live measurement eval on the branch" (AGENTS:937-938).
- (B) Chat already sends published prices to research. The interpreter prompt covers a figure a "page publishes and the user did not state (a product's price" (src/argus/agent_runtime/interpreter/unsupported_admission.py:104). That text is frozen under AGENTS:935-938.
- (B) No chat-to-record write path exists. `docs/api/openapi.yaml` and `src/argus/api/routers/` have no financial-account, asset, transaction, household, or update route. The only account routes are profile and usage (`/api/v1/me`, `/api/v1/me/usage`).
- (C) "API routes, action schemas, chat-to-record integration, runtime state ownership, jobs, and event contracts for the new surfaces." (DA:56)

### 1.16 Home

- (A) Home answers "What do I have and owe?" (MVEE:84), "What changed?" (MVEE:85), and "What needs my attention?" (MVEE:86).
- (A) "Home leads with the upcoming financial period." (MVEE:47) "Preserve asset/debt summaries and deeper detail." (MVEE:47)
- (A) "Relevant next actions: a payment approaching, a budget nearing its limit, or an account needing an update." (MVEE:92)
- (A) "Do not turn Home into a generic market-news feed or a collection of charts." (MVEE:97)
- (A-pkg) Wave 1 navigation keeps "Home (the slot is reserved and appears in stage 2)" (W1S1:38), and hides net worth (W1R:34).
- (B) Not found. `web/app` has chat, account, auth, login, signup, r, privacy, terms, dev, and api routes only.
- (R) "That single tool is more valuable in Santo Domingo than a net-worth graph." (SRC:267) "Fake richness via home-value net worth." (EXEC:85)
- (C) The MVEE never uses the phrase *net worth*. Whether Home shows one total per currency that includes asset estimates is undecided.

### 1.17 Accounts

- (A) Minimum capacity includes "Edit transactions and categories; correct or undo mistakes." (MVEE:108) and "Reconcile a recorded balance against a statement or the user's observed balance." (MVEE:109)
- (A) See 1.1, 1.3, and 1.4 for types, fields, and ownership. "The primary addition is a persistent, user-correctable personal financial picture." (MVEE:302)
- (A-pkg) Accounts are hidden in Wave 1 (W1R:34).
- (A) "Do not expose unfinished surfaces just because they are approved in the vision." (DA:81)
- (B) Not found. No financial-accounts table, API route, or web surface exists. `web/app/account` holds only a password and security page (web/app/account/security/page.tsx).

### 1.18 Plan

- (A) Each plan shows "current position, intended outcome, planned contribution or limit, and progress." (MVEE:141)
- (A) Budgets, debts, and goals: "They must not independently allocate the same money." (MVEE:48)
- (A) "Saving a scenario does not authorize any real-money action." (MVEE:143)
- (R) The housing journey ends "optionally save a housing goal." (MAP:134)
- (C) No canon connects an asset's value to a plan, for example selling a vehicle to fund a goal.

### 1.19 Privacy, logging, and analytics

- (A) "Keep financial amounts, document contents, transcripts, and credentials out of analytics and ordinary logs." (MVEE:267)
- (A) "Storage and guest policies still need explicit implementation decisions." (MVEE:267)
- (A) "Authentication secrets must not enter chat, analytics, or ordinary logs." (MVEE:250)
- (A) "Household membership alone must not expose private accounts, documents, chats, or income." (MVEE:399)
- (A) "private information stays private unless its owner chooses to share it." (PRODUCT:27)
- (A-pkg) "No amounts, no question or answer text, no names, no emails, and no free text of any kind in any property." (W1S0:57)
- (B-doc) A test "fails if any field could hold free text or a money-formatted value" (DM:1229). Found: src/argus/observability/analytics_events.py and tests/test_analytics_events.py.
- (B) Loguru runs with `diagnose=False` (src/argus/log_sink.py:12), so logs omit local variable values.
- (B-doc) "Cost rows never store raw prompts, transcripts, credentials, balances, holdings" (DM:1447-1448). Spot-check: the creating migration `supabase/migrations/20260702000001_add_cost_ledger_entries.sql` has no balance, holding, or transcript column.
- (B-doc) Public receipts: "broker or account data, and user-private memory are never present." (DM:1578-1579) Found: `audit_public_excerpt_payload` at src/argus/domain/public_excerpts.py:261.
- (C) Retention and consent rules for third-party listing content (seller names, phone numbers, photos) do not exist (inference). Retention is open under MVEE:320.

### 1.20 Provider and integration authorization

- (A) "MVEE approval does not assign every feature, unlock stages, or authorize provider integrations" (DA:23)
- (A) On what locked means: "It does not mean implemented, validated market demand, a final schema, a model instruction change, or permission to deploy." (DA:33)
- (A) "No structural architecture shifts (service ownership changes or protocol swaps) are allowed without explicit approval." (ARCH:10) "No breaking changes (structural JSON shape changes) are allowed without explicit approval or critical implementation blockers." (API:10)
- (A) "Provider selection is not locked." (MVEE:179) "a provider's general marketing claim does not establish support." (MVEE:246)
- (A) "Before a real integration, resolve institution-specific feasibility, terms, authentication, credential/session handling, and user consent." (MVEE:250)
- (A) "Technical/provider choices that remain open are not implied approvals to build them." (PRODUCT:337-338)
- (A) "Resolve the relevant open technical contracts before implementing a new financial-record or household capability." (AGENTS:129-130)
- (A) "durable Supabase discovery/market-data caches require explicit schema, freshness, and invalidation design." (AGENTS:431)
- (A) "voice provider integration, and broker/export execution remain design-only until the roadmap explicitly starts those slices." (AGENTS:343-345)
- (A) "Production deploys remain manual and founder-directed." (AGENTS:342) API contract first: "Update `docs/API_CONTRACT.md` before implementation PRs." (AGENTS:920)
- (A) "escalate a concrete unresolved product choice or conflicting package instead of inventing it." (DA:61)
- (A-pkg) A PR needs "Priya's written eval verdict and a Codex re-review" (W1RD:59) when it touches "money math (calculations, rounding, currency, presenters that print amounts);" (W1RD:62-63), "a database migration;" (W1RD:65), or "user data or consent (analytics, attribution, profile fields, saved cards, sharing);" (W1RD:67-68). "Tests that need a real provider (OpenRouter, Perplexity, PostHog, Resend) are run by the internal team." (W1RD:80-81)
- (B) "Only searches built from provider-validated public symbols are eligible." (src/argus/domain/research/cache.py:3) Inference: vehicle or property lookups would never enter the shared research cache.
- (C) "Maintained market-product inventory, commercial relationships, and execution permissions." (MVEE:322)
- (R) "The founder owns Dominican data access and outlet deals." (ATST:222) "Argus does not build its own bank-login scraper." (ATST:226-227) "do not scrape what you cannot license" (SRC:273)

### 1.21 Loading, failure, empty, and insufficient-data states

- (A) The frontend must "never fake these states with timers" (DESIGN:227) and otherwise "show a neutral loading indicator only." (DESIGN:227)
- (A) "Avoid flashing or rapid updates. Use calm shimmers for loading states." (DESIGN:431)
- (A) "a figure only you know is asked as one plain question instead." (DESIGN:301)
- (A) Failures reuse one treatment: "Existing shared attention/failure treatment" (DESIGN:337). Guest "errors must remain calm, accessible, and localized in English and Spanish." (DESIGN:455-456)
- (A) "Avoid long required wizards." (DESIGN:419) "Manual entry must work without AI." (DESIGN:204)
- (A) "Make clear what is known and what remains unrecorded." (MVEE:185)
- (A) Recovery must "offer a manual path when parsing, voice, or bank access fails." (MVEE:268) "Failed imports must be recoverable without re-adding successful records." (MVEE:224)
- (A) "Never hide defaults, unsupported behavior, missing data, or asset-class constraints." (AGENTS:413)
- (A) "A refusal that names a capability the user did not ask about is a defect." (PRODUCT:251-252)
- (R) "offer to add the missing facts rather than calculate a reassuring fiction." (MAP:66)
- (C) DESIGN.md has no Accounts, Home, Updates, or proposed-estimate card spec. It defers because the MVEE "owns surface structure, household contexts, and product behavior." (DESIGN:4-5)

### 1.22 Language rules

- (A) "Preserve Spanish and English support, with the Dominican audience informing language and examples." (MVEE:65)
- (A) "English (`en`) and Spanish (`es-419`)." (DESIGN:401) "The AI response language must always mirror the UI language preference." (DESIGN:404) "Date, number, and currency formatting must adapt to the `locale` token." (DESIGN:405)
- (A) "Make the picture understandable without dense dashboards or financial jargon." (PRODUCT:49)
- (A) "Use plain language, small follow-up choices, and honest educational context." (AGENTS:414)
- (A) "Explain limitations in product language, not provider plumbing." (AGENTS:413) Users hear "not vendor-specific implementation details unless the product explicitly decides otherwise." (AGENTS:433)
- (A) "No raw enums or internal field names in user-facing text" (AGENTS:849)
- (A) The em dash ban applies "in user-facing copy, in any language." (RULES:37)
- (A-pkg) "es-419 first, with English alongside." (W1R:29) "No em dash (U+2014) in any new copy or model-facing text." (W1R:174)
- (R) "Do not adopt the source's “make the card the villain,” “apariencia,” or “investing is theater” framing as default product language." (MAP:78) The source frames vehicles as status spending: "Cars, nights out, luxury signaling financed with debt." (SRC:53) Inference: vehicle copy must stay neutral.
- (C) No en or es-419 wording exists for *estimated value*, *asking price*, *comparable*, or a not-an-appraisal disclaimer.

## 2. Open decisions a valuation feature depends on

Canonical list pointer: "The canonical list is [MVEE section 9]" (DL:25). "These open implementation choices do not reopen the approved ecosystem structure." (MVEE:326)

1. "Account onboarding, guest persistence, and conversion timing." (MVEE:316) Decides whether a guest can record an asset.
2. "Exact voice, OCR/document, and banking providers and supported formats/institutions." (MVEE:317) Sets the precedent that providers are not selected.
3. "Source-file/audio retention details and any future automatic acceptance policy." (MVEE:320) Decides whether a listing estimate could ever apply without review, and how long listing snapshots are kept.
4. "Notification delivery channels and scheduling defaults." (MVEE:321) Decides whether and how a changed estimate reaches the user.
5. "Maintained market-product inventory, commercial relationships, and execution permissions." (MVEE:322) Covers listing sources, licensing, and partnerships (inference).
6. "Engineering breakdown, release order, timelines, and platform sequencing." (MVEE:323)
7. "Household invitation delivery channel and detailed membership, removal, retention, and permission mechanics." (MVEE:324) Covers co-owned assets.
8. "Account onboarding, guest persistence, registration/conversion timing, and any changes to current access gates." (DA:53)
9. "Financial-record schema, balance/transaction reconciliation model, money arithmetic contracts, migrations, and historical-data conversion." (DA:54)
10. "Household membership lifecycle, permission enforcement/RLS, ownership, revocation, deletion, and retention implementation." (DA:55)
11. "API routes, action schemas, chat-to-record integration, runtime state ownership, jobs, and event contracts for the new surfaces." (DA:56)
12. "Voice/OCR providers, supported file formats/institutions, secure bank-access design, wallet/device capabilities, and automatic-acceptance policies." (DA:57)
13. "Scheduling, external-fact monitoring, notification delivery channels, and associated data access." (DA:58)
14. "Native app architecture, shared components, delivery order, rollout flags, acceptance gates, and work packages for the full ecosystem." (DA:59)
15. FX source, outside MVEE section 9: "Which source to use is Lucas's call" (W1R:30).

## 3. Direct mentions of listings, comparables, SuperCarros, SuperCasas, Corotos, market value, asking price

None in canon. No code mentions them either. Commands run from the worktree root (`grep` is ugrep on this machine):

```
grep -rniE 'supercarros|supercasas|corotos|classified|clasificad|asking price|precio de venta|comparables?\b|market value|valor de mercado|valor estimado|tasaci[oó]n|appraisal|listing|marketplace|scrap' docs .agent AGENTS.md CLAUDE.md
grep -rniE 'anuncios?\b|compraventa|concesionari|dealer|comparable sales|comps\b|precio de lista|list price|aval[uú]o|kelley|edmunds|zillow|zestimate' docs .agent/designs AGENTS.md
grep -rliE 'supercarros|supercasas|corotos' --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next .
```

- The brand grep over the whole worktree returns no file.
- *listing* hits are API listing semantics, such as the computed-answer list route (API:5675, API:5685), or unrelated QA text.
- *valor de mercado* appears only as stock market capitalization in QA transcripts (`docs/reports/evidence/377/browser/57-guest-allowance-ceiling-es.txt:181`, `docs/reports/evidence/377/browser/03-chip2-comparison-thorough-es.txt:10`).
- *dealer* appears only in captured Terms text: "Argus is not a broker, dealer, investment adviser" (docs/evidence/breakpoint-audit/chrome/terms-720-en-dark.txt:18), repeated in the 390 and 1024 captures.
- Adjacent (R) hits: "Net-worth vanity with Zillow-style home values." (SRC:329) and "do not scrape what you cannot license" (SRC:273).

## 4. Statements that conflict with, or constrain, a feature where listings propose a new estimate and the user confirms

Direct opposition exists only in (R) research:
- (R) Under "What not to copy" (SRC:324): "Net-worth vanity with Zillow-style home values." (SRC:329) "Illiquid housing + informal assets will produce fake richness." (SRC:329)
- (R) Under "Do not steal" (EXEC:82): "Fake richness via home-value net worth." (EXEC:85)
- (R) On net worth: "Only after revolving is visible." (EXEC:62) "Otherwise it is theater." (EXEC:62) The approved MVEE rejected gating by debt stage (MVEE:51), so this line has no force, but it records the author's view.
- (R) By analogy: "A bank offer, credit report, or mortgage advertisement must not automatically create an account, debt, or transaction." (MAP:118) Inference: a listing is an advertisement, so it may propose but never write.

Approved constraints. None forbids the feature, and the confirmation requirement matches it:
- (A) "Any future automatic acceptance of trusted feeds requires an explicit policy rather than silently removing user review." (MVEE:254) Auto-applying a listing estimate conflicts until that policy exists.
- (A) Drafts: "unconfirmed proposals do not affect balances, budgets, goal progress, or alerts about actual spending." (MVEE:261) By analogy: "OCR output is a proposal, not an authoritative financial fact." (MVEE:232)
- (A) "Changes to a balance must not silently manufacture income or spending." (MVEE:113) Inference: a confirmed rise cannot appear as income, and a confirmed fall cannot appear as spending.
- (A) "Treat DOP and USD separately. Do not silently combine currencies. Any future conversion must expose its rate, date, and source." (MVEE:66) With (A-pkg) "Wave 1 has no exchange-rate source, and the money code refuses to add two currencies" (W1R:30), USD comparables cannot price a DOP record today.
- (A) "It becomes useful when there is maintained, sourced inventory." (MVEE:153) "Future directions include maintained financial-product discovery, shopping assistance, bank partnerships, remittances" (MVEE:310). Inference: the feature must not drift into shopping help.
- (A) "Notifications should invite a return without exposing financial amounts in push/email previews." (MVEE:163) A push that states the new estimate is not allowed.
- (A) "Compute what the user gave you. Never prescribe what they should do." (PRODUCT:79) The estimate may inform, but Argus must not advise selling or buying. Research may quote prices: "quoting research-grounded prices, figures, or valuations to the reader is correct and encouraged" (AGENTS:434).
- (A) "research turns never write strategy/confirmation/execution state, and the shared research cache is public-market data only, never reusable for anything user-scoped." (AGENTS:434) A research turn cannot write the record, and a user's vehicle lookup cannot use the shared cache.
- (A) "durable Supabase discovery/market-data caches require explicit schema, freshness, and invalidation design." (AGENTS:431) Stored listing snapshots need that design first.
- (A) Vendor names stay out of the voice (AGENTS:433), while cards show "the page title and date it was read from" (DESIGN:301). Inference: citing a listing page is allowed, and describing the data vendor is not.
- (A) "Argus never presents one number as the future and never says what the user should do." (PRODUCT:258-259) This governs forecasts. Inference: a present-value range fits the same spirit, but no rule requires it.
- (A) "That loop fails if capture is too burdensome, stale facts appear current, hypothetical actions change actual balances" (MVEE:382). An old estimate shown as current breaks the loop.
- (A) "Do not expose unfinished surfaces just because they are approved in the vision." (DA:81) With (A-pkg) accounts and net worth hidden in Wave 1 (W1R:34), shipping this needs a package reconciliation.
- (A) Any interpreter prompt change needs a scorecard: "Changing any of it requires a live measurement eval on the branch" (AGENTS:937-938).

Unresolved tensions (C):
- Decision 8 says "Stated personal figures are ephemeral facts." (GF:1791), and the 2026-09-27 ledger report says it "remains the storage rule" (LEDGER:67). MVEE:177 makes confirmed records durable. A chat-proposed asset record needs this reconciled.
- MVEE:101 omits vehicles and property, and PRODUCT.md only avoids prohibiting "recording diverse personal assets" (PRODUCT:343). No approved asset type exists to hold the estimate.
- MVEE:258 lists user-entered, extracted, connected, and calculated provenance. A market estimate from third-party listings fits none of them cleanly.

## 5. Gaps no canon document answers

1. Are vehicles and residential property account types, holdings, or a new asset record? Does the founder accept property estimates in Home totals at all, given the (R) home-value caution?
2. Which fields does an asset carry (nickname, make, model, year, mileage, location, size, purchase price, purchase date, estimated value, estimate date, estimate source)?
3. How does fractional ownership work, and does a 50 percent share count at half in the personal view and in full in the household view? What if the co-owner is outside the household?
4. How does a financing debt (car loan, mortgage, informal lender) link to its asset, and is equity shown? How does the debt stay counted once across contexts and currencies?
5. Is an estimated asset value excluded from the remaining-money estimate (MVEE:47), and how is illiquidity labeled?
6. Does a confirmed revaluation appear under "What changed?" (MVEE:85) on Home and in account activity, and under what label?
7. Which provenance class holds a listing-derived estimate, and what source context is retained (URLs, titles, dates, prices, photos)?
8. How are comparables chosen and aggregated (match criteria, count, asking-price discount, outliers, point versus range)? Does the one-page-per-publisher drawer rule apply?
9. How are USD listings compared with a DOP record before an FX source exists, and which FX source and date rule apply afterwards?
10. May Argus read classified sites at all? Scraping, licensed feeds, partnerships, or user-pasted links only? Who approves terms and commercial relationships?
11. What retention and privacy rules apply to third-party listing content, including seller names and phone numbers?
12. When does an estimate count as stale, what is the refresh cadence, and who triggers a refresh: the user, a schedule, or a chat question?
13. Does a changed estimate generate an Update, at what threshold, and through which channel without stating amounts?
14. What happens with too few comparables or failed retrieval? Canon implies keeping the last confirmed value and its date (MVEE:252) but has no rule for valuation lookups.
15. How are past estimates stored, reverted, and attributed to a household member?
16. May chat propose an asset record or estimate update, and how does that reconcile with decision 8? Which confirmation surface applies outside chat?
17. May guests record assets or request estimates, and under which allowance, since research lookups are metered (API:5711-5713)?
18. Does Plan use asset values, for example selling a vehicle to fund a goal?
19. What en and es-419 wording names *estimated value*, *asking price*, and *comparable*, and is a not-an-appraisal disclaimer required? Does presenting a property value carry Dominican tasación rules?
20. Are estimates, comparables, or listing pages searchable?
21. Which analytics events, if any, describe valuation use without amounts?
22. Which Wave 1 package or later lane would host this, given accounts and net worth are hidden in Wave 1?
23. What are the loading, empty, failure, and insufficient-data designs for an Accounts asset screen and a proposed-estimate card?

## 6. Quote check

Every quote-and-reference pair in this file was checked by the script below. It resolves aliases from the table, reads the cited lines with two lines of slack, collapses whitespace, and requires an exact substring match and fewer than 25 words. Run it from the repository root with this file's path as the argument.

```
python3 - canon.md <<'EOF'
import re, sys, pathlib
root = pathlib.Path(".")
text = pathlib.Path(sys.argv[1]).read_text()
alias = dict(re.findall(r"^\| ([A-Z0-9]+) \| `([^`]+)` \|$", text, re.M))
pairs = re.findall(r'"([^"]+)" \(([^():\s]+):(\d+)(?:-(\d+))?\)', text)
bad = []
for q, ref, a, b in pairs:
    lines = (root / alias.get(ref, ref)).read_text().splitlines()
    lo, hi = max(int(a) - 3, 0), min(int(b or a) + 2, len(lines))
    window = " ".join(" ".join(lines[lo:hi]).split())
    if " ".join(q.split()) not in window or len(q.split()) >= 25:
        bad.append((ref, a, q[:70]))
print(len(pairs), "quotes checked,", len(bad), "failed")
for item in bad: print(item)
EOF
```
