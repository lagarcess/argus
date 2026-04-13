# Project Agents & Tools: Argus

AI agent configuration registry for the Argus backtesting engine. This file serves as the primary index for skills, rules, and workflows used by all AI agents (both interactive and autonomous) working on the project.

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
| `frontend-patterns/`                 | React/Next.js, Robinhood design system, component patterns, form validation |
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

**API Contract:** [`docs/api/api_contract.md`](./docs/api/api_contract.md)
**OpenAPI Spec:** [`docs/api/openapi.yaml`](./docs/api/openapi.yaml)
**Scheduled Framework:** [`.agent/.jules/README.md`](./.agent/.jules/README.md)

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
