---
description: TDD development loop — write test, implement, verify.
---

# /implement — Test-Driven Development

1. **Create branch**: `<type>/issue-<num>-<short-desc>` (e.g., `feat/issue-42-backtest-api`).

2. **Write failing test** (Red phase):
   - Create or update test file in `tests/`.
   - Test must fail with a clear assertion error.
   - Run: `poetry run pytest tests/<path> -v -x`

3. **Implement** (Green phase):
   - Write minimum code to make the test pass.
   - Follow patterns in `coding-standards` and `backend-patterns` skills.
   - If touching `analysis/`, read `numba-patterns` skill first.

4. **Refactor** (Refactor phase):
   - Clean up while keeping tests green.
   - Run full suite: `poetry run pytest tests/ -v`

5. **Lint check**: `poetry run ruff check .`

> References: `testing-patterns` skill, `coding-standards` skill
