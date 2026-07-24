# Argus Guest Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a public visitor use the real Argus chat, complete one historical simulation, and convert into a permanent account without losing the temporary workspace.

**Architecture:** A real Supabase anonymous identity owns one temporary, owner-scoped workspace. A typed server account context controls guest capabilities and lifetime allowances while the existing LangGraph runtime, message settlement, backtest admission, feedback, history, and search paths remain canonical. New-account conversion links an identity in place; existing-account conversion uses one atomic, single-use workspace claim.

**Tech Stack:** FastAPI, Pydantic, Supabase Auth/Postgres/RLS, PostgreSQL functions, LangGraph composition only, Next.js/React, TypeScript, i18next, Playwright, pytest, Bun.

## Global Constraints

- Start from a founder-prepared worktree based on the latest
  `codex/private-alpha-next`.
- Read the mandatory canon, active roadmap, decision memo,
  `docs/superpowers/specs/2026-07-24-guest-experience-design.md`, and the current
  Always Progresses status before editing.
- Work through Blocks 1–4 in order. Each block gets its own reviewable commits
  and must pass its stop gate before the next block begins.
- Do not modify `src/argus/agent_runtime/**`, interpreter prompts, strategy
  capability semantics, market-data providers, or backtest math.
- Do not add a guest chat brain, fake result path, guest prompt tier, frontend
  quota counter, or browser-only authorization.
- Server truth comes from a verified Supabase Auth user plus a server-owned
  guest-workspace record. Never trust email, display name, editable metadata,
  or a public frontend flag as proof of guest status.
- `ARGUS_GUEST_ACCESS_ENABLED` and
  `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED` default off. The frontend flag is
  presentation-only.
- Public enablement, deployment, push, PR mutation, merge, and issue closure
  require separate founder authorization.
- Stop immediately on a cross-owner read, partial ownership transfer,
  double-charge, runtime regression, or contradiction with current canon.
- After each block, reassess complexity and remove machinery that does not
  protect ownership, conversion, cost, abuse resistance, or rollback.

---

## Phase 0 — Verify the lane and freeze the boundary

### Task 1: Prove the worktree and current integration baseline

**Files:**

- Read:
  - `docs/PRODUCT.md`
  - `docs/ARCHITECTURE.md`
  - `docs/API_CONTRACT.md`
  - `docs/DATA_MODEL.md`
  - `.agent/designs/argus/DESIGN.md`
  - `docs/specs/private-alpha-next-roadmap.md`
  - `docs/specs/private-alpha-next-decision-memo.md`
  - `docs/superpowers/specs/2026-07-24-guest-experience-design.md`
  - `docs/superpowers/specs/2026-07-23-always-progresses-continuity-design.md`
  - `docs/superpowers/plans/2026-07-23-always-progresses-continuity.md`

- [ ] Run the fail-closed preflight:

```bash
git rev-parse --show-toplevel
git branch --show-current
git status --porcelain
git fetch origin codex/private-alpha-next
git merge-base --is-ancestor origin/codex/private-alpha-next HEAD
git rev-parse HEAD
```

Expected: intended worktree, intended feature branch, clean status, and current
integration ancestry. Stop instead of switching, rebasing, or stashing when any
fact differs.

- [ ] Record the starting SHA and current status of Always Progresses,
  Grounded Discovery, and Full Omnisearch.
- [ ] Inventory the live owners before changing code:

```bash
rg -n "current_user|private_alpha_email_allowed|signup|login" \
  src/argus/api src/argus/domain
rg -n "usage_counters|settling_usage|admit_backtest_job" \
  src/argus supabase/migrations tests
rg -n "ChatInterface|ChatSidebar|ProfileMenu|SettingsMenu|FeedbackDialog" \
  web/components web/app web/lib
rg -n "create table|user_id uuid|conversation_id uuid|thread_id" \
  supabase/migrations
```

