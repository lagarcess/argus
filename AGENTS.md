# Project Agents & Tools: Argus

Argus is a chat-first AI investing idea validation platform.

Users describe investing or trading ideas in natural language and Argus helps them understand, structure, simulate, and review how those ideas would have performed historically — without risking real capital.

The conversation is the primary product surface.
The backtesting engine is critical infrastructure.

This file is the primary orientation guide for AI coding agents working in the repository.

# 🛡️ Read These First (Mandatory)

Before making code changes, agents must review these source-of-truth docs in this order:

1. `docs/PRODUCT.md`
   - Product truth, scope boundaries, user priorities, and the "Golden Path."
2. `docs/ARCHITECTURE.md`
   - System boundaries, stateful vs stateless responsibilities, service ownership, and deployment model.
3. `docs/API_CONTRACT.md`
   - Frontend/backend contract, endpoint shapes, request/response truth, and auth/profile behavior.
4. `docs/DATA_MODEL.md`
   - Persistence truth, entities, ownership rules, and RLS expectations.
5. `.agent/designs/argus/DESIGN.md`
   - Visual system, product UX rules, chat-first interaction design, and anti-patterns.

> [!IMPORTANT]
> If code contradicts these docs, assume the docs represent intended Alpha direction unless implementation constraints prove otherwise.

# 🎯 Alpha Product Truth

**Argus Alpha Priorities:**
- Chat-first UX & AI-first onboarding
- Strategy drafting through conversation
- Simple, trustworthy backtests
- Recents/history retrieval
- Collections (organizational, not portfolios)
- English + Spanish support
- Fast iteration over feature breadth

**Out of Scope for Alpha:**
- Brokerage integrations & real money trading
- Social feeds & institutional tools
- Advanced portfolio analytics
- Mixed-asset backtests (Equity + Crypto in one run)
- Native mobile apps (PWA/Mobile-web only)

# ⚙️ Canonical Current Constraints

- **Same-Asset Simulations Only**: Runs must be either 100% Equity or 100% Crypto.
- **Default Benchmarks**: Equity -> `SPY`, Crypto -> `BTC`.
- **Logic**: Long-only, equal-weight multi-symbol runs.
- **Limits**: Max 5 symbols per run.
- **Localization**: Static UI must support English (`en`) and Spanish (`es-419`).
- **Organization**: Collections may mix themes/assets; runs may not mix asset classes.

# 🚀 Implementation Priority Order

1. Happy-path user experience (The "Golden Path")
2. API contract correctness
3. Reliability / Trust (Accurate metrics & benchmarks)
4. Mobile-friendly chat UX
5. Performance (<3s backtests)
6. Nice-to-have polish
7. Future complexity

> [!TIP]
> If unsure, optimize for: *"Does this help a normal person test an investing idea faster?"*

---

# 🧭 Current Milestone: Private Alpha Next Integration

When working from `codex/private-alpha-next`, use
`docs/specs/private-alpha-next-integration.md` as the active integration
staging source of truth. That doc records what conversation-trust work is
already closed, what remains high leverage, and what low-risk debt is safe for
external async agents.

Integration guardrails:

- Worker branches start from `codex/private-alpha-next`, not directly from
  `main`, unless the task is an urgent hotfix.
- External async agent Jules must work on focused `jules/**` branches and must
  not push directly to `main` or to the integration branch.
- Jules PRs should target `codex/private-alpha-next`; CI is configured to run on
  `jules/**` pushes and on PRs targeting the integration branch.
- Codex reviews worker diffs before merging or cherry-picking them into the
  integration branch.
- Production deploys remain manual and founder-directed.
- Perplexity Research Lab remains design-only until a later approved
  implementation milestone.

---

# 🧭 Completed Checkpoint: Private Alpha Conversation Trust

When working on private-alpha conversation trust branches, including
`codex/private-alpha-conversation-trust` and follow-up branches such as
`codex/private-alpha-ux-trust-followups`, use
`docs/specs/private-alpha-conversation-trust.md` as the milestone source of
truth for historical context. This milestone hardened the current private-alpha
chat/backtest loop; it does not implement the Perplexity Research Lab thesis.

