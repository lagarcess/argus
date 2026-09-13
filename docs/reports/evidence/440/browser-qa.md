# Browser proof, issue #440

Journey from the issue, driven headless with the committed `qa-driver.mjs`
against the local dev stack (mock auth, memory persistence, synthetic market
data, real LLM interpretation through OpenRouter, shadow jobs off) with
`ARGUS_IN_PLACE_CARD_EDITS_ENABLED=true`, desktop viewport 1280x800, English.
Frames were read against rendered text and the persisted conversation
messages before being trusted.

Steps: idea "Buy and hold Apple for the last year with $10,000", open the
dates drawer and move the start to 2024-08-11, apply, cancel the card, send
"Run that Apple idea again for the last six months".

## Before, at `e3b98690`

| Frame | What it shows |
| --- | --- |
| `before-1-card.png` | Card for the last year, Sep 5, 2025 to Sep 4, 2026 |
| `before-2-dates-drawer.png` | Dates drawer open, start typed as 2024-08-11 |
| `before-3-dates-applied.png` | Card rewritten in place, Aug 11, 2024 to Sep 4, 2026, no turn spent |
| `before-4-cancelled.png` | Draft canceled, pills and actions removed |
| `before-5-followup.png` | New card still Aug 11, 2024 to Sep 4, 2026, no disclosure |

The persisted follow-up card was byte-identical to the cancelled card's
strategy: same `date_range`, same drawer `explicit_range` intent, no
`edit_disclosure`.

## What fired

Trace logging at three hops of the same journey (temporary, not committed):

| Hop | Date range it produced |
| --- | --- |
| Interpret stage, planner path (`artifact_assumption_edit_planned`) | 2026-03-05 to 2026-09-05 |
| Confirm stage payload | 2026-03-05 to 2026-09-04 |
| Published `final` payload and persisted card | 2024-08-11 to 2026-09-04 |

Both model reads were right: the primary read carried a six-month
`rolling_window` intent and the edit planner emitted `set date_window` for it.
The runtime built the right card. The published payload came from the
workflow-level `confirmation_payload` channel, which the drawer edit's
checkpoint sync had filled with the edited card and which no turn cleared;
`_public_result` reads that channel ahead of the turn's own run-state
payload. The cancel is incidental: it is a deterministic API control turn
that never runs the graph, so nothing reset the channel.

`control-5-followup.png` is the same journey without the drawer edit on the
pre-fix code: the follow-up card reads Mar 5, 2026 to Sep 4, 2026, isolating
the drawer sync as the only feeder.

## After, runtime source as committed in `69c839b1`

| Frame | What it shows |
| --- | --- |
| `after-1-card.png` | Card for the last year |
| `after-2-dates-drawer.png` | Dates drawer open, start 2024-08-11 |
| `after-3-dates-applied.png` | Card rewritten in place to Aug 11, 2024 |
| `after-4-cancelled.png` | Draft canceled |
| `after-5-followup.png` | New card Mar 5, 2026 to Sep 4, 2026 with the planner's note "Changing the period to the last six months." |

The persisted follow-up card carries the six-month `rolling_window` intent
and a fresh confirmation id.

## Unapplied direction

The browser journey exercises the applied direction. The refused direction,
where the edit could not be applied and the typed `edit_disclosure` must
ride the card the turn produced, is pinned by
`tests/test_issue_440_cancelled_draft_dates.py`; the stale channel dropped
that record the same way it dropped the applied window.
