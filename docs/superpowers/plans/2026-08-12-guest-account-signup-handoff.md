# Guest Account Signup Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace anonymous identity mutation with real account signup while preserving the complete guest workspace through an idempotent handoff.

**Architecture:** The browser first prepares a workspace-lifetime handoff and receives its HttpOnly claim cookies. A guest-only signup endpoint then invokes ordinary Supabase password signup, and a database trigger binds the newly inserted Auth UUID atomically. The existing email-bound claim transaction remains the sole product-owner rewrite and runs immediately when signup returns a session or on first login after email confirmation.

**Tech Stack:** FastAPI, Pydantic, Supabase Auth, PostgreSQL/PLpgSQL, React/Next.js, TypeScript, pytest, Vitest, Playwright.

## Global Constraints

- Base is `codex/private-alpha-next` at `e61707bfb85946f8fc6a3495faa587a3ff829cb1`.
- Do not mutate an anonymous Auth user into a permanent user.
- Preserve guest conversations, messages, runs, jobs, Ideas, evidence, decisions, and context.
- Keep `EmailAlreadyRegisteredError` as the explicit existing-account refusal.
- A signup handoff cannot outlive the guest workspace's fixed seven-day expiry.
- Do not touch `render.yaml`, `.env.example`, `.github/argus-env.sh`, release profiles, `.env`, `web/.env.local`, or Supabase email templates.
- Do not apply hosted migrations or deploy production from this lane.
- Keep English and Spanish behavior aligned. Add no em dash to user-facing copy.

---

### Task 1: Lock the contract and migration shape

**Files:**
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Create: `supabase/migrations/20260812183000_guest_account_signup_handoffs.sql`
- Test: `tests/test_guest_handoff_postgres.py`

**Interfaces:**
- Consumes: existing `guest_workspace_handoffs`, `claim_guest_workspace_handoff_by_email`, and guest workspace fixed expiry.
- Produces: `handoff_kind`, `public.prepare_guest_signup_handoff(...)`, and the Auth insert binding trigger.

- [ ] **Step 1: Add failing real-Postgres tests**

Add tests that call `public.prepare_guest_signup_handoff`, insert a non-anonymous
`auth.users` row with the nested proof marker, and assert the handoff binds that
UUID while the marker is removed. Add rejection cases for a wrong proof/email,
a destination change after binding, expiry beyond the workspace, and browser
role execution.

- [ ] **Step 2: Run the focused database tests and observe RED**

Run:

```bash
poetry run pytest tests/test_guest_handoff_postgres.py -q
```

Expected: new tests fail because the prepare RPC, kind column, and trigger do
not exist.

- [ ] **Step 3: Add the minimal forward migration**

Add `handoff_kind`, replace the expiry and destination foreign-key constraints,
add the locked prepare RPC plus service-role-only wrapper, and add the Auth
insert binding trigger. Retain the legacy `finalize_linked_guest_identity`
trigger temporarily so email-change confirmations already in flight at deploy
can finish, while removing its only runtime producer. Keep transactions short
and acquire handoff/workspace locks in the same order as claim.

- [ ] **Step 4: Apply to the disposable local database and run GREEN**

Run the repository's local Supabase reset, then rerun the focused Postgres test.
Expected: all focused tests pass, including the existing claim rollback and
concurrency cases.

- [ ] **Step 5: Commit the database boundary**

```bash
git add docs/API_CONTRACT.md docs/DATA_MODEL.md supabase/migrations tests/test_guest_handoff_postgres.py
git commit -m "fix(auth): bind guest signup handoffs atomically"
```

### Task 2: Replace the backend identity-link route

**Files:**
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/api/routers/auth.py`
- Modify: `src/argus/domain/supabase_guest_accounts.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `src/argus/domain/username_signup.py`
- Test: `tests/test_guest_conversion.py`
- Test: `tests/test_alpha_api_supabase.py`
- Test: `tests/test_guest_signup_local_supabase.py`

**Interfaces:**
- Consumes: `public.prepare_guest_signup_handoff`, a prepared handoff cookie, the existing claim RPC, and ordinary `SupabaseGateway.signup`.
- Produces: `GuestAccountSignupRequest`, `GuestHandoffKind`, `serialized_guest_signup`, `get_guest_signup_handoff`, `get_auth_user_by_id`, `resend_signup_confirmation`, and `POST /api/v1/auth/guest/signup`.

- [ ] **Step 1: Replace old link tests with failing signup tests**

Exercise the real route behavior: signup requires a prepared matching handoff,
a fresh signup passes its nested proof to Supabase, confirmation-required
responses retain the guest session and pre-existing handoff cookies, immediate
sessions claim the graph, bound unconfirmed retries resend without another
signup call, and foreign existing emails return
`409 account_exists_use_login` before provider mutation.

- [ ] **Step 2: Run focused backend tests and observe RED**

```bash
poetry run pytest tests/test_guest_conversion.py tests/test_alpha_api_supabase.py -q
```

Expected: failures name the missing request model, route, gateway methods, and
retry serializer.

- [ ] **Step 3: Implement the guest signup saga**

The route branch order is:

```python
with serialized_guest_signup(database_url, email, username) as prevalidation:
    handoff = gateway.get_guest_signup_handoff(prepared_cookie, ...)
    if prevalidation.auth_user_id:
        reconcile_only_if_same_bound_destination()
    else:
        result = gateway.signup(..., guest_signup_proof=handoff)
        verify_trigger_bound_returned_user()
    create_profile()
    claim_now_only_if_session_exists()
```

Delete `link_anonymous_identity`, its raw `PUT /auth/v1/user`, the old request
schema, and the `/auth/guest/link` route.

