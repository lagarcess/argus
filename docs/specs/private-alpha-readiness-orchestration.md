# Private Alpha Readiness Orchestration

Status: Active coordination note
Date: 2026-06-16
Branch: `codex/private-alpha-readiness-clean`
Checkpoint: `dca0d30 docs(readiness): record provider date QA proof`
Audience: Codex release captain, bounded subagents, reviewers

## Mission

Deliver the controlled private-alpha readiness slice end to end so Argus can be
handed to two trusted private-circle users.

Use `docs/specs/private-alpha-controlled-readiness-panel.md` as the active
sprint source of truth. Use this note as the broadcast packet for subagents so
all work starts from the same checkpoint, boundaries, and verification posture.
Later docs-only evidence commits may advance the branch, but bounded agents
should treat `dca0d30` as the latest verified implementation checkpoint unless
the release captain explicitly provides a newer verification bundle.

The release captain owns prioritization, sequencing, architecture tradeoffs,
merge/deploy readiness, final browser QA, and all commits. Subagents may scout,
test, implement bounded slices, or review, but they do not own the final gate.

## No-Touch Boundaries

Do not implement or configure these slices in this readiness sprint:

- Legal/privacy/consent.
- Analytics/PostHog/product analytics activation.

Do not start future-horizon work from
`docs/specs/private-alpha-next-decision-memo.md` yet. The memo is context only
until readiness exits. Specifically do not implement Idea/Evidence/Decision
memory, broker/export handoff, voice, iOS, Research Lab, engine abstraction, or
new analytics instrumentation as part of this sprint.

The original `codex/private-alpha-readiness` worktree is quarantined. Treat it
as read-only evidence only; do not salvage code or docs from it without fresh,
focused review against this clean branch.

## Active Slices

The release captain is responsible for delivering these remaining readiness
slices:

1. Spanish backend execution.
2. Backtest trust hardening.
3. Security and feedback hardening.
4. Workflow/SRE gate.
5. Cold start and UX research readiness.

Legal/privacy/consent and Analytics/feedback remain founder-gated/no-touch for
implementation. Existing feedback paths may be verified where they are part of
Security and feedback hardening, but do not add analytics vendors or consent
surfaces.

## Subagent Protocol

Every subagent prompt must include:

- Branch/checkpoint and this orchestration note path.
- One slice goal only.
- Allowed files/directories.
- Forbidden files/directories.
- Whether the task is read-only audit, implementation, or review.
- Required verification commands.
- Expected output shape:
  - status: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`;
  - files inspected or changed;
  - findings or changes;
  - tests/checks run with exact commands and outcomes;
  - remaining risks;
  - recommended next step.

Subagents must not broaden scope. They must stop and report if they discover
work that touches no-touch boundaries, production deploys, Supabase migrations,
RLS/auth model changes, Render topology/env naming, runtime architecture, or
future-horizon product features.

## Verification Standard

Local tests prove implementation behavior. Browser QA proves product readiness.

Use focused tests first, then broaden only when risk warrants it. Any runtime,
frontend, or visible user-flow change needs browser QA before the slice is
called ready. The final gate requires a manual smoke covering login, chat,
Spanish prompt, confirmation, run, result, Quick take, Explain result, reload,
and feedback.

## Commit Discipline

Commit aggressively at cohesive checkpoints:

- one coherent slice or proof update;
- focused verification completed;
- browser QA note captured when relevant;
- no unrelated changes staged.

Use conventional commit messages. Do not accumulate broad dirty WIP across
runtime, docs, tests, frontend, security, ops, and backtest trust.
