# Issue #454 Password Recovery CAPTCHA Plan

**Goal:** Make self-serve password recovery satisfy Supabase CAPTCHA protection and surface rejected requests to the user.

**Integration base:** `c3a9aca181ea43770a81c13ec2fb5f02f85af293`

**Constraints:** Keep CAPTCHA enabled. Do not touch `render.yaml`, `.env.example`, `.github/argus-env.sh`, `.env`, `web/.env.local`, the release profile, email templates, or approved branding. Do not open a recovery link or change a password.

## Task 1: Lock the request contract with failing tests

**Files:**
- Modify: `web/__tests__/auth-captcha-confirmation.test.ts`
- Modify: `web/__tests__/auth-security.test.ts`

Add tests that require the browser recovery request to acquire and send a bounded `captcha_token`, require the server boundary to reject missing or invalid tokens before provider work, require the provider call to receive the token, and require provider rejection to return a non-success response. Run the focused tests and record the expected failures.

## Task 2: Implement the bounded CAPTCHA path

**Files:**
- Modify: `web/lib/auth-security.ts`
- Modify: `web/lib/recovery-request.ts`
- Modify: `web/app/api/auth/recovery/route.ts`
- Modify: `docs/API_CONTRACT.md`

Reuse the existing password-auth Turnstile acquisition helper, forward `captcha_token` through the same-origin recovery route, validate it at the server boundary, and pass it to Supabase as `options.captchaToken`. Preserve generic success for valid, accepted recovery requests and invalid email shapes, while returning a generic non-success response for provider rejection so the existing localized form alert appears.

## Task 3: Sweep and verify auth coverage

**Files:**
- Inspect: `web/lib/argus-api.ts`
- Inspect: `web/lib/guest-session.ts`
- Inspect: `src/argus/api/routers/auth.py`
- Inspect: `src/argus/domain/supabase_gateway.py`
- Inspect: `src/argus/domain/supabase_guest_accounts.py`

Trace every client-called authentication entry point and classify CAPTCHA coverage or non-applicability. Run focused tests, lint, type checks, build, and the modularity budget check. Confirm forbidden files are unchanged.

## Task 4: Hosted proof and delivery

Confirm the Cloudflare production widget allows `arguschat.ai`. Submit one real recovery request to the allowlisted admin address without opening its link or changing a password. Read Supabase Auth logs and require `POST /recover` status `200`. Fetch current integration, reconcile only if it advanced, commit, push, open a PR against `codex/private-alpha-next`, complete a clean review pass with zero unresolved threads, and report the exact head.
