---
description: Resolve upstream conflicts, rebase, and verify infrastructure integrity before PR review.
---

**Context**: As the team scales to parallel agents (Human, Antigravity, Jules), feature branches quickly fall behind `main`. Automated bot-merges (like Jules running `git pull`) often silently squash or reject infrastructure updates (e.g., changes to `.github/workflows/deploy.yml` made by someone else). This workflow safely synchronizes the local branch with `main` explicitly protecting infrastructure files.

1.  **Fetch & Assess Git Tree**
    // turbo
    - `git fetch origin`
    - Check the distance behind main: `git log --oneline HEAD..origin/main`
    - If behind, proceed to Git Sync. If up-to-date, proceed straight to `/review`.

2.  **Infrastructure Pre-Check**
    - Diff `origin/main` against the feature branch *specifically* for infrastructure files:
      `git diff origin/main...HEAD -- .github/ .agent/ pyproject.toml poetry.lock`
    - **Identify**: Are there files altered in `main` that Jules (or the current branch) also touched or silently reverted?

3.  **Strict Rebase (Preferred) or Supervised Merge**
    - Instead of a blind `git pull` merge, attempt a rebase: `git rebase origin/main`.
    - Rebasing ensures that our branch applies its changes *on top* of the current infrastructure, dramatically reducing the chance of a "silent overwrite" of a teammate's previous work.
    - If conflicts occur, pause the workflow and **ask the Human** for guidance or use the GitHub MCP to examine conflict markers.
    - **CRITICAL**: If an infrastructure file conflicts, the `origin/main` (theirs) version is ALMOST ALWAYS correct unless the explicit goal of the PR is to change that infrastructure file.

4.  **Verify Integrity & Handoff**
    - Once synced, run a quick `git status` and a targeted `git diff origin/main...HEAD` to verify the resulting diff only contains the *intended* feature work, not reverted infrastructure.
    - Proceed to `/verify` (specifically the Pytest/Mypy suite) to ensure the newly synced upstream code hasn't broken the local feature.
    - Output: "✅ Branch synced successfully. Safe to proceed with `/review`."
