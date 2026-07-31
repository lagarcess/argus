# Public alpha readiness: capacity split, load proof, spend cap, and an honest conversion wall

Founder-locked 2026-07-30. This is not a feature lane; it's the operational
readiness gate for turning Argus's guest and chat surfaces from
warm-up/session availability into standing 24/7 availability, ahead of
recruiting a wider set of testers.

## 1. Why

Today Argus is warm-started per session, not standing. The active roadmap's
outcome 2 already unlocked security/usage controls and per-turn recovery
guarantees (`docs/specs/private-alpha-interim-roadmap.md`), but those were
proven under founder-driven, bounded sessions — never under continuous,
anonymous, unattended traffic. The decision memo frames the goal of this
whole phase as finding *"the smallest private-alpha execution envelope that
gives us honest PMF signal from serious users"*
(`docs/archive/private-alpha-backtest-execution-capacity.md`) — not maximum
scale, not revenue. Going 24/7 with open guest access is the first time that
envelope gets tested by real, unattended demand instead of a founder at a
keyboard. This lane exists to prove the envelope before opening the door
wider, and to make sure the door, once opened, doesn't dead-end the people
who walk through it.

## 2. Locked decisions

1. **Two independent scaling levers, not one.** `argus-api`'s Render plan
   tier and Render Workflow concurrency are tuned separately. Backtests scale
   horizontally through Workflows (already wired:
   `ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED=true`); the API only moves up a
   tier once it is lean and orchestration itself is the proven bottleneck —
   never as a substitute for fixing the in-process coupling. One move is
   forced, not chosen: both services sit on Render's `free` plan today,
   which spins down on idle — that spin-down IS the current
   warm-up-per-session behavior. Standing 24/7 availability therefore
   requires moving both `argus-api` and `argus-app` off `free` in this
   lane; the load test decides WHICH paid tier, not whether. Expect
   roughly $7/mo per service at the entry paid tier (verify current Render
   pricing at change time) plus usage-based Workflow compute; the PR
   records the chosen tiers and the actual monthly number.
2. **The load test runs on real infrastructure, not local/synthetic, before
   any tier decision.** Concurrency envelope, already scoped in the archived
   capacity doc: 1 job idle, 5 simultaneous globally, 2 queued same-user, 10
   queued globally, one invalid-envelope retry, one upstream transient-
   failure retry. Runs on Render standard workflow compute.