- [ ] Write the exact owner graph found at this head into the first migration's
  SQL comments. Do not rely on the older design's list when Always Progresses
  has added tables.
- [ ] Confirm no runtime file is in the proposed diff.

---

## Block 1 — Guest identity and policy spine

### Task 2: Activate the typed canon before implementation

**Files:**

- Modify: `docs/PRODUCT.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/api/openapi.yaml`
- Modify: `.agent/designs/argus/DESIGN.md`
- Test: `tests/test_alpha_artifacts.py`
- Test: `tests/test_alpha_api_supabase.py`

- [ ] Add red contract tests for these exact public shapes:

```python
class GuestAccountSummary(BaseModel):
    expires_at: datetime
    conversation_limit: Literal[1]
    message_limit: Literal[10]
    simulation_limit: Literal[1]
    feedback_limit: Literal[5]


class AccountCapabilities(BaseModel):
    can_create_additional_conversation: bool
    can_manage_conversation: bool
    can_save_decision: bool
    can_manage_account: bool
    can_use_omnisearch: bool
    can_submit_feedback: bool


class UserResponse(BaseModel):
    user: User
    account_kind: Literal["guest", "registered"]
    guest: GuestAccountSummary | None
    capabilities: AccountCapabilities
```

- [ ] Define the endpoint contract:

```text
POST /api/v1/auth/guest
POST /api/v1/auth/guest/link
POST /api/v1/auth/guest/handoffs
POST /api/v1/auth/guest/handoffs/{handoff_id}/claim
GET  /api/v1/me
```

All mutation failures use existing Problem Details, request IDs, secure cookie
rules, origin checks, and idempotency conventions.

- [ ] Define the additive `usage_counters.period = guest_session` contract and
  the fixed `period_start`/`period_end` semantics.
- [ ] Document that `profiles.email` is nullable only for a verified anonymous
  Auth user; permanent profiles still require the verified provider email.
- [ ] Document the exact account-conversion transfer boundary and the tables
  deliberately excluded from owner rewriting:
  `cost_ledger_entries` and security/route evidence retain their original
  anonymous attribution or become null through existing FK behavior.
- [ ] Run:

```bash
poetry run pytest tests/test_alpha_artifacts.py tests/test_alpha_api_supabase.py -q --no-cov
```

Expected before implementation: new contract pins fail. Commit only after the
canon and static contract agree.

### Task 3: Add server flags and one typed account context

**Files:**

- Create: `src/argus/api/guest_access.py`
- Modify: `src/argus/api/dependencies.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/api/routers/profile.py`
- Modify: `.env.example`
- Modify: `web/.env.local.example`
- Test: `tests/test_guest_access_policy.py`
- Test: `tests/test_private_alpha_release_profile.py`
- Test: `tests/test_render_release_profile_contract.py`

- [ ] Write failing tests for:
  - both server flags defaulting off;
  - client/server flag mismatch failing closed;
  - verified `is_anonymous=true` producing `account_kind=guest`;
  - a registered user producing `account_kind=registered`;
  - editable metadata never changing account kind;
  - guest expiry and capabilities coming from the server record;
  - current private-alpha behavior remaining byte-compatible when flags are
    off.

- [ ] Implement the exact interfaces `guest_access_enabled() -> bool`,
  `public_account_access_enabled() -> bool`, and
  `account_context(request: Request) -> AccountContext` around:

```python
@dataclass(frozen=True)
class AccountContext:
    kind: Literal["guest", "registered"]
    user_id: str
    expires_at: datetime | None
    capabilities: AccountCapabilities
```

`current_user()` verifies the provider user, stores one typed
`AccountContext` on `request.state`, and returns the existing profile model so
ordinary route ownership remains unchanged.

- [ ] Change `User.email` to `str | None`, then fix every consumer to require a
  permanent email explicitly where needed. Do not invent a placeholder email.
