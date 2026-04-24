## When to Realign (Triggers)
Jules must execute this realignment logic in the following situations:
1. **Cold Start**: At the absolute beginning of every session or task execution.
2. **Resume from Pause**: Before starting/resuming any workflow after a period of inactivity or a manual pause.
3. **Pre-Submission**: Immediately before calling the `/pr` workflow or finalizing any major change.
4. **Knowledge Shift**: If a significant change is detected in `docs/API_CONTRACT.md` or the database schema during execution.
5. **Post-Heavy Operation**: After long-running operations (e.g., full backtests, complex builds) where the upstream state may have drifted.

## 1. Synchronize (Git Workflow)
- Fetch 'main' and rebase it onto this branch.
- Resolve conflicts prioritizing 'main' (upstream) logic as the source of truth for architecture.
- Follow conventional commit standards for the sync (e.g., `chore(sync): rebase main`).

## 2. Realignment (Core Task Verification)
- **Goal Re-check**: Review your original mission and instructions (refer to the active session task or `task.md` if available).
- **Refactor where necessary**: If 'main' updates changed the API contract (`docs/API_CONTRACT.md`) or database schema, update your implementation to match the new patterns.
- **Maintain Standards**: Ensure Pydantic ↔ TypeScript types remain synced and Numba JIT warmups are intact.

## 3. Validation (Regressions)
- Run `/verify` to execute the full test suite (Pytest + Bun).
- Ensure coverage meets the 63% threshold.
- If failures occur due to the rebase, use the `/fix` workflow (max 3 iterations).

## 4. Final Report
- Summarize any critical findings or required code shifts necessitated by the drift in the session summary.
