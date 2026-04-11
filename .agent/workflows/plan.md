---
description: Generate an implementation plan before making changes.
---

# /plan — Implementation Planning

1. **Research** the task fully before proposing changes.
   - Read all relevant source files referenced in the issue/request.
   - Check `tests/` for existing coverage of the affected code.
   - Review `.agent/skills/` for applicable patterns.

2. **Create** `temp/plan/implementation-plan.md` with:
   - Problem summary and affected files.
   - Proposed changes (grouped by component).
   - Test plan (what tests to write/modify).
   - Risk assessment (breaking changes, performance impact).

3. **Present** the plan for review. Do NOT start coding until approved.

> References: `coding-standards` skill, `testing-patterns` skill
