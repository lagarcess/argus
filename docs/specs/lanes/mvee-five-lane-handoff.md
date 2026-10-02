# Five-lane MVEE delivery handoff

**Status:** Draft scoping. This file assigns no worker, merge, hosted change, or deployment.
**Integration:** `codex/private-alpha-next` at `d9a7acfcfc9970edb07fee2cbbd1c21e19536772`, 2 October 2026. That commit is `d9a7acfc`, which includes landed PR #776. Remote integration matched this SHA at the time of writing.
**Design checkout to preserve:** `codex/cuadrao-design-scan-recents` at `8f521518`. That branch owns Cuadrao UI chrome and has already diverged from integration. Delivery lanes do not edit its files and do not merge it.
**Product owner:** [MVEE](../argus-minimum-viable-ecosystem-experience.md). This handoff links to that owner. It does not copy a second scope list.
**Execution map:** [execution board](../argus-execution-board.md).

The five lanes below are the founder's delivery order. They may be built in parallel. They land on integration one at a time through one integration captain.

## What this handoff is allowed to decide

The MVEE, the [decision log](../argus-decision-log.md), the [Household permission policy](household-permission-policy.md), the API contract, and the data model already lock behavior cited below. A product-lead hypothesis is not a decision. Each one is marked **already specified**, **consistent but unspecified**, or **conflicting**.

