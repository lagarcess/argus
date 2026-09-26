# Argus minimum viable ecosystem experience

**Status:** Founder-approved experience direction, recorded September 26, 2026.
**Audience:** Product, design, engineering, and collaborating agents.
**Decision source:** Founder conversation approving the ecosystem structure and asking to lock it into a document, including information ingestion.
**Purpose:** Define the smallest cohesive ecosystem, its surfaces, and the movement of information between them. This is an experience specification, not an implementation schedule or a claim of shipped capability.

## 1. The product decision

**Argus helps people understand where they stand, keep their money organized, and know what to do next.**

The initial audience is people living in the Dominican Republic. Cash, disconnected banks, documents, and manual records are normal starting conditions. Argus should remain useful under those conditions.

We are testing a minimum viable ecosystem, not restricting the product to one calculator or one narrow financial obligation. People can enter through different needs: understanding spending, organizing accounts, managing debt, saving toward something, or comparing financial alternatives. Their activity should improve the same financial picture.

The strongest recurring pain point is not yet established. This breadth is intentional: observe what people use, what brings them back, and which connected experiences deserve expansion or removal. Do not present the proposed differentiation as proven market demand.

The reinforcing experience is:

**Record → understand → plan → notice change → return and update.**

Not everyone must complete every step or use every surface. Each surface must be useful on its own and make the others more useful.

### Relationship to existing documents

Use [documentation authority](../DOCUMENTATION_AUTHORITY.md) for the reading order,
document ownership, historical pointers, and assigned-package reconciliation.

This document owns the founder-approved pivot experience described here. It changes the intended product direction from chat as the entire workspace to a financial ecosystem with chat as a powerful entry point and interaction method.

Existing production documentation continues to describe current implementation and operational safeguards. This document does not assert that the pivot is implemented, silently rewrite release gates, authorize deployment, or establish an engineering sequence. Older chat-primary scope statements should not be used to erase this explicitly approved future experience. Implementation work must reconcile relevant contracts and product documentation explicitly.

Wave sequencing and engineering breakdown are deliberately outside this document. Account onboarding and the exact guest-to-account conversion flow remain undecided.

### 1.1 Locked audience and experience emphasis

**Founder approval, September 26, 2026:** Following the social-research discussion, the founder explicitly approved the proposed niche and ecosystem emphasis with “Yes you got it lock it.” This section is the canonical decision; supporting research retains its provenance and does not own approved scope.

Design first for **Dominican adults juggling cash, bank accounts, and debt, who already try to organize their money but cannot confidently tell what remains after their commitments.** Income may arrive by quincena, commissions, remittances, or other variable sources. This is a design focus, not an eligibility rule or a requirement that everyone have every account type.

The experience promise is:

> Know what is already committed, what remains until your next income, and how your choices change that.

Lock these refinements into the ecosystem:

- **Home leads with the upcoming financial period.** Show near-term commitments, received versus expected income, and an understandable estimate of remaining money. Preserve asset/debt summaries and deeper detail.
- **Budgets, debt payments, and goals share the same financial picture.** They must not independently allocate the same money. Match completed activity against its planned commitment rather than subtracting both.
- **Each confirmed entry reduces future effort.** Reuse relevant confirmed context, match later imports, preserve corrections, and make returning easier than reconstructing the picture elsewhere.
- **Tracking and decisions reinforce each other.** Existing Argus calculations and explanations use the recorded context to explore consequences; hypothetical scenarios never silently become actual financial activity.
- **Preserve ecosystem breadth and open chat.** Market questions, investing, and historical comparisons remain accessible without a debt-repayment gate or prescribed life-stage sequence.
- **Support personal and household finances together.** A person can invite their partner and combine shared accounts, responsibilities, and plans while retaining individual accounts. Household collaboration is part of the minimum ecosystem; section 12 owns its experience and sharing boundaries.

