# Public Alpha Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the founder-locked public-alpha readiness lane as one pull
request with independently reviewable Phase 1 and Phase 2 commits, real hosted
capacity/cost evidence, capped and segmented OpenRouter traffic, a safe
allowlist-backed access-request flow, a single-purpose approval notification,
and honest localized signup states.

**Architecture:** Hosted OpenRouter key resolution moves behind one typed
traffic-class policy shared by API requests and Workflow jobs; local development
continues to use the conventional `OPENROUTER_API_KEY`. Waitlist requests add a
`requested` role to the existing service-role-only allowlist table, while an
ops-token-protected approval action sends one localized SMTP notification and
then performs the requested-to-user transition. The frontend places the
request-access state ahead of the existing signup form and renders the missing
sessionless-signup confirmation state without creating new account
infrastructure.

**Tech Stack:** Python 3.10, FastAPI, Pydantic, Supabase/Postgres with RLS,
Render Workflows, Python `smtplib`/`email.mime`, React 18, Next.js, TypeScript,
react-i18next, Bun, pytest, Playwright.

## Global Constraints

- Authoritative spec:
  `docs/superpowers/specs/2026-07-30-public-alpha-readiness.md` at
  `147ef7aa5f715bc231420d86ca0a183da2d6dd08`.
- One pull request targets `codex/private-alpha-next`; the founder merges it.
- Phase 2 implementation starts only after the Phase 1 spend cap is live in the
  OpenRouter dashboard and the hosted fail-loud deployment has been proved.
- Hosted registered traffic uses `ARGUS_PROD_OPENROUTER_API_KEY`, capped at
  `$10/week`; hosted guest traffic uses
  `ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY`, capped at `$5/week`.
- Hosted code never reads `OPENROUTER_API_KEY`; local development and evals keep
  that exact dev-only variable name.
- Missing hosted prod or guest OpenRouter keys fail application/Workflow boot
  loudly; there is no fallback to the dev key.
- Keep `permanent_account_access_allowed()` unchanged and never flip
  `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED`.
- Reuse `private_alpha_allowlist`; add no waitlist table and expose no direct
  anon/authenticated table access.
- `requested`, disabled, unknown, or malformed allowlist roles never grant
  permanent account access or fall back to `user`.
- The public access-request endpoint returns the same accepted response for new
  and duplicate requests and does not disclose allowlist state.
- Approval uses direct SMTP to `smtp.resend.com:465`, username `resend`, password
  `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD`, and sender
  `Argus <noreply@get-argus.com>`.
- Approval email sending is exactly one single-purpose helper. Do not add a
  Resend SDK/API client, a dependency, template system, retry queue, generic
  email service, invite acceptance, account pre-creation, or password setup.
- The approval link opens the existing signup form; it does not use
  `admin.inviteUserByEmail`.
- All new user-facing copy, including the approval notification, has `en` and
  `es-419` variants.
- Load evidence comes from real Render API/Workflow/Supabase infrastructure on
  standard Workflow compute. Synthetic estimates do not satisfy the gate.
- Do not weaken the required load envelope: one idle job, five simultaneous
  global jobs, two queued same-user jobs, ten queued global jobs, one invalid
  envelope retry/failure, and one controlled transient-upstream retry.
- Stop and report if the live capacity ceiling is below that envelope, the
  existing non-allowlisted signup path creates broken accounts, or the direct
  SMTP notification cannot be delivered.
- No `git stash`; preserve unrelated work and never mutate another worktree.

---

### Task 1: Segment Hosted OpenRouter Traffic And Fail Loud

**Files:**

