# Browser QA for #508 and #523 (confirm-stage English prose)

Captured 2026-08-21 at the fix head, real backend and real web app, both
workspace languages, memory persistence, synthetic market-data fixtures,
real OpenRouter interpretation. `browser-qa.json` holds the captures.

## What each capture proves

**#508 is fixed.** `confirmation_payload.strategy.assumptions` is `[]` on
both the English and the Spanish turn, in the live SSE final frame and in
the persisted message. Before the fix the confirm stage overwrote that
field with its own English strip; the guard
`test_confirm_stage_does_not_fabricate_english_assumption_prose` fails on
the base `stages/confirm.py` and passes at this head, which is the
executable before/after proof.

**The card did not change.** The Spanish card on screen is fully Spanish
("Comprar y mantener", "Listo para ejecutar", "Sin comisiones",
"Sin deslizamiento", "Referencia: SPY"), rendered from the typed fields
(`status`, `strategy_type`, `rows[].key`, `display_facts`). The card's own
`assumptions` strip and `display_facts` are byte-identical in role to the
pre-fix capture in `docs/reports/evidence/434-489-482/browser-qa.json`.

**The assumptions capability answer still works.** Asked on the pending
Spanish confirmation, it now quotes the card strip from the confirmation
reference metadata instead of the deleted confirm-stage strip, so the
answer matches what the card shows. Its own English scaffold lives in
`artifact_context.py` and is outside this lane's two targets.

**#523's premise is half wrong, recorded as found.** `summary` is not
dead: it is the persisted message content for every confirmation card turn
(`agent.py` persisted_text, `retest.py`, `apply_pending_card_update`), and
from there it becomes the conversation's `last_message_preview`, which the
recents list and the archived-chats views paint. The Spanish workspace's
recents subtitle on screen reads "Ready to test buy-and-hold for AAPL over
1 de enero de 2023 al 31 de diciembre de 2024.", an English scaffold
around a Spanish-formatted period. `title` paints only when a card has no
asset symbols; `statusLabel` is the i18n default value behind
`chat.confirmation.status.*` and a legacy status decode for old persisted
cards, so neither paints on current cards. The preview leak is filed as
its own issue; this lane's #523 fix removes the ignored `language`
parameters and documents the seam without changing what the card emits.
