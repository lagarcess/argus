# Cuadrao iPhone candidate: coordination ledger

Lead: Claude (took over from GrokTeam, October 3, 2026). Founder: Lucas, who
approves every merge. Source handoff:
[PR #790 comment](https://github.com/lagarcess/argus/pull/790#issuecomment-5975107437).
This ledger records owners, branches, exact commits, dependencies, evidence and
blockers. It grants no merge, deployment or hosted change.

## Verified references at takeover

| Ref | Commit | State |
| --- | --- | --- |
| Integration `codex/private-alpha-next` | `a8c37d3a182fbdb3228f6003272418e65286bc1a` | Matches the handoff. No newer commit after fetch. |
| PR #790 `codex/cuadrao-release-ui` | `ad6a81723509b8e868155344a803c45b02353cf7` | Matches the handoff. Conflicts with integration in `.agent/designs/cuadrao/DESIGN.md` only. |
| Coordination branch `claude/cuadrao-iphone-testing-226f69` | starts at `a8c37d3a` | Holds this ledger and the final combined candidate record. |

No origin branch has a commit newer than the integration tip.

## Units

| Unit | Owner | Branch | Base | Head | Depends on | State |
| --- | --- | --- | --- | --- | --- | --- |
| W1 Reconcile PR #790 | worker W1 | `codex/cuadrao-release-ui` | merge of `a8c37d3a` into `ad6a8172` | pending | none | running |
| W2 Household invitations on iPhone | worker W2 | `claude/cuadrao-household-invites-ios` | W1 merge commit | pending | W1 merge, shared invitation views | running |
| W3 Docs batch, Profile backend list, issue triage, #789 check | worker W3 | `claude/cuadrao-docs-issues-batch` | `a8c37d3a` | pending | small overlap with #790 docs | running |
| W4 Baseline verification | worker W4 | detached `a8c37d3a` (no commits) | `a8c37d3a` | n/a | none | running |
| W5 Terms and retention research for #781 | worker W5 | none (report only) | n/a | n/a | none | running |
| Combined candidate | lead | `claude/cuadrao-iphone-candidate` (to create) | integration + W1 + W2 + W3 | pending | W1, W2, W3 | not started |

## File ownership

- W1: `ios/**` except W2's paths, `.agent/designs/cuadrao/DESIGN.md`,
  `docs/reports/evidence/cuadrao-release-ui/**`, `docs/reports/evidence/784/README.md`.
- W2: `ios/ArgusFoundation/Household/**`, new invitation wiring, its tests,
  `docs/reports/evidence/cuadrao-household-invites/**`. Reuses, does not own,
  `ios/ArgusFoundation/ReleaseUI/Invitations/**`.
- W3: `docs/**` outside W1's paths. No code.
- Lead: this folder, shared contracts, dependency order, final reconciliation.

## Standing gates (not opened by this work)

Merges, deployment, hosted flags, hosted migrations, secret rotation, legal
publication, external messages and paid provider tests need Lucas. The
share-pages decision and the destructive migration `20261003150100` approval
stay later release gates. No deletion-retry schedule is created. Feature
enablement blockers #800, #805, #806, #784 and #778 stay open.

## Evidence and results

Filled in as units report.
