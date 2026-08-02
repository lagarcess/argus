# Issue #337 — clear a resolved attention marker in the conversation rail

Remove a stale **Needed attention** rail tick after the same conversation path
recovers into a usable confirmation, without hiding independent failures.

Founder-locked 2026-08-02, after the August 1 checkpoint evidence identified
G-02's marker persisting after the G-01 recovery.

Founder acceptance correction, 2026-08-02: G-01/G-02 came from a Guest
session. Acceptance must therefore preserve the Guest's one legitimate
completed-backtest tick after the resolved clarification tick clears. A
registered-account fixture with two completed runs is not representative proof
because the Guest contract permits one simulation.

## 1. Why

The conversation is Argus's primary product surface, and `docs/PRODUCT.md`
requires trust through clarity. A rail marker that says a question still needs
attention after the user has supplied the missing facts and received a
confirmation contradicts the visible state of the conversation.

Issue #337 and the locked G-01/G-02 evidence report establish the expected
outcome: the marker clears after successful recovery.

## 2. Locked decisions

1. A rail `needs attention` tick is transient when a later confirmation
   resolves its recovery path in the same rendered transcript.
2. The transition is derived locally from existing transcript artifacts. It
   does not add a backend API, durable field, provider call, or LLM decision.
3. A later confirmation must not clear a separate, unrelated failure/recovery
   path; the derivation requires the transcript relationship that proves the
   successful recovery.
4. Result and decision-saved ticks retain their current behavior. Failed-job
   and independent recovery ticks remain visible.
5. Regression coverage uses the G-01/G-02 shape: an attention-producing
   clarification/recovery followed by the user-supplied facts and a successful
   confirmation.
6. A long Guest transcript with one completed backtest keeps that result tick
   visible after the resolved clarification tick clears. The rail must not
   disappear merely because only one legitimate tick remains.

## 3. Reserved / parked scope

- Durable per-turn resolution state -- unnecessary because the rail is a
  render-time navigation aid and the transcript already carries the required
  artifacts.
- Changes to the activity indicator, sidebar unread state, or other rail tick
  kinds -- not implicated by #337.
- Any change to runtime clarification or confirmation generation -- the
  evidence points to the rail's local derivation, not a malformed artifact.

## 4. Contract gates

- `web/lib/conversation-rail.ts` -- adjust only the render-time rail tick
  derivation and the minimum legitimate tick count needed to keep the rail
  visible on a long Guest transcript.
- `web/__tests__/conversation-activity-rail.test.ts` -- add the exact
  transcript regression and protect unrelated recoveries.
- No API, OpenAPI, persistence, or localization contract changes are expected.

## 5. Execution contract

- **PR shape:** one focused frontend PR targeting `codex/private-alpha-next`.
- **Proof required before ready:** test-first red/green evidence for the
  G-01/G-02 regression; a real local Guest/Auth/persistence replay showing one
  completed-backtest tick and no stale clarification tick before and after
  reload; focused Bun test suite; relevant frontend lint/type checks; EN and
  es-419 browser screenshots showing the marker clears; a proportional
  independent code review; exact-head GitHub CI status.
- **Where it stops:** a Draft or posted PR. The founder merges; no production
  deployment, migration, or integration-branch merge is part of this lane.

## 6. Stop conditions

- If correct resolution requires a new durable relationship, backend event, or
  API contract, stop and report rather than infer it in the UI.
- If the transcript cannot distinguish the recovered path from an unrelated
  failure without hiding the latter, stop and report.
- If the focused evidence points to malformed runtime confirmation artifacts,
  stop and report before widening the lane beyond the rail.

## Sources

### Argus authority

- `docs/PRODUCT.md` — Conversation is the product; trust through clarity.
- `docs/ARCHITECTURE.md` — frontend renders canonical artifacts and avoids
  inventing backend facts.
- `docs/reports/2026-08-01-current-checkpoint-experience-feedback.md` — locked
  G-01/G-02 evidence; do not edit.
- GitHub issue #337 — acceptance criteria and no-touch boundary.
- `docs/superpowers/specs/2026-07-31-conversation-activity-rail.md` — the rail
  is render-time only and supports typed recoverable/retryable failure ticks.

### Inference

- The current rail's historical `error_recovery` classification is the cause:
  it has no local resolution rule. This lane will prove the exact transcript
  relationship in a regression test before implementation.
