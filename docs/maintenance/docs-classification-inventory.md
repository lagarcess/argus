# Docs Classification Inventory

## Summary

Snapshot note: refreshed for `codex/private-alpha-next` after P2.0/P2.1 landed
and after the evidence-aware loop was reclassified as source thesis for the
decision memo.

Current source stack after the canon docs:

1. `docs/specs/private-alpha-next-roadmap.md` is the active Private Alpha Next
   execution board.
2. `docs/specs/private-alpha-next-decision-memo.md` is the active strategic
   north star and slice-onboarding source.
3. `docs/specs/private-alpha-ci-cd-sota.md`,
   `docs/PRIVATE_LAUNCH_RUNBOOK.md`, and
   `docs/release-manifests/TEMPLATE.md` are release-discipline references.
4. `docs/specs/private-alpha-next-integration.md` is staging/process context.

Quarantine branches are reference material only. Do not broad cherry-pick
runtime work from `codex/private-alpha-next-quarantine-fc231e8`; promote only
small, reviewed, revertable slices.

Release-discipline note: `docs/specs/private-alpha-ci-cd-sota.md` remains the
release-gate reference. It does not own Private Alpha Next product sequencing.

Archive pass: high-confidence stale private-alpha specs and completed checkpoint
docs were moved from `docs/specs/` to `docs/archive/` so active agents do not
mistake them for current command sources.

## Inventory

