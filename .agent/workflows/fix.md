---
description: Fix a failing test — read error, fix code, verify. Max 3 iterations.
---

# /fix — TDD Inner Loop

1. **Read** the failing test output carefully. Identify:
   - Which test failed and the assertion message.
   - The expected vs actual values.
   - The traceback and root cause.

2. **Fix** the code (not the test, unless the test itself is wrong).
   - Make the minimal change needed.
   - Follow `coding-standards` skill patterns.

3. **Verify**: `poetry run pytest tests/<failing_test> -v -x`

4. **Loop** up to 3 times. If still failing after 3 attempts:
   - Document what you tried.
   - Escalate by presenting findings.

> References: `testing-patterns` skill
