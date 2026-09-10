# Retire profiles.theme: evidence

Integration base `3ceada30`. Code under test `b089da93`.

## The spec

`web/e2e/profile-language-save.spec.ts` answers every `/me` itself under mock
auth. Its two theme cases open Appearance in a signed-in chat and pick the
theme the system does not prefer. They check that the page switched, that
`argus-theme` holds the choice, and that no `PATCH /me` was sent. After a
reload they check that the choice still applies and that still nothing was
sent. A request sent after the change proves the absence, because requests are
reported in the order they were sent.

| Case | `3ceada30`, app source untouched | `b089da93` |
| :--- | :--- | :--- |
| English account, system dark, picks Light | fails: `PATCH /me` sent with `{"theme": "light"}` | passes |
| Spanish account, system light, picks Oscuro | fails: `PATCH /me` sent with `{"theme": "dark"}` | passes |
| The six language cases from #581 | pass | pass |

At the base both theme cases got past the class and storage checks and failed
only on the request. Switching theme already worked in the browser; the
request was the only thing to remove.

- `red-at-3ceada30.txt`: the new backend, unit and browser tests run against
  the base.
- `green-at-b089da93.txt`: the browser run at the fix, with a clean tracked
  tree.

## Screenshots

Captured by the green run at `b089da93`, 1280x720, after the reload with
Appearance opened again.

- `en-theme-light-after-reload.png`: the system prefers dark. The page is
  light and Light is selected.
- `es-419-theme-dark-after-reload.png`: the system prefers light. The page is
  dark, in Spanish, and Oscuro is selected.

## Gates at `b089da93`

- `poetry run pytest` on the new and touched backend files, the OpenAPI
  compatibility test and the canon doc tests: 622 passed.
- `poetry run pytest tests -q --no-cov`: 6628 passed, 585 skipped, 3 failed.
  The three are a discovery composer language test, a graded interpretation
  routing test and a saved-decision proposal test, and this change touches
  none of them. They fail only with the canonical `.env` linked. In a worktree
  at `b089da93` with no `.env`, which is how CI runs, all three pass.
- `poetry run ruff check src tests workflows scripts`: passed.
- `cd web && bun test`: 1662 pass, 0 fail across 165 files.
- `cd web && bun run lint`: 0 errors. The 8 warnings are in
  `StrategyConfirmationCard.tsx` and `ChatSidebar.tsx`, which this lane does
  not touch.
- `cd web && bun run build`: compiled, TypeScript finished.
- `eslint` on every changed web file: clean.
- `scripts/check_modularity_budget.py`: no violations.
