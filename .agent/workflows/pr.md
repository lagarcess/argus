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

3. **Branch naming**: `<type>/issue-<num>-<short-desc>`
   - Types: `feat`, `fix`, `refactor`, `chore`, `docs`

4. **Commit message format** (conventional commits):
   ```
   <type>: <description> (#<issue>)

   - Specific change 1
   - Specific change 2
   ```

> References: `git-workflow` rule
