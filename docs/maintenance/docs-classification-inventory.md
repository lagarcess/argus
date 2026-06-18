# Docs Classification Inventory

## Summary

*   **Canon:** 6
*   **Current Active Goal:** 1
*   **Active Staging/Process Context:** 1
*   **Branch/Lane-Specific Active Context:** 4
*   **Future/Later Context:** 2
*   **Maintenance:** 6
*   **Historical Evidence / Completed Checkpoint:** 21
*   **Stale/Superseded:** 1
*   **Unclear/Needs Owner Decision:** 16

Snapshot note: refreshed for the `codex/private-alpha-next` CI/CD SOTA mission.
For this branch, `docs/specs/private-alpha-ci-cd-sota.md` is the current active
goal. `docs/specs/private-alpha-next-integration.md` remains staging/process
context, and `docs/specs/private-alpha-next-decision-memo.md` is future context
only.

## Inventory

| File | Classification | Rationale | Recommended next action | Notes / possible stale references |
| :--- | :--- | :--- | :--- | :--- |
| `AGENTS.md` | canon | Root level agent instructions and canon pointer. | None | Current |
| `docs/PRODUCT.md` | canon | Defined as canon product source of truth. | None | Current |
| `docs/ARCHITECTURE.md` | canon | Defined as canon architecture source of truth. | None | Current |
| `docs/API_CONTRACT.md` | canon | Defined as canon API contract source of truth. | None | Current |
| `docs/DATA_MODEL.md` | canon | Defined as canon data model source of truth. | None | Current |
| `.agent/designs/argus/DESIGN.md` | canon | Explicitly listed as canon design source of truth. | None | Current |
| `docs/specs/private-alpha-ci-cd-sota.md` | current active goal | Active execution roadmap for `codex/private-alpha-next` release-captain work. | Use as the first non-canon execution source for the current mission. | Current |
| `docs/specs/private-alpha-next-integration.md` | active staging/process context | Records integration-lane branch mechanics, closed work, and Jules boundaries. No longer owns the current execution order when it conflicts with the CI/CD SOTA spec. | Keep as staging context. | Current context, not command doc |
| `docs/specs/private-alpha-conversation-trust.md` | historical evidence / completed checkpoint | Marked as merged and deployed checkpoint; useful for conversation-trust design context but not current execution scope. | Keep as historical context. | Completed |
| `docs/specs/private-alpha-readiness-orchestration.md` | branch-specific active context | Active coordination note for `codex/private-alpha-readiness-clean`; not the current `codex/private-alpha-next` CI/CD execution roadmap. | Keep with branch-scope note. | Readiness lane |
| `docs/specs/private-alpha-controlled-readiness-panel.md` | branch/lane-specific active context | Controlled-alpha readiness panel for readiness decisions; useful context but not the CI/CD SOTA roadmap. | Keep with readiness-lane scope note. | Readiness lane |
| `docs/specs/private-alpha-performance-readiness-audit.md` | branch/lane-specific active context | Supporting performance addendum for the controlled readiness slice. | Keep with readiness-lane scope note. | Readiness lane |
| `docs/specs/private-alpha-next-decision-memo.md` | future/later context | Promoted decision memo; user identified it as the later goal after the CI/CD SOTA mission. | Do not implement during the CI/CD SOTA milestone unless explicitly resumed. | Future |
| `docs/specs/evidence-aware-idea-loop.md` | future/later context | Active refined product spec for the post-conversation-trust direction. It keeps direct test, education, light evidence, deep research, and monitoring as lanes into one durable idea loop. | Keep as future product context. | Future |
| `docs/specs/research-lab-thesis.md` | historical evidence | Earlier Research Lab thesis draft. It is retained for context and explicitly refined by `docs/specs/evidence-aware-idea-loop.md`. | Keep as historical context. | Superseded by active evidence-aware loop spec. |
| `docs/specs/private-alpha-backtest-execution-capacity.md` | unclear/needs owner decision | Draft from 2026-06-05, frames architecture questions before scaling. Not clearly an active spec for the current milestone, nor pure historical evidence. | Determine if this is an active spec or historical. |  |
| `docs/specs/agent-architecture.md` | historical evidence | Proposed architecture from 2026-04-29. Predates the conversation trust milestone. | Add historical banner. | Stale date. |
| `docs/CONVERSATIONAL_RUNTIME.md` | unclear/needs owner decision | Status is "Active Alpha implementation", but unclear if it's canon, active spec, or superseded by `docs/ARCHITECTURE.md`. | Decide if canon or stale/superseded. |  |
| `docs/archive/LAUNCH_GATE_FINAL_CLOSURE_PLAN.md` | archived/superseded | Explicitly marked "> Historical plan. This document records an earlier launch-closure checklist and should not be treated as the current milestone source of truth." | Archived under `docs/archive/`; use `docs/specs/private-alpha-conversation-trust.md` for the completed trust checkpoint and `docs/specs/private-alpha-ci-cd-sota.md` for the active CI/CD gate. | Explicitly stale. |
| `docs/ARGUS_SYSTEM_STEERING.md` | historical evidence | "Pre-private-launch steering reference... planning reference, not an implementation ticket" from 2026-05-19. | Add historical banner. |  |
| `docs/QA_CONVERSATIONAL_TRANSCRIPTS.md` | unclear/needs owner decision | QA script. Could be canon process, or an active spec, or archive if out of date. | Clarify if this QA process is still active. | Uses legacy orchestrator path? |
| `docs/PRIVATE_LAUNCH_RUNBOOK.md` | branch/lane-specific active context | Current operational gate for the controlled private-alpha readiness sprint. Useful for release operations, but not the CI/CD SOTA spec source. | Keep as operational runbook context. | Readiness/runbook lane |
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
| `.agent/handoffs/HANDOFF_PACKET_TEMPLATE.md` | unclear/needs owner decision | Template for handoffs. Needs verification if this is canon. | Verify if handoff template is 'canon'. | |
| `.agent/handoffs/SECTION3_OWNERSHIP_CHECKLIST.md` | unclear/needs owner decision | Handoff checklist. Needs verification if this is canon. | Verify if handoff checklist is 'canon'. | |
| `.agent/handoffs/SECTION4_OWNERSHIP_CHECKLIST.md` | unclear/needs owner decision | Handoff checklist. Needs verification if this is canon. | Verify if handoff checklist is 'canon'. | |
| `docs/maintenance/dead-code-candidates.md` | maintenance | Inventory of dead code candidates. | Keep updated as codebase evolves. | |
| `docs/maintenance/docs-classification-inventory.md` | maintenance | This file. | Keep updated as docs evolve. | |
| `docs/maintenance/i18n-key-audit.md` | maintenance | Inventory of i18n keys. | Keep updated as keys are added/removed. | |
| `docs/maintenance/language-enablement-checklist.md` | maintenance | Checklist for language enablement. | Track progress of language support. | |
| `docs/maintenance/large-file-modularity-inventory.md` | maintenance | Inventory of large files for modularity. | Keep updated as refactoring occurs. | |
| `docs/maintenance/spanish-readiness-inventory.md` | maintenance | Inventory of Spanish readiness. | Keep updated as translations progress. | |