- Create: `src/argus/llm/openrouter_key_policy.py`
- Modify: `src/argus/llm/openrouter.py`
- Modify: `src/argus/domain/discovery_search/selection.py`
- Modify: `src/argus/api/app_setup.py`
- Modify: `src/argus/api/chat/backtest_jobs.py`
- Modify: `src/argus/api/chat/backtest_admission_flow.py`
- Modify: `src/argus/api/routers/agent.py`
- Modify: `src/argus/api/routers/backtest.py`
- Modify: `workflows/backtest_job.py`
- Modify: `workflows/main.py`
- Modify: `.github/argus-env.sh`
- Modify: `.github/private-alpha-release-profile.json`
- Modify: `.github/render-env-sync.sh`
- Modify: `render.yaml`
- Modify: `.env.example`
- Modify: `docs/GUEST_PUBLIC_LAUNCH_SAFETY.md`
- Test: `tests/test_openrouter_policy.py`
- Test: `tests/test_environment_scripts.py`
- Test: `tests/test_ci_workflow.py`
- Test: `tests/test_private_alpha_readiness.py`
- Test: `tests/test_render_workflow_execution.py`
- Test: focused discovery and API job tests selected from existing suites

**Interfaces:**

- Produces:
  `OpenRouterTrafficClass = Literal["guest", "registered"]`,
  `openrouter_traffic_class(kind) -> ContextManager[None]`,
  `resolve_openrouter_api_key(kind: OpenRouterTrafficClass | None = None) -> str`,
  and `validate_hosted_openrouter_configuration() -> None`.
- Persists `openrouter_traffic_class` as the literal `guest` or `registered` in
  durable backtest-job execution metadata. The Workflow restores that scope
  before any OpenRouter-backed result readout.
- Local mode is any non-hosted `APP_ENV`; hosted mode is `APP_ENV` equal to
  `production`, `staging`, or `preview`.

- [ ] **Step 1: Add failing key-policy tests**

  Cover local dev-key resolution, registered/guest hosted resolution, both
  missing-key failures, proof that hosted mode ignores a populated
  `OPENROUTER_API_KEY`, and nested ContextVar reset:

  ```python
  def test_hosted_guest_never_falls_back_to_dev_key(monkeypatch):
      monkeypatch.setenv("APP_ENV", "production")
      monkeypatch.setenv("OPENROUTER_API_KEY", "dev-only")
      monkeypatch.delenv("ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY", raising=False)
      with pytest.raises(RuntimeError, match="ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY"):
          resolve_openrouter_api_key("guest")
  ```

- [ ] **Step 2: Run the focused policy tests red**

  Run:
  `poetry run pytest tests/test_openrouter_policy.py -q --no-cov`

  Expected: import/behavior failures because the policy does not exist.

- [ ] **Step 3: Implement the minimal typed policy and replace direct key reads**

  Keep secret values out of logs and exceptions. Hosted errors name only the
  missing variable. Replace every direct production/runtime
  `os.getenv("OPENROUTER_API_KEY")` read in the LLM and discovery paths with the
  policy.

- [ ] **Step 4: Propagate account type through durable jobs**

  Add `account_kind: Literal["guest", "registered"]` to
  `BacktestJobShadowContext`; include it as `openrouter_traffic_class` in
  `execution_metadata`; set it from the verified `AccountContext`; and restore
  the scope around Workflow execution/readout. Direct authenticated backtest
  routes persist `registered`; guest chat persists `guest`.

- [ ] **Step 5: Add API and Workflow boot validation**

  Call `validate_hosted_openrouter_configuration()` before the FastAPI lifespan
  initializes persistence and before the Workflow service constructs/starts
  tasks. Add `APP_ENV=production` to the hosted Workflow contract so it cannot
  silently behave like local development.

- [ ] **Step 6: Update environment and release contracts**

  Replace hosted `OPENROUTER_API_KEY` requirements with both segmented variables
  in `render.yaml`, the release profile, env-sync allowlists, and tests.
  Document all three variables in `.env.example`, explicitly marking the
  original name dev-only. Update the launch-safety statement to say the guest
  and registered production keys have hard weekly limits, while noting that
  the dashboard state is the live control.

- [ ] **Step 7: Prove fail-loud and regression behavior**

  Run:

  ```bash
  poetry run pytest tests/test_openrouter_policy.py \
    tests/test_environment_scripts.py tests/test_ci_workflow.py \
    tests/test_private_alpha_readiness.py \
    tests/test_render_workflow_execution.py -q --no-cov
  OPENROUTER_API_KEY= ARGUS_PROD_OPENROUTER_API_KEY= \
    ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY= ALPACA_API_KEY= \
    ALPACA_SECRET_KEY= \
    ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
    poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py \
    -q --no-cov
  ```

  Expected: all pass, and a separate `APP_ENV=production` import/startup probe
  exits nonzero while naming the missing hosted variable.

