# Native auth and session continuity proof

**Status:** Proof report with runnable probes. It recommends a contract and
proposes changes. It does not change Argus endpoints, cookies, Supabase
settings, RLS, email templates, or any production client.
**Date:** 2026-09-27
**Question:** What is the smallest safe way for Swift/SwiftUI and
Kotlin/Compose clients to enter and keep an Argus session, using existing
Argus and Supabase authentication, without weakening the checks the web
relies on?
**Inputs:** [Native readiness audit](native-readiness-audit.md) WP-A and
recommendations E1 to E3. Assignment direction for the native stacks as
recorded in that audit (§1). [#718](https://github.com/lagarcess/argus/issues/718)
owns message and event contracts and is not touched here.

## 1. Answer

Keep sign-in, sign-up, guest start, and guest conversion on the existing Argus
endpoints, and hand the session Argus returns to the official Supabase SDK.
The SDK then owns storage, refresh, revocation, and recovery callbacks, as the
web's Supabase client does today. The iOS probe does exactly this against
unchanged Argus on the iOS 27 simulator, and everything except the log-hygiene
check passes.

Three things stand between that contract and production:

1. **A server defect, independent of native.** Argus's shared server-side
   Supabase client keeps the most recent session it signed in and refreshes it
   on a timer. That rotates the refresh token the client holds, and a client
   whose token is two rotations behind is signed out. This affects web users
   too (proposal P1, finding F1).
2. **Guest conversion needs a transport for the handoff secret.** Unchanged
   Argus works if the app keeps exactly the two handoff cookies in secure
   storage and replays them only on `/api/v1/auth` paths. The additive header
   transport (E3) removes cookie handling from the apps and fixes an orphaned
   session on wrong-account sign-in. It is demonstrated only through a
   synthetic adapter (proposals P2 and P3).
3. **Hosted configuration and identifiers that do not exist yet.** They are a
   Turnstile page on an Argus HTTPS origin, redirect allowlist entries, app
   identifiers, and association files. Real-device and production-sitekey
   behavior is unverified (§8).

Android is unverified at every level above source. The Kotlin probe is
written but has never been compiled, because this machine has no Android SDK
or JDK. Its network and secure-storage I/O runs on an injected I/O dispatcher,
never the caller's, and has regression tests that have also never run.

## 2. Evidence levels and environment

Evidence levels are kept separate throughout, as the assignment requires:

| Level | Meaning in this report |
| --- | --- |
| 1 | Source inspection of Argus, web, or SDK code |
| 2 | Synthetic adapter or mock. Here: the handoff header adapter in `probes/native-auth/adapter/` |
| 3 | Unchanged Argus with local auth. The Python HTTP probe is language-neutral, not a native client |
| 4 | Simulator or emulator execution of a native client |
| 5 | Real device or hosted verification. None in this report |

| Item | Value |
| --- | --- |
| Original integration base | `f0a90763b` |
| Current integration at capture | `3b9313f3d` (#721, agent-runtime log fields only; no overlap, §10) |
| Reconciliation merge | `8e88294f7` |
| Evidence capture head | `8f4b05de0`, clean tree, every file. Later commits change only Markdown and evidence, which the gate checks (§2.1) |
| Local auth stack | Supabase CLI 2.117.0, GoTrue v2.196.0, project `argus-native-auth-proof` on ports 57450 to 57459, created from this branch's migrations. Overrides: `jwt_expiry = 60`, email confirmations on, one synthetic redirect `argusnativeproof://auth-callback` |
| Argus API | Unchanged source at the head above, port 57460, provider keys blank, synthetic market data, guest access on, public account access off |
| iOS | Xcode 27.0 (27A266a), iOS 27.0 simulator "Argus Native Auth Proof" (iPhone 17 Pro), supabase-swift 2.55.2 pinned |
| Android | No SDK, emulator, or JDK on this machine. Source only, never compiled |
| Captcha | Cloudflare published test secrets in local Supabase Auth, and test sitekeys in the web view. No production keys |
| Paid calls | None. No chat turn, model, market-data, or email provider call |

Durable evidence is in
[`evidence/native-auth-session-proof/`](evidence/native-auth-session-proof/).
Probes and reproduction steps are in
[`probes/native-auth/`](../../probes/native-auth/README.md).

### 2.1 Current acceptance versus historical observations

**Current acceptance** is only what the evidence gate verifies at the head it
is run against. `probes/native-auth/expectations.json` declares every check
each suite must produce and the only documented failures, A14 and I11.
`probes/native-auth/evidence_gate.py` fails on a missing, repeated, or
undeclared check, any other failure, a documented failure that now passes, an
iOS run whose xcodebuild counts disagree, an app log that departs from the
declared steps, or a capture from a dirty tree or from runtime code that
changed after the capture. Every runner exits with the gate's verdict. To
re-verify:

```bash
python3 probes/native-auth/evidence_gate.py docs/reports/evidence/native-auth-session-proof
```

**Historical observations** are things seen during development that are not
current acceptance and are not claimed as such:

- An iOS "Open in ArgusAuthProbeApp?" prompt before custom-scheme delivery,
  seen in three runs but not in the current capture (§3.6).
- Earlier captures at `8e88294f7` and before. They showed the same outcomes but
  were taken from a tree the runners did not record as clean, before the gate
  existed. They are replaced, not cited.

## 3. Recommended native contract

This keeps every web behavior. Items marked **needs P#** depend on a proposal
in §6. Everything else works against unchanged Argus.

### 3.1 Entry stays on Argus

- Guest start, sign-in, sign-up, and guest sign-up go to the existing
  `/api/v1/auth/*` routes with a captcha token, no `Origin` header, and no
  cookies. The session comes back in JSON (A1, C1, I1).
- Clients do not call Supabase password sign-in directly. It would skip
  Argus's attempt limiter, profile repair, and guest claim (A12, A13). It does
  not skip captcha (B1) or the private-alpha allowlist, which `current_user`
  enforces on every request (A13).
- The HTTP client never stores or sends cookies. Argus sets `sb-auth-token` on
  sign-in, and `current_user` accepts that cookie when a request has no bearer
  header. A platform-default cookie store therefore turns a missing header into
  the previous user's identity (A11). The iOS probe uses an ephemeral
  `URLSession` with cookies disabled (I2). The Android probe uses
  `CookieJar.NO_COOKIES`.

### 3.2 The SDK owns the session

- After entry, the app calls `setSession` (Swift) or `importSession` (Kotlin)
  with the returned tokens (I1).
- Refresh goes directly to Supabase Auth with the public anon key, as the web
  does. Refresh needs no captcha token (B1).
- Refresh is single-flight. supabase-swift shares one in-flight refresh task
  (I3: eight concurrent requests, one new access token). The Kotlin probe adds
  its own mutex because supabase-kt's behavior is unverified. The rotated
  token is persisted before use. Supabase tolerates the immediate parent
  token after the 10-second reuse window but refuses a token two rotations old
  (A5b), so one lost refresh response is survivable and two are a sign-out.
- Storage is device-only. The probe's Keychain store uses
  `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly` (I1). supabase-swift's
  default store uses `AfterFirstUnlock`, which travels through backups, so
  apps pass their own store. The Android probe encrypts with a non-exportable
  Keystore key.
- Request rule: send the bearer, and on 401 refresh once and retry once. A
  second 401, or a refused refresh, means signed out (A6, I4). Argus returns
  the same `unauthorized` code for expired and revoked tokens, so the client
  cannot and need not tell them apart.
- Logging: pass no logger to the SDK in release builds, and never interpolate
  a `Session` value. With a logger attached, supabase-swift logs the raw refresh
  token, and `Session`'s default description contains both tokens (I11, a
  deliberate failing check).

### 3.3 Leaving and switching accounts

- Sign-out calls `signOut(scope: .local)`, which revokes this device's
  session. Argus rejects the unexpired access token on the next request
  because `current_user` checks `auth.sessions` (A8, I5). "Sign out
  everywhere" uses `.global`, and "other devices" uses `.others` (A9).
- Argus `POST /auth/logout` only deletes cookies. Forgetting tokens locally
  leaves the refresh token live (A7, I5). Native clients do not call it and
  do not treat local deletion as sign-out.
- supabase-swift removes the local session before sending the revoke and does
  not retry a failed revoke. An offline sign-out therefore leaves the server
  session alive. Clients keep the refresh token in a pending-revoke slot and
  retry at next launch (engineering decision E-4, §7).
- Account switching: every account-scoped request records an account epoch.
  Sign-out, sign-in, or a switch ends the epoch, clears account caches, and
  drops any late response (I6). The server cannot do this for the client
  (A10).

### 3.4 Guest continuity

- The app persists the guest bearer and sends it on the next guest start, so
  Argus reuses the guest instead of minting a new one (C1).
- **Today (unchanged Argus):** the handoff secret exists only as two HttpOnly
  cookies scoped to `/api/v1/auth` (C2). A bearer-only client loses the
  guest conversation (C3). An app that stores exactly those two cookies in
  secure storage, and replays them only on `/auth/` paths, converts correctly
  (C4, I7). That includes a lost response retried with the same handoff (C5), a
  cancelled attempt (C6), and new-account sign-up with email confirmation and
  an app relaunch in between (C8, I9). The handoff for new-account sign-up
  lives 7 days (C8), so it must survive restarts.
- **Proposed (needs P2, P3):** a header transport where the app receives
  `handoff_secret` in JSON and sends it back in headers. It removes cookie
  parsing from both apps and returns the session beside a wrong-destination
  problem, so the app can keep or revoke it (S1 to S7 at level 2, I8 at level
  2 on the simulator).
- In both transports, the handoff secret is single-purpose. It is sent only to
  `/api/v1/auth/*`, deleted when Argus reports the handoff finished, and never
  logged. Evidence writers refuse to persist it.
- After conversion the old guest bearer is refused with
  `guest_session_expired` (C9), and a later account switch does not expose the
  converted conversation (C10).

### 3.5 Bot protection (E1)

- The app shows the Turnstile widget in a `WKWebView` (Android `WebView`)
  loading a page from an Argus HTTPS origin, and receives the token through a
  script message handler. The token goes unchanged to the existing endpoints.
- On the simulator with test sitekeys: the pass key returned a token and Argus
  started a guest, with Supabase verifying the token against Cloudflare's test
  secret (T1). The fail key surfaced its error to the app, with no token and
  no request (T2). The interactive key made Turnstile report an interactive
  challenge, which the app logged (T3). A UI test tapped Cancel without
  completing the challenge, and the sheet closed without sending a request (T4).
- Supabase also requires a captcha token on `/recover` (T5), so native
  recovery runs behind the same check.
- Tokens are single-use and valid for 300 seconds, per Cloudflare. The app
  fetches a fresh token for every attempt (B4) and never retries with one it
  already used.

### 3.6 Confirmation and recovery links

- **Now:** email confirmation lands on the web `site_url` with an
  implicit-flow session in the URL fragment (D1). Argus's `/auth/signup` has
  no parameter a native client could use to change that. Recovery through the
  web route redirects only to the web (source, `web/lib/recovery-request.ts`).
  Native users finish both on the web.
- **With an allowlisted app callback:** PKCE recovery returns
  `?code=` to the callback, and the SDK exchanges it for a session Argus
  accepts (D2, I10, T5). A repeated, forged, foreign-device, unlisted, or
  expired callback yields no session (D3 to D5, D7, I10, T5). After a reset,
  the app signs out everywhere, as the web recovery page does (D6).
- PKCE binds the link to the device that requested it (D4). A user who
  requests recovery on the phone and opens the email on a laptop cannot finish
  on the laptop through this flow. This is the substance of founder decision
  X1 (§7).
- iOS sometimes asks "Open in ArgusAuthProbeApp?" before delivering a
  custom-scheme URL. In the current capture it did not ask, and a UI test
  that would have accepted the prompt recorded 0 prompts (`app/run.json`).
  As a historical observation, not current acceptance: iOS did ask in three
  earlier runs, including a clean-tree run at `9045f4798`
  (`historical/callback-prompt-9045f4798.png`). What triggers it was not
  isolated. Universal links avoid scheme prompts and scheme hijacking, but
  they need identifiers and hosting that do not exist (§6 P8).

## 4. Evidence matrices

"Remaining requirement" names what must happen before production use.

### 4.1 iOS (Swift/SwiftUI)

Client: `ArgusNativeAuth` with supabase-swift 2.55.2, XCTest hosted in
`ArgusAuthProbeApp`, iOS 27.0 simulator. Level 4 unless noted.

| ID | Scenario | Argus path | Expected | Observed | Result | Remaining requirement |
| --- | --- | --- | --- | --- | --- | --- |
| I1 | Sign in through Argus, SDK session, relaunch | Unchanged | Session restored from device-only Keychain; `/me` 200 | Restored; `/me` 200; all items `ThisDeviceOnly` | Pass | Real-device Keychain behavior (level 5) |
| I2 | Transport refuses Argus cookies | Unchanged | No cookie stored; bearer-less request 401 | None stored; 401 | Pass | None |
| I3 | Eight concurrent requests inside the refresh margin | Unchanged | One refresh, all 200, rotated token persisted | 1 access token, 8 × 200, rotated | Pass | P1, or the server can rotate the token first (F1) |
| I4 | Revoked on another device | Unchanged | Refresh refused, local session cleared | Signed out, cleared | Pass | None |
| I5 | Forget locally versus `signOut(.local)` | Unchanged | Forgotten token live; signed-out tokens dead | Forgotten refresh 200; access 401, refresh 400 | Pass | Offline revoke retry (E-4) |
| I6 | Account switch with a request in flight | Unchanged | Late response dropped; caches cleared | Dropped; cache gone; Bob sees Bob | Pass | Production app state layer |
| I7 | Guest to existing account, scoped handoff cookies | Unchanged | Claim; handoff deleted | Claimed; deleted | Pass | P2 recommended; works without it |
| I8 | Guest conversion over header transport; wrong account | Synthetic (level 2) | Claim; wrong account's session revoked | Claimed; `guest_handoff_wrong_destination`; revoked | Pass at level 2 | P2, P3 |
| I9 | Guest sign-up, email confirmation, relaunch | Unchanged | Handoff survives relaunch; claim on sign-in | Survived; claimed | Pass | P4 to return the confirmation to the app |
| I10 | Recovery callbacks: valid, repeated, other device, forged, error | Unchanged + lane redirect | Only the first valid callback on the requesting device works | Session, `/me` 200; others refused | Pass | P4, P7, P8, F-X1 |
| I11 | Tokens stay out of logs | Unchanged | No token in SDK log output or `Session` description | Both contain tokens | Fail (finding) | Ship with `logger: nil`; never log `Session` |
| T1 | Turnstile pass sitekey in `WKWebView`, then guest start | Unchanged + test secret | Token to app; guest session; `/me` 200 | As expected | Pass with test keys | P6; production sitekey on a device (§8) |
| T2 | Turnstile fail sitekey | Test sitekey | Error reaches app, no token, no request | As expected | Pass with test keys | Same as T1 |
| T3 | Turnstile interactive sitekey | Test sitekey | Turnstile reports an interactive challenge in the web view | `turnstile.interactive` logged; screenshot | Pass for rendering. The challenge was never completed | Human completion on a device |
| T4 | Cancel the check (UI test tap) | Test sitekey | Sheet closes; no token, no request | `request_sent=false`; no `guest.start` | Pass | None |
| T5 | Recovery behind Turnstile, callbacks delivered one at a time with `simctl openurl`; a UI test accepts iOS's first-delivery prompt | Unchanged + lane redirect | Custom scheme reaches app; issued code gives session; repeated and forged refused | Session, `/me` 200; repeated and forged refused; no prompt in this capture | Pass for custom scheme | Universal links unverified (P8) |

### 4.2 Android (Kotlin/Compose)

Client: `probes/native-auth/android` (supabase-kt 3.8.0, OkHttp). No
toolchain on this machine, so nothing below executed.

| ID | Scenario | Argus path | Expected | Observed | Result | Remaining requirement |
| --- | --- | --- | --- | --- | --- | --- |
| K1 | Sign in, Keystore-backed session, new client instance | Unchanged | `/me` 200 | Not run | Unverified | Run per `probes/native-auth/android/README.md` |
| K3 | Concurrent requests inside the refresh margin | Unchanged | All 200 | Not run | Unverified | Same, plus confirm whether supabase-kt single-flights refresh |
| K4 | Revoked on another device | Unchanged | Signed out | Not run | Unverified | Same |
| K6 | Account switch drops a late response | Unchanged | Dropped | Not run | Unverified | Same |
| K7 | Guest conversion, scoped handoff cookies | Unchanged | Claimed | Not run | Unverified | Same |
| K8 | Guest conversion, header transport | Synthetic (level 2) | Claimed | Not run | Unverified | Same, then P2 |
| K-TS | Turnstile in Android `WebView` | Not built | Token to app | Not built | Unverified | Needs an app module |
| K-MT | Transport and secure store called from the main thread under StrictMode | Unchanged | No main-thread network or disk access; `/me` 401; value round-trips | Not run | Unverified | `MainThreadSafetyTest` on an emulator |
| K-IO | `send` runs on the injected I/O dispatcher, not the caller's thread | MockWebServer | Only the I/O thread executes the request | Not run | Unverified | `TransportDispatcherTest` (JVM, needs SDK to compile) |
| K-AL | App Links callback | Not built | Intent delivered | Not built | Unverified | Signing SHA-256, `assetlinks.json` (P8) |

The contract in §3 is platform-neutral. It assumes nothing Android-specific
that the iOS run did not already exercise at the HTTP level (level 3).

### 4.3 Language-neutral HTTP probe (reference)

The Python probe is not a native client. It proves how unchanged Argus and
local Supabase behave, which both platforms depend on. Suites: session A1 to
A14, guest C1 to C10, callbacks D1 to D7, captcha B1 to B4 (level 3), and the
synthetic adapter S1 to S7 (level 2). Every check passes except A14, which is
finding F1. Per-check expected and observed values are in the evidence JSON.

## 5. Findings and failed assumptions

| # | Finding | Evidence | Severity | Where it goes |
| --- | --- | --- | --- | --- |
| F1 | Argus's shared server-side `supabase-py` auth client (`SupabaseGateway.auth_client`, created with default `ClientOptions`) stores the last session it signed in and refreshes it on a timer 10 s before expiry. A session left alone after Argus sign-in had 3 refresh tokens, 2 revoked, 55 s later with no client activity. The client's own refresh then failed with `refresh_token_already_used`. It also means the API process holds a user's live tokens in memory | A14; `supabase_auth/_sync/gotrue_client.py` `_save_session`; `src/argus/domain/supabase_gateway.py` `from_env` | High. Intermittent sign-outs for web and native. The timer fires once per access-token lifetime (hosted value not inspected; 3600 s is the repository default), for the most recent sign-in on each API process, so it bites idle workers and apps that sleep through two lifetimes | P1, assignment N1 |
| F2 | A platform-default cookie store captures `sb-auth-token` from `/auth/login`, and a later request without a bearer is authenticated as that user | A11. The first build of this lane's own probe harness and its synthetic adapter both hit this (fixed; S7 pins it) | High for any native client that keeps default cookie handling | Contract §3.1 |
| F3 | Wrong-account sign-in during guest conversion returns 403 with the new session only in `Set-Cookie`. A bearer client gets no tokens for a live session | C7 | Medium. Orphaned session the user cannot see or revoke | P3 |
| F4 | A bearer-only client cannot convert a guest against unchanged Argus | C3 | Medium. Temporary conversation lost | Contract §3.4, P2 |
| F5 | supabase-swift logs the raw refresh token when given a logger, and `Session`'s description contains tokens | I11 | Medium. Secrets in crash or analytics logs | Contract §3.2 |
| F6 | supabase-swift's default Keychain accessibility is `AfterFirstUnlock`, not device-only | Source `Sources/Auth/Internal/Keychain.swift` | Low to medium. Tokens migrate through backups | Contract §3.2 |
| F7 | Argus maps a rejected captcha to 401 "Invalid email or password" on sign-in, and to 503 on guest start | B3 | Low. A native user may retype a correct password | P5 |
| F8 | Supabase requires a captcha token on `/recover` | T5, GoTrue `api.go` | Informational. Native recovery needs the web-view check | Contract §3.5 |
| F9 | Recovery with PKCE works only on the requesting device | D4, I10 | User-visible | Founder decision X1 |
| F10 | iOS sometimes shows an "Open in" confirmation before a custom-scheme callback (three earlier runs; not the current capture). Custom schemes can also be claimed by another app | §2.1, §3.6 | User-visible friction and link integrity | P8 when identifiers exist |
| F11 | A password reset through recovery already revoked other sessions in this GoTrue version. The web also signs out globally | D6 | Informational | Contract §3.6 |
| F12 | Always-pass test secret accepted a non-dummy token, although Cloudflare documents that test secrets accept only the dummy token | B2 | Informational. Test keys prove the plumbing, not token validity | §8 |

## 6. Proposed backend and hosted changes

Each is a separate proposal. None is implemented here.

| # | Proposal | Type | Why | Size |
| --- | --- | --- | --- | --- |
| P1 | Create `SupabaseGateway.auth_client` with `auto_refresh_token=False` and `persist_session=False` (or sign out of it after each call), with a failing test first that asserts no user session is retained | Backend fix | F1. Needed by web today | Small |
| P2 | Additive handoff transport for bearer clients in `src/argus/api/routers/auth.py`, read through the same helper as the cookies: opt-in request header, `handoff_secret` in the create response, `Argus-Guest-Handoff-Id` and `-Secret` request headers, a "cleared" signal, and no `Set-Cookie` for that transport. `API_CONTRACT.md` first | API contract + backend | F4, and removes cookie parsing from both apps | Small to medium |
| P3 | When sign-in succeeds but the claim fails, return the session in the body for the header transport | API contract + backend | F3 | Small, with P2 |
| P4 | Let Argus `/auth/signup` and `/auth/guest/signup` pass an allowlisted `emailRedirectTo`, and review hosted confirmation and recovery email templates (the `token_hash` pattern if scanners pre-open links) | Backend + hosted | D1. Confirmation returns to the app | Small backend, hosted review |
| P5 | Distinct problem code for a rejected captcha on sign-in and guest start | Backend | F7 | Small |
| P6 | Host the Turnstile page on an Argus HTTPS origin listed on the production sitekey | Web + hosted Cloudflare | E1 production path | Small page, hosted config |
| P7 | Native recovery request path with Argus's limiter and redirect allowlist: an Argus API route, or the web route accepting an allowlisted native redirect | Backend or web | Today the only limited path redirects to the web | Small |
| P8 | Universal links and App Links: `apple-app-site-association` and `assetlinks.json` served by the web app, `applinks:` entitlement, redirect allowlist entries in hosted Supabase | Hosted + apps | Replaces custom-scheme callbacks (F10) | Needs Team ID, bundle ID, package name, signing SHA-256 |

## 7. Decisions

### Founder decision (material)

**X1. Where native users finish email confirmation and password recovery.**
Recommended: finish on the web now, with a clear step back to the app, and
return to the app once P4, P7, and P8 exist. Consequence to weigh: in-app
recovery is bound to the device that requested it (F9). Web completion works
on any device, as today.

### Engineering decisions (resolved with a recommendation)

| # | Decision | Recommendation |
| --- | --- | --- |
| E-1 | Session owner (audit E2) | Official Supabase SDKs after Argus entry. No Argus refresh endpoint |
| E-2 | Handoff transport (audit E3) | Ship with scoped cookies against unchanged Argus if needed. Adopt P2 before the first native release |
| E-3 | Bot protection (audit E1) | Hosted Turnstile page in a web view. Keep platform attestation as a later option |
| E-4 | Offline sign-out | Pending-revoke slot retried at launch |
| E-5 | Token storage | Device-only Keychain; Keystore-encrypted storage on Android; no SDK default stores |
| E-6 | SDK logging | `logger: nil` in release; lint or review rule against logging session values |

## 8. What remains unverified, and how to verify it

| Gap | Why not verified | Smallest procedure |
| --- | --- | --- |
| Turnstile with the production sitekey in `WKWebView` and Android `WebView` | Needs P6 and an approved hosted page | Serve the page from a staging Argus origin listed on a staging sitekey. Run T1 to T4 on one physical iPhone and one Android phone. Record whether managed mode shows an interaction, and the error codes |
| Token expiry and reuse against real Cloudflare | Test secrets do not model them (F12) | On staging, obtain a token, wait over 300 s, submit it, and expect `timeout-or-duplicate`. Then submit one token twice |
| Hosted Supabase settings (JWT lifetime, rotation, reuse interval, captcha provider, redirect list, templates) | Dashboard not inspected; production access out of scope | Owner exports the auth settings. Rerun A4, A5, A6, and B1 against a staging project |
| Universal links and App Links | No identifiers or hosting | After P8, test on physical devices with `?mode=developer` (iOS) and `adb shell pm verify-app-links` (Android) |
| Android client | No toolchain | `probes/native-auth/android/README.md` |
| F1 in production | Local stack only | After P1 ships, rerun A14. Before that, the effect is predicted from source and local timing |

## 9. Implementation assignments

| # | Assignment | Owner | Depends on |
| --- | --- | --- | --- |
| N1 | P1: stop the server auth client from retaining and refreshing user sessions; failing test first; A14 as acceptance | Backend auth (`supabase_gateway.py`) | None |
| N2 | Write the native session subsection of `API_CONTRACT.md` §7 from §3 of this report | API contract owner | None |
| N3 | P2 and P3: header handoff transport and session beside a claim failure | Backend auth router | N2 |
| N4 | P5: captcha-specific problem code | Backend auth router | N2 |
| N5 | P6: hosted Turnstile page and sitekey hostnames | Web + release owner | Hosted approval |
| N6 | P4, P7, P8: app return for confirmation and recovery | Backend + web + release owner | X1, app identifiers |
| N7 | Production iOS auth module from `probes/native-auth/ios/ArgusNativeAuth` | iOS owner | N1; N3 or scoped cookies; N5 |
| N8 | Run the Android probe, then build the production module | Android owner | Android environment |

## 10. Delivery record

- Original integration base `f0a90763b`. Current integration `3b9313f3d`.
  Reconciled by merge `8e88294f7`. Evidence captured at `8f4b05de0`.
- Overlap disposition: #721 changes agent-runtime debug log fields
  (`discovery_focused_read.py`, `knowledge_answer.py`, one test). This lane
  adds only `probes/native-auth/`, this report, and evidence. There is no shared
  runtime owner, API or data contract, UI state, migration, environment
  variable, or test.
- Every evidence file records its capture head and whether the tree was clean.
  The Argus code exercised is unchanged `src/` at that head. PR #728 fixes A14
  separately; this branch does not contain it, so A14 stays a documented
  failure here and the gate will fail if it starts passing.
- No production system, real account, paid provider, or hosted setting was
  touched.
