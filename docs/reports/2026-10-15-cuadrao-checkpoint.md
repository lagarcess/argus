# Cuadrao checkpoint, 2026-10-15

Status of Business web, the iPhone app, marketing and launch readiness. This is a snapshot, not a plan. It changes no scope and starts no work.

**Basis**
- Integration tip `a76d5b6cb`, with CI and the local smoke test green.
- Open PRs and issues on GitHub.
- The sprint map of 2026-10-14.
- Public GET requests to staging and to cuadrao.ai on 2026-10-15.

Each claim was checked against a commit, a PR, a test result, a screenshot folder or a live request. Where a fact could not be verified, it says "unverified".

## The short version

- **Business web** is the furthest along, and it runs on staging. An invited owner can upload a receipt, get it read automatically and review it. The accountant side is built, but nobody has walked it on staging. There is no in-app step where the accountant "accepts the period", which is the stated finish line.
- **The iPhone app** has not been on a phone since the 2026-10-12 build. That phone's signing profile has reportedly expired. Guest mode works in the simulator but is switched off in release builds. No build has gone to TestFlight.
- **Marketing**: there is no public website. cuadrao.ai has no web address record, so it serves nothing. The finished site exists only in the repo. Staging's privacy and terms pages still carry the old Argus support address, `support@get-argus.com`, and the old Argus policy text. The iPhone app links to those pages.
- **Launch**: every launch gate is open. The items that block the most are counsel review of the legal pages, published privacy and terms URLs, Apple enrollment, Meta verification and a pricing decision.
- **Decisions from you** unblock more than any engineering task right now. They are listed in section 6.

---

## 1. Business web (/biz) and WhatsApp

### What a user can complete today

Try it at https://cuadrao-web-staging.onrender.com/biz. You need an invited account; the invite list is a table in the staging database. Staging very likely runs `a76d5b6cb`. Its public API description matches that commit exactly, but the commit itself is unverified because Render's tool refused access.