- [ ] Make `/me` return the typed account and capability truth.
- [ ] Run:

```bash
poetry run pytest \
  tests/test_guest_access_policy.py \
  tests/test_private_alpha_release_profile.py \
  tests/test_render_release_profile_contract.py -q --no-cov
```

### Task 4: Add the guest workspace, RLS, and fixed expiry

**Files:**

- Create: `supabase/migrations/20260724000001_add_guest_workspaces.sql`
- Modify: `src/argus/domain/supabase_gateway.py`
- Create: `src/argus/domain/guest_workspaces.py`
- Test: `tests/test_guest_workspace_postgres.py`
- Test: `tests/test_supabase_gateway.py`
- Test: `tests/test_checkpoint_rls_migration.py`

- [ ] Start with real-Postgres red tests for:
  - nullable guest profile email;
  - one workspace and at most one conversation per anonymous owner;
  - fixed seven-day expiry that activity cannot extend;
  - owner-only guest workspace visibility;
  - another guest and a permanent user seeing zero rows;
  - browser roles having no direct write authority over expiry, claim state, or
    cleanup state.

- [ ] Create server-owned tables:

```sql
create table public.guest_workspaces (
  user_id uuid primary key references public.profiles(id) on delete cascade,
  conversation_id uuid unique references public.conversations(id) on delete set null,
  status text not null check (status in ('active','claiming','claimed','expired')),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  claimed_by uuid references public.profiles(id) on delete set null,
  claimed_at timestamptz,
  updated_at timestamptz not null default now(),
  check (expires_at = created_at + interval '7 days')
);
```

The exact invariant may be implemented by a trigger when PostgreSQL rejects a
volatile/default expression in the check. The value remains server-owned and
immutable.

- [ ] Revoke direct mutation from `anon` and `authenticated`; allow only
  owner-scoped `SELECT` where the product needs it. Service-owned API paths
  perform mutations.
- [ ] Add gateway methods with these exact signatures:
  - `create_guest_workspace(*, user_id: str, created_at: datetime) -> GuestWorkspace`
  - `get_active_guest_workspace(*, user_id: str, at: datetime) -> GuestWorkspace | None`
  - `bind_guest_conversation(*, user_id: str, conversation_id: str) -> GuestWorkspace`

- [ ] Run the real-Postgres suite with the repository's existing disposable
  database gate. A skipped database proof is not completion evidence for this
  task.

### Task 5: Implement anonymous bootstrap without weakening permanent auth

**Files:**

- Modify: `src/argus/api/routers/auth.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `src/argus/api/dependencies.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `supabase/config.toml`
- Test: `tests/test_guest_auth.py`
- Test: `tests/test_alpha_api.py`
- Test: `tests/test_alpha_api_supabase.py`
- Test: `tests/test_private_alpha_release_profile.py`

- [ ] Write red tests proving:
  - the guest flag off returns 404/403 without creating an Auth user;
  - one valid guest cookie reuses the same anonymous user;
  - CAPTCHA and IP throttling run before Auth creation;
  - anonymous login never consults or mutates the allowlist;
  - private-alpha permanent signup/login still requires an active allowlist
    row when public account access is off;
  - public account mode permits an ordinary user but never grants
    admin/developer status;
  - an explicitly disabled row remains blocked in both modes.

- [ ] Add `GuestBootstrapRequest` with a bounded CAPTCHA token and optional
  resolved language.
- [ ] Add
  `SupabaseGateway.sign_in_anonymously(*, captcha_token: str, language: Language)`.
- [ ] Implement `POST /auth/guest`:
  1. origin/flag check;
  2. existing valid session reuse;
  3. IP limiter;
  4. provider CAPTCHA verification through the supported Supabase option;
  5. anonymous Auth creation;
  6. minimal profile creation;
  7. guest workspace creation;
  8. existing `auth_response()` secure cookies.
