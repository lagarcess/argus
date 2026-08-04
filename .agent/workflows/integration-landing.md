# /integration-landing — Argus Integration Landing

Use this workflow after the founder confirms that one or more PRs have merged
into `codex/private-alpha-next`. It is repository-owned so local and cloud
agents can perform the same landing routine without depending on a locally
installed skill.

## Authority

This workflow may synchronize `codex/private-alpha-next`, reconcile active
roadmap/integration documents and fully delivered issues, audit tracked
environment templates, commit and push bounded housekeeping to integration,
and wait for exact-head CI.

It must not touch `main`, merge another PR, deploy, change hosted environments,
apply hosted migrations, expose testers, or repeat paid evals, provider-backed
browser turns, or real backtests solely because a merge landed.

## Procedure

1. Read `AGENTS.md`, `docs/specs/private-alpha-next-roadmap.md`,
   `docs/specs/private-alpha-next-integration.md`, and
   `docs/specs/private-alpha-interim-roadmap.md`.
2. Identify every newly merged PR in first-parent integration order. Record the
   PR number, PR head, integration parent, merge SHA/time, linked issues,
   accepted evidence, changed files, environment names, and exact remainder.
3. Verify each PR is `MERGED` into `codex/private-alpha-next`. For squash merges,
   compare trees instead of requiring the PR commits to be ancestors.
4. Fetch integration. Use the canonical integration checkout when it exists and
   is clean, then update it with `git pull --ff-only`. Never discard local work,
   force-push, reset, or modify another worker checkout.
5. Reconcile only what the landing made stale:
   - active roadmap and integration ledgers;
   - linked issue acceptance and closure state;
   - API/data/config documentation already affected by the PR;
   - new configuration names in tracked example files, using safe placeholders
     and never secret values.
6. Preserve accepted lane evidence. Do not reopen review or rerun expensive
   proof over unchanged surfaces. Run focused docs/config checks, inspect the
   full diff, and run `git diff --check`.
7. Commit explicit housekeeping paths with a conventional commit and push
   `codex/private-alpha-next` directly. Do not open a housekeeping PR unless the
   founder requests one.
8. Fetch again, prove a clean checkout with local HEAD equal to
   `origin/codex/private-alpha-next`, and wait for exact-head integration CI and
   private-alpha smoke to reach terminal state.

## Cloud execution and noisy handoff

A cloud agent should complete this workflow when it has a clean integration
checkout plus permission to push integration and update GitHub issues. If any
of those capabilities is missing, do not improvise or silently leave the
landing half-finished. Comment once on the merged PR when possible and repeat
this exact banner in the final response:

```text
🚨🚨🚨 FOUNDER ACTION REQUIRED — INTEGRATION LANDING NOT RUN 🚨🚨🚨
PR #<number> merged as <sha>, but roadmap/issues/env parity and exact-head
integration verification are still pending. Run the Argus integration landing
workflow from the canonical codex/private-alpha-next checkout.
```

## Completion report

Report merged PRs and SHAs, local/remote integration parity, documents updated
or archived, issues closed or intentionally retained, environment-template
changes, housekeeping commit/push, exact-head CI, and explicit confirmation
that `main`, deployments, hosted systems, and tester exposure were untouched.
