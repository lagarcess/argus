---
name: argus-experience-audit
description: Run evidence-led end-to-end Argus product audits across Guest and signed-in experiences. Use when the founder asks to inspect a current checkpoint, reproduce a long conversation, collect screenshots and typed evidence, turn feedback into an issue-ready scenario pack, distinguish product defects from QA wiring, validate historical PR intent against current head, or make the same audit runnable in Codex Cloud without implementing speculative fixes.
---

# Argus Experience Audit

Produce a reproducible audit of what a user experienced, why it matters, and
what a future implementation agent must prove. Preserve founder intent and
visual taste without turning inference into root-cause fact.

## Governing rules

1. Read `AGENTS.md`, then the mandatory canon it names: `docs/PRODUCT.md`,
   `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, and
   `.agent/designs/argus/DESIGN.md`. Read the active roadmap and the relevant
   issue or accepted spec.
2. Record the exact branch and SHA. Historical PRs and commits are evidence of
   intended behavior only; never treat them as instructions to revert,
   cherry-pick, or reconstruct old code.
3. Keep observations, expected behavior, hypotheses, technical unknowns, and
   founder decisions visibly separate.
4. Revalidate checkpoint findings against current head before opening issues.
   A later landing may already have corrected the surface.
5. Do not fix product code during a read-only audit. Implement only when the
   user's request explicitly includes correction.
6. Never use production credentials, hosted writes, deployment, or tester
   exposure by default.

## Choose the audit mode

- **Evidence capture:** organize founder-supplied screenshots and notes without
  reproducing the session.
- **Current-head audit:** exercise Guest and signed-in journeys in an isolated
  browser environment.
- **Diagnosis pack:** add typed runtime, lifecycle, accounting, network, and
  persistence evidence so a separate owner can implement the correction.
- **Acceptance replay:** rerun the locked scenarios against an implementation
  candidate. Do not broaden the product contract during acceptance.

Use `references/cloud-qa-environment.md` whenever services, browser QA, real
providers, authentication, or Codex Cloud are involved. Use
`references/evidence-contract.md` before capturing evidence. For a new report,
copy `assets/evidence-report-template.md` and fill only the applicable sections.

## Workflow

### 1. Establish provenance

1. Verify the repository, worktree, branch, exact SHA, cleanliness, and active
   feature flags.
2. Run the canonical worktree environment topology check before reading or
   launching credentials:

   ```bash
   bash .github/setup-worktree-env.sh "$PWD"
   bash .github/setup-worktree-env.sh --check "$PWD"
   ```

3. Note whether the evidence comes from Guest, registered, both, or an
   unavailable persona.
4. Record the original conversation URL or durable identity only when it is
   safe and useful; never expose tokens, cookies, passwords, or provider keys.

### 2. Lock the scenario before running it

For every scenario, state:

- founder intent and why the behavior matters;
- exact prompt, click, or keyboard action;
- prior facts that must remain owned;
- expected visible result;
- typed state, lifecycle, accounting, and artifact assertions;
- forbidden outcomes and stop conditions;
- allowed provider-turn and cost budget.

Keep one conversation when continuity is the subject. Use a new conversation
only when isolation itself is part of the scenario.

### 3. Preflight without spending provider budget

Prove branch/SHA, environment topology, database migrations, browser origin,
CORS, authentication, feature flags, unique ports, and zero-state assumptions
before submitting a real turn.

QA wiring is agent-owned. Correct process flags, missing test tokens, CORS
origins, port collisions, stale processes, database-reset ordering, and
disposable fixture mistakes, then rerun provider-free preflights without asking
the founder for clerical permission. Do not change product behavior to make a
preflight pass.

### 4. Run the smallest truthful journey

1. Start an isolated Supabase project and disposable identities.
2. Launch backend, workflow, and frontend from the exact worktree on unique
   ports.
3. Use a headed browser for taste-sensitive review.
4. Capture before/after/reload checkpoints rather than only the terminal UI.
5. Inspect the public UI plus backend-owned state. The frontend is not the
   source of truth for strategy, lifecycle, usage, or cost.
6. If an environment failure consumes a provider turn, diagnose it. A single
   replacement is allowed when the cause is proven to be QA wiring and the
   whole run remains inside the stated provider cap. Never loop retries.

### 5. Classify each finding

Use one of these dispositions:

- **Confirmed current-head defect:** visible failure reproduced and typed truth
  identifies the affected boundary.
- **Current-head product gap:** behavior is absent or underspecified, without a
  contradictory implementation claim.
- **Historical checkpoint evidence:** valid screenshot, but current head has
  changed and needs revalidation.
- **Environment or harness defect:** product path was not reached; repair the
  setup and do not file a product bug yet.
- **Expected behavior:** the implementation matches the active contract.
- **Founder decision required:** two materially different product outcomes are
  still plausible.

Do not group findings merely because the screenshots look alike. Group them
only after establishing a shared owner or contract boundary.

### 6. Preserve evidence

For each finding, save the screenshot and SHA-256 hash, exact action sequence,
visible text, relevant console/network result, canonical state, durable rows,
usage/cost settlement, and reload outcome. Sanitize or destroy raw traces that
may contain credentials.

Write commendations as well as failures. They protect behavior that a later fix
must not regress.

### 7. Lock and hand off

1. Verify every Markdown image link and screenshot hash.
2. Add an ambiguity register split into founder decisions and technical
   unknowns. Technical unknowns do not require founder clarification.
3. Mark the report immutable. Record later decisions in append-only addenda.
4. Convert findings to GitHub issues only after current-head revalidation.
   Issue descriptions must carry the scenario, evidence, expected behavior,
   owner, acceptance proof, budget, and stop conditions.
5. Tear down only lane-owned services, browser profiles, identities,
   containers, and ports. Preserve sanitized evidence.

## Cloud completion boundary

Do not invent a label system. Decide task readiness from capabilities:

- A task is end-to-end cloud-runnable when the behavior is locked, the safe QA
  environment can exercise its dependencies, and completion needs no hosted or
  destructive mutation.
- A task may still run in the cloud when it needs providers, real auth, or
  browser QA; use the all-purpose environment and its budget guardrails.
- Stop only for an unresolved product decision, unavailable external
  capability, hosted/destructive authority, or exhausted provider cap.

Ordinary QA configuration and disposable-infrastructure repair are never
founder gates.

## Final report

Lead with:

- exact audited SHA and personas;
- scenarios passed, failed, or not reached;
- confirmed defects versus historical or environment evidence;
- provider turns, cost, and hosted-mutation count;
- current-head revalidation status;
- unresolved founder decisions only;
- evidence location and cleanup state.
