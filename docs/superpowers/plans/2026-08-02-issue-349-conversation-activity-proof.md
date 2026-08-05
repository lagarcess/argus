# Issue 349 Conversation Activity Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close issue #349 with current-head proof that registered and Guest conversation activity follows the locked contract and that manual unread persists through real Postgres/RLS and reload.

**Architecture:** Keep PR #329's API, database, and frontend ownership unchanged unless a reachable product defect is reproduced. Repair only the date-sensitive Playwright fixture that blocks the required Spanish acceptance replay, then capture disposable local Postgres/RLS and real-auth browser evidence in a bounded verification report.

**Tech Stack:** Next.js 16, React 19, TypeScript, Playwright, FastAPI, Python 3.10.20, Supabase CLI/Postgres 17, pytest, Bun.

## Global Constraints

- Integration base is `6533377c1a08539136a622a7d53eee20d0efd845` from `origin/codex/private-alpha-next`.
- `docs/superpowers/specs/2026-08-01-conversation-activity-attention-unread-lifecycle.md` is the design authority.
- Guests receive `working`, `needs_input`, `needs_attention`, automatic read, and new-activity behavior; Guest manual unread and owner menus remain absent.
- Do not change conversation ordering, pagination, LangGraph/SSE ownership, API shapes, or the migration contract.
- Do not apply a hosted migration, deploy, expose testers, or merge the PR.
- Stop if proof requires a provider turn, hosted write, new Guest management capability, or product decision.

---

### Task 1: Make the browser acceptance clock current-day stable

**Files:**
- Modify: `web/e2e/conversation-activity-ui.spec.ts`
- Test: `web/e2e/conversation-activity-ui.spec.ts`

**Interfaces:**
- Consumes: the existing Recents day-grouping behavior and localized `Today` / `Hoy` disclosure labels.
- Produces: a fixture timestamp that is always in the browser run's current day while preserving source ordering.

- [ ] **Step 1: Preserve the failing evidence**

Run:

```bash
cd web
CONVERSATION_ACTIVITY_EVIDENCE_DIR=../temp/qa-evidence-349/6533377c/fixture \
  PLAYWRIGHT_PORT=3149 \
  bun run test:e2e e2e/conversation-activity-ui.spec.ts
```

Expected before the fix: the Spanish journey times out waiting for `Mostrar más en Hoy` because the fixed `2026-08-01` fixture falls into Yesterday on `2026-08-02`.

- [ ] **Step 2: Use the current test-run timestamp**

Replace the fixed constant with:

```ts
const NOW = new Date().toISOString();
```

Do not change production grouping or localized labels.

- [ ] **Step 3: Run the previously failing Spanish journey**

Run:

```bash
cd web
PLAYWRIGHT_PORT=3149 \
  bun run test:e2e e2e/conversation-activity-ui.spec.ts \
  --grep "Spanish desktop"
```

Expected: `1 passed`.

- [ ] **Step 4: Run the full conversation-activity browser matrix**

Run the Task 1 Step 1 command again.

Expected: `11 passed` with English, Spanish, desktop, mobile, keyboard, reduced-motion, activity-state, and read/unread menu journeys.

### Task 2: Prove disposable Postgres/RLS persistence and Guest boundaries

**Files:**
- Test: `tests/test_conversation_activity_postgres.py`
- Test: `tests/test_conversation_activity.py`
- Test: `tests/test_guest_conversation_policy.py`

**Interfaces:**
- Consumes: migration `20260801000000_add_conversation_activity_read_states.sql`.
- Produces: proof for migration parity, service-only mutation, owner RLS, cursor races, Guest automatic read, and registered-only manual unread.

- [ ] **Step 1: Rebuild the loopback QA database from zero**

Run:

```bash
supabase db reset --local
supabase migration list --local
```

Expected: local and applied history both contain `20260801000000`.

- [ ] **Step 2: Run the disposable Postgres proof**

Run:

```bash
eval "$(supabase status -o env)"
ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" \
  poetry run pytest tests/test_conversation_activity_postgres.py -q --no-cov
```

Expected: `8 passed`.

- [ ] **Step 3: Run projection and Guest-policy tests**

Run:

```bash
poetry run pytest tests/test_conversation_activity.py \
  tests/test_conversation_activity_migration.py \
  tests/test_guest_conversation_policy.py -q --no-cov
```

Expected: `56 passed`.

### Task 3: Capture the real-auth UI-to-database journey

**Files:**
- Create: `docs/reports/2026-08-02-issue-349-conversation-activity-verification.md`
- Create: `docs/reports/assets/issue-349-conversation-activity/*`

**Interfaces:**
- Consumes: local Supabase Auth, FastAPI activity endpoints, the Next.js owner menus, and `conversation_read_states`.
- Produces: sanitized before/after/reload screenshots plus a verification tuple and state classification.

- [ ] **Step 1: Generate worktree-local non-production environment files**

Run:

```bash
bash scripts/qa/write-local-env.sh
bash scripts/qa/assert-nonprod-target.sh
```

Expected: both files are regular worktree-local files targeting loopback and mock Auth is false.

- [ ] **Step 2: Launch exact-head backend and frontend on lane-owned ports**

Use the repository QA scripts or explicit process-local overrides. Do not persist provider keys or make a provider turn.

- [ ] **Step 3: Verify registered persistence**

With a disposable registered identity, create/open a conversation, select **Mark as unread**, verify the durable row through the owner-scoped API/database, reload, verify **Marked unread**, then select **Mark as read** and verify the flag clears without reordering.

- [ ] **Step 4: Verify Guest applicability**

With a disposable Guest identity, prove automatic typed activity/read projection is visible and durable, the owner menus/manual unread action are absent, `mark_read` succeeds, and a direct `mark_unread` request returns `403 account_conversion_required`.

- [ ] **Step 5: Write and self-review the evidence report**

Record exact SHA, personas, flags, migration history, commands, browser actions, durable rows, request statuses, screenshot hashes, zero provider turns, zero hosted mutations, and the state-by-state Guest applicability table. Keep observed, proven, expected, inferred, and unknown claims separate.

### Task 4: Verify, review, and publish

**Files:**
- Modify only files named by Tasks 1 and 3.

**Interfaces:**
- Consumes: the final diff and exact candidate SHA.
- Produces: a reviewed PR targeting `codex/private-alpha-next` that closes #349 without merge authority.

- [ ] **Step 1: Run focused and repository checks**

```bash
cd web && bun test __tests__/guest-shell.test.tsx \
  __tests__/chat-header-menu.test.tsx \
  __tests__/recent-chat-actions.test.tsx \
  __tests__/conversation-activity-state.test.ts \
  __tests__/use-conversation-activity.test.tsx
cd ..
poetry run pytest tests/test_conversation_activity.py \
  tests/test_conversation_activity_migration.py \
  tests/test_conversation_activity_postgres.py \
  tests/test_guest_conversation_policy.py -q --no-cov
git diff --check
```

- [ ] **Step 2: Review the exact diff against issue #349 and the locked spec**

Reject any change that broadens product behavior instead of repairing evidence determinism.

- [ ] **Step 3: Reconcile current integration if it advanced**

Fetch `origin/codex/private-alpha-next`, compare semantic overlap, merge it one-way only if necessary, and rerun invalidated evidence.

- [ ] **Step 4: Commit, push, and open the PR**

Use conventional commits, target `codex/private-alpha-next`, reference and close #349, request mandatory review, and report exact-head CI without merging.
