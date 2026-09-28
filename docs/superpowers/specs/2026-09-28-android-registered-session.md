# Android registered-session continuation

Connect the accepted native Android shell to existing Argus registered sessions,
with secure relaunch, profile hydration, refresh, sign-out and browser recovery.
Founder authorization was recorded in the Android launch chat on September 28,
2026 and relayed through the Project delivery lead. This is one bounded client
implementation; financial-account wiring remains with its accepted later contract.

## 1. Why

PRODUCT sections 3–5 and MVEE sections 2–3 approve native clients that carry the
same user/session and profile truth as the existing product. Foundation #730
landed as `a8e09b72339c7bc676715dabf8a9cceaac81cf03`; server session-isolation
fix #728 landed as `4e024a4e2837058e73c4be6c528fc41f24d7a03e`. This lane connects
those existing capabilities without a second auth service or financial model.

## 2. Locked decisions

1. Branch `codex/android-auth-continuation` starts from fetched integration
   `19550f28e344c1004dd3ea366625c25fae4b3355`. Spec precedes implementation.
2. Keep the accepted five-tab shell, native Back, appearance and bilingual
   controls. Account/session access lives under Profile & settings. Signing in
   is optional; do not make the existing sample chat an auth-first entry point.
3. Registered entry uses existing `POST /api/v1/auth/login`, then bearer-bound
   `GET /api/v1/me`. Argus owns validation, policy, profile and capabilities.
   No direct provider password-login bypass. Only fields required for profile
   display are projected, ignoring additional server fields without inventing them.
4. Supabase Kotlin SDK owns import, refresh and real session revocation. Use a
   compatible pinned SDK (3.2.6 initially, verified against foundation Kotlin
   2.2/AGP 9.1/API 36 before acceptance). No code copied from #726's auth probe.
5. One device-only Android Keystore/AES-GCM session store; no tokens/passwords
   in logs, saved UI state, screenshots, backups or plaintext preferences.
   Network, cryptography and disk I/O stay off the main thread. Password form
   state is ephemeral and cleared after submission/exit; profile is memory-only.
6. Serialize SDK session mutations and bind each response to an identity epoch.
   Never render stale /me data after sign-out/switch. Retire private UI and caches
   immediately when sign-out begins. Revocation failure is visible/retryable;
   local deletion must not claim server revocation. Account switch completes
   sign-out before the next registered sign-in.
7. Relaunch restores securely, refreshes via the SDK when needed, and verifies
   /me before showing private profile. Explicit rejection clears invalid session;
   transient network/verification failure preserves recoverability without
   showing another account's data. Same-user refresh does not change ownership.
8. Browser recovery opens the existing web forgot-password entry and keeps the
   complete PKCE recovery flow in that browser; users return for fresh native
   sign-in. No native recovery initiation, callbacks, deep links or app-return
   promise. No new signup/resend surface in this registered sign-in slice.
9. Exposure is default-off. The opt-in development build consumes explicit
   local configuration with generated synthetic public keys and a local-test
   CAPTCHA token only for a captcha-disabled disposable stack. No production
   endpoint or key is baked in. Reject nonlocal hosts for that testing mode;
   production CAPTCHA hosting/identity configuration remains a separate gate.
10. Do not bootstrap, convert or silently replace a real guest session. If a
    restored session is guest-owned, retain it and present a continuity boundary;
    clean-session registered sign-in remains available. Existing guest handoff
    cookies and proposed header transport are not interchangeable.
11. Only own `mobile/android/**` and this lane's focused spec/report/evidence.
    No server, API_CONTRACT, DATA_MODEL, iOS, web, #726 or financial-account edits.
12. Resource reservation: unique `android-auth-611c` local Supabase project;
    API 59400, gateway 59401, DB 59402, mail UI 59403, SMTP 59404, remaining
    59405–59419 only as needed. Bind-check before starting; no killing other
    listeners. Use a dedicated named AVD and checked free emulator port. Never
    stop shared adb or other stacks, including 574xx/584xx/564xx/55432.

## 3. Reserved / parked scope

- Financial rules, records/account CRUD and UI wiring: await accepted #735 APIs.
- Complete native guest conversion and session-on-error transport: backend
  prerequisite with a named owner; synthetic #726 adapter is not production.
- Signup/resend UX, native PKCE/App Links, production CAPTCHA hosting, app identity,
  signing/publishing and hosted configuration: separate accepted contracts.
- Voice, sharing, chat streaming, domain persistence, analytics and model-facing
  changes. No paid calls, market providers or customer credentials.

## 4. Contract gates

Existing server contracts remain unchanged. Canonical owners are
`src/argus/api/routers/auth.py`, `routers/profile.py`, `schemas.py`,
`dependencies.py`, `domain/supabase_gateway.py`, and browser recovery under
`web/app/api/auth/recovery/` / `web/app/auth/recovery/`. `/auth/logout` only clears
browser cookies; use the SDK for native revocation. `/me` owns account_kind,
capabilities and language/locale. A 503 verification failure is not logout.

Document native configuration, storage/revocation lifecycle and test commands
under `mobile/android/README.md`; write actual acceptance and limitations under
`docs/reports/android-registered-session.md`. No canonical schema amendment is
required or authorized. A newly required server behavior goes to the lead.

## 5. Execution contract

One spec-first PR targeting `codex/private-alpha-next`, labeled and taken out of
draft after implementation. Keep exposure default-off. No merge/deploy.

Verification: build, lint, unit tests for contract/error classification, secure
storage and session ownership; mocked HTTP success/rejection/transient failure,
refresh single-flight, late /me results after account switches, failed sign-out,
and guest preservation. Instrumented local synthetic acceptance must prove
registered sign-in -> /me -> process relaunch -> refresh -> sign-out and account
switch. Prove native old-session rejection after successful revocation. Verify
browser recovery opens the existing browser route without native PKCE state.
Inspect EN/es-419 UI, keyboard/native Back, larger text and two phone sizes.
Commit sanitized durable captures and machine-readable evidence with exact SHAs.

Use normal one-way integration reconciliation and semantic-overlap assessment,
merged-tree modularity check, exact-head CI and review-exhaust. Address confirmed
findings, reply/react/resolve, then one clean latest-delta review with zero
unresolved threads. Do not repeat unrelated paid/browser matrices.

## 6. Stop conditions

- New server/API/domain behavior, unclear identity or guest ownership, production
  CAPTCHA/callback decisions: report the concrete gap to the lead and continue
  independent registered-session work.
- Occupied reserved resource: do not kill/restart its owner; coordinate a free
  resource before dependent tests.
- #726 probe failures stay with that owner and do not gate independent registered
  client work. Frozen verification at `08791d90` already reported compile defects.
- Do not weaken token storage, revocation truth or account isolation to make a
  test pass. Escalate if a safe fix exceeds this client-only boundary.

## Sources

- [Authority](../../DOCUMENTATION_AUTHORITY.md), [Product](../../PRODUCT.md),
  [MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md),
  [Architecture](../../ARCHITECTURE.md), [API](../../API_CONTRACT.md),
  [Data model](../../DATA_MODEL.md), [Design](../../../.agent/designs/argus/DESIGN.md).
- [Supabase session import](https://supabase.com/docs/reference/kotlin/auth-setsession),
  [refresh](https://supabase.com/docs/reference/kotlin/auth-refreshsession), and
  pinned 3.2.6 SDK source, inspected before use.
- [Probe verification defects](https://github.com/lagarcess/argus/pull/726#issuecomment-5878151525)
  are verification evidence, not an implementation template.