Milestone guardrails:

- Re-enable fast CI and local verification without automatic production deploys.
- Unify confirmation, queued/running job, result, and assistant-turn actions as
  one coherent artifact lifecycle.
- Keep feedback/retry/more-menu actions structured and turn-scoped; do not use
  prose matching to infer retry behavior.
- Add out-of-focus chat attention state without inventing backend facts in the
  frontend.
- Treat Quick take, Explain result, and Try next as distinct result surfaces:
  Quick take is the first-glance result readout, Explain result is the deeper
  fact-grounded breakdown action, and Try next must come from supported next
  experiments rather than generic advice or duplicated Quick take prose.
- Do not restore "copy conversation link" or "share conversation id" as a
  pseudo-share action. Until the public excerpt feature exists, the header menu
  should expose only real owner actions such as rename, pin, and delete.
- When public conversation excerpts are implemented, they must be immutable,
  sanitized snapshots behind owner-only create/revoke and an unguessable public
  slug. Do not expose source conversation ids, route receipts, provider/model
  metadata, retry payloads, or direct anon table access.
- Keep Perplexity/Research Lab work as design-only unless a later milestone
  explicitly starts that implementation. The preserved thesis lives in
  `docs/specs/research-lab-thesis.md`.

Never let UI polish violate the runtime principles below: the frontend renders
backend-provided artifacts, LangGraph remains the only chat brain, and
deterministic result prose must not become the normal happy-path Argus voice.

---

# 🧭 Argus Philosophy & Runtime Principles

Argus is chat-first, AI-first, and trust-first. The assistant should help a normal person move from a rough investing idea to a clear historical test with as little friction as possible, while being honest about assumptions, limitations, and supported execution.

## Product Philosophy

- **Conversation is the product**: The chat thread is the primary workspace. Forms, dashboards, and dense configuration screens are secondary and should not replace conversational progressive disclosure.
- **The backtesting engine is critical infrastructure**: Results must be reproducible, grounded in real engine outputs, and presented with clear assumptions.
- **Simplicity beats breadth**: Prefer the smallest supported path that lets the user test an idea safely and understand the result.
- **Trust through clarity**: Never hide defaults, unsupported behavior, missing data, or asset-class constraints. Explain limitations in product language, not provider plumbing.
- **Beginner-friendly by default**: Use plain language, small follow-up choices, and honest educational context. Avoid trading-terminal complexity unless the user explicitly asks for more depth.
- **Chat-first continuity**: Confirmation cards, result cards, saved strategies, and follow-up actions must remain attached to the conversation flow and hydrate correctly after reload.

## Runtime Migration Principles

These principles come from the recent modular monolith / LangGraph migration plans in `docs/superpowers/plans/` and must not regress:

