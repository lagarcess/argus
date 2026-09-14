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
- The `/messages` transport, as the card turn's `content`, as
  `confirmation_card.summary`, and inside the full card copy each confirmation
  reference nests (`before/messages-930*.json`).

## The fix

Decision for this lane: delete the sentence; artifact naming and the search
index read the card's typed facts; model history receives the confirmation's
typed facts instead of prose; no live eval in this lane.

- `07c14964` deletes the sentence. Card turns persist empty content on the chat
  route, the retest path and in-place edits. `argus.domain.confirmation_turn_facts`
  derives strategy type, symbols and dates; thread history, naming and the
  stored preview read them. The four preview writers share
  `stored_message_preview`.
- `43d971ea` removes the field from the web card type, fixtures and e2e mocks.
- `0d57492a` updates `API_CONTRACT.md`, `DATA_MODEL.md` and
  `CONVERSATIONAL_RUNTIME.md`.
- `d226ba1f` moves two existing tests off the retired sentence.
- `196b9e84` reconciles integration `231184bb` one way (no overlapping files).
- `57c34585` answers Codex round 1: each fact has one owner and no fallback.
  The card owns `strategy_type` and dates, the payload owns only the symbol
  list, and a legacy card missing a fact yields null.
- `e8925e04` answers Codex round 2. Legacy rows nest full card copies in
  `active_confirmation_reference` and `artifact_references`, so the recursive
  reader scrub now drops the retired `summary` from every card copy at any
  depth, for every message kind. The committed replay scripts derive the
  repository root from their own location, and the capture scans the whole
  transport instead of one field.

## After, at `e8925e04` with a clean tree

Headless Chromium against a memory-mode replay (`replay_confirmation_api.py`,
`capture_confirmation_evidence.mjs`), workspace `es-419`, zero provider calls,
zero hosted database reads or writes, zero console errors
(`after/capture-report.json`). Every capture records a whole-transport scan:
`transport_contains_ready_to_test` is false and `transport_card_summary_paths`
is empty.

| Capture | What it shows |
| :--- | :--- |
| `es-buy-and-hold-card.png` | Spanish card; transport content `""`; no `Ready to test` in the DOM or anywhere in `/messages` |
| `es-recurring-buys-card.png` | Same for a recurring plan |
| `es-rsi-threshold-card.png` | Same for an RSI threshold rule |
| `es-buy-and-hold-card-after-in-place-edit.png` | The real direct-edit endpoint rebuilt and persisted the card at $25,000; the whole response carries no sentence and no card copy with `summary` |
| `es-legacy-card-turn.png` | A row stored the old way, sentence as content, as `summary` and inside both nested references; `/messages` carries it nowhere |

The captures at `0d57492a` and `57c34585` checked only the top-level card. At
those heads the legacy row still returned the sentence inside both nested
references, which Codex round 2 found in the committed files.

`after/thread-history.json` records, for all four conversations including the
legacy row, the model history and naming input as
`{"confirmation_card":{"strategy_type":...,"symbols":[...],"date_range":{...}}}`
and the stored preview as, for example, `AAPL buy_and_hold 2024-01-02 2024-12-31`.
`after/conversations.json` and `after/search-aapl.json` show typed previews.

## Reproduce

From the repository root with the backend environment active:

```bash
python docs/reports/evidence/confirmation-summary-prose/replay_confirmation_api.py
```

```bash
cd web && NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8593/api/v1 NEXT_PUBLIC_MOCK_AUTH=true NEXT_PUBLIC_ENABLE_SPANISH=true NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 NEXT_PUBLIC_SUPABASE_ANON_KEY=replay-local-anon bun run dev -- --hostname 127.0.0.1 --port 3293
```

```bash
node docs/reports/evidence/confirmation-summary-prose/capture_confirmation_evidence.mjs
```

The harness writes `temp/replay-manifest.json` and the capture writes
`temp/evidence-after/`, both under the repository root.

## Tests

`tests/test_confirmation_turn_prose.py` has 40 cases, all in `en` and `es-419`:
seven shapes (buy and hold, recurring buys, RSI threshold, dip buying,
indicator threshold, signal strategy, moving-average crossover) through the
card builder and the chat route; the in-place edit; a legacy row read through
`/messages` and model history; the Supabase finalize and create preview
writers; the one-owner invariant; and an in-place edit of a legacy row.

- The first 36 failed on `736dfd03`.
- `test_card_turn_readers_only_see_facts_the_card_carries` fails on `01bcfed`
  (the legacy card got the payload's `dca_accumulation` and 2024 dates).
- `test_a_legacy_card_turn_sentence_reaches_no_reader` fails on `7fee0131`
  (the sentence survived inside the nested references).
- `test_an_in_place_edit_of_a_legacy_card_returns_no_retired_sentence` already
  held on `7fee0131`, because that route rebuilds the card and both references;
  it stays as the invariant for that transport.

All 40 pass at `e8925e04`.

## Live route check

`route-check/` drove real turns through the chat route at `4e89d289`, in
English and Spanish: create a card, change an input, run it, and ask about the
result, with artifact naming invoked after each turn. The history the chat
route loaded held every card turn as the card's typed facts, every captured
model call that received a card turn received that form, and naming, which
built its input only after each conversation's first card turn and skipped the
other turns, read that card turn the same way. The retired sentence appeared in
no captured model input, and no follow-up misread the card. The Spanish result question
timed out once at the answer composer and answered correctly on one retry.
Billed $0.162 of the $0.50 cap. The full live measurement was skipped because
it builds each case's history itself and cannot see this change.

## Limits

- Rows written before this change keep the English sentence in
  `conversations.last_message_preview` until the conversation's next message,
  and the interpreter keeps reading a legacy card's `summary` until that card
  is rebuilt. The founder accepted both as they are: no backfill, no change to
  what the model reads for cards made before this change. In the replay the
  legacy row's preview was written at head, so it shows typed search text.
- Model context changed: card turns in thread history are typed-facts JSON,
  checked live by the route check above.
- For conversations whose card predates this change, the interpreter's
  `active_confirmation_reference` dump into model context
  (`llm_interpreter.py`, `focused_extraction.py`) still carries that legacy
  `summary` until the card is rebuilt. New cards carry none. Reported, not
  changed here.
- The replay seeds card turns through the real card builder and the real
  `create_message` with the content the chat route now persists; the chat
  route itself is proven by the route tests, since a live turn needs a model.
- The lifecycle preview writers used to index degraded clarification fallback
  text; they now share the owner that excludes it, as `DATA_MODEL.md` already
  stated.
