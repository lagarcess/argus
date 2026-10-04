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

State at October 3, 2026, late evening CT. Heads are exact at the time of writing.

| Unit | Branch | Base | Head | PR | Review | State |
| --- | --- | --- | --- | --- | --- | --- |
| W1 Reconcile #790 | `codex/cuadrao-release-ui` | merge `ad0532f11` of `a8c37d3a` | `e9195b587620d9611ef1f22d90c90975b03c48d6` | [#790](https://github.com/lagarcess/argus/pull/790) | independent review of `e9195b58` running | ten pickup items done; two failing UI tests in its own screens and seven unclassified ones being worked by a second worker |
| W2 Household invitations on iPhone | `claude/cuadrao-household-invites-ios` | `ad0532f11`, then merge of `c82f093d5` | `6fb15a01` | none yet | reviewed at `6fb15a01`: 1 P1, 4 P2, 7 P3; fix worker running | stub-verified; live local round trip running |
| W3 Docs batch | `claude/cuadrao-docs-issues-batch` | `a8c37d3a` | `876c2f8a6f7bedce6d8a61807ad65bc131315114` | [#808](https://github.com/lagarcess/argus/pull/808) | PASS, two rounds, pinned | CI green, ready for founder merge decision |
| W4 Baseline verification | detached `a8c37d3a` | n/a | n/a | n/a | n/a | backend, real Postgres, GoTrue, web done; baseline UI suite and lag traces finishing |
| W5 Terms and retention research | none | n/a | n/a | n/a | n/a | done, report only; #781 stays draft |
| W6 Default grants and gate script | `claude/pytest-gate-reports-failures` | `a8c37d3a` | `ecd2bb5704db21f4d1ff1be3e64ce9325aa6b9c2` | [#809](https://github.com/lagarcess/argus/pull/809) | PASS, two rounds, pinned | CI running |
| W7 Live local invite round trip | none | reads `6fb15a01` | n/a | n/a | n/a | running |
| Combined candidate | `claude/cuadrao-iphone-candidate` (to create) | integration + #790 + Household + #808 + #809 | pending | none | pending | waits on W1 and W2 fix heads |

## Shared Mac

The lead is the only scheduler. Simulator tests, traces and device builds run
under one lock. Three full UI suites overlapped from 20:23 to about 21:30 CT on
October 3 (baseline, #790, Household); their timings are contended and their
logs are kept. No further full suite runs except one on the combined candidate.

## Unresolved security finding: Supabase default grants

Status: unresolved, recommended severity Medium (latent), founder to confirm.
A database built fresh on the newer Supabase Postgres image (17.6.1.171) gives
`anon` and `authenticated` full default privileges on new `public` tables; the
CI image (17.6.1.140) does not. Seventeen early tables gain select, insert,
update and delete. All have RLS, and cross-user requests were blocked, but a
signed-in user could set `is_admin` on their own profile, reset their own usage
counter and insert a conversation without the API. The hosted project is
stricter than both (no `public` default grant row; read-only catalog check).
No fix is written. It rises to High if any database with real users is built
fresh on the newer defaults.

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
