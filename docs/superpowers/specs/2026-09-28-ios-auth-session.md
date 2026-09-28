# iPhone registered-session continuation

Connect the reviewed iPhone shell to existing Argus authentication, proving a
real local sign-in -> /me -> relaunch -> sign-out journey. Direct founder
authorization in this chat on September 28, 2026 permits this continuation and
ongoing coordination with the Project delivery lead; no merge/deploy/hosted work.

## 1. Why

PRODUCT preserves existing account and guest behavior while the MVEE adds native
ecosystem interfaces. Registration is required for financial operations, but
chat remains guest-accessible. This slice establishes a reusable registered
session owner without rebuilding server authentication or a client ledger.
The current batch in DOCUMENTATION_AUTHORITY assigns `ios/` to this lane.

Fresh integration base: `19550f28e344c1004dd3ea366625c25fae4b3355`.
Foundation #729 merged as `f61e47f1243d94fe5d5fa631c4bd9f67906fcfc9`.
Design #727 merged at head `f0a64ffb9d70ce5b82491cf8e1803bb8a6ec7431`.
Server session isolation #728 merged as
`4e024a4e2837058e73c4be6c528fc41f24d7a03e`.
Read-only proof #726 is open at `d03f3c265604f7c73f65886740d32ddfe190e85d`;
its probes and synthetic adapter are evidence, not production implementation.
New worktree: `ios-auth-session/private-alpha-next`; branch `codex/ios-auth-session`.
The foundation worker branch remains unchanged.

## 2. Locked decisions

1. Keep the locked five destinations, shared controls, bilingual copy and
   persistent appearance. Account entry lives in Profile, with existing App
   preferences retained. Financial screens remain explicitly local samples.
2. Auth exposure is default off. Disabled mode creates no client or network
   request. Enable through ignored, validated development configuration;
   production bundle identity, signing and hosted endpoints remain unapproved.
3. Ordinary signup/login use existing `/api/v1/auth/signup` and `/auth/login`.
   Preserve CAPTCHA, attempt limits, account access rules, profile creation,
   request language and canonical errors. No direct SDK password login.
4. Official `supabase-swift` Auth product (pinned initially 2.55.2, matching
   inspected evidence) owns refresh and revocation after Argus returns tokens.
   A native device-only Keychain adapter owns durable credentials. No tokens,
   passwords, session objects or CAPTCHA values enter logs, screenshots or
   analytics. Verify persistence failures rather than trusting swallowed SDK
   storage errors. Pin resolved dependencies; inspect actual SDK behavior.
5. Use a dedicated cookie-free transport for both Argus and SDK fetches. Never
   store/replay ambient `sb-auth-token` cookies. Require configured origins,
   reject cross-origin redirects and avoid credentials crossing environments.
   HTTPS is normal; loopback HTTP is allowed only for isolated development.
6. `/api/v1/me` owns displayed product identity. Bind its response to the
   current SDK identity and account epoch. Account changes invalidate pending
   requests and storage generation; late responses/refreshes cannot resurrect
   old identity or write credentials into the replacement session.
7. One logical refresh and retry after an authenticated 401. Another 401 or
   explicit rejected refresh ends usable session. Transport/5xx failures remain
   retryable; 503 session verification failure does not become logout. SDK
   internal transient retries are distinct and must be disclosed in evidence.
8. Sign out through SDK local revocation, not Argus's cookie-clear endpoint.
   Preserve a device-only pending revoke before SDK local removal, report
   failure honestly, and retry without replacing a new account. Block entry
   while unresolved revocation/cleanup could leak an old session. Test expired
   credentials and SDK-suppressed logout statuses; a returned method alone is
   not proof of revocation. No global/other-device management in this slice.
9. Signup without a session displays Check your email and return-to-sign-in.
   Do not call login automatically or claim verification. No general resend
   endpoint exists. Guest-signup retry is not a general resend API; explain
   unsupported resend rather than implementing another auth service.
10. Forgot password opens configured web `/auth/forgot-password` externally.
    Initiation, CAPTCHA and PKCE completion stay in that same browser; native
    returns to fresh sign-in. No native recovery initiation, verifier transfer,
    custom schemes, universal links, callback parsing or automatic return claim.
11. CAPTCHA acquisition uses a bounded WKWebView bridge with exact configured
    main-frame origin and message validation, cancellation and error handling.
    Fresh token per attempt, never automatic replay of a consumed token. Local
    validation uses public test sitekeys and the corresponding local Supabase
    test-secret mode; no production bypass or hosted bridge is created.
12. Lead narrowed guest scope: no new bootstrap/restore UI or conversion flows.
    If a stored SDK identity is anonymous, retain it and refuse native
    registration/account switching with an explicit unsupported-transfer state.
    #726's wrong-destination session-in-cookie and proposed header transport are
    a separately owned backend prerequisite. They do not block registered proof.

## 3. Reserved / parked scope

