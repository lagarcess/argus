# Confirmation card summary prose

## The defect

At integration `736dfd03`, `_confirmation_summary` in
`src/argus/api/chat/confirmation.py` built every card's `summary` as English
scaffolding around a language-formatted period. A Spanish workspace persisted,
for the three shapes seeded in `before/`:

- `Ready to test buy-and-hold for AAPL over 2 de enero de 2024 al 31 de diciembre de 2024.`
- `Ready to test recurring buys for AAPL over 2 de enero de 2024 al 31 de diciembre de 2024.`
- `Ready to test TSLA with an RSI threshold over 2 de enero de 2024 al 31 de diciembre de 2024.`

It painted nowhere on screen: PR #116 removed it from the card, and PR #551
made Recents and Search previews typed. It still reached four readers:

- Model thread history (`before/thread-history.json`), which the clarifier,
  the DCA audits and the discovery read send to the model on follow-up turns,
  and the interpreter sends when no artifact context is present.
- Artifact naming, through the same history and the latest assistant line.
- The stored `last_message_preview` that conversation search indexes.
- The `/messages` transport, as the card turn's `content` and as
  `confirmation_card.summary` (`before/messages-930*.json`).

## The fix

Decision for this lane: delete the sentence; artifact naming and the search
index read the card's typed facts; model history receives the confirmation's
typed facts instead of prose; no live eval in this lane.

- `07c14964` deletes the sentence. Card turns persist empty content on the chat
  route, the retest path and in-place edits. `argus.domain.confirmation_turn_facts`
  derives strategy type, symbols and dates; thread history, naming and the
  stored preview read them. The four preview writers share
  `stored_message_preview`. The reader boundary blanks content and drops
  `summary` on legacy card turns.
- `43d971ea` removes the field from the web card type, fixtures and e2e mocks.
- `0d57492a` updates `API_CONTRACT.md`, `DATA_MODEL.md` and
  `CONVERSATIONAL_RUNTIME.md`.
- `d226ba1f` moves two existing tests off the retired sentence.
- `196b9e84` reconciles integration `231184bb` one way (no overlapping files).
- `57c34585` answers Codex round 1: each fact has one owner and no fallback.
  The card owns `strategy_type` and dates, the payload owns only the symbol
  list, and a legacy card missing a fact yields null.

## After, at `57c34585` with a clean tree

Headless Chromium against a memory-mode replay (`replay_confirmation_api.py`,
`capture_confirmation_evidence.mjs`), workspace `es-419`, zero provider calls,
zero hosted database reads or writes, zero console errors
(`after/capture-report.json`). The first capture ran at `0d57492a` and gave
the same results.

| Capture | What it shows |
| :--- | :--- |
| `es-buy-and-hold-card.png` | Spanish card; transport content `""`, no `summary`; no `Ready to test` in the DOM |
| `es-recurring-buys-card.png` | Same for a recurring plan |
| `es-rsi-threshold-card.png` | Same for an RSI threshold rule |
| `es-buy-and-hold-card-after-in-place-edit.png` | The real direct-edit endpoint rebuilt and persisted the card at $25,000; response content `""`, no `summary` |
| `es-legacy-card-turn.png` | A row stored the old way, sentence as content and `summary`; the reader transport returns content `""` and no `summary` |

`after/thread-history.json` records, for all four conversations including the
legacy row, the model history and naming input as
`{"confirmation_card":{"strategy_type":...,"symbols":[...],"date_range":{...}}}`
and the stored preview as, for example, `AAPL buy_and_hold 2024-01-02 2024-12-31`.
`after/conversations.json` and `after/search-aapl.json` show typed previews.

## Tests

`tests/test_confirmation_turn_prose.py` has 38 cases: seven shapes (buy and
hold, recurring buys, RSI threshold, dip buying, indicator threshold, signal
strategy, moving-average crossover) in `en` and `es-419` through the card
builder and the chat route, plus the in-place edit, a legacy row, and the
Supabase finalize and create preview writers in both languages. The first 36
failed on `736dfd03`. `test_card_turn_readers_only_see_facts_the_card_carries`
fails on `01bcfed` (the legacy card got the payload's `dca_accumulation` and
2024 dates) and passes at `57c34585`.

## Limits

- Rows written before this change keep the English sentence in
  `conversations.last_message_preview` until the conversation's next message.
  No backfill migration; readers never receive that column. In the replay the
  legacy row's preview was written at head, so it shows typed search text.
- Model context changed: card turns in thread history are typed-facts JSON.
  The live measurement eval was not run and waits for the founder.
- The replay seeds card turns through the real card builder and the real
  `create_message` with the content the chat route now persists; the chat
  route itself is proven by the route tests, since a live turn needs a model.
- The lifecycle preview writers used to index degraded clarification fallback
  text; they now share the owner that excludes it, as `DATA_MODEL.md` already
  stated.
