# Project Agents & Tools: Argus

AI agent configuration registry for the Argus backtesting engine.

---

## 🎯 Jules Agents — Autonomous Scheduled Tasks

Argus uses **Jules** (Antigravity's async AI scheduler) to run autonomous agents on a fixed schedule. See [`.jules/README.md`](./.jules/README.md) for framework overview.

| Agent             | Role                   | Frequency        | Reference                                                                        | Journal                               |
| :---------------- | :--------------------- | :--------------- | :------------------------------------------------------------------------------- | :------------------------------------ |
| **Sentinel** 🛡️   | Security Guardian      | Weekly (Tue 9am) | [`.jules/scheduled_tasks/sentinel.md`](./.jules/scheduled_tasks/sentinel.md)     | `.agent/.jules/journal/sentinel.md`   |
| **Bolt** ⚡       | Performance Guardian   | Daily (6am)      | [`.jules/scheduled_tasks/bolt.md`](./.jules/scheduled_tasks/bolt.md)             | `.agent/.jules/journal/bolt.md`       |
| **Palette** 🎨    | UX Guardian            | Daily (7am)      | [`.jules/scheduled_tasks/palette.md`](./.jules/scheduled_tasks/palette.md)       | `.agent/.jules/journal/palette.md`    |
| **Trinity** 🧪    | Test Automation        | Daily (8am)      | [`.jules/scheduled_tasks/trinity.md`](./.jules/scheduled_tasks/trinity.md)       | `.agent/.jules/journal/trinity.md`    |
| **Architect** 🏗️  | Database Guardian      | Weekly (Sat 3pm) | [`.jules/scheduled_tasks/architect.md`](./.jules/scheduled_tasks/architect.md)   | `.agent/.jules/journal/architect.md`  |
| **Chronicler** 📚 | Documentation Guardian | Weekly (Sun 6pm) | [`.jules/scheduled_tasks/chronicler.md`](./.jules/scheduled_tasks/chronicler.md) | `.agent/.jules/journal/chronicler.md` |

**Journal rule:** Only log critical findings. If no action required, write "no critical finding" and stop (no PR creation).

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

| Skill                     | When to Use                                                                    |
| :------------------------ | :----------------------------------------------------------------------------- |
| `coding-standards/`       | Python/TypeScript style, logging, validation patterns                          |
| `numba-patterns/`         | JIT compilation, warmup, pure-math constraints                                 |
| `backend-patterns/`       | API-first design, sync execution, error responses, caching                     |
| `testing-patterns/`       | pytest, TDD workflow, coverage strategy, rate-limit tests                      |
| `frontend-patterns/`      | React/Next.js, Robinhood design system, component patterns, form validation    |
| `security-review/`        | RLS policies, JWT handling, Supabase auth, Alpaca secrets, is_admin bypass     |
| **`mock-data-patterns/`** | Faker generators, mock API endpoints, toggle mechanism (NEXT_PUBLIC_MOCK_API)  |
| **`database-patterns/`**  | Supabase migrations, RLS immutability, quota management, Edge Functions        |
| **`monorepo-patterns/`**  | API contract sync, coordinated deployment, Bun + Poetry, TypeScript ↔ Pydantic |

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
| `/review` | Code review: standards, security (Sentinel checks), design (Palette checks)  |
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
2. **Read setup guide**: See [`docs/startup.md`](./docs/startup.md) for full step-by-step instructions
3. **Start dev environment**: Terminal 1: `poetry shell && fastapi dev src/argus/api/main.py`, Terminal 2: `cd web && bun run dev`
4. **Toggle mock data**: `NEXT_PUBLIC_MOCK_API=true` (frontend only for independent dev), `NEXT_PUBLIC_MOCK_API=false` (real API)
5. **Build + test**: `poetry run pytest` (backend), `bun test` (frontend), `bun run build` (production)

---

## � Documentation

**Setup & Launch:** [`docs/startup.md`](./docs/startup.md) — Dependencies, environment config, running backend/frontend, troubleshooting
**API Contract:** [`docs/api_contract.md`](./docs/api_contract.md) — Endpoint specs, request/response schemas, error codes
**Agent Framework:** [`.jules/README.md`](./.jules/README.md) — Jules scheduler, scheduled tasks, skills, rules, workflows

---

## �🛑 Never-Violate Standards

1. **API Contract First**: Update `docs/api_contract.md` before backend/frontend PRs; Pydantic ↔ TypeScript types must sync.
2. **Structured Logging**: Use `loguru` (backend) + React Query logs (frontend). No `print()`.
3. **TDD First**: Write failing test before fixing any bug; use Faker for realistic test data.
4. **JIT Warmup**: Changes to `src/argus/analysis/` require `warmup_jit()` in tests.
5. **<3 Second Backtest**: Single-symbol backtest must execute end-to-end in <3s.
6. **No Backend Secrets in Frontend**: Root `.env` (backend), `web/.env.local` (frontend NEXT*PUBLIC*\* only).
7. **Use `temp/`**: Never dump scratch files in project root.
8. **Monorepo Coordination**: Backend + frontend must run together after `setup.sh` (deploy together, test together).9. **Critical Findings Only**: Agents journal only critical improvements (security bugs, >20% perf gain, new test coverage). No action? Write "no finding" and stop (no PR).