An account balance is not the same as money remaining after commitments. Show the estimate's period, included obligations, source freshness, currency, and assumptions. Expected income does not increase the current actual balance. Timing matters: a positive end-of-period estimate must not hide a shortfall before an earlier bill is due. When information is missing, make that visible instead of presenting an unconditional “safe to spend” number.

Approval locks the product direction, not a claim that demand or retention has already been proven. Learn which uncertainties users resolve, which inputs are burdensome, and which real decisions bring them back.

## 2. Product character and platforms

- Retain the current Argus visual identity and typography. The founder rejected replacing it with a new visual identity.
- Feel elegant, modern, crisp, calm, and trustworthy: a personal financial control room with the reassurance of a citadel.
- Optimize for a phone and natural, one-handed flows. Avoid shrinking a desktop dashboard onto mobile.
- Native iOS and Android apps are the intended mobile products, not PWA shells. Web remains a useful product surface; platform implementation and sequencing are separate decisions.
- Use progressive disclosure: clear summaries first, details when requested. Avoid walls of charts, dense tables, decorative widgets, and unnecessary setup.
- Preserve Spanish and English support, with the Dominican audience informing language and examples.
- Treat DOP and USD separately. Do not silently combine currencies. Any future conversion must expose its rate, date, and source.

### Navigation

Primary navigation: **Home · Accounts · Argus · Plan · Search**.

Use a refined floating glass treatment on mobile, simple recognizable icons, and the Argus logo for the central chat destination. Visible labels need not sit beside every icon, but controls require accessible names and a clear selected state. Adapt the glass treatment to platform capabilities; a web approximation is not proof of native system behavior.

The bar may compact or recede while scrolling and return when needed. Movement must not make navigation difficult to recover, obscure input, or ignore reduced-motion settings.

Updates and profile live in the header, outside the primary bar. Profile opens app/account settings; Home owns the personal financial overview. Keep the chat header restrained: no redundant “Ask Argus” title or duplicate top-left branding over the branded cold start. Home may retain the wordmark; other surfaces use clear destination titles.

## 3. Minimum useful capacity of each surface

### Home: understand where I stand

Home answers:

1. What do I have and owe?
2. What changed?
3. What needs my attention?

Minimum capacity:

- A clear summary of recorded assets and debts, separated by currency.
- Recent meaningful activity: spending, income, payments, and progress.
- Relevant next actions: a payment approaching, a budget nearing its limit, or an account needing an update.
- A readily available Record action.
- Resume unfinished work, such as reviewing a statement import.
- Open the account, transaction, plan, or explanation behind a summary.

Use a simple vertical mobile flow. Do not turn Home into a generic market-news feed or a collection of charts. Incomplete information should still be useful: say “Based on your recorded accounts” and show freshness instead of suggesting comprehensive live coverage.

### Accounts: organize the financial facts

Minimum account types include cash, checking, savings, investments, credit cards, and other debts. Cash is first-class.

Minimum capacity:

- Create an account manually or populate supported fields from a document.
- Inspect balance, currency, activity, source, and last-updated date.
- Record spending, income, transfers, payments, and balance corrections.
- Edit transactions and categories; correct or undo mistakes.
- Reconcile a recorded balance against a statement or the user's observed balance.
- Track investments initially through recorded balances or holdings without requiring a portfolio terminal.
- Distinguish individual and joint accounts, with explicit household visibility. One joint account can appear in both personal and household contexts without becoming two accounts or being counted twice.

Transfers between owned accounts are not spending. A credit-card payment must not count purchases twice. A cash withdrawal is a transfer to cash when that is what happened; later cash purchases are expenses. Changes to a balance must not silently manufacture income or spending.

### Argus: ask, understand, and get things done

Preserve the existing chat experience: time-aware greetings, typed hero animation, starter chips, composer, conversational continuity, grounded calculations, research, historical simulations, comparisons, result explanations, and retrieval. Do not add a persistent blinking cursor to the completed hero text.

Minimum capacity:

- Ask general finance and market questions without first recording personal finances.
- Ask about recorded accounts, activity, and plans when available and permitted.
- Describe financial activity and review a proposed record.
- Speak activity or questions, then review the interpreted content.
- Upload a supported file, statement, scan, or image for review.
- Create or adjust a plan through a confirmed action.
- Compare investments with alternatives such as savings or certificates of deposit using supported calculations and sourced assumptions.

Conversational answers and financial writes are distinct. Asking “What if I spent RD$5,000?” must not record an expense. New proposed financial records require confirmation. The assistant can help across the app; it is not necessary to visit chat for every edit.

Guest chat remains part of the intended experience. Do not settle persistent storage, registration timing, or onboarding policy through incidental UI choices; those decisions are parked.

### Plan: decide what I want to change

Minimum capacity:

- A spending budget.
- A savings goal.
- A debt-payment plan.

Each shows the same understandable structure: current position, intended outcome, planned contribution or limit, and progress. Users can create and edit these manually or through Argus.

Existing calculators supply useful scenarios. A savings calculation can become a goal; a payoff calculation can become a debt plan; an opportunity-cost comparison can inform a decision. Saving a scenario does not authorize any real-money action.

Projected progress and actual progress are separate. “If you save RD$3,000 monthly” is a projection. Recorded contributions establish what happened. Avoid counting the same contribution twice when it appears through multiple sources.

### Search: find what I already know

Minimum capacity is unified retrieval across transactions, accounts, plans, goals, conversations, saved answers, and prior analyses, with direct links to their owning surfaces.

Build on the existing Omnisearch and history experience. Finding “that certificate comparison” should recover useful prior thinking, not require remembering which screen created it.

Market-product discovery is an expansion direction: loans, cards, insurance, savings products, and other alternatives. It becomes useful when there is maintained, sourced inventory. Do not fill the minimum ecosystem with fictional offers or imply shopping/execution capabilities that do not exist.

### Updates: tell me when something deserves attention

The bell opens a persistent inbox. Minimum useful categories are budget thresholds, goal milestones, payment reminders, scheduled summaries, changed conditions relevant to saved answers/plans, and records needing review or refresh.

Every update should explain what changed, why it matters, and where to act. Delivery preferences belong in settings. Scheduled briefs should concern useful, selected context rather than become a generic daily feed.

Distinguish changes in user records from external market changes. Argus can observe what its sources provide; without fresh banking information it cannot claim to see every transaction. Investment-performance updates require an appropriate data source, time window, and comparison basis.

Notifications should invite a return without exposing financial amounts in push/email previews. Details belong inside the authenticated experience.

### Profile: control Argus

Own language, notification preferences, security, data controls, export, account management, and household invitations/membership. Keep this separate from Accounts and Home so “my profile” does not ambiguously mean “my finances.” The financial view itself switches between personal and household context within the main experience.

## 4. Information ingestion: one destination, several entry methods

The product must work with incomplete banking connectivity. Users may mix input methods without creating competing copies of their finances.

**All ingestion methods converge on one flow:**

**Capture → interpret/extract → review and resolve → confirm → save the canonical record → update dependent surfaces.**

The confirmed record is the durable financial fact. Chat messages, uploaded files, notifications, and extracted text provide context and provenance; they are not independent competing ledgers. Home, Accounts, Plan, Search, and Updates derive from the same confirmed records.

The input methods below are part of the experience direction. Their technical readiness differs. Wallet integrations and bank access are experiments, not promises of universal support or prerequisites for a useful ecosystem. Provider selection is not locked.

### 4.1 Direct manual entry and editing

Users can add accounts, opening balances, transactions, debts, holdings, goals, and corrections without AI. Keep common entries short, with sensible reusable choices and editable details.

Support both individual activity and balance updates. Someone who only knows their current balance can record that fact without inventing a complete transaction history. Make clear what is known and what remains unrecorded.

Saving a manual form is the user's confirmation; do not add redundant AI approval steps. Manual corrections should be available for every imported or interpreted record.

### 4.2 Type to Argus

