# Browser pass at the reconciled head `803f6094` (PR #527 over `8bf55aeb`)

Captured 2026-08-23 against a local stack built from this worktree at
`803f6094`: real OpenRouter interpretation with the integration env's model
tiers, real Alpaca market data (`ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider`),
memory persistence, mock auth, canonical env sourced into the backend process
only. The rendered app was driven by a headed Playwright Chromium window so
the turns were watchable. `browser-pass.json` holds, per turn, the user
message, the full on-screen transcript, the screenshot name, and the facts
pulled from the SSE final frame. Every screenshot is a full-page capture of
what the user saw at that point.

The Claude Browser pane was tried first and abandoned: it reported
`document.visibilityState === "hidden"` for the whole session, painted the
page at a stale size, and stopped delivering clicks to the composer. The
headed window is the repo's proven path for this kind of evidence.

## Why this pass exists

The review round on this PR argued a live eval was owed because
`strategy.assumptions`, which the fix empties of its English strip, is
interpolated into the interpreter's prior-strategy system message on every
follow-up turn, and `approval_guard._MATERIAL_STRATEGY_FIELDS` includes
`assumptions`. The founder's decision: no eval, because no suite case
exercises a conversational approval after a card; a browser does. So this
pass drives exactly that path in both languages.

## What the user saw

**Conversational approval after a card, both languages.** "yes, run it" and
"sí, ejecútalo" each produced one assistant line and left the card
untouched:

- en: "The visible confirmation is still ready. Use the card to start the
  simulation, or use the card controls to change it."
- es-419: "La confirmación visible sigue lista. Usa la tarjeta para iniciar
  la simulación, o usa sus controles para cambiarla."

No re-ask, no re-interpretation, no second card. The stream final frame is
`ready_to_respond` with the typed `recovery.code = confirmation_action_guidance`;
the Spanish line is the bundle's rendering of that code.

This is the designed behaviour, not a regression, and it is untouched by the
PR: with a live confirmation card, both approval branches in
`stages/interpret_actions.py:700-750` return this guidance, because the card
is the sole owner of quota-bearing execution (the #437 run-consumption
design; `tests/agent_runtime/test_confirmation_liveness.py::test_live_confirmation_still_gets_guidance`
pins it, and the branch dates from #183). The guard's only live effect here
is guidance versus falling through to re-drafting: a material-patch verdict
on the approval would have produced a new card or a clarifying question. It
produced guidance in all four approval turns (two per language, one of them
after an edit had changed the prior-strategy context), so the changed
`assumptions` did not make the guard misread an approval.

**The card then runs, both languages.** Clicking the card's "Run backtest" /
"Ejecutar backtest" after the text approval completed a real simulation on
Alpaca data: `$20,020`, `+$10,020 gain · +100.2% total return`, `Compared
with SPY: Beat by 46.4 percentage points`, `Worst drop -16.8%`; in Spanish
`+$10,020 ganancia · +100.2% rendimiento total`, `Comparado con SPY: Superó
por 46.4 puntos porcentuales`, `Peor caída -16.8%`, with a Spanish Lectura
rápida. Those are the real AAPL and SPY returns for 2023 through 2024, which
fixtures could not produce.

**An edit after the card exists, both languages.** "Change the benchmark to
QQQ" / "Cambia el benchmark a QQQ" on a live card produced a fresh card with
"Benchmark: QQQ" / "Referencia: QQQ", the prior card marked "Updated", and
(in Spanish) the line "Cambiando el benchmark a QQQ." The final frame is a
new `await_approval` with `confirmation_payload.strategy.comparison_baseline`
and `launch_payload.benchmark_symbol` both `QQQ`. This is the turn the
interpreter sees the emptied `assumptions` in its prior-strategy context and
must not treat as a pure approval; it did not.

**The plain case.** The Spanish workspace card is fully Spanish on screen:
"Comprar y mantener / Listo para ejecutar / CAPITAL INICIAL / PERIODO / 3 ene
2023 → 31 dic 2024 / Acciones / Datos diarios / Sin comisiones / Sin
deslizamiento / Referencia: SPY / Editar capital / Editar fechas / Editar
costos / Ejecutar backtest / Cambiar supuestos / Cancelar". Every
confirmation frame in both languages carries
`confirmation_payload.strategy.assumptions: []`, and the Spanish frames carry
`launch_payload.language: es-419`. The deleted strip's strings ("No fees",
"No slippage", "1D bars", "Daily data") occur zero times anywhere in the
Spanish final frame.

## English still in the Spanish stream, all known and out of scope here

Counted in the Spanish final frame, none of it painted where the card shows
Spanish, each already tracked:

- `card.title` ("AAPL buy and hold"), `card.statusLabel` ("Ready to run"),
  `card.rows[].value` ("Buy and Hold"), `card.actions[].label` ("Run
  backtest"): persisted-compat English beside the typed keys the frontend
  localizes from (#523's seam, documented on `_confirmation_summary`).
- `card.summary` ("Ready to test buy-and-hold for AAPL over 3 de enero de
  2023 al 31 de diciembre de 2024."): reaches readers only through
  `last_message_preview`, #528.
- `card.assumptions` (`["$10,000 starting capital", "Datos diarios",
  "Benchmark: SPY"]`): the Spanglish strip the assumptions answer quotes,
  #530.
- `assistant_response` on the approval turns is the English compat text for
  the typed recovery code; the screen rendered the Spanish bundle copy.

## Observation outside this lane, not acted on

The result card states the benchmark gap from the typed magnitude (46.4
points) while the LLM Quick Take subtracts the rounded returns (100.2 minus
53.9, 46.3). Both languages. A prose-versus-typed disagreement on the result
surface, the judge lane's territory, noted for the founder.

## Head

Runtime and frontend trees at this head differ from the previous capture
head only by the integration merge; the PR's own delta is unchanged
(`git diff 8bf55aeb 803f6094 --stat` is the same nine files as before the
reconcile). Deterministic gates at `803f6094`: backend 5660 passed, 523
skipped, the `mem0` module deselected for the worktree venv (green in CI).
