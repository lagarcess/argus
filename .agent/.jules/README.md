# Jules – AI Agent Reference & Journal

This directory contains reference documentation and mandatory logic for the Jules autonomous scheduling framework.

---

## 📚 Structure

### `.agent/.jules/realignment.md`

**Mandatory Rule**: This file defines the "Branch Sync & Goal Realignment" logic. Every Jules session must execute these steps (rebase main, re-verify mission, validate regressions) before concluding.

---
**Key principles:**
- **Goal Realignment**: Jules must always stay aligned with the `main` branch and the original mission.
- **Shared Skills**: Jules uses the global repository at `.agent/skills/`.
- **Quarantine**: Scheduled task definitions and journals are maintained in the root `temp/` folder for manual review.

---

## 📅 Maintenance Protocol

| Step              | Action                                  | Rationale                               |
| ----------------- | --------------------------------------- | --------------------------------------- |
| **Sync**          | `git fetch origin main && git rebase`  | Prevent architectural drift             |
| **Realignment**   | Re-check mission vs API contract        | Ensure functional integrity             |
| **Verify**        | Run `/verify` workflow                  | Maintain 63% coverage and <3s latency   |

---

## 🧠 What are Skills?

Jules draws from the **global Argus skills** located in `.agent/skills/`.

**Autonomous Selection**: Jules is authorized to proactively select and apply *any* relevant skill from the global library `.agent/skills/` based on the context of the task, ensuring best practices are maintained without explicit instruction.

**Core available skills:**
- `coding-standards/`
- `numba-patterns/`
- `backend-patterns/`
- `testing-patterns/`
- `frontend-patterns/`
- `security-review/`
- `supabase/`
- `stitch-loop/`

---

## 🔄 Rules & Workflows

Jules follows the project-wide rules in `.agent/rules/` and workflows in `.agent/workflows/`. Specifically, it must always check against `realignment.md` in this directory.

---

## 📖 Documentation References

- **API contract:** `docs/api/api_contract.md`
- **Master Registry:** `AGENTS.md` (overall agent structure, skills, rules)

---

## 📝 Realignment Checklist (Mandatory)

1. **Synchronize**: Force rebase of `main`, prioritize upstream.
2. **Realignment**: Re-verify mission against current `docs/api/api_contract.md`.
3. **Validation**: Enforce `/verify` and iterate failures with `/fix`.
4. **Reporting**: Summarize shifts necessitated by drift.

---

## 🚫 Anti-Patterns

- ❌ Ignore `main` branch updates during long-running tasks.
- ❌ Proceed with stale mission goals after API contract shifts.
- ❌ Skip `/verify` before declaring a task complete.
- ❌ Create new localized skills (always use `.agent/skills/`).

---

## Resources

- **Antigravity Docs:** https://antigravity.google/docs/
- **API reference:** `docs/api/api_contract.md`
- **Project agents:** `AGENTS.md`