| File | Classification | Rationale | Recommended next action | Notes / possible stale references |
| :--- | :--- | :--- | :--- | :--- |
| `AGENTS.md` | canon | Root level agent instructions and canon pointer. | None | Current |
| `docs/PRODUCT.md` | canon | Defined as canon product source of truth. | None | Current |
| `docs/ARCHITECTURE.md` | canon | Defined as canon architecture source of truth. | None | Current |
| `docs/API_CONTRACT.md` | canon | Defined as canon API contract source of truth. | None | Current |
| `docs/DATA_MODEL.md` | canon | Defined as canon data model source of truth. | None | Current |
| `.agent/designs/argus/DESIGN.md` | canon | Explicitly listed as canon design source of truth. | None | Current |
| `docs/specs/private-alpha-next-roadmap.md` | current active roadmap | Active P1 board for done/next/deferred labels, slice stop criteria, and integration criteria. | Use as the first non-canon execution source for Private Alpha Next product work. | Created after P0 reintegration |
| `docs/specs/private-alpha-next-decision-memo.md` | active strategic source | Strategic north star for Private Alpha Next; contains the addenda and details each slice must onboard through. | Read relevant sections before planning or implementation. | Current |
| `docs/specs/private-alpha-ci-cd-sota.md` | release-discipline reference | Completed CI/CD SOTA plan; still owns canary, manifest, Render validation, and deployment discipline. | Use for release gates, not product sequencing. | Completed/reference |
| `docs/PRIVATE_LAUNCH_RUNBOOK.md` | release-discipline reference | Operational gate for controlled private-alpha validation and launch steps. | Keep as operator runbook. | Current release ops |
| `docs/release-manifests/TEMPLATE.md` | release-discipline reference | Template for candidate SHA, env fingerprint, evidence, approver, and rollback target. | Use when producing a candidate manifest. | Current release ops |
| `docs/specs/private-alpha-next-integration.md` | active staging/process context | Records integration-lane branch mechanics, quarantine rules, closed work, Jules boundaries, and P0 reintegration process. | Keep as staging/process context. | Current context, not command doc |
| `docs/archive/private-alpha-conversation-trust.md` | archived historical evidence / completed checkpoint | Marked as merged and deployed checkpoint; useful for conversation-trust design context but not current execution scope. | Keep archived for branch archaeology. | Completed |
| `docs/archive/private-alpha-status-action-parity-audit.md` | archived historical evidence / implemented slice | Implemented and locally verified; useful as artifact lifecycle evidence but not current execution scope. | Keep archived for branch archaeology. | Completed |
| `docs/archive/private-alpha-readiness-orchestration.md` | archived branch-specific context | Coordination note for `codex/private-alpha-readiness-clean`; not the current Private Alpha Next roadmap. | Keep archived for readiness-lane archaeology. | Readiness lane |
| `docs/archive/private-alpha-controlled-readiness-panel.md` | archived branch/lane-specific context | Controlled-alpha readiness panel for readiness decisions; useful evidence but not the active roadmap. | Keep archived for readiness-lane archaeology. | Readiness lane |
| `docs/archive/private-alpha-performance-readiness-audit.md` | archived branch/lane-specific context | Supporting performance addendum for the controlled readiness slice. | Keep archived for readiness-lane archaeology. | Readiness lane |
| `docs/specs/evidence-aware-idea-loop.md` | source thesis / strategic background | Source product thesis for the durable idea loop. It directly informed `docs/specs/private-alpha-next-decision-memo.md`, which now owns current strategy. | Keep in `docs/specs/` with a clear source-thesis banner; do not treat as the active sequencing doc. | Provenance for the current decision memo |
| `docs/archive/research-lab-thesis.md` | archived historical evidence | Earlier Research Lab thesis draft. It is retained for context and refined by `docs/specs/evidence-aware-idea-loop.md`, which then informed the decision memo. | Keep archived for product archaeology. | Superseded by evidence-aware source thesis and current decision memo |
| `docs/archive/private-alpha-backtest-execution-capacity.md` | archived historical evidence | Draft from 2026-06-05; later release/runtime docs own active deployment discipline and architecture truth. | Keep archived for runtime-capacity archaeology. | Historical capacity draft |
| `docs/archive/agent-architecture.md` | archived historical evidence | Proposed architecture from 2026-04-29. Predates the conversation trust milestone. | Keep archived for architecture archaeology. | Stale date |
| `docs/CONVERSATIONAL_RUNTIME.md` | unclear/needs owner decision | Status is "Active Alpha implementation", but unclear if it's canon, active spec, or superseded by `docs/ARCHITECTURE.md`. | Decide if canon or stale/superseded. |  |
| `docs/archive/LAUNCH_GATE_FINAL_CLOSURE_PLAN.md` | archived/superseded | Explicitly marked "> Historical plan. This document records an earlier launch-closure checklist and should not be treated as the current milestone source of truth." | Archived under `docs/archive/`; use `docs/archive/private-alpha-conversation-trust.md` for the completed trust checkpoint and `docs/specs/private-alpha-ci-cd-sota.md` for release-gate discipline. | Explicitly stale. |
| `docs/ARGUS_SYSTEM_STEERING.md` | historical evidence | "Pre-private-launch steering reference... planning reference, not an implementation ticket" from 2026-05-19. | Add historical banner. |  |
| `docs/QA_CONVERSATIONAL_TRANSCRIPTS.md` | unclear/needs owner decision | QA script. Could be canon process, or an active spec, or archive if out of date. | Clarify if this QA process is still active. | Uses legacy orchestrator path? |
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


## Prior Banner Pass Summary

This records a previous docs-janitor pass. It is not the active source order;
use the inventory table above for current classification.

### Files that already carry or were recommended for historical treatment:
- `docs/ARGUS_SYSTEM_STEERING.md` -> AGENTS.md, docs/specs/private-alpha-next-integration.md
- `docs/PRODUCTION_READINESS_AUDIT.md` -> docs/archive/private-alpha-conversation-trust.md
- `docs/archive/agent-architecture.md` -> docs/ARCHITECTURE.md
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

### Files that already carry or were recommended for superseded treatment:
- `docs/archive/LAUNCH_GATE_FINAL_CLOSURE_PLAN.md` -> docs/archive/private-alpha-conversation-trust.md

### Files intentionally skipped (unclear/needs owner decision):
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
*   `docs/archive/research-lab-thesis.md` already carries its own historical/refined status banner from the active evidence-aware idea-loop spec and did not need a second Jules banner pass.