- [ ] **Step 4: Run unit and local-Supabase GREEN**

```bash
poetry run pytest tests/test_guest_conversion.py tests/test_alpha_api_supabase.py -q
poetry run pytest tests/test_guest_auth_local_supabase.py tests/test_guest_signup_local_supabase.py -q
```

Expected: route tests pass and the real local flow proves source UUID differs
from destination UUID while the complete graph moves once.

- [ ] **Step 5: Commit the backend flow**

```bash
git add src/argus tests
git commit -m "fix(auth): create permanent accounts for guest signup"
```

### Task 3: Move the web conversion flow to guest signup

**Files:**
- Modify: `web/lib/guest-api.ts`
- Modify: `web/components/guest/useGuestConversion.ts`
- Modify: `web/components/guest/ExpiredGuestSession.tsx`
- Modify: `web/__tests__/guest-conversion.test.ts`
- Modify: `web/e2e/guest-experience.spec.ts`

**Interfaces:**
- Consumes: `POST /api/v1/auth/guest/signup`, `AuthResponsePayload.guest_claim`, and ordinary `signupWithEmail` for expired sessions.
- Produces: `registerGuestAccount(...)` and confirmation-aware guest conversion behavior.

- [ ] **Step 1: Add failing web behavior tests**

Assert that active guest signup first prepares a `new_account_signup` handoff
with the current conversation and typed pending action, then sends ordinary
signup fields with a fresh CAPTCHA token to the guest signup route. Assert that
`session: null` returns `email_confirmation_required` without refreshing or
closing, while an immediate session verifies `guest_claim` before refreshing
account and Recents. Assert expired guests use ordinary signup and show the
check-email state.

- [ ] **Step 2: Run focused web tests and observe RED**

```bash
cd web && bun test __tests__/guest-conversion.test.ts
```

Expected: tests fail because `registerGuestAccount` and the confirmation branch
do not exist.

- [ ] **Step 3: Implement the web flow**

Replace `linkGuestIdentity` with `registerGuestAccount`, prepare the signup
handoff before acquiring a new password CAPTCHA token, call the guest signup
endpoint through authenticated `apiFetch`, and persist only a returned
permanent session. Keep the modal open in the localized check-email state when
confirmation is required.

- [ ] **Step 4: Run focused web tests GREEN**

```bash
cd web && bun test __tests__/guest-conversion.test.ts
```

Expected: active and expired guest signup branches pass without source-text-only
assertions.

- [ ] **Step 5: Commit the client flow**

```bash
git add web
git commit -m "fix(web): register guests through account signup"
```

### Task 4: Synchronize machine contracts and verify the candidate

**Files:**
- Modify: `docs/api/openapi.yaml`
- Modify: only directly affected test snapshots or evidence files.

**Interfaces:**
- Consumes: FastAPI `app.openapi()` and the completed backend/web flow.
- Produces: exact generated OpenAPI plus deterministic verification evidence.

- [ ] **Step 1: Regenerate and check OpenAPI**

Run the repository-pinned OpenAPI generator and structural compatibility gate.
The generated contract must contain `/api/v1/auth/guest/signup` and no
`/api/v1/auth/guest/link`.

- [ ] **Step 2: Run focused and broad deterministic gates**

```bash
poetry run pytest tests/test_guest_conversion.py tests/test_guest_handoff_postgres.py tests/test_guest_auth_local_supabase.py tests/test_guest_signup_local_supabase.py -q
poetry run pytest -q
cd web && bun test && bun run lint && bun run build
```

Also run `scripts/check_modularity_budget.py` against the would-be merged tree.

- [ ] **Step 3: Audit forbidden and unrelated scope**

Confirm the diff does not contain `render.yaml`, `.env.example`,
`.github/argus-env.sh`, release profiles, `.env`, `web/.env.local`, or email
template changes.

### Task 5: Publish, hosted acceptance, and review loop

**Files:**
- Create: `docs/reports/evidence/480/` only for durable non-secret acceptance artifacts.

**Interfaces:**
- Consumes: exact pushed PR head and its branch-deployed staging surface.
- Produces: hosted Auth log, email, browser/data-preservation evidence, clean review, and exact-head handoff.

- [ ] **Step 1: Reconcile current integration one way**

Fetch `origin/codex/private-alpha-next`, record its SHA, compare semantic overlap,
and merge it into this worker branch only if it advanced. Rerun invalidated
deterministic gates and the merged-tree modularity check.

- [ ] **Step 2: Push and open the requested PR**

Push `codex/issue-480-guest-registration-handoff` and open a PR targeting
`codex/private-alpha-next`, linked to #480. State why UUID-preserving linking
was originally selected and why the handoff now replaces it. Flag the manual
migration requirement conspicuously.

- [ ] **Step 3: Run exact-head hosted acceptance**

For English and Spanish separately: start as a real guest, reach one
confirmation card, complete one backtest, register, inspect the fresh email,
confirm the Supabase Auth audit action `user_signedup`, confirm the account, log
in, and verify every guest conversation and result. Then perform a genuine
existing-account email change and verify the email-change message includes the
correct old address.

- [ ] **Step 4: Run review to a clean terminal state**

Request one review on the latest head, validate each finding against the lane,
apply only proportionate fixes, rerun affected proof, and stop when the latest
delta review is clean and unresolved review-thread count is zero.

- [ ] **Step 5: Report exact terminal evidence and stop**

Report original integration base, current integration SHA, reconciliation merge
SHA if any, overlap disposition, exact PR head, migration status, deterministic
and hosted proof, CI terminal state, and clean review state. Do not merge or
deploy production.