| Flow | Status | Evidence |
|---|---|---|
| Owner uploads a receipt. It is read automatically, opens in review and survives a reload. | Works on staging | #1112. Proven with one synthetic image; one paid read cost USD 0.039. Real photos (crumpled, handwritten, dark) not yet tried. |
| Owner approves a reviewed receipt, and it becomes one saved expense. | Worked on 2026-10-12 | The review screens changed since, so it needs a fresh walk. |
| Owner links WhatsApp, sends a receipt photo, gets it read and answers one follow-up. | You walked it on 2026-10-13 | Works only for Meta test numbers, because the Meta app is unpublished (#941). |
| Owner forwards an email receipt; it lands in the Bandeja and is read with "Preparar con IA". | Walked on 2026-10-13 | That walk is recorded only in open docs PR #1071. Automatic reading of emailed receipts is draft #1083. |
| Sign in and sign out | Walked on 2026-10-12 | Three later fixes not re-walked (#1063, #1064, #1093). |

**Built and probably on staging, but never walked by anyone**
- Accountant invite and the client switcher (#988, #1082, #1084).
- The Personal mark, "Sin comprobante fiscal" and the accountant's 606 answer (#1088, landed overnight).
- The CSV + Excel + receipts export (#973, #974).
- Many files at once, notes, e-CF checks, the DGII QR, duplicates.

**Only locally**
- The fixture preview: run `cd web && bun run dev`, then open `http://localhost:3000/dev/business-preview`.
- #1126, the single review page with matching counts and "RNC desconocido". CI is green, but it hasn't been evaluated or landed.

**Only in tests**
- "Pagué 850" by text (J1) and income by text (J3). Business chat is off, WhatsApp is receipts-only, and no screen creates income.

### Partly built, broken or not started

- **No invite email.** An invited accountant is matched silently when they sign in with that email. Whether a brand-new invited email can create an account on staging is unverified.
- **Password reset** is built (#1119) but switched off on staging. Whether the default reset email arrives is unverified.
- **No "accept the period" action exists.** It is the stated finish line, but there is no screen, route or record for it.
- **Approval is owner-only**, enforced in the database (#1089). The locked plan says a firm can approve per client. See the conflicts in section 7.
- **Copy still on integration**: "¿Cómo quieres que Argus te llame?" and the "Preparar con IA" button. The locked review flow says the button goes away.
- **Open defects**: #1124 (Personal mark ledger), #1118, #1106 (email budget), #1102–#1104 (Inbox polling), #1070.
- **Not started**: design pass on staging web, a staging redeploy and smoke check after each landing, the real-receipt run (needs your yes to pay), "Aprobar y siguiente", supplier memory by RNC, and "aprobar siempre".

### Approved requirements still open (sprint map §1.8)

- **In #1126**: one review page, the read banner shown once, counts that agree, "RNC desconocido".
- **Not done**:
  - Argus wording in the name question.
  - Password reset email.
  - Firm approval per client.
  - Date format and the period label (no evidence either way).
  - The accessibility and layout items: danger group, 44px "Crear", labeled icons, empty states.
- **Done in code, never walked**: the records and the export package.

### Deployed vs local

- **On staging, probably**: everything through #1088.
- **On integration but not on staging**: nothing.
- **In PRs only**: #1126 (review page and counts), #1083 (automatic email reading, draft with conflicts), #1068 (a test), #1081 and #1071 (docs), #925 (chat restrictions).
- **On staging but not in the repo**: two migrations from #1083, which are applied on staging while their files exist only in that PR.

### Next complete customer flow

The owner sends receipts on the web, reviews them on one page and approves them. The invited accountant then:
- opens that client;
- sees each record with its source and marks;
- answers the 606 question;
- downloads the CSV + Excel + receipts package.

This uses only pieces that are already built. What remains:
1. Land #1126.
2. Redeploy staging and record the commit.
3. Make the accountant invite work: hand over or send the invite, and confirm the invited email can sign up.
4. Get password reset to deliver on staging.
5. Run real receipts on staging (paid, needs your yes).
6. Walk the whole flow on one recorded build.
7. Decide what "the accountant accepts the period" means (section 6).

---

## 2. iPhone app (personal and household)

### What a user can complete today

- **TestFlight**: never uploaded. The plan holds TestFlight until the signed-in free tier passes on staging.
- **Your phone**: the last recorded build is `phone-build-ebff591e0`, built 2026-10-12 from a lane commit and pointed at staging.
  - On 2026-10-13 you passed: sign in, add an account, income, an expense, and reordering accounts.
  - You failed: a cash transfer and a credit-card payment. Both are fixed on integration but not re-walked.
  - Plan, Search, receipts and household were never walked on a phone.
  - That build's signing profile reportedly expired 2026-10-13. A new phone build needs you signed in to Xcode.
- **Simulator only**: everything since 2026-10-12. That includes the guest mode work, sign-out isolation, the launch hold and the 130-screen Spanish set.
- **Guest mode**: all 45 guest journeys passed when the consumer lane landed. Since then, one Spanish journey (`testGuestMovementsInSpanish`) fails on integration itself, and no issue is filed yet. Guest mode is off in release builds until you approve opening it.

Where to try it today: only a simulator built from integration. A phone needs a fresh build after you sign in to Xcode.

### Partly built, broken or not started

- **Design pass blockers**:
  - Stacked, differently worded error messages with two "Reintentar" buttons.
  - Development leftovers in release screens: "Vista de desarrollo", sample toggles.
- **12 high findings**: "Transacción" not yet "Movimiento", the first-plan hero showing when plans exist, the tab bar riding above the keyboard, money and date formats that disagree, destructive rows not red, the Recibos empty state not per spec, and more. All are in `cuadrao-ux-audit/screens-2026-10-15/DESIGN_PASS.md`.
- **Language**: an unsupported device language falls back to English. The locked rule is Spanish.
- **Open PRs**:
  - #1123 (guest copy and sheet art slot) was rejected for a grey band under "Ahora no". The one-line fix is known but not applied.
  - #1125 (launch logo stays put) has green CI, but the signed-in cold start is unproven.
  - PR B: Search back is blocked behind #1123, and the currency half waits on you.
- **Eight older iOS PRs have no owner**: #1001, #1003, #1005, #1013, #1025, #1077, #1079 and #1085, last worked on 2026-10-12 or 2026-10-13. Each now shows about 300 changed files against integration, and #1077 looks superseded.
- **Not started**: onboarding, the camera explainer, illustrations, hiding the tab bar with the keyboard, the Plan fixes, grouped Search results, and Spanish fallback.

### Approved requirements still open (sprint map §1.1–1.7)

- **§1.1 Guest mode**:
  - Done in code and on the simulator: first-win trigger, sheet, identity label, sign-out isolation.
  - In #1123: the locked first-open copy and the sheet art slot.
  - Not done: the remaining art slots.
- **§1.2 Onboarding**: not started, by plan.
- **§1.3 Language**: "Español" in Perfil is done. Spanish fallback is not done.
- **§1.4 Search**: recents done; grouped "Todo" results and tab fit not done.
- **§1.5 Lists**: the red swipe is done. The Recibos empty state, the danger group, removing "Vista de desarrollo" and "Movimiento" are not done.
- **§1.6 Launch and session**, which product ranked first:
  - The hold is done, and the logo match is in #1125.
  - The signed-in no-flash check is unproven.
  - Not done: one error with a working "Reintentar", the tab bar with the keyboard, the Plan hero, and the neutral goal at DOP 0.
- **§1.7 Illustrations**: not started; waits on decision D3.

### Deployed vs local

- **On a phone**: the 2026-10-12 lane build only.
- **On integration, not on any phone**: all consumer work since then (landed in #1121).
- **In PRs only**: #1123 and #1125, plus the eight unowned PRs.
- **Local and uncommitted**: PR B's failing Search test.

### Next complete customer flow

The recommended next flow is the guest's first win, finished on a real iPhone:
1. Open the app and choose "Probar sin cuenta".
2. See the first-open note.
3. Add an account.
4. Save the first expense.
5. See "Tus gastos solo están en este iPhone" and choose "Crear cuenta" or "Ahora no".
6. Relaunch: the book is still there.

What remains:
- Fix and land #1123.
- Fix the failing Spanish journey at its cause.
- Land Search back.
- Check the sheet height on a device, because the design pass and #1120 disagree.
- You sign in to Xcode, and we make a new phone build.
- You walk steps 29–34.

Opening guest mode to real users in release builds is a separate decision for you.

The alternative is launch and session (§1.6), which product ranked first. It needs the signed-in proof, one error with a working "Reintentar", the tab-bar fix, the Plan fixes and a signed-in phone walk.

---

## 3. Marketing site, legal and support

### What a visitor can do today

- **cuadrao.ai and www.cuadrao.ai**: nothing. Neither has a web address record. Only email works: mail to hola@cuadrao.ai reaches iCloud.
- **Staging** (https://cuadrao-web-staging.onrender.com): `/privacy` and `/terms` load, but they show the old Argus early-access policy text with the contact `support@get-argus.com`. The iPhone app's privacy links open these pages.
- **The approved bilingual marketing site exists only on integration** (`marketing/`). It has home (Business), personal, contact and privacy pages, in Spanish and English. Draft PR #927, which would publish it, targets `main` and is missing the latest polish round (#984).

### Partly built, broken or not started

- **No Render service** for the marketing site, and no DNS.
- The early-access signup migration was never applied to a hosted database.
- **The Terms page and "Quién es responsable"** are placeholders. There is no support page or form.
- **Legal drafts** are in `docs/legal/`, with placeholders and 24 open questions. Counsel review is not recorded.
- **The business inquiry form** has been mock-tested only, and no hosted email has been sent from `notify.cuadrao.ai`. cuadrao.ai has no DMARC record.
- **Not started**: the pricing note (due 10-16), the provider cost sheet, the pilot note, the five weekly numbers, and logging the 10-13 to 10-15 decisions in the decision log (its last entry is 10-12).

### Deployed vs local

| Surface | Live? |
|---|---|
| cuadrao.ai site | No. Repo only. |
| Marketing privacy page | No. Repo only; publication held. |
| Staging /privacy, /terms | Yes, with old Argus text |
| Legal drafts | No. Repo docs only. |
| Sending domain notify.cuadrao.ai | DNS set up; nothing sent |

---

## 4. Launch readiness by gate

| Gate | Engineering still open | Non-engineering still open |
|---|---|---|
| **First outside business** | The signup acceptance line links to Argus terms; deletion and retention text matches no published page; no accessibility check of Business web; the Business flow in §1 | Counsel DR on one-line acceptance; published privacy and terms URLs (Meta requires one); your "legal pages yes/no"; legal effective date (D10) |
| **App Store submission** | Walk every screen on a real iPhone; demo account; App Store privacy answers matching the privacy page; a paywall (none exists) | D-U-N-S and Apple organization enrollment; published support and privacy URLs; age rating |
| **Anyone pays** | No purchase flow; renewal and cancel terms at the pay button | Pricing (D5); liability and governing law with counsel; DMCA agent |
| **Personal app public launch** | Everything above | The age question |

**Non-engineering work** (owner is you unless noted)
- **Counsel US and DR**: review privacy and both terms, the DR fiscal-records questions and governing law. Not started.
- **Company**: EIN, bank account, move the domain and provider billing to the LLC, IP assignment, CPA questions, D-U-N-S, Apple enrollment, Meta business verification and the WhatsApp production number.
- **Go-to-market**:
  - Follow-ups on the 17 outreach emails, due 10-16.
  - Recruit 3–5 businesses and 1–2 accountants.
  - A design-partner accountant walk.
  - Warm introductions.
- **Product**: the pricing note, the provider cost sheet, the five weekly numbers, an illustration drafts-or-hire decision, the tagline, and social accounts.
- **Device work**: sign in to Xcode, then walk the phone steps.

---

## 5. Running apps and local machine

- **Staging API** (`cuadrao-api-staging`): healthy. Staging web: up. Exact commit unverified (see §1).
- **Production** (`argus-app`, `argus-api` on `main`): the old Argus product, untouched by this sprint.
- **Local Docker**: two database stacks, `argus-qa` (the default for every worktree) and `cuadrao-business-sandbox`. Nine abandoned stacks were removed today with your approval.
- **Free disk**: 164 GB.

---

## 6. Decisions needed from you

**Unblocks work today**
1. **Currency display for PR B.** The design guide only says the code appears once and stays secondary. I recommend `DOP −850.00`. The options were described in chat but never written down; I will lay them out with screenshots before you choose.
2. **The eight unowned iOS PRs.** For each: reconcile, fold into PR B or PR D, or close.
3. **Paid real-receipt run on staging**: a few cents per read. Yes or no.
4. **Sign in to Xcode on your Mac.** Not a decision, but every phone check waits on it.

**Product**
5. **How the accountant "accepts the period"**: the stated finish line has no action in the product.
6. **D6 accountant access**: can an accountant or firm approve? The database is owner-only today; the locked plan says a firm can approve per client.
7. **Proposed, not locked**:
   - 606 suggestions per supplier RNC.
   - No standalone accountant signup.
   - Whether "Preparar con IA" goes away for email too.
8. **Guest mode in release builds**: open it to users, with its privacy review.
9. **D2 onboarding flow** and **D3 illustration drafts vs a paid illustrator**.
10. **The splash tagline**, or logo only.
11. **Blank opening balance**: the code and decision log treat blank as 0.00; the design guide still says "pending founder confirmation".
12. **The guest English copy** in #1123, flagged for product.
13. **Guest plans in the account move**: hand-typed guest goals and budgets have nowhere to go on the server (#1099).
14. **D7 and D8**: deleting a sole owner with a business or household, and deleting a shared plan.

**Business and legal**
15. **D5 pricing.** The note is due 10-16, while the decision log says pricing is deferred.
16. **D10 legal effective date**, and "legal pages yes/no".
17. **Where the legal pages live**: on cuadrao.ai, or temporarily on staging. Meta and Apple both need a stable public URL.
18. **Publishing the marketing site**: refresh and land #927, create the Render service, set up DNS, and apply the signup migration. Each step needs its own yes.
19. **The website headline**: "Cada cuenta. En su sitio." on the site vs "Tus recibos y registros, listos para tu contador." in the sprint map.
20. **Legal open questions** in `docs/legal/OPEN_QUESTIONS.md`: Q1 entity details, Q2 legal contact, Q4 B2B only, Q12 in-app purchase, Q14 active providers, Q21 page URLs, Q22 which documents counsel reviews first.
21. **The pilot date.**

---

## 7. Conflicting instructions

These are flagged here and not resolved.

1. **Is the LLC formed?** The sprint map says "done". The legal open questions, the documentation authority map, the marketing runbook and #941 say it is pending. The site footer already says "© 2026 Cuadrao LLC".
2. **Who builds and lands what.**
   - The sprint map says Codex builds server and web while Claude builds iOS only, then says your 2026-10-15 instruction overrides that.
   - The Business spec says Codex coordinators land PRs.
   - AGENTS.md says the root coordinator alone merges.
   - Overnight, you approved Claude self-landing with an independent review per PR. #1126 is Business work on a Claude branch.
3. **Firm approval.** The decision log (L11) and sprint map §1.8 say a firm can approve per client. The database allows owner-only approval (#1089), and D6 is still open.
4. **"No decision is open."** The Business spec and decision log say this, while the sprint map lists open decisions D2–D11.
5. **WhatsApp scope.** The Business spec says the agent talks to the owner in WhatsApp first and polish waits for J1. Current authority says WhatsApp is receipts-only. Meanwhile, /biz polish is under way.
6. **The "Preparar con IA" button.** It is locked as removed (2026-10-14). It still exists, and #1083 relies on it.
7. **Marketing to `main`.** #927 targets `main`, while the marketing handoff and AGENTS.md say nothing goes to `main` under the current grant.
8. **Pricing.** The decision log says deferred, while the sprint map has a pricing note due 10-16.
9. **Paid AI calls.** AGENTS.md says the development key is pre-authorized within an allowance. The sprint map and #1118 say every paid call needs your yes.
10. **Legal draft owner.** The execution board and #831 name #781. #1029 replaced it and landed, even though its body said "Do not merge". #781 is still open.
11. **Spanish fallback.** It is locked as Spanish; the app falls back to English.
12. **"Transacción" label.** An older add-tray lock uses "Transacción". The sprint map locks "Movimiento" everywhere.
13. **Blank opening balance.** The decision log says blank = 0.00; the design guide says pending.
14. **Guest data moving into an account.** Earlier decision-log entries say it is not built. It now exists behind an off switch (#1098), and the sprint map says to keep its Perfil line hidden for now.
15. **Stale status documents.**
    - The execution board lists an old integration tip and old phone build 3455, and still shows #939 as pending although it landed.
    - #1126's body names an old head.
    - #1081 says there is no Business switcher; #1084 landed one.
    - #1083's body says its migrations are not on staging; they are.
16. **Worktree removal.** A standing rule says to leave worktrees for you. Today you approved removing five finished ones. This is resolved by your approval and noted here only for the record.

---

Evidence notes behind this checkpoint, with file and line for every claim, are kept locally in `docs/sprint/scratch/checkpoint-*.md`. They are not in git.
