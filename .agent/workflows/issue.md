---
description: Diagnose, validate, and create high-quality GitHub issues.
---

# /issue — Create GitHub Issue

1. **Diagnose** the problem:
   - Reproduce the issue with a minimal test case.
   - Identify root cause and affected files.

2. **Fetch context** (if referencing existing issues):
   ```
   & "C:\Program Files\Git\bin\bash.exe" ./.agent/scripts/github/get_issue_details.sh <ISSUE_NUM>
   ```

3. **Draft issue** with:
   - **Title**: Clear, concise problem statement.
   - **Labels**: `bug`, `feature`, `refactor`, `chore`.
   - **Body**: Problem description, expected behavior, reproduction steps.
   - **Task checklist**: Specific implementation steps.

4. **Link** related issues and PRs.

> References: GitHub scripts in `.agent/scripts/github/`
