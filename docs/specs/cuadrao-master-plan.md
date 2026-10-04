# Cuadrao master plan: execution roadmap

**Status:** Planning roadmap, drafted October 4, 2026 (CT). It merges the product half by the Product Lead (Iris) and the engineering half by the Head of Engineering (Yelena), and the docs seat (Maya) assembled it. It is not an authority over the [MVEE](argus-minimum-viable-ecosystem-experience.md), the [execution board](argus-execution-board.md) or the [decision log](argus-decision-log.md). Nothing here authorizes a merge, deploy, migration, hosted flag, paid provider or new runtime work. The Oct 4 mobile roadmap lock in [#813](https://github.com/lagarcess/argus/pull/813) is the delivery checkpoint, and the execution board keeps delivery authority. Founder locks live in the decision log; this plan links to them instead of restating them as new decisions.

**Sources:** Lucas's two October 4 documents, recorded verbatim as [go to market vision](../research/2026-10-04-cuadrao-gtm-vision-source.md) (cited as **GTM**) and [product and business architecture](../research/2026-10-04-cuadrao-product-business-architecture-source.md) (cited as **Blueprint**). Repo facts were read on integration `codex/private-alpha-next` at `a8c37d3a` (Oct 3, 6:09 AM CT). Open issues and PRs are as of October 4.

**Related open PRs:** [#813](https://github.com/lagarcess/argus/pull/813) (draft, execution board Oct 4 roadmap lock) and [#808](https://github.com/lagarcess/argus/pull/808) (profile hidden rows backend; touches the decision log, MVEE, board, handoff, FK census, `DATA_MODEL.md` and `API_CONTRACT.md`). This plan doesn't edit the execution board.

## How to read this plan

- **Labels.** **[fact]** comes from the repo, GitHub or a cited source. **[proposed]** is a recommendation that still needs a lock. **[estimate]** is a rough size, not a commitment. "For Lucas to lock" marks a proposal waiting on the founder. "Unverified" marks a claim nobody re-checked, including the PSFE requirements and e-CF signing details taken from the Blueprint.
- **Parts.** [Part A](#part-a-product) is Iris's product half and [Part B](#part-b-engineering) is Yelena's engineering half, kept close to how each author wrote them. Section references inside each part use that part's letter: §A3 is the pillar table, §B2 is the space model. Notes marked **Maya's note** are the docs seat's, not the authors'.
- **Where the halves disagree,** [the conflict table](#where-the-two-halves-disagree) lists each case with a suggested resolution. Where the plan combines product and engineering content, engineering detail follows Part B.
- **Where the plan disagrees with repo canon,** [the canon table](#conflicts-with-repo-canon) lists it. The canon docs are not edited here; the [side-track checklist](#side-track-checklist) holds the follow-ups.

## Locked on October 4

Lucas set the launch shape in the room on October 4 at 12:30 PM CT. The [decision log entry](argus-decision-log.md#october-4-2026-cuadrao-launch-shape) is the record; in short:

1. **Consumer iPhone app:** personal and household only. A short invite-only TestFlight under the existing October 2 invite rules, then a public launch and fast iteration.
2. **Cuadrao for Business:** the full service is on the web. The business space in the iPhone app stays thin (capture, quick approvals, where money stands) and goes only to the first business testers on TestFlight. Public consumers never see it. How to keep it out of the public build is the Head of Engineering's call; her decision is Option C in §B3.4.
3. **cuadrao.ai** promotes the whole suite and carries the waitlists.
4. **Stack:** stays on Resend, Render and Supabase.

**Fiscal route correction (Lucas, Oct 4, 12:39 PM CT, recorded in Yelena's engineering notes):** partner first. Connecting to a DGII-certified provider (PSFE) is the fastest route to a full business service and to live invoicing through Cuadrao. Cuadrao's own DGII backend is the parallel track while Lucas handles the DGII paperwork. The pilot starts by tracking the invoices owners already issue, then issues through Cuadrao once the provider connection is live. Choosing the provider is part of Lucas's partner track. The Blueprint names Alanube and Alegra as references; no provider is chosen.

**Lucas's further Oct 4 calls (about 12:44 PM CT, relayed by Iris):**

1. **Plaid is kept,** not an open decision. The Plaid sandbox plus Faker-generated data is how the team stress-tests financial data. Real Plaid serves Dominicans in the US and Dominicans with accounts abroad. Manual entry stays available for anything Plaid doesn't cover. Production Plaid access needs Plaid's application and security review; that's a light partner step on Lucas's founder track, next to the US entity, not a blocker.
2. **Dominicans in the US** is a named consumer segment. This is Lucas's Oct 4 addition next to the locked first users (people living in the Dominican Republic); it doesn't replace the DR-first lock. See [canon row 11](#conflicts-with-repo-canon).
3. **Market-data providers are parked for the pilot, not deleted:** Alpaca, Kraken, BCRD and the other market-data providers. Their keys come out of the live setup and the code stays. Perplexity covers general finance questions in chat. **Open check:** if any screen totals peso and dollar accounts together, Cuadrao needs one dependable exchange-rate source, and Perplexity must never supply numbers that get stored. Yelena is checking whether anything converts currencies today.
4. **Gmail import stays an open decision.**

The rest of this plan is proposals. F1 to F5 in §A7 and the questions in §B9 stay open.

## Roadmap at a glance

This summary combines both halves. Sizes are Yelena's estimates (§B6). Order inside each stream is a proposal.

| Stream | What it delivers | First step | Waits on |
| --- | --- | --- | --- |
| **Consumer TestFlight** (personal + household, iOS) | The connected candidate from #813 in invite-only TestFlight, then public | The must-do issues in §B7 and the minimum in §A4 | Apple team and bundle id (§B3.2), cuadrao.ai DNS, email and AASA |
| **Shared foundation** | Space and membership model (§B2), entitlement service (§B5), scoped storage (#778), audit and approvals | Space model steps 1-2 (§B2.3) for personal and household | Lucas's lock on §B2 |
| **Business ledger** (web first, thin app space for pilots) | Web shell, roles, money and ops, Inbox and Vault, customers, non-fiscal invoices, external e-CF tracking, matching, accountant export | Space model step 4, then the web shell | Roles matrix lock; about 12-18 eng-weeks [estimate] |
| **Fiscal: certified-provider bridge** (partner first) | Live e-invoicing through Cuadrao via a PSFE | Adapter against the provider's sandbox, behind the shared fiscal-backend interface | A PSFE agreement (Lucas's partner track); about 3-5 eng-weeks [estimate], the first fiscal work |
| **Fiscal: own backend** (parallel, lower priority) | Offline e-CF XML builder, validator, sequencing, submission state machine, evidence store, Cuadrao DGII MCP | Offline build against DGII's published specs | Lucas's DGII paperwork; about 6-10 eng-weeks [estimate] |
| **Brand and domain** | `ai.cuadrao.app`, cuadrao.ai web, API host, AASA, email domain, redirects | Entity and Apple team choice (§B3.2 step 0) | F3 |
| **Founder tracks** | Entity, Apple enrollment, PSFE partner, Plaid production access, pilot recruitment, DGII answer | See §A5 | Lucas |

**What runs in sequence:** the space model before any business data exists; the invoice record and its fiscal-state fields locked before the fiscal streams touch the ledger; no compliance promise to a customer before a live issuance route exists; own PSFE status after at least three pilot issuers.

**Issue placement for #686 and #694:** both are must-dos at the time of the next integration-to-`main` promotion, not TestFlight blockers. Any promotion that carries #674 applies its migration and env keys first (#686), and the forged-header check runs in that promotion window (#694). This matches Yelena's reasoning in §B7 and Iris's deferral in §A6.

## Where the two halves disagree

Each row names the sections, what each half says, and a suggested resolution. None of these resolutions is a lock unless the row says so.

| # | Topic | Product (Part A) | Engineering (Part B) | Suggested resolution |
| --- | --- | --- | --- | --- |
| 1 | **e-CF route** | §A7 contradiction 1 withdraws "partner first" and adopts the Blueprint: own fiscal backend and DGII MCP as the goal, a certified provider only as an optional fallback. §A5 (b) calls the bridge optional. | §B6 and the fiscal route line: partner first, per Lucas's 12:39 PM CT correction. The bridge is the route to live invoicing and the first fiscal work; own backend runs in parallel at lower priority. | **Resolved by Lucas's correction:** partner first. Iris to update contradiction 1 and §A5 (b). F2's remaining question is timing (see row 2). |
| 2 | **F2 and pillar order for fiscal work** | §A3 lists pillar 7 (own offline fiscal tooling) above pillar 9 (live issuance, "optionally" via a PSFE). F2 recommends tracking over bridging for pilots before Nov 15. | Tracking externally issued e-CF is the first pilot step; issuance moves to the provider bridge once live. Own backend replaces the provider later. | Compatible on tracking first. Keep F2 open on whether live e-CF is in the first business release. Iris to re-check pillars 7 and 9 against the partner-first order. |
| 3 | **Keeping business out of the public build** | §A4: Yelena is comparing a server switch and a separate TestFlight build; product defers. | §B3.4: Option C, compile-time `CUADRAO_BUSINESS` build plus server authorization. Server-only gating is ruled out for App Store builds. | Follow §B3.4. It's the Head of Engineering's decision under lock 2. |
| 4 | **Business role presets** | §A2 and pillar 1: three presets (owner, associate, accountant). | §B2.2: owner, admin, bookkeeper, approver, accountant, viewer, plus a separate billing admin flag. | Lucas locks the roles matrix (§B6 "needs Lucas's matrix lock"). Suggest Iris's three presets as the starting UI, mapped onto Yelena's permission roles. |
| 5 | **Space model and consumer TestFlight** | §A4's TestFlight minimum doesn't include the space-model migration; §A3 runs pillar 1 alongside pillar 2. Pillar 1's first slice includes a business space. | §B2.3: steps 1-3 are cheapest before external TestFlight; consumer TestFlight needs steps 1-2. The business kind comes last (step 4) and is web first. | Not a TestFlight blocker unless Lucas says so. Schedule steps 1-2 before production holds tester data where possible; the business space follows step 4. |
| 6 | **#686, #694** | §A6: keep deferred; un-defer #686 if Argus web stays live (F5). | §B7: listed under consumer TestFlight because the TestFlight API is `argus-api` on `main`. | **Settled by steering:** must-dos at main-promotion time, not TestFlight blockers. |
| 7 | **#807 scope** | §A6: item 15 and alerting, "before an external beta" per the issue. | §B7: item 15 for TestFlight; items 3 (alerting) and 5 (per-worker limiter) before public launch. | Item 15 before TestFlight. Ask Yelena whether alerting moves up to match the issue's "before an external beta". |
| 8 | **#671, #676** | §A6: keep deferred; moot if arguschat.ai redirects. Un-defer #676 if Argus web stays live. | §B7: before public launch. The iOS app relies on web password recovery (#676) and the limiters scale with workers (#671). | Follow §B7. Both apply to the Cuadrao surfaces whatever F5 decides. |
| 9 | **#684, #685** | §A6: keep deferred; un-defer if Argus web stays live. | §B7: archive when guest flow and backtests retire; until then they matter on arguschat.ai. | Compatible. Tie both to the F5 answer. |
| 10 | **#803, #804** | §A6: keep deferred; fold #804's worker-count check into #807. | §B7: before public launch. §B3.2 cites #803 for the cost of an Apple team change. | Before public launch, with #804's worker-count check folded into #807. |
| 11 | **#700, #656** | §A6: keep deferred; re-check against the chat runtime assignment. | §B7: before public launch (#700 if the Cuadrao agent reuses the chat turn path; #656 because calculations stay). | Re-check when the agentic runtime assignment is scoped; if the chat path is reused, before public launch. |
| 12 | **#690** | §A6: keep deferred (live Argus web security). | §B7: re-scope to the business, agent and file surfaces before real business data. | Follow §B7 for business pilots. |
| 13 | **Archive vs keep deferred** (#640, #606, #644, #653, #623, #620, #696) | §A6: keep deferred; re-check against chat runtime. | §B7: archive or close as obsolete after the pivot. | Lucas or Iris confirm before any closure. |
| 14 | **Android** | §A2: partial, "iPhone first, Android after". | §B1.1: park; no Android release is committed (GTM p.5). | Park. It also conflicts with canon (canon row 7). |
| 15 | **Guest flow** | §A6 lists guest issues as live-web security. | §B1.1: drop from Cuadrao; delete with the chat retirement. | Engineering call for Cuadrao surfaces; deleting it needs F5 and conflicts with canon (canon row 6). |
| 16 | **WhatsApp intake access** | §A3 pillar 3: "no access" (Meta business account is platform onboarding). | §B6: "1-away" (Meta WhatsApp Business Platform). | Wording only; both say no regulator. Use "1-away". |
| 17 | **Revenue: one RevenueCat entitlement** | §A5 recommends IAP plus web on one RevenueCat entitlement; lists Lemon Squeezy for a DR-only entity. | §B5: the server entitlement table is the source of truth; RevenueCat has no Lemon Squeezy integration, so on a DR entity the API is the only reconciler. | Server table as source of truth; RevenueCat feeds it. F4 stays open. |
| 18 | **`GUEST_PUBLIC_LAUNCH_SAFETY.md`** | §A6: update during the domain move. | §B8: archive with the guest flow and web chat retirement, not before. | Update domain references during the move; archive when the guest flow retires. |
| 19 | **Execution board size** | §A6: shrink it; move pre-October sections to `docs/archive/`. | §B8: keep it (#813 section). | Out of scope here: this plan doesn't edit the board, and #813, #808 and #790 all touch it. Revisit after they land. |
| 20 | **Staging and sole-owner deletion** | Not covered. | §B4 and §B9 questions 2-3. | Add to Lucas's open questions (done in §B9). |
| 21 | **Plaid** | §A2: Plaid sandbox listed under imports and connectors as partial; no DR bank feeds. | §B1.1: salvage; Plaid is US-only with no Dominican coverage. §B6: "Gated for DR users", "Keep only for foreign accounts". | **Settled by Lucas's 12:44 PM CT call:** keep Plaid. Sandbox plus Faker data for stress tests; real Plaid for Dominicans in the US and accounts abroad; manual entry for the rest. Production access is a founder-track partner step. |
| 22 | **Market-data providers** | Not covered. | §B1.1: salvage the chat and calculations selectively; `market_data` is part of the Argus-era code. No call on provider keys. | **Settled by Lucas's call:** parked for the pilot. Keys come out of the live setup; code stays; Perplexity covers general finance questions. Exchange-rate source is an open check. |
| 23 | **Gmail import** | §A2: partial (foundation, not enabled). | §B6: "1-away" (Google OAuth verification and annual security assessment). | **Lucas's call:** stays an open decision. |

**Maya's note on the product half:** I was told that Iris sent corrections to the product half. I didn't receive them, and the product half used here is the version dated October 4 (last changed 12:34 PM CT). Part A is that version, with three edits for the public repo: the prospect-list file path is removed, the box file paths for the sources now point to the committed source records, and notes mark where Lucas's fiscal correction and Yelena's §B3.4 decision supersede the text.

## Conflicts with repo canon

These canon passages conflict with the October 4 sources, the locks above or the plan. None of them is edited in this PR. Each needs a founder lock or a docs rewrite, listed in the [side-track checklist](#side-track-checklist).

| # | Canon | What it says | What conflicts | Suggested follow-up |
| --- | --- | --- | --- | --- |
| 1 | [Decision log](argus-decision-log.md#locked), 2026-09-28 (clarified 2026-09-29) | "Revenue, pricing, paywalls and billing remain deferred." | GTM "What we have decided": "Both products can earn revenue." §A3 pillar 8 and §B5 plan entitlements and billing in sandbox. | Lucas confirms a decision-log entry that lifts the deferral for revenue direction while prices stay open. Then update [DOCUMENTATION_AUTHORITY](../DOCUMENTATION_AUTHORITY.md#founder-deferral). |
| 2 | Decision log, 2026-09-24 | "Argus keeps all its existing grounded chat and calculation capability." | §B1.1 drops the web chat UI and retires backtests; §A6 retires backtest and quant research as the product center. Calculations and grounding are kept. | Lucas confirms what "keeps" now covers (calculations and grounding yes; web chat UI and backtests retire). |
| 3 | Decision log, 2026-09-26; [DOCUMENTATION_AUTHORITY](../DOCUMENTATION_AUTHORITY.md) | "Preserve Argus visual identity"; the authority doc says the product "retains the Argus visual identity". | Cuadrao brand, design graft (#783/#785/#786/#792) and the cuadrao.ai cutover (§B3). | Rewrite the authority doc for Cuadrao (§B8) after a decision-log entry on the brand. |
| 4 | [MVEE](argus-minimum-viable-ecosystem-experience.md#financial-spaces) "Financial spaces" | Business is a named private space and "does not imply employees, payroll, invoicing or tax accounting". | Premium business with roles, invoices and e-CF (GTM, Blueprint, §A2, §B6). | Iris's resolution (§A7 contradiction 2): the MVEE limit becomes the consumer release scope; business gets its own spec. |
| 5 | [MVEE §1.6](argus-minimum-viable-ecosystem-experience.md#16-holds-later-work-and-unresolved-decisions) and DOCUMENTATION_AUTHORITY | "Web remake: frozen"; "replacing web with a landing page is not decided". | Lock 2 (full business service on web) and lock 3 (cuadrao.ai landing page with waitlists). | Iris's resolution (§A7 contradiction 3): the freeze covers the Argus consumer web. Amend §1.6 after the decision-log entry. |
| 6 | MVEE "Guest access and registration" (locked guest boundary) | A locked guest access boundary. | §B1.1 and §B1.3 drop the guest flow from Cuadrao and delete it with the chat retirement. | Ties to F5. Needs a founder lock before deleting guest code. |
| 7 | Decision log, 2026-09-26; MVEE §1.6 | Native iOS and Android plus web intent; Android "remains an intended native product"; "retain the existing web/PWA stack". | §B1.1 parks Android; GTM gives no Android date; F5 may retire arguschat.ai web. | Compatible if "park" means not scheduled. Record when F5 is answered. |
| 8 | [MVEE §1.4](argus-minimum-viable-ecosystem-experience.md#14-infrastructure-and-cost-constraints) | Reuse Render and the existing Supabase project on the current plan; preserve existing chats, research and backtests. | Lock 4 agrees on the stack. §B4 and §B9 question 2 ask whether to reopen §1.4 for a staging project; §B1.4 names a fresh project as a flip condition. | Stays locked unless Lucas answers §B9 question 2 otherwise. |
| 9 | [PRODUCT.md](../PRODUCT.md) | Argus product overview, approved September 26. | One Cuadrao with three contexts (GTM, §A1). | Rewrite for Cuadrao (§B8). |
| 10 | MVEE §1.2 private iPhone delivery | Private physical-iPhone delivery as the immediate finish line. | Lock 1: invite-only TestFlight, then a public launch. | Superseded in direction by lock 1; amend the MVEE when the board's next checkpoint lands. |
| 11 | [Decision log](argus-decision-log.md#locked), 2026-09-24 | "The first user is people living in the Dominican Republic, not the diaspora." | Lucas's Oct 4 addition of Dominicans in the US as a named consumer segment, served by real Plaid. | Lucas confirms a decision-log entry that adds the segment next to the DR-first lock without replacing it. |

## Side-track checklist

These run beside the main streams. Each item names an owner where one is known. Docs that conflict with the plan are not edited until the conflict is resolved by a lock.

**Docs pass** (Maya; combines §A6 and §B8 where they agree)
- [ ] Archive the Argus-era specs both halves list: `docs/specs/private-alpha-next-*` (roadmap, decision memo, p2.1 audit, refine-to-version, chat header title, conversational-edit contract), `docs/specs/wave-1/`, `graded-interpretation-routing.md`, `evidence-aware-idea-loop.md`, `conversation-sharing.md`, and the pointer stubs `argus-active-roadmap.md`, `argus-grounded-finance-roadmap.md`, `argus-pivot-strategy.md`, `argus-answers-that-stay-true-roadmap.md`. Check inbound links first. Proposed as a separate docs-cleanup PR.
- [ ] Archive `docs/superpowers/` (agent working notes, 146 files) in the same cleanup PR, after checking inbound links.
- [ ] Hold until the guest flow and web chat retire: `docs/GUEST_PUBLIC_LAUNCH_SAFETY.md`, `docs/QA_CONVERSATIONAL_TRANSCRIPTS.md`, `docs/BREAKPOINTS.md`, `.agent/designs/argus/DESIGN.md`. Update domain references in `GUEST_PUBLIC_LAUNCH_SAFETY.md` during the domain move (conflict row 18).
- [ ] Rewrite for Cuadrao after the canon locks: `DOCUMENTATION_AUTHORITY.md`, `PRODUCT.md`, MVEE "Financial spaces" and §1.6 (canon rows 1-5, 9).
- [ ] New docs once locked: the space and ownership spec (§B2), a business spec or business MVEE section (§A7 contradiction 2), and `docs/CUADRAO_CODE_MAP.md` (§B1.3).
- [ ] Update during the domain move: `PRIVATE_LAUNCH_RUNBOOK.md` (email records, canary inbox), `docs/release-manifests/`, `ios/*.md` setup docs.
- [ ] Evidence size: consider moving dated `docs/reports/evidence/` files (about 4,950, 2,195 of them PNGs) out of the main tree while keeping links. Start from `docs/maintenance/docs-classification-inventory.md`.
- [ ] Execution board: no edits until #813, #808 and #790 land; #813 and #808 each conflict with #790 in the board (§B8).

**Founder locks to record** (Lucas; Maya records them in the decision log once confirmed)
- [ ] Space and membership model, roles matrix and business retention rule (§B2, conflict row 4).
- [ ] Revenue direction lifted from "deferred", prices still open (canon row 1).
- [ ] Cuadrao brand replacing the Argus visual identity (canon row 3).
- [ ] Business scope beyond the MVEE private Business space (canon row 4).
- [ ] Web freeze scope and the landing page (canon row 5).
- [ ] Dominicans in the US as a named consumer segment, next to the DR-first lock (canon row 11).
- [ ] Gmail import: ship or not (Lucas's Oct 4 call keeps it open).
- [ ] F1 to F5 (§A7) and §B9 questions 1-4.

**Open engineering checks** (Yelena)
- [ ] Does anything convert currencies today? If any screen totals peso and dollar accounts, pick one dependable exchange-rate source. Perplexity never supplies stored numbers.
- [ ] Take the market-data provider keys (Alpaca, Kraken, BCRD and the others) out of the live setup; keep the code.

**Issues** (Yelena files the business issues after the space-model lock)
- [ ] File issues for space model steps 1-4, roles and permissions, audit log, entitlement service, business Inbox/Vault, thin app space and its release-check CI, the certified-provider bridge adapter, and the offline fiscal backend.
- [ ] Confirm closure or archiving for #640, #606, #644, #653, #623, #620, #696 (conflict row 13).

**Founder tracks** (Lucas)
- [ ] Entity (US, DR or both) and Apple organization enrollment before the first external build (F3, §B3.2 step 0).
- [ ] PSFE partner choice for the bridge (fiscal route correction).
- [ ] Plaid production access: Plaid's application and security review. A light partner step next to the US entity, not a blocker.
- [ ] DGII answer on a foreign, non-certified software provider (pending per the Blueprint).
- [ ] First business segment and who recruits about 10 pilot owners (F1).
- [ ] Argus web during the transition (F5).

---

## Part A: Product

**Author:** Iris (Product Lead). **Date:** October 4, 2026. **Status:** Draft for Lucas to lock. This is direction, not a list of shipped features. "Exists" means code is on integration `a8c37d3a` or in an open PR, usually behind a default-off switch. It does not mean the feature is live.

**Sources:** Lucas's Oct 4 GTM and Blueprint (now recorded in `docs/research/`, see §A7); PR #813 (Oct 4 roadmap lock); PRs #790, #808, #809, #810, #812, #781; the MVEE, the decision log and DOCUMENTATION_AUTHORITY on integration; open issues as of Oct 4. Outside facts are cited at the end of this part.


### A1. Vision

Cuadrao is **one product with three contexts: personal, household and business.** A person has one identity and joins spaces. Personal is private by default. Household shares only what members choose to share, and each member keeps their own finances. Business is a premium workspace with its own records, collaborators and workflows. A business role gives no access to anyone's personal or household space, and any combined view follows each space's permissions. All three share identity, money records, documents, capture, search and authorized actions, including AI actions. That shared base is one platform and **one codebase**, delivered on two tracks.

**Why business is the stronger thesis.** Consumer money trackers compete with free spreadsheets. Many Dominican small businesses run the owner's money and the business's money as one pile, spread across WhatsApp, paper receipts, bank exports and the accountant. E-invoicing makes this urgent now. Under Ley 32-23, the last group (small, micro and unclassified taxpayers) has until **November 15, 2026**, after DGII's six-month extension in Aviso 06-26 [1][2]. That deadline gets us in the door. People keep paying because their records stay organized and ready for the accountant. Consumer still ships first: it's the product already taking shape, it lets us learn from real use, and it can also earn revenue. The Oct 4 vision dropped the idea that consumer is a free loss leader.

### A2. Product map

Tags: **[exists]** code on integration (mostly default-off) · **[partial]** foundations or UI exist, connected journey open · **[new]** not built.

#### Consumer (personal + household): iPhone first, Android after

| Subproduct | State | Grounding |
| --- | --- | --- |
| Identity and access: email, Apple and Google sign-in, invite gate, 10 beta invites, founder group link, cuadrao.ai waitlist | partial | Backend #788/#794; Apple/Google #793/#795/#802 (off, gates in #800); iOS invites in #810 (open) |
| Spaces: Personal, Household, private Business, Custom; moving accounts between spaces | partial | MVEE §1.4: "space ownership and authorization still need production contracts" |
| Accounts, activity, balance checks | exists | Account first slice, local financial loop (#735, #745) |
| Plans: budgets, goals, debt, shared plans | exists/partial | Shared household planning #773 |
| Household: membership, grants, leaving, deletion with "Exmiembro" | exists/partial | #763, #766, #788, #799, #801; frozen balance is still open (#805) |
| Capture and receipts: camera, upload, drafts, review | partial | UI #785, durable drafts #776; extraction blocked by #778 |
| Imports and connectors: statement/CSV, Plaid sandbox, Gmail, Shortcuts, review queue | partial | #768–#772 as foundations, not enabled; no DR bank feeds |
| Home, Search, Updates inbox, private push | partial | Designs #786; connected paths and push setup open (#813) |
| Ask Cuadrao (chat, then agentic actions) | partial/new | Argus runtime exists (explanations, calculations, research); Cuadrao chat design #785; agentic runtime not implemented (#813). Lucas starts chat work Oct 5 |
| Voice | new | Researched, parked |
| Profile, controls, AI consent, deletion, legal | partial | Release UI #790 (open), deletion #799/#801, Terms/Privacy draft #781 |
| Android | partial | Shell #730; accounts branch stopped |

> **Maya's note:** Lucas's Oct 4 calls keep Plaid (sandbox plus Faker data for stress tests; real Plaid for Dominicans in the US and accounts abroad), add Dominicans in the US as a named consumer segment, and leave Gmail import open. See [Locked on October 4](#locked-on-october-4).

#### Business (premium): thin in the app, full service on the web

Lucas agreed the **business space in the iPhone app stays thin**: capturing receipts and invoices, quick approvals, and checking where money stands. **The full service is the business web workspace**, so we don't build business twice. Everything below is **[new]** unless noted. Much of it reuses consumer foundations.

| Subproduct | Surface | Notes |
| --- | --- | --- |
| Business space, roles (owner, associate, accountant), invitations, leaving, ownership transfer | web + app (join/switch) | Starts from household grants; business records belong to the business (Yelena's model) |
| Personal ↔ business money moves ("paid a supplier with my personal card", "took cash from the register") | app + web | Two linked records, one in each space, never one shared record |
| Document inbox and vault: camera, upload, then WhatsApp Business forwarding | app (capture) + web (review) | Reuses capture and drafts [partial]. WhatsApp intake is planned, not built |
| Customers (light CRM) | web | Collections-focused, not a sales pipeline |
| Invoices without fiscal issuance: quotes, drafts, tracking invoices issued elsewhere, collections | web; app approves and checks | Commercial, fiscal and payment status kept separate |
| Payment matching and allocation (partial payments, fees) | web | Exact-money rules from consumer |
| Reports and accountant period package (CSV plus documents) | web | Deterministic numbers; AI only explains |
| e-CF fiscal backend and Cuadrao DGII MCP | web/backend | Blueprint goal. Live issuance is gated (§A3) |
| External assistants (API or MCP with scoped grants) | API | Later |
| Projects and time, tax preparation, tax filing | web | Optional or future; filing is separately gated |

### A3. Pillars ranked by leverage

There's no fixed order. Higher pillars unlock more of the ones below them. **No access** means no certified partner, regulator or bank is needed.

| # | Pillar | Access | Why it's high leverage | First shippable slice |
| --- | --- | --- | --- | --- |
| 1 | **Spaces and permissions foundation** | No access | Every other pillar depends on who owns a record. It's cheap to fix now while there's no real data | Yelena's ownership model locked; personal and household running on it; a business space with three role presets |
| 2 | **Consumer core loop to TestFlight** | No access | It's the product closest to done, and first-tester learning starts here | The connected candidate from #813: onboarding, accounts and activity, plans, household, sign-in, deletion |
| 3 | **Capture and document inbox** | No access (WhatsApp needs a Meta business account, which is platform onboarding, not a regulator) | Shared by consumer and business, and the main time-saver for owners | Photo or upload → draft → review → record into the chosen space |
| 4 | **Personal ↔ business separation** | No access | It's the owner's real pain and the hardest test of the space model | Two money-move actions that create linked records in each space, plus the owner's combined view |
| 5 | **Business admin without fiscal issuance** | No access | The blueprint (p.13) says business can launch before e-CF. It works for owners who already invoice through DGII's free invoicing tool or another provider | Customer → invoice draft → PDF → mark paid / match → accountant export |
| 6 | **Ask Cuadrao (agentic)** | No access (needs AI consent and a model provider) | One interface across all contexts, using the same actions and permissions as the screens | Read-only answers over the user's own space, then a proposed draft record that needs confirmation |
| 7 | **Own fiscal tooling, prepared offline** | No access to build; live use is gated | Lets us detach from partners later | e-CF XML builder and validator against DGII's published technical specs, with no live submission |
| 8 | **Revenue capture** | Gated by company entity and store agreements, not regulators | Both products can earn revenue | Paywall and entitlements in sandbox; no prices (§A5) |
| 9 | **Live e-CF issuance** | Gated by each customer's DGII issuer certification, a compliant signing route (INDOTEL-authorized trust service), and optionally a certified provider (PSFE) [3][4] | It's the regulatory way in | One pilot issuer certified through the route Lucas picks (§A7, F2) |
| 10 | **Own PSFE status** | Gated by DGII: our own RNC with software activity, e-CF issuer status, three certified customer issuers, and a full dossier [3] | Independence from providers | After at least three pilot issuers |
| 11 | Bank feeds, money movement, cards, tax filing | Gated by banks, aggregators, licenses and DGII channels | Long-term vision only | Not in this plan's first push |

**What can run in parallel:** 1 alongside 2 (separate owners); 3 and 4 once 1 is locked; 5 and 7 alongside each other on the web track; 6 starts with Lucas's chat work but its runtime design waits for its own scoped assignment (#813). **What must run in sequence:** 1 before any business data exists; 9 before any compliance promise to a customer; 10 after 9.

> **Maya's note:** the pillar table is kept as Iris wrote it. For the order of fiscal work after Lucas's partner-first correction, see [conflict rows 1-2](#where-the-two-halves-disagree) and §B6.

### A4. Path to first real testers

#### Consumer TestFlight (personal + household)

**Minimum, from #813's release gates and open issues:** one connected candidate assembled and checked on the phone (#790 → #810 → #812, then #808 and #809); onboarding end to end (install → invite code → sign-in → first useful action); connected accounts, plans and household journeys including revoking access; sign-in gates (#800, plus #798 items 2–3); deletion that actually completes (#805, #806); #811 fixed before any fresh real-user database is built; #784 Mac verification of the real candidate; #778 if receipt extraction is in the build; AI consent enforced before chat or documents send data to a model; Privacy and Terms live at cuadrao.ai (#781); privacy manifests, permission strings and accessibility; reviewer access through the invite gate. External TestFlight builds go through Beta App Review and must follow the guidelines. Testers can't be charged or paid for access (guideline 2.2) [5].

**Success signals (proposed, thresholds set after the first baseline):** time to first useful record or plan; return in week 2; household invites accepted and activated; invites sent per person and their conversion; zero money-math or cross-space leak defects; crash-free sessions; deletions that complete; support load per tester.

#### Business TestFlight + concierge

**Shape:** about 10 owners from one segment, served hands-on. The earlier research lane produced a first batch of DR small-business prospects; the list stays off the public repo. Owners use the **thin business space in the iPhone app** (capture, quick approvals, where money stands) and the **business web workspace** for everything else. The first loop runs **without live e-CF**: owners keep issuing through their current route (for example DGII's free invoicing tool [6]), and Cuadrao tracks those invoices.

**Keeping business out of the public App Store build** while it's in testing is required, because guideline 2.3.1(a) bars hidden or dormant features [5]. **Yelena is comparing two approaches and will make the recommendation:** a server switch per account, or a separate TestFlight build from the same code that includes business. The product half defers to her.

> **Maya's note:** Yelena's decision is Option C in §B3.4: a compile-time business build for TestFlight pilots plus server-side authorization.

**Minimum:** pillar 1 locked; a business space with role presets; capture into the business space; the two money-move actions; customer → invoice draft → payment matched → accountant export on the web; a written support and responsibility boundary for the concierge service.

**Success signals:** time to first completed workflow; how often the accountant accepts the export without rework; exception and unmatched rates; owner time saved; repeat use per month; support minutes per owner; willingness to pay (a stated price or a commitment, no price set by us yet).

### A5. Founder tracks running in parallel

**Institutional access.** (a) Each pilot customer's issuer certification and signing route [3][4]. (b) An optional certified-provider bridge, only if it makes a safe pilot faster. The blueprint names no partner and treats it as a fallback. (c) The DGII answer on a foreign, non-certified software provider, which was still pending on Oct 4 per the blueprint. (d) Later, our own PSFE application. (e) Banks and aggregators for the long-term vision.

> **Maya's note:** Lucas's Oct 4 12:39 PM CT correction makes the certified-provider bridge the route to live invoicing (partner first), so (b) is no longer optional. See [Locked on October 4](#locked-on-october-4).

**Company entity: US vs DR.** For consumer, I agree with Yelena: the choice mostly changes which payment accounts we can open, not what we build. For business it can change more, and Lucas should know:
- **Stripe:** stripe.com/global doesn't list the Dominican Republic (checked Oct 4) [7]. A Stripe account for Cuadrao's own billing likely needs a US entity. Stripe also can't be the payment rail for DR business customers collecting from their own clients. The blueprint already says to choose that provider by DR merchant eligibility.
- **Lemon Squeezy:** acts as merchant of record and lists the Dominican Republic for bank payouts [8]. It's the most entity-flexible web option.
- **Apple and Google:** apps in "banking and financial services" "should be submitted by a legal entity" rather than an individual (5.1.1(ix)) [5]. Whether a money manager counts is App Review's call. Enrolling as an organization is the safe path either way.
- **DGII:** a Cuadrao PSFE needs an RNC whose activity covers software, plus e-CF issuer status [3]. DR business customers may also expect valid fiscal receipts (comprobantes) from us. Confirm with a DR accountant before assuming a US-only entity works for selling to businesses.

**Revenue tools** (no pricing decided; Yelena owns the engineering detail):

| Tool | What it enables | Fits |
| --- | --- | --- |
| RevenueCat | Subscriptions and entitlements across App Store and Play. It also connects Stripe Billing so web purchases unlock the app [9]. It's not a payment processor itself | Consumer in-app billing; one entitlement across app and web |
| Apple IAP / Google Play Billing | Required to unlock digital features in the app (3.1.1) [5]. Small Business Program commission is 15% [10] | Consumer and business premium inside the app |
| Stripe Billing | Web subscriptions, invoices, tax tooling; needs a supported-country entity [7] | Business web, web purchases (US entity) |
| Lemon Squeezy | Merchant of record: handles sales tax and VAT, pays out to DR banks [8] | Web purchases if we stay DR-only or want an MoR |

**Open point: business premium's subscription route.** The business space is also used inside the same iPhone app, so its subscription must follow Apple's rules. What the guidelines (updated June 8, 2026) allow [5]:
- **Sell it through in-app purchase too** (via RevenueCat), alongside web billing. This always works. Under 3.1.3(b), people can use subscriptions bought on our website inside the app, *provided they're also available as in-app purchases*.
- **Sell only on the web and have the app unlock it.** This only fits narrow exceptions. 3.1.3(c) covers apps sold *only* to organizations for their employees, and "consumer, single user, or family sales must use in-app purchase", which a one-owner business may not satisfy. 3.1.3(f) covers free stand-alone companion apps with no purchasing inside, which Cuadrao isn't, since consumer sells inside the app. Outside the US storefront, the app can't point users to web checkout. We can still email our own users about it outside the app.
- **US storefront:** the guideline text now lets US-storefront apps include buttons and links to web checkout [5]. That follows the Epic v. Apple contempt ruling. The Ninth Circuit affirmed it in Dec 2025 but sent the commission question back to the district court [11]. Apple proposed 15% / 10% / 5% link-out commissions in Aug 2026 [12]. No rate is set, and the Supreme Court granted review on June 30, 2026 [13], so this can change. Our main market is the DR storefront, where this exception doesn't apply. The text also doesn't obviously remove 3.1.3(b)'s "also available as IAP" condition. Confirm with App Review before relying on web-only.
- **My recommendation:** plan for in-app purchase plus web billing on one RevenueCat entitlement, with no web-checkout prompts in non-US storefronts. Prices are still Lucas's call.

**Brand and domain.** cuadrao.ai is the home: site, waitlist, `/privacy`, `/terms`, and the universal-link file the invite links need (#810). Details in §A6.

### A6. Side tracks

#### Brand and domain rewire

**Found in the repo:** the old app is **`arguschat.ai`** (Lucas typed "argustchat.ai"; Yelena confirmed `arguschat.ai`). The API is **`api.arguschat.ai`** (since Aug 13), with Render hosts `argus-app-suz5.onrender.com` and `argus-ohr5.onrender.com`. Email runs on a **second domain, `get-argus.com`**: `noreply@` (Supabase Auth and Resend), `support@` (Cloudflare routing), with `send.`, DKIM and DMARC records (PRIVATE_LAUNCH_RUNBOOK). `api.argus.app` appears only as placeholder problem-type URLs in API_CONTRACT.md. cuadrao.ai is already referenced about 27 times on integration.

**What the rewire must deliver:**
1. `arguschat.ai` → `cuadrao.ai` redirects, with a short notice for existing Argus accounts. Moving domains signs people out, so plan for it.
2. Supabase auth redirect and recovery URLs moved to cuadrao.ai.
3. A cuadrao.ai sending domain in Resend (SPF, DKIM, DMARC) and `support@cuadrao.ai`. #781 P5 needs that address.
4. An API host on the new brand, plus a matching iOS config.
5. The universal-link file on cuadrao.ai.
6. Legal: the live Argus terms (investing research) archived and the Cuadrao terms published (#781).
7. A decision on Argus web (see F5).

**Product criteria for rewire vs a new repo** (Yelena decides):
- Time to first testers on both tracks.
- Keeping the landed native, financial, household, sign-in and deletion work, including its tests and FK census.
- Whether existing Argus accounts and data carry over.
- How much the space model forces a schema rework.
- Renaming "Argus" in code is cosmetic. It alone isn't a reason to start fresh.

**What must be inherited:**
- Identity and accounts
- Exact-money services, revisions and idempotency
- Accounts, activity and plans
- Household grants and deletion
- Capture and drafts
- The ingestion contract
- Explanations and calculations from chat
- Feedback, the Resend adapter, PostHog
- Invites and the gate

**Retire as the product center:** backtest and quant research.

#### Docs pass candidates (Maya runs it and checks each one first)

- **Rewrite for Cuadrao:**
  - `DOCUMENTATION_AUTHORITY.md`: still titled Argus, dated Sep 29; says web is frozen and revenue deferred.
  - `PRODUCT.md`: Argus alpha overview.
  - The MVEE: Argus naming. Its Business is "manual records, no invoicing, employees or tax".
- **New:** a business spec (or a business MVEE section), Yelena's ownership model, and this master plan.
- **Shrink:** `argus-execution-board.md` is 3,107 lines. Keep the Oct 4 section current and move the dated pre-Oct sections to `docs/archive/`.
- **Archive candidates in `docs/specs/`:** `private-alpha-next-*` (roadmap, decision memo, p2.1 audit, refine-to-version, chat header title, conversational-edit contract), `wave-1/`, `graded-interpretation-routing.md`, `evidence-aware-idea-loop.md`, `conversation-sharing.md`, and the pointer stubs (`argus-active-roadmap`, `argus-grounded-finance-roadmap`, `argus-pivot-strategy`, `argus-answers-that-stay-true-roadmap`).
- **Agent working notes:** `docs/superpowers/` and `.superpowers/sdd/`.
- **Update during the domain move:** `PRIVATE_LAUNCH_RUNBOOK.md`, `GUEST_PUBLIC_LAUNCH_SAFETY.md`, `docs/release-manifests/` (Argus web history).

#### Open issues

**Un-defer for the first-tester push:**

| # | Title | Why |
| --- | --- | --- |
| 800 | Apple/Google sign-in ship gates | Blocks turning on either sign-in switch; covers 4.8 and 5.1.1(v) |
| 805 | Lane 6: frozen closed-line balance | Blocks deletion in any distributed build |
| 806 | Lane 6: real PostHog deletion adapter | Deletion can't finish without it |
| 811 | Explicit client grants on 17 tables | Must be fixed before any fresh real-user database |
| 784 | iOS commits without Mac verification | The real candidate needs a Mac pass |
| 778 | Document sources to Supabase Storage | Blocks receipt extraction, which is core to capture |
| 798 | Sign-in follow-ups (allowlist orphans, Apple name, Hide My Email) | Tester-visible onboarding UX |
| 807 | Lane 6 ops follow-ups | Only item 15 (who runs the deletion sweep; revisit no-cron) and alerting. The issue says to do this before an external beta |

PR #809 (pytest gate) isn't an issue but should land too.

**Keep deferred:**
- #797, #803, #804. Bring #797 back when the space-model migration starts, and fold #804's worker-count check into #807.
- #700, #696, #656, #653, #644, #640, #623, #620, #606 (Argus chat and backtest quality). Re-check against the chat runtime assignment.
- #671, #676, #684, #685, #686, #694, #690 (security on the live Argus web). These become moot if `arguschat.ai` moves to a redirect or holding page. **If Argus web stays live, un-defer #676, #684, #685 and #686**, because they affect live production (F5).
  **Maya's note:** #686 and #694 are placed as must-dos at main-promotion time, not TestFlight blockers (see [Roadmap at a glance](#roadmap-at-a-glance)).
- **Missing issues:** nothing tracks business yet. Filing pillar 1 and pillars 3–5 slices is Yelena's call.

### A7. Conflicts and open questions

**Where the blueprint is:** two Oct 4 documents, *Cuadrao consumer and business go to market vision* and *Cuadrao Product and Business Architecture*. Neither was in the repo on Oct 4: no e-CF, DGII or Ley 32-23 text appeared on any recent branch, including #813. They are now recorded as the [GTM source](../research/2026-10-04-cuadrao-gtm-vision-source.md) and the [Blueprint source](../research/2026-10-04-cuadrao-product-business-architecture-source.md).

**Contradictions, each with a proposed resolution:**
1. **e-CF route.** My earlier advice was to connect to a certified provider first. The blueprint makes our **own fiscal backend and DGII MCP** the goal, with a certified provider only as an optional fallback. Lucas's Oct 4 ask mentions both. *Resolution:* I'm withdrawing "partner first" as the default and adopting the blueprint. The first business loop runs without live issuance, so a bridge is only needed if a pilot must issue through us before our route is ready (F2).
   **Maya's note:** superseded by Lucas's 12:39 PM CT correction: partner first, with our own backend as the parallel track (see [Locked on October 4](#locked-on-october-4) and §B6). The docs seat hasn't received Iris's updated wording.
2. **The MVEE limits Business to a private manual space** ("no employees, payroll, invoicing or tax") while the blueprint calls for a premium business product. *Resolution:* the MVEE limit becomes the consumer release's scope. Business gets its own spec. Record it in the decision log.
3. **"Web remake frozen"** (MVEE §1.6, DOCUMENTATION_AUTHORITY) vs the business web workspace. *Resolution:* the freeze covers the Argus consumer web. The business web workspace is a new, scoped surface, per Lucas's Oct 4 decision.
4. **"Revenue deferred; don't assign free and paid features"** vs "both products can earn revenue". *Resolution:* the direction has changed. Still no prices. Billing can be built in sandbox, and TestFlight can't charge.
5. **Business in TestFlight while consumer is public, in one codebase.** Guideline 2.3.1(a) bars hidden features. *Resolution:* Yelena recommends how to keep it out (a server switch per account, or a separate TestFlight build).
6. **"Entity mostly changes payment accounts."** That's true for consumer. For business it may also decide the PSFE route and whether we can issue valid fiscal receipts to DR customers (§A5). *Resolution:* treat it as an input to F3, not as settled.
7. **"Stripe for business invoicing."** Stripe can bill for Cuadrao's own subscription with a supported entity. It isn't the rail for DR owners collecting from their own clients. *Resolution:* pick customer payment links by DR merchant eligibility, later.
8. **Domain.** "argustchat.ai" is `arguschat.ai`, and `get-argus.com` (email) also has to move. Lucas didn't mention it. *Resolution:* include it in the rewire.
9. **Deletion and "Former member" were built for households only.** *Resolution:* a business case goes into Yelena's ownership model: when an associate leaves, business records stay with the business and their personal space survives.

**True founder calls (kept short):**
- **F1. First business segment.** The blueprint lists independent service providers, small professional-service firms, or owners already collecting documents on WhatsApp. Who recruits the ~10 owners?
- **F2. Is live e-CF in the first business release or after it?** If a pilot must issue before Nov 15, do we bridge through a certified provider or track their DGII free-tool or current-provider invoices? I recommend tracking.
  **Maya's note:** Lucas's correction already sets the route (partner first) and the pilot's start (tracking). What stays open is whether live e-CF is in the first business release.
- **F3. Company entity:** US, DR, or both, and in what order. Is the Apple developer account enrolled as an organization? That's needed for 5.1.1(ix) safety.
- **F4. Business premium route:** in-app purchase plus web on one entitlement (my recommendation) vs web-only under an exception. Prices stay open.
- **F5. Argus web during the transition:** a redirect or holding page now (the security backlog becomes moot), or keep serving Argus (un-defer the four security issues).

---

#### Part A references (checked October 4, 2026)

- [1] DGII, Aviso 06-26 (6-month extension from May 15, 2026): https://dgii.gov.do/publicacionesOficiales/avisosInformativos/Documents/2026/06-26.pdf · DGII community confirming Nov 15, 2026: https://ayuda.dgii.gov.do/conversations/discusiones/facturacion-electronica/69fba8306d5db755fb24def4
- [2] Ley 32-23, art. 37 schedule: https://dgii.gov.do/transparencia/baseLegal/Documents/Leyes/Ley%2032-23.pdf
- [3] PSFE and issuer-certification requirements, as cited in Lucas's blueprint pp.14–15 (DGII CA4409, FI-GDF-016/017). Not independently re-fetched.
- [4] DGII CA5198 certificate custody and signing models, as cited in the blueprint p.16. Not re-fetched.
- [5] Apple App Review Guidelines (last updated June 8, 2026): 2.2, 2.3.1(a), 3.1.1, 3.1.1(a), 3.1.3(b)(c)(f), 4.8, 5.1.1(v)(ix): https://developer.apple.com/app-store/review/guidelines/
- [6] DGII Facturador Gratuito (about 150 invoices a month): https://dgii.gov.do/cicloContribuyente/facturacion/comprobantesFiscalesElectronicosE-CF/Paginas/facturador-gratuito.aspx · https://ayuda.dgii.gov.do/conversations/facturacin-electrnica/ca5391-cuntas-facturas-e-tems-por-factura-puedo-emitir-a-travs-del-facturador-gratuito/6a26b5432794307d12297f61
- [7] Stripe global availability (DR not listed): https://stripe.com/global
- [8] Lemon Squeezy supported countries (DR bank payouts): https://docs.lemonsqueezy.com/help/getting-started/supported-countries · merchant of record: https://www.lemonsqueezy.com/reporting/merchant-of-record
- [9] RevenueCat × Stripe Billing: https://www.revenuecat.com/docs/web/integrations/stripe
- [10] Apple Small Business Program: https://developer.apple.com/app-store/small-business-program/
- [11] Ninth Circuit, Epic v. Apple, No. 25-2935 (Dec 11, 2025): https://cdn.ca9.uscourts.gov/datastore/opinions/2025/12/11/25-2935.pdf
- [12] Apple's proposed link-out commissions (Aug 13, 2026): https://9to5mac.com/2026/08/13/apple-proposes-commissions-of-up-to-15-for-off-app-store-purchases-in-the-us/
- [13] Apple proffer citing certiorari granted June 30, 2026: https://9to5mac.com/wp-content/uploads/sites/6/2026/08/Epic_Games_Inc_v_Apple_Inc__candce-20-05640__1708.0.pdf · status summary: https://www.macobserver.com/news/apple-app-store-link-out-injunction-live-what-changed-developers/

---

## Part B: Engineering

**Author:** Yelena (engineering). **Drafted:** Sunday Oct 4, 2026, CT. **Status:** draft input for Maya's merged draft PR. Iris owns the product half. Nothing here authorizes a merge, deploy, migration, hosted flag, paid provider or new runtime work; [#813](https://github.com/lagarcess/argus/pull/813) and the [execution board](argus-execution-board.md) keep that authority.

**Baseline read for this draft (read-only):** integration `codex/private-alpha-next` at `a8c37d3a` (#801 merge, Oct 3 6:09 AM CT). `main` (production) is `a9286b21` (Sep 17), 102 commits behind. Open PRs: #813 (draft, `c2748bbd`), #790 (`53a4d67d`), #808 (`a1ebf4b4`), #809 (`ecd2bb57`), #810 (`329fd00d`, stacked on #790), #812 (`5753b5d7`, stacked on #810). Source docs: *Cuadrao consumer and business go to market vision* (Oct 4), called **GTM** below, and *Cuadrao Product and Business Architecture*, called **Blueprint** below. File paths are relative to the repo root on integration unless noted.

**Scope locked by Lucas in the room (Oct 4, 12:30 PM CT), applied throughout:**
1. Consumer iOS launches with **personal + household only**, after a short invite-only TestFlight under the existing invite rules, then goes public and iterates.
2. **Cuadrao for Business is a full web service first.**
3. The business space in the iOS app exists **only for the first business testers on TestFlight**, next to personal + household. Public consumers never see it.
4. The cuadrao.ai landing page promotes the whole suite and carries the waitlists.

Iris's proposal fits this and I've used it here: one codebase, with a thin business space in the app (receipt and invoice capture, quick approvals, where money stands) and the full service on web.

**Aligned with Iris's product half** (Part A). Her half owns the vision, the product map, the leverage ranking, the tester paths, the revenue-tool options and the F1-F5 founder calls; this half doesn't repeat them. Two inputs shape the business sections here:
- **Deadline:** the e-CF deadline for small, micro and unclassified taxpayers is **Nov 15, 2026**, after DGII's extension in Aviso 06-26 (Part A references [1][2]).
- **Fiscal route (Lucas correction, Oct 4 12:39 PM CT):** partner first. Connecting to a DGII-certified provider (PSFE; the Blueprint names Alanube and Alegra as references) is the fastest route to a full business service. Our own DGII backend is the parallel track while Lucas handles the DGII paperwork. The pilot starts by tracking the invoices owners already issue, then issues through Cuadrao once the provider connection is live. Picking the provider is part of Lucas's partner track.

Labels: **[fact]** comes from the repo, GitHub or a cited source. **[proposed]** is my recommendation and needs a lock. **[estimate]** is a rough size, not a commitment.

---

### B1. Rewire or new repo

**Answer: rewire in place.** Keep `lagarcess/argus`, its Supabase project and its migration ledger. Build Cuadrao on the financial, household, auth and deletion foundations that landed in the last week. Freeze the Argus-era chat, backtest and guest surfaces behind their existing flags and retire them on a schedule, instead of porting or deleting them now. Rename what users and Apple see (app name, bundle id, domains, email sender) before external TestFlight. Rename internals (`argus` package, `ARGUS_*` env vars, `argus_private` schema) later, or never.

#### B1.1 Inventory and classification

| Area | What exists (fact) | Size | Call |
|---|---|---|---|
| **Native iOS** | `ios/ArgusFoundation` app, with 109 Swift files in `ios/ArgusFoundation/Cuadrao` (design graft #783/#785/#786/#792) and the `ios/Packages/ArgusSession` client (40 Swift files) that calls the financial, household, invite and auth APIs. Release UI in #790; invites wired in #810; launch perf in #812. Build 3423 was installed on the founder's iPhone 15 with sample data and auth off (#813). Needs Xcode 27 (#784). | ~37k LOC Swift | **Keep.** It's the consumer product. Rename the target and display name (§B3). |
| **Backend API** | FastAPI modular monolith, `src/argus/api/main.py`, 40+ routers in `src/argus/api/routers/` | ~40k LOC `api/` | **Keep.** Split the routers into Cuadrao and legacy groups (§B1.3). |
| **Financial domain** | `src/argus/domain/recording` (accounts, activities, money, assets: 5.4k), `planning` (budgets, goals, debts, claims: 3.9k), `calculations` (2.5k), `finance` | ~13k LOC | **Keep.** It's exact-money, revision-protected and idempotent, and it's the reuse the Blueprint asks for (Blueprint §07 "Reuse the current foundations"). Imports from Argus-era modules: one `canonical_hash` from `domain/backtest_admission.py`. |
| **Household** | `src/argus/domain/household` (6.7k LOC): membership, consent, account grants, shared plans, invites with keyed digests (#788/#794) | | **Keep.** Becomes the household space kind (§B2). |
| **Ingestion** | `src/argus/domain/ingestion` (10k LOC): Plaid, Gmail, documents (vision extraction via OpenRouter, `documents/extractor.py`), iOS Shortcuts tokens, reconcile/duplicates/matching | | **Salvage.** Documents, reconcile and Shortcuts carry straight into the business Inbox. Document bytes sit in Postgres bytea until #778. Plaid is US-only (`render.yaml` `PLAID_COUNTRY_CODES=US`) and has no Dominican coverage (`docs/specs/lanes/financial-ingestion-connectors.md` L18). Gmail uses the restricted `gmail.readonly` scope (`ingestion/gmail/config.py:23`), which needs Google verification plus an annual security assessment (connector doc L36, L155). |
| **Auth** | Supabase GoTrue, email/password, native Apple and Google behind default-off flags (#793/#795/#802), and an invite gate (#788/#794) | | **Keep.** #800 gates stand. |
| **Account deletion (Lane 6)** | `src/argus/domain/account_deletion`, migration `20261004090000_account_deletion.sql`, placeholders, revocations, a manual sweep (`scripts/ops/resume_account_deletions.py`) | 1.2k LOC + 1.1k SQL | **Salvage.** The household path is correct. Business needs a different leave/delete rule (§B2.5). |
| **Supabase migrations** | 111 files, 91 tables, ~18k LOC SQL. FK census with a drift test (`docs/specs/lanes/account-deletion-fk-census.md`, about 100 user-id columns, see #797) | | **Keep the ledger.** The production migration gate (`scripts/ops/production_migration_gate.py`, runbook L125-150) compares against it. Starting over loses that safety net. |
| **Test and eval harness** | `tests/` has 776 files and ~317k LOC, with a real-Postgres CI matrix (`guest-release-gates`). Integration CI: 10,216 backend, 605 real-DB and 2,207 web tests (GrokTeam handoff on #790). There's also `agent-runtime-regression.yml` and the canary/smoke workflows. | | **Keep.** The 152 test files on financial, household, ingestion, deletion and invite code are the strongest asset. The Argus chat/backtest eval suites stay until the chat is retired. |
| **Chat and calculations** | `src/argus/agent_runtime` (62k LOC): research/backtest-oriented interpreter, stages and tools. `domain/backtesting`, `market_data`, `research`, `workflows/` (Render Workflows backtest jobs) | ~75k LOC | **Salvage selectively.** Locked direction keeps the grounded chat and calculations (room lock, MVEE "Agentic ecosystem direction"). But the runtime touches financial data in only 4 files, and #813 says the agentic runtime lane is unimplemented and needs its own bounded assignment. Keep calculations and grounding safeguards. The Cuadrao financial agent is a new lane on top of them. |
| **Web** | Next.js 16 / React 19 (`web/`, ~140k LOC TS). Routes: `/chat`, `/r/[receiptId]` share pages, login/signup/recovery, privacy/terms, `/auth/native-captcha`. **No financial UI.** | | **Salvage the shell, drop the chat UI.** Keep Supabase SSR auth, recovery (the iOS app relies on web recovery, `ios/AUTH_SETUP.md` L111), i18n, captcha bridge and legal pages. Business web is new routes in this app [proposed]. |
| **Guest flow** | Anonymous users, guest workspaces, Turnstile, visitor allowances: about 102 files across src/web/tests/migrations. Open security issues #671/#684/#685/#686 | | **Drop from Cuadrao.** The invite gate replaces it. Keep the code until arguschat.ai web is retired, then remove it in one PR. |
| **Android** | `mobile/android` foundation, 3.3k LOC, last touched #739 (Sep 29), `applicationId ai.argus.foundation.sample` | | **Park.** No Android release is committed (GTM p.5). |
| **Docs** | 5,765 files, about 4,950 of them under `docs/reports/evidence` (2,195 PNGs) | | Maya's pass (§B8). |

> **Maya's note:** Lucas's Oct 4 calls (12:44 PM CT) keep Plaid (sandbox plus Faker data for stress tests; real Plaid for Dominicans in the US and accounts abroad) and park the market-data providers for the pilot (keys out of the live setup, code kept). See [Locked on October 4](#locked-on-october-4).

#### B1.2 Rewire cost compared with a new build [estimate]

| Work | Rewire | New repo |
|---|---|---|
| Surface rebrand (bundle id, name, domains, email, AASA) | S (3-5 eng-days) | Same |
| Space and membership model (§B2) | M-L (3-5 eng-weeks), expand/contract on existing tables | M (2-3 eng-weeks) for the schema, but only after re-creating everything below |
| Re-create financial, planning, household, invites, deletion with equal tests | 0 | L-XL (10-16 eng-weeks): ~30k LOC domain, ~13k LOC SQL, ~150 real-PG test files |
| Re-create the iOS client package and connected flows | 0 | M-L (4-6 eng-weeks) |
| Quarantine the Argus-era surfaces | S-M (1-2 eng-weeks) | 0 |
| CI, release gates, migration gate, runbook | 0 | M (2-3 eng-weeks) |

On these numbers a new repo costs about 4-5x more before the first tester sees anything. The main risk in rewiring is people working on the wrong code: 75k LOC of chat/backtest code and thousands of evidence files can mislead an onboarding team. §B1.3 covers it.

#### B1.3 Containing the Argus-era leftovers [proposed]

- **Naming.** Users and Apple see "Argus Sample" (`ios/Config/Info.plist`), `local.argus.foundation` (`ios/Config/Development.xcconfig`), `noreply@get-argus.com` (`src/argus/domain/resend_email.py:21-22`) and `support@get-argus.com` (`render.yaml`). Fix all of these before external TestFlight (§B3). Internal names (`argus` package, 277 distinct `ARGUS_*` names in code, 71 of them in `render.yaml`, the `argus_private` schema) are invisible to users. Renaming a schema is a destructive migration under the gate, so leave it.
- **Web chat product.** Freeze `arguschat.ai` chat: no new features, keep security fixes. The landing page moves to cuadrao.ai (§B3), and business web is built in `web/` under new routes. Retire `/chat` and the share pages when Lucas decides; the production share-pages setting already differs from integration (handoff on #790).
- **Guest flow.** Keep it off Cuadrao surfaces. Delete it with the chat retirement. Until then, #686's migration and env keys still ship with the next promotion.
- **Code layout.** Add a CODEOWNERS-style map, `docs/CUADRAO_CODE_MAP.md` (Maya), listing Cuadrao-owned and legacy-frozen paths. Group routers under `/api/v1` by owner. Don't move files yet; `scripts/check_modularity_budget.py` already guards size.

#### B1.4 What would flip this to a new repo

1. The space model forces re-keying most of the ~100 user-id columns **and** production holds no financial data worth keeping. Every financial/household migration (20260928 onward) is newer than production `main` `a9286b21`. I couldn't verify whether any were applied out of band. If a fresh schema in a new Supabase project became cheaper than expand/contract, it would flip. It also conflicts with MVEE §1.4 ("reuse ... the existing Supabase project on the current plan"), so that would be Lucas's call.
2. The agentic-runtime decision (#813) picks a framework that can't share the domain services in-process. That affects `agent_runtime/` only, not the repo.
3. Counsel says the "independent Cuadrao implementation" (GTM p.6) requires a clean-room repo for the fiscal stack. As written, the GTM line concerns third-party code licenses, not Argus code.
4. CI time or onboarding confusion measurably blocks delivery after the §B1.3 containment.

---

### B2. Space, ownership and membership model [proposed, for Lucas to lock]

#### B2.1 Today [fact]

- **Every record belongs to a person.** `financial_accounts.user_id` is "one fact" of ownership, ON DELETE CASCADE (`supabase/migrations/20260928200000_financial_accounts_first_slice.sql` L4-12). Records and revisions copy it for RLS. `space_id text not null default 'personal'` exists on accounts, but it's a free-text label: there's no spaces table and no reader of it outside the deletion copy (`20261004090000_account_deletion.sql` L1071).
- **Household = grants and claims, not ownership.** `household_account_grants` (`20261001090000_household_membership.sql` L71), plan bindings, participants and claims (`20261002000000_shared_household_planning.sql`). The migration states "ownership or space_id" never moves (L6).
- **Deletion is the only place ownership moves.** Lane 6 creates one placeholder per sharing scope (`scope_kind in ('household','group')`, deletion migration L256-270), as an `auth.users` row with an `exmiembro+...@cuadrao.invalid` email (#799 B2). Rows the household depends on move to the placeholder. Private rows are deleted.
- **Business: nothing.** MVEE "Financial spaces" (`docs/specs/argus-minimum-viable-ecosystem-experience.md` L410-425) allows a named *private* Business space with no employees, invoicing or tax. Space ownership "still need[s] production contracts".

#### B2.2 Definitions

| Term | Definition |
|---|---|
| **Person** | One identity (`auth.users` + `profiles`). Never shared, never owned by a space. |
| **Space** | A container that owns records. `kind ∈ {personal, household, business}`. Each person gets exactly one personal space at signup, with one member, not transferable. Household and business spaces have members. |
| **Membership** | (space, person, role, status, valid_from, valid_until, granted_by). Roles belong to the space kind. Household: admin/member (as today). Business: owner, admin, bookkeeper (capture/enter), approver, accountant (read/export, time-limited), viewer. A separate **billing admin** flag grants no financial content (Blueprint §02). |
| **Record ownership** | A *root aggregate* carries `owner_space_id`: account, plan, document/inbox item, customer, invoice, vault file, export. Child rows (activities, revisions, allocations, invoice lines) inherit it through their composite FK, the way records inherit `user_id` today. **No mechanical `space_id` on every table** (Lucas, room). |
| **Grant** | Permission for a space or member to *see or act on* a record owned elsewhere. It never moves ownership. Household sharing stays grant-based. |
| **Transfer link** | Two records, one in each space, each created under that space's own authorization, plus a `cross_space_link` row naming both. Never one record shared across spaces (Iris; Blueprint §02). |
| **Actor reference** | Who did it, stored on revisions, approvals and audit rows. In shared spaces it points at the **membership**, not straight at `auth.users`. A person's deletion therefore never meets an FK RESTRICT (it hit 4 of them in Lane 6: census blockers 3-5 and `apple_sign_in_credentials`). |
| **Identity retention rule** | For a member's own personal space, delete everything (Lane 6). In a household, keep the history under the household placeholder "Exmiembro" (Lane 6 as built). In a business, keep the membership row with role and a name snapshot for audit while statutory retention applies; after that, pseudonymize to "Former member (role)". The retention period is counsel's input. |

#### B2.3 Mapping today onto it, and the migration path [proposed]

Use expand/contract, with each step passing the production migration gate (runbook L139-145) and updating the FK census in the same PR (census drift test).

1. **Expand (additive).** Create `spaces` and `space_memberships`. Backfill one personal space per auth user. Backfill one household space per `households` row, reusing `households.id` as the space id so grants and bindings stay valid. Add a nullable `owner_space_id` on root aggregates (start with `financial_accounts`, then plans and documents) and backfill it from `user_id`. Dual-write.
2. **Switch readers.** RLS and service checks move to `is_space_member(owner_space_id, auth.uid(), permission)`, one aggregate at a time. Add a real-PG cross-space leakage test for each aggregate (Blueprint §06 "test ... cross-space leakage").
3. **Contract.** Set `owner_space_id` to NOT NULL. `user_id` becomes `created_by` (a person or actor reference, not ownership). Drop the free-text `space_id`. This step is `contract-replacing`, so it needs a maintenance window or expand/contract plan per the runbook.
4. **Business kind.** Add the business kind, roles and permissions last, with the business record types (customers, invoices, inbox, vault).

The cheapest time to do steps 1-3 is **before external TestFlight**, while hosted production has no financial rows. Consumer TestFlight only needs steps 1-2 for personal and household. Step 4 is web-first (scope locks 2 and 3).

#### B2.4 Test cases

| Case | Outcome under the model |
|---|---|
| **An associate leaves a business** | The membership ends (`valid_until=now`) and access is revoked immediately, including signed URLs and search. Business records stay with the business, and actor references keep the membership with a name snapshot. The associate's personal and household spaces aren't touched. Nothing moves. |
| **The owner transfers ownership** | An owner-role handover between two active members, with consent from the receiver and an audit row. Records don't move (the space owns them). Billing admin is a separate step. A business always keeps at least one owner, as households already require an admin (`households_check`, census blocker 2). |
| **An employee enters receipts** | The bookkeeper role grants `document.upload` and `activity.draft` on that business only. Drafts need an approver. They can't see accounts outside their grant, and they never see the owner's personal or household spaces. |
| **An accountant gets time-limited access** | The accountant role has `valid_until` and is scoped to read and export for a period. Every export is versioned (Blueprint Module 8). Access ends without anyone acting; revocation is immediate. |
| **A household member leaves** | Already built: grants revoked, consent lifecycle, plan responsibility carry (`20261002030000`-`20261002050000`). Personal space untouched. |
| **A person deletes their account while in a household and a business** | Personal space: deleted (Lane 6 data step). Household: Lane 6 placeholder as built. Business: membership ended, actor pseudonymized per the retention rule, business records untouched. **Gap:** Lane 6 has no business branch, and a sole business owner can't delete until ownership is transferred or the business is closed (proposed rule). |
| **The owner pays a business expense personally** | A personal-space expense (card) plus a business-space expense with "paid by owner" status and a payable to the owner. A `cross_space_link` joins them. "Pay me back" later creates a business payment and a personal income or refund, linked the same way. Both sides need the owner's authority in each space. |
| **Combined owner dashboard** | A read-only projection across the spaces the viewer belongs to, computed per space and then summed per currency. Linked pairs count once: a payable to the owner and the matching personal expense net out. Household totals use only granted records, as they do today. DOP and USD are never added together (Blueprint Module 7). |

#### B2.5 Who keeps each record when someone leaves

| Record type | Personal | Household | Business |
|---|---|---|---|
| Accounts, activities, revisions | The person (deleted with the account) | The owner keeps it. The household loses the grant. | The business |
| Plans, budgets, goals, debts | The person | Shared plan: the household, under the placeholder on deletion (Lane 6) | The business |
| Documents, receipts, vault files | The person | The uploader's space, plus grants | The business, including files a departed bookkeeper uploaded |
| Customers, invoices, e-CF records | n/a | n/a | The business, kept for the fiscal retention period (counsel) |
| Approvals, audit log | The person | The household (actor becomes "Exmiembro") | The business (actor becomes a membership snapshot, then pseudonymized) |
| Cross-space links | Each side stays with its own space. The link survives as long as both sides exist. | | |
| Chat history and memories | The person, never shared | The person | Agent actions on business records are logged in the business audit. The conversation stays with the person. |
| Connector credentials (Plaid, Gmail) | The person (revoked on deletion, Lane 6) | n/a | The business connection, revoked when its admin leaves unless re-authorized |

#### B2.6 Scope has to travel everywhere [fact and proposed]

- **Search:** `src/argus/domain/financial_search.py` and `postgres_search_reader.py` filter by user today. They need to filter by membership, and each result must show its space (MVEE L422-424).
- **Jobs:** the Render Workflows tasks (`workflows/main.py`) and extraction, imports and reminders need `space_id` and `actor_membership_id` in the payload, and they must recheck the grant when they run (Blueprint §06).
- **File storage:** #778's bucket paths become `space/<space_id>/...`, with downloads proxied through the same grant check.
- **AI retrieval:** memory vectors key on `payload->>'user_id'` (#797 item 4) and context packets key on the user. Agent retrieval has to be scoped to the selected space plus the person's permissions (Blueprint §06 "Read only records visible ... in the selected space").

#### B2.7 Thin business space in the app (scope lock 3) [proposed]

The model and API are shared. Business web is the full client. The app's business space uses only three surfaces, all on the same endpoints: (a) capture a receipt or invoice photo into the business Inbox, (b) quick approvals (approve or reject drafts assigned to the member), (c) a read-only view of where the money stands. Anything more than that belongs on web. The Swift code for these lives behind a compile-time condition (§B3.4).

---

### B3. Brand and domain cutover

#### B3.1 Current state [fact]

- **iOS:** the default bundle id is `local.argus.foundation`, and the display name is "Argus Sample". Build 3423 was signed as `local.cuadrao.design.47R3855RTJ` (#813). Team and app ID aren't approved (`ios/Config/Device.local.xcconfig.example`). I didn't find an App Store Connect record (unverified). Android: `ai.argus.foundation.sample`.
- **Domains:** `arguschat.ai` (web on Render, A records 216.24.57.x) and `api.arguschat.ai` (Render `argus-ohr5.onrender.com`, #694). `get-argus.com` carries email: the Resend sender, plus Cloudflare Email Routing MX for support@. `cuadrao.ai` is on Cloudflare NS (the same NS pair as the other two) with **no A or MX records**, and HTTPS didn't connect (DNS-over-HTTPS check, Oct 4 ~12:30 PM CT). The invite universal-link base is already `https://cuadrao.ai/invite#` (`src/argus/domain/household/invite_codes.py:36`, flag `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED`). The AASA file and Associated Domains aren't done (#810 out of scope).
- **Supabase Auth:** the hosted Site URL and redirect list aren't in the repo. `supabase/config.toml` lists only localhost. Apple and Google OAuth callbacks are `https://<ref>.supabase.co/auth/v1/callback` (`ios/AUTH_SETUP.md` L80, L89).
- **Render:** `ARGUS_APP_ORIGIN=https://arguschat.ai`, with CORS listing arguschat.ai and `NEXT_PUBLIC_ARGUS_API_URL=https://api.arguschat.ai/api/v1` (`render.yaml`).

#### B3.1a Old-domain inventory (repo, integration `a8c37d3a`, `git grep`)

**`get-argus.com` (email domain): 13 non-docs files plus 62 docs files.** Every runtime and config hit:

| Where | What |
|---|---|
| `src/argus/domain/resend_email.py:21-22` | Sender `noreply@get-argus.com`, header `Argus <noreply@get-argus.com>`. Used by approval email (`access_approval_email.py`) and feedback notification (`api/feedback_notification.py`). |
| `render.yaml:232`, `.github/private-alpha-release-profile.json:118`, `.env.example:83-84,455`, `web/.env.local.example:22-23` | `NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL=support@get-argus.com` |
| `web/argus_display_contract/support_contact.json:2` | The single owner of the support address shown in web (#596) |
| `docs/PRIVATE_LAUNCH_RUNBOOK.md:666-673` | Supabase Auth SMTP sends as `noreply@get-argus.com` through Resend. Custom MAIL FROM is `send.get-argus.com` (`v=spf1 include:amazonses.com ~all`), DKIM is at `resend._domainkey.get-argus.com`, and DMARC is at `_dmarc.get-argus.com` (reports to support@, started at `p=none`). Cloudflare Email Routing handles inbound support@ (MX `route1-3.mx.cloudflare.net`, DNS-over-HTTPS read Oct 4). |
| `tests/test_private_alpha_canary_split.py` (5×), `web/e2e/support/private-alpha-canary-session.ts:42`, runbook L403 | The canary signs up `private-alpha-canary+<hex>@get-argus.com` and depends on that inbox routing. |
| Tests that pin the strings | `tests/test_access_approval_email.py`, `test_feedback_notification.py`, `test_access_request_postgres.py`, `tests/evals/test_prose_evidence.py`, `web/__tests__/legal-pages.test.tsx` |

**`arguschat.ai`: 14 non-docs files plus 40 docs files.**
- **Runtime/config:** `render.yaml` (CORS, `ARGUS_APP_ORIGIN`, `NEXT_PUBLIC_ARGUS_API_URL`), `.github/argus-env.sh`, `.github/private-alpha-release-profile.json`, `.env.example`, `src/argus/domain/access_approval_email.py`, `AGENTS.md`, and the Android `AuthEnvironmentTest.kt`.
- **Tests:** release-profile, environment, canary and perf tests (`tests/test_environment_scripts.py` ×9, `test_private_alpha_release_profile.py` ×5, ...).
- **Render hosts:** `argus-app-suz5.onrender.com` and `argus-ohr5.onrender.com` appear in 14 non-docs files. Render subdomains are disabled for the API (`renderSubdomainPolicy: disabled`).

**Not a cutover item:** `api.argus.app` appears only as problem-type URIs (`src/argus/api/dependencies.py` ×4, `app_setup.py`, `openapi_compat.py`, `docs/api/openapi.yaml`). These are contract identifiers that clients may match on, not resolved hosts. Leave them, or version them in a deliberate API-contract change.

#### B3.2 Sequence that doesn't break TestFlight [proposed]

0. **Choose the legal entity and Apple Developer team before the first external build** (US or DR, §B9). Sign in with Apple identifiers are tied to the team, and an app transfer forces a user migration (old tokens return `invalid_grant`, #803). An organization enrollment needs a D-U-N-S number (unverified for timing).
1. **Register the permanent bundle id** (e.g. `ai.cuadrao.app`) and create the App Store Connect record "Cuadrao". The bundle id can't be changed once the record exists. Enable the Sign in with Apple and Associated Domains capabilities. Set `PRODUCT_NAME` and the display name to Cuadrao. Set `ARGUS_APPLE_BUNDLE_ID` in Render to match.
2. **DNS on cuadrao.ai** (Cloudflare): add `cuadrao.ai` and `www` as custom domains on the web service (landing page), and `api.cuadrao.ai` as a **second custom domain on the same `argus-api` service**. `api.arguschat.ai` stays up. Add both to CORS and the origin settings. Point `app.cuadrao.ai` at business web when it exists. The first TestFlight build should use `api.cuadrao.ai`, so testers never need re-pointing.
3. **AASA:** serve `https://cuadrao.ai/.well-known/apple-app-site-association` from the web app, `application/json`, no redirect, with `TEAMID.ai.cuadrao.app` and paths `/invite*`. Add `applinks:cuadrao.ai` to the entitlements. Then turn on `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED`, both server and client (#810).
4. **Email (get-argus.com → cuadrao.ai):**
   - In Resend, verify `cuadrao.ai` with the same record set get-argus.com uses: MAIL FROM `send.cuadrao.ai` with SPF `include:amazonses.com`, DKIM `resend._domainkey.cuadrao.ai`, and DMARC `_dmarc.cuadrao.ai` at `p=none`, tightened after a week of clean reports (runbook L666-673 pattern).
   - Add Cloudflare Email Routing MX on cuadrao.ai for `support@`, and set the DMARC report mailbox.
   - Then, in one PR, switch `resend_email.py:21-22`, `support_contact.json`, the `NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL` values (render.yaml, release profile, env examples) and the pinned tests, and move the Supabase Auth SMTP sender in the dashboard.
   - Move the canary to `private-alpha-canary+...@cuadrao.ai` in the same PR.
   - **Keep get-argus.com's MX, SPF, DKIM and DMARC records for at least 90 days.** Existing users reply to it, and old auth emails have its links.
   - The Privacy/Terms support address (#781 P5) follows the switch.
5. **Supabase Auth:** add the cuadrao.ai Site URL and exact redirect URLs (recovery at `/auth/recovery`). **Don't add a Supabase custom domain before TestFlight**, because it changes the OAuth callback that Apple's Services ID and Google's web client are registered against. Add the cuadrao.ai origin to the Google web client and Apple Services ID.
6. **arguschat.ai:** after the landing page is live, 301 every web path to cuadrao.ai, keeping the path so `/r/<id>` share links still resolve. Keep `api.arguschat.ai` serving for at least one release cycle of old clients, then retire it.
7. **Env renames last:** read `CUADRAO_*` with an `ARGUS_*` fallback in one config module, flip Render, then remove the fallbacks. This doesn't block testers.

#### B3.3 Landing page with waitlists (scope lock 4) [proposed]

The waitlist today is only an external URL (`ARGUS_WAITLIST_URL`, `invite_codes.py:206`). There's no capture backend. Proposed: a static cuadrao.ai landing page in `web/` that promotes the suite, plus one `waitlist_signups` table with interest flags (consumer iOS, business web, Android) and a Resend double opt-in. Size S. The privacy text (#781) has to cover it.

#### B3.4 Gating business in the iOS app [engineering decision]

**The rule:** Guideline 2.3.1(a) says "Don't include any hidden, dormant, or undocumented features in your app; your app's functionality should be clear to end users and App Review" (App Review Guidelines, last updated June 8, 2026, https://developer.apple.com/app-store/review/guidelines/, read Oct 4). Guideline 2.2 says TestFlight builds "should be intended for public distribution and should comply with the App Review Guidelines".

| Option | How it works | 2.3.1 risk | Cost |
|---|---|---|---|
| A. Server-side entitlement only | One binary. The business space shows when the account has a business membership or entitlement. | **High in App Store builds.** Business code ships dormant for every public user. It's defensible only if described in review notes with a reviewer business account, which contradicts "public consumers never see it". | Lowest build cost |
| B. Compile-time flag, separate TestFlight build | A `Business-Beta` build configuration sets the Swift condition `CUADRAO_BUSINESS`. App Store and consumer TestFlight builds compile the business code out. Business builds go only to a "Business pilots" TestFlight group. | **None for App Store builds**, because the code isn't in the binary. The beta build is honest: its testers see the feature. | Two build flavors on one App Store Connect record, plus a CI gate |
| **C. B + server-side authorization (chosen)** | B for what's in the binary. Server-side membership or entitlement for what any client may do. | None | B + nothing extra, since the server checks are needed anyway |

**Decision (engineering, firm): Option C.** Server-only gating (A) is ruled out for App Store builds. Use the same app record and bundle id, so Sign in with Apple, invites and AASA stay single. Add a release-check CI step that fails when an App Store candidate has `CUADRAO_BUSINESS` set, or has business strings in the binary. That's the same pattern as the #800 gate 3 "release force-off" and the existing `CUADRAO_DESIGN_PREVIEW` compile and Info key. Business pilots join through the existing invite gate. External TestFlight groups need Beta App Review per significant build (Guideline 2.2), so plan review time for business builds. When business reaches the public App Store app, the flag flips on in the App Store flavor. Business becomes a documented feature with review notes and a reviewer business account, and IAP rules apply (§B5).

The server is the real boundary in both flavors. A consumer build that called business endpoints would still get 403 without a business membership.

---

### B4. Platform: Resend, Render, Supabase

| | Set up today [fact] | Needed [proposed] |
|---|---|---|
| **Render** | `argus-api` (Python, `standard`, Virginia, deploys `main`, autodeploy off, Render subdomain disabled). `argus-app` (Next.js on Bun, `starter`). A Render Workflows service for backtest jobs (`workflows/main.py`, `ARGUS_BACKTEST_*_TASK`), not in `render.yaml`. No cron service. | cuadrao.ai custom domains (§B3). One more workflow task family for extraction, imports and reminders when business needs them. Verify `WEB_CONCURRENCY`, because the in-process rate limiters scale with workers (#671, #804, #807). A cron for the deletion sweep stays **off** (Lucas, Oct 3, 2:04 AM CT; runbook L804-810), so an operator runs `scripts/ops/scheduled_maintenance.py` daily while any run is in flight. |
| **Supabase** | One hosted project, which MVEE §1.4 locks ("a second Supabase project or paid upgrade is not a prerequisite"). Supabase Preview branches run in CI but were skipped or cancelled at the concurrent-branch limit (Priya's #799/#801 evals). CI is pinned to CLI 2.109.0 because newer images change default grants (#811). | Staging and prod: today TestFlight would run against production. A separate staging project contradicts MVEE §1.4 and would be **built fresh**, which #811 says leaves 17 tables open until fixed. So fix #811 before any new project, or use branches as staging (Lucas, §B9). |
| **Migration gate** | `scripts/ops/production_migration_gate.py`, with additive / contract-replacing / destructive classes and founder approval for destructive (runbook L139-145). Pending in prod: #674's migration first (#686), the #794 destructive `20261003150100` (backup plus founder OK), and all migrations from 20260928 onward. | Run the gate for the integration-to-main promotion that carries the TestFlight backend. Set `ARGUS_INVITE_CODE_SECRET` before any household or beta flag. |
| **Storage** | No buckets in migrations. Document sources sit in `financial_document_extractions.source_bytes` bytea (#778). | A private bucket keyed by space (§B2.6). #778 must land before `ARGUS_DOCUMENT_EXTRACTION_ENABLED` anywhere. Business needs it on day one. |
| **Resend** | SMTP `smtp.resend.com`, sender `noreply@get-argus.com` (`resend_email.py`). Used for approval and feedback mail. | cuadrao.ai domain (§B3.2 step 4). Waitlist opt-in, invites and business notifications. |
| **Costs to watch** | OpenRouter models on six routes (`render.yaml` `ARGUS_*_MODEL`), Perplexity research, PostHog, and Render `standard` + `starter` + workflows | Vision extraction per document, storage growth, Supabase branch hours, WhatsApp per-conversation fees (if adopted), and Gmail's annual security assessment (if Gmail ships). Track cost per space (Blueprint §11). |

---

### B5. Revenue capture: engineering view

**The rules and tool options are in §A5** (App Review Guidelines last updated June 8, 2026: 3.1.1, 3.1.1(a) US storefront, 3.1.3(b)/(c)/(f), 2.2; Stripe, Lemon Squeezy, RevenueCat). Facts I checked myself that change the build:
- Stripe's global page doesn't list the DR (https://stripe.com/global, fetched Oct 4). Stripe Managed Payments (merchant of record) is GA in 39 countries as of Apr 22, 2026, and the DR isn't on its business-location list (https://docs.stripe.com/payments/managed-payments/eligibility).
- Lemon Squeezy lists DR bank payouts and DOP selling (https://docs.lemonsqueezy.com/help/getting-started/supported-countries), and its 2026 update steers toward Stripe Managed Payments (https://www.lemonsqueezy.com/blog/2026-update).
- RevenueCat Web supports Stripe Billing, Paddle Billing or RevenueCat Billing (https://www.revenuecat.com/docs/web/overview), and **has no Lemon Squeezy integration listed**.
- TestFlight can't charge (Guideline 2.2), so billing is off the tester critical path; only entitlement plumbing is on it.

**Engineering consequences (Iris owns the commercial options):**
1. **One server-side entitlement table is the source of truth**, keyed on `(subject_type ∈ {person, space}, subject_id, entitlement, source ∈ {app_store, web, manual}, valid_until)`. A business premium entitlement attaches to the **space**. A consumer plan attaches to the **person**; household sharing of a plan is a policy on top. Every client checks the API, never a store SDK alone. Size M.
2. **Consumer iOS (public):** use StoreKit through RevenueCat with App User ID = Supabase user id. A RevenueCat webhook writes into the entitlement table. This needs the Paid Apps Agreement and banking for the chosen entity.
3. **Business web:**
   - **US entity:** Stripe Billing works, with tax handled by Stripe Tax or Managed Payments if eligible. RevenueCat can import it if one dashboard is wanted.
   - **DR entity:** Lemon Squeezy works, through a direct webhook into the entitlement table. RevenueCat can't see it, so the API stays the only reconciler.
   - With a merchant of record such as Lemon Squeezy, the MoR is the seller, so Cuadrao issues no DR fiscal receipt for the subscription (see §B6, "Entity consequences").
   - Write one `BillingProvider` adapter interface either way, so a later switch doesn't touch entitlement logic.
4. **When business reaches the App Store app** (§A5 recommendation: IAP plus web on one entitlement):
   - Add a business IAP product in RevenueCat. Its webhook writes the same space-level entitlement.
   - The App Store flavor shows no web-checkout prompt outside the US storefront. That needs a storefront check in the paywall (StoreKit `Storefront.current`).
   - Nothing else changes, because the entitlement already attaches to the space.

   During TestFlight, business pilots get a `manual` entitlement source (no charge, per 2.2).
5. **Membership vs billing:** the billing admin flag grants no content (§B2.2), and seat counts read from memberships.

---

### B6. Pillars with no institutional access: cost and feasibility

Sizes [estimate]: S = 1 eng-week or less, M = 2-4, L = 5+. **Now** = buildable now. **1-away** = one named relationship away. **Gated** = regulator, counsel or certification controls it. I'm not ranking them; order is Iris's call.

**Shared foundation (both tracks need these first)**

| Pillar | Status | Size | Depends on | Parallel? |
|---|---|---|---|---|
| Space and membership model, steps 1-3 (§B2.3) | Now | M-L | none | Must precede the business record types |
| Entitlement service (§B5) | Now | M | Entity for the live providers | Yes |
| Scoped storage (#778 plus space paths) | Now | M | Space model step 1 | Yes |
| Audit log and approvals framework | Now | M | Space model | Yes |
| Durable jobs beyond backtests | Now | M | Render Workflows exists | Yes |
| Agentic Cuadrao: financial read and propose tools | Now (OpenRouter), behind the AI consent gate (#813) | L | Bounded runtime assignment (#813), space-scoped retrieval | After the manual services |

**Consumer (personal + household, iOS)**

| Pillar | Status | Size | Notes |
|---|---|---|---|
| Accounts, activities, plans, budgets, goals, debts | Now, mostly landed | S-M to connect and verify | #813 "Accounts, Plans, Household" row |
| Household invites and sharing | Now, landed backend, iOS in #810 | S | AASA (§B3.2) |
| Onboarding and sign-in | Now | M | #800, Apple and Google keys (Lucas) |
| Receipt capture and document extraction | Now | M | #778, AI consent gate |
| CSV/statement import | Now | M | No file parser found in `ingestion/`; reconcile exists |
| iOS Shortcuts capture | Now, landed (`ingestion/shortcuts`) | S | |
| Push and reminders | 1-away: APNs key (Lucas) | M | Updates inbox |
| Gmail bank-alert intake | 1-away: Google OAuth verification plus annual security assessment | S code, L process | Connector doc L36, L155 |
| Plaid | Gated for DR users (no Dominican coverage) | n/a | Keep only for foreign accounts |
| DR bank data (Bridge, banks) | Gated (banks, Superintendencia de Bancos, Bridge) | n/a | Lucas's track |
| Consumer billing (RevenueCat) | 1-away: entity plus Paid Apps Agreement | M | Not on the TestFlight path |
| Account deletion enablement | Now | M | #805, #806 |

> **Maya's note:** per Lucas's Oct 4 call, Plaid is kept: sandbox plus Faker data for stress tests now, and real Plaid for Dominicans in the US and with accounts abroad once Plaid's production review clears. Gmail import stays an open decision.

**Business (full web first, plus a thin app space for pilots)**

| Pillar | Status | Size | Notes |
|---|---|---|---|
| Business web shell (auth, space switcher, roles UI) in `web/` | Now | M | Reuses Supabase SSR auth and i18n |
| Roles and permissions matrix | Now (needs Lucas's matrix lock) | M | Blueprint §02 presets |
| Money and ops: cash, manual accounts, imports, reconciliation | Now (reuses recording, reconcile) | M | Space model step 4 |
| Document Inbox and Vault | Now (reuses the extraction pipeline) | M-L | #778 |
| Customers / light CRM | Now | S-M | |
| Quotes, non-fiscal invoice drafts, tracking existing invoices | Now | M | Must never look like an e-CF (Blueprint §13) |
| Collections, allocations, payment matching (manual evidence) | Now | M-L | Blueprint §08 allocation rules |
| Reports and accountant package/export | Now | M | |
| Accountant time-limited access | Now | S on top of memberships | |
| Thin app space: capture, approvals, money view (§B2.7) | Now | M | Compile-time gated (§B3.4) |
| Telegram intake | Now (Bot API) | S-M | Candidate only |
| WhatsApp Business API intake | 1-away: Meta WhatsApp Business Platform (business verification, Cloud API or a BSP) | M | Per-conversation cost |
| POS read-only adapter (Alegra or Odoo) | 1-away: vendor API access plus pilot merchants | M | Discovery first (Blueprint §10) |
| Payment links | 1-away: a payment provider eligible for DR merchants (unnamed) | M | |
| External API/MCP over authorized actions | Now (internal), external after the permission model | M-L | Blueprint §06 |
| **Tracking externally issued e-CF** (owners keep issuing via DGII's Facturador Gratuito or their current provider; Cuadrao records e-NCF, issuer RNC, status, PDF/XML and links payments) | Now | M | **First pilot step** (Iris F2: track). Needed before Nov 15, 2026 for owners in the Aviso 06-26 group. Issuance moves to the provider bridge once that's live. |
| Own fiscal backend, offline: versioned e-CF XML builder, XSD/business-rule validator against DGII's published specs, sequencing, durable submission state machine, evidence store (canonical invoice, XML, hash, responses) | Now (no live submission) | L | Blueprint §14 and §16, Iris pillar 7. **Parallel track** behind Lucas's DGII paperwork; it eventually replaces the provider. It's designed so the issuer is the customer and private keys never enter the model or MCP payloads. |
| Cuadrao DGII MCP over that backend (schema retrieval, draft validation; submit and status later) | Now (read and validate tools) | M | Exposes only actions the permission layer already allows (Blueprint §06) |
| DGII test-environment submission and certification walk for one pilot issuer | 1-away: a pilot taxpayer with an RNC, Virtual Office access, a tax digital certificate and FI-GDF-016 | M of engineering, plus weeks of DGII process | Blueprint §15. The DGII foreign-provider question was still unanswered as of Oct 4, 16:32 UTC. |
| Signing adapter | 1-away: a trust service (Viafirma/AVANSI candidate, Blueprint §16) or customer-controlled signing. Custody legality is with counsel. | M-L | Pluggable, so a vendor swap keeps evidence and idempotency |
| Live e-CF issuance through Cuadrao's backend | Gated: each customer's DGII issuer authorization, plus the signing route and operating-entity eligibility | S on top of the rows above once gates clear | Not in the first pilot |
| **Certified-provider bridge (partner first)** | 1-away: a PSFE agreement (provider chosen in Lucas's partner track; Alanube and Alegra are the Blueprint references) | M | **The route to live e-invoicing through Cuadrao.** It sits behind the same fiscal-backend interface as our own backend, so we can switch later without touching the ledger. The interface and adapter can be built against the provider's sandbox before the contract is signed. |
| Cuadrao PSFE status | Gated: our own RNC with software activity, e-CF issuer status, three certified customer issuers, dossier and DGII tests (Blueprint §15) | L (process) | After the pilot issuers |
| Tax preparation (records readiness) | Now | M | Filing is gated (DGII Virtual Office, qualified professional) |
| Business web billing | 1-away: entity plus Stripe or Lemon Squeezy | S-M | §B5 |

**What can run in parallel:** three streams on top of the space model:
- (a) the consumer TestFlight path, which needs only steps 1-2;
- (b) the business ledger: web shell, roles, money, Inbox, customers, invoice drafts, external e-CF tracking, matching and accountant export;
- (c) the offline fiscal backend and DGII MCP.

Stream (c) touches (b) only at the invoice record and its fiscal-state fields, so lock that schema first. Both clients share one entitlement and audit stream.

**Business-ledger sizing for the first pilot [estimate]:**
- The pilot is the space model step 4, roles, Inbox, customers, non-fiscal invoices, external e-CF tracking, matching, export, and the thin app space.
- That's roughly 12-18 eng-weeks of work, so 6-9 calendar weeks with two engineers in parallel on (b).
- None of it waits on DGII.
- The certified-provider bridge adds about 3-5 eng-weeks [estimate] and is the first fiscal work to start (adapter against the provider sandbox, then live once the agreement is signed).
- The offline fiscal backend (c) adds about 6-10 eng-weeks and runs in parallel at lower priority, behind Lucas's DGII paperwork.

**Entity consequences for the fiscal track (engineering only; Lucas decides, Iris F3):**
- **PSFE needs a DR RNC.** Our own PSFE requires an RNC with software activity and e-CF issuer status (Blueprint §15). If we're US-only, the backend must stay in the "customer is the issuer, Cuadrao is software" model, which depends on DGII's pending answer on foreign non-certified providers. Build that way anyway: it's the model every route needs first.
- **Valid DR fiscal receipts for our own subscription bills need a DR issuer.** If DR business customers need valid comprobantes for what Cuadrao charges them, a DR entity has to issue them. That entity would then become the fiscal backend's first issuer (which also meets the PSFE "existing e-CF issuer" prerequisite). Billing webhooks would trigger an e-CF per charge, and a merchant of record like Lemon Squeezy would conflict, because the MoR, not Cuadrao, is the seller of record.
- **A US entity with Stripe** gives us US billing, but no DR fiscal receipts from us.
- **Make the billing → fiscal hook configurable per entity**, so either answer fits without a rewrite.

---

### B7. Issues triage for the next push

27 issues are open (fetched Oct 4). **Correction to the brief:** #789 is **closed**: it was closed Oct 4 at 9:53 AM CT after #794 and recorded in #813.

**Must-do for consumer TestFlight (invite-only)**
- #800: Apple/Google sign-in ship gates (release force-off, 4.8, privacy manifest, revocation) before either flag goes on in TestFlight.
- #784: Mac verification of the combined candidate, plus the permission-key release gate.
- #811: explicit client grants on 17 early tables. #813 lists it as a release gate. It's mandatory before any fresh database (staging or rebuilt).
- #778: document bytes to private Storage before extraction is on, if receipts are in tester scope (#813 puts receipts in the journeys).
- #805: Lane 6 frozen closed-line balance. It blocks the deletion flag in TestFlight. Without it, testers only get the flag-off support fallback.
- #806: real PostHog deletion adapter. Same gate as #805.
- #798: Hide My Email linking and the allowlist-orphan decision are marked "before the beta". Apple name capture goes with them.
- #686: the promotion that carries the TestFlight backend must apply #674's migration and env keys first.
- #694: the forged-header check runs in that promotion window.
- #809 (PR, not an issue): land the pytest-gate fix so the gate line can't misreport failures.

  Iris keeps #686/#694 deferred unless Argus web stays live (her F5). I've listed them here because the TestFlight API *is* `argus-api` on `main`. Any promotion carrying #674 has to apply its migration and env keys first, whether or not arguschat.ai web stays up. They become moot only for the web-security residual.
- #807 (item 15 only): name the operator for the daily deletion sweep while runs are in flight.

**Must-do for business TestFlight pilots and business web** (no issue exists yet; Maya or Yelena should file them after the lock [proposed])
- Space model steps 1-4. #797 (census drift gaps) goes with it, since re-keying will move FKs the gate can't see today.
- Roles and permissions, audit log, and the entitlement service.
- Business Inbox/Vault on #778 storage, the thin app space with the compile-time gate (§B3.4), and its release-check CI.
- #690: re-scope the parked security rescan to the new business, agent and file surfaces before real business data.

**Needed before public launch**
- #807 items 3 and 5: alerting and the per-worker deletion limiter.
- #804, #803: invite-hardening and Apple notes.
- #671: in-memory auth rate limiters, which scale with workers.
- #676: password-recovery limiter on a spoofable header. The iOS app relies on web recovery.
- #700: chat idempotency, if the Cuadrao agent reuses the chat turn path.
- #656: a raw internal name in calculation answers, since calculations stay (room lock).

**Archive, or close as obsolete after the pivot** (Lucas or Iris confirm; most are already `triage:backlog`)
- #640, #606: web chat presentation and freshness (frozen web chat).
- #644, #653: Argus chat prose and acceptance traces (diagnosis already stopped).
- #623, #620: backtest capital and grounded-math research changes (founder-deferred).
- #696: share-receipt currency (share pages retiring).
- #684, #685: guest/research and backtest admission abuse. Close when the guest flow and backtests are retired; until then they still matter on arguschat.ai.

---

### B8. Docs pass inputs for Maya

**Current canon to keep, and rewrite for Cuadrao where noted:**
- `AGENTS.md`.
- `docs/DOCUMENTATION_AUTHORITY.md`: rewrite. It still says "Argus" and "retains the Argus visual identity".
- `docs/PRODUCT.md`: rewrite for three contexts.
- MVEE: amend "Financial spaces" L410-425, which excludes business invoicing and employees and now conflicts with the business premium scope.
- The execution board (#813 section).
- The decision log.
- `ARCHITECTURE.md`, `API_CONTRACT.md` and `DATA_MODEL.md`: these will need the space model.
- `PRIVATE_LAUNCH_RUNBOOK.md`, `docs/specs/private-alpha-ci-cd-sota.md`, `docs/release-manifests/TEMPLATE.md`.
- `docs/specs/lanes/*`: financial, household-permission-policy, document-extraction, financial-ingestion-connectors, account-deletion-fk-census, mvee-five-lane-handoff.
- `docs/specs/cuadrao-accounts-design-lock.md`, `docs/reports/mobile-design-lock-2026-09-28.md`, `.agent/designs/cuadrao/DESIGN.md`.
- `ios/*.md` setup docs.
- `docs/CONVERSATIONAL_RUNTIME.md`, until the agentic lane replaces it.

**Archive candidates:** §A6 list, which I agree with. Add `docs/GUEST_PUBLIC_LAUNCH_SAFETY.md` and `docs/QA_CONVERSATIONAL_TRANSCRIPTS.md` (archive with the guest flow and web chat retirement, not before), `docs/BREAKPOINTS.md` and `.agent/designs/argus/DESIGN.md` (web Argus), and the 146 files in `docs/superpowers/`.

**New, from this half:** the space and ownership spec (§B2, once locked) and `docs/CUADRAO_CODE_MAP.md` (§B1.3). Also commit both source docs (§A7).

**Size:** `docs/reports/evidence/` is ~4,950 files, 2,195 of them PNGs. Consider moving dated evidence out of the main tree (an archive branch or release assets) while keeping the links. `docs/maintenance/docs-classification-inventory.md` already exists as a starting point.

**PR conflicts Maya will hit:** #813 and #808 each **conflict with #790** in `docs/specs/argus-execution-board.md` (`git merge-tree`, Oct 4). #813 and #808 merge cleanly with each other. #790 now merges cleanly with integration; the DESIGN.md conflict in the handoff is gone. #808 L620 (`account_deletion_request`) is left for Lucas to amend.

---

### B9. Open questions only Lucas can answer

Iris's F1-F5 cover segment, e-CF timing, entity, business premium route and Argus web. These are the engineering-specific ones on top:

1. **Lock the space model in §B2**, including the business identity-retention rule. The fiscal retention period needs counsel.
2. **Staging:** TestFlight against the production project (MVEE §1.4 as locked), or reopen §B1.4 for a separate staging project after #811?
3. **Sole-owner deletion:** must a sole business owner transfer ownership or close the business before deleting their account?
4. **Bundle id and name:** confirm `ai.cuadrao.app` and "Cuadrao" (availability unverified). Enroll the Apple team as an organization *before* the first external build (Iris F3, Guideline 5.1.1(ix)). Changing teams later forces a Sign in with Apple migration (#803).

#### Not verified in this draft
- Whether any 20260928+ migration exists in hosted production (no DB access). Hosted Supabase Auth settings, Render dashboard state and `WEB_CONCURRENCY`.
- The App Store Connect record and the availability of the name "Cuadrao". D-U-N-S timing.
- Paddle's availability for a DR entity. Current Render, Supabase and Resend prices (none are quoted on purpose).
- The cuadrao.ai DNS check was a single DNS-over-HTTPS read and one HTTPS attempt, around 12:30 PM CT.
- Size estimates are judgment, not measured.
- Aviso 06-26 / Nov 15 and the DGII process steps come from Iris's refs and the Blueprint. I didn't re-fetch DGII.
