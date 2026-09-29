# Web financial accounts: the first durable account journey

Deliver a development-only account journey using the landed Accounts API and
existing web session, transport, dialog, theme and language owners.

Founder-authorized September 29, 2026 through the delivery-lead implementation
handoff. The flow is settled. Visual polish and PR #732 remain held.

## 1. Why

[PRODUCT](../../PRODUCT.md) sections 1–3 and the
[MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md) Accounts,
quick setup and registered-access sections make manual account records a useful
first step. This slice proves that a person can save, reopen and correct their
own facts without chat, invented activity or a second financial-rule owner.
The accepted backend is PR #735, landed as
`296195e86c972e846c251d256b3cc211975bfd57`.

## 2. Locked decisions

1. Serve `/dev/financial-accounts` using the existing server-side development
   route guard (`notFound()` in production). Production navigation and entry
   points stay unchanged. The server's default-off
   `ARGUS_FINANCIAL_ACCOUNTS_ENABLED` and `financial_accounts_unavailable` response
   remain authoritative; a client flag cannot grant access.
2. Reuse the existing Supabase browser singleton, session refresh/revocation,
   `apiFetch` with `expectedUserId` and abort signal, and `getMe(expectedUserId)`.
   Reuse existing login/signup and guest conversion behavior. Do not invent a
   second token store, auth endpoint, callback or guest claim flow. Registered
   access must be verified by the server before financial data/actions appear.
3. The bounded journey is sign in, list, create, reopen, edit supported metadata,
   add a first opening or correct it with a reason, inspect revision history,
   archive and restore. Unknown and known zero remain distinct. There is no
   account deletion, activity, transaction history or calculated total.
4. Use the API's nine account types and server-owned currency validation,
   precision, nature, locks and accounting rules. Reuse the generated currency
   catalog for choices. The server's decimal-string `amount` is the read owner;
   never convert amounts or bigint minor units through JavaScript Number.
   Formatting changes separators only and never rounds a value.
5. A liability write is positive owed. A signed read value is adapted to that
   input convention using returned `nature`; it is never directly resubmitted
   as positive-owed input. A date-only correction omits unchanged `amount`.
   Preserve untouched stored instants and IANA zones. Nickname clearing sends
   an explicit blank/null PATCH value.
6. Every edit retains the account snapshot the person saw. PATCH sends its
   `expected_version`; opening PUT sends that version and its
   `expected_revision` (null for an initial opening). No automatic version
   advancement, resubmission or overwrite on conflict.
7. Create retries reuse one immutable payload and Idempotency-Key. If the
   outcome is uncertain, keep the attempt separate from edits until the person
   resolves it. PATCH/PUT network or server uncertainty requires a canonical
   reread and explicit reconciliation before another write. Keep the draft and
   show old/current facts for comparison; adopting a newer snapshot is explicit.
8. Keep data and drafts only in memory for the current identity. Abort requests,
   retire late responses and clear all private state when the session changes,
   expires or logs out. A refresh for the same verified identity retains drafts.
   Reopening/reloading reads server truth, with no fixture fallback.
9. Localize code-based RFC 9457 errors, field help and actions in English and
   es-419. Distinguish unavailable, unauthenticated, guest, not found, stale,
   idempotency conflict and validation failures. Schema omission of required
   `expected_version` is tested according to the actual landed 422 response.
10. Use restrained current Argus typography, theme tokens and reusable modal
    behavior. A compact account list/detail layout adapts to tablet/narrow
    widths; no ecosystem-shell promotion or redesign. Reuse #732's presentation
    ideas selectively with provenance; its fixture types and Check balance
    calculation are not compatible API implementations.
11. Existing appearance persistence and profile-owned language remain the only
    preference owners. Support keyboard focus/return, browser navigation,
    scrolling, long labels and increased text. Other ecosystem destinations are
    unavailable here; do not display invented records or imply cross-platform
    sync has already been accepted.

## 3. Reserved / parked scope

- PR #732, its branch, evidence and port 3197 preview are preserved. Its visual
  hold is not acceptance or merge authorization.
- No backend, API schema, migration, auth server/guest-handoff, canonical
  financial-rule, chat/runtime/prompt, billing/analytics/provider edits.
- No imports, activity, transfers, refunds, balance checks, household/space
  permissions, chart adoption, totals or currency conversion.
- No new production destination, hosted changes, deployment or merge. No paid
  provider or model turns. No visual redesign rounds.

## 4. Contract gates and reuse map

