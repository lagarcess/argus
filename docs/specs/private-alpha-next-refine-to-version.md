# Refine to Version: Post-Result Edit Routing (Lane A1)

Status: SHIPPED (routing + loop repair) — issue #141, PR #148, merged
`5fc7a9a` on `codex/private-alpha-next`, 2026-07-03.
Follow-up: A1b (linked `IdeaVersion` emission) is the next spine-chain slice;
comparison (A2) stays gated on A1b. See the execution board in
`private-alpha-next-roadmap.md`.

This spec records shipped behavior. It was authored after the founder answered
the lane's product questions live (2026-07-01) instead of a pre-build spec
review; it exists so later lanes (A1b, A2) extend a written contract instead
of reverse-engineering PR #148.

## Problem

Observed live (issue #141, conversation `eda24763`):

- The result-card `Refine idea` action tagged its pending state
  `requested_field:"refinement"` (`api/chat/result_actions.py`), which the
  edit contract's trigger
  (`_request_targets_pending_artifact_assumption_edit`) did not recognize.
  Refine edits bypassed the operations planner, fell to generic
  interpretation, and could drop the edit or lose asset/date context.
- A new idea referencing the prior result ("buy COST from the same time
  period") verbally acknowledged the window but never stored it, producing a
  repeated date-confirmation loop: every "yes" re-asked the same question.

## Founder decisions (2026-07-01)

1. Scope is repair only: routing and the confirmation loop. Linked
   `IdeaVersion` emission was split out as A1b.
2. Refinement is a first-class edit context everywhere, not a one-guard
   patch. The refine chip and natural-language edits are two entry points
   into the same typed edit operations.
3. A new idea right after a completed result may borrow its context: "same
   time period" binds silently to the latest run's date window. Bound values
   must render on the confirmation card as visible assumptions.

## Shipped contract

- Post-result edits route through the typed artifact-edit planner regardless
  of entry point (refine chip, confirmation-card chip, natural language).
- The supported-edit discriminator counts date-window and cadence evidence as
  planner-expressible operations; strategy reshapes (new strategy type or
  entry/exit logic) still fork to full interpretation.
- Same-period references bind to the latest completed run's window once; a
  confirmed pending date answer materializes and repeated affirmatives do not
  re-ask.
- Spine rules upheld: handlers consume the interpreter's typed output only.
  No text re-scanning, no post-LLM intent flips, no per-language copy.

## Verification

- Regression suites added in PR #148:
  `tests/agent_runtime/test_refine_action_edit_routing.py`,
  `tests/agent_runtime/test_post_result_edit_routing.py`,
  `tests/agent_runtime/test_latest_result_window_binding.py`,
  `tests/agent_runtime/test_validation_failure_copy.py`.
- Codex review finding (date/cadence edits skipping the planner) fixed with
  tests tightened to assert the direct route, proven red first.
- CI fully green on PR #148 (backend, frontend, local-smoke, ownership-gate).

## Deferred (not shipped here)

- A1b: emit a new linked `IdeaVersion` when a refine produces a changed idea
  (P1 spine supports lineage). This is what unlocks the A2 comparison
  readout.
- Any comparison behavior (A2).
