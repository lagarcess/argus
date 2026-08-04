# Review Proportionality Guardrail Design

**Status:** Approved for design on 2026-07-17

## Goal

Prevent valid review work from growing into speculative, self-perpetuating
complexity while preserving strict treatment of user-visible correctness,
security, privacy, evidence integrity, and durable-state risks.

## Decision

Add one canonical review-proportionality rule to root `AGENTS.md`, next to the
integration review guardrails. Do not duplicate the rule in a skill.

The existing `argus-review-contract` skill already requires agents to read
`AGENTS.md` first, so every review-contract run inherits the repository rule.
Agents that do not invoke the skill still receive the same instruction.

## Guardrail Contract

For every proposed response to a review finding, the implementing or reviewing
agent must:

1. Validate that the finding is real, reachable, and relevant to the active
   lane before changing code.
2. Assess its severity, likelihood, affected users or artifacts, and whether it
   threatens correctness, security, privacy, evidence integrity, or durable
   state.
3. Compare the smallest safe fix with the complexity it adds: new branches,
   state, services, dependencies, caches, schemas, special cases, files, and
   regression surface.
4. Keep the fix when the risk justifies it, simplify it when a smaller existing
   primitive is sufficient, or discard it when the finding is speculative or
   the proposed complexity is disproportionate.
5. Escalate instead of weakening a confirmed correctness, security, privacy,
   evidence, or durable-state requirement when the smallest safe fix exceeds
   the lane.

After implementing a fix, reassess the actual diff using the same factors.
Remove or simplify machinery that the validated finding does not justify, and
confirm that the fix did not turn a narrow risk into a broader design change.

A review cycle may revisit only risk surfaces materially changed by the latest
fix. It must not turn unchanged code into a fresh source of speculative
requirements merely to continue the loop.

## Placement and Scope

Place the rule under `AGENTS.md` → `Integration guardrails`, immediately after
the rule that Codex reviews worker diffs before integration.

The rule applies to:

- local and cloud code review;
- review-comment follow-up;
- subagent review and acceptance passes;
- pre-ready and pre-merge review loops;
- roadmap-slice implementation when a reviewer proposes additional scope.

It does not change current release gates, severity definitions, issue
acceptance criteria, or the requirement to validate review comments before
fixing them.

## No-Touch Surfaces

Do not change:

- product runtime, API, frontend, database, or deployment behavior;
- the canonical quality-pillar definitions;
- active roadmap sequencing or issue acceptance criteria;
- global or project skills as part of this change.

## Verification

1. `AGENTS.md` contains one unambiguous proportionality rule.
2. The rule explicitly protects confirmed high-impact requirements from being
   discarded merely because their fix is difficult.
3. The rule explicitly rejects speculative edge-case expansion and repeated
   review of unchanged surfaces.
4. The rule requires a post-fix reassessment of the actual diff.
5. Repository search finds no duplicated copy in an Argus skill or another
   source-of-truth document.
6. `git diff --check` passes and the diff changes documentation only.

## Stop Conditions

Stop and reassess if the wording:

- permits a confirmed correctness, security, privacy, evidence, or durable-state
  defect to be waived solely because the fix is complex;
- assigns numeric severity or likelihood thresholds that the repository does
  not already define;
- creates a new release gate;
- duplicates the policy across `AGENTS.md` and a skill;
- encourages broad redesign instead of the smallest safe lane-local fix.