- [ ] Configure local/isolated QA to allow anonymous Auth while production
  remains off by default. Do not change hosted production settings in this
  task.
- [ ] Run the focused auth suite and confirm no secret, token, or CAPTCHA
  payload enters logs.

### Task 6: Extend canonical usage settlement to `guest_session`

**Files:**

- Modify: `src/argus/domain/usage_limits.py`
- Modify: `src/argus/api/chat/allowance.py`
- Modify: `src/argus/domain/backtest_admission_gateway.py`
- Modify: `src/argus/api/routers/feedback.py`
- Create: `supabase/migrations/20260724000002_add_guest_session_allowances.sql`
- Test: `tests/test_guest_allowance_accounting.py`
- Test: `tests/test_allowance_accounting_postgres.py`
- Test: `tests/test_chat_request_admission.py`

- [ ] Write red tests for exactly:
  - 10 useful terminal assistant responses = 10 guest message units;
  - failure, interruption, recoverable failure, and exact replay = 0 extra;
  - one unique admitted simulation = 1 unit;
  - exact admission replay = 0 extra;
  - a second unique simulation returns a typed pre-admission conversion
    requirement;
  - five feedback submissions succeed and the sixth is rejected;
  - registered hour/day counters remain unchanged.

- [ ] Add the constants `GUEST_MESSAGE_ALLOWANCE = 10`,
  `GUEST_SIMULATION_ALLOWANCE = 1`, and `GUEST_FEEDBACK_ALLOWANCE = 5`, plus the
  exact interface
  `allowance_windows(account: AccountContext, resource: str) -> list[dict[str, object]]`.

```python
GUEST_MESSAGE_ALLOWANCE = 10
GUEST_SIMULATION_ALLOWANCE = 1
GUEST_FEEDBACK_ALLOWANCE = 5
```

For a guest, return one `guest_session` window with the exact workspace
creation/expiry. For a registered user, return the existing hour/day windows.

- [ ] Extend the two existing atomic SQL owners rather than adding guest-only
  writers:
  - `append_conversation_message_settling_usage`
  - `admit_backtest_job`

Each accepts explicit start/end only for `guest_session`, validates them against
the active guest workspace, and preserves replay-before-charge behavior.

- [ ] Make feedback charge and insert one atomic operation. Do not leave
  `check_and_increment` followed by a separate feedback insert for guest mode.
- [ ] Run:

```bash
poetry run pytest \
  tests/test_guest_allowance_accounting.py \
  tests/test_allowance_accounting_postgres.py \
  tests/test_chat_request_admission.py -q --no-cov
```

### Task 7: Enforce one conversation and implement cleanup

**Files:**

