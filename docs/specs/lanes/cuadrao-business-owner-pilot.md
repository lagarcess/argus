# Cuadrao Business owner pilot

## Assignment and authority

This is the October 7, 2026 founder-scoped Business handoff. It scopes the whole
first usable pilot, not only its UI. This PR contains planning only. The founder
will assign the implementing Claude lane separately. No agent was dispatched.

One full-stack owner assesses, builds, verifies and prepares integration landing.
Use the [handoff](cuadrao-business-owner-pilot-handoff.md) to start that lane.
The owner may divide delivery into reviewable PRs without splitting frontend and
backend responsibility. Every delivered user job must work through real storage.

Read [documentation authority](../../DOCUMENTATION_AUTHORITY.md), the
[MVEE](../argus-minimum-viable-ecosystem-experience.md), and existing
[API](../../API_CONTRACT.md), [data](../../DATA_MODEL.md) and
[architecture](../../ARCHITECTURE.md) contracts. This assignment narrows the
Business pilot. It does not rewrite consumer release decisions or imply every
MVEE capability is in this pilot. Record applicable new experience decisions in
the canonical documents with implementation, without overwriting another lane.

Planning base fetched on October 7 is
`93571e593e1677561e1dd38f63b6475574942e2d` on
`origin/codex/private-alpha-next`. Code pointers below were inspected at that
base. They establish reuse candidates, not tested Business availability.
Production deployment identity was not verified for this scope PR. A visual
inspection of the signed-in production chat established only sidebar, composer
and search presentation. Refresh code and issue state at assignment time.

## Deliver the owner outcome

An owner sends a receipt to Cuadrao through WhatsApp or uploads it on the web.
Cuadrao saves the private source, prepares a reviewable draft and shows it in
one inbox. The owner corrects the draft, selects the account and confirms the
expense. After leaving and returning, the owner can find the expense and its
original receipt. Repeated delivery cannot silently create another expense.

The owner can also see a small, accurate business overview and ask Cuadrao's
built-in AI about saved expenses, with links back to the supporting records.
The product is for business owners. It is not an accountant's workstation.

One owner operates each pilot business. No employee submissions, associate
accounts, approver hierarchy or household sharing is included. Private Business
records must remain separate from the same person's Personal and Household data.

## Preserve the agreed experience

| Area | Required pilot behavior |
| --- | --- |
| App shell | Reuse Argus's responsive web/PWA shell, restrained typography, spacing, rounded controls and collapsible sidebar. Preserve existing guest and registered chat outside Business. |
| Search | A desktop top search entry opens the existing omnisearch interaction. Add authorized Business results and source links through canonical search owners. Do not build a second search index just for this page. |
| Sidebar | Expose working overview, receipt inbox, expense records, New chat, Recents and settings destinations. Exact labels and grouping are reviewed in the local preview. No dead future-feature icons. |
| Main panel | Show useful summary cards with period/currency filters and drill-down to their actual records. Keep a full conversation view available. |
| Composer | Keep the familiar composer available at the bottom on overview and conversation views without covering content or losing an unfinished draft. Define its contextual handoff to a conversation. |
| Profile | Top-right at desktop widths. Preserve the existing placement on smaller viewports. Reuse one profile state and menu owner. |
| Phone web | Cards stack, navigation stays usable, upload and review work with touch and the keyboard. This does not promise offline ingestion or background browser execution. |
| Languages | English and Spanish, including loading, empty, validation, failure and recovery states. |

Start the overview with receipts awaiting review, confirmed expenses in the
selected period and imports needing attention. Show recorded coverage and
freshness. Use separate currency totals; do not add DOP and USD or invent FX.
Do not show profit, runway, revenue or trend claims without sufficient real data.
Summary cards can use deterministic facts. Generative summaries are not required.

Separate conversations, New chat and Recents remain. Agent actions can later
operate within those conversations. A consumer continuous-conversation target
does not require replacing Business history in this assignment.

Preserve the broader Business direction for accounts, planning, customers and
useful actions. It is not necessary to build all of Midday to finish this pilot.
Company logo customization, a detachable/draggable desktop composer, dashboard
builders, invoicing, bank integration, team billing and the native Business app
are outside this slice.

