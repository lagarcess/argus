---
description: Create a comprehensive pull request from current changes.
---

# /pr — Pull Request

1. **Verify** all checks pass first (run `/verify`).

2. **Generate PR body** with:
   - **Title**: `<type>: <description> (#<issue>)` (e.g., `feat: add backtest API endpoint (#42)`)
   - **Summary**: What changed and why.
   - **Changes**: List of modified files grouped by component.
   - **Testing**: What tests were added/modified.
   - **Screenshots**: If UI changes (link to capture).
   - **Labels**: Select relevant labels (e.g. `feature`, `core`).

3. **Branch naming**: `[scope/]<type>/*` (e.g. `feat/strategy-builder` or `web/fix/header`)
   - Types: `feat`, `fix`, `chore`, `docs`

4. **Commit message format** (conventional commits):
   ```
   <type>: <description> (#<issue>)

   - Specific change 1
   - Specific change 2
   ```

> References: `git-workflow` rule
