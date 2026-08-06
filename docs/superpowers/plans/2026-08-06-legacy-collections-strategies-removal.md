# Legacy Collections and Strategies Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the retired Collections and Strategies product surfaces and environment switches without breaking reads of historical records.

**Architecture:** Delete the dedicated frontend and REST write/list surfaces, stop producing or rendering legacy Save actions, and make the existing chat compatibility response unconditional instead of flag-driven. Preserve database models, tables, migrations, historical identifiers, and current readers that tolerate old rows.

**Tech Stack:** Next.js/React/TypeScript, Bun/Vitest, FastAPI/Pydantic, pytest, Ruff, Supabase/Postgres contracts, Render Blueprint, Playwright CLI.

## Global Constraints

- Base from `origin/codex/private-alpha-next` SHA `9664e221fa50187d6b078ccdfcffd90cbc76d852`.
- Do not use `git stash`.
- Do not change `ARGUS_ASSET_PROVIDER_MODE` or its fallback behavior.
- Restrict `web/components/chat/ChatInterface.tsx` changes to the retired Strategies view and legacy Save action.
- Preserve legacy tables, migrations, read models, historical `strategy_id` identities, and the owned direct-run read path.
- No merge, deploy, hosted environment mutation, or database migration.
- Commit browser screenshots under `docs/reports/evidence/legacy-surface-removal/`.

---

### Task 1: Lock removal behavior with failing tests

**Files:**
- Create: `tests/test_legacy_surface_removal.py`
- Modify: `web/__tests__/alpha-frontend.test.ts`
- Modify: `tests/section3/test_engine_simulation.py`
- Modify: `tests/test_chat_backtest_state_machine.py`

**Interfaces:**
- Consumes: FastAPI `app`, current result-card builder, filesystem source tree.
- Produces: executable proof that dedicated routes and frontend files disappear,
  new cards contain only `show_breakdown` and `refine_strategy`, and old rows
  still validate/project through History.

- [ ] **Step 1: Add the backend removal contract**

  Add tests that call `GET/POST /api/v1/strategies` and
  `GET/POST /api/v1/collections` and expect `404`, then seed owned legacy
  `Strategy` / `Collection` objects in the memory store and assert `GET
  /api/v1/history` returns valid compatibility items without mutation.

- [ ] **Step 2: Update the frontend structural contract**

  Replace assertions that require disabled flags with assertions that
  `CollectionsView.tsx`, `StrategiesView.tsx`, and `CollectionPicker.tsx` do not
  exist; `ChatInterface.tsx` and `ChatSidebar.tsx` contain no Strategies mount;
  and active env contract files contain none of the three retired variable
  names.

- [ ] **Step 3: Change result-action expectations before production code**

  In engine and chat integration tests, expect exactly
  `show_breakdown, refine_strategy`. Retain a stale `save_strategy` action test
  that proves the backend returns the history-preserved explanation and creates
  no legacy Strategy.

- [ ] **Step 4: Run the focused tests and verify RED**

  Run:

  ```bash
  bun test __tests__/alpha-frontend.test.ts
  poetry run pytest tests/test_legacy_surface_removal.py tests/section3/test_engine_simulation.py tests/test_chat_backtest_state_machine.py -q
  ```

  Expected: failures identify existing files/routes/flags and the still-emitted
  `save_strategy` result action.

### Task 2: Remove the frontend surfaces