## Adapt starter chips and preserve personality

Founder clarification on October 7 keeps the existing starter-chip interaction.
Adapt chips to actual pilot entry points, such as uploading a receipt, reviewing
pending receipts and asking about saved expenses. Chips open the correct flow or
prepare an editable question. They must not auto-approve expenses, invoke paid
AI without consent or advertise unfinished features. Test empty and populated
Business states so suggestions lead somewhere useful.

The founder's reference to new-chat type-out messages means the rotating welcome
or starter copy, not a new chart type. Business-specific greetings and additional
Cuadrao personality are optional later polish. Preserve suitable existing copy
and motion without making a copywriting pass a pilot requirement. Respect reduced
motion and avoid repeatedly announcing animated text to screen readers.

Inventory the Argus A in the chat background, chat-loading transitions and the
top-left corner. Replace those through a shared brand asset once the founder
approves the Cuadrao logo. Logo design and that replacement are not pilot blockers.
Do not invent a final logo or treat marketing's provisional favicon as approved
application branding. Keep a clear asset owner so future replacement is consistent.

## Adapt the composer to receipt intake

Founder clarification on October 7 adds the consumer ingestion experience to
Business's existing composer. Use an attachment/add control as the initial
entry point. Omit the asset/indicator `@` picker in the Business composer for
this pilot. Preserve it in existing Argus chat where it still has a purpose.
This changes presentation, not the shared runtime's existing finance abilities.

Assess `ios/ArgusFoundation/Cuadrao/Receipts/CuadraoReceiptCapture.swift`,
`CuadraoReceiptNativePicker.swift` and
`ios/ArgusFoundation/Connected/ConnectedReceiptDrafts.swift` for the consumer
interaction and contract. Reuse the contract and interaction intent, not Swift
components inside a browser. Consumer release flags remain owned by consumer.
Also distinguish financial receipt ingestion from `web/components/receipt/`,
which contains existing answer/evidence receipt presentation.

- Every supported browser gets a normal file picker. Show camera or photo
  capture where supported, with a file-picker fallback on denial or failure.
- Desktop can offer file drop and image/file paste where supported. Keep upload
  reachable through a labeled button, keyboard and touch.
- Detect actual input/browser capabilities. Use responsive breakpoints for
  placement and spacing; screen width or user-agent guesses alone must not decide
  whether someone has a camera or can upload. Do not request camera access on load.
- Show only working ingestion actions. Forwarded email and Gmail do not appear
  as usable controls before their integrations exist. WhatsApp setup is a linked
  intake method, not an invented local file-picker capability.
- Save attachment state independently of unsent chat text. Attaching a file must
  not silently send the message, consent to AI or approve an expense. Navigating
  between inbox, overview and chat must preserve the intended destination.
- Test narrow desktop windows, touch laptops, mobile Safari, permission denial,
  picker cancellation and unsupported camera capture, not only phone/desktop
  user-agent presets.

## Complete both intake paths

### Web upload and review

- Accept the existing bounded PDF, JPEG and PNG contract first. State supported
  formats and limits before upload. Assess iPhone photo formats and either safely
  normalize them or give an actionable unsupported-format message.
- Save source and draft before preparation. A capture can succeed while AI is
  unavailable or consent is declined. Do not describe a draft as a saved expense.
- Show original source and editable merchant, date, amount, currency, category
  and destination account. Keep useful line items, tax, service and tip when
  supported by the receipt. Unknown fields stay unknown until corrected.
- Correcting a proposal does not rewrite the original extraction evidence.
  Distinguish proposal edits from edits to an already confirmed expense.
- Use the existing canonical approval/posting service. One receipt total creates
  one purchase, not separate purchases for its total and each line item.
- Allow review later, retry after recoverable failure, and removal under the
  existing source-retention and financial-history rules. Never erase confirmed
  money merely because an intake connector is disconnected.
- If the receipt does not establish payment, do not infer a paid expense or
  balance movement. Ask for the missing fact using the canonical money contract.

### WhatsApp receipt intake

WhatsApp and web upload are both part of the first pilot. Forwarded email follows
next; connected read-only Gmail follows forwarded email. Neither email path is
an implementation requirement here.

