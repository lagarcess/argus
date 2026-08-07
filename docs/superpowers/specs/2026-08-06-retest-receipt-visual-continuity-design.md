# Retest receipt visual continuity

Status: **APPROVED — implementation follow-up for PR #363**

This design is a narrow visual-continuity addendum to the typed Retest work in
PR #363. It does not change Retest admission, provider-window truth, action
payloads, confirmation behavior, usage accounting, or the backtest job
lifecycle.

## Problem

Submitting an enabled Retest action currently creates an optimistic structured
user message with the localized action label but without the backend-owned
receipt facts. The chat renderer therefore paints the shared one-line action
pill first. When the final stream payload supplies `retest_receipt`, the same
message swaps to the taller two-line Retest receipt. Slow coverage checks make
that component and layout change visible as a flicker.

The first frame is not generated prose, but it looks less intentional than the
settled receipt and weakens the visual continuity of the action the user just
took.

## Locked behavior

The Retest user turn uses one stable receipt container from optimistic submit
through settled success:

1. The optimistic frame immediately renders the Retest icon and localized
   action label in the final receipt container.
2. A quiet, `aria-hidden` placeholder reserves the context row without
   inventing symbols, strategy facts, dates, or duration.
3. The final backend payload replaces that placeholder in place with the
   backend-owned receipt context.
4. A terminal failure clears the pending presentation and keeps the existing
   recovery treatment. It must not leave an animated loading placeholder
   behind.
5. Hydrated messages never infer pending state. A persisted complete receipt
   renders ready immediately; legacy or incomplete metadata keeps the existing
   settled one-line action fallback.

The container's width may adapt to its final content, but its component type,
corner treatment, vertical rhythm, and reserved second-row height must not swap
between optimistic and ready frames.

## Ownership and data flow

- The optimistic `Message` projection owns one ephemeral presentation flag for
  this turn only. It is not persisted and is not a new product or job state.
- `ChatInterface` sets the flag only for an optimistic `retest_run` message and
  clears it on every terminal final or error path.
- `RetestReceipt` renders `pending` or `ready` presentation from that explicit
  flag plus the optional backend receipt.
- The existing `retest_receipt` payload remains the only authority for the
  second-line facts.
- Reload continues to use structured message metadata and never recreates
  pending state.

No new polling, timer, request lifecycle, backend field, API contract, or
localized product copy is introduced.

## Failure and recovery

Pending presentation is purely optimistic UI. It ends when the current request
reaches any terminal final, SSE error, HTTP rejection, or ambiguity resolution.
The existing assistant or user-turn recovery projection remains authoritative.
Retry continues to replay the typed action and creates one new optimistic
receipt for that retry without duplicating the durable receipt.

## Verification

- A component test must fail before implementation by proving that an
  optimistic Retest message renders the same receipt shell and reserved context
  row as the ready message.
- Projection tests cover pending creation, success settlement, failure
  settlement, and reload without pending state.
- Existing Retest, chat recovery, and job lifecycle tests remain green.
- A delayed-response Chromium check captures the optimistic and settled frames
  in English and es-419 and asserts that the receipt shell identity and height
  remain stable.
- Only the affected receipt evidence is refreshed at the exact final head.

## Scope and stop conditions

This is one focused commit in PR #363. Stop and report if the fix requires
client-derived canonical receipt facts, a backend contract change, a second
request state machine, changes to backtest job polling, or unrelated chat
renderer refactoring. The founder remains the only merge authority.