## Banner Applied Summary

### Files receiving 'Historical' banner:
- `docs/ARGUS_SYSTEM_STEERING.md` -> AGENTS.md, docs/specs/private-alpha-next-integration.md
- `docs/PRIVATE_LAUNCH_RUNBOOK.md` -> docs/specs/private-alpha-conversation-trust.md
- `docs/PRODUCTION_READINESS_AUDIT.md` -> docs/specs/private-alpha-conversation-trust.md
- `docs/specs/agent-architecture.md` -> docs/ARCHITECTURE.md
- `docs/superpowers/plans/2026-04-29-conversational-backtest-agent-runtime.md`
- `docs/superpowers/plans/2026-05-06-agent-runtime-phase-1-remediation.md`
- `docs/superpowers/plans/2026-05-06-agent-runtime-phase-2-retire-legacy-orchestrator.md`
- `docs/superpowers/plans/2026-05-06-agent-runtime-phase-3-4-nlu-collapse.md`
- `docs/superpowers/plans/2026-05-06-agent-runtime-phase-5-streaming-persistence.md`
- `docs/superpowers/plans/2026-05-06-agent-runtime-phase-6-structural-hygiene.md`
- `docs/superpowers/plans/2026-05-06-streaming-persistence-ui-orchestration.md`
- `docs/superpowers/plans/2026-05-12-conversational-contract-hardening.md`
- `docs/superpowers/plans/2026-06-03-conversation-artifact-continuity.md`
- `docs/superpowers/plans/2026-06-04-private-alpha-reliability-hardening.md`
- `docs/superpowers/plans/2026-06-06-async-backtest-job-state.md`
- `docs/superpowers/plans/2026-06-06-render-workflow-proof.md`
- `docs/superpowers/specs/2026-05-13-artifact-centered-runtime-rebuild-scope.md`
- `docs/superpowers/specs/2026-05-13-artifact-runtime-production-readiness-second-pass.md`
- `docs/superpowers/specs/2026-05-15-artifact-runtime-milestone-checkpoint.md`
- `docs/superpowers/specs/2026-05-17-sidebar-revamp-runtime-parity-qa.md`

### Files receiving 'Superseded' banner:
- `docs/archive/LAUNCH_GATE_FINAL_CLOSURE_PLAN.md` -> docs/specs/private-alpha-conversation-trust.md

### Files intentionally skipped (unclear/needs owner decision):
- `docs/specs/private-alpha-backtest-execution-capacity.md`
- `docs/CONVERSATIONAL_RUNTIME.md`
- `docs/QA_CONVERSATIONAL_TRANSCRIPTS.md`
- `docs/superpowers/specs/2026-06-03-chat-disclaimer-design.md`
- `.agent/rules/git-workflow.md`
- `.agent/rules/testing.md`
- `.agent/rules/workspace.md`
- `.agent/rules/performance.md`
- `.agent/rules/coding-standards.md`
- `.agent/workflows/*.md`
- `.agent/.jules/realignment.md`
- `.agent/.jules/README.md`
- `.agent/ownership/README.md`
- `.agent/handoffs/HANDOFF_PACKET_TEMPLATE.md`
- `.agent/handoffs/SECTION3_OWNERSHIP_CHECKLIST.md`
- `.agent/handoffs/SECTION4_OWNERSHIP_CHECKLIST.md`

## Out of scope observations

*   Multiple detailed references and templates exist under `.agent/skills/` which were intentionally excluded from this inventory to keep it focused on high-level workflows and product documentation.
*   No high-risk, obviously stale instructions were immediately identified in the high-level scan of the skills directory, but a deeper audit of `.agent/skills/` may be beneficial later.
*   `docs/specs/research-lab-thesis.md` already carries its own historical/refined status banner from the active evidence-aware idea-loop spec and did not need a second Jules banner pass.