**Files:**
- Delete: `web/components/views/CollectionsView.tsx`
- Delete: `web/components/views/StrategiesView.tsx`
- Delete: `web/components/chat/CollectionPicker.tsx`
- Delete if confirmed self-only: `web/components/settings/DeletedItemsView.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/components/sidebar/ChatSidebar.tsx`
- Modify: `web/components/views/SettingsView.tsx`
- Modify: `web/components/chat/StrategyResultCard.tsx`
- Modify: `web/lib/argus-api.ts`
- Modify: `web/lib/private-alpha-flags.ts`
- Modify: `web/lib/chat-result-actions.ts`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`

**Interfaces:**
- Consumes: current Chat, Recents, Omnisearch, Settings, result-card contracts.
- Produces: a chat/settings shell with no Strategies/Collections navigation,
  mounts, API client, Save control, or dead locale namespace.

- [ ] **Step 1: Delete the orphaned components**

  Remove the three locked legacy components. Delete `DeletedItemsView.tsx` only
  if repository-wide reference search confirms the file refers only to itself;
  the live recently-deleted UI remains inside `SettingsView.tsx`.

- [ ] **Step 2: Remove navigation and mount ownership**

  Narrow `View` to `"chat" | "settings"`, delete the Strategies sidebar prop
  and button, and remove only Strategies/Save-action branches from
  `ChatInterface.tsx`.

- [ ] **Step 3: Retire frontend writes and visible Save behavior**

  Remove Strategy/Collection API clients and view-only types. Make visible
  result actions exactly `show_breakdown` and `refine_strategy`; old persisted
  `save_strategy` entries are filtered rather than rendered. Remove saving-state
  UI and helpers while retaining historical metadata types used to hydrate old
  messages.

- [ ] **Step 4: Keep Settings visually identical**

  Make Recently Deleted accept chats only and remove the unreachable Strategy
  restore/import/icon code. Do not alter layout, copy, or account behavior.

- [ ] **Step 5: Remove dead locale keys and run GREEN**

  Remove only keys owned by the deleted surfaces / Save action, keep EN and
  es-419 key parity, then run:

  ```bash
  bun test __tests__/alpha-frontend.test.ts __tests__/result-card-playground.test.ts
  bun run lint
  ```

  Expected: exit `0`.

### Task 3: Remove dedicated backend write/list surfaces

**Files:**
- Delete: `src/argus/api/routers/strategies.py`
- Delete: `src/argus/api/routers/collections.py`
- Delete: `src/argus/api/chat/strategies.py`
- Modify: `src/argus/api/main.py`
- Modify: `src/argus/api/routers/__init__.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/api/routers/agent.py`
- Modify: `src/argus/agent_runtime/stages/interpret.py`
- Modify: `src/argus/agent_runtime/stages/interpret_internal/offline_recovery.py`
- Modify: `src/argus/agent_runtime/stages/next_step.py`
- Modify: `src/argus/domain/backtesting/cards.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `src/argus/api/artifact_naming.py`
- Modify: `src/argus/api/chat/title_finalization.py`
- Modify: `src/argus/api/naming.py`
- Delete: `tests/test_openrouter_naming_routes.py`
- Modify: `tests/test_artifact_naming.py`
- Modify: endpoint/save-action tests discovered by focused search.

**Interfaces:**
- Consumes: base `Strategy` / `Collection` read models, existing History/Search
  readers, owned direct backtest `strategy_id` resolution.
- Produces: no registered CRUD routers or legacy Strategy creation path; stale
  Save requests degrade to a non-mutating history-preserved response.

- [ ] **Step 1: Unregister and delete dedicated routers**

  Remove their imports/router registration and delete route-only Pydantic
  request/response/pagination models. Retain base `Strategy` and `Collection`
  models and update the retired-template validator comment to describe
  compatibility reads.

- [ ] **Step 2: Delete current Strategy/Collection mutations**

  Remove Supabase create/patch/delete/attach methods after confirming no current
  caller remains. Retain read methods needed by direct-run compatibility and old
  row deserialization.

- [ ] **Step 3: Stop producing new Save actions**

  Remove `save_strategy` from new result cards and runtime next actions. Delete
  saved-Strategy creation/naming code. Keep the stale-action type and chat
  compatibility response, but remove the environment predicate so it can never
  enter a creation branch.

- [ ] **Step 4: Remove retired route and mutation tests**

  Delete only tests whose production subject no longer exists. Preserve tests
  for historical strategy ownership, `BacktestRun.strategy_id`, History/Search
  tolerance, guest handoff, and run reproducibility.

- [ ] **Step 5: Run backend GREEN**

  Run:

  ```bash
  poetry run pytest tests/test_legacy_surface_removal.py tests/section3/test_engine_simulation.py tests/test_chat_backtest_state_machine.py tests/agent_runtime/test_interpret_stage.py tests/agent_runtime/test_workflow.py tests/test_artifact_naming.py -q
  poetry run ruff check src tests
  ```

  Expected: exit `0`.

### Task 4: Remove environment plumbing and update contracts