- [ ] **Step 8: Commit Phase 1 spend-cap code**

  Commit:
  `feat(openrouter): segment hosted traffic by capped key`

**Release-captain gate after Task 1:**

1. Set both new Render secret values before deployment and remove hosted use of
   the legacy `OPENROUTER_API_KEY`.
2. Push the exact Task 1 commit, deploy API and Workflow from that SHA, and
   capture one successful registered call plus one guest call.
3. Temporarily remove one new variable from a non-public validation deploy or
   use an equivalent boot probe, capture the failed boot, restore the variable,
   and return the service to healthy.
4. Confirm the OpenRouter dashboard still shows `$10/week` for prod and
   `$5/week` for guest. Only then may Task 3 begin.

### Task 2: Exercise The Real Capacity Envelope And Lock Paid Tiers

**Files:**

- Create: `scripts/benchmarks/public_alpha_render_load.py`
- Create: `tests/test_public_alpha_render_load.py`
- Create: `docs/release-evidence/public-alpha-readiness.md`
- Modify: `workflows/main.py`
- Modify: `tests/test_render_workflow_execution.py`
- Modify: `render.yaml`
- Modify: `.github/private-alpha-release-profile.json`
- Modify: `docs/PRIVATE_LAUNCH_RUNBOOK.md`
- Modify: `tests/test_private_alpha_release_docs.py`

**Interfaces:**

- Produces a sanitized artifact with schema
  `argus_public_alpha_render_load/v1` under
  `temp/benchmarks/public-alpha-render-load/`.
- The harness consumes API/app URLs, Render API key, Supabase service-role
  credentials, and dedicated load identities from environment variables; it
  never prints credentials, auth tokens, emails, or message content.
- The real backtest task uses Render plan `standard` and one retry
  (`Retry(max_retries=1, wait_duration_ms=1000)`); the cheap workflow proof task
  may retain its existing smaller plan.

- [ ] **Step 1: Add red harness-contract and Workflow tests**

  Assert the artifact contains, for every case, start/end time, admitted and
  rejected counts, p50/p95 wall time, queue-to-start, start-to-finish,
  terminal statuses, Render task-run ids, retry attempts, and sanitized failure
  codes. Assert the real task selects `standard` compute and one retry.

- [ ] **Step 2: Run focused tests red**

  Run:
  `poetry run pytest tests/test_public_alpha_render_load.py tests/test_render_workflow_execution.py -q --no-cov`

- [ ] **Step 3: Implement the real-infrastructure harness**

  Reuse the deployed internet benchmark's canonical confirmation/run/poll
  helpers. Create only dedicated temporary load identities and conversations,
  mark their artifacts with `source=public_alpha_capacity_load`, and clean them
  through existing service-role boundaries after the report is durable.
  Execute these exact cases:

  1. one job while the API is idle;
  2. five simultaneous jobs belonging to five users;
  3. three submissions for one user, proving one running and two queued;
  4. fifteen submissions across distinct users, proving five running and ten
     queued without silently admitting a sixteenth running or eleventh queued;
  5. an invalid compact job envelope dispatched to the real task, proving one
     retry then terminal failure;
  6. a service-role-created, ops-marked transient probe that fails its first
     Workflow attempt with `failed_upstream` and succeeds on the one retry.

  The controlled transient marker is accepted only on service-role-created
  capacity-test jobs and is never accepted from a public request payload.

- [ ] **Step 4: Run deterministic harness tests green**

  Run:
  `poetry run pytest tests/test_public_alpha_render_load.py tests/test_render_workflow_execution.py -q --no-cov`

- [ ] **Step 5: Release captain runs the harness against Render**

  Run the exact committed harness against the branch-deployed API, Supabase,
  and standard Workflow compute. If the live system cannot sustain the exact
  envelope, stop and report the measured ceiling without changing limits.

