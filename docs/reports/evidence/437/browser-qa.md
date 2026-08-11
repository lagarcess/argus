# Flag-on browser QA, issue #437

In-place card editing surface exercised with
`ARGUS_IN_PLACE_CARD_EDITS_ENABLED=true` against the local dev stack
(mock auth, in-memory persistence, synthetic market data, real LLM
interpretation, shadow jobs off), captured with the committed
`qa-driver.mjs` at real viewports and read against rendered text before
being trusted. Backend and frontend served from this lane's worktree.

Recaptured in full at `d5294518` after the review rounds changed the
result-link and withheld-cleanup runtime (`f3e51c53`, `69e20979`,
`d5294518`), replacing the original `cb7dd3bc` capture. All four cells
were produced by one run of the committed driver with its default cell
set. Later commits are re-validated against the exercised journeys
rather than blanket-trusted: `eaa31ce2`, `a9e97268`, and `b43b885b`
change only the refused-link and worker cleanup paths, which no frame
exercises (the captured journeys run with shadow jobs off and never
enter the worker) and the refusal unit and worker tests prove, and
evidence-record edits carry no runtime. Any future commit that moves an
exercised path requires a fresh capture.

## Matrix

| Cell | Viewport | What the frames show |
| --- | --- | --- |
| `desktop-en` | 1280x800 | Card with Edit capital / Edit dates / Edit costs pills; capital drawer open in flow with the action row still visible; capital applied ($10,000 to $25,000) with no turn spent; dates drawer open; start date applied (2025 to 2024); Cancel leaves a dead "Draft canceled" card with pills and actions removed; a fresh idea mints a new editable card; Run backtest publishes the result card with quick take and try next |
| `desktop-es` | 1280x800 | Same full journey in es-419: Editar capital / Editar fechas / Editar costos, Listo para ejecutar, Ejecutar backtest, Cambiar supuestos, Cancelar, LECTURA RAPIDA and QUE PROBAR DESPUES on the run result |
| `phone-en` | 375x812 | Card at phone width with wrapped pill rows; both drawers expand downward in normal flow inside the card and the card's own actions stay below the drawer (no takeover, no clipping); both edits applied |
| `phone-es` | 375x812 | Same drawer behavior localized; period line proves the dates edit applied (11 ago 2025 to 11 ago 2024 start) |

## What this verifies

- Direct capital and date edits spend no turn, append no message, and
  rewrite the card in place (transcript still holds one user message and
  one card through both edits).
- One disclosure idiom at every width: the drawer pushes card content
  down and closing rolls it back; the card survives its own drawer
  (amendment 3.4b).
- A cancelled card is dead: pills and actions are removed and no
  non-turn entry point remains.
- Cancel, edit, run again works end to end in both languages: after
  cancelling, a fresh card is editable and runnable, and its result
  publishes normally through the gated link path.
- No em dashes in the exercised static surfaces in either language.

## Side observations (outside this lane's diff, filed separately)

- With shadow jobs off, in-process runs never stamp the card; filed as
  #439 with the reachable drift interleaving.
- After a cancelled draft whose dates were edited in place, a follow-up
  "run that idea again for the last six months" produced a card that
  kept the drawer-edited 2024-2026 period with no disclosure that the
  six-month request was not applied (silent-drop class, conversational
  path).