Example: “Gasté RD$850 en comida, en efectivo.”

Argus proposes the amount, currency, date, activity type, category, and cash account. The user can confirm or edit the proposal before it affects their finances.

Ask only for material missing information. Do not silently guess an account, currency, debt, or transfer relationship when the choice changes the financial picture. Multiple activities in one message may become a reviewable batch.

Distinguish actual activity from hypotheticals, intentions, questions, and quotations. “Voy a pagar…” is not evidence that a payment occurred.

### 4.3 Speak to Argus

Voice is another way to express the same questions and activities, not a separate financial workflow.

- Record speech, transcribe it, and interpret the intended question or action.
- Let the person inspect and correct important interpreted details.
- Present the same editable financial draft used for typed input.
- Save only after confirmation.
- Handle interrupted recordings or uncertain amounts without creating partial financial records.

ElevenLabs or another provider may be evaluated; none is selected by this decision. Speech-to-text is the core capture need. A full real-time spoken assistant is not implied. Audio retention and consent must be explicit product decisions, not hidden provider defaults.

### 4.4 Upload a file or statement

Support a path for statements and structured transaction files. Exact supported formats and institutions must be stated truthfully as they become available; the intended document path includes PDFs and images, while structured files can include CSV-type exports.

The experience should:

1. Identify the account, currency, statement period, and available balances.
2. Extract candidate transactions and relevant statement facts, such as payment due dates or rates when actually present.
3. Show the original source alongside reviewable extracted information when needed.
4. Flag uncertain fields, missing pages, unreadable content, and suspected duplicates.
5. Let the user assign the account, correct categories/details, and confirm a reviewed batch.
6. Explain what was added, skipped, or left unresolved.

Do not force separate confirmation for every reliable row in a large statement. Batch confirmation must remain understandable, with exceptions highlighted. Failed imports must be recoverable without re-adding successful records.

Statement balances and transactions may describe the same money. Do not add them together as if both were new activity. Preserve statement dates instead of presenting older statement data as today's bank balance.

### 4.5 Photograph or scan a document

Camera capture, document scans, receipts, and screenshots feed the document-review flow. Help users capture readable, complete information and request a retake when necessary.

A photographed receipt can propose a purchase; a bank screenshot may establish only a balance. Extract only what the source supports. OCR output is a proposal, not an authoritative financial fact. Users can always correct or abandon it.

### 4.6 Apple Pay / Google Pay and device-assisted capture

Explore opt-in device workflows that detect a payment-related event and offer a draft: “A payment was detected. Add it to your tracking?”

Potential paths include Apple Shortcuts/App Intents and permitted Android integrations. Feasibility must be validated on the actual platform, device, and payment flow. Neither Apple Pay nor Google Pay is assumed to expose a universal transaction feed to Argus.

Only draft fields the event actually supplies. Missing merchant, amount, currency, or account details must remain unresolved or be supplied by the user. A device notification is not proof of a settled transaction.

The user opts in, can disable the integration, reviews the draft, and can dismiss it. Match later statement imports against these entries so the same purchase is not counted again. Do not imply background tracking is active when the platform cannot support it.

### 4.7 Bank connections and read-only browser-assisted experiments

Direct APIs or aggregators may eventually provide balances and transactions. Named bank coverage, permission, freshness, and failure behavior must be verified; a provider's general marketing claim does not establish support.

The founder also wants to explore user-authorized, read-only browser-assisted access where APIs are absent: the user authenticates to their bank through a secure flow, and an experiment retrieves permitted financial information for review/import. This is an exploration direction, not a selected architecture or a claim that all Dominican banks support it.

Before a real integration, resolve institution-specific feasibility, terms, authentication, credential/session handling, and user consent. Do not bypass MFA or bank security controls. Authentication secrets must not enter chat, analytics, or ordinary logs. The exact secure access design remains open.

Bank access must show connection state, last successful refresh, and actionable failure/re-authentication status. A failed refresh must preserve existing records and their old freshness timestamp. This ingestion path does not authorize payments, transfers, trading, or other banking actions.