- [ ] **Step 6: Choose paid web-service tiers from the live evidence**

  Select the cheapest non-free plan that keeps API orchestration and the app
  responsive under the measured envelope. Record the plan name, current unit
  price, two-service fixed monthly total, standard Workflow hourly price, test
  duration, and measured Workflow cost. Set both `argus-api` and `argus-app`
  away from `free` in `render.yaml` and the live dashboard.

- [ ] **Step 7: Write durable evidence and run docs tests**

  `docs/release-evidence/public-alpha-readiness.md` must contain the exact
  candidate SHA, timestamp, URLs without secrets, case table, actual numbers,
  selected tiers, monthly cost, Workflow concurrency/backpressure values,
  dashboard cap reset cadence, and rollback command/plan.

  Run:
  `poetry run pytest tests/test_public_alpha_render_load.py tests/test_private_alpha_release_docs.py -q --no-cov`

- [ ] **Step 8: Commit Phase 1 capacity evidence**

  Commit:
  `perf(render): lock the public alpha capacity envelope`

### Task 3: Add The Fail-Closed Waitlist And Single-Purpose Approval Action

**Precondition:** The release-captain gate after Task 1 is recorded as complete
in the SDD ledger. Do not dispatch this task before that line exists.

**Files:**

- Create: Supabase migration from
  `supabase migration new add_requested_private_alpha_access`