- **LLM-first interpretation**: Normal user language must reach the structured LLM interpreter before routing decisions. Do not add regex, hardcoded language gates, or legacy NLU shortcuts before the interpreter.
- **Deterministic guardrails after interpretation**: Code validates facts the LLM cannot own: asset resolution, provider availability, same-asset constraints, max symbol limits, date/data windows, executable indicator support, benchmark defaults, and required fields.
- **One active chat brain**: The LangGraph runtime is the only active conversational runtime. Do not restore or recreate a parallel legacy orchestrator, state machine, or second intent taxonomy.
- **LangGraph owns runtime memory**: Runtime thread state belongs in the LangGraph checkpointer using `thread_id == conversation_id`. Supabase owns product persistence such as messages, conversations, backtest runs, strategies, collections, feedback, and usage counters.
- **Supabase product records are durable artifacts**: Messages store assistant/user text and structured metadata. Backtest runs store immutable result truth. Strategies are saved from canonical run/result state, not reconstructed frontend prose.
- **Canonical SSE is data-only**: Production chat streaming should emit canonical `data: {"type": ...}` frames: `stage_start`, `token`, `stage_outcome`, `final`, then `[DONE]`. Legacy named `event:` parsing may be tolerated by the frontend during migration, but new backend paths should not depend on it.
- **Thin FastAPI routers**: API routes perform auth, quota checks, request validation, transport, persistence, and error shaping. They must not become a second conversational orchestrator.
- **Frontend renders, it does not invent**: The web app renders backend-provided stages, cards, actions, and persisted metadata. It should not fake progress states, reconstruct strategies from text, or infer hidden run context.
- **Composer mentions are provenance, not shortcuts around validation**: The `@` tool must use provider-backed asset discovery and the supported indicator catalog, not a tiny static menu. Selected mentions help bound ambiguous references for the backend, but normal LLM interpretation and backend validation still own executable meaning. Browser-session discovery caching is acceptable; durable Supabase discovery/market-data caches require explicit schema, freshness, and invalidation design.
- **No Alpha RAG/vector overreach**: Do not add embeddings, pgvector, semantic memory, or agentic RAG for the launch chat/backtest loop. Use provider catalogs, structured state, run metadata, saved strategies, and text search until a concrete Beta need exists.
- **Provider details stay internal**: Users should hear capability truth ("I can test BTC over that period" or "that data range is not available for this instrument"), not vendor-specific implementation details unless the product explicitly decides otherwise.

---

## 🛡️ Rules (`.agent/rules/`) — Always-Follow Guidelines

| Rule                  | Scope                                 | Purpose                                                                       |
| :-------------------- | :------------------------------------ | :---------------------------------------------------------------------------- |
| `coding-standards.md` | `src/**/*.py`, `web/**/*.ts`          | Python loguru/types, TypeScript zod/react-hook-form, API contract sync        |
| `testing.md`          | `tests/**/*.py`, `web/__tests__/**/*` | TDD-first, 63% coverage, Faker mock data, frontend integration                |
| `git-workflow.md`     | All                                   | Conventional commits, monorepo branch naming, feature flags, API contract PRs |
| `performance.md`      | `src/argus/analysis/**`, `web/**`     | Numba <50ms/analytic, <3s backtest, <30s build, Bun hot-reload                |
| `workspace.md`        | All                                   | Monorepo layout, Poetry + Bun, env separation, mock data toggle               |

---

## 🧠 Skills (`.agent/skills/`) — Domain Knowledge

| Skill                                | When to Use                                                                 |
| :----------------------------------- | :-------------------------------------------------------------------------- |
| `coding-standards/`                  | Python/TypeScript style, logging, validation patterns                       |
| `numba-patterns/`                    | JIT compilation, warmup, pure-math constraints                              |
| `backend-patterns/`                  | API-first design, sync execution, error responses, caching                  |
| `testing-patterns/`                  | pytest, TDD workflow, coverage strategy, rate-limit tests                   |
| `frontend-patterns/`                 | React/Next.js, Argus design system, component patterns, form validation    |
| `security-review/`                   | RLS policies, JWT handling, Supabase auth, Alpaca secrets                   |
| `supabase/`                          | Supabase CLI, Auth, Edge Functions, and migration workflows                 |
| `supabase-postgres-best-practices/`  | Performance optimization, GIN indexing, and RLS bottlenecks                 |
| `mock-data-patterns/`                | Faker generators, mock API endpoints, toggle mechanism                      |
| `database-patterns/`                 | Supabase migrations, RLS immutability, quota management                     |
| `monorepo-patterns/`                 | API contract sync, Bun + Poetry coordination                                |
| `design-taste-frontend/`             | High-end UI/UX, CSS hardware acceleration, metric-based design              |
| `emil-design-eng/`                   | UI polish, animation physics, and micro-interaction details                 |
| `react-components/`                  | Stitch-to-React conversion, modular component architecture                  |
| `redesign-existing-projects/`        | Upgrading legacy UI to premium, anti-generic standards                      |
| `shadcn-ui/`                         | Shadcn component integration, customization, and best practices             |
| `stitch-design/`                     | Stitch MCP orchestration, prompt enhancement, screen generation             |
| `stitch-design-taste/`               | Semantic design system enforcement, premium aesthetics                      |
| `stitch-loop/`                       | Iterative Baton-Passing loop for rapid UI development                       |
| `rag-architect/`                    | RAG/LLM agent architecture, DeepSeek R1/Qwen integration                    |
| `database-schema-designer/`         | Precision SQL migrations, RLS policies, and Phase C accounting              |
| `apple-hig-expert/`                  | Premium UI/UX aesthetics, Argus/Apple-grade physics                         |
| `skill-security-auditor/`           | Automated security gating for agent skills and external plugins               |
| `playwright-pro/`                   | Advanced E2E testing framework, target 63% coverage                          |
| `senior-architect/`                 | Principal-level system guidance and Institutional-grade reliability         |
| `saas-metrics-coach/`               | Fintech quota throughput and monetization logic                              |

