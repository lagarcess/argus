# Docs Classification Inventory

## Summary

*   **Canon:** 6
*   **Active Spec:** 3
*   **Historical Evidence:** 20
*   **Archive Candidate:** 1
*   **Unclear/Needs Owner Decision:** 13

## Inventory

| File | Classification | Rationale | Recommended next action | Notes / possible stale references |
| :--- | :--- | :--- | :--- | :--- |
| `AGENTS.md` | canon | Root level agent instructions and canon pointer. | None | Current |
| `docs/PRODUCT.md` | canon | Defined as canon product source of truth. | None | Current |
| `docs/ARCHITECTURE.md` | canon | Defined as canon architecture source of truth. | None | Current |
| `docs/API_CONTRACT.md` | canon | Defined as canon API contract source of truth. | None | Current |
| `docs/DATA_MODEL.md` | canon | Defined as canon data model source of truth. | None | Current |
| `.agent/designs/argus/DESIGN.md` | canon | Explicitly listed as canon design source of truth. | None | Current |
| `docs/specs/private-alpha-conversation-trust.md` | active spec | Marked as merged and deployed checkpoint, explicitly names current private-alpha direction. | None | Current |
| `docs/specs/private-alpha-next-integration.md` | active spec | Marked as "Active integration staging baseline" and "working source of truth for the next integration branch". | None | Current |
| `docs/specs/research-lab-thesis.md` | active spec | Listed as a draft design spec for the next milestone and explicitly not an implementation plan for the current conversation-trust milestone. Classified as active spec because it is clearly marked as design-only/future direction. | Review | Future direction |
| `docs/specs/private-alpha-backtest-execution-capacity.md` | unclear/needs owner decision | Draft from 2026-06-05, frames architecture questions before scaling. Not clearly an active spec for the current milestone, nor pure historical evidence. | Determine if this is an active spec or historical. |  |
| `docs/specs/agent-architecture.md` | historical evidence | Proposed architecture from 2026-04-29. Predates the conversation trust milestone. | Add historical banner. | Stale date. |
| `docs/CONVERSATIONAL_RUNTIME.md` | unclear/needs owner decision | Status is "Active Alpha implementation", but unclear if it's canon, active spec, or superseded by `docs/ARCHITECTURE.md`. | Decide if canon or archive candidate. |  |
| `docs/LAUNCH_GATE_FINAL_CLOSURE_PLAN.md` | archive candidate | Explicitly marked "> Historical plan. This document records an earlier launch-closure checklist and should not be treated as the current milestone source of truth." | Add superseded banner pointing to `docs/specs/private-alpha-conversation-trust.md`. | Explicitly stale. |
| `docs/ARGUS_SYSTEM_STEERING.md` | historical evidence | "Pre-private-launch steering reference... planning reference, not an implementation ticket" from 2026-05-19. | Add historical banner. |  |
| `docs/QA_CONVERSATIONAL_TRANSCRIPTS.md` | unclear/needs owner decision | QA script. Could be canon process, or an active spec, or archive if out of date. | Clarify if this QA process is still active. | Uses legacy orchestrator path? |
| `docs/PRIVATE_LAUNCH_RUNBOOK.md` | historical evidence | Runbook for "first trusted-user internet tests". Private launch has passed (we are in "private alpha next"). | Keep for historical reference, or update. | URLs might still be valid, but process is historical. |
| `docs/PRODUCTION_READINESS_AUDIT.md` | historical evidence | Audit for `codex/production-readiness-gap-implementation` from 2026-05-05. | Add historical banner. |  |
| `docs/superpowers/plans/2026-05-06-streaming-persistence-ui-orchestration.md` | historical evidence | Implementation plan for Phase 5 from 2026-05-06. | Add historical banner. |  |
| `docs/superpowers/plans/2026-05-12-conversational-contract-hardening.md` | historical evidence | Implementation plan from 2026-05-12. | Add historical banner. |  |
| `docs/superpowers/plans/2026-05-06-agent-runtime-phase-6-structural-hygiene.md` | historical evidence | Implementation plan from 2026-05-06. | Add historical banner. |  |
| `docs/superpowers/plans/2026-05-06-agent-runtime-phase-2-retire-legacy-orchestrator.md` | historical evidence | Implementation plan from 2026-05-06. | Add historical banner. |  |
| `docs/superpowers/plans/2026-05-06-agent-runtime-phase-3-4-nlu-collapse.md` | historical evidence | Implementation plan from 2026-05-06. | Add historical banner. |  |
| `docs/superpowers/plans/2026-06-03-conversation-artifact-continuity.md` | historical evidence | Implementation plan from 2026-06-03. | Add historical banner. |  |
| `docs/superpowers/plans/2026-05-06-agent-runtime-phase-5-streaming-persistence.md` | historical evidence | Implementation plan from 2026-05-06. | Add historical banner. |  |
| `docs/superpowers/plans/2026-06-06-render-workflow-proof.md` | historical evidence | Implementation plan from 2026-06-06. | Add historical banner. |  |
| `docs/superpowers/plans/2026-05-06-agent-runtime-phase-1-remediation.md` | historical evidence | Implementation plan from 2026-05-06. | Add historical banner. |  |
| `docs/superpowers/plans/2026-06-06-async-backtest-job-state.md` | historical evidence | Implementation plan from 2026-06-06. | Add historical banner. |  |
| `docs/superpowers/plans/2026-04-29-conversational-backtest-agent-runtime.md` | historical evidence | Implementation plan from 2026-04-29. | Add historical banner. |  |
| `docs/superpowers/plans/2026-06-04-private-alpha-reliability-hardening.md` | historical evidence | Implementation plan from 2026-06-04. | Add historical banner. |  |
| `docs/superpowers/specs/2026-06-03-chat-disclaimer-design.md` | unclear/needs owner decision | Spec from 2026-06-03. Unknown if fully implemented or still active. | Verify implementation status. |  |
| `docs/superpowers/specs/2026-05-13-artifact-centered-runtime-rebuild-scope.md` | historical evidence | Spec from 2026-05-13. | Add historical banner. |  |
| `docs/superpowers/specs/2026-05-13-artifact-runtime-production-readiness-second-pass.md` | historical evidence | Spec from 2026-05-13. | Add historical banner. |  |
| `docs/superpowers/specs/2026-05-17-sidebar-revamp-runtime-parity-qa.md` | historical evidence | QA doc from 2026-05-17. | Add historical banner. |  |
| `docs/superpowers/specs/2026-05-15-artifact-runtime-milestone-checkpoint.md` | historical evidence | Checkpoint doc from 2026-05-15. | Add historical banner. |  |
| `.agent/rules/git-workflow.md` | unclear/needs owner decision | Active rule for agents, but might be considered "canon" for agent rules. Will mark as unclear. | Clarify if agent rules are "canon" or separate. |  |
| `.agent/rules/testing.md` | unclear/needs owner decision | Active rule. | Clarify if agent rules are "canon". |  |
| `.agent/rules/workspace.md` | unclear/needs owner decision | Active rule. | Clarify if agent rules are "canon". |  |
| `.agent/rules/performance.md` | unclear/needs owner decision | Active rule. | Clarify if agent rules are "canon". |  |
| `.agent/rules/coding-standards.md` | unclear/needs owner decision | Active rule. | Clarify if agent rules are "canon". |  |
| `.agent/workflows/*.md` | unclear/needs owner decision | Active workflows. | Clarify if workflows are "canon". |  |
| `.agent/.jules/realignment.md` | unclear/needs owner decision | Active instructions. | Clarify if .jules instructions are "canon". |  |
| `.agent/.jules/README.md` | unclear/needs owner decision | Active instructions. | Clarify if .jules instructions are "canon". |  |
| `.agent/ownership/README.md` | unclear/needs owner decision | Active ownership rules. | Clarify if ownership docs are "canon". |  |

## Out of scope observations

*   Multiple detailed references and templates exist under `.agent/skills/` which were intentionally excluded from this inventory to keep it focused on high-level workflows and product documentation.
*   No high-risk, obviously stale instructions were immediately identified in the high-level scan of the skills directory, but a deeper audit of `.agent/skills/` may be beneficial later.