The landed [API contract §17.3](../../API_CONTRACT.md#173-financial-accounts-first-slice),
[Data Model §12.1.4](../../DATA_MODEL.md#1214-financial-accounts-first-slice),
[first-slice spec](../../specs/lanes/financial-accounts-first-slice.md), actual
`src/argus/domain/recording/schemas.py` and backend tests own the wire contract.
This client needs no change to those owners or the frozen mobile archive.

| Concern | Read/reuse owner | Lane-owned addition |
| --- | --- | --- |
| Session and verified profile | `web/lib/supabase-client.ts`, `argus-api.ts`, `chat-auth-ownership.ts`, `auth-security.ts` | Accounts request/session invalidation boundary |
| Auth presentation | `web/components/auth/AuthForm.tsx`, existing guest entry/conversion | Route-local presentation/adaptation only |
| HTTP/errors | `web/lib/argus-api-transport.ts` | Focused `web/lib/financial-accounts*` adapter, types and client state |
| Currency choices | `web/lib/home-country.ts` and generated catalog | Lossless input/read formatting, no currency-rule copy |
| Dialogs/focus | `AdaptivePanel`, `useModalSurface`, established controls | Colocated account forms/details |
| Theme/language | Existing theme provider, i18next, profile preference persistence | Namespaced EN/es-419 account copy |
| Development exposure | Existing `/dev` page guard | `/dev/financial-accounts` only |
| Layout provenance | #727 mobile lock; selected account presentation in held #732 | Functional account journey; no imported ecosystem shell/fixture actions |

Allowed writes are focused account files under `web/lib/`, the colocated route,
focused frontend/e2e tests and web-specific spec/report/evidence. Shared production
owners and global tokens are read/reuse dependencies. Coordinate a necessary
shared-file change before editing it. Existing forms use controlled React input;
follow that installed pattern without introducing a form framework solely for
this isolated route. Server validation remains authoritative.

## 5. Execution contract

- **Original fetched integration:**
  `296195e86c972e846c251d256b3cc211975bfd57`.
- **Worker:** `codex/web-financial-accounts` in the attached managed worktree
  `/Users/garces/.codex/worktrees/web-financial-accounts/private-alpha-next`.
  The first commit contains this spec only. One normal labeled implementation
  PR targets `codex/private-alpha-next`; all fixes/evidence stay in that PR.
- **Resource ownership:** dedicated local Supabase project `web-accounts`,
  unique container/project suffix, ports 60400–60419; Next development port
  3198 after a fresh port check. No shared `supabase.env`. Keep generated local
  credentials outside Git with restricted permissions; no hosted credentials.
  Apply only already-landed migrations to this isolated database. Never reset
  shared stacks. Preserve Android 594xx, native 574xx and other existing stacks.
- **Current inspection:** the new checkout has no `.env`/`.env.local` or env
  symlinks; #732 owns the listener on 3197. Owned ports were free at start.
  Recheck before binding. Test/build dependencies may reuse installed packages
  read-only; do not mutate another lane's dependency directory.
- **Delegation:** bounded scouts, separate implementation/test file ownership
  and independent review. The captain owns integration, evidence, PR/review
  disposition and cleanup. Completed agents leave no active follow-up.
- **Deterministic proof:** adapter/payload/error and identity-currentness tests;
  create replay immutability; stale account/opening versions; debt sign/date-only
  correction; explicit nickname clearing; unknown/zero and lossless high values;
  existing frontend lint/tests/build and applicable CI. Avoid repeated broad runs
  when an unchanged surface's evidence remains valid.
- **Real local proof:** registered sign-in via existing auth, known/zero/unknown
  creation, reopen/edit, first opening/correction history, debt amount and
  date-only corrections, archive/restore, precision and date/zone errors,
  flag-off/401/guest403/owner-safe404, stale edit and stale currency/nature opening,
  lost-response create replay, uncertain PATCH/PUT reconciliation, user A/B
  isolation and outstanding-response retirement on identity switch. Prove API
  process restart plus app reload/process restart against durable Postgres.
  Memory/mock tests cannot substitute for this gate.
- **Browser proof:** desktop/tablet/narrow, EN/es-419, Light/Dark/System with
  persistence, keyboard/dialog focus, scrolling/history, long labels and larger
  text; no provider calls. Demonstrate the route is unreachable in a production
  build and production entry points remain intact. A streamed HTTP 200 carrying
  the framework's 404 boundary is not described as a transport 404.
- **Durable evidence:** commit screenshots and interaction records under
  `docs/reports/evidence/<pr>/`, citing exact code head, environment, outcomes and
  limits. If later commits do not alter the accepted surface, explicitly compare
  and revalidate rather than imply a fresh capture. Provide local run commands
  and a non-secret configuration contract for later shared-backend checking.
- **Readiness:** fetch integration again; assess semantic overlap across session,
  transport, data contract, UI, environment and tests; reconcile one way only.
  Preserve history. Check modularity on the resulting merged tree. Run independent
  scoped review and `argus-review-exhaust`; validate findings, fix in-scope
  causes, reply/react/resolve, finish with clean latest-delta review and zero
  unresolved findings. Write the final audit after review and exact-head CI.
- **Stop:** reviewed, unmerged PR. Founder/captain owns later landing and exposure.

## 6. Stop conditions

- A required capability has no landed contract or requires forbidden owner
  changes: report the specific missing seam; do not invent an endpoint.
- Local resources cannot be isolated, require shared/hosted changes, or automatic
  approval rejects a necessary action: preserve state and report the exact block.
- A financial amount cannot stay lossless, identity can leak across accounts,
  or a confirmed uncertainty/concurrency requirement exceeds this client: escalate
  the concrete failure rather than claim acceptance.
- The assigned journey requires reopening #732's design hold or new product
  decisions: keep functional progress bounded and ask the lead for that decision.

## Sources

### Argus authority

AGENTS.md reading order; PRODUCT; DOCUMENTATION_AUTHORITY; MVEE; ARCHITECTURE;
API_CONTRACT §17.3; DATA_MODEL §12.1.4; DESIGN; mobile design lock September 28;
financial-accounts-first-slice; the founder-authorized implementation handoff.

### External inspiration

None. No new design research is needed for this functional continuation.

### Inference

A separate development route is the smallest exposure boundary that proves the
accepted workflow without promoting the held ecosystem shell. Browser request
cancellation plus identity-generation checks are required even when server owner
checks work, because late responses must not repaint another identity's screen.