- Modify: `src/argus/api/routers/conversations.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Create: `src/argus/domain/guest_cleanup.py`
- Create: `scripts/ops/cleanup_expired_guest_workspaces.py`
- Create: `supabase/migrations/20260724000003_guest_conversation_and_cleanup.sql`
- Test: `tests/test_guest_conversation_policy.py`
- Test: `tests/test_guest_cleanup_postgres.py`

- [ ] Red-test concurrent attempts to create two guest conversations; exactly
  one may exist.
- [ ] Red-test that replacing an empty conversation does not reset identity,
  expiry, or counters.
- [ ] Red-test cleanup ordering:
  - mark workspace expired;
  - deny further product reads/writes;
  - remove conversation-owned product rows;
  - delete the anonymous Auth user through a server-admin operation;
  - preserve converted permanent accounts and privacy-safe aggregate evidence.
- [ ] Make the cleanup command idempotent, bounded, dry-run capable, and safe
  under concurrent invocations:

```bash
poetry run python scripts/ops/cleanup_expired_guest_workspaces.py --dry-run --limit 25
poetry run python scripts/ops/cleanup_expired_guest_workspaces.py --limit 25
```

- [ ] Add structured counts only; never log transcript, email, token, or raw
  prompt data.

**Block 1 stop gate**

- [ ] Auth, RLS, usage, one-conversation, and cleanup real-Postgres proofs pass.
- [ ] Existing private-alpha auth and registered allowance suites pass.
- [ ] No runtime/interpreter file changed.
- [ ] Review the block for cross-owner, quota, and cleanup risk before
  continuing.

---

## Block 2 — Guest chat shell and onboarding

### Task 8: Bootstrap guest entry in the server-rendered route

**Files:**

- Modify: `web/app/page.tsx`
- Modify: `web/app/chat/page.tsx`
- Modify: `web/lib/supabase-server.ts`
- Modify: `web/lib/supabase-client.ts`
- Modify: `web/lib/argus-api.ts`
- Create: `web/lib/guest-session.ts`
- Test: `web/__tests__/guest-session.test.ts`
- Test: `web/e2e/guest-entry.spec.ts`

- [ ] Red-test:
  - guest flag off keeps the current auth-first landing;
  - guest flag on creates/reuses one anonymous session and opens `/chat`;
  - route reload keeps the same UUID and conversation;
  - a frontend-on/server-off mismatch shows a fail-closed retry state;
  - server-rendered guest responses are dynamic and never shared across
    visitors.
- [ ] Implement server bootstrap as one idempotent call to `/auth/guest`.
- [ ] Keep the current landing auth component reusable for the later modal;
  do not delete the auth-first rollback path.

### Task 9: Extract and reuse the verified starter actions

**Files:**

- Create: `web/components/chat/StarterActions.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`
- Test: `web/__tests__/guest-starter-actions.test.tsx`
- Test: `web/__tests__/alpha-frontend.test.ts`

- [ ] Move the current three labels, icons, localized values, and
  `handleSend(value)` behavior into one shared component.
- [ ] Prove the same component renders for guest and registered empty chats.
- [ ] Prove the chips disappear after the first accepted message.
- [ ] Prove `NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED=false` and the
  stale goal-selection onboarding remain off for guests.

### Task 10: Render the guest shell from server capabilities

**Files:**

- Create: `web/components/guest/GuestHeader.tsx`
- Create: `web/components/guest/GuestSettingsMenu.tsx`
- Create: `web/components/guest/GuestLegalFooter.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/components/sidebar/ChatSidebar.tsx`
- Modify: `web/components/sidebar/ProfileMenu.tsx`
- Modify: `web/components/SettingsMenu.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `web/__tests__/guest-shell.test.tsx`
- Test: `web/__tests__/spanish-ui-smoke.test.ts`

- [ ] Render from `capabilities`, not scattered environment checks.
- [ ] Guest top right: theme, language, feedback, and Sign in only.
- [ ] Hide bottom account settings and the conversation three-dot menu.
- [ ] Keep New chat, Recents, Omnisearch, and Add decision visible.
- [ ] Show:
  - empty-chat value statement;
  - pre-message Terms/Privacy footer;
  - post-message education/safety footer with permanent legal links;
  - quiet exact expiry status.
- [ ] Meet keyboard, focus, 44px target, 16px mobile input, light/dark, and
  EN/ES requirements.

### Task 11: Add artifact-anchored hints without creating a tour

**Files:**

- Create: `web/components/guest/GuestArtifactHint.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/components/chat/StrategyResultCard.tsx`
- Test: `web/__tests__/guest-artifact-hints.test.tsx`

- [ ] Show the confirmation hint only when a backend confirmation artifact
  exists.
- [ ] Show the result hint only when a result artifact exists.
- [ ] Persist dismissal in browser-local presentation state.
- [ ] Prove there are no timers, fake progress, forced steps, or runtime writes.

**Block 2 stop gate**

- [ ] Browser entry, shell, starter, localization, mobile, and reload tests pass.
- [ ] The current registered shell remains visually and behaviorally intact.
- [ ] No fake conversation or frontend-created runtime artifact exists.

