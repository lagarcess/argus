# Native readiness audit

**Status:** Read-only investigation report. It proposes work; it does not approve
contracts, select providers, or change the canonical architecture, API, or data
model documents.
**Date:** 2026-09-27
**Question:** How can Argus's existing backend and web capabilities support the
approved native iOS/Android clients and the
[minimum viable ecosystem experience (MVEE)](../specs/argus-minimum-viable-ecosystem-experience.md),
while the existing web/PWA and its behavior are retained?

## 1. Scope, inspected source, and limits

| Item | Value |
| --- | --- |
| Inspected base | `origin/codex/private-alpha-next` at `ab9143c18740c28f582646d405445c01c4c8aff4` ("docs(product): lock MVEE and replace conflicting product guidance (#704)", 2026-09-26) |
| Worktree / branch | Sibling managed worktree, branch `codex/native-readiness-audit` created from the fetched base |
| Environment | Cloud container; source reading only. No services started, no provider calls, no Supabase or Render access, no package installation |
| Assignment direction | iOS: Swift + SwiftUI (UIKit where needed). Android: Kotlin + Jetpack Compose (Android Views where needed). Web/PWA retained. Shared backend, records, permissions, calculations, and conversational runtime |

**Evidence classes used in this report.**

- **Documented**: stated in a canon or contract document. It may describe intent.
- **Implemented**: present in source at the inspected SHA. Statements cite `path:line`.
- **Inferred**: follows from reading code paths but was not executed in this audit.
- **Deployed**: *not verified for anything in this report.* The Render MCP connection failed
  (`ERR_PROXY_TUNNEL`), production access is out of scope, and branch contents do not prove deployment.
  Hosted Supabase Auth settings (captcha provider, JWT lifetime, refresh-token rotation, redirect
  allow-list, email templates) live in the Supabase dashboard and were not inspected. The local
  `supabase/config.toml` disables captcha and uses `jwt_expiry = 3600`; hosted values may differ.

**Short file names.** After first mention, `auth.py`, `conversations.py`, and `agent.py` mean the
modules under `src/argus/api/routers/`; `schemas.py` and `dependencies.py` mean
`src/argus/api/schemas.py` and `src/argus/api/dependencies.py`; bare `web` TypeScript names are under
`web/lib/`.

