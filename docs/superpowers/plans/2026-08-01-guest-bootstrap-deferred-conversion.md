# Guest Bootstrap Deferred Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILLS: Use
> `superpowers:test-driven-development` for each behavior change and
> `superpowers:verification-before-completion` before any completion claim.

**Goal:** Let a new or expired visitor reach and type in the normal guest chat
without creating an anonymous identity or acquiring CAPTCHA until the first
explicit submit, while preserving guest allowances, conversion, and expiry
recovery.

**Architecture:** Keep the read-only `GET /me` session probes. Represent an
unauthenticated visitor on `/chat` as an explicit pre-bootstrap guest
presentation state. On the first submit, acquire the existing guest CAPTCHA and
bootstrap the anonymous session, refresh canonical account truth, run the
existing allowance gate, and only then create a conversation and stream the
turn. A bootstrap response with `renewed_after_expiry=true` renders the existing
`ExpiredGuestSession` surface reactively. No backend, schema, API, allowance, or
CAPTCHA-acquisition behavior changes.

**Tech Stack:** React 19, Next.js 16, TypeScript, Bun test, Playwright.

## Constraints

- Base: `origin/codex/private-alpha-next` at
  `8e2a62177f8e2c946c6fd397fe019fd824cbc032`.
- Source of truth:
  `docs/superpowers/specs/2026-08-01-guest-bootstrap-deferred-conversion.md`,
  including its Phase 1 close-out.
- Preserve `GET /me` on load. Read-only session restoration is explicitly in
  scope; identity creation is not.
- `web/lib/guest-captcha.ts` is a no-touch file. Reuse
  `acquireGuestCaptchaToken` through `startGuestSession` unchanged.
- #321 is present through PR #326 at `8e2a6217`; its timeout wrapper, widget
  shell, interactive-deadline reset, focus containment, and dark-mode behavior
  are the reusable acquisition boundary. Stop if this lane would need to change
  `guest-captcha.ts` rather than sequencing `startGuestSession` around it.
- Do not add backend runtime, schema, API-contract, allowance-policy,
  onboarding, provider, or hosted configuration changes.
- Do not change `ExpiredGuestSession` restart internals; change only how the
  existing surface is triggered.
- Keep the authenticated guest funnel event for a starter-action selection;
  emit it only after guest bootstrap and canonical `/me` refresh have
  established the authenticated relay, and before allowance admission.
- Map the preserved `/me` probe narrowly: only `401` and the known
  `guest_session_expired` `403` enter pending guest. Fail closed for
  `private_alpha_access_required` and every other profile error; they must not
  trigger guest bootstrap.
- Keep the pre-stream loading state neutral. Do not fake a backend
  `stage_start`, expose CAPTCHA/provider language, or add a separate
  verification step.
- Before identity exists, do not claim an expiry or server capability and do
  not offer identity-dependent Feedback, Omnisearch, Recents mutations, or
  conversion copy that says a conversation will be kept. Local language/theme
  controls and the ordinary Sign-in path remain available.
- English and Spanish (`es-419`) must have equivalent visible behavior.
- Worktree environment files are canonical links and remain read-only.
- End at a reviewed Draft PR against `codex/private-alpha-next`. Do not merge,
  deploy, mutate hosted Supabase, expose testers, or mark the PR ready.

## Task 1: Lock the deferred-entry contract with failing tests

**Files:**

- Modify: `web/__tests__/guest-session.test.ts`
- Modify: `web/__tests__/guest-entry-routing.test.ts`
- Modify: `web/__tests__/guest-starter-actions.test.tsx`
- Modify: `web/__tests__/guest-shell.test.tsx`
- Modify: `web/e2e/guest-entry.spec.ts`
- Modify as required by invalidated eager-bootstrap setup:
  `web/e2e/support/guest-qa.ts`
- Modify only if directly invalidated:
  `web/e2e/guest-experience.preflight.spec.ts`

**Steps:**

1. Add source-contract assertions that `GuestEntry` navigates to `/chat`
   without importing or calling `startGuestSession` or `retryGuestSession`.
