# One profile write path: evidence

Integration base `542fcfb2`. Code under test `167ae5a0`.

## The spec

`web/e2e/profile-language-save.spec.ts` answers every `/me` itself under mock
auth, so a refused save is chosen rather than waited for.

| Case | `542fcfb2`, app source untouched | `167ae5a0` |
| :--- | :--- | :--- |
| Refused save, English account picks Español | fails: no alert | passes |
| Refused save, Spanish account picks English | fails: no alert | passes |
| Front door writes no profile | fails: `PATCH /me` sent | passes |
| Saved language survives a reload | passes | passes |
| A late save cannot close the panel that replaced it | passes | passes |

- `red-at-542fcfb2.txt` is the run against the base.
- `green-at-167ae5a0.txt` is the run at the fix, with a clean tree.

The late-save case passes at the base because the old modal closed before it
saved. To show it guards the new modal, it was run at `167ae5a0` with
`if (session !== editSessionRef.current) return;` removed from
`LanguageModal.tsx`: it failed at `expect(appearance).toBeVisible()`, because
the late success closed the Appearance panel. The line was restored before
the green run.

## Screenshots

Captured by the green run at 1280x720.

- `en-refused-save.png`: an English account tried Español. The panel stays
  open in English, English stays checked, and "Could not update language yet."
  shows above the list.
- `es-419-refused-save.png`: a Spanish account tried English. The panel stays
  in Spanish, Español stays checked, and "No pudimos actualizar el idioma
  todavía." shows above the list.
- `en-saved-as-es-419.png`: a save the account took. The panel closed and the
  chat renders in Spanish.

## Gates on the tree committed as `167ae5a0`

- `cd web && bun test`: 1658 pass, 0 fail across 165 files. `62b58d1f` on its
  own: 1653 pass, 0 fail across 164 files.
- `cd web && bun run build`: compiled, TypeScript finished.
- `eslint` on every changed file: clean.
- `scripts/check_modularity_budget.py`: no violations. `ProfileMenu.tsx` went
  from 1453 to 1395 lines and `ChatInterface.tsx` from 2592 to 2573.