Begin with the same draft/review boundary. Any future automatic acceptance of trusted feeds requires an explicit policy rather than silently removing user review. API partnerships can replace the access mechanism without replacing the user's financial records or experience.

## 5. Shared ingestion and trust requirements

- **Provenance:** distinguish user-entered, extracted, connected, and calculated information. Retain enough source context to explain a record without spreading sensitive raw content everywhere.
- **Dates:** distinguish activity date, statement/as-of date, and capture/refresh time.
- **Currency:** preserve source currency; ask when ambiguous. Do not infer dollars or pesos from an unqualified amount.
- **Drafts:** unconfirmed proposals do not affect balances, budgets, goal progress, or alerts about actual spending.
- **Duplicates:** handle repeated uploads, overlapping statements, spoken/manual entries later seen in a statement, and repeated integration events. Surface uncertain matches for review rather than silently deleting legitimate similar purchases.
- **Transfers and repayments:** link the two sides where known and avoid double-counting spending or income.
- **Reconciliation:** distinguish a balance correction from a new transaction. Explain discrepancies; never invent missing activity to force agreement.
- **Corrections:** let users edit, undo, or remove mistakes and see the resulting changes across surfaces. Keep enough history to explain changes.
- **Freshness:** an old known balance remains old, even if Argus opens the screen today. The app must not imply continuous awareness beyond available data.
- **Privacy and control:** explain what is collected and retained; provide appropriate deletion/export controls. Keep financial amounts, document contents, transcripts, and credentials out of analytics and ordinary logs. Storage and guest policies still need explicit implementation decisions.
- **Recovery:** preserve review progress where appropriate and offer a manual path when parsing, voice, or bank access fails.

## 6. Connected journeys that the ecosystem must support

### Record everyday cash activity

Type or speak an expense → review and confirm → cash account activity updates → relevant budget changes → Home reflects recorded spending → any meaningful threshold update links back to the budget.

### Understand a statement

Upload or scan a statement → resolve extraction and duplicate issues → confirm → Accounts reflects the new information → Home explains what changed → ask Argus about a charge or payment → save a plan if useful.

### Explore a financial choice

Ask a general market or personal-finance question → receive a grounded calculation or sourced explanation → compare a supported alternative → optionally save a goal or plan → record actual progress → revisit with updated facts.

An investment simulation remains historical evidence, not a promise of future performance or an executed investment.

### Return because something changed

A relevant recorded or external fact changes → Argus creates an explainable update → the user opens the affected account, plan, or answer → inspects the basis → adjusts or records an action if desired.

## 7. Carry forward the existing Argus investment

| Existing capability | Role in the ecosystem |
| --- | --- |
| Chat, cold-start motion, greetings, chips, composer | Familiar entry and conversational help |
| Grounded calculators | Explain choices and support saved plans |
| Research and historical simulations | Explore investments and opportunity costs |
| Structured results, assumptions, confirmations | Make proposals and consequences reviewable |
| Conversations, history, Omnisearch | Recover prior reasoning and evidence |
| Localization, guest access, mobile experience | Reduce friction when starting and returning |
| Saved-answer and change-awareness direction | Relevant updates tied to a person's context |

