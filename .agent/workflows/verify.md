---
description: Run the ownership gate, full test suite, linting, and type checking.
---

# /verify - Full Verification

// turbo-all

1. Run branch ownership gate:
   ```
   python .agent/scripts/ownership/verify_branch_ownership.py
   ```

2. Run linter:
   ```
   poetry run ruff check .
   ```

3. Run full test suite with coverage:
   ```
   poetry run pytest tests/ -v --cov=src/argus --cov-report=term-missing
   ```

4. Verify no local environment files are about to be committed:
   ```bash
   git ls-files "**/.env*" ":(exclude)**/*.env.example" 2>/dev/null | grep -q . && echo "SECRETS IN GIT" || echo "Clean"
   ```

5. Report results: pass/fail for each step + coverage percentage.
