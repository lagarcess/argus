---
description: Testing and TDD constraints (Model Decision - Trigger on any task modifying tests/**/*.py)
---

# TDD & Testing Rules

You are editing the test suite. This project strictly follows Test-Driven Development (TDD) via the `/tdd` workflow.

## 1. Refactoring Requires New Tests
- **Rule**: If you extract logic from a massive file (like `main.py`) into a new class or module, you **MUST** create a dedicated unit test file for that new class (e.g., `tests/engine/test_new_class.py`). Do not rely on the existing integration tests in `test_main.py` to cover the newly decoupled unit.

## 2. Never Bypass Failing Tests
- **Rule**: When running the `/fix` loop, if a test is failing, you must fix the *source code*, not loosen the test to make it pass (unless the test itself is fundamentally flawed based on new requirements).

## 3. Delegation of Mechanics
- **Rule**: Follow the strict testing mechanics (e.g., AAA pattern, factory generation, assertion helpers) defined in the `test-writer` skill to maintain suite quality.