3. **A hard OpenRouter spend cap is required before 24/7 exposure.** Target
   shape is two segmented keys (guest, registered) — OpenRouter confirms
   per-key limits reject further requests on that key before they reach the
   provider, fully isolating one segment's overspend from the other, though
   both still draw from one shared account credit balance. If the two-key
   code change (threading account type into the LLM client's key selection)
   can't land in this window, ship a single capped production key as the
   interim floor and say so explicitly — never ship with no cap at all.
   **Key + env topology (locked 2026-07-30, keys already created):**
   - `ARGUS_PROD_OPENROUTER_API_KEY` — new `argus-prod` key, $10/week
     reset. All hosted non-guest traffic.
   - `ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY` — new `argus-guest` key,
     $5/week reset. Hosted guest traffic once the key-selection code lands.
   - `OPENROUTER_API_KEY` — the original uncapped `argus-dev-key`, demoted
     to dev/local-only. **NOT renamed** — every eval script and tool
     expects the conventional name, and renaming invites the fake-failure
     env drift this repo has been burned by before. Hosted runtime must
     never read it.
   - **No silent fallback, fail loud:** in hosted environments, a missing
     `ARGUS_PROD_OPENROUTER_API_KEY` (or guest var, once guest routing
     lands) is a boot failure — never a fallback to `OPENROUTER_API_KEY`.
     A silent fallback would route production onto the uncapped dev key
     and defeat the cap invisibly. Local dev keeps using
     `OPENROUTER_API_KEY` exactly as today.
   - **Deploy ordering:** the Render dashboard/CLI values for the new env
     vars must exist BEFORE the deploy that reads them ships — a
     `render.yaml` change referencing a `sync: false` var with no
     dashboard value boots the API keyless. The founder has authorized
     env-var changes via Render CLI, so the builder may set them, but the
     ordering rule stands regardless of who does it.
   Never cap the shared dev key: founder eval sessions must neither trip
   the production cap nor pollute decision 6's zero-trip count, and the
   prod key's usage graph is the first clean production-cost metric
   separated from dev burn.
4. **Registration stays allowlist-gated through this lane.** The signup form
   in `GuestConversionModal.tsx` already exists (`POST /auth/signup`, gated
   by `permanent_account_access_allowed()` in
   `src/argus/api/guest_access.py`) — the UI and endpoint are not being
   rebuilt. **Correction (2026-07-31): this form was NOT actually working
   end to end against production before decision 11 fixed it** — the
   original "already works for allowlisted emails" claim was based on
   reading the code, not exercising it live, and production's CAPTCHA
   requirement was silently rejecting every signup attempt regardless of
   allowlist status. See decision 11 for the fix. The gap this decision
   still addresses is separate: a non-allowlisted visitor can fill the
   form out and gets rejected with no explanation or path forward. The
   copy changes from that silent-rejection form to an honest
   "request access" prompt for non-allowlisted visitors. Nothing about
   `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED` changes here.
5. **Waitlist requests reuse the existing `private_alpha_allowlist` table**
   (a pending/requested state on the same table, same `role`-column
   mechanism already used for admin/developer), not a new model.
6. **The exit criterion for opening registration is written down now, not
   decided later.** 14 consecutive days of guest traffic with zero
   spend-cap trips and zero capacity incidents. Any incident resets the
   clock — the window must be a clean, unbroken 14 days. Once met,
   `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED` flips — manually, by the founder,
   never by a PR merge or an automated check.
7. **Real email delivery is a prerequisite, not an afterthought — provider is
   Resend.** Supabase's built-in email service is rate-limited to a handful
   of emails per hour, not viable for waitlist approvals or signup
   confirmations at any real volume. Resend is the chosen SMTP provider: free
   tier (3,000/month, 100/day) comfortably covers pre-PMF volume, it's the
   documented default pairing for Supabase SMTP, and setup is copy-paste
   credentials with no sandbox-approval step (unlike AWS SES). Account and
   API key already created by the founder (2026-07-30); wiring the key into
   Supabase's hosted Auth → SMTP settings is a founder action (credential
   entry), not something an agent does, and must happen before either flow
   sends mail for real users. Domain `get-argus.com` purchased via
   Cloudflare Registrar (already the Turnstile provider) on 2026-07-30 for
   DNS/SPF/DKIM verification, since Argus has no domain today (still on
   Render's default `*.onrender.com`). Sender address will be
   `noreply@get-argus.com` or similar under this domain.
8. **Email confirmation is the chosen low-friction signal filter, on
   purpose.** Verified live in the hosted Supabase dashboard on
   2026-07-30 (Auth → Sign In / Providers): "Confirm email" is ON,
   "Allow new users to sign up" is ON. One click in an email is the
   deliberate friction floor: enough to filter typo/throwaway addresses on
   both the waitlist request and eventual registration, not enough to be a
   real barrier to a genuinely interested tester.
9. **Email delivery must be provable without the founder in the loop, and
   approval must NOT use Supabase's admin invite mechanism.**
   The founder will not be available to check an inbox during the build.
   (a) Send mechanism: **direct SMTP from the Argus backend using Python's
   standard library** (`smtplib`/`email.mime` — no third-party SDK, no new
   dependency in `pyproject.toml`), connecting to `smtp.resend.com` with
   the same Resend credentials already verified working for Supabase's
   Auth emails. Supabase's own Auth SMTP is confirmed scoped to Auth
   lifecycle emails only (signup/OTP/recovery/invite) with no arbitrary
   transactional-email operation — so the approval notification cannot
   ride that path as originally written; sending it directly is the
   correct amendment, not a scope expansion. The email links the approved
   visitor back to the EXISTING signup form (`AuthForm`/
   `GuestConversionModal`, decision 4) — it does not pre-create an
   account. **Explicitly ruled out: Supabase's `admin.inviteUserByEmail` /
   built-in invite email.** That mechanism pre-creates an unconfirmed Auth
   user and sends a non-PKCE link that Argus's frontend has no page built
   to complete (`detectSessionInUrl` is off; the one email-link completion
   page expects a PKCE `code`, built for password recovery, not invites)
   — completing it would require a new invite-acceptance/password-setup
   flow, real new account infrastructure and out of scope. **Scope guard:**
   this stays a single-purpose helper for exactly this one email — it is
   not the start of a general email-sending capability; do not generalize
   it or add a template system, retry queue, or additional email types
   beyond this one. The Resend SMTP password is duplicated as a new Argus
   secret, `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD` — a credential
   existing in two secret stores you already control (Supabase dashboard,
   Render env), not a new external integration surface. **Already set
   locally (2026-07-30):** the founder added `RESEND_API_KEY` and
   `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD=${RESEND_API_KEY}` to the shared
   integration `.env`, for local dev/testing only — this is NOT the
   hosted Render secret, which is a separate, later value set via CLI per
   section 4's ordering rule. Before relying on the local value, confirm
   the `${RESEND_API_KEY}` reference actually resolved (value starts with
   `re_`) rather than trusting the literal string blindly — `.env`
   interpolation depends on the loader supporting it. (b) Autonomous
   proof: verify delivery by sending to Resend's test inbox
   (`delivered@resend.dev`) and capturing the Resend dashboard/API email
   log showing the send accepted and delivered — screenshot or API
   response attached to the PR. This same recipe satisfies section 4's
   deferred live test-send; no human inbox is part of the acceptance
   loop, and the founder spot-checks the Resend log afterward at their
   leisure.
10. **The existing confirmed-signup flow is missing a "check your email"
    state — fixing it is in scope.** Right now a sessionless signup
    response (expected when email confirmation is required) is treated as
    success and the user is redirected straight to `/chat` instead of
    being told to confirm their email. This is a live, user-facing gap
    exposed the moment decision 8 turned "Confirm email" on — it directly
    contradicts the spec's own goal of not dead-ending people who walk
    through the door. Fix: a UI state on the existing signup form showing
    "check your email to confirm," driven off the signup response's
    session-presence — not a new page, not new backend account
    infrastructure, just a missing state in a flow that already exists.
11. **Production hosted Supabase Auth had three settings mismatched
    against this spec's assumptions — proven via Management API against
    the confirmed production project ref (`lgdhvepyrzbnscqssgqq`, no
    preview branch exists for this lane), fixed as follows:**
    - **Native anonymous sign-ins were disabled — turn ON.** Proven load-
      bearing, not assumed: `POST /auth/guest`
      (`src/argus/api/routers/auth.py:142`) calls
      `supabase_gateway.sign_in_anonymously()`, which calls Supabase's
      `auth.sign_in_anonymously()`
      (`src/argus/domain/supabase_guest_accounts.py:44`) — hosted guest
      bootstrap cannot function without this. This corrects and replaces
      any earlier assumption in this spec that guest mode's mechanism was
      independent of Supabase's native anonymous auth.
    - **Turnstile/CAPTCHA is enabled project-wide, and the existing
      signup/login flow was never wired to supply a token — this was a
      pre-existing gap, not something this lane broke.** Fix: reuse the
      existing `acquireGuestCaptchaToken` mechanism
      (`web/lib/guest-captcha.ts`, already built for guest mode) in the
      signup/login submission too. This is reuse, not new CAPTCHA
      infrastructure, and stays in scope. Do not disable CAPTCHA
      project-wide to work around this —
      `docs/GUEST_PUBLIC_LAUNCH_SAFETY.md` already documents it as a
      guardrail. First confirm Supabase has no per-flow CAPTCHA scoping
      option (quick dashboard check) before building the token-wiring, in
      case a simpler toggle exists.
    - **`mailer_autoconfirm=true` on the live Management API contradicts
      decision 8 — set it to `false` via the Management API directly and
      confirm it holds.** Treat this specific API field as ground truth
      over the dashboard's "Confirm email" toggle, which was visually
      confirmed ON earlier but does not conclusively explain this
      discrepancy; don't spend time debugging why they disagree, just set
      the authoritative value.
    **Authorization:** the agent may make all three of these production
    Supabase Auth changes itself via the Management API — these are
    configuration toggles, not credential entry, and the founder has
    already granted equivalent infra authority for Render CLI changes
    (decision 3). Report the before/after state of all three for the
    record once changed.

## 3. Reserved / parked scope

- **Allowlist repurposed into a beta-feature tier** (vs. a pure access
  gate) — deferred until after registration opens for real; this lane does
  not build any feature-gating layer.
- **Per-user OpenRouter keys** (one capped key per registered account,
  which OpenRouter's Provisioning API supports) — noted as the stronger
  future option once there's real per-user usage data to size against; this
  lane ships the simpler two-segment version only.
- **Any UI surface distinguishing beta vs. public-alpha users** — out of
  scope; nothing here builds a visible tier distinction.
- **New cost/analytics infrastructure** — the spend cap is external
  (OpenRouter dashboard config), not a new internal ledger or PostHog wiring
  beyond what already exists in `src/argus/observability/cost_ledger.py`.
- **Custom-branded Resend email templates** — default transactional
  templates are enough for a waitlist-approval email at this volume;
  worth revisiting once there's an actual list of users seeing them.

## 4. Contract gates

- `render.yaml` — both services move off `free` (idle spin-down is
  incompatible with 24/7 — decision 1), tier per service chosen from the
  load-test numbers, monthly cost recorded in the PR; Render Workflow
  concurrency settings documented alongside the change that sets them (not
  necessarily in this same file, but recorded somewhere durable); the two
  new OpenRouter env vars added (`sync: false`), replacing hosted use of
  `OPENROUTER_API_KEY` per decision 3's topology — dashboard values set
  before the deploy that reads them; `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD`
  added (`sync: false`, decision 9) — same ordering rule, dashboard value
  before the deploy that reads it.
- `.env.example` — document the three-var OpenRouter scheme so a fresh
  checkout knows `OPENROUTER_API_KEY` is dev-only; document the new SMTP
  password var.
- Hosted Supabase Auth dashboard — explicitly confirm/set "Confirm email";
  configure Resend as the custom SMTP provider. Neither is a code change,
  both are real configuration that must be verified, not assumed from local
  defaults. **Domain (`get-argus.com`) and SMTP config are done as of
  2026-07-30** — DKIM/SPF/DMARC verified in Resend, custom SMTP saved in
  Supabase, "Confirm email" and "Allow new users to sign up" both verified
  ON in the live dashboard. Acceptance signal: a real signup or
  password-reset against a running instance actually delivers an email to
  an inbox — not just that the SMTP config saved without error. This live
  test-send is deferred, on purpose, to whenever Phase 2 is actually being
  built and tested against a running server (no promotion/deployment is
  live yet) — it is not a precondition to starting Phase 1 or committing
  this spec, only to Phase 2's own PR counting as ready.
- OpenRouter dashboard — create/configure the capped key(s); record the
  reset cadence chosen (daily/weekly/monthly) and why.
- `docs/GUEST_PUBLIC_LAUNCH_SAFETY.md` — currently states *"there is no hard
  provider spending limit."* Update once the cap is live; this line is the
  literal acceptance signal for locked decision 3.
- `private_alpha_allowlist` — migration for whatever pending/requested state
  the waitlist needs; no new table.
- `docs/API_CONTRACT.md` + OpenAPI artifact — the waitlist "request access"
  capture needs a new public endpoint. The existing `POST /auth/signup`
  creates a full Supabase auth user and rejects non-allowlisted emails
  outright; a request-access flow instead needs to record a pending row on
  `private_alpha_allowlist` without creating an auth account, for a visitor
  who isn't allowlisted yet. That's a new endpoint, not a repurposing of
  `/auth/signup` — document it and regenerate the OpenAPI artifact as part
  of this lane. This was missing from the original contract-gates pass and
  is the one real API-contract item this spec introduces.
- Frontend conversion-wall copy — EN/es-419, screenshots required before the
  PR counts as ready.

## 5. Execution contract

**PR shape: one PR delivering the whole spec.** Phase 1 and Phase 2 land as
separate commits inside it, not separate PRs — matching how the other lanes
this cycle shipped (spec as first commit, slices as commits, one PR).

**Phase 1 commits — independent of Phase 2, can land in any commit order:**
- Load test execution against real infra + written-up results.
- Capacity split configuration (API tier + Workflow concurrency).
- Spend cap configuration (OpenRouter dashboard + the two-key code change,
  or the documented single-key interim).

**Phase 2 commits — sequenced after Phase 1's spend cap is live** (a real
OpenRouter dashboard state, not a code dependency, but still a genuine
safety ordering: don't widen the door before the spend cap exists):
- New `POST` endpoint for waitlist request capture (see the API-contract
  gate above) + `private_alpha_allowlist` migration.
- Conversion-wall copy change (request-access framing ahead of the existing
  `AuthForm`/`GuestConversionModal` signup form for non-allowlisted
  visitors — the form itself is not being rebuilt, it already works for
  allowlisted emails).
- Approval notification: direct stdlib SMTP send from the Argus backend
  to `smtp.resend.com`, linking back to the existing signup form — NOT a
  Supabase admin invite, NOT a Resend SDK/API integration (decision 9).
  New secret: `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD` in Render.
- "Check your email" UI state on the existing signup form for the
  sessionless-response case (decision 10) — also fixes a live gap in
  today's flow, not just new-user copy.

This is the smaller of the two phases in surface area, since the
account-creation backend and UI already exist end to end for allowlisted
users — but it does add one new endpoint, which is why the API-contract
gate above matters.

**Proof required before the PR counts as ready:** every gate from section 4
actually done (dashboard settings verified, not assumed; OpenAPI
regenerated); EN/es-419 for anything user-facing; screenshots for the
conversion-wall change; the load test's actual numbers written up
(section 2); the live test-send (section 4) confirmed against a running
instance before this PR is called done, even though it isn't a
precondition to starting the work.

**Where it stops:** a Draft or posted PR, same as every other lane this
cycle. The founder merges. The founder alone flips
`ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED` later, manually, once locked decision 6's
criterion is actually observed — this is never something a PR, a script, or
an agent decides on its own.

## 6. Stop conditions

- If the load test reveals a real capacity ceiling below what a wider public
  alpha needs, stop and report the actual number — do not quietly lower the
  test's bar to make it pass.
- If a custom SMTP/email provider requires signing up for a new paid vendor
  account, stop and get explicit founder approval before creating it.
- If the two-key OpenRouter segmentation can't land in this window, ship the
  single account-wide cap and report the gap plainly — do not ship with no
  cap while waiting for the better version.
- Self-serve registration already exists end to end for allowlisted emails —
  `web/components/auth/AuthForm.tsx` wired through
  `web/components/guest/GuestConversionModal.tsx`, backed by a real
  `POST /auth/signup` in `src/argus/api/routers/auth.py`, gated by
  `permanent_account_access_allowed()`. Phase 2 is a copy/capture change
  ahead of that existing surface, not new account-creation infrastructure.
  If the existing signup path turns out to have gaps deeper than "no
  friction filter and confusing rejection copy" once actually exercised
  (e.g. it silently creates disabled/broken accounts for non-allowlisted
  emails instead of cleanly rejecting), stop and report rather than quietly
  expanding scope.

## Sources

### Argus authority
- `docs/specs/private-alpha-interim-roadmap.md`
- `docs/specs/private-alpha-next-decision-memo.md`
- `docs/archive/private-alpha-backtest-execution-capacity.md`
- `docs/GUEST_PUBLIC_LAUNCH_SAFETY.md`
- `render.yaml`, `supabase/config.toml`
- `src/argus/domain/supabase_gateway.py` (allowlist `role` column,
  `signup()` at line ~268 calls plain `auth_client.auth.sign_up(...)` with no
  `email_confirm` override)
- `src/argus/api/routers/auth.py` (`POST /auth/signup`, line ~654)
- `src/argus/api/guest_access.py` (`permanent_account_access_allowed()`,
  line ~46 — the actual allowlist-vs-public gate)
- `web/components/auth/AuthForm.tsx`, `web/components/guest/GuestConversionModal.tsx`,
  `web/app/signup/page.tsx` (existing self-serve signup UI, confirmed live
  today for allowlisted emails)

### External primary guidance
- OpenRouter — per-user/per-key spending limits:
  <https://openrouter.zendesk.com/hc/en-us/articles/51680687417499-Can-I-create-one-API-key-per-user-with-its-own-spending-limit-Management-API-keys>
- OpenRouter — Provisioning API Keys:
  <https://openrouter.ai/docs/features/provisioning-api-keys>
- OpenRouter — API Credit & Rate Limits:
  <https://openrouter.ai/docs/api_reference/limits>
- Supabase — email confirmation defaults and SMTP rate limit:
  <https://supabase.com/docs/guides/auth/auth-email>
- Resend — Supabase SMTP integration guide:
  <https://resend.com/docs/send-with-supabase-smtp>

### Inference
- The exact exit-criterion number in locked decision 6 is not decided — it's
  marked as a founder input, not invented.
- Whether the hosted Supabase project's "Confirm email" setting is currently
  on is inferred from Supabase's documented hosted-default (on) but not
  independently verified against the live dashboard.
