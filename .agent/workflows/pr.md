---
description: Create a comprehensive Pull Request from current changes
---

1. **Final Verification**
   - Execute the `/verify` workflow.
   - **VERIFICATION SCOPE**: The workflow will run and capture:
     - Full test suite execution (pass/fail count)
     - Pre-commit hook execution (all hooks, with specific violations if any)
     - Type checking and linting (mypy (fix all), ruff - both checks and format)
   - **DECISION LOGIC**:
     - ✅ **All checks PASS**: Proceed to step 2 (Security & Privacy Scan)
     - ⚠️ **Pre-commit hooks FAIL**: Fix immediately and re-run `/verify` (repeat until pass)
     - ❌ **Test failures**: Run `/fix` workflow for self-correction, then re-run `/verify`
   - **REPORT OUTPUT**: Display all test/lint/hook results before proceeding

2. **Security & Privacy Scan**
   // turbo
   - **Secret Scan**: Scan the `git diff` for potential leaks (High Entropy strings, "BEGIN PRIVATE KEY", "ghp\_", etc.).
   - **PII Scan**: Ensure no personal data (names, IPs) from local logs was accidentally committed.
   - **Env Check**: Verify that NO changes to `.env` or `secrets/` are included in the commit.
   - If leaks found -> **STOP** and warn user.

3. **Knowledge Capture**
   - Execute the `/learn` workflow to extract and save lessons from this session.

4. **Documentation & Knowledge Base Update**
   - Review `README.md`, `DEPLOYMENT.md`, and any files in `docs/`.
   - Update them to reflect:
     - New features or changed functionality.
     - Critical system behavior changes.
     - New configuration requirements.
   - **Privacy Check**: Ensure no sensitive internal logs or secrets are exposed in public docs.
   - **Auto-Sync**: Run `poetry run sync-docs` to regenerate Handbook and DBML from the latest schema.
   - Commit these documentation changes.

5. **PR Documentation Generation**
   - Ensure directory exists: `if (!(Test-Path "temp/pr")) { New-Item -ItemType Directory -Path "temp/pr" -Force }`
   - analyze the git diff and `temp/plan/implementation-plan.md`.
   - generate a PR Title and Description following this template:
   - Save to `temp/pr/description.md` (gitignored). DO NOT commit this file.

     ```markdown
     ## Problem

     Fixes #[Issue Number]
     [Description of the problem this PR solves]

     ## Solution

     [High-level technical approach]
     [Key architectural decisions]

     ## Changes

     - [File/Component]: [Change description]
     - [File/Component]: [Change description]

     ## Verification

     - [ ] Unit Tests passed
     - [ ] System checks passed
     - [ ] Manual verification step (if any)
     ```

6. **Branch & Push**
   // turbo
   - Create a new branch (if not already on one): `git checkout -b feat/issue-number-description`
   - Push changes: `git push origin HEAD`

7. **Submission**
   - **Enforce SemVer Rule**: Strictly follow the guidelines defined in `.agent/rules/conventional-commits.md` for constructing the PR title and inferring Labels based on the original branch prefix.
   - Output the PR command for the user (referencing the temp file):
     - `gh pr create --title "<type>(<scope>): <description>" --body-file temp/pr/description.md --label "[inferred-label]"`
   - **Optional**: Ask user if they want to add specialized reviewers.
