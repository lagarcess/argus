---
description: Run the full test suite, linting, and type checking.
---

# /verify — Full Verification

// turbo-all

1. Run linter:
   ```
   poetry run ruff check .
   ```

2. Run full test suite with coverage:
   ```
   poetry run pytest tests/ -v --cov=src/argus --cov-report=term-missing
   ```

3. Verify no legacy references:
   ```
   grep -r "crypto_signals" src/ tests/ --include="*.py"
   ```

4. Report results: pass/fail for each step + coverage percentage.
