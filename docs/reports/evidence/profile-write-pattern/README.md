# One profile write path: evidence

Integration base `542fcfb2`. Code under test `0d86cc95`: the lane, the Codex
round 1 fix `8f3f2ddf`, and integration `802fdfb3` merged in.

## The spec

`web/e2e/profile-language-save.spec.ts` answers every `/me` itself under mock
auth, so a refused save is chosen rather than waited for.

| Case | `542fcfb2`, app source untouched | Before round 1 | `0d86cc95` |
| :--- | :--- | :--- | :--- |
| Refused save, English account picks Español | fails: no alert | passes at `167ae5a0` | passes |
| Refused save, Spanish account picks English | fails: no alert | passes at `167ae5a0` | passes |
| A save the account took is kept when its reply fails | not written yet | fails at `2308dbe1`: refusal shown | passes |
| Saved language survives a reload | passes | passes at `167ae5a0` | passes |
| A late save cannot close the panel that replaced it | passes | passes at `167ae5a0` | passes |
| Front door writes no profile | fails: `PATCH /me` sent | passes at `167ae5a0` | passes |

- `red-at-542fcfb2.txt`: the run against the base.
- `green-at-167ae5a0.txt`: the run before review round 1.
- `review-round-1-red-at-2308dbe1.txt`: the round 1 tests, unit and browser,
  run against the unfixed write path.
- `green-at-0d86cc95.txt`: the current run, with a clean tracked tree.

The late-save case passes at the base because the old modal closed before it
saved. To show it guards the new modal, it was run at `167ae5a0` with
`if (session !== editSessionRef.current) return;` removed from
`LanguageModal.tsx`: it failed at `expect(appearance).toBeVisible()`, because
the late success closed the Appearance panel. The line was restored before
the green run.

## Screenshots

Captured by the green run at `0d86cc95`, 1280x720.

- `en-refused-save.png`: an English account tried Español. The panel stays
  open in English, English stays checked, and "Could not update language yet."
  shows above the list.
- `es-419-refused-save.png`: a Spanish account tried English. The panel stays
  in Spanish, Español stays checked, and "No pudimos actualizar el idioma
  todavía." shows above the list.
- `en-saved-as-es-419.png`: a save the account took. The panel closed and the
  chat renders in Spanish.
- `en-kept-after-failed-reply.png`: the account took Español but its reply
  failed. The account was asked, the save was kept, and the chat renders in
  Spanish with no refusal.

## Gates at `0d86cc95`

- `cd web && bun test`: 1662 pass, 0 fail across 165 files. Before round 1,
  `62b58d1f` on its own: 1653 pass, 0 fail across 164 files.
- `cd web && bun run build`: compiled, TypeScript finished.
- `eslint` on every changed file: clean.
- `scripts/check_modularity_budget.py`: no violations. `ProfileMenu.tsx` went
  from 1453 to 1395 lines and `ChatInterface.tsx` from 2592 to 2573.
