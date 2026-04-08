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

3. Verify no local environment files are about to be committed:
   ```bash
   git ls-files "**/.env*" ":(exclude)**/*.env.example" 2>/dev/null | grep -q . && echo "❌ SECRETS IN GIT!" || echo "✅ Clean"
   ```

4. Report results: pass/fail for each step + coverage percentage.