Unknowns stay unknown. [Issue #778](https://github.com/lagarcess/argus/issues/778) plans to move retained document source bytes out of Postgres bytea and into a private Supabase Storage bucket before documents are enabled. Search uses the document API and never storage internals, so that move does not affect Search.

## Product-lead hypotheses

### 1. Invitation delivery

An invite produces a share link, an invite code, and a QR code. Email is out of this pass.

**Founder settled** on 2 October 2026. The share sheet and user-sent WhatsApp or Messages stay as already specified in the [MVEE invitation delivery lock](../argus-minimum-viable-ecosystem-experience.md#invitation-delivery-founder-locked-september-27-2026) and the [30 September design lock](../cuadrao-accounts-design-lock.md). Argus does not send a WhatsApp Business API message. The founder adds an invite code and a QR code beside the link. File cites are in lane 2. The share link is present on integration and on the design branch. The household invite code is not in either tree. The household QR is not in either tree.

**Email is later work.** The founder states that Resend and the cuadrao domain exist and are not connected, and that connecting them comes later. This pass does not send invitation email. The MVEE still selects Resend for a later channel. That lock is deferred, not reversed. Do not build a Household mail sender in this lane.

**Consistent but unspecified** for a link that opens the installed app. No `CFBundleURLSchemes` or associated domain is registered under `ios/`. The design canvas shares `https://cuadrao.invalid/invite/...`, and that host does not resolve. The URL people share stays open. See decision 1.

### 2. Household visibility

Each account stays private until its owner shares it. Leave or removal revokes access immediately. Search and Updates follow the same rule.

**Already specified.** [MVEE section 12](../argus-minimum-viable-ecosystem-experience.md#invite-and-choose-what-to-share) says membership alone must not expose private accounts, documents, chats, or income. The [permission policy](household-permission-policy.md) separates create, invite, and share. Accepting an invitation grants membership only. `src/argus/domain/household/postgres.py` `_end_membership` revokes grants whose owner is the departing user and grants whose recipient is the departing user, in the same transaction as `left_at`. The API contract states the same rule: departure withdraws outbound shares and recipient access immediately, and closure ends all grants without deleting financial records. [MVEE Search and Updates](../argus-minimum-viable-ecosystem-experience.md#shared-financial-picture) already require those screens to respect the same visibility. Household financial search is implemented. The Updates inbox is not, so the rule is specified and not yet executed there.

### 3. Leaving

Shared accounts and their history stay with the household. The leaver keeps their private accounts.

**Conflicting** for accounts the leaver owns. The locked rule is that the owner keeps the account and its history. Sharing changes visibility, not owner and not `space_id`. See the MVEE reassigning section, [DATA_MODEL.md](../../DATA_MODEL.md#1215-households-membership-invitations-grants), and the API contract departure paragraph: "Departure never deletes financial activity, exposes private funding, or transfers ownership. The owner retains their original records." On leave or removal, remaining members lose access to that owner's shared accounts because the grants are revoked. The leaver does keep every account they own, shared or not. Other people's accounts disappear from the leaver's household view because the leaver's recipient grants are revoked.

**Already specified, and different from accounts,** for plans the owner had shared. Before departure, the native flow explains that those plans become archived and read-only for remaining authorized members. Previously shared history and linked transactions stay visible through that projection. Future forecast movement stops. Remaining members still need live membership and the existing plan consent. This is the 1 October rule in the API contract and in landed PR #773. It does not move the funding account to the household.

The case of a shared account the leaver owns is resolved. Ownership decides. It is not an open product decision. What remains open is joint-plan export and retention beyond that archived package, which the decision log and the execution board already name.

### 4. Moving an account between spaces

History and linked plans move with the account. Home comparisons follow the account.

**Already specified** for history, and not implemented. The [MVEE reassigning section](../argus-minimum-viable-ecosystem-experience.md#reassigning-accounts-between-spaces) keeps balance, opening position, activity, corrections, notes, and recoverable removed entries with the account. A move creates no transaction. `financial_accounts.space_id` exists, defaults to `personal`, and no route reads or writes it. `src/argus/domain/recording/` has no `space_id` field on `AccountFacts`.

**Conflicting** for linked plans. The same MVEE section says the budgets and goals themselves remain where they are. The move explains which space budgets stop and start including the account's matching activity. Links to transfers, payments, refunds, loans, household sharing, forecasts, debt plans, documents, and unfinished entries are identified and not broken. The disposable sketch moves standalone accounts and explains why a linked account is blocked. Group moves and permission-aware link migration still need the production contract the MVEE names.

**Consistent but unspecified** for Home comparisons. Nothing stores a comparison. The design canvas derives chart points from the accounts in the selected space. A production series that reads `space_id` would follow the account after a move. No such series exists. See lane 1.

### 5. Home empty months and comparisons

Empty months show as no data, not zero. A comparison appears only when both periods have real data.

**Consistent but unspecified** as a backend rule, and consistent with two existing rules that are not a chart contract. The MVEE says a missing balance is not zero, an unknown value does not contribute zero, and a month without expectations is not a claim that future expenses are zero. The design canvas shows an empty period rather than a zero line: `CuadraoHomeBalanceChart` uses `home-chart-empty` when the period has no points, and `CuadraoSpendingChart` uses the empty-period copy when coverage includes the month and no expenses were recorded. `GET /api/v1/financial-home` does not do this. `home_response` in `src/argus/domain/recording/loop_reads.py` returns zero minor-unit spending strings for a currency that has accounts and no matching expenses. Those zeros are the current month totals, not a chart series, and they must not be copied into the chart.

**Conflicting** for the comparison clause, against the landed design canvas. Balance comparison in `CuadraoBalanceBreakdown` appears only when both an opening point and a closing point exist. Spending comparison does not wait for spending in both periods. `CanvasSpendingStory.comparison` returns the previous interval when that interval is inside coverage, and `previousTotal` is then the sum of recorded expenses, which is zero when there are none. `CuadraoSpendingChart` states that recorded spending matches the previous period when the difference is zero. The MVEE does not choose between these. The founder has to choose before the Home series is coded. See the open decisions below.

### 6. Amounts in Updates

Amounts may appear in the in-app inbox. They never appear in push notifications or email.

**Already specified.** The [MVEE Updates section](../argus-minimum-viable-ecosystem-experience.md#updates-tell-me-when-something-deserves-attention) says notifications invite a return without exposing financial amounts in push or email previews, and that details belong inside the authenticated experience. Invitation email has the same amount ban. The execution board's unresolved-input row recommends a persistent inbox and opt-in private push previews, with no financial details outside the authenticated app, and leaves the channel choice to the founder. No inbox, push, or update email is implemented. `sheet.updates.detail` in both `Localizable.strings` files says monitoring and notification delivery are not connected.

## Contracts between lanes

Household owns permission rules. Other lanes call that owner. They do not store a second grant, a second membership, or a client-side allow list.

Spaces owns what a move does to history, plans, Home, and Search. The rule to implement is the MVEE rule, not hypothesis 4's plan clause. The account id stays the same. Current assignment changes by `space_id`. Historical balances, corrections, and settlements are not rewritten and are not copied onto the destination. The move is an auditable event, idempotent, and recoverable. Budget and goal rows stay in the space where they were created. Their inclusion of the account's activity changes with `space_id`. Household grants are untouched by a space move. Home and Search read the same `space_id` and recompute from canonical history. They do not keep a private copy of which space an account is in, and they do not keep a copied series.

Updates consumes events from the lane that owns the fact. It stores read state and a source link. It does not copy the amount, the draft, or the invitation token into the inbox row. Display text is read from the current source at open time, so a revoked grant, an approved draft, or a paid bill cannot leave a stale private fact in the inbox.

### Source link

This shape is a technical contract for these lanes. It is not a founder product decision. It reuses ids that already exist.

```json
{"kind":"account|activity|expectation|budget|goal|debt|bill|document|conversation|invitation","id":"<uuid>","household_id":"<uuid or null>"}
```

| `kind` | `id` is | Open with |
| --- | --- | --- |
| `account` | `financial_accounts.id` | Existing account detail |
| `activity` | Logical activity id, never a leg or an old revision | Existing activity detail |
| `expectation` | Personal expectation id | Existing Plan expectation editor |
| `budget`, `goal`, `debt` | That plan's id | The existing Search open path in `FinancialSearchModel.open` |
| `bill` | Shared plan id whose `PlanRef.kind` is `bill`, or a personal expectation whose kind is `bill` | The owner already used by Household plan detail or the personal expectation editor. `household_id` is set only for the shared plan |
| `document` | `connection_id` from `/api/v1/financial-documents` | `GET /api/v1/financial-documents/{connection_id}` and, for bytes, `GET /api/v1/financial-documents/{connection_id}/source` |
| `conversation` | `conversations.id`, the same id `GET /api/v1/search` returns as `SearchItem.conversation_id` | The existing conversation reader. There is no native conversation screen in the connected shell today. Chat on that shell is still `ChatSampleView` |
| `invitation` | `household_invitations.id` | See the invitation gap in lane 3. The token is not part of the link |

`household_id` is null for a personal record. It is set only for a household-authorized projection. Opening the link rechecks current Household permission. Failure uses the same unavailable destination Search already shows. A document link never carries `source_bytes`, a storage object key, or a bucket path.

Personal financial search and conversation search stay separate HTTP APIs. `GET /api/v1/search` returns conversation dossiers. `GET /api/v1/financial-search` returns financial records. The client can show them in one list. The server does not merge those stores.

## What must be locked before coding

| Before this work starts | Lock |
| --- | --- |
| Any lane writes a migration or edits OpenAPI, API types, or `Localizable.strings` | The captain assigns the migration version and is the only writer of those shared files for that landing. Latest migration on this tip is `supabase/migrations/20261003130000_financial_document_drafts.sql`. New files sort after it. Existing migrations are not edited. |
| Home chart series | Founder choice on hypothesis 5's comparison clause. Do not encode either rule until that choice is recorded in the MVEE. |
| Household email | Later work. The founder deferred it on 2 October 2026. Resend and the cuadrao domain are not connected to invitations. Do not build invitation email in this pass. |
| A link that opens the app | Founder choice of app identity and URL. MVEE section 1.6 still lists app identity and distribution as undecided. Decision 1. |
| How an invitee gets the TestFlight build | Open. A Cuadrao invite does not add anyone to TestFlight by itself. Decision 2. Product-lead proposal (b) in lane 2 is waiting and is not adopted. |
| First TestFlight distribution | Schedule external beta review of the first build before that distribution. This is a release constraint, not a product choice. |
| Updates trigger for "invitation received" | The schema has no recipient until `accepted_by` is set at acceptance. `household_invitations` stores `token_hash`, expiry, and the creator. A server inbox cannot address the invitee before they present the token. Updates may record a row for the signed-in user who previews or accepts. It must not store the token. A pre-accept inbox item for a named invitee is unsupported and is not to be invented. |
| Updates bill timing | No lead time is specified. "Approaching" has no number of days in the MVEE or the Plan contract. The inbox store can be built. The bill trigger waits for that number. |
| Spaces, linked accounts | Do not move them. The MVEE sketch blocks a linked account and explains why. Standalone moves may proceed under the history and plan rules above. |
| Search documents | Read the document API only. Do not import `store_postgres.py` or select `source_bytes` from Search. |

Household permission rules, account departure, and the plan-stays-in-its-space rule are already locked. Those lanes do not wait for a new product decision before coding the specified part.

## Landing order

One integration captain lands one lane at a time onto `codex/private-alpha-next`. Parallel branches do not merge each other. The captain reconciles the current integration into the worker one way, then merges the worker through its PR.

Account moves should not land second. The earlier second slot existed so Home and Search would read one `space_id` writer. That reason still holds for a space catalog. It does not hold for moving an existing account. A move that rewrites or copies balance history would reach integration before the Home reader exists to catch it. The founder warns that a move is hard reconciliation of balance history, settlements, and backfilling. That slice is the highest-risk part of Spaces.

1. **Household delivery.** Permission and membership are already on integration. This pass adds the share link, invite code, and QR the founder described, and not email. Land it before Updates writes invitation rows.
2. **Spaces catalog only.** Space rows, unique names, archive, and a new account choosing a space. No move of an existing account. This is the one `space_id` writer later readers use.
3. **Search.** Document and conversation opens should exist before Updates navigates to them. Search does not move accounts. The source-link kinds above are the destination list.
4. **Home series.** Derived from canonical history and filtered by the account's current space, after the catalog writer exists.
5. **Account moves.** After that Home reader exists, with Codex review and the dedicated eval in lane 5. Idempotent, recoverable, and not a copy of history.
6. **Updates.** Land last. It only stores read state and links. Its producers are Household invitations, Plan bills, and document draft status.

If the captain will not split Spaces, land the whole Spaces lane after the Home series, in slot 4, and do not land it second.

A lane that is blocked on a founder decision does not hold the others. Household does not wait on email. Spaces catalog can land while account moves wait on the Home reader. Linked account moves stay blocked. Updates can land the inbox and the draft-ready row while bill timing and push channels wait.

## Codex review

Codex review is not a merge gate. Request it only for work that changes durable money, authorization, or schema.

| Lane | Review |
| --- | --- |
| Household | Yes if delivery changes grant revocation, token storage, or RLS. No for a share sheet that only displays the token the create-invitation response already returns. |
| Spaces | Yes. The space table is migration and authorization work. Account moves also require a dedicated eval before landing. The eval is specified in lane 5. |
| Search | Yes if a query can return another owner's document or conversation. No for a read-only adapter that calls the existing document and conversation owners and adds no table. |
| Home | Yes if the series is a new stored table. No if it is derived inside the existing financial-home read transaction from canonical activity and balance observations. |
| Updates | Yes for the inbox table, its RLS, and any trigger that copies a private amount or a token. |

## Shared file ownership

| Files | Writer | Rule |
| --- | --- | --- |
| `ios/ArgusFoundation/Cuadrao/**`, `ios/DesignPreviewTests/**`, `ios/ArgusFoundationUITests/Cuadrao*Design*`, `ios/ArgusFoundationUITests/CuadraoHomeChartUITests.swift`, navigation icons, `.agent/designs/cuadrao/` | Design lane on `codex/cuadrao-design-scan-recents` | Do not edit. `CuadraoUpdatesCanvas.swift` exists only on that branch. |
| `ios/ArgusFoundation/Connected/ConnectedCuadraoShell.swift`, `FoundationShell.swift`, `CuadraoNavigationBar.swift`, `AppDestination` | One native navigation writer, assigned by the captain for the landing that changes tabs or the bell | Other lanes add a destination handler beside these files and hand the wiring to that writer. |
| `docs/API_CONTRACT.md`, `docs/api/openapi.yaml`, `ios/Packages/ArgusSession/Sources/ArgusSession/*.swift` public types | The lane that owns the contract, one landing at a time | Swift types match the contract. No second client model of money or permissions. |
| `ios/ArgusFoundation/Resources/en.lproj/Localizable.strings` and `es-419.lproj/Localizable.strings` | Captain, at the landing | The design branch has already diverged both files. Parallel lanes list new keys in the PR. They do not edit the strings files. |
| `supabase/migrations/*.sql` | The domain owner, one new file, version assigned by the captain | Do not edit a migration that is already on integration. |
| `docs/specs/argus-execution-board.md` | Captain | Lane PRs do not rewrite historical landing records. |

## Open founder decisions

Only these still require the founder. Everything else in this file is either already locked or is a technical contract the lanes can implement.

1. **URL that opens the app.** App identity is still open in MVEE section 1.6. The connected scheme is unregistered. The design host does not resolve. Choose the URL people share before anyone calls the link real delivery.
2. **How an invitee gets the TestFlight build.** A Cuadrao invite does not add anyone to TestFlight by itself. The distribution record in lane 2 says what the beta is. It does not choose the install path. Product-lead proposal (b) is waiting and is not adopted.
3. **Spending comparison when the previous covered period has no expenses.** The canvas compares and can show a zero difference. Hypothesis 5 hides the comparison unless both periods have real data. Record the choice in the MVEE before the Home series is coded. Unknown balances stay unknown either way.
4. **How many days before a due bill creates an inbox row.** Unspecified. Needed only for the bill trigger.
5. **Push and email channels for Updates.** The amount ban is locked. Which channels exist, and whether push is opt-in, is the open row already on the execution board. The in-app inbox does not wait on it. Household invitation email is not this item. It is later work.
6. **Joint-plan export and retention beyond the archived read-only departure package.** Already listed as open. Account custody on leave is not part of this question.

Invitation email is not in this list. The founder deferred it. Product-lead proposals (a), (b), and (c) in lane 2 are waiting. They are not decisions.

A named invitee on an invitation, before that person opens the link, is not a founder decision to resolve by adding a column in this pass. The current invitation has no recipient. Do not add one unless the founder explicitly expands invitation delivery.

## Lane 1. Home real data

**MVEE:** [Home](../argus-minimum-viable-ecosystem-experience.md#home-understand-where-i-stand), populated summary, and [charts](../argus-minimum-viable-ecosystem-experience.md#13-complete-scope-checklist) row D05. Serves the questions "what do I have and owe," "what changed," and "what needs attention."

### Journey and completion

A signed-in person opens Home in Personal, then in a private space once Spaces has landed. The balance chart and the activity insights use that space's recorded accounts and activity for one currency at a time. A month with no recorded movement is an empty period, not a zero balance and not zero spending. Unknown balances stay out of the known total. A comparison follows the founder choice in decision 3 above. The person can open the account or activity behind a point. Relaunch shows the same series. A second currency is a separate series. Household Home includes only accounts that Household grants allow, and it drops them when the grant is revoked.

Completion is a real Postgres read, an app relaunch, a second user who cannot see the first user's series, and the same screen in English and Spanish. The design canvas sample series is not completion.

### What exists

| Piece | Where | PR |
| --- | --- | --- |
| Connected Home position, one reporting month, five recent activities, and the Plan forecast | `GET /api/v1/financial-home` and `GET /api/v1/financial-plan`. Response built by `home_response` in `src/argus/domain/recording/loop_reads.py`. Month window is `period` in `src/argus/domain/recording/money_home.py` | #745, #747, #749 |
| Connected Cuadrao Home | `ios/ArgusFoundation/Connected/ConnectedCuadraoHome.swift` renders `FinancialHome` text, accounts, coming up, and recent activity. It does not construct `CuadraoHomeBalanceChart` or `CuadraoHomeInsights` | #760 |
| Chart and insight chrome, sample observations | `CuadraoHomeOverview.swift`, `CuadraoHomeInsights.swift`, `CuadraoHomeBalanceChart.swift`, `CuadraoBalanceHistory.swift`, `CuadraoSpendingHistory.swift`, `CuadraoSpendingStory.swift` | #775 activity insights, #777 balance-change states |
| Sample history | `CanvasBalanceHistory.examples` invents earlier balances. `CanvasSpendingHistory.examples` invents expenses. `CuadraoAccountsPreview` holds that data in memory | Design canvas, not the API |

Reuse `home_response`, `spending`, and the Plan forecast. Do not add a second balance. Derive a series from canonical account observations and current logical activity, or add one stored series owned by the recording read. The chart views should take that series. They should stop calling `CanvasBalanceHistory.examples` on the connected path.

### Gaps

- No multi-month balance or spending series on the API. `financial-home` is one month, and its spending totals are zero when nothing was recorded.
- Connected Home never reads the chart chrome.
- Empty-month and comparison behavior is canvas-only, and the comparison clause conflicts with hypothesis 5 until the founder chooses.
- Household snapshot `GET /api/v1/households/{id}/snapshot` returns positions and activities, not a chart series.
- Design branch `8f521518` also edits the chart files. A backend series can land without those edits. Binding the connected view waits until the captain can touch `ConnectedCuadraoHome.swift` without colliding with that branch.

### Allowed files

`src/argus/domain/recording/loop_reads.py`, `money_home.py`, a new series module next to them, `src/argus/api/routers/financial_loop.py`, the financial-home section of `docs/API_CONTRACT.md` and `docs/api/openapi.yaml` when this lane is the one landing, and tests under `tests/financial_accounts/` or the recording tests that already cover `home_response`.

No-touch: `ios/ArgusFoundation/Cuadrao/**`, design preview tests, and `ConnectedCuadraoHome.swift` while the design branch still differs on it. Household grant tables. Plan definition tables.

### Acceptance

Real Postgres. Relaunch the app and read the same points. An account with an unknown balance does not become zero. A month with accounts and no activity is the empty state the founder chose, not the current zero string. Household series hides an account the moment its grant is revoked. English and Spanish strings for the empty state and the comparison. Flag off: `ARGUS_FINANCIAL_ACCOUNTS_ENABLED` unset still returns `404` on the financial routes.

## Lane 2. Household invitations

**MVEE:** [section 12](../argus-minimum-viable-ecosystem-experience.md#12-household-collaboration-approved-minimum-capacity), invitation delivery, and the [permission policy](household-permission-policy.md). Board rows for #763, #766, and #773.

### Journey and completion

A registered admin creates a household and shares one invitation as a link, an invite code, and a QR code. The recipient, on their own sign-in, previews the link or enters the code, accepts, and sees no accounts until an owner shares one. The owner shares a single account as view, then optionally grants edit. The recipient records only what the edit grant allows. The admin revokes the invitation before use, and that token dies. A member leaves, or the admin removes them. Access ends in that request: grants in both directions are revoked, the leaver's own accounts remain theirs, and a plan they had shared becomes the archived read-only projection already implemented. An expired link and a revoked link fail with the existing errors. The same acceptance retried with the same idempotency key does not create a second membership.

Completion includes the share link, the invite code, and the QR, English and Spanish, relaunch, and a third registered user who receives 404s for the household. Invitation email is not part of completion. It is later work.

### Distribution record

The founder settled this for the TestFlight beta. The landing page runs a waitlist, and the founder onboards the first users himself. Those users can invite anyone. Each invitee also becomes a TestFlight tester through the invite. Invites carry a link plus a code so the network effect can be tracked.

A Cuadrao invite does not add anyone to TestFlight by itself. How the invitee gets the build is decision 2. This handoff does not choose it. Product-lead proposal (b) below is one proposal and is not adopted.

Schedule TestFlight external beta review of the first build before first distribution. That review is a release constraint. It is not a product choice.

### Who invited whom

Invitations do not record a referral graph. `household_invitations` stores `created_by` for the user who created the invite and `accepted_by` for the user who accepted it, in `supabase/migrations/20261001090000_household_membership.sql`. Both columns are `on delete set null`. The migration comment says acceptance may keep `accepted_at` after `accepted_by` clears. There is no row that keeps the inviter and the invitee after either auth user is deleted, and there is no chain from an invitee to the invites they later send except a join of those two columns while both ids still exist. `profiles` invite cohort, the pattern on `signed_in`, `session_started`, `landing_viewed`, and `first_answer_shown` in `src/argus/observability/analytics_events.py`, is a campaign code. It is not a person. That is a gap for the network-effect report.

### What exists

Landed on this tip:

| PR | What it shipped |
| --- | --- |
| #763 `fbcc399b` | Default-off membership API. Flag `ARGUS_HOUSEHOLDS_ENABLED`. Tables in `20261001090000_household_membership.sql`, extended by `20261001120000` and `20261001130000`. Routes in `src/argus/api/routers/households.py` |
| #766 `079ec8d8` | Native consent and canonical household activity. `src/argus/api/routers/household_financial.py`. Native `ios/ArgusFoundation/Household/` |
| #773 `f28b5642` | Shared budgets, bills, goals, debt, private contributions, and departure retention. `src/argus/api/routers/household_planning.py`. Migrations `20261002000000` through `20261002050000`. The execution board section for #773 still says the lane was unmerged. That sentence is older than the squash on this tip |

Routes already implemented: `POST /api/v1/households`, `POST /api/v1/households/{id}/invitations`, revoke, `POST /api/v1/household-invitations/preview`, `POST /api/v1/household-invitations/accept`, leave, remove member, transfer admin, close, account-grant create, patch, delete, and replace. Token plaintext is returned once. Replay returns `token: null`. TTL is seven days, `INVITE_TTL` in `src/argus/domain/household/repository.py`.

Checked on integration at this tip and on `codex/cuadrao-design-scan-recents` at `8f521518`.

**Share link, present on both.** Integration: `ShareLink` in `ios/ArgusFoundation/Household/HouseholdManagement.swift` shares `argus-household://invite#` plus the one-time token, and the same view shows that URL as selectable text at `household.invite.link`. `ios/ArgusFoundationUITests/HouseholdUITests.swift` expects the `argus-household://invite#` prefix. Design branch: `CuadraoInvitationShareSheet` in `ios/ArgusFoundation/Cuadrao/CuadraoHouseholdInvitation.swift` shares `https://cuadrao.invalid/invite/...` through `UIActivityViewController`, presented from `ios/ArgusFoundation/Cuadrao/CuadraoHouseholdSheet.swift`. That host does not resolve, and the canvas comment says the sheet never exposes a real invitation. Nothing on either tree handles the URL on open.

**Invite code, not there.** No household screen on integration or on the design branch shows an invite code. The design button labeled "View code card" is not a household code. It opens the plan-group sample below.

**QR, not there for a household invite.** Integration has no `CIFilter.qrCodeGenerator` under `ios/`. The design branch has one QR, and it is a plan-group sample, not a household invitation. `ios/ArgusFoundation/Cuadrao/Planning/CuadraoGroupInvitation.swift` opens `CuadraoGroupCodeCard` from `group-invite-code`. `ios/ArgusFoundation/Cuadrao/Planning/CuadraoGroupCodeCard.swift` draws a QR whose payload is `Cuadrao design preview |` plus the in-memory group id. The card says the sample code does not join a real group. `ios/ArgusFoundationUITests/CuadraoGroupDesignUITests.swift` only exists on that branch and screenshots `group-code-qr`. Those files are not on integration. They do not create, store, or accept an invitation.

Reuse the Household service, the command receipt, and the native journal. Do not add a second invitation table or a second token store. The code and the QR the founder settled are a presentation of the same invitation the create route already returns.

### Gaps

- The shared URL does not open the app.
- The household invite code and the household QR are not implemented. The plan-group sample QR is not a substitute.
- No durable who-invited-whom record, as written above. A report cannot keep the inviter after `created_by` or `accepted_by` is cleared.
- Invitation email is later work. Do not add a Resend send, a do-blitz short link, or an invitation email template in this pass. Supabase still owns other email templates. A later Household email must not become another template living only in a dashboard, and its body contains no amounts.
- Invitations name no recipient before accept. See the lock table.
- Design "Personas" and the connected management screens are different files. This lane keeps the connected `Household/` module. It does not restyle it inside `Cuadrao/`.

### Product Lead proposals waiting on the founder

These are proposals. They are not decisions, and this handoff does not adopt them.

**(a) Per-user invite quota.** For example 3 to start, with more granted manually. No quota column or counter exists on `household_invitations` or on the member row.

**(b) The in-app invite code is the real gate.** A TestFlight public link only installs the app. Anyone without a code lands on the cuadrao.ai waitlist. This is the proposal for decision 2. A Cuadrao invite still does not enroll TestFlight by itself.

**(c) Three network metrics from day one, on the who-invited-whom record.** That record is the gap above. None of the three is an existing analytics event. The closed PostHog registry in `src/argus/observability/analytics_events.py` is `first_answer_shown`, `signed_in`, `card_saved`, `goal_created`, `checklist_step_completed`, `reminders_opted_in`, `reminders_opted_out`, `session_started`, `installed_app_opened`, `landing_viewed`, and `receipt_shared`. The optional `cohort` string on `signed_in`, `session_started`, `landing_viewed`, and `first_answer_shown` is a campaign code, not an inviter.

| Metric | Where it would come from |
| --- | --- |
| Invites sent per user | Gap. No analytics event and no PostHog capture. A count of `household_invitations` by `created_by` exists only while that user id remains. |
| How many of those invites get accepted | Gap for PostHog. `accepted_at` on the same row is the SQL mark that an accept happened. `accepted_by` does not survive deletion of the acceptor, so the count of accepts is not a count of people once that column clears. |
| How many invitees invite someone themselves | Gap. No event. The only join is `accepted_by` of one row to `created_by` of a later row, and both columns clear on user delete. Without the durable record, PostHog cannot answer this. |

### Allowed files

`src/argus/domain/household/`, `src/argus/api/routers/households.py`, `src/argus/api/households.py`, `ios/ArgusFoundation/Household/`, `ios/Packages/ArgusSession/Sources/ArgusSession/Household.swift`, `tests/household/`, and the Household section of the API contract and OpenAPI when this lane is landing.

No-touch: grant semantics in `_end_membership` unless a Codex-reviewed bugfix, `CuadraoHousehold*.swift`, `CuadraoGroupInvitation.swift`, `CuadraoGroupCodeCard.swift`, financial account ownership, Plan math, Resend, and invitation email templates.

### Acceptance

Two real users and a third who is denied, against Postgres. Create, share the link, show the code and the QR for that same invitation, preview, accept by link and by code, share one account, edit grant, leave, remove, revoke, expire. Relaunch both clients. Retry a lost accept response and get one membership. Disable the flag and confirm `404 households_unavailable` before auth. English and Spanish on the share sheet, the code, the QR, the preview, and the departure explanation. No invitation email is sent. A referral report, if proposal (c) is later accepted, reads the durable who-invited-whom record and not PostHog cohort.

## Lane 3. Updates

**MVEE:** [Updates](../argus-minimum-viable-ecosystem-experience.md#updates-tell-me-when-something-deserves-attention). This lane's triggers are the three named for this pass: bill approaching, draft ready, invitation received. The broader MVEE list, including budget thresholds, goal milestones, and scheduled summaries, stays on the board. This lane does not close that list.

### Journey and completion

The person taps the bell and sees a persistent inbox. A personal or shared bill inside the chosen lead time, a document whose status becomes `review_ready`, and an invitation the signed-in user has previewed or accepted each produce one row. The row says what happened and opens the source through the source link. Opening marks it read. Read state survives relaunch. Another user does not see the row. After a grant is revoked, a household row disappears or opens as unavailable. Amounts, when the source still has them, appear only in this authenticated inbox.

Completion does not include push or email. Those wait on founder decision 5, and they must omit amounts when they are built.

### What exists

The bell is wired and the inbox is not.

- Connected shell: `ConnectedCuadraoHome` calls `showUpdates`, and `ConnectedCuadraoShell` presents `FoundationSheet.updates`.
- `FoundationSheets.swift` renders the sample page. Copy key `sheet.updates.detail` says delivery is not connected. Same string in `en` and `es-419`.
- Design branch only: `CuadraoUpdatesCanvas.swift` at `8f521518` shows sample rows for an account that needs a balance and for plan progress, with local read state. It is not on integration and it is not durable.
- Bill facts: personal expectations of kind `bill`, and shared plans of kind `bill`, already have dates. No scheduler writes an inbox row.
- Draft facts: document `status` includes `review_ready`. The route requires the ingestion gate and `ARGUS_DOCUMENT_EXTRACTION_ENABLED`, which defaults off. PR #776.
- Invitation facts: create and preview exist. No recipient user before accept. No inbox table. `conversation_read_states` is chat read state. It is not this inbox.

### Gaps

- No inbox table, no read state, no trigger writer.
- "Invitation received" cannot fan out to an unknown invitee. The row exists for the user who previewed or accepted.
- Bill lead time is unspecified.
- Native chat and document screens that the source link opens are incomplete. Updates can store the link before those screens land. It cannot claim the open works until Search or the document lane has a real destination.
- Push and email are unspecified as channels and specified as amount-free if they exist.

### Allowed files

A new Updates package under `src/argus/domain/` and one router, a new migration assigned by the captain, `FoundationSheets.swift` only through the navigation writer, and tests that create a bill, a document draft, and an invitation preview and then read the inbox as that user and as someone else.

The document service keeps owning draft status. The Plan service keeps owning due dates. The Household service keeps owning invitations. Updates reads those rows. It does not add a status column to them.

No-touch: `CuadraoUpdatesCanvas.swift`, `source_bytes`, invitation token storage, push providers.

### Acceptance

Postgres. Create each of the three facts, relaunch, and see the same unread rows. Mark one read, relaunch, and see it read. A second user gets an empty inbox. Revoke a household grant and the related row is gone or unavailable. A document row's open path uses `connection_id` and still works if bytes later move to Storage. English and Spanish for the inbox chrome. With the document flag off, no draft row appears and the document routes still 404. Amounts are absent from any push or email payload added in this lane. If those channels are not built, the test shows they are not sent.

## Lane 4. Search coverage

**MVEE:** [Search](../argus-minimum-viable-ecosystem-experience.md#search-find-what-i-already-know). Board lane for #751. Documents are the #776 contract. Conversations stay on `GET /api/v1/search`.

### Journey and completion

The person searches from the connected Search tab. Existing results still open account, activity, expectation, budget, goal, and debt detail, and Back returns to the same query, filters, and scroll origin. A saved document and an existing conversation also appear. Opening the document loads it from the document API and shows the draft, not a filename with only Delete. Opening the conversation loads that conversation. A document or conversation owned by someone else is absent. A household member does not find another member's private document or chat. Relaunch restores the search origin and refetches.

### What exists

| Piece | Where | PR |
| --- | --- | --- |
| Financial search | `GET /api/v1/financial-search`. `src/argus/domain/financial_search.py` kinds `account`, `activity`, `expectation`, `budget`, `goal`, `debt`. Native `FinancialSearch.swift`, `FinancialSearchModel.swift`, `FinancialSearchView.swift` | #751, then #753, #755, #757 for the later kinds |
| Household financial search | `GET /api/v1/households/{id}/search`. Hit shape in `financial_schemas.SearchHit`, with `plan_ref` for shared plans | #766, #773 |
| Conversation search | `GET /api/v1/search` in `src/argus/api/routers/search.py`. Items are `type: conversation` with `conversation_id` | Existing Omnisearch, not the iPhone financial tab |
| Documents | `src/argus/api/routers/financial_documents.py`. List, get, source download, proposal patch. `require_document_surface` requires the ingestion gate and `ARGUS_DOCUMENT_EXTRACTION_ENABLED`, which defaults off. Bytes in `financial_document_extractions.source_bytes` via `src/argus/domain/ingestion/documents/store_postgres.py` | #776 |
| Design Search chrome | `CuadraoSearchCanvas.swift` has sample sections for plans, chats, files, and memory. `CuadraoHomeCanvas.swift` notes that chats, files, and memory stay sample-only | Design canvas |

The connected Search tab mounts `FinancialSearchDestination` from `ConnectedCuadraoShell`. It does not mount the canvas.

Reuse `financial_search.search` for financial rows and the document service's list and get methods for documents. Reuse `GET /api/v1/search` for conversations. Do not point Search at `source_bytes`. If a later change moves bytes to Supabase Storage, only the document owner changes. Search keeps calling `/financial-documents` and `/financial-documents/{connection_id}`.

### Gaps

- Financial search does not return documents or conversations. The API contract says it does not search conversations.
- Native `FinancialSearchModel.open` has no document or conversation destination. The assistant tab is `ChatSampleView`.
- Canvas file results are examples in `CuadraoSearchReferences.swift`, not drafts.
- Household search does not include documents or chats. MVEE says those stay private unless explicitly shared. No document-sharing grant exists. Search must omit private documents from household results. Do not invent a share flag.
- [Issue #778](https://github.com/lagarcess/argus/issues/778) plans to move retained document source bytes out of Postgres bytea and into a private Supabase Storage bucket before documents are enabled. Search uses the document API and never storage internals, so that move does not affect Search.

### Allowed files

`src/argus/domain/financial_search.py`, `src/argus/api/routers/financial_search.py`, the connected search Swift files named above, `ArgusSession` search types, and the connected financial Search section of the API contract when this lane is landing. Conversation hits call the existing search reader. They do not copy its SQL into financial search.

No-touch: `store_postgres.py` except a bugfix the document owner makes, `CuadraoSearchCanvas.swift`, interpreter prompts, `GET /api/v1/search` ranking.

### Acceptance

Postgres with one saved document and one conversation for user A, and the same kinds for user B. A finds only A's rows and opens the document through the document API and the conversation through the conversation id. Back restores the query. Relaunch refetches. B's queries do not include A's ids. A household member without a document grant does not see the other member's draft. English and Spanish filters, including the new document and conversation labels once the captain adds the strings. Document flag off: financial search still returns the existing kinds and returns no document hits. No test reads `source_bytes` from the Search package.

## Lane 5. Spaces

**MVEE:** [Financial spaces](../argus-minimum-viable-ecosystem-experience.md#financial-spaces), [managing private spaces](../argus-minimum-viable-ecosystem-experience.md#managing-private-spaces), and [reassigning accounts](../argus-minimum-viable-ecosystem-experience.md#reassigning-accounts-between-spaces). Board row D04.

### Journey and completion

Personal already exists for every account because `space_id` defaults to `personal`. The person creates one named private Business space and one named Custom space. Names are unique among their spaces, including archived ones. They move a standalone account from Personal to Business. The account id is unchanged. Opening balance, activity, corrections, and notes still load. No new transaction appears. A budget that included the account stops including it in Personal and does not move the budget row. A goal or debt plan linked to the account still opens and still points at the same account id. Household grants on that account are unchanged. Home and Search, after those lanes land, show the account in Business and label that space. The person cannot move an account that has a transfer, payment, cross-account refund, loan link, or unfinished document draft. The screen explains the link. Archive and restore of an empty-of-purpose private space follow the MVEE: archive keeps the records, delete is only for an empty private space, and Personal cannot be renamed, archived, or deleted.

Production limits and purge windows stay unspecified. This lane ships one Business and one Custom space per user, archive, and restore. It does not ship a purge job or an unlimited entitlement.

Moving an account between spaces is the highest-risk part of this lane. The founder warns that it means hard reconciliation of balance history, settlements, and backfilling. The catalog of spaces is not that risk. Account moves land after the Home series, with Codex review and the dedicated eval below. They do not land second.

### Move invariants

- Do not rewrite historical balances, opening balances, corrections, or settlements. Do not copy them onto the destination.
- Record the move as an auditable event: account id, source space, destination space, actor, and time. The account id does not change. `space_id` is the current assignment only.
- Home series and comparisons are recomputed from canonical history. They are not a snapshot copied onto the new space.
- The move is idempotent and recoverable. A repeat of the same move does not apply twice. A failed move leaves one end state, source or destination, with history intact.

### Reconciliation cases the lane must test

- Opening balance and later corrections stay the same rows and revisions. The move does not write a new opening balance.
- Recorded activity amounts and dates are unchanged. A month with no activity stays empty.
- A settlement between two accounts, including a transfer or a payment, is not rewritten. Moving one account in a linked pair is blocked, and both histories stay put. The same block covers a cross-account refund, a loan link, and an unfinished document draft.
- Backfill after the move: a correction or an activity dated before the move appends to canonical history. It does not create a destination copy and does not rewrite the pre-move revision.
- Repeating the same move is a no-op: one event, one space assignment.
- An interrupted move retries to the same end state. The account is still in the source space with no event, or in the destination space with one event. It is never in both, and history is never half-copied.
- Home series and the comparison, read after the move, match a fresh computation from canonical history for the destination space. They do not match a copied snapshot.
- Household grants, budget rows, and goal rows keep their ids. Budget inclusion follows the account's new space without relocating the budget.

### Dedicated eval

Codex review covers the space table and the move. The move also needs a dedicated eval before landing. The eval runs the cases above against Postgres and fails if any historical balance, correction, or settlement row changes, if the move event is missing or duplicated, or if the Home series differs from a fresh read of canonical history.

### What exists

| Piece | Where |
| --- | --- |
| Column | `financial_accounts.space_id text not null default 'personal'` in `supabase/migrations/20260928200000_financial_accounts_first_slice.sql`. [First-slice spec](financial-accounts-first-slice.md) says no route reads or writes it |
| Domain | `PERSONAL_SPACE = "personal"` in `src/argus/domain/recording/accounts.py`. `AccountFacts` has no space field. Household grants must not rewrite `space_id`. The membership migration comment says the same |
| Canvas | `CuadraoSpacesPreview.swift`, `CuadraoSpacesSheet.swift`, `CuadraoSpaceSelector.swift`. In-memory Personal, Household, Business, and Custom. New accounts take `selectedSpaceID` in `CuadraoFirstAccountSheet.swift`. No move-to-space action. The 30 September design lock says the hold menu has rename, add transaction, and archive, and has no move-to-space. The MVEE still puts Move to another space on Manage account. The connected app follows the API, which has neither |

Reuse the account id, the recording service, and the canvas rules for rename, archive, and empty delete as the behavior contract. Persist them in the recording owner. Do not keep a second space list in the client.

### Gaps

- No space table, so a Business or Custom name has nowhere to live. `space_id` as free text cannot enforce unique names or archive. A space row owned by the user, with the account's `space_id` as a foreign key, is the missing owner. Personal is the default row, not a deletable one. This is a schema addition, not a second account store.
- No move command, no link check, no budget-inclusion update. The move, when it is built, follows the invariants above. It is not a rewrite of history.
- Connected Home, Accounts, and Search do not send or display a space.
- Household is a membership projection, not a `space_id`. Do not store household as `space_id`. The MVEE already separates share from private-space assignment.

### Allowed files

`src/argus/domain/recording/accounts.py` and the account repository that writes `financial_accounts`, a new space module beside it, `src/argus/api/routers/financial_accounts.py`, one new migration, the account section of the API contract and data model when this lane is landing, and the account tests.

Budget inclusion changes go through the existing budget reader, which already filters by `account_ids`. The move updates that selection or the reader's space filter. It does not relocate the budget row. The Plan owner reviews that read. Spaces does not fork budget math.

No-touch: `CuadraoSpaces*.swift`, household grant SQL, document storage, the chart canvas.

### Acceptance

Postgres. Create Business and Custom, relaunch, and see the same names. Move a standalone account, relaunch, and read the same activity on the same account id in the new space, with the same opening balance and the same correction revisions. The source budget no longer counts that account's new activity, and the budget id is unchanged. A linked transfer blocks the move and leaves every row in place. A household grant still resolves after the move. A second user cannot list the spaces. Delete is rejected while the space has an account. Personal delete and rename are rejected. English and Spanish for the move review and the blocked-link explanation. `ARGUS_FINANCIAL_ACCOUNTS_ENABLED` off still 404s the new routes. The dedicated eval above is part of acceptance for the move, not a substitute for it.

## Blocks before a lane starts

| Lane | Can start now | Blocked until |
| --- | --- | --- |
| Home | Reading the current `financial-home` response and listing the series gap | Founder decision 3, then the series. View binding also waits on the design-branch collision for `ConnectedCuadraoHome.swift` |
| Household | Share link, accept, leave, and remove. Code and QR present the same invitation. Email is later work and does not block | A link that opens the app until decision 1. How an invitee gets the TestFlight build until decision 2. Proposals (a), (b), and (c) wait and are not in this pass unless the founder adopts them |
| Updates | Inbox table and read state, draft-ready rows from `review_ready`, invitation rows after preview or accept | Bill trigger until decision 4. Push and email until decision 5. Navigation to a document or conversation until those destinations exist |
| Search | Document and conversation hits through the existing APIs, behind the document flag for documents | Nothing in the founder list. Issue #778 moves retained source bytes to a private Supabase Storage bucket before documents are enabled. Search does not wait on it, because Search uses the document API and never storage internals |
| Spaces | Space catalog only: rows, names, archive, new accounts choosing a space | Account moves until the Home series reader exists, then Codex review and the dedicated eval. Linked moves stay blocked. Home and Search display of the new space lands with those lanes |

No lane is dispatched by this document.