**Files:**
- Modify: `.env.example`
- Modify: `web/.env.local.example`
- Modify: `render.yaml`
- Modify: `.github/private-alpha-release-profile.json`
- Modify: `.github/argus-env.sh`
- Modify: `.github/local-smoke.sh`
- Modify: `scripts/qa/write-local-env.sh`
- Modify: `scripts/qa/run-guest-experience-qa.sh`
- Modify: `tests/test_local_smoke_contract.py`
- Modify: `AGENTS.md`
- Modify: `docs/PRODUCT.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `.agent/designs/argus/DESIGN.md`
- Modify: `docs/CONVERSATIONAL_RUNTIME.md`
- Modify: `docs/QA_CONVERSATIONAL_TRANSCRIPTS.md`
- Modify: `docs/maintenance/dead-code-candidates.md`
- Regenerate: `docs/api/openapi.yaml`

**Interfaces:**
- Consumes: release profile schema, Render Blueprint, local mode scripts,
  canonical FastAPI OpenAPI.
- Produces: one consistent release contract with no retired variables and docs
  that distinguish removed surfaces from read-safe legacy records.

- [ ] **Step 1: Remove all active env declarations together**

  Delete the three exact variable names from examples, profile env/capabilities,
  Render services, shell env arrays/exports, local env writers, smoke checks,
  and active setup documentation. Verify the provider-mode variable remains.

- [ ] **Step 2: Update product and technical canon**

  Remove claims that the UI is merely hidden behind flags. State that dedicated
  endpoints and surfaces are removed, rows remain read-only compatibility data,
  and current recall belongs to Omnisearch / Idea Ledger.

- [ ] **Step 3: Regenerate OpenAPI**

  Run:

  ```bash
  poetry run python scripts/generate_openapi_artifact.py
  poetry run pytest tests/test_openapi_compatibility.py tests/test_alpha_artifacts.py tests/test_local_smoke_contract.py -q
  ```

  Expected: exit `0`; `/api/v1/strategies` and `/api/v1/collections` are absent.

- [ ] **Step 4: Prove protected provider configuration is unchanged**

  Run:

  ```bash
  git diff 9664e221fa50187d6b078ccdfcffd90cbc76d852 -- src/argus/domain/market_data/assets.py tests/evals tests/agent_runtime | rg "ARGUS_ASSET_PROVIDER_MODE|ARGUS_MARKET_DATA_PROVIDER_MODE"
  ```

  Expected: no diff output.

### Task 5: Full verification and browser evidence

**Files:**
- Create: `docs/reports/evidence/legacy-surface-removal/chat.png`
- Create: `docs/reports/evidence/legacy-surface-removal/sidebar.png`
- Create: `docs/reports/evidence/legacy-surface-removal/settings.png`
- Create: `docs/reports/evidence/legacy-surface-removal/README.md`

**Interfaces:**
- Consumes: final local API/web candidate and the locked base SHA.
- Produces: exact-head deterministic, build, and durable browser evidence.

- [ ] **Step 1: Run every required gate**

  Run full commands without file filters:

  ```bash
  cd web && bun test
  poetry run pytest
  poetry run ruff check .
  cd web && bun run build
  ```

  Record command, exit code, duration, and counts. For any failure, create a
  separate clean worktree at base SHA (never stash), run the identical command,
  and classify only from the side-by-side result.

- [ ] **Step 2: Run real-browser acceptance**

  Start the deterministic local stack, open the app with Playwright CLI,
  capture ordinary chat, expanded sidebar, and Settings, and verify there is no
  Strategies/Collections entry or Save Strategy control. Exercise no paid
  provider or Render workflow.

- [ ] **Step 3: Commit durable evidence**

  Write the exact candidate SHA, local URLs/mode, viewport, assertions, and
  screenshot filenames in the evidence README. Stop preview processes and
  clean scratch browser state.

- [ ] **Step 4: Audit exact diff and integration overlap**

  Fetch `origin/codex/private-alpha-next`, record its current SHA, compare
  `base..HEAD` with `base..origin/codex/private-alpha-next`, run the modularity
  budget against the would-be merged tree, and confirm `ChatInterface.tsx`
  contains no unrelated edits.

- [ ] **Step 5: Commit and push**

  Stage only this lane, commit with a Conventional Commit message, push
  `codex/remove-legacy-collections-strategies`, and do not merge or deploy.
