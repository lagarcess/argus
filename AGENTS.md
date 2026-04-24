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

1. **Initialize workspace**: Run `.github/setup.sh` (Poetry + Bun + mock data ready)
2. **Start dev environment**: Terminal 1: `poetry run fastapi dev src/argus/api/main.py`, Terminal 2: `cd web && bun run dev`
3. **Build + test**: `poetry run pytest` (backend), `bun test` (frontend)

---

## 📖 Documentation

- **Product Truth**: [`docs/PRODUCT.md`](./docs/PRODUCT.md)
- **Architecture**: [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- **API Contract**: [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md)
- **Data Model**: [`docs/DATA_MODEL.md`](./docs/DATA_MODEL.md)
- **Design System**: [`.agent/designs/argus/DESIGN.md`](./.agent/designs/argus/DESIGN.md)
- **OpenAPI Spec**: [`docs/api/openapi.yaml`](./docs/api/openapi.yaml)
- **Scheduled Framework**: [`.agent/.jules/README.md`](./.agent/.jules/README.md)

### 🛡️ Developer Identity: Mock Auth Mode
To bypass the Supabase OAuth wall in development environments (e.g., remote VMs), set the following environment variable:

`NEXT_PUBLIC_MOCK_AUTH=true`

**Benefits for Agents:**
- **Auth Bypass**: Instantly logs in as "Mock Developer" (mock user).
- **Sticky Sessions**: Automatically hydrated session across all refreshes.
- **Access Control**: Grants access to `/builder`, `/strategies`, etc., without OAuth.


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