This is a reuse map, not a claim that components need no adaptation or an exhaustive inventory of production features. Existing capabilities, interactions, records, and gates carry forward unless explicitly changed; omission from this document is not retirement. The primary addition is a persistent, user-correctable personal financial picture. Preserve the existing conversational intelligence and trust boundaries while connecting it to those records. [PRODUCT.md](../PRODUCT.md#current-production-availability-and-planned-changes) owns current availability and approved transitions; the planned experience does not itself enable a hidden feature.

## 8. Differentiation and boundaries

The intended differentiation is a complete-feeling experience even when financial data is incomplete: cash, documents, manual input, and eventual bank connections are all normal ways to participate. Combine low-effort recording with grounded explanations and continuity across a person's financial life.

The minimum ecosystem should feel credible through reliable editing, clear navigation, useful retrieval, currency handling, transparent freshness, and connected outcomes. These are experience goals, not an assertion of verified competitor parity.

Future directions include maintained financial-product discovery, shopping assistance, bank partnerships, remittances, bank-backed accounts/cards, and investment roundups. They are not required capacities of this minimum ecosystem and are not authorized financial execution by this document.

The boundary for adding a capability is: **does it help someone understand, maintain, or improve the same financial picture?**

## 9. Decisions deliberately left open

- Account onboarding, guest persistence, and conversion timing.
- Exact voice, OCR/document, and banking providers and supported formats/institutions.
- Wallet/device automation feasibility and permissions by platform.
- Secure design and institution-specific conditions for browser-assisted bank access.
- Source-file/audio retention details and any future automatic acceptance policy.
- Notification delivery channels and scheduling defaults.
- Maintained market-product inventory, commercial relationships, and execution permissions.
- Engineering breakdown, release order, timelines, and platform sequencing.
- Household invitation delivery channel and detailed membership, removal, retention, and permission mechanics. The household capability itself is approved; these details must preserve section 12's visibility and consent boundaries.

These open implementation choices do not reopen the approved ecosystem structure. Agents should preserve the distinction between the intended experience, an exploratory integration, and a currently working feature.

## 10. Supporting research

- [DR and Latin American finance pain points: research-to-MVEE mapping](../research/2026-09-26-dr-latam-finance-painpoints-mvee.md) — founder-supplied social/market research recorded September 26, 2026, with the original text and executive summary preserved separately. Its audience and experience-emphasis proposal was subsequently approved and is owned by section 1.1 above. Other research suggestions remain candidates unless explicitly adopted.

## 11. Pain points, limits, and the reinforcing loop

### 11.1 Pain points the minimum ecosystem is designed to address

These are intended outcomes, not assertions of shipped behavior or guaranteed financial improvement.

| User pain | How the ecosystem helps | Boundary |
| --- | --- | --- |
| “My money is scattered; I cannot see where I stand.” | Accounts unifies recorded cash, bank balances, investments, and debts; Home summarizes; Search retrieves the source | Coverage depends on supplied records and supported connections; incomplete coverage stays visible |
| “I do not know what remains until I get paid.” | Home relates dated commitments to recorded money and explicit income assumptions; Plan shows allocations | Estimates expose missing expenses and uncertain income; Argus cannot guarantee affordability |
| “My income varies, so a fixed monthly budget does not fit.” | Separate actual receipts from expected inflows; revise timing and plans when circumstances change | Argus cannot guarantee a commission, remittance, job, or future income |
| “Recording everything is too much work.” | Manual, typed, spoken, and document inputs converge on reviewable records; retain context and match imports | Capture cannot become effortless by inventing facts; device and bank automation remain conditional integrations |
| “I keep paying debt but do not understand the result.” | Bring debts and activity together; explain payment scenarios, costs, and actual versus projected progress | Calculations depend on supplied terms and supported models; Argus does not refinance or negotiate debts |
| “My budget, debt payments, and goals compete for the same money.” | Plan relates all commitments to a shared picture and shows how a proposed choice affects it | The person chooses priorities; no forced financial ladder or automatic money movement |
| “Bills and irregular expenses catch me off guard.” | Record recurring and occasional obligations, show upcoming dates, and issue selected reminders | A reminder does not pay a bill; unknown obligations cannot be monitored |
| “An emergency erased my progress.” | Show its effect on accounts and goals; support revising a plan without blame | Visibility and planning do not provide emergency cash or insurance |
| “I cannot tell how a choice changes my situation.” | Argus uses grounded calculations, comparisons, and recorded facts to explain alternatives; a useful scenario can become a saved plan | A simulation is not a promise, executed transaction, or automatic recommendation |
| “I do not trust a number or cannot find where it came from.” | Expose assumptions, provenance, freshness, and editable records; Search reconnects an answer to its evidence | Transparency helps assess information; it does not certify every external source as correct |
| “We manage money together but cannot see our shared commitments clearly.” | Invite a partner; combine explicitly shared individual and joint accounts, obligations, budgets, and goals in a household view | Household membership does not grant access to every personal account or conversation; only authorized shared information contributes to the shared picture |

### 11.2 Pain points only partially addressed or outside the minimum

- **Insufficient income, inflation, and housing prices:** Argus can expose a shortfall and model choices; it cannot create surplus, employment, cheaper housing, or purchasing power. Do not equate a structural shortfall with poor discipline.
- **Housing access:** Supported payment scenarios and savings goals can help exploration. Mortgage underwriting, preapproval, access to a lender, and dedicated qualification workflows are not minimum capabilities promised here.
- **Credit access and bureau problems:** Explaining supported supplied information is different from obtaining a bureau feed, fixing a credit file, predicting a score, or determining why a lender declined. Those specialized services are not locked into this minimum.
- **Fraud and scams:** Grounded explanations can expose missing information or unsupported claims. Guaranteed scam detection, account-takeover monitoring, and recovery of losses are not provided by this ecosystem definition.
- **Banking and financial execution:** No claim of universal live bank access, automated bill payment, debt negotiation, subscription cancellation, remittance transfer, custody, card issuance, or trade execution.
- **Household scope:** Partner invitations and combined household finances are included, as defined in section 12. Joining a household does not provide bank-account authority, merge personal identities, or make all private records visible. Broader family/dependent and professional-advisor roles are not implied by this decision.
- **Behavior and emotional stress:** Clear, neutral feedback and low-effort routines may help. Habit, reduced anxiety, and retention are outcomes to learn from users, not guarantees or substitutes for human support.

### 11.3 Five experience pillars and how they reinforce the loop

These are MVEE experience pillars, distinct from the repository's engineering quality pillars. They describe the existing approved loop rather than five new modules or navigation destinations.

| Experience pillar | Primary surfaces | Value to the person | How it strengthens the next step |
| --- | --- | --- | --- |
| **Record with little effort** | Accounts, Argus, shared capture/review controls | Keep finances up to date through the input method that fits the moment | Confirmed, corrected facts make the financial picture more useful |
| **Understand the picture** | Home, Accounts, Argus, Search | See what is known, committed, changing, or uncertain | Clear explanations make it easier to choose a realistic action or plan |
| **Plan and compare choices** | Plan, Argus | Connect budgets, debts, and goals; explore consequences before acting | Saved commitments establish meaningful dates, thresholds, and progress to revisit |
| **Notice relevant change** | Updates, Home | Recognize a deadline, change, milestone, or stale assumption while it is useful | Each update links to the affected record or decision and gives a reason to return |
| **Return and adjust easily** | All surfaces, with Search for continuity | Record what actually happened, correct facts, and revise a plan without starting over | Updated records improve the next explanation, forecast, and reminder |

The loop is **record → understand → plan → notice → return and update**. It also supports direct entry at any point: a question, an account check, a saved goal, or a useful reminder. Daily use and visiting every surface are not requirements.

Profile/data controls and transparent provenance support trust throughout. Search preserves continuity. Chat crosses the entire loop, contributing capture, interpretation, explanation, and comparison rather than competing with the other surfaces.

### 11.4 Example and failure conditions

A person confirms a received commission. Accounts records it. Home places it alongside upcoming obligations. Plan shows the remaining room after existing commitments. The person asks what an extra debt payment would change and saves a chosen plan. A reminder opens that plan; after the person actually pays, they confirm the payment. The transaction matches the planned commitment, progress updates, and the next visit starts from the revised picture.

That loop fails if capture is too burdensome, stale facts appear current, hypothetical actions change actual balances, several surfaces allocate the same money, reminders are irrelevant, or corrections do not propagate. Polished navigation alone cannot compensate for these breaks.

Retention is intended to come from accumulated useful context and recurring real decisions. The product should remain valuable even when someone dismisses notifications; interruptions are not a substitute for utility.

## 12. Household collaboration: approved minimum capacity

**Founder decision, September 26, 2026:** Include a combined household view and a way to invite a partner. Individual and joint accounts can both be part of the financial picture. This explicitly supersedes the earlier boundary that treated household collaboration as a separate future decision.

### One person can belong to both financial contexts

Provide a clear **Personal / Household** context choice without adding another primary navigation destination. Use the same Home, Accounts, Argus, Plan, Search, and Updates surfaces in the appropriate context. A person can use Argus alone; inviting a partner is optional.

The personal view contains the person's own financial picture and any joint accounts they are authorized to see, with ownership clearly labeled. The household view combines explicitly shared information, rather than summing two personal dashboards.

### Invite and choose what to share

- A person creates a household and invites their partner. The invitation must be accepted before access is granted; each person keeps their own sign-in.
- Before sharing, show what the partner will be able to see and do. Household membership alone must not expose private accounts, documents, chats, or income.
- Support individual accounts kept private, individual accounts explicitly shared with the household, and joint accounts shared by the partners.
- A person can contribute an agreed amount to a household plan without exposing the source account's entire balance or history. Mark whether that contribution is planned or received.
- Account ownership, visibility, and permission to edit are distinct. Label them clearly; joining a household does not transfer ownership or confer banking authority.
- Sharing can be reviewed and revoked. Leaving/removal must stop future unauthorized access, explain effects on shared plans, and avoid silently deleting another person's records. Exact retention and ownership mechanics remain implementation decisions.

### Shared financial picture

**Home:** Show shared money and obligations, expected versus received contributions, and household progress. Identify missing or stale information. Describe totals as based on shared records, not as everything either partner owns.

**Accounts:** Label individual versus joint ownership and who can see or edit the record. Both partners can inspect authorized shared activity. Keep private account details out of the household view.

**Plan:** Support shared budgets, bills, debt commitments, and goals. Make contribution responsibilities understandable without requiring a 50/50 split. Private plans remain private unless explicitly shared.

**Argus:** Let a person ask about the personal or shared picture, with the active context clear. A proposed entry must identify the relevant account or household commitment before confirmation. Answers, summaries, and calculations must not expose another person's private facts indirectly.

**Search and Updates:** Respect the same visibility boundaries. Shared milestones and obligations can generate relevant household updates; private activity must not leak through search results, totals, notifications, exports, or suggested actions. Each person controls their notification preferences.

**Capture and review:** The approved capture paths in section 4 should also serve shared records. Existing chat is a foundation to extend; manual, conversational, voice, document, and connection-based financial-record capture still need their scoped technical contracts and implementation. Show the destination and sharing scope before confirmation. Uploading a document to a household context must make source-document visibility clear; it must not unexpectedly share unrelated private pages or details.

### One shared fact, no duplicate money

- A joint account imported by both people is still one account. Match overlapping transactions and resolve uncertain matches before double-counting.
- A contribution transferred from an individual account to a joint account must not become new household income merely because it moved accounts. Preserve the distinction between external income, transfers, and contributions; show the reporting scope.
- A shared bill appears once in the household obligation total, even when both people contribute toward it. A planned contribution is not actual available cash.
- Confirmed shared updates propagate to both partners' authorized views. Make it possible to identify who recorded or corrected an entry and resolve mistakes without silently overwriting another person's work.
- Information that was not shared must not be silently included in shared calculations, even if a personalized aggregate could conceal its source.

### How the household strengthens the loop

One partner records a household purchase → the shared budget reflects it → both can understand what remains → they adjust an agreed contribution or goal → a relevant update brings either person back → the next confirmed action refreshes the same picture.

The value is less repeated coordination and fewer conflicting versions of shared commitments. This adds collaborative usefulness to the existing loop without making surveillance, mandatory sharing, or relationship management part of the product promise.
