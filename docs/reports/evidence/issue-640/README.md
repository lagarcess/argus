# Issue #640: keep observers fresh when focus precedes admission

## Result

A focus or visibility retry that still sees the loaded `latest_message_id`
starts the same two-second saved-tail checks used for unanswered users. The
window is `ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS` (180 seconds by default) from
that retry and is not extended by later idle activity or matching-id updates.
Once an unanswered saved user message is loaded, the existing reply deadline
owns the turn and these admission checks do not extend it.

Saved API messages remain canonical. Anchors, scroll, cancellation, and sender
deduplication are unchanged. Ordinary activity refreshes still reconcile full
history; only the bounded observer checks read the saved tail. No API shape,
database, migration, model-facing text, user-facing copy, `render.yaml`, or
release-contract change.

## Exact interleaving and browser proof

1. Both tabs load the same saved conversation ending in assistant message M.
2. Tab A clicks Send. The stream exists, but no user message has been saved.
3. Tab B focuses. Its activity read is idle and `latest_message_id` is still M.
4. The API then saves the user message and assistant reply for A. No later
   focus, visibility, or activity event is sent to B.
5. B's bounded admission check loads the newer saved messages and stops.

The English and Spanish cases fail on the pre-fix runtime from integration
`708864ef76961df2767d7e09c2fbf5f9812179c7` at test head
`8fdcec3ac5f74d63ecc8a9208c204314313b6fd1`. Both pass after
`d36bba76c34b8a26c17c87dbf33d60ae736aaff0`. All 21 previously accepted browser
cases also pass, including
anchors, scroll, hidden observers, unanswered-user polling, and long-history
tail reads: **23 passed**.

| Locale | Observer before | Observer after |
| --- | --- | --- |
| English | [red](red/640-pre-admission-en.png) | [green](green/640-pre-admission-en.png) |
| Spanish | [red](red/640-pre-admission-es-419.png) | [green](green/640-pre-admission-es-419.png) |

[Red log](browser-red.txt), [green log](browser-green.txt). The two tabs use one
shared local API fixture. No providers, paid runs, or model-facing text are
involved.

## Timeout and deterministic proof

[Reload unit tests](unit-green.txt): the new admission cases fail before the
fix ([red](unit-red.txt)) and pass after it. A controlled clock advances a
matching-id focus through 180 seconds without extending the deadline. A later
focus after expiry may start a new admission window. Loading an unanswered user
hands off to the existing reply deadline, which retry cannot restart. Account,
navigation, local sender ownership, and unreadiness cancel the watch. A
matching-id activity revision alone does not start it.

```sh
bun test --cwd web __tests__/conversation-activity-transcript-reload.test.ts __tests__/conversation-transcript-read-cost.test.ts
PLAYWRIGHT_PORT=3198 bun run --cwd web test:e2e conversation-activity-ui.spec.ts conversation-transcript-freshness.spec.ts --grep-invert 'durable backtest stays|coarse pointer|resolved clarification'
```

## Integration

- Original integration base: `708864ef76961df2767d7e09c2fbf5f9812179c7`.
- Current integration: `708864ef76961df2767d7e09c2fbf5f9812179c7`.
- No reconciliation merge. Semantic overlap: none; integration did not move.
- [Modularity](modularity.txt) on this tree: no budget violations.
- Focused freshness units: 35 passed. Full frontend suite: **2,069 passed**.
- This file is acceptance evidence, not a production or deployment claim.