---

## Block 3 — Conversion and visible capability gates

### Task 12: Build one centered, contextual auth modal

**Files:**

- Create: `web/components/auth/AuthModal.tsx`
- Create: `web/components/auth/auth-modal-state.ts`
- Refactor: `web/app/page.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `web/__tests__/guest-auth-modal.test.tsx`

- [ ] Reuse the landing page's validated fields, password visibility,
  error treatment, legal copy, and API functions.
- [ ] Support `signup-first` and `signin-first` entry modes plus a typed reason:

```ts
type GuestConversionReason =
  | "second_simulation"
  | "message_limit"
  | "save_decision"
  | "new_conversation"
  | "keep_history";
```

- [ ] Preserve composer input, active artifact, and typed pending action when
  opening/canceling the modal.
- [ ] Trap and restore focus. Escape closes only non-destructive state.

### Task 13: Link a new permanent identity in place

**Files:**

- Modify: `src/argus/api/routers/auth.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `web/lib/argus-api.ts`
- Modify: `web/components/auth/AuthModal.tsx`
- Test: `tests/test_guest_identity_linking.py`
- Test: `web/e2e/guest-conversion-new-account.spec.ts`

- [ ] Red-test that linking:
  - requires a valid, unexpired anonymous session;
  - uses the provider's supported identity-link/update operation;
  - preserves the Auth UUID;
  - fills the verified profile email;
  - changes `/me.account_kind` to registered;
  - leaves every product row under the same owner;
  - resumes the pending action at most once.
- [ ] Failure leaves the guest workspace and pending artifact unchanged.
- [ ] Do not use admin-created replacement users or frontend row copying.

### Task 14: Implement the existing-account single-use claim

**Files:**

- Create: `supabase/migrations/20260724000004_guest_workspace_handoffs.sql`
- Create: `src/argus/domain/guest_workspace_claim.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `src/argus/api/routers/auth.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `web/lib/argus-api.ts`
- Test: `tests/test_guest_workspace_claim_postgres.py`
- Test: `tests/test_guest_workspace_claim_api.py`
- Test: `web/e2e/guest-conversion-existing-account.spec.ts`

- [ ] Create a short-lived handoff with only a hash at rest. Bind it to:
  source owner, one workspace, one source conversation, optional typed pending
  action, expiry, and single-use status.
- [ ] Store the opaque handoff secret in a secure, SameSite, HttpOnly cookie.
  Never place it in a query string, local storage, analytics, or logs.
- [ ] Before writing the claim function, derive the complete transfer set from
  actual foreign keys at this head. It must include all conversation/product
  rows landed by Always Progresses and exclude immutable cost/security evidence
  from owner rewriting.
- [ ] Red-test:
  - wrong destination, expired, replayed, or tampered handoff;
  - two concurrent claims;
  - foreign row injected into the source graph;
  - failure halfway through every table group;
  - complete success with no duplicate conversation, job, run, idea, evidence,
    lifecycle, or checkpoint thread;
  - guest counters not merged into registered counters;
  - source deletion only after product graph safety.
- [ ] Implement one PostgreSQL transaction with row locks. On any mismatch,
  update zero product owners and consume nothing.
- [ ] Keep `thread_id == conversation_id`; move only explicit owner metadata in
  checkpoint payloads if the integrated Always Progresses schema requires it.
  Do not rewrite conversational state or prose.

### Task 15: Gate New chat, Add decision, limits, and second Run

**Files:**