Use Meta's official Cloud API. During development use its test business number
and approved testers, including the founder's personal WhatsApp as a sender.
Do not migrate the founder's personal number into a business sender. The company
number is pending. Confirm test resources in the actual Meta account before
claiming availability. Do not buy a number or subscribe to another provider.

The narrow pilot proposal is receipt intake plus a receipt acknowledgement and
an authenticated web review link. Correction and expense approval happen in the
web app. The founder has not separately selected WhatsApp conversational review;
show this boundary in the first assessment instead of silently expanding it.

The implementation contract must cover:

- Verified linking of a WhatsApp sender to one signed-in Business owner and
  destination. A phone number supplied in text is not proof of ownership.
- Unknown or disconnected senders, relinking and revocation. Never guess an
  owner from a filename, forwarded sender name or document content.
- Webhook verification and signature validation, bounded media download from
  trusted provider endpoints, type/size validation, and privacy-safe logs.
- Durable receipt of the delivery before acknowledging it. Replay of the same
  provider message must converge on the original draft and confirmation result.
- Cross-channel duplicate handling. Exact bytes can be recognized; WhatsApp can
  transform an image, so receipt similarity needs review instead of silent
  deletion. Different legitimate purchases must remain distinguishable.
- Explicit AI consent scoped to the linked owner. Sending a document alone must
  not become implicit consent to an unapproved model provider.
- Acknowledgement only after durable capture, failures that can be recovered,
  and owner-scoped review links that disclose no financial data to another user.
- Outbound acknowledgement rules, provider limits and any template/cost needs.
  Do not assume unrestricted outbound messaging.

A public HTTPS callback is needed for real delivery. Prepare a bounded temporary
local tunnel or existing approved endpoint for founder review. Do not expose
local services, send real messages or create hosted resources in this scope PR.
The final real test must use a synthetic receipt and an explicitly approved test
sender. Replay fixtures prove code behavior, not actual WhatsApp connectivity.

## Keep one record and one set of permissions

The assessment must name owners for these concepts before implementation:

| Concept | Required contract |
| --- | --- |
| Business context | Explicit owner/business/account authorization, independent of visual navigation and consumer household grants. Assess #819 before choosing schema. |
| Intake delivery | Source channel, provider delivery identity where applicable, owner, Business destination and linked document identity. |
| Retained source | Private object reference, MIME type, size and fingerprint, authorized retrieval and deletion. |
| Document draft | Existing durable identity, preparation status, version, consent, extracted evidence and editable proposal. |
| Confirmation | Existing review event, stable idempotency key and canonical financial activity link. Retry and concurrent confirmation cannot post twice. |
| Search/overview/AI | Read the same confirmed records and authorization context; drafts and failed imports are explicitly distinct. |

These are requirements for an assessed contract, not instructions to create six
new tables. Extend canonical owners only where the existing shape cannot express
the approved behavior. Do not create a second ledger or a second approval state.

Private Storage work in #778 is a real enablement dependency. Current source
bytes live in Postgres. Coordinate ownership and complete private object storage,
source retrieval and cleanup before enabling receipt ingestion for the pilot.

Preparation currently uses FastAPI BackgroundTasks. Persisted drafts do not prove
that a process restart will finish a job. Reuse the existing job direction and
coordinate #823/#826 to define durable dispatch, bounded retries, restart recovery
and stale-result rejection. Do not introduce another worker platform by default.
A closed browser must not cancel accepted intake. Provider timeouts with uncertain
outcomes must not trigger unbounded duplicate spend.

## Connect a bounded built-in assistant

Cuadrao provides its own AI by default. Preserve the existing LangGraph runtime,
conversation persistence, streaming and grounded calculations. The initial
Business job is read-only expense Q&A, for example "What did I spend this month?"
and "Show the receipt for this expense."

- Read authorized Business records through a typed tool/service contract.
- Compute totals deterministically with period, currency and recorded coverage.
- Link answers to actual expenses and their source where available.
- Make missing data and unavailable capabilities explicit. Do not answer from
  mock balances, marketing examples or a model's recollection of money.
- Recheck permissions on tool reads and source links. A changed conversation
  context cannot grant access to Personal or Household records.
