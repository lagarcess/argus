# Previous saved-message identity proof

The current follow-up proof is [README.md](README.md).

# Issue #598: saved transcript freshness

## Current design

The API owns `activity.latest_message_id`, selected from saved messages in the
same `(created_at, id)` order as the message API. The owner-scoped, bounded query
also supplies conversation previews. A plain reply advances this identity even
without a job or chat-turn lifecycle row. Job timestamps and read cursors cannot
supply this fact; marking read leaves the message identity intact.

The web records the last raw API message id alongside each loaded transcript,
before message projection. On activity updates and focus/visibility recovery it
compares that snapshot with the backend identity. A mismatch loads and replaces
the transcript from the saved-message API. The sending tab keeps its active
request and already-delivered canonical reply. Refreshes coalesce, cancel across
account/conversation changes, and retry on a later activity update after failure.

Refresh uses a transcript-only path. It keeps the current URL/message anchor and
restores the reader's scroll offset. It does not navigate or infer assistant text.
An open conversation omitted from the first history page receives the existing
single-conversation activity read.

## Red/green browser acceptance

The same six regression cases fail on unchanged current integration
`350e3dca8f573f5dfd61f1f753d8ed16a2724c9e`, then pass on reconciled commit
`39a2e5135e741ebf3a20122004cb95587843a0c7`.

Each case uses two Chromium tabs and one shared intercepted API fixture. All
responses are local fixtures; no providers or paid runs. This proves browser
behavior, while backend tests cover the persisted-message projection separately.
The test deliberately uses a plain assistant reply, no job, no unread cursor,
and no working projection delivered to the observer.

| Observer scenario | English before / after | Spanish before / after |
| --- | --- | --- |
| Hidden for the entire turn, then visible/focused | [red](v2/red/598-v2-hidden-en.png) / [green](v2/green/598-v2-hidden-en.png) | [red](v2/red/598-v2-hidden-es-419.png) / [green](v2/green/598-v2-hidden-es-419.png) |
| Visible, receives only idle activity on the next poll | [red](v2/red/598-v2-visible-en.png) / [green](v2/green/598-v2-visible-en.png) | [red](v2/red/598-v2-visible-es-419.png) / [green](v2/green/598-v2-visible-es-419.png) |
| Same idle-only update while reading a message deep link | [red](v2/red/598-v2-anchor-en.png) / [green](v2/green/598-v2-anchor-en.png) | [red](v2/red/598-v2-anchor-es-419.png) / [green](v2/green/598-v2-anchor-es-419.png) |

Assertions cover exactly one reply in each tab, exactly one observer message
reload after completion, no sender reload after completion, unchanged URL and
scroll offset, and no extra reload after another focus/activity update. The
anchor screenshots remain above the new reply intentionally; the DOM assertion
checks that the saved reply is present without moving the reader.

[Red log](v2/browser-red.txt), [green log](v2/browser-green.txt), and
[commit/test provenance](v2/provenance.json) are committed with the images.
The six cases join eleven accepted existing activity cases: **17 passed**.
Four older activity-suite failures were reproduced on unchanged original
integration and remain outside this issue: result-card heading, mobile Recents
opener, and clarification rail count in both locales. Their original proof is
in [baseline-browser.txt](baseline-browser.txt). No acceptance was weakened.

## Deterministic verification

- [33 reload/activity unit cases](v2/reload-unit.txt), including idle-only updates,
  sender deduplication, cancellation, failed reads, and an omitted open conversation.
- [195 focused backend cases](v2/backend-focused.txt), including a no-job plain reply,
  owner scoping, and message-id normalization at the query boundary.
- A real-PostgreSQL keyset test now verifies that an ordinary saved reply changes
  the latest id and a foreign owner receives no row. The CI database matrix runs it.
- [1,997 frontend tests](v2/frontend-unit.txt) pass.
- Frontend lint has zero errors and eight existing unrelated warnings; production
  build passes. The free mocked evaluation harness passes 270 cases.
- [Modularity budget](v2/modularity.txt) passes on the reconciled tree.

Reproduce the provider-free acceptance:

```sh
bun test --cwd web __tests__/conversation-activity-transcript-reload.test.ts __tests__/use-conversation-activity.test.tsx
PLAYWRIGHT_PORT=3198 bun run --cwd web test:e2e conversation-activity-ui.spec.ts conversation-transcript-freshness.spec.ts --grep-invert 'durable backtest stays|coarse pointer|resolved clarification'
```

## Integration and review provenance

- Original lane base: `edeaffa9f6565e4750fa0685a050f10aefd6d718`.
- Previous integration merge: `08caf9863aadf679d969bbea1cd6bceaae5cb4d2`, incorporating
  `a4a183138aadf1cff8268d0ce169e444732116fe`.
- Current integration: `350e3dca8f573f5dfd61f1f753d8ed16a2724c9e`.
- Current one-way merge: `39a2e5135e741ebf3a20122004cb95587843a0c7`.
- Intervening integration changes concern promotion documents and scorecard
  validation. No shared chat runtime, API/data contract, UI state, migration,
  environment, or directly affected test owner changed. Browser evidence remains
  valid and was recaptured after reconciliation. No release contract or
  `render.yaml` change is authored by this PR.
- The first working-transition implementation was rejected. Its report is
  preserved as [superseded history](original-working-transition.md).
- This report precedes the single requested redesign review. The terminal PR
  comment will record the final head, CI, review outcome, zero unresolved threads,
  and explicit final-head revalidation of these committed images.