- Create: `web/lib/guest-capability-gates.ts`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/components/chat/StrategyResultCard.tsx`
- Modify: `web/components/sidebar/ChatSidebar.tsx`
- Modify: `src/argus/api/routers/conversations.py`
- Modify: `src/argus/api/chat/allowance.py`
- Modify: `src/argus/api/chat/backtest_admission_flow.py`
- Test: `web/__tests__/guest-capability-gates.test.tsx`
- Test: `tests/test_guest_server_gates.py`

- [ ] Frontend behavior:
  - empty New chat resets;
  - non-empty New chat offers Start over or Create account;
  - Add decision opens conversion and retains artifact ID;
  - the 11th attempted completed turn opens conversion before sending;
  - the second unique Run opens conversion before admission;
  - cancel loses nothing.
- [ ] Server behavior independently rejects bypass attempts before provider,
  persistence, usage, or execution work.
- [ ] Typed action resumption uses IDs and idempotency keys, never display prose.
- [ ] Do not change runtime semantics in
  `src/argus/api/chat/backtest_admission_flow.py`; pass the account-specific
  allowance into the existing admission owner only.

### Task 16: Make Recents and feedback honestly guest-safe

**Files:**

- Modify: `src/argus/api/routers/history.py`
- Modify: `src/argus/api/routers/feedback.py`
- Modify: `web/components/sidebar/ChatSidebar.tsx`
- Modify: `web/components/feedback/FeedbackDialog.tsx`
- Test: `tests/test_guest_history_feedback.py`
- Test: `web/__tests__/guest-history-feedback.test.tsx`

- [ ] Guest history returns at most the one owned conversation and truthful
  expiry.
- [ ] Guest feedback supports general, bug, feature, and optional scalar
  rating; it never requires email.
- [ ] Explicit transcript-context consent remains required.
- [ ] The current sanitizer continues excluding URL query, auth material,
  headers, raw transcript, and nested arbitrary browser data.

### Task 17: Reconcile Omnisearch without inventing discovery

**Files:**

- Modify: `src/argus/api/routers/search.py`
- Modify: `src/argus/api/search_assembly.py`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Test: `tests/test_guest_omnisearch.py`
- Test: `web/__tests__/guest-omnisearch.test.tsx`

- [ ] Owner-scoped temporary conversation/artifact search may ship in this
  block.
- [ ] Provider-backed grounded discovery may be exposed only if its pillar has
  landed and its server capability is true.
- [ ] Otherwise show a scoped Search-unavailable state for discovery while
  keeping current-workspace search functional.
- [ ] Prove zero cross-owner records, hidden Strategies/Collections
  destinations, or provider/model/receipt metadata.

**Block 3 stop gate**

- [ ] New-account and existing-account conversions pass on real Postgres/Auth.
- [ ] Pending actions resume exactly once.
- [ ] No partial transfer, duplicate charge, duplicate artifact, or lost guest
  workspace is possible.
- [ ] Omnisearch exposure matches the integrated Grounded Discovery state.

---

## Block 4 — Evidence and public-readiness gate

### Task 18: Add privacy-safe guest funnel events

**Files:**

- Modify the existing server/client analytics envelope owners found in Phase 0
- Test: `tests/test_guest_observability.py`
- Test: `web/__tests__/guest-analytics.test.ts`

- [ ] Add only the approved funnel concepts from the design.
- [ ] Pin a sanitizer test proving no prompt, assistant prose, exact capital,
  exact dates, email, display name, cookie, token, IP, title, preview, or model
  name enters frontend analytics.
- [ ] Keep provider cost and latency in the existing server-owned evidence
  ledger, correlated by privacy-safe IDs.

### Task 19: Run the deterministic and security matrices

**Files:**

- Test: all files added above
- Modify: `tests/test_spine_guardrails.py` only if a new non-runtime ownership
  boundary needs a static pin
- Modify: `scripts/check_modularity_budget.py` only when a justified new module
  must be registered

- [ ] Run focused tests after every task.
- [ ] Run the hermetic backend gate with keys blanked:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov
```

- [ ] Run full backend, frontend, lint, build, modularity, and whitespace gates:

```bash
poetry run pytest tests/ -q
poetry run ruff check src tests
poetry run python scripts/check_modularity_budget.py
(cd web && bun test)
(cd web && bun run lint)
(cd web && bun run build)
git diff --check
```