2. Add a route assertion that guest-capable `/chat` can render without an
   established Supabase user while the auth-first rollback still redirects.
3. Rewrite the first guest browser fixture so `GET /me` returns unauthorized
   until `POST /auth/guest` succeeds.
4. Assert zero `POST /auth/guest`, zero usage request, zero conversation create,
   and zero chat stream on initial load and while typing.
5. Assert the first typed send and the first starter-action send order:
   `/auth/guest` -> `/me` -> `/me/usage` -> `/conversations` -> `/chat/stream`.
6. Add a probe-state contract that only `401` and
   `403 guest_session_expired` become bootstrap-required; assert
   `private_alpha_access_required` fails closed with no bootstrap.
7. Assert the composer is disabled with one neutral in-flight presentation
   while bootstrap is pending, with no separate auth/CAPTCHA copy and no early
   `stage_start` label.
8. Assert `renewed_after_expiry=true` on the first send renders the existing
   expiry surface in both English and Spanish and performs no allowance,
   conversation, or stream request.
9. Assert starter metadata reaches the send owner and its event occurs once,
   after canonical `/me` refresh and before `/me/usage`; typed sends and failed
   bootstrap/refresh emit zero starter events.
10. Add a same-tick duplicate-submit case proving exactly one bootstrap,
    canonical refresh, usage read, conversation create, stream, and starter
    event.
11. Separate any shared `freshGuest()` provisioning from the public deferred
    entry journey. Existing authenticated-guest specs may provision a session,
    but setup must not consume a message, allowance, conversation, or provider
    call.
12. Run the focused tests and confirm they fail for the expected eager-bootstrap
   and route-guard reasons before changing production code:
   `cd web && bun test __tests__/guest-session.test.ts __tests__/guest-entry-routing.test.ts __tests__/guest-starter-actions.test.tsx __tests__/guest-shell.test.tsx`.

## Task 2: Render the explicit pre-bootstrap guest surface

**Files:**

- Modify: `web/components/guest/GuestEntry.tsx`
- Modify: `web/app/page.tsx`
- Modify: `web/app/chat/page.tsx`
- Modify: `web/lib/landing-entry.ts`
- Modify: `web/lib/guest-account.ts`
- Modify: `web/components/guest/useGuestShellActions.ts`
- Modify: `web/components/guest/useGuestExperience.ts`
- Modify: `web/components/guest/GuestHeader.tsx`
- Modify: `web/components/guest/GuestSettingsMenu.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`

**Steps:**

1. Reduce `GuestEntry` to presentation routing only: it replaces `/` with
   `/chat` and performs no guest bootstrap, retry, expiry, or CAPTCHA work.
2. Classify both the landing-page and chat-page session probes through small,
   testable routing helpers. Preserve missing-session entry, and fail closed on
   private-alpha denial or any unknown profile error.
3. Let the `/chat` server page render for an unauthenticated visitor only when
   both guest presentation and CAPTCHA configuration are available. Preserve
   the auth-first redirect when that rollback condition is false.
4. Add one explicit client state with four meanings: profile probe in progress,
   established account, guest bootstrap required, or expired guest. Only a
   missing session (`401`) or `guest_session_expired` (`403`) may enter guest
   bootstrap required. Treat `private_alpha_access_required` and all other
   profile failures as fail-closed errors.
5. Treat “guest bootstrap required” as guest presentation for the empty heading,
   composer, legal copy, starter actions, local language/theme controls, and
   ordinary Sign-in path, without inventing an expiry timestamp or canonical
   account facts.
6. Keep a distinct established-guest signal for authenticated guest-only
   operations and analytics.
7. Suppress pre-bootstrap Feedback and Omnisearch affordances. Do not open the
   guest conversion modal before a conversation exists; Sign in routes to the
   preserved auth landing instead.
8. Run the focused Task 1 tests and keep unrelated registered hydration tests
   green.

## Task 3: Bootstrap inside first-submit admission

