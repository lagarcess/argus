# Project Agents & Tools: Argus

AI agent configuration registry for the Argus backtesting engine.

---

## 🛡️ Rules (`.agent/rules/`) — Always-Follow Guidelines

| Rule | Scope | Purpose |
| :--- | :--- | :--- |
| `coding-standards.md` | `src/**/*.py` | loguru logging, type hints, 90 char limit, Pydantic |
| `testing.md` | `tests/**/*.py` | TDD-first, 63% coverage target, pytest conventions |
| `git-workflow.md` | All | Conventional commits, branch naming, PR process |
| `performance.md` | `src/argus/analysis/**` | Numba JIT warmup, pure math, perf targets |
| `workspace.md` | All | temp/ for scratch, Poetry, file organization |

---

## 🧠 Skills (`.agent/skills/`) — Domain Knowledge

| Skill | When to Use |
| :--- | :--- |
| `coding-standards/` | Python code style, logging, validation patterns |
| `numba-patterns/` | JIT compilation, warmup, pure-math constraints |
| `backend-patterns/` | Data provider, caching, config, error handling |
| `testing-patterns/` | pytest, TDD workflow, coverage strategy |
| `frontend-patterns/` | React/Next.js components, design system, API integration |
| `security-review/` | Secrets, .env safety, API boundaries, auth |

---

## ⚙️ Workflows (`.agent/workflows/`) — Slash Commands

### Core Development
| Command | Description |
| :--- | :--- |
| `/plan` | Generate implementation plan before making changes |
| `/implement` | TDD loop: write test → implement → verify |
| `/fix` | Fix a failing test (max 3 iterations) |

### Quality & Release
| Command | Description |
| :--- | :--- |
| `/review` | Code review with security and quality checks |
| `/verify` | Run full test suite + lint |
| `/pr` | Create a comprehensive pull request |
| `/perf` | Benchmark Numba JIT performance paths |

### Discovery & Ops
| Command | Description |
| :--- | :--- |
| `/issue` | Diagnose, validate, create GitHub issues |
| `/learn` | Extract engineering lessons from completed work |

---

## 🔧 Scripts (`.agent/scripts/github/`) — GitHub Context

| Script | Purpose |
| :--- | :--- |
| `batch_get_issues.sh` | Fetch multiple issues in one go |
| `get_issue_details.sh` | Fetch + format a single issue |
| `parse_issues.py` | Parse issue JSON → readable agent context |
| `parse_pr_comments.py` | Parse PR review comments → prioritized report |

Usage:
```bash
& "C:\Program Files\Git\bin\bash.exe" ./.agent/scripts/github/batch_get_issues.sh 42 43 44
```

---

## 🛑 Never-Violate Standards

1. **Structured Logging**: Use `loguru` with context. No `print()`.
2. **TDD First**: Write a failing test before fixing any bug.
3. **JIT Warmup**: Changes to `src/argus/analysis/` require `warmup_jit()`.
4. **Use `temp/`**: Never dump scratch files in the project root.
5. **Secrets in `.env`**: Never commit credentials to source control.