- [ ] Run the real-Postgres matrix for RLS, settlement, transfer, and cleanup.
  Do not count a skip as proof.
- [ ] Run an independent security/privacy review focused on anonymous Auth,
  handoff secrecy, RLS, service-role functions, abuse, cleanup, and analytics.

### Task 20: Perform founder-visible production-parity browser QA

**Files:**

- Create: `web/e2e/guest-experience.spec.ts`
- Update: `scripts/qa/README.md`
- Evidence: `temp/qa-evidence-guest/` (gitignored)

- [ ] Use a real anonymous Supabase identity, real persistence, real
  interpreter, live provider-backed discovery, and the exact candidate SHA.
- [ ] Execute the 20 visible acceptance checks in the design once, with no
  hidden retries.
- [ ] The QA agent must inspect the rendered chat, not only DOM/API state.
- [ ] Capture sanitized evidence:
  - screenshots;
  - `/me` and usage shapes without auth material;
  - owner/count/expiry database facts;
  - zero cross-owner results;
  - network ledger for local-only chart interactions;
  - console status.
- [ ] Stop at the first product failure and report it. Do not begin an
  unbounded repair/review/eval loop.
- [ ] No paid live-eval scorecard is required unless runtime/interpreter code
  changed, which would mean this lane exceeded scope.

### Task 21: Reconcile integration dependencies and release docs

**Files:**

- Modify: `docs/specs/private-alpha-next-roadmap.md`
- Modify: `docs/specs/private-alpha-next-integration.md`
- Modify: `docs/specs/private-alpha-ci-cd-sota.md`
- Modify: `docs/PRIVATE_LAUNCH_RUNBOOK.md`
- Modify: `docs/release-manifests/TEMPLATE.md`
- Modify: `render.yaml` only after founder authorizes a branch-deployed canary

- [ ] Rebase/merge the latest founder-approved integration checkpoint.
- [ ] Re-run the exact-head deterministic and browser gates.
- [ ] Confirm Always Progresses and guest-safe Grounded Discovery/Omnisearch
  dependencies are truly integrated.
- [ ] Keep all public flags off.
- [ ] Document:
  - actual implementation status;
  - migration order;
  - cleanup schedule;
  - abuse controls;
  - canary identity;
  - rollback;
  - remaining founder decisions.
- [ ] Stop before push, PR state change, deployment, public enablement, merge,
  or issue closure unless the founder authorizes that exact operation.

## Commit Sequence

Use small conventional commits; recommended boundaries:

1. `docs(guest): activate public guest contracts`
2. `feat(auth): add typed guest account context`
3. `feat(data): add owner-scoped guest workspaces`
4. `feat(auth): bootstrap anonymous guest sessions`
5. `feat(usage): settle guest lifetime allowances`
6. `feat(guest): enforce temporary conversation lifecycle`
7. `feat(web): add guest entry and shared starters`
8. `feat(web): add guest shell and legal guidance`
9. `feat(auth): link guest identities in place`
10. `feat(auth): claim guest workspace atomically`
11. `feat(guest): gate durable actions contextually`
12. `feat(search): scope guest omnisearch`
13. `test(guest): prove production-parity guest journey`
14. `docs(guest): record readiness and rollback`

Do not squash away the four block boundaries before independent review.

## Final Completion Definition

The implementation candidate is complete only when:

- all four block stop gates pass;
- real PostgreSQL proves ownership, transfer, allowance, and cleanup;
- a real anonymous user completes the founder-visible journey;
- one result, reload, Recents, conversion, and action resumption work;
- registered behavior remains unchanged;
- no runtime/interpreter file changed;
- public flags remain off;
- an independent security/privacy review and product/code review find no
  blocker;
- the current Codex release captain and founder approve promotion.

An implemented branch without these gates is useful leverage, not a
public-ready guest experience.
