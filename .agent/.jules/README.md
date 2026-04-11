# Jules – AI Agent Reference & Journal

This directory contains reference documentation and journals for Jules (scheduling framework).

---

## 📚 Structure

### `.agent/.jules/scheduled_tasks/`

Reference documents for each scheduled task agent. **For reference only** — these are read by Jules during task execution to understand its role, best practices, anti-patterns, and where to journal findings.

Each task file includes:

- Mission statement
- Command reference
- Good/bad patterns with examples
- Anti-patterns to avoid
- Journal instructions (write to `.agent/.jules/journal/`)

**Available tasks:**

- `sentinel.md` — 🛡️ Security Guardian
- `bolt.md` — ⚡ Performance Guardian
- `palette.md` — 🎨 UX Guardian
- `trinity.md` — 🧪 Test Automation Guardian
- `architect.md` — 🏗️ Database Guardian
- `chronicler.md` — 📚 Documentation Guardian

### `.agent/.jules/journal/`

Where agents **write learnings**. Only create journal entries for critical findings.

**Journal files** (one per agent):

- `sentinel.md` — Security vulnerabilities, policy breaches
- `bolt.md` — Performance improvements (>20% speedup)
- `palette.md` — UX improvements (accessibility fix, design system alignment)
- `trinity.md` — Test coverage additions (new endpoint tests, quota tier validation)
- `architect.md` — Schema changes (new table, RLS policy, quota reset)
- `chronicler.md` — Documentation artifacts (new guide, API update, troubleshooting)

---

## ◼️ What is Jules?

Jules is the **Antigravity AI scheduling framework**. You define "scheduled tasks" (agents) that run on a fixed schedule and report findings in a shared journal.

**Key principles:**

- Each task runs autonomously (independently scheduled)
- Each task writes learnings to a **shared journal** (not task-specific doc)
- Task reference docs explain **purpose, not execution** (no "how to run" instructions)
- **Only log critical findings** — if there's nothing to improve, write "no action needed" and stop (no PR)
- **Anti-patterns matter** — task reference should warn about common mistakes

---

## 📅 Suggested Schedule

| Task              | Schedule              | Rationale                               |
| ----------------- | --------------------- | --------------------------------------- |
| **Sentinel** 🛡️   | Weekly (Tuesday 9am)  | Security audits before code reviews     |
| **Bolt** ⚡       | Daily (6am)           | Performance regression detection early  |
| **Palette** 🎨    | Daily (7am)           | Daily UX micro-improvements             |
| **Trinity** 🧪    | Daily (8am)           | Keep coverage healthy, catch gaps early |
| **Architect** 🏗️  | Weekly (Saturday 3pm) | Weekly schema review, no time pressure  |
| **Chronicler** 📚 | Weekly (Sunday 6pm)   | Lessons learned, team knowledge sync    |

---

## 🧠 What are Skills?

Skills are **reusable packages of knowledge** that extend agent capabilities.

Each skill contains:

- **Instructions:** How to approach the task
- **Best practices:** Conventions to follow
- **Code examples:** Real usage patterns
- **Resources:** Scripts, templates, references

When an agent runs, it reads relevant skills and applies their guidance.

**Argus skills** (in `.agent/skills/`):

- `coding-standards/` — Python/TypeScript style, logging, type hints
- `numba-patterns/` — JIT compilation, warmup, pure-math constraints
- `backend-patterns/` — API-first design, sync execution, error responses
- `testing-patterns/` — pytest, TDD workflow, coverage strategy
- `frontend-patterns/` — React/Next.js components, design system
- `security-review/` — RLS policies, JWT handling, Supabase auth
- `mock-data-patterns/` — Faker generators, mock API endpoints
- `database-patterns/` — Supabase migrations, RLS, quota management
- `monorepo-patterns/` — API contract sync, coordinated deployment

---

## 🔄 What are Rules & Workflows?

**Rules** (in `.agent/rules/`): Always-follow guidelines for the codebase.

- `coding-standards.md` — Language conventions
- `testing.md` — TDD-first, coverage targets
- `git-workflow.md` — Branch naming, commit messages
- `performance.md` — Backtest <3s, build <30s, Numba targets
- `workspace.md` — Monorepo layout, env separation

**Workflows** (in `.agent/workflows/`): Command reference (e.g., `/plan`, `/implement`, `/review`).

---

## 📖 Documentation References

Scheduled tasks need to know where to find setup instructions and API docs:

- **Setup & launch:** `docs/startup.md` (environment, dependencies, launch guide)
- **API contract:** `docs/api_contract.md` (endpoint specs, request/response schemas)
- **Architecture:** `AGENTS.md` (overall agent structure, skills, rules)

---

## 🎯 Example: Running a Scheduled Task

**Sentinel runs daily:**

1. Read `sentinel.md` (mission, focus areas, patterns)
2. Read relevant skills (security-review, coding-standards)
3. Audit codebase for security gaps
4. If critical finding:
    a. Create a short-lived feature branch (see **Branching & PRs** below).
    b. Write to `.agent/.jules/journal/sentinel.md` + create PR.
5. If no issues: Write "no critical findings" in journal + stop.
6. Never create PR if there's no actionable improvement

---

## 📝 Journal Entry Template

```markdown
## [Date use YYYY-MM-DD format] - [Issue/Finding Title]

- **Issue/Opportunity:** Brief description
- **Root cause / Reason:** Why this matters
- **Action taken:** What was fixed/improved
- **Verification:** How it was tested
- **PR:** #42 (or "none" if no action needed)

Additional notes...

---

## 🌳 Branching & PRs

Jules follows **trunk-based development** with short-lived feature branches.

### Naming Convention
- `feat/*` – New features
- `fix/*` – Bug fixes
- `chore/*` – Maintenance, docs, performance, tests, etc.
- `docs/*` – Documentation only

**Optional scope prefix:** Use `web/` or `core/` for targeted changes (e.g. `web/feat/strategy-builder`).

### Guidelines
- **Obvious Tasks**: Use clear, descriptive branch names (e.g., `web/fix/header-z-index`).
- **Dubious/Complex Tasks**: Infer a logical branch name based on the core change.
- **Protected Main**: Never commit directly to `main`. All changes require a PR.

### PR Labels
Always suggest or apply relevant labels when creating PRs:
- **Type**: `feature`, `bug`, `chore`, `docs`, `perf`, `refactor`, `test`
- **Scope**: `core`, `web`, `api`, `db`
- **Priority**: `high-priority`, `med-priority`, `low-priority`
```

---

## 🚫 What NOT to Do

❌ Create a new journal entry for every scheduled task run (only critical findings)
❌ Log routine checks with "no findings" as separate files (write inline or skip)
❌ Ignore anti-patterns in task recommendations
❌ Create PRs for non-critical improvements
❌ Mix task execution instructions in task reference docs
❌ Update scheduled task reference docs frequently (only on major changes)

---

## Resources

- **Antigravity Docs:** https://antigravity.google/docs/
  - Skills: https://antigravity.google/docs/skills
  - Rules & Workflows: https://antigravity.google/docs/rules-workflows
- **Setup guide:** `docs/startup.md`
- **API reference:** `docs/api_contract.md`
- **Project agents:** `AGENTS.md`