---

## ⚙️ Workflows (`.agent/workflows/`) — Command Reference

### Core Development

| Command      | Description                                             |
| :----------- | :------------------------------------------------------ |
| `/plan`      | Generate implementation plan before changes (API-first) |
| `/implement` | TDD: write test → implement → verify (mock data ready)  |
| `/fix`       | Fix a failing test (max 3 iterations, verify mock API)  |

### Quality & Release

| Command   | Description                                                                  |
| :-------- | :--------------------------------------------------------------------------- |
| `/review` | Code review: standards, security, design audits                              |
| `/verify` | Full suite: pytest + Bun lint + coverage check (63%+) + backtest perf (<3s)  |
| `/pr`     | Create PR: include API contract link if schema changed, mark scope (api/web) |
| `/perf`   | Benchmark: Numba analysis, backtest latency, Bun build time                  |

### Discovery & Ops

| Command  | Description                                                               |
| :------- | :------------------------------------------------------------------------ |
| `/issue` | Diagnose: trace backend/frontend, check with mock API first               |
| `/learn` | Extract lessons: what patterns worked, metrics improved, blockers removed |

---

## 🔧 Scripts (`.agent/scripts/github/`) — GitHub Context

| Script                 | Purpose                                       |
| :--------------------- | :-------------------------------------------- |
| `batch_get_issues.sh`  | Fetch multiple issues in one go               |
| `get_issue_details.sh` | Fetch + format a single issue                 |
| `parse_issues.py`      | Parse issue JSON → readable agent context     |
| `parse_pr_comments.py` | Parse PR review comments → prioritized report |

Usage:

```bash
& "C:\Program Files\Git\bin\bash.exe" ./.agent/scripts/github/batch_get_issues.sh 42 43 44
```

---

## 🚀 Quick Start (Local Development)

Argus supports two primary local scenarios. Choose the script first; do not
manually juggle backend mode flags for normal work.

### Fast Iteration (Dev Mode)
**Use this for:** Building features, debugging, UI work, isolated testing — no persistence needed.

1. **Initialize workspace** (one time):
   ```bash
   .github/setup.sh
   ```

2. **Activate Dev Mode** (Terminal 1: Backend):
   ```bash
   .github/dev.sh
   ```
   This sources `.env` if present, then overrides backend runtime flags for fast
   synthetic-data development.

3. **Start frontend** (Terminal 2):
   ```bash
   cd web && bun run dev
   ```

4. **Frontend env**: for fast mock-auth dev, set in `web/.env.local`:
   ```bash
   NEXT_PUBLIC_MOCK_AUTH=true
   NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1
   ```

5. **Access**: Open `http://localhost:3000` → Auto-logs in as "Mock Developer"

6. **Build + test**:
   ```bash
   poetry run pytest tests/
   cd web && bun test
   ```

### Production Parity (QA Mode)
**Use this for:** End-to-end testing, launch validation, browser QA matrix, release verification.

1. **Initialize workspace** (one time):
   ```bash
   .github/setup.sh
   ```
   Your `.env` should already contain real Supabase credentials and API keys.

2. **Activate QA Mode** (Terminal 1: Backend):
   ```bash
   .github/qa.sh
   ```
   This requires real Supabase, OpenRouter, Alpaca, and `DATABASE_URL` values in
   `.env`, then overrides backend runtime flags for strict production-parity QA.