**Files:**

- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/components/guest/useGuestExperience.ts`
- Modify: `web/components/chat/StarterActions.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Modify: `web/__tests__/chat-turn-artifact-ux.test.ts`
- Modify: `web/__tests__/guest-analytics.test.ts`

**Steps:**

1. Add a synchronous first-submit latch so repeated Enter/click events cannot
   continue past one coalesced bootstrap into duplicate allowance checks or
   conversation creation.
2. When guest bootstrap is required, enter the ordinary turn in-flight lock and
   show a neutral localized “Sending…” submission status; do not claim a
   backend stage. Mark the submission region busy and replace the neutral state
   only when a real `stage_start` arrives.
3. Call `startGuestSession` with the current UI language.
4. If `renewed_after_expiry=true`, capture the returned public-account
   presentation permission, switch to the expired state, release the turn lock,
   and render `ExpiredGuestSession`. Stop before usage or conversation work.
5. Otherwise call the existing `refreshAccount`, require canonical account
   truth, and pass that just-refreshed account kind into the existing
   `admitSend` gate so React state timing cannot skip guest allowance checks.
6. Preserve the locked order: bootstrap, account refresh, allowance admission,
   conversation creation, user-message projection, stream.
7. On bootstrap or refresh failure, release the lock, retain the typed composer
   value, show localized existing guest-entry recovery copy beside the
   composer, and create no conversation.
8. Carry starter metadata into the send owner, then capture its funnel event
   after successful canonical `/me` refresh and before admission. It must use
   the authenticated guest relay, remain exactly once under same-tick duplicate
   input, and remain zero for typed sends or bootstrap/refresh failures.
9. Preserve existing registered, established-guest, retry, conversion-resume,
   conversation-switch, and stream-reconciliation behavior.
10. Run the focused source/unit tests and then the guest browser spec.

## Task 4: Browser acceptance and regression verification

**Files:**

- Modify as evidence requires: `web/e2e/guest-entry.spec.ts`
- Do not modify: `web/lib/guest-captcha.ts`

**Steps:**

1. Run focused frontend tests:
   `cd web && bun test __tests__/guest-session.test.ts __tests__/guest-entry-routing.test.ts __tests__/guest-starter-actions.test.tsx __tests__/guest-analytics.test.ts __tests__/guest-shell.test.tsx __tests__/chat-turn-artifact-ux.test.ts`.
2. Run the hermetic frontend suite: `cd web && bun test`.
3. Run lint/type/build checks selected by the repository scripts for the touched
   frontend files.
4. Run a production build server-gate matrix with mock auth disabled: guest
   enabled plus CAPTCHA configured renders `/chat`; guest disabled redirects to
   the auth-first surface; CAPTCHA unavailable redirects to auth-first. The
   normal QA runner's mock-auth bypass is not evidence for this gate.
5. Run the zero-provider guest Playwright harness in English and Spanish.
6. Record browser evidence in both English and Spanish for:
   - new visitor: composer visible, typing causes no bootstrap;
   - first typed send: one bootstrap, one allowance read, one conversation,
     ordinary response;
   - first starter action: same ordering and one funnel event;
   - returning valid guest: normal hydration, no bootstrap;
   - returning expired guest: composer first, expiry only after first submit;
   - bootstrap failure: localized recovery, typed text retained, no conversation;
   - mobile: composer and 44px controls remain reachable.
   Capture exact-candidate screenshots or equivalent Playwright artifacts for
   the core idle, submit, expiry, and failure states.
7. Run `git diff --check`, inspect `git diff --stat`, and verify with
   `git diff --exit-code -- web/lib/guest-captcha.ts` that the protected file is
   unchanged.
8. Request independent contract and QA review. Fix only validated findings on
   touched behavior and rerun the affected evidence.
9. Create a Draft PR against `codex/private-alpha-next` with exact SHA, tests,
   browser evidence, rollback (`git revert` of this slice), #321 dependency
   status, and explicit no-merge/no-deploy boundaries.
