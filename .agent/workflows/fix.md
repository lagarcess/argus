---
description: Universal TDD and self-correction loop for test failures
---

1. **Test Identification & Execution Loop**
   // turbo
   - Identify the specific test file you are working on, or read the output of the failed test/lint command globally.
   - Run the specific test using poetry (e.g., `poetry run pytest tests/path/to/test_file.py --no-cov`).
   - *Note*: Always refer to `.agent/rules/pytest-guide.md` for proper command formatting (e.g. using `--no-cov` for test subsets, outputting debug info to `temp/test_results/`).

2. **Self-Correction (Max 3 Attempts)**
   // turbo
   - **Attempt 1**:
     - Read the source code causing the error. Fix it based on the failure output.
     - Re-run the specific failing test.
     - If PASS -> Stop and Report Success.
   - **Attempt 2 (if 1 fails)**:
     - Read the new error message (did it change?).
     - Check `docs/development/knowledge-base.md` for similar past issues.
     - Apply a different fix.
     - Re-run the test.
     - If PASS -> Stop.
   - **Attempt 3 (if 2 fails)**:
     - Re-read the `temp/plan/implementation-plan.md` to ensure we aren't violating the design.
     - Try a fundamental correction.
     - Re-run the test.

3. **Escalation**
   - If Attempt 3 fails:
     - **STOP**.
     - Report: "Unable to auto-fix. Manual intervention required."
     - Show the last error log.