3. **Start frontend** (Terminal 2):
   ```bash
   cd web && bun run dev
   ```

   For real auth QA, set in `web/.env.local`:
   ```bash
   NEXT_PUBLIC_MOCK_AUTH=false
   NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1
   ```

4. **Run full QA suite**:
   ```bash
   # Backend contract & runtime tests
   poetry run pytest tests/agent_runtime/ -q
   
   # Frontend integration
   cd web && bun test __tests__/
   
   # Browser QA (if Playwright is set up)
   bun run test:e2e
   ```

### What Each Mode Script Does

**`.github/dev.sh`** sets:
- `ARGUS_PERSISTENCE_MODE=memory` — Ephemeral, no database writes
- `ARGUS_DEV_MEMORY_FALLBACK=true` — Tolerant (failures don't block the chat)
- `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture` — Hardcoded test assets (no API calls)
- `ARGUS_CHECKPOINTER_MODE=memory` — No checkpoint persistence
- `ARGUS_MOCK_AUTH=true` — Backend mock auth for local development

**`.github/qa.sh`** sets:
- `ARGUS_PERSISTENCE_MODE=supabase` — Durable, all writes go to Supabase
- `ARGUS_DEV_MEMORY_FALLBACK=false` — Strict (errors propagate for debugging)
- `ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider` — Real provider-backed asset resolution
- `ARGUS_CHECKPOINTER_MODE=postgres` — Runtime recovery/reload through Supabase Postgres
- `ARGUS_MOCK_AUTH=false` — Real backend auth validation

**Your `.env` stays mostly constant** — It stores credentials and safe defaults.
The scripts are authoritative for backend mode flags, so you should not need to
remember the right `ARGUS_*` combination for dev vs QA.

**Recorded provider fixtures** are not the default manual QA path. They are for
deterministic provider tests or CI when `ARGUS_ASSET_FIXTURE_PATH` points to a
provider-shaped asset catalog snapshot. Until such a snapshot is generated and
versioned, manual QA should use `live_provider` so symbol recognition exercises
the same provider-backed resolution path production will use.

### Feature Flags (All Private-Alpha)
Keep these disabled unless explicitly testing:
```bash
NEXT_PUBLIC_STRATEGIES_ENABLED=false
NEXT_PUBLIC_COLLECTIONS_ENABLED=false
NEXT_PUBLIC_OMNISEARCH_ENABLED=false
NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED=false
NEXT_PUBLIC_PRIVATE_ALPHA_ONBOARDING_ENABLED=false
```

### Frontend Environment (web/.env.local)
Create `web/.env.local` with frontend-specific settings:
```bash
cp web/.env.local.example web/.env.local
```

For fast Dev Mode:
```bash
NEXT_PUBLIC_MOCK_AUTH=true
NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_STRATEGIES_ENABLED=false
NEXT_PUBLIC_COLLECTIONS_ENABLED=false
NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED=false
```

For QA Mode with real Supabase auth:
```bash
NEXT_PUBLIC_MOCK_AUTH=false
NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1
NEXT_PUBLIC_STRATEGIES_ENABLED=false
NEXT_PUBLIC_COLLECTIONS_ENABLED=false
NEXT_PUBLIC_CHAT_EXPLORATORY_SUGGESTIONS_ENABLED=false
```

---

## 📖 Documentation

- **Product Truth**: [`docs/PRODUCT.md`](./docs/PRODUCT.md)
- **Architecture**: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- **API Contract**: [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md)
- **Data Model**: [`docs/DATA_MODEL.md`](./docs/DATA_MODEL.md)
- **Design System**: [`.agent/designs/argus/DESIGN.md`](./.agent/designs/argus/DESIGN.md)
- **OpenAPI Spec**: [`docs/api/openapi.yaml`](./docs/api/openapi.yaml)
- **Scheduled Framework**: [`.agent/.jules/README.md`](./.agent/.jules/README.md)

### Documentation Classes

- **Canon docs**: `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`,
  `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, and
  `.agent/designs/argus/DESIGN.md`. These define intended Alpha direction.
- **Active milestone/spec docs**: files under `docs/specs/` that explicitly
  name the current branch or milestone. Use them for scoped execution details
  after reading canon docs.
- **Historical plans**: older closure plans and `docs/superpowers/plans/*`
  files are evidence and context, not current source of truth unless an active
  milestone doc points back to them.

### 🛡️ Developer Identity: Mock Auth Mode
To bypass the Supabase auth wall in fast Dev Mode, set the following frontend
environment variable:

`NEXT_PUBLIC_MOCK_AUTH=true`

Keep `NEXT_PUBLIC_MOCK_AUTH=false` for QA Mode when validating signup, login,
logout, persistence, reload, and private-alpha allowlist behavior.

**Benefits for Agents:**
- **Auth Bypass**: Instantly logs in as "Mock Developer" (mock user).
- **Sticky Sessions**: Automatically hydrated session across all refreshes.
- **Access Control**: Grants access to `/builder`, `/strategies`, etc., without OAuth.


---

## ⚙️ Architectural Patterns

### 1. Fail-Open Deterministic Fallback
Used for: LLM-backed features that must never block the chat

Pattern:
- Try LLM with bounded timeout (ThreadPoolExecutor)
- On timeout/failure → deterministic fallback
- Log failure but don't expose to user
- Route receipt captures outcome for ops

Example: `result_breakdown_message()` in src/argus/api/chat/breakdown.py

### 2. Task-Scoped Execution Budget
Used for: All OpenRouter calls

Pattern:
- Each task (interpretation, breakdown, naming) has own profile
- Profile controls: temperature, max_tokens, timeout_seconds, max_retries
- Same code path; different budgets based on task importance
- Route receipt captures latency, model, tier, token usage

Example: OPENROUTER_PROFILES in src/argus/llm/openrouter.py

### 3. Stage Result Contract
Used for: Runtime decision-making stages

Pattern:
- Stage returns StageResult(outcome: str, stage_patch: dict)
- Outcome drives routing (ready_to_confirm, needs_clarification, etc.)
- Patch contains only state mutations
- Stage is pure function of (state, contract)

Example: confirm_stage() in src/argus/agent_runtime/stages/confirm.py

### 4. Response Voice Contract
Used for: All assistant-facing prose

Pattern:
- Explicit tone contract defined in response_style.py
- Anti-patterns: dense PDF tone, metric dumps, generic lists, jargon
- Deterministic facts ground LLM language
- No raw enums or internal field names in user-facing text
- Result readouts must preserve surface ownership: Quick take should not render
  supported next experiments as visible "Try next" copy, while Explain result
  must not reuse Quick take / Quick Breakdown headings.

Example: ARGUS_RESPONSE_STYLE_CONTRACT in src/argus/agent_runtime/response_style.py

### 5. Provider Mode Abstraction
Used for: Making asset/market data deterministic without HTTP mocking

Pattern:
- `ARGUS_MARKET_DATA_PROVIDER_MODE` controls data source.
- Modes:
  - `live_provider`: real provider catalog/data; default for manual QA and production-like validation.
  - `recorded_provider_fixture`: provider-shaped catalog snapshot; deterministic tests/CI only and requires `ARGUS_ASSET_FIXTURE_PATH`.
  - `synthetic_unit_fixture`: small hardcoded unit fixture; fast Dev Mode only.
- Code path unchanged; only data source changes.
- Enables deterministic testing with real code paths without making synthetic fixtures look like production truth.

Example: _asset_provider_mode() in src/argus/domain/market_data/assets.py

### 6. Capability Contract Pattern
Used for: Validating what's executable vs draft-only

Pattern:
- CapabilityContract class centralizes "can I execute this?"
- Returns ranked candidates, not binary yes/no
- Used by interpret → confirm → execute → capability Q&A
- Single source of truth across all surfaces

### 7. Semantic Integrity Rules
Used for: Preserving user intent across edits and defaults

Pattern:
- User-explicit constraints (dates, assets, cadence) are immutable
- Defaults only fill gaps, never overwrite user intent
- If constraint cannot be preserved → clarify, don't override
- For DCA: recurring_contribution is sacred once set

Example: conserve_semantic_constraints() in src/argus/agent_runtime/semantic_integrity.py

### 8. Anti-Pattern Checklist
Never do this:
- ❌ Regex/phrase gates before LLM interpretation
- ❌ Strategy name routing (use intent + capability contract)
- ❌ Parallel chat orchestrators (LangGraph is the only brain)
- ❌ Frontend prose inventing strategy state
- ❌ Raw enum/field names in assistant voice
- ❌ Unsupported causality from context packets
- ❌ Silent defaults overwriting user constraints
- ❌ Duplicate action surfaces (one button per action, owned by one component)
---

## 🛑 Never-Violate Standards

1. **API Contract First**: Update `docs/api_contract.md` before implementation PRs.
2. **Structured Logging**: Use `loguru` (backend) + React Query logs (frontend). No `print()`.
3. **TDD First**: Write failing test before fixing any bug.
4. **JIT Warmup**: Changes to `src/argus/analysis/` require `warmup_jit()` in tests.
5. **<3 Second Backtest**: Single-symbol backtest must execute in <3s.
6. **No Backend Secrets in Frontend**: Root `.env` (backend), `web/.env.local` (frontend).
7. **Use `temp/`**: Never dump scratch files in project root.
8. **Monorepo Coordination**: Backend + frontend must run together after `setup.sh`.
9. **Critical Findings Only**: Only PR/Journal critical improvements (security bugs, >20% perf gain).
10. **Postgres Performance**: All SQL/RLS must be audited against `postgres-best-practices`.
11. **Branch Sync & Goal Realignment**: Every agent session must fetch/rebase `main` and re-verify original mission against any architectural drift before completion.

---

# 🧠 Agent Decision Rules

Before implementing any feature, ask:
1. Is this aligned with `PRODUCT.md`?
2. Is this compatible with `API_CONTRACT.md`?
3. Does `DATA_MODEL.md` already define the source of truth?
4. Does this preserve `ARCHITECTURE.md` boundaries?
5. Does this fit `DESIGN.md` chat-first UX?
6. Is this simpler than the alternative?

*If the answer to any of these is "No," pause and redesign.*

# 🎨 Frontend Guidance
- Prioritize mobile-friendly responsive chat UX.
- Use progressive disclosure to handle complexity.
- Avoid cluttered dashboards and dense data tables by default.
- Ensure all static UI strings are translatable (i18next).

# 🛠️ Backend Guidance
- Keep request handling stateless and reproducible.
- Treat Supabase as the canonical persistence layer.
- Enforce contract-first changes and strict rate limits.
- Provide graceful, RFC 9457-compliant error responses.

# ⚖️ If Docs Conflict
Priority order of authority:
1. `PRODUCT.md`
2. `API_CONTRACT.md`
3. `DATA_MODEL.md`
4. `ARCHITECTURE.md`
5. `DESIGN.md`
6. Existing code

*Argus should feel modern, intelligent, simple, trustworthy, and fast — never intimidating.*

---

## Commit / Checkpoint Discipline

For multi-step or high-risk work, do not accumulate large uncommitted diffs.

Before starting:
- Check `git status`.
- Identify any user-owned changes and do not overwrite them.
- Use a branch/worktree for substantial work.

During implementation:
- Prefer atomic, single-purpose changes.
- After each coherent slice, run focused verification.
- If the slice is working, create a conventional commit checkpoint before moving to the next slice.
- Do not let runtime/UI work grow into 50-file uncommitted diffs unless explicitly approved.

For long plans:
- Each worker/slice should end with: tests run, browser smoke note if applicable, known caveats, and either a commit or a clear reason it remains uncommitted.

Never:
- Commit unrelated user changes.
- Hide broken work in a broad checkpoint.
- Use vague commit messages.
- Leave large exploratory diffs without explaining rollback risk.