**Missing documentation pointer.** The native stack named in this assignment has not reached
the base branch. [PRODUCT.md §4](../PRODUCT.md#4-product-principles),
[MVEE §2](../specs/argus-minimum-viable-ecosystem-experience.md#2-product-character-and-platforms),
the [decision log](../specs/argus-decision-log.md) (2026-09-26 row), and
[ARCHITECTURE.md §5](../ARCHITECTURE.md#5-frontend-architecture) ("does not yet select native
frameworks") all record native iOS/Android intent without frameworks, and
[DOCUMENTATION_AUTHORITY.md](../DOCUMENTATION_AUTHORITY.md#what-remains-technical-or-undecided)
still lists "Native app architecture" as undecided. This report therefore treats the explicit
assignment direction as its scope. A founder-approved decision-log entry, and a one-line pointer
from ARCHITECTURE.md §5 to it, are the missing pieces (decision F1 below). This report does not add them.

## 2. Summary

- **The backend is already mostly client-neutral.** Every product route resolves identity through
  one dependency that accepts `Authorization: Bearer <Supabase access token>` before any cookie
  (`src/argus/api/dependencies.py:419`), verifies the token with Supabase, and checks that the
  session row still exists (`dependencies.py:470`). Conversations, messages, activity, chat
  streaming, jobs, runs, history, search, computations, decisions, discovery, profile, usage, and
  feedback can be consumed by a native HTTP client without backend change.
- **Authentication is the blocking surface.** Guest start, sign-in, and sign-up each require a
  Cloudflare Turnstile token that only a browser widget currently produces; guest conversion
  carries its secret in HttpOnly cookies; token refresh, sign-out revocation, password change, and
  password recovery run in the browser's Supabase client or a Next.js route, not in the Argus API.
- **Chat streaming is simple to consume** (data-only SSE, `[DONE]` terminator, keepalive comments,
  RFC 9457 errors), and the documented reconnect rule is "re-fetch messages". Mobile backgrounding
  makes the disconnect path common, and its user-visible result on phones has not been measured.
- **Cards render from structured payloads, not prose**, but the wire types are not machine-published
  (message `metadata` and SSE frames are untyped in OpenAPI), and a meaningful share of display
  composition (result readout fallback, recovery copy, recovery actions, localized labels) lives in
  web TypeScript and the web i18n catalog. Porting that logic twice would create three copies of one fact.
- **No upload or file-ingestion capability exists.** Financial accounts, transactions, plans,
  households, sharing permissions, notifications, and device registration have no implemented
  contract. Those remain undefined and are listed as decisions, not as native prerequisites.

## 3. Capability table

Status key: **Reuse** = consumable unchanged by a native client; **Adapt** = bounded
adaptation needed; **Missing** = no implemented capability.

| Capability | Current owner | Endpoint / payload | Browser dependency | Status | Source evidence |
| --- | --- | --- | --- | --- | --- |
| Identity resolution | `current_user` dependency | `Authorization: Bearer` or `sb-*auth-token` cookie; 401/403/503 Problem Details | Cookie fallback only | Reuse | `src/argus/api/dependencies.py:393-533` |
| Session liveness | `auth_session_is_active` | Reads `auth.sessions` by JWT `session_id` | None | Reuse | `src/argus/api/auth_sessions.py:27-76` |
| Guest start | `POST /auth/guest` | `{captcha_token, language}` → Supabase session JSON + cookies | Turnstile widget for token | **Adapt** | `src/argus/api/routers/auth.py:184-290`; `src/argus/api/schemas.py:1057-1059`; `web/lib/guest-captcha.ts:1-35` |
| Sign-in / sign-up | `POST /auth/login`, `POST /auth/signup` | `{email, password, captcha_token}` → `{user, session}` | Turnstile; response also sets cookies | **Adapt** | `auth.py:746-920`; `schemas.py:983-1003` |
| Guest conversion | `POST /auth/guest/handoffs`, `/auth/guest/signup`, `/auth/login`, `/claim` | Handoff id and secret in HttpOnly cookies, `path=/api/v1/auth` | Cookie jar | **Adapt** | `auth.py:298-392`, `auth.py:603-604`, `auth.py:861-862` |
| Token refresh | Browser Supabase client | Supabase Auth `refresh_token` grant, anon key | `@supabase/ssr` browser storage | **Adapt** | `web/lib/argus-api-transport.ts:33-53`; `web/lib/supabase-client.ts`; `web/lib/argus-api.ts:570-590` |
| Logout / revoke | Browser Supabase `signOut` + `POST /auth/logout` | Backend only deletes cookies | Browser client | **Adapt** | `auth.py:940-946`; `web/lib/argus-api.ts:711-719`; `web/lib/auth-security.ts:44-80` |
| Password change / recovery | Supabase `updateUser`; Next.js `POST /api/auth/recovery` | Recovery link targets web `/auth/recovery` | Next route, web origin | **Adapt** | `web/lib/auth-security.ts:97-150`; `web/app/api/auth/recovery/route.ts`; `supabase/config.toml:165-175` |
| Profile, usage, market session | `profile`, `market` routers | `GET/PATCH /me`, `GET /me/usage`, `GET /market/session`; returns `account_kind`, guest limits, `capabilities` | None | Reuse | `src/argus/api/routers/profile.py:50-67`; `docs/API_CONTRACT.md` §8 |
| Conversations | `conversations` router | CRUD, `/guest/replace`, cursor pages | None | Reuse | `src/argus/api/routers/conversations.py:169-530` |
| Messages / hydration | `GET /conversations/{id}/messages` | Cursor or `anchor_message_id`; `Message.metadata: dict[str, Any]` | None | Reuse (untyped) | `conversations.py:666`; `schemas.py:324-330`; `docs/API_CONTRACT.md:3437` |
| Activity / attention | `conversation_activity` router | `latest_message_id`, `operation`, `attention`; `mark_read`/`mark_unread` | None | Reuse | `src/argus/api/routers/conversation_activity.py:68-110`; `docs/API_CONTRACT.md:3259-3341` |
| Chat turn stream | `POST /chat/stream` | `data:` frames `stage_start`, `token`, `stage_outcome`, `final`, `error`, then `[DONE]`; `: keepalive` comments; `Idempotency-Key`, `X-Request-Id` | None | Reuse | `src/argus/api/routers/agent.py:265`; `src/argus/api/chat/streaming.py:7-16`; `docs/API_CONTRACT.md:3467` |
| Structured actions | `ChatActionPayload` | `{type, label?, labelKey?, payload}` with typed ids (confirmation, run) | None | Reuse | `schemas.py:751-763`; `docs/API_CONTRACT.md:3589` |
| Confirmation edits | Confirmation routes | `/confirmations/{id}/direct-edit`, `/peer-assets` | None | Reuse | `conversations.py:851`, `conversations.py:1092` |
| Tool-result cards and recompute | `tool_result_cards` + recompute route | Backend-localized `presentation`, sources, `repair` | None | Reuse | `src/argus/domain/tool_contracts.py:86`, `:173`; `src/argus/api/routers/tool_results.py:56`; `docs/API_CONTRACT.md:3496-3587` |
| Backtest / research jobs | Backtest router | `GET /backtest-jobs/{id}`, `/by-action/{confirmation_id}`, `GET /backtests/{run_id}`; research answer as `result_message` | None (polling) | Reuse | `src/argus/api/routers/backtest.py:613-719`; `docs/API_CONTRACT.md:5029-5075` |
| Run dossiers | Conversations router | `GET /conversations/{id}/run-dossiers` | None | Reuse | `conversations.py:531`; `docs/API_CONTRACT.md:3354` |
| History / Recents | `GET /history` | Cursor pages with activity projection | None | Reuse | `src/argus/api/routers/history.py:63` |
| Omnisearch | `GET /search` | Typed rows with `conversation_id`, `message_id`, `run_id`, dossiers, ledger groups | None | Reuse | `src/argus/api/routers/search.py:53`; `docs/API_CONTRACT.md:5816` |
| Computations / decisions | `computations`, `decisions`, `evidence` routers | answers list, compare, continue, refresh, rerun, decision save/open | None | Reuse | `src/argus/api/routers/computations.py:46-104`; `src/argus/api/routers/decisions.py:28-135`; `src/argus/api/routers/evidence.py:16` |
| Composer mentions | `discovery` router | `GET /discovery/assets`, `/discovery/indicators` | None | Reuse | `src/argus/api/routers/discovery.py:46-83` |
| Client capability handshake | `X-Argus-Client-Capabilities` | Additive presentation opt-in (`dossier_decision_conversion_v1`) | None | Reuse | `src/argus/api/client_capabilities.py:9-49`; `web/lib/argus-api-transport.ts:13-31` |
| Result readout text | Web `result-readout-*` | Uses backend `result_readout_content` when its language matches; otherwise composes from `result_fact_bank` + web i18n | Web i18n catalog | **Adapt** | `web/lib/artifact-response-transport.ts:8-22`; `web/lib/result-readout-display.ts:16-40`; `docs/API_CONTRACT.md:5042-5051` |
| Recovery copy and actions | Web `chat-recovery-display.ts` | Derives display text and action options from typed metadata codes | Web i18n catalog | **Adapt** | `web/lib/chat-recovery-display.ts:103-700` (1,116 lines) |
| Localized labels | Web i18n catalog (1,723 `en` keys) | Backend emits `locale_key` / `label_key` into that namespace | Bundled with web | **Adapt** | `web/public/locales/en/common.json`; `docs/API_CONTRACT.md:3513-3517` |
| Shared display policy | `argus_display_contract` package | JSON read by backend and web build | None | Reuse | `web/argus_display_contract/result_display_policy.json`; `src/argus/domain/result_money.py:19`; `pyproject.toml:10` |
| Temporary chat (memory opt-out) | Web localStorage | `memory_opt_out` flag per request | `localStorage` | **Adapt** | `web/lib/browser-storage.ts:33-46`; `web/lib/argus-api.ts:1041`; `schemas.py:840-842` |
| Memory controls | `personalization_memory` router | role-gated settings, records, export JSON | None | Reuse | `src/argus/api/routers/personalization_memory.py:108-379` |
| Feedback | `POST /feedback` | Text + bounded context; no attachments | None | Reuse | `src/argus/api/routers/feedback.py:19`; `schemas.py:953-968` |
| Public receipts | `evidence_receipts`, `public_receipts` routers | Owner create/revoke; public view at web `/r/[receiptId]` | Web page for viewing | Reuse | `src/argus/api/routers/evidence_receipts.py:145-357`; `web/app/r/` |
| File upload / ingestion | none | none | n/a | **Missing** | No `UploadFile`, multipart route, bucket, or file input found in `src/`, `web/`, or `supabase/migrations/` |
| Financial records, household, sharing | none | none | n/a | **Missing** | [DOCUMENTATION_AUTHORITY](../DOCUMENTATION_AUTHORITY.md#what-remains-technical-or-undecided) |
| Notifications / device registration | none | none | n/a | **Missing** | No user-facing notification or device-token code found in `src/`, `web/lib/`, `web/components/`, or `supabase/` (`src/argus/api/feedback_notification.py` only emails feedback to the team) |
| Account deletion | Feedback type | `type: "account_deletion_request"` | None | **Adapt / decision** | `schemas.py:954` |

## 4. Answers to the eight questions

### 4.1 What native clients can consume unchanged

All `/api/v1` product routes in the table marked **Reuse**. The shared properties that make this true:

- Bearer auth is first-class (`dependencies.py:419-421`); cookies are a fallback.
- The auth-origin guard admits requests that carry no `Origin` header (`auth.py:923-937`), which is
  the normal native case. CORS is irrelevant to native HTTP clients.
- Errors are flat RFC 9457 bodies with `code` and `request_id` (`src/argus/api/app_setup.py:94-105`),
  plus `Retry-After` on 429.
- Identity for navigation is typed: search, history, activity, and jobs return conversation,
  message, run, and job ids rather than web URLs, so native deep links can target ids.
- Account class and capabilities come from the server (`profile.py:50-67`), so native gating can
  render them without re-deriving guest policy.
- The `X-Argus-Client-Capabilities` handshake already lets a client opt into additive presentation;
  native clients can declare the same tokens as they reach parity.

### 4.2 What depends on Next.js, cookies, storage, browser events, or frontend-only logic

| Dependency | Where | Native consequence |
| --- | --- | --- |
| Cloudflare Turnstile browser widget | `web/lib/guest-captcha.ts:1-35`; required by `schemas.py:986,1003,1058,1151` | No native path to guest start, sign-in, or sign-up |
| HttpOnly handoff cookies | `auth.py:343, 369-389, 417, 603-604, 861-862` | Guest conversion needs a cookie jar or another secret transport |
| Browser Supabase session storage and auto-refresh | `web/lib/supabase-client.ts`; `argus-api-transport.ts:40-48` | Native owns token storage and refresh |
| Next.js route for password recovery | `web/app/api/auth/recovery/route.ts`; `auth-security.ts:141` | Native recovery request has no Argus API endpoint |
| Web-origin email links | `supabase/config.toml:165-175`; no `web/public/.well-known/` | Confirmation and recovery links open the web, not the app |
| localStorage-only temporary chat | `browser-storage.ts:33-46`; `argus-api.ts:1041` | Opt-out does not follow the user across devices |
| Client-side readout, recovery, and action projection | `artifact-response-transport.ts:8-22`; `chat-recovery-display.ts` | Must be ported or moved server-side (§6 G6) |
| Web i18n catalog as key namespace | `web/public/locales/*/common.json` | Native needs the same keys or resolved strings |
| Markdown rendering policy | `web/components/chat/ChatMessage.tsx:272` (react-markdown, GFM) | Native renderers must match content and image policy ([#688](https://github.com/lagarcess/argus/issues/688)) |
| Tab/account-scope epochs | `web/lib/chat-request-session.ts:209-216` | Native needs equivalent account-scoped cache invalidation |

`web/proxy.ts` only hides a dev route in production and is not a native dependency.

### 4.3 Bounded adaptation for auth, refresh, logout, guest chat, and account switching

```text
Web today
 Browser ──Turnstile widget──▶ token
 Browser ──POST /auth/login {email,pw,captcha}──▶ Argus API ──▶ Supabase Auth
 Browser ◀── {user, session{access,refresh}} + Set-Cookie sb-* ──
 Browser ──supabase.auth.setSession()──▶ browser storage
 Browser ──Bearer access──▶ Argus API (every call)
 Browser ──supabase refresh (anon key)──▶ Supabase Auth          (no Argus API involvement)
 Browser ──supabase.auth.signOut()──▶ Supabase Auth (revokes)  + POST /auth/logout (clears cookies only)
```

- **Sign-in and sign-up**: the API returns the session in JSON (`argus-api.ts:570-590` reads it),
  so a native client can store tokens in Keychain/Keystore. The only blocker is the captcha token (G1).
- **Refresh**: implemented only in the browser Supabase client. The smallest adaptation that matches
  today's web ownership is for native clients to refresh directly against Supabase Auth with the
  public URL and anon key, as the web does. The alternative is an Argus refresh endpoint. Either is a
  founder/architecture choice (F3). Note that `supabase/config.toml:183-186` enables refresh-token
  rotation with a 10-second reuse window locally; concurrent refreshes from one app must be serialized.
- **Logout**: `POST /auth/logout` deletes cookies and does not revoke (`auth.py:940-946`). Revocation
  is a Supabase `signOut`. Because `current_user` checks `auth.sessions`, a revoked access token fails
  on the next call (`dependencies.py:470-490`). A native logout must revoke, not merely discard tokens.
- **Guest chat**: after guest start (G1), guest turns are ordinary bearer calls. Guest limits and
  capabilities arrive from `/me`. Guest allowances key on the trusted client IP
  (`src/argus/api/client_ip.py:1-15`, `src/argus/domain/visitor_usage.py:33-37`), the same for native and
  mobile web; this is existing behavior, not a native prerequisite.
- **Guest conversion**: the handoff secret is issued and read only as HttpOnly cookies. A native
  client with a persistent, per-account cookie jar could complete it without backend change, but
  the same jar would also capture `sb-auth-token` cookies that `current_user` accepts when no bearer
  is sent (`dependencies.py:422-445`). The smallest safe choices are (a) a jar limited to
  `/api/v1/auth` with `sb-*` cookies discarded, or (b) an additive body/header transport of the
  handoff secret for bearer clients. Either needs an owner decision (F4).
- **Account switching**: the server is stateless per request. The client must drop tokens, stop
  in-flight streams, and discard account-scoped caches before issuing a new identity. The web does
  this with an account epoch (`chat-request-session.ts:209-216`) and still has a stale-tab resend gap
  ([#688](https://github.com/lagarcess/argus/issues/688)).

### 4.4 Streaming, cancellation, reconnects, retries, errors, and hydration

```text
Native ──POST /chat/stream (Bearer, Idempotency-Key, X-Request-Id)──▶ API
  API: auth → validation → quota → durable user message + lifecycle row (accepted)
  API ──data: {"type":"stage_start"...}  data: {"type":"token"...}  ": keepalive"──▶ Native
  API ──data: {"type":"final","payload":{...message_id...}}  data: [DONE]──▶ Native
  On failure: data: {"type":"error", code, message, message_id, recovery, retry_last_turn?} then [DONE]

Disconnect ─▶ documented rule: GET /conversations/{id}/messages (no token replay)
           ─▶ GET /conversations/{id}/activity: compare latest_message_id, read operation status
           ─▶ run_backtest only: GET /backtest-jobs/by-action/{confirmation_id}
```

- **Implemented**: data-only frames and keepalives (`streaming.py:7-16`), a 120-second runtime event
  timeout (`agent.py:157`), durable lifecycle states and a 15-minute stale-turn reconciler that runs
  on the next POST or message read (`docs/API_CONTRACT.md:537-640`), and retry by
  `failed_assistant_id` (`docs/API_CONTRACT.md:3467-3494`).
- **Inferred, not executed**: when the response generator closes, the threaded runtime worker is
  cancelled (`src/argus/api/chat/runtime_worker.py:111-125`). Only the result breakdown is explicitly
  shielded (`agent.py:1018`) and tested to survive disconnect (`tests/test_result_breakdown_jobs.py:60`).
  An ordinary turn cut off before its terminal message persists stays `running` until the reconciler
  marks it `abandoned` with a retry offer (`tests/test_chat_turn_route_matrix.py:1090`).
- **Phone impact**: backgrounding the app during an answer is routine on iOS and Android. Under the
  inferred behavior, the user returns to a conversation shown as working for up to 15 minutes and
  then a retry prompt. A resend with a new `Idempotency-Key` spends another turn
  ([#700](https://github.com/lagarcess/argus/issues/700)). Mobile web shares this path.
- **User cancellation**: there is no stop-generation endpoint and no web stop control; aborts occur
  only on navigation or account change. Confirmation cancellation is a structured action
  (`src/argus/api/chat/cancellation.py`).
- **Async work**: backtests and thorough research are durable jobs; native polls
  `GET /backtest-jobs/{id}`, as the web does. Supabase Realtime is documented as the target but is
  not wired (`docs/API_CONTRACT.md:1879-1881`).

### 4.5 Rendering stages, cards, citations, assumptions, and actions from payloads

Yes for data, partially for presentation.

- **Authoritative and structured**: result cards and run facts, confirmation cards, tool-result
  cards (backend-localized `presentation`, per-fact `source`, typed `repair`), research sources,
  `next_experiments` rows with `label_key`, `send_text`, and typed reasons, recovery codes, and
  structured actions. No reviewed web path reconstructs strategy meaning from assistant prose.
- **Stages**: `stage_start` carries a stage name and, for tools, `{locale_key, interpolation_args}`;
  copy is chosen client-side from the web catalog.
- **Composed in the web client from typed facts**: the result Quick take and Breakdown fallback
  (`result-readout-display.ts:16-60`), recovery sentences and recovery action options
  (`chat-recovery-display.ts:103-700`), and assumption text. These are deterministic projections of
  typed data, not prose parsing, but they exist only in TypeScript.
- **Wire typing gap**: `Message.metadata` is `dict[str, Any]` (`schemas.py:330`), the SSE 200 body is
  `type: string` (`docs/api/openapi.yaml:461-463`), and the web hand-maintains its view types
  (`web/components/chat/types.ts`, 415 lines). Pydantic models already exist for several parts
  (`ToolResultCard`, `ToolProgress`, `ResearchSource`), but no published schema covers the envelopes.

### 4.6 How history, search, calculations, research, and backtests connect

All four connect through ids that resolve to one conversation transcript:

```text
/search row ──conversation_id, match.message_id, dossier.run_id / result_message_id──┐
/history row ──conversation_id, latest_message_id, activity──────────────────────────┤
job poll ──result_run_id (backtest) | result_message (research)─────────────────────┤
                                                                                     ▼
GET /conversations/{id}/messages?anchor_message_id=…  →  metadata.result_card / tool_result_cards / computation
GET /backtests/{run_id}, GET /conversations/{id}/run-dossiers, GET /decisions/{id}
```

A native client can open any search or history result by id and render the anchored transcript
page. Computed answers carry `metadata.computation` and are listed by `GET /computations/answers`.

### 4.7 Uploads and files today versus planned ingestion

**Today:** none. No upload route, multipart handling, Storage bucket, migration touching
`storage.*`, or file input exists. Supabase Storage is enabled in local config with no buckets
(`supabase/config.toml:116-126`). Feedback accepts text and bounded JSON context only. The only
file-like output is `GET /memory/export` (JSON attachment) and public receipt pages.

**Planned (MVEE §4.4-4.5):** statements, CSV-type files, PDFs, images, camera scans. Provider,
format, retention, storage, extraction, review, and confirmation contracts are all undefined.
Native camera and document capture have nothing server-side to send to yet.

### 4.8 Existing contracts that support the pivot, and what remains undefined

**Supports:** bearer identity, owner-scoped conversations and messages, durable turn lifecycle,
structured actions with confirmation cards (a working capture → review → confirm pattern for
simulations), tool-result cards with sources and recompute, jobs, Omnisearch with typed rows and
dossiers, computed answers and decisions, the client-capability handshake, Problem Details, and the
shared display-policy package.

**Undefined:** financial accounts, transactions, balances, currency handling for DOP/USD records,
plans (budget, goal, debt), households, membership, sharing and edit permissions with RLS,
chat-to-record proposal and confirmation actions, file and voice ingestion, notification inbox and
delivery, device registration, and account deletion. The
[authority map](../DOCUMENTATION_AUTHORITY.md#what-remains-technical-or-undecided) already names
these as open. The existing `AccountCapabilities` (`schemas.py:191`) is a guest/registered switch,
not a resource permission model, and should not be stretched into household permissions.

## 5. Documented intent versus implementation discrepancies

| Statement | Where documented | What the source shows |
| --- | --- | --- |
| Notifications are "Hidden/flagged for Alpha" | [PRODUCT.md](../PRODUCT.md#current-production-availability-and-planned-changes) | No user-facing notification inbox, delivery, or flag code was found in `src/`, `web/lib/`, or `web/components/` at this SHA. Either it lives elsewhere or the row describes a design surface. Owner should confirm |
| Supabase Realtime is the job-status target transport | `docs/API_CONTRACT.md:1879` | Polling only |
| Auth transport "Supabase Auth session cookie or bearer token" | `docs/API_CONTRACT.md:67-75` | Accurate for requests; refresh, revoke, and recovery are outside the Argus API |

## 6. Contract gaps

Ordered by how directly they block the native clients while preserving existing behavior.

| # | Gap | User impact | Smallest plausible adaptation |
| --- | --- | --- | --- |
| G1 | Captcha token only obtainable from the Turnstile browser widget | Native users cannot start a guest chat, sign in, or sign up | Decide the native bot-protection path (F2); then an additive contract note. No backend change if the token stays a Turnstile token |
| G2 | Session refresh, revoke, password change, and recovery live in the browser Supabase client and a Next.js route | Native sessions expire hourly (local config) with no documented refresh path; logout could leave refresh tokens live | Document the native session contract: either direct Supabase Auth use mirroring web, or thin Argus endpoints (F3) |
| G3 | Guest handoff secret travels only as HttpOnly cookies | Guest-to-account conversion loses the temporary conversation on native unless a jar is managed | Scoped cookie jar with `sb-*` discard, or additive body/header transport for bearer clients (F4) |
| G4 | Email confirmation and recovery links target the web origin; no app/universal link association | Users leave the app to finish signup or recovery | Decide web-completion versus app links (F5); association files are web-hosted assets |
| G5 | Ordinary turn continuity across disconnect is unmeasured on phones | Backgrounded answers may show "working" up to 15 minutes, then a paid retry | Measure first (WP-D). Only then decide whether server-side completion after disconnect is warranted |
| G6 | Deterministic presentation composed in web TypeScript from typed facts | Native must port well over 1,000 lines of TypeScript per platform, creating three owners of the same copy | Inventory projections; per projection, choose backend-resolved text or a shared catalog plus ported template (F6) |
| G7 | Wire payloads untyped in OpenAPI | No generated Swift/Kotlin models; drift found only at runtime | Publish JSON Schema for SSE frames and metadata envelopes from existing Pydantic models, plus golden fixtures |
| G8 | Web i18n catalog is the de-facto key namespace for backend `locale_key`/`label_key` | Native strings drift from web or show raw keys | Package the catalog as a shared contract, like `argus_display_contract` |
| G9 | Temporary chat opt-out is device-local | Opt-out on one device is ignored on another | Decide device-local versus account-synced (F7) |
| G10 | Account deletion only by feedback request | App-store review risk; unclear user path | Founder decision on in-app deletion scope (F8) |
| G11 | No upload, record, household, permission, notification, or device contracts | New MVEE surfaces cannot be built on either platform | Contract definition packages after founder decisions; not native prerequisites |

## 7. Proposed independent work packages

These are proposals for assignment, not created issues. Each preserves existing web behavior.

### WP-A Native session and guest-entry contract

- **Outcome:** a written, reviewed contract that lets a bearer-only client start a guest session,
  sign in, sign up, refresh, revoke, recover, convert a guest, and switch accounts.
- **Owns:** a new API_CONTRACT §7 subsection (by its owner), any additive handoff transport in
  `src/argus/api/routers/auth.py` and `schemas.py`, and tests.
- **Prerequisites:** F2, F3, F4, F5.
- **No-touch:** interpreter prompts and schema descriptions, LangGraph runtime, web auth UI,
  cookie names in `browser_cookies.py` (unless the privacy disclosure is updated with them).
- **Acceptance evidence:** a scripted bearer-only client (no cookies, no `Origin`) completing guest
  start → turn → handoff → signup/login → claim → logout-with-revocation against a local stack;
  existing auth, guest, and cookie-disclosure tests unchanged and green.

### WP-B Wire-format schemas and golden fixtures

- **Outcome:** machine-readable schemas for SSE frames, `final` payload, and message metadata
  envelopes (result card, confirmation, tool-result card, recovery, research sources, next
  experiments, backtest job sidecar), plus recorded fixtures per card and failure type.
- **Owns:** a generated schema artifact and a test that validates existing test payloads against it.
- **Prerequisites:** none.
- **No-touch:** runtime behavior, `Field(description=...)` text in the eval-reachable tree
  (AGENTS.md Never-Violate 12 applies if touched), web types.
- **Acceptance evidence:** schema test green; OpenAPI structural gate unchanged; fixtures cover en
  and es-419 and at least one non-buy-and-hold strategy.

### WP-C Presentation ownership inventory

- **Outcome:** a list of every client-side projection from typed payloads to text or actions,
  with a per-item recommendation (backend-resolved or shared catalog plus template), and a packaged
  shared locale catalog.
- **Owns:** a docs report and catalog packaging similar to `web/argus_display_contract/`.
- **Prerequisites:** F6.
- **No-touch:** visible web copy and layout, backend prose, model-facing text.
- **Acceptance evidence:** inventory cross-referenced to files; a test proving backend-emitted
  `locale_key`/`label_key` values exist in the packaged catalog for both languages.

### WP-D Mobile turn-continuity measurement

- **Outcome:** evidence of what a disconnect does to ordinary, research, breakdown, and
  `run_backtest` turns in hosted-parity mode, and what the user sees on return.
- **Owns:** a deterministic test or local-stack harness and a findings report.
- **Prerequisites:** none. Coordinate with [#700](https://github.com/lagarcess/argus/issues/700).
- **No-touch:** runtime code during measurement; paid provider calls and Render workflow dispatch.
- **Acceptance evidence:** mocked or synthetic-provider runs per turn type showing lifecycle
  state, persisted messages, activity projection, and allowance usage after disconnect.

### WP-E Ecosystem contract definitions (records, households, ingestion, updates)

- **Outcome:** separate, bounded contract proposals for financial records, household permissions,
  file ingestion, and notifications/device registration, each client-neutral.
- **Prerequisites:** MVEE §9 decisions for each area; WP-A for identity assumptions.
- **No-touch:** existing chat, simulation, and search contracts; legacy Strategy/Collection rows.
- **Acceptance evidence:** reviewed contract documents; no implementation.

## 8. Decisions needing founder input

| # | Decision | Why it blocks |
| --- | --- | --- |
| F1 | Record the native stack (Swift/SwiftUI with UIKit, Kotlin/Compose with Views) in the decision log and point ARCHITECTURE §5 to it | Canon docs still say native frameworks are unselected |
| F2 | Bot protection for native guest start and sign-in: keep Turnstile via an embedded web view, or approve another mechanism | G1 blocks all native entry |
| F3 | Whether native apps call Supabase Auth directly for refresh, revoke, and password changes (as web does), or through Argus endpoints | Determines who owns native session lifecycle |
| F4 | Guest-conversion secret transport for native (scoped cookie jar or body/header) | Preserves the guest conversation on signup |
| F5 | Where email confirmation and password recovery complete for native users (web or in-app links) | Determines association files and redirect allow-list changes |
| F6 | Presentation ownership: backend-resolved localized text versus a shared catalog with ported templates | Avoids three copies of result and recovery copy |
| F7 | Temporary chat (memory opt-out): device-local or account-synced | Consistency across devices |
| F8 | In-app account deletion scope for store submission | Only a feedback-request path exists |
| F9 | Acceptable behavior for answers interrupted by app backgrounding, after WP-D evidence | Cost versus continuity trade-off |

Guest onboarding, offline synchronization, financial schemas, notification providers, and ingestion
providers are deliberately not selected here.

## 9. Related issues and pull requests

| Item | Relevance |
| --- | --- |
| [#700](https://github.com/lagarcess/argus/issues/700) Dedupe ordinary chat turns by Idempotency-Key | Native reconnect/resend currently spends another turn |
| [#688](https://github.com/lagarcess/argus/issues/688) Remote Markdown images; stale tab resend under new account | Same rendering and account-switch rules apply to native |
| [#686](https://github.com/lagarcess/argus/issues/686), [#671](https://github.com/lagarcess/argus/issues/671), [#676](https://github.com/lagarcess/argus/issues/676) | Client-IP trust and rate-limit keying affect native and mobile web equally |
| [#640](https://github.com/lagarcess/argus/issues/640) Keep an observing conversation fresh | Same activity/freshness contract native clients will poll |
| [#687](https://github.com/lagarcess/argus/issues/687), [PR #706](https://github.com/lagarcess/argus/pull/706) Private content in logs | MVEE privacy rules for records and documents |
| [#701](https://github.com/lagarcess/argus/issues/701) Closed analytics event registry | Native analytics events should join the same registry |
| [PR #672](https://github.com/lagarcess/argus/pull/672) Docs accuracy and draft Wave 1 roadmap | Open docs PR touching roadmap context; avoid overlapping edits |
| [PR #705](https://github.com/lagarcess/argus/pull/705) Docs-only CI hardening | Affects how this report's PR is gated |

No open issue or pull request on native clients, mobile auth, uploads, or financial records was
found at the time of this audit.

## 10. Verification performed

- Every `path:line` reference above was read at `ab9143c`.
- Relative documentation links in this report were checked to resolve to existing files.
- The docs-reading pytest selection (`.github/docs-reading-tests.sh`, 42 files) could not run locally: project dependencies are not installed in this container and installation was out of scope. CI owns that gate.
- No runtime, test, or migration file was changed; no service was started; no provider was called.