- Create: `src/argus/domain/access_approval_email.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/api/routers/auth.py`
- Modify: `src/argus/api/routers/ops.py`
- Modify: `src/argus/api/openapi_compat.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `render.yaml`
- Modify: `.env.example`
- Modify: `.github/argus-env.sh`
- Modify: `.github/private-alpha-release-profile.json`
- Modify: `.github/render-env-sync.sh`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Test: `tests/test_access_requests.py`
- Test: `tests/test_access_approval_email.py`
- Test: `tests/test_alpha_api_supabase.py`
- Test: `tests/test_openapi_compatibility.py`
- Test: `tests/test_private_alpha_readiness.py`
- Test: migration/RLS tests following existing repository patterns

**Interfaces:**

- Public request:
  `POST /api/v1/auth/access-requests`
  with body
  `{"email": "person@example.com", "language": "en" | "es-419"}`.
- Public response for new, duplicate, already-approved, or disabled addresses:
  HTTP `202` with `{"accepted": true}`.
- Internal approval:
  `POST /internal/access-requests/approve` with ops bearer token and body
  `{"email": "person@example.com"}`.
- `send_access_approval_email(*, recipient: str, language: Language,
  signup_url: str) -> str` returns Resend's SMTP message id/accepted receipt
  without logging the recipient or password.

- [ ] **Step 1: Create the migration with the Supabase CLI**

  Discover the command first with `supabase migration new --help`, then create
  `add_requested_private_alpha_access`. Alter the existing table to permit
  `requested` and add `language text not null default 'en' check (language in
  ('en', 'es-419'))`. Preserve RLS, revoke all from `anon, authenticated`, and
  grant only `service_role`.

- [ ] **Step 2: Add red gateway, endpoint, RLS, and SMTP tests**

  Prove:

  - requested and unknown roles return `None`, never `user`;
  - the public endpoint normalizes email, records a requested row, does not
    overwrite admin/developer/user/disabled rows, and returns the same 202;
  - origin enforcement and the existing bounded auth-attempt limiter protect
    the route;
  - no `anon` or `authenticated` table privileges/policies exist;
  - SMTP uses `SMTP_SSL("smtp.resend.com", 465)`, `login("resend", password)`,
    From `Argus <noreply@get-argus.com>`, multipart plain/HTML localized copy,
    and a hashed `Resend-Idempotency-Key`;
  - a missing SMTP password fails before any allowlist role transition;
  - the internal approval action is 404 without the matching ops token.

- [ ] **Step 3: Run focused tests red**

  Run:
  `poetry run pytest tests/test_access_requests.py tests/test_access_approval_email.py tests/test_alpha_api_supabase.py -q --no-cov`

- [ ] **Step 4: Implement request capture and fail-closed role lookup**

  Keep `permanent_account_access_allowed()` untouched. Use the service-role
  gateway to insert only `requested` rows; convert uniqueness conflicts to the
  generic accepted response and never update an existing approved/disabled
  record.

- [ ] **Step 5: Implement exactly one approval email helper**

  Build the two localized literal bodies inside
  `send_access_approval_email`; do not introduce a base mailer, template
  registry, background job, or dependency. The link is
  `${ARGUS_APP_ORIGIN}/?auth=signup`.

- [ ] **Step 6: Implement the internal approval ordering**

  Load an active `requested` row and its language. Send first with the
  deterministic hashed idempotency key, then compare-and-set
  `role=requested AND disabled_at IS NULL` to `role=user`. Return success only
  after both operations succeed. This ordering prevents a silently approved
  visitor if SMTP fails; Resend idempotency prevents a duplicate message if an
  accepted send is followed by a transient database failure and the operator
  retries.

- [ ] **Step 7: Update environment and API contracts**

  Add `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD` as `sync: false` to the API service
  and environment/release contracts. Add the public endpoint to
  `docs/API_CONTRACT.md`, add requested/language truth to `docs/DATA_MODEL.md`,
  and add the internal approval operation as an exact named OpenAPI exclusion.

- [ ] **Step 8: Generate and verify OpenAPI**

  Run:

  ```bash
  poetry run python scripts/generate_openapi_artifact.py
  poetry run pytest tests/test_openapi_compatibility.py \
    tests/test_access_requests.py tests/test_access_approval_email.py \
    tests/test_alpha_api_supabase.py -q --no-cov
  ```

- [ ] **Step 9: Commit Phase 2 backend**

  Commit:
  `feat(access): add waitlist requests and approval email`

### Task 4: Add Honest Request-Access And Check-Email UI States

**Files:**

- Modify: `web/lib/argus-api.ts`
- Modify: `web/lib/guest-api.ts`
- Modify: `web/app/page.tsx`
- Modify: `web/components/auth/AuthForm.tsx`
- Modify: `web/components/guest/GuestConversionModal.tsx`
- Modify: `web/components/guest/useGuestConversion.ts`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `web/__tests__/access-request-flow.test.ts`
- Test: focused existing auth and guest-conversion tests
- Test: `web/e2e/public-alpha-access-request.spec.ts`

**Interfaces:**

- `requestAccess({email, language}) -> Promise<{accepted: true}>`.
- `signupWithEmail(...) -> Promise<{response: AuthResponsePayload,
  needsEmailConfirmation: boolean}>`, where the boolean is true only when the
  successful response has no persisted session.
- Existing authenticated signup success still navigates to `/chat`.

- [ ] **Step 1: Add red interaction and localization tests**

  Cover landing signup and guest conversion in both languages:

  - the default gated surface explains request access;
  - “Already approved? Sign up” reveals the existing `AuthForm`;
  - submitting a request shows the same non-enumerating success state;
  - a sessionless successful signup shows “Check your email” and does not route
    to `/chat`;
  - a signup response with a session keeps the existing navigation;
  - the guest conversation remains present behind the modal;
  - keyboard focus moves to the state heading and returns correctly.

- [ ] **Step 2: Run focused frontend tests red**

  Run:
  `cd web && bun test __tests__/access-request-flow.test.ts`

- [ ] **Step 3: Implement the minimal API-client result types**

  Preserve the raw auth response while exposing
  `needsEmailConfirmation = !response.session` after the session persistence
  attempt. Add the public request-access client without exposing backend
  Problem Details to distinguish list membership.

- [ ] **Step 4: Wrap, do not replace, the existing forms**

  Add request-access and approved-signup modes around `AuthForm` and
  `GuestConversionModal`. Keep existing allowlisted signup and guest identity
  linking paths intact. Add the sessionless success panel to the existing form
  surface; do not add a route or page.

- [ ] **Step 5: Add exact EN/es-419 copy**

  Add localized heading, explanation, email label, request action, generic
  accepted state, approved-user signup link, and check-email state. Keep the
  Spanish locale as `es-419`.

- [ ] **Step 6: Run focused and broad frontend verification**

  Run:

  ```bash
  cd web
  bun test __tests__/access-request-flow.test.ts __tests__/guest-session.test.ts \
    __tests__/alpha-frontend.test.ts
  bun run lint
  bun run build
  ```

- [ ] **Step 7: Commit Phase 2 frontend**

  Commit:
  `feat(auth): add localized public alpha signup states`

### Task 5: Prove The Exact Candidate And Publish The Founder Handoff

**Files:**

- Modify: `docs/release-evidence/public-alpha-readiness.md`
- Modify: `docs/GUEST_PUBLIC_LAUNCH_SAFETY.md` if live evidence requires a
  factual correction
- Create: sanitized screenshots under the repository's accepted release-evidence
  location if the project stores images; otherwise attach them directly to the
  PR and record their names/hashes in the evidence document
- Test: all focused and standing release gates

**Interfaces:**

- Consumes the exact Phase 1 and Phase 2 commit SHAs.
- Produces a Draft or posted PR targeting `codex/private-alpha-next`.

- [ ] **Step 1: Validate and apply the migration on the approved QA target**

  Use the repository non-production guard before any hosted QA migration.
  Verify the requested-role constraint, duplicate request behavior, fail-closed
  access lookup, and RLS/privilege posture with test queries. Do not migrate an
  unapproved shared target.

- [ ] **Step 2: Verify the founder-set SMTP secret exists before deployment**

  Audit Render environment metadata without printing values. If
  `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD` is absent, stop the deployment and ask the
  founder to set it; do not invent, copy, or log the credential.

- [ ] **Step 3: Deploy the exact Phase 2 candidate**

  Keep `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=false`. Capture API/app/Workflow
  deploy ids, exact SHA, health/readiness, and environment contract audit.

- [ ] **Step 4: Prove approval and signup email delivery**

  Create a dedicated requested row for `delivered@resend.dev`, call the
  ops-token-protected approval action, and verify the row becomes `user`.
  Query Resend delivery logs using verification-only connector access and
  capture the accepted/delivered record without secrets. Separately exercise a
  sessionless confirmed-signup response against the running instance and record
  the visible check-email state.

- [ ] **Step 5: Capture EN/es-419 browser evidence**

  Run Playwright against the branch-deployed app and capture desktop plus mobile
  screenshots of request access, request accepted, approved signup, and check
  email in both locales. Do not enter or expose a founder password.

- [ ] **Step 6: Run the final backend/frontend gates**

  Run:

  ```bash
  OPENROUTER_API_KEY= ARGUS_PROD_OPENROUTER_API_KEY= \
    ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY= ALPACA_API_KEY= \
    ALPACA_SECRET_KEY= \
    ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
    poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py \
    -q --no-cov
  poetry run pytest tests/test_openrouter_policy.py \
    tests/test_public_alpha_render_load.py tests/test_access_requests.py \
    tests/test_access_approval_email.py tests/test_openapi_compatibility.py \
    tests/test_alpha_api_supabase.py tests/test_environment_scripts.py \
    tests/test_ci_workflow.py tests/test_private_alpha_readiness.py \
    tests/test_private_alpha_release_docs.py \
    tests/test_render_workflow_execution.py -q --no-cov
  cd web && bun test && bun run lint && bun run build
  git diff --check
  ```

- [ ] **Step 7: Reconcile the spec's stale inference footer**

  Remove the two inference bullets that claim decision 6 and hosted confirm
  email remain undecided/unverified; the locked decisions and founder-provided
  live verification supersede them.

- [ ] **Step 8: Push and open the one PR**

  The PR body includes Summary, Changes, Motivation, Impact, Testing,
  Risks/Rollback, Checklist, the actual Render plan/monthly cost, Workflow test
  cost, live load table, cap reset cadence, fail-loud proof, Resend delivery
  proof, screenshots, migration/RLS evidence, and the explicit statement that
  the founder alone merges and later flips public account access after 14 clean
  consecutive days.
