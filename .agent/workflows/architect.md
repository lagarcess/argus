---
description: Analyze monoliths, map dependencies, and draft extraction strategies
---

**Context**: Use this workflow when a single file has grown too large (e.g., `main.py` > 1000 lines or > 50KB) and is becoming a bottleneck for AI modifications.

1. **Structural Analysis**
   // turbo
   - Count the lines in the target file: `Get-Content [target_file] | Measure-Object -Line`
   - Run a symbol extraction to see all classes and functions: `poetry run python -c "import ast; print('\n'.join([node.name for node in ast.walk(ast.parse(open('[target_file]').read())) if isinstance(node, (ast.FunctionDef, ast.ClassDef))]))"`

2. **Dependency Mapping**
   - Identify which sections of the file belong to `domain`, `engine`, `repository`, or `market`.
   - Look for "God Classes" or functions that do 4+ different things.

3. **Draft the Extraction Plan**
   - Create `temp/plan/extraction-plan.md`.
   - Define the new Target Modules (e.g., "Extract lines 100-300 to `src/crypto_signals/engine/initializer.py`").
   - Define the testing strategy (What new test files need to be created?).

4. **Review & Handover**
   - Present `temp/plan/extraction-plan.md` to the user via `/notify_user`.
   - Do **NOT** execute the code moves until the user explicitly approves the architecture plan.
   - Once approved, proceed to `/implement`.
