# Omnisearch Memory Recall Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Omnisearch the deterministic memory inspector defined in
`docs/superpowers/specs/2026-07-29-omnisearch-memory-recall.md`: one row per
conversation, full-transcript recall, bounded dossiers, asset rollups,
open-at-match, and two actionable panel verbs.

**Architecture:** Replace artifact-shaped result streams with a
conversation-shaped read model assembled from existing Conversation, Message,
BacktestRun, Idea, IdeaVersion, EvidenceArtifact, and DecisionNote truth.
Postgres selects and ranks one winning match per conversation before cursoring;
memory mode feeds the same projector. The frontend renders typed dossier and
action contracts and never reconstructs canonical facts.

**Tech Stack:** Python 3.10, FastAPI/Pydantic, PostgreSQL 17/Psycopg/Supabase,
Next.js/React/TypeScript, Bun/Vitest, Playwright.

## Global Constraints

- Base is `codex/private-alpha-next`; the branch is
  `claude/omnisearch-memory-recall`; the locked spec at `3d99792e` is the first
  commit.
- This is one PR. Tasks 1-4 land as exactly one conventional commit each,
  matching the four slices in spec Section 5. Do not create separate PRs.
- Read `AGENTS.md`, the five mandatory canon docs in order, and decision memo
  sections 2-5 before changing code.
- Reuse `src/argus/domain/evidence.py::decision_recall_preview` and the PR #305
  assembly paths. Do not duplicate decision/evidence sanitation.
- Group one row per conversation before ranking, cursoring, and pagination.
  Never collapse artifact rows in the browser or after a page boundary.
- Full-transcript search returns only a bounded matched fragment and provenance;
  it never returns raw transcript rows.
- Object matches rank above transcript matches. Exact and prefix behavior stays
  the default; no fuzzy/semantic search.
- Zero LLM or provider calls for search, hover, focus, preview, dossier
  assembly, asset recognition, or either verb's composition.
- No hover-time generation, new durable digest/summary model, RAG, embeddings,
  pgvector, public view/RPC, unbounded per-keystroke query, or auto-execution.
- Archived conversations remain eligible; soft-deleted conversations are
  excluded. Every Postgres query remains owner/workspace scoped.
- Static copy ships in English and `es-419`; mobile controls have 44px hit
  areas and inputs remain at least 16px.
- Every typed addition updates `docs/API_CONTRACT.md`,
  `docs/api/openapi.yaml`, backend Pydantic schemas, and frontend TypeScript
  types in the same task.
- Use TDD: name the production break, write the regression, observe the expected
  failure, implement the minimum, and observe green before refactoring.
- Never write through `.env` or `web/.env.local`; both are symlinks to the
  integration worktree. Never use `git stash`.
- Before each slice commit run its focused backend and frontend tests, Ruff on
  changed Python, `scripts/check_modularity_budget.py`, and `git diff --check`.
- Before publication run the founder-specified hermetic full backend suite with
  `.env` moved aside and restored, all `web/` Bun tests, Ruff, modularity,
  OpenAPI compatibility, and browser QA.

---

### Task 1: Conversation Rows and Dossier Projection

**Files:**
- Create: `src/argus/domain/conversation_recall.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/domain/evidence.py`
- Modify: `src/argus/api/search_assembly.py`
- Modify: `src/argus/domain/postgres_search_reader.py`
- Modify: `src/argus/api/routers/search.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/api/openapi.yaml`
- Modify: `web/lib/argus-api.ts`
- Modify: `web/lib/command-palette-items.ts`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `tests/test_alpha_api.py`
- Test: `tests/test_alpha_api_supabase.py`
- Test: `tests/test_search_bounded_reads.py`
- Test: `tests/test_search_postgres.py`
- Test: `web/__tests__/command-palette-items.test.ts`

**Interfaces:**
- Produce a typed `conversation` search row whose `id` and `conversation_id`
  are the canonical conversation id.
- Produce `dossier.decision`, `dossier.tested`, `dossier.outcome`, and
  `dossier.left_off` from stored truth, with bounded symbol/family/metric lists.
