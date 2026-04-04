---
description: AI code review with security and quality checks.
---

# /review — Code Review

1. **Diff scan**: Review all changed files in the current branch.
   ```
   git diff main --stat
   git diff main
   ```

2. **Quality checks** (for each changed file):
   - [ ] Type hints on all function signatures?
   - [ ] `loguru` used (no `print`)?
   - [ ] Tests added/updated for new behavior?
   - [ ] Error handling with specific exceptions?
   - [ ] No hardcoded secrets or credentials?

3. **Security scan** (reference `security-review` skill):
   - [ ] No secrets in source code or git history?
   - [ ] Input validation on any new data entry points?
   - [ ] No overly broad exception handling (`except Exception`)?

4. **Performance check** (if touching `analysis/`):
   - [ ] JIT warmup called in new tests?
   - [ ] No Python objects inside `@njit` functions?
   - [ ] Benchmarks still within targets?

5. **Summarize** findings as: APPROVE, REQUEST_CHANGES, or NEEDS_DISCUSSION.

> References: `coding-standards` skill, `security-review` skill, `numba-patterns` skill
