---
description: TDD-first, 63% coverage target, pytest best practices.
globs: ["tests/**/*.py"]
---

# Testing Rule

1. **TDD-first**: Write a failing test before fixing any bug.
2. **Coverage target**: 63% minimum. Focus on analysis logic.
3. Use plain `assert` and `pytest.approx()` for floats.
4. Name tests descriptively: `test_<behavior>`.
5. Use `conftest.py` for shared fixtures.
6. Call `warmup_jit()` before any Numba performance tests.

See: `.agent/skills/testing-patterns/SKILL.md` for full details.