- `dossier.decision` reuses `decision_recall_preview`, preserves the note
  verbatim, and names the judged run when more than one run exists.
- `dossier.left_off` names the latest completed run/date and carries only typed
  stored-truth nudge codes: `undecided`, `suggestion_untaken`, or
  `stale_result`.
- Empty-query ordinary search returns recents-first conversation rows.
- Decision-state chips return conversations holding that state; ledger counts
  remain backend-owned and exact.

- [ ] **Step 1: Write focused failing backend contract, one-row, dossier,
  parity, owner, archive/delete, and cursor regressions.**
- [ ] **Step 2: Run the focused backend tests and record failures caused by
  artifact rows and the missing typed dossier.**
- [ ] **Step 3: Add typed schemas/docs and the shared deterministic projector,
  then make Postgres group/hydrate by conversation before cursoring.**
- [ ] **Step 4: Write failing frontend projection/rendering tests for the
  dossier order and verbatim note.**
- [ ] **Step 5: Render the typed conversation row and dossier in EN/ES, then
  run focused backend/frontend tests green.**
- [ ] **Step 6: Regenerate OpenAPI, run the slice quality gates, and commit
  `feat(omnisearch): project one memory dossier per conversation`.**

### Task 2: Transcript Haystack and Jump to Match

**Files:**
- Create: `supabase/migrations/20260729000001_add_message_recall_index.sql`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/domain/postgres_search_reader.py`
- Modify: `src/argus/api/search_assembly.py`
- Modify: `src/argus/api/routers/conversations.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/api/openapi.yaml`
- Modify: `web/lib/argus-api.ts`
- Modify: `web/lib/chat-conversation-routing.ts`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Test: `tests/test_bounded_read_indexes.py`
- Test: `tests/test_bounded_read_indexes_postgres.py`
- Test: `tests/test_search_bounded_reads.py`
- Test: `tests/test_search_postgres.py`
- Test: `tests/test_alpha_api.py`
- Test: `web/__tests__/chat-conversation-routing.test.ts`
- Test: `web/__tests__/alpha-frontend.test.ts`

**Interfaces:**
- Add typed `match: { layer, fragment, count, message_id }`; `message_id` is
  present only for a transcript winner.
- Search user-authored Message content as a bounded candidate source and use a
  query-plan-proven message content index.
- Object layers (`decision`, `evidence`, `idea`, `run`) outrank `message`.
- Opening a row uses the existing conversation read API with an additive
  owner-scoped anchor parameter so the matched message is loaded and scrolled
  into view; Enter opens at match.

- [ ] **Step 1: Write failing migration, bounded-query, ranking, provenance,
  archive/delete, guest, and open-at-message regressions.**
- [ ] **Step 2: Observe the failures against title/last-preview-only search.**
- [ ] **Step 3: Add the migration and bounded Message candidate path, retaining
  exact rechecks and owner/workspace predicates.**
- [ ] **Step 4: Add the typed anchor read/open path and frontend focus/scroll
  behavior.**
- [ ] **Step 5: Regenerate OpenAPI, run focused tests and slice gates, and
  commit `feat(omnisearch): recall transcript matches in place`.**

### Task 3: Asset Rollup Row

**Files:**
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/domain/conversation_recall.py`
- Modify: `src/argus/domain/postgres_search_reader.py`
- Modify: `src/argus/api/routers/search.py`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/api/openapi.yaml`
- Modify: `web/lib/argus-api.ts`
- Modify: `web/lib/command-palette-items.ts`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `tests/test_alpha_api.py`
- Test: `tests/test_search_postgres.py`
- Test: `web/__tests__/command-palette-items.test.ts`

**Interfaces:**
- Add a typed `asset_rollup` row placed above conversation rows when the exact
  or prefix query matches a canonical symbol already present in owned runs.
- Include `symbol`, `run_count`, `decision_counts`, and `last_touched_at`.
  A multi-asset run counts once under every involved symbol and the UI says
  “involving”.
- Asset recognition reads only owned canonical run facts and never calls an
  asset resolver/provider.
- Asset rollups are additive presentation rows and do not consume or corrupt
  the conversation cursor.

- [ ] **Step 1: Write failing memory/Postgres parity tests for exact/prefix,
  multi-asset counts, decision counts, no-provider behavior, and row order.**
- [ ] **Step 2: Observe the missing rollup failures.**
- [ ] **Step 3: Add bounded backend aggregation and typed projection.**
- [ ] **Step 4: Add EN/ES rollup rendering and frontend tests.**
- [ ] **Step 5: Regenerate OpenAPI, run focused tests and slice gates, and
  commit `feat(omnisearch): summarize owned history by asset`.**

### Task 4: Panel Verbs and Palette Canon

**Files:**
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/domain/conversation_recall.py`
- Modify: `src/argus/api/search_assembly.py`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/api/openapi.yaml`
- Modify: `web/lib/argus-api.ts`
- Modify: `web/lib/command-palette-items.ts`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: `tests/test_alpha_api.py`
- Test: `tests/test_alpha_api_supabase.py`
- Test: `web/__tests__/command-palette-items.test.ts`
- Test: `web/__tests__/alpha-frontend.test.ts`

**Interfaces:**
- `run_fresh` action carries the anchored run's canonical setup and a
  deterministic current-window send string. It opens the source conversation
  and submits through the shipped prebaked-send path, yielding confirmation
  only and never auto-running.
- `decision` action carries the owner-checked evidence artifact target, current
  state/note, and anchored run label; it calls the existing decision endpoint.
- Saving a decision refreshes row, chips, counts, and panel without stale state.
- Add/Add decision wording follows whether the anchored left-off run is
  undecided.
- Cmd+Enter opens at left-off; digits 1-9 choose visible rows; hover and keyboard
  focus select the dossier; no-results copy is honest; empty query remains
  recents-first; the 200ms debounce remains and is regression-pinned.

- [ ] **Step 1: Write failing deterministic-action, no-generation,
  refresh-state, keyboard, empty/no-result, debounce, EN/ES, and mobile
  regressions.**
- [ ] **Step 2: Observe failures for missing action and keyboard contracts.**
- [ ] **Step 3: Add typed action projection and reuse the existing decision and
  prebaked-send contracts without adding a runtime or API owner.**
- [ ] **Step 4: Implement keyboard, focus, empty/no-result, and responsive
  polish.**
- [ ] **Step 5: Regenerate OpenAPI, run focused tests and slice gates, and
  commit `feat(omnisearch): make recalled dossiers actionable`.**

## Exact-Head Acceptance and Publication

- [ ] Move only the `.env` symlink to a unique `/tmp` path, run
  `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture
  .venv/bin/python -m pytest tests/ -q`, and restore the exact symlink in a
  shell trap.
- [ ] Run `cd web && bun test`.
- [ ] Run `.venv/bin/python -m ruff check src tests scripts`.
- [ ] Run `.venv/bin/python scripts/check_modularity_budget.py`.
- [ ] Run `.venv/bin/python -m pytest tests/test_openapi_compatibility.py -q`.
- [ ] Run `git diff --check` and verify exactly four implementation commits
  follow the founder spec commit.
- [ ] Launch a spare-port backend with mock auth, memory persistence, memory
  checkpointer, synthetic fixtures, and all provider keys blank; launch web on
  a spare port by process-local environment overrides only.
- [ ] Use Playwright CLI to prove EN and ES desktop/mobile: recents, transcript
  match, jump, dossier, rollup, decision mutation, and Run it fresh confirmation.
  Save screenshots under `output/playwright/omnisearch-memory-recall/`.
- [ ] Run a whole-branch Argus contract/code review against
  `origin/codex/private-alpha-next`, fix all confirmed Important/Critical
  findings in one bounded correction round, and re-run affected gates.
- [ ] Push the branch, open one PR to `codex/private-alpha-next`, apply
  `enhancement`, `web`, `api`, and `db`, post screenshot evidence, fix the
  review round with reasoned replies/reactions, and wait for final-tip CI.
- [ ] Stop at the posted PR. Do not merge, deploy, close the issue, or mutate
  hosted Supabase.