- Treat receipt text and attachments as untrusted data, never instructions.
- Do not add autonomous writes, background agents, generic RAG, memory changes,
  voice or a parallel interpreter. Model-facing changes require the repository's
  applicable scorecard/evaluation gates and separately bounded live spend.

The wider approved direction includes connecting an owner's external AI through
MCP, similar to [Midday's connection flow](https://midday.ai/mcp/chatgpt/).
That lets the external AI use authorized Cuadrao tools. It does not mean a user's
ChatGPT subscription powers Cuadrao's composer. External MCP/OAuth and customer
API-key support are deferred follow-ups. Preserve reusable tool boundaries now;
do not implement an MCP server or token store in this slice.

## Inspect these existing owners first

| Existing path | Observation at the planning base | Assessment needed |
| --- | --- | --- |
| `web/components/sidebar/SidebarShell.tsx`, `ChatSidebar.tsx`, `ProfileMenu.tsx`, `profileMenuPlacement.ts` | Existing navigation/profile components. | Reuse shell with desktop-only profile relocation; preserve mobile and guest behavior. |
| `web/components/chat/ChatInterface.tsx`, `ChatInput.tsx` | Chat owns substantial conversation/composer state. | Extract only necessary shared layout seams; do not copy the whole chat brain into Business. |
| `web/components/sidebar/ChatCommandPalette.tsx`, `command-palette/`, `RecentsQuickPeek.tsx` | Existing search/dossier/recents UI. | Extend typed results and routing without leaking context or dropping existing history. |
| `src/argus/api/routers/financial_documents.py`, `src/argus/api/documents.py` | Registered-owner, gated upload/list/read/source/proposal/prepare paths. | Connect Business UI and adapter; current upload schedules process-local background work. |
| `src/argus/domain/ingestion/documents/` | Source/draft persistence, receipt structure and extraction/preparation. | Business ownership, Storage, transport provenance and restart recovery. |
| `src/argus/domain/ingestion/reconcile/` | Import observations, duplicate handling and canonical recording boundary. | Trace reviewed receipt edits through exactly-once posting; confirm cross-channel behavior. |
| `src/argus/domain/recording/` | Canonical money/account owners. | Prove Business context, account selection, correction and balance effects. |
| `src/argus/domain/financial_search.py`, `src/argus/api/routers/financial_search.py` | Typed financial search includes accounts and activities; document is not currently a hit kind. | Add source/draft retrieval to the existing search contract where required. |
| `tests/ingestion/`, `tests/test_document_extractions_postgres.py`, `tests/test_ingestion_reconcile_postgres.py`, `tests/test_financial_search_postgres.py` | Focused existing verification entry points. | Extend realistic fixtures and real Postgres evidence; do not duplicate every test. |

The existing marketing Business guide owns website presentation, not this app's
availability. No WhatsApp adapter was verified in this scoped read. Claude must
search before claiming it is absent or creating one.

## Work in this order with one accountable lane

1. Fetch remote integration. Record its SHA and assess this brief against code,
   open PRs and #778, #819, #823, #824, #826, #827 and #828. Return a short
   reuse/build/conflict table, concrete API/data/job contracts, file ownership,
   and any genuine founder decisions. Continue independent local work.
2. Show the founder a local desktop and phone preview using the existing shell.
   Agree overview, inbox, review and chat navigation. Clearly label fixture data.
   UI approval is not proof of the connected flow.
3. Complete web upload through review, canonical save, retrieval and overview on
   local real services. Include minimal Business account setup or selection so
   the journey does not depend on manually editing the database.
4. Connect WhatsApp to that same pipeline. Prove identity binding, replay and
   recovery locally, then run the authorized real test-number journey.
5. Connect the bounded built-in expense Q&A and record links. Preserve existing
   chat/history and run the applicable regression and live evaluation gates.
6. Reconcile current integration, review the whole slice and deliver durable
   evidence. Prepare the separate activation packet with actual configuration,
   remaining provider inputs, cost, rollback and hosted smoke plan.

These are work ordering steps within one slice, not isolated frontend/backend
projects or long-lived incubation branches. Claude may propose small integration
PRs with unfinished functionality default-off. Do not mark the pilot complete
until all required connected journeys pass.

## Verify the complete slice

| Scenario | Required evidence |
| --- | --- |
| Upload/save/return | Real API and local Postgres/Storage; source and draft survive reload, reviewed expense appears once, search opens it and its source. |
| WhatsApp/save/return | Approved real test sender and synthetic photo or PDF; acknowledgement, web review, canonical save and later retrieval. Record provider mode separately from fixture tests. |
| Duplicate delivery | Replay provider event, repeat upload, deliver same receipt across channels, double-click approval and retry after lost response. Show one financial effect and explain uncertain near-duplicates. |
| Correction | Correct merchant/date/category/amount/currency/account before save; stale revision cannot overwrite newer review. Explicit correction after save uses canonical money behavior. |
| Missing data | Unreadable receipt, unknown currency, ambiguous payment, unsupported file and absent account produce recoverable states without invented money. |
| Failure/restart | Declined AI consent, provider failure, expired media, disconnected sender, worker interruption and browser close preserve valid saved state; retry remains bounded. |
| Isolation | Two owners plus Personal/Household context; forged webhook, unknown sender and direct draft/source/search/tool access cannot cross boundaries. |
| Overview and AI | Totals match saved expenses for the selected period/currency; drafts excluded; AI sources resolve and deleted/inaccessible records do not leak. |
| UI regression | Desktop and phone widths, English/Spanish, keyboard/focus/touch; composer draft survives navigation; existing chat, search, Recents and profile behavior remain intact. |
| Retention | Source removal/disconnect/account deletion removes private stored objects as required without silently rewriting confirmed financial history. |

Use focused tests plus actual browser journeys. Record manual-entry baseline and
receipt-assisted active review time, correction count and completion rate on
realistic labeled synthetic receipts. Measure capture acknowledgement and review
loading on the target environment. Agree numerical budgets in the assessment;
this planning PR does not invent performance results or require broad load tests.

Store exact-head screenshots, test logs and acceptance results under
`docs/reports/evidence/cuadrao-business-owner-pilot/` or durable GitHub attachments.
Record original/current integration base, reconciliation merge, semantic overlap,
PR head, CI and review result. Local mock-provider success is not provider proof;
local real-service success is not hosted pilot acceptance.

## Coordinate without blocking unrelated lanes

- Consumer owns iOS #877/#899 and its release candidate. Business does not edit
  `ios/`, alter consumer navigation, or reopen guest/pricing/household decisions.
- Marketing owns #880/#895 and `marketing/` extraction, forms, DNS and Resend.
  Assess work against that extraction before editing the web shell. Do not pull
  website code back into the application or alter its release candidate.
- #778 private source storage and #823 document jobs are shared dependencies.
  Confirm one active writer for each contract. Reuse existing issues rather than
  launching a competing storage, consent or job implementation.
- #819 owns space migration; #824 search; #826/#827 conversational runtime;
  #828 AI consent. Business proposes narrow extensions with their owners and
  retains the existing interpreter until an approved contract changes it.
- Schema additions use a coordinated migration order. No `db push` to the live
  project, backdating to bypass a gate, ledger repair or gate-pin changes here.
- Supabase stays Free; Docker is the development/rehearsal environment. No new
  hosted staging, automatic preview branch, subscription or service purchase.
  Check GitHub/Supabase automatic behavior before publishing migration PRs.

## Approval and completion boundaries

The assigned Claude owner can perform local implementation, tests, PR edits and
review follow-up. It drives landing preparation and the repository landing
workflow after the authorized merge. Founder merge authority remains unless the
founder explicitly delegates bounded integration merges when assigning the lane.
No promotion to main, deployment, DNS, live migration, provider activation,
credential creation, message sending or paid run is granted by this scope PR.

Before live extraction tests, propose provider, fixtures, attempt limits and
maximum spend. Before real WhatsApp delivery, identify the test sender, callback,
synthetic receipt and acknowledgement. Batch required founder inputs once the
concrete setup is ready. Company-number activation is needed for public pilot
availability; test-number proof can precede company approval.

Finish with separate statements for implemented, locally verified,
provider-verified and hosted-enabled. Record concrete blockers instead of calling
a default-off or mock-only implementation a launched Business product.
