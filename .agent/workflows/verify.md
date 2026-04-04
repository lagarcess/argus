---
description: strict code review, system verification, and auto-commit
---

**Setup**: Ensure directory exists: `if (!(Test-Path "temp/verify")) { New-Item -ItemType Directory -Path "temp/verify" -Force }`

1. **System Health & Regression Check**
   // turbo
   - **CRITICAL**: Run the **FULL** test suite AND generate coverage: `$env:COVERAGE_FILE="temp/coverage/.coverage"; poetry run pytest --cov=src --cov-report=html:temp/coverage/html --cov-report=xml:temp/coverage/coverage.xml`
   - *Note*: Always run the full suite at the end to check for overall coverage and regressions, as per `.agent/rules/pytest-guide.md`.
   - **Regression Trap**: Check if the total number of passed tests equals the baseline expectation. If tests fail that previously passed -> **REGRESSION DETECTED**.
   - **Coverage Check**: Ensure coverage meets threshold (63%, ideally higher).
   - **Type Checking**: Run type checking (if applicable): `poetry run mypy src`
   - **Smoke Test**: Run smoke test (Main Flow check): `python -m src.crypto_signals.main --smoke-test`
   - **Doc Parity**: Verify root-vs-wiki synchronization: `poetry run sync-docs --check`
   - **On Failure**: Automatically trigger the `/fix` workflow to attempt self-correction. Do NOT blindly change broken tests to make them pass.

2. **Local CD Pre-Flight (Docker)**
   - ⚠️ **CURRENTLY FLAGGED AS BROKEN**: Do not enforce this step to block PRs until the Docker environment bug is resolved. You can still run `/preflight` manually to diagnose it, but skip it in the automated verify pipeline for now.

3. **Deep Agent Review**
   - Review the `git diff` of pending changes.
   - Act as a "Senior Engineer" verifyer:
     - **Gap Analysis**: Are there missing edge cases?
     - **Security**: Potentially unsafe operations?
     - **Scalability**: Any O(N^2) loops or heavy sync operations in async paths?
   - If issues are found, **fix them immediately** (do not ask, just fix, unless it requires design change).

4. **Pre-Commit Hook Execution & Resolution**
   - **Branch Guard**: Ensure we aren't on `main`.
   - Attempt to commit: `git add . && git commit -m "feat: [description]"`
   - **CAPTURE OUTPUT**: Save full pre-commit hook output.
   - **If ALL hooks pass**: Proceed to Success.
   - **If hooks fail**: Identify if auto-fixable (ruff format) or manual (logic). Run `/fix` for manual. Retry max 3 times.

5. **Final Success**
   - If commit succeeds, output: "✅ Verification passed, no regressions found, and code committed."