- Guest conversion, generic resend and app-return/recovery callbacks await
  explicit server/hosted contracts and owners. Preserve existing web behavior.
- Financial account wiring waits for the VM backend owner's accepted payload
  contract. No endpoints, arithmetic, local ledger or financial persistence.
- No chat runtime, model prompts, providers, voice, sharing, analytics,
  production credentials, app identifiers, signing accounts or hosted settings.
- No edits to another worker, `src/`, `web/`, `supabase/`, canonical product,
  API/data/design docs, Android or chart-validation paths.

## 4. Contract gates and ownership

Own `ios/`, this spec and `docs/reports/evidence/ios-auth-session/` only. Add a
focused auth setup document and typed native session package. Server endpoints
and records remain unchanged, so API_CONTRACT/DATA_MODEL amendments are neither
needed nor authorized. Source conflicts go to the lead, not a parallel service.

The session package owns transport, credential lifecycle, identity and errors;
SwiftUI owns fields, navigation and accessible localized presentation. The app
creates one session owner. Financial samples do not derive signed-in account
facts. Tests inject transport/storage boundaries, not a competing product auth.

## 5. Execution contract

One implementation PR to `codex/private-alpha-next`, spec committed first.
Default-off exposure; no separate incubation branch. Release captain integrates
bounded workers and independently verifies behavior. Founder owns merge.

Local environment allocation from lead: unique stack `ios-auth-8be2`, ports
58400 API, 58401 Supabase gateway, 58402 DB, 58403 mail UI, 58404 SMTP,
58405 test CAPTCHA bridge; lead subsequently reserved 127.0.0.1:3001 for
unchanged web recovery because canonical validation rejects HTTP58406.
58406-58419 remain spare.
Bind-check before startup; never stop another listener. Copy canonical local
Supabase configuration/migrations to ignored scratch, never mutate shared stacks.
Synthetic accounts/credentials only; provider configuration blank and no turns.
Use iPhone17e `8B7975F1-1338-4966-90E2-770416CAF174` and iPhone18 Pro Max
`0335699A-C522-492B-A8C3-8FD3D7CAC06A`. Other simulators remain untouched.

Required evidence:

- Unit/integration tests for cookie refusal, environment/redirect validation,
  single refresh, bound 401 retry, transient 503, persistence failures, stale
  account responses and stale storage writes, pending sign-out and retry.
- Actual unchanged Argus + isolated Supabase registered login -> SDK -> /me ->
  relaunch -> /me -> revoke, proving prior access/refresh rejection. Concurrent
  refresh, invalid login, confirmation-required signup, expiry/revocation and
  A-to-B isolation exercised with synthetic identities.
- Two-size simulator UI evidence for English/es-419, auth errors and pending
  states, keyboard, accessibility, dark/light presentation; foundation checks
  remain green. Prove local CAPTCHA pass/cancel/fail with test keys; distinguish
  test bridge from production acceptance. Browser recovery launch failure is
  explicit; document same-browser recovery proof and anything unverified.
- Commit sanitized results/screenshots with exact source boundary, repeatable
  commands, limitations and cleanup record. No secrets in artifacts.
- Local docs links, diff check, modularity on reconciled would-be merged tree;
  exact-head CI; ready-for-review PR, address relevant Codex findings and zero
  unresolved threads. Terminal audit only after review response.

Before READY fetch current integration, one-way merge if needed, report semantic
overlap and retain/revalidate only affected evidence. End at open reviewed PR;
no merge, deployment or hosted changes. Clean up only lane-owned processes,
containers/simulators after proof, retain durable evidence and report gaps.

## 6. Stop conditions

Stop dependent implementation and report to lead if it requires a new server
endpoint/schema, guest transfer policy, hosted CAPTCHA/callback setting, native
production identity, financial contract, secret access or production/model call.
Do not work around server access or security gates. Continue independent
registered-session work when a guest or future account-wiring gap is isolated.

## Sources

Argus authority: `AGENTS.md`, `docs/PRODUCT.md`,
`docs/DOCUMENTATION_AUTHORITY.md`, MVEE guest-access/registration,
`docs/ARCHITECTURE.md` platform direction, `docs/API_CONTRACT.md` sections 7-8,
`docs/DATA_MODEL.md` profile/guest ownership, `.agent/designs/argus/DESIGN.md`.
Current owners: `src/argus/api/routers/auth.py`, `web/lib/argus-api.ts`,
`web/components/auth/AuthForm.tsx`, `web/lib/auth-security.ts`,
`web/app/auth/forgot-password/page.tsx`, `web/app/auth/recovery/page.tsx`.
Evidence reference: #726 at the exact commit above; official SDK source at
2.55.2 (`40344fb3a7007d772218c6ddf6bca9febd8cb226`).
Engineering inference: generation-bound credential storage and explicit pending
revocation are needed because the inspected SDK can finish asynchronous refresh
or clear local credentials before a failed revocation. Tests must prove the
reachable cases; avoid adding unrelated account-management machinery.
