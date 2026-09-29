# Android financial accounts

Founder-authorized September 29, 2026 through the delivery lead. One Android
client implementation PR, based on landed account API #735 and session #739.

## 1. Why

Serve MVEE Accounts: a registered person records, reopens and corrects their
financial facts. Connect the existing native foundation to canonical server
records, retaining the September 28 design lock and EN/es-419 support.

## 2. Locked decisions

1. Sign in through the existing session owner; Accounts provides list, create,
   detail, metadata edit, opening entry/correction, archive and restore.
   Active accounts stay in the ordinary list; Manage accounts exposes archived
   accounts. Other destinations remain explicitly sample/unavailable.
2. API_CONTRACT section 17.3 at `296195e86c972e846c251d256b3cc211975bfd57`
   owns payloads. PATCH binds the version the form opened with. Opening PUT
   binds BOTH that account version and opening revision (null when absent).
   Never refresh these silently under an existing draft.
3. Create retries retain an immutable body and Idempotency-Key. Uncertain
   writes and stale conflicts reread current server truth, preserving the
   same-identity draft for explicit reconciliation. No blind overwrite.
4. One SessionController owns credentials, refresh, revocation and identity
   epochs. Add a bounded authenticated-request seam; tokens never enter UI,
   logs or another session store. Hide private content while unverified;
   discard state, drafts and late results when identity retires.
5. Financial state is an in-memory projection of server responses. Relaunch
   restores the session then refetches accounts. No offline financial database,
   synthetic successful writes, totals, activity or direct Supabase writes.
6. Unknown differs from known zero. Money uses exact decimal strings and
   BigDecimal/Long, never Double. Locale controls separators; server owns
   currency validity, precision, nature, signs and accounting. Positive owed
   is the liability input convention; signed response amounts are not flipped
   again on display. Dates preserve their offset and IANA zone.
7. Code-based localized RFC9457 errors preserve draft input and explain next
   actions. 401 uses session recovery; guest403 does not become login failure;
   flagoff404 is unavailable; owner-safe404 never discloses another owner.
8. Preserve default-off local-debug auth and release-disabled configuration.
   Local real-auth/real-Postgres acceptance is explicitly authorized, with
   generated synthetic accounts and already-landed migrations only.

## 3. Reserved / parked scope

No backend/API/schema/migration changes; no auth-server or guest conversion;
no shared canon edits, chat/runtime/prompts, billing/analytics, transactions,
imports, transfers, household, chart/voice integrations, totals or deletion.
No visual redesign, production signing, deployment or hosted configuration.

## 4. Contract gates

Read-only authorities: API_CONTRACT 17.3, DATA_MODEL 12.1.4,
`docs/specs/lanes/financial-accounts-first-slice.md`, MVEE and DESIGN.
Changes owned by this lane: `mobile/android/**`, this Android spec and focused
Android run instructions/report/evidence. A missing contract is escalated.

## 5. Execution contract

- Original fetched integration: `296195e86c972e846c251d256b3cc211975bfd57`.
  Worker: `codex/android-financial-accounts`, clean reused checkout 611c.
  This specification is the first commit; implementation follows in this PR.
- Local ownership: dedicated `Argus_Auth_611c` AVD/emulator5584 (not physical
  hardware), reserved ports59400–59419, unique `android-accounts-611c` stack.
  Inventory found only this lane's old `android-auth-611c` stack on59401–59404;
  safely retire that owned stack before replacement. No shared adb reset or
  other lane's containers/services. Inspect env symlinks before use; launch
  with an explicit local-only environment, never inherited provider secrets.
- Bounded agents own distinct Android modules/tests. Parent integrates,
  verifies independently and owns cleanup; no concurrent edits to owned files.
- Verify build, JVM behavior tests, lint and disabled release. Native real API
  evidence covers known/zero/unknown, exact precision/date-zone, create replay,
  stale metadata and stale currency/nature opening, missing expected_version
  schema rejection, archive/restore, guest/flag/auth failures, A/B isolation,
  delayed responses, API restart and app process restart against Postgres.
- UI: EN/es-419 phone, light/dark, keyboard and large text; durable sanitized
  screenshots under `docs/reports/evidence/android-financial-accounts/`.
  No paid/model calls. Reuse unchanged evidence only with explicit revalidation.
- Leave reproducible local command/config instructions for the captain's
  separate shared-backend cross-surface check; independent Android fixtures
  are not proof of cross-surface synchronization.
- Delivery: normal ready PR, exact-head CI, independent scoped review plus
  clean latest-delta Codex review and zero unresolved threads. Reconcile current
  integration one way, report semantic overlap and verify merged-tree modularity.
  Post terminal audit only after final review. Founder owns merge/deployment.

## 6. Stop conditions

Escalate missing/inconsistent landed contracts, required backend changes,
unowned resources, hosted credentials or production configuration needs.
Do not weaken version/identity/durability guarantees to get green evidence.
Automatic approval rejection is reported with its exact reason, not bypassed.

## Sources

Load-bearing: AGENTS.md, PRODUCT, DOCUMENTATION_AUTHORITY, MVEE, ARCHITECTURE,
API_CONTRACT, DATA_MODEL, DESIGN, September 28 mobile lock, landed first-slice
spec, and the founder-authorized delivery-lead kickoff in this chat.
No external design research or new product approval is required.
