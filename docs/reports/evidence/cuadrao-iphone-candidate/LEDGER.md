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

## Round 2 state (October 4, 2026, afternoon CT). Supersedes the section below.

**Combined candidate:** `claude/cuadrao-iphone-candidate` at
`03a33ef2be86cd86f4ad65c51d3e95a08a0e7ba8` (verification branch, not for merge).

| Component | PR | Head | Independent review | CI |
| --- | --- | --- | --- | --- |
| Release UI, pickup items, app defect fixes | [#790](https://github.com/lagarcess/argus/pull/790) | `53a4d67d6bbac3dc9d21fe79f2af685462f0ba69` | eight rounds, PASS | green at `c2b47c66`; `53a4d67d` adds evidence only |
| Household and beta invitations (stacked on #790) | [#810](https://github.com/lagarcess/argus/pull/810) | `2cd7662ae4` | four rounds, PASS at code head `18b49191`; later commits are merges | not run by CI |
| Lag fixes measured on the iPhone (stacked on #810) | [#812](https://github.com/lagarcess/argus/pull/812) | `122bb23219` | three rounds, PASS at code head `b56c56d3` | not run by CI |
| Docs batch, deletion flag-off fallback | [#808](https://github.com/lagarcess/argus/pull/808) | `a1ebf4b4f24e2778b2e9501aa3ab8d1cb8bd8c1e` | three rounds, PASS | see PR |
| Pytest gate script | [#809](https://github.com/lagarcess/argus/pull/809) | `ecd2bb5704db21f4d1ff1be3e64ce9325aa6b9c2` | two rounds, PASS | green |

Landing order: #808 and #809 independent; #790, then #810, then #812.

**Candidate verification at `03a33ef2`** (`reports/CANDIDATE-03a33ef2.md`): full
iOS UI suite, run alone: 167 tests, 119 passed, 48 skipped, 0 failed, 0
never-idle waits, 46.2 min (integration baseline: 82 passed, 5 failed, 49
waits). Debug and Release builds succeed; Release has no harness, review or
preview launch strings; client flags default false. Ten host check runners
pass, including byte-identical money formatting (12157 checks in each of nine
locales). Docs checks pass. Backend, Postgres and web were not rerun: no file
outside `ios/`, one doc and evidence changed since they passed at `4af8fced`.
Signed device build 3428 saved, not installed.

**Lag, measured on the iPhone 15** (`reports/LAG-phone*.md`, `lag/`): first
frame of Home 1.09 s to about 0.17 s; hitch time ratio during the founder's
90 s script 62.0, then 29.6, then 15.7 ms/s across builds 3425, 3426, 3427.
All fixes are repeated computation in app code with identical output. The
phone carries optimized build 3427.

**Security:** client default-grants finding assessed and filed as
[#811](https://github.com/lagarcess/argus/issues/811); record in
`SEC-default-grants.md`. Hosted production re-verified not affected on
October 4; nothing hosted was changed. No fix is written.

**Issues:** #789 closed as completed by #794 with evidence.

**Open after this round:** one-off wrong typed amount in a UI suite, not
reproduced in 3,180 keystrokes under an induced stall (instrument saved in
#790's evidence); deferred performance items with measured cost in #812; no
connected journey has run on a physical phone.

## Final state (October 4, 2026, early morning CT)

**Combined candidate:** `claude/cuadrao-iphone-candidate` at
`0408469282a4fe3c5c7857fa668544f7cff7624c`. It contains integration
`a8c37d3a182fbdb3228f6003272418e65286bc1a` and the four component heads below.
It is a verification branch. It is not for merge.

| Component | PR | Branch | Head | Independent review | CI at head |
| --- | --- | --- | --- | --- | --- |
| Release UI, pickup items, app defect fixes | [#790](https://github.com/lagarcess/argus/pull/790) | `codex/cuadrao-release-ui` | `4bb1696a3df3dcd72f652fc5ddcefd27e721c292` | six rounds, PASS at `9493ea57`; `4bb1696a` restores one file byte-identical to `cc68b341` (checked by diff) | see PR |
| Household and beta invitations on iPhone (stacked on #790) | [#810](https://github.com/lagarcess/argus/pull/810) | `claude/cuadrao-household-invites-ios` | `329fd00d49fa8200ee32a4c2373bd5299927a9e1` | four rounds, PASS at code head `18b49191`; later commits are merges of #790 | not run by CI (base is not integration) |
| Docs batch | [#808](https://github.com/lagarcess/argus/pull/808) | `claude/cuadrao-docs-issues-batch` | `876c2f8a6f7bedce6d8a61807ad65bc131315114` | two rounds, PASS | green |
| Pytest gate script | [#809](https://github.com/lagarcess/argus/pull/809) | `claude/pytest-gate-reports-failures` | `ecd2bb5704db21f4d1ff1be3e64ce9325aa6b9c2` | two rounds, PASS | green |

Landing order: #808 and #809 are independent. #790 before #810. #808 and #790
both edit one board row ("1. Trust and profile, 13 to 14"); whichever lands
second needs the resolution used in the candidate (keep the October 3 avatar
decision text and the hidden-rows link).

## Verification of the candidate

Full detail: `reports/CANDIDATE-4af8fced.md`, `reports/CANDIDATE-2520da49.md`,
`reports/W1g.md`, baseline in `reports/W4.md`. Raw logs stay on the build Mac
under `~/.claude/orchestrate/cuadrao-iphone-candidate/`.

| Check | Head it ran on | Result |
| --- | --- | --- |
| Backend full suite (Linux container) | `4af8fced` | 10231 passed, 1081 skipped, 0 failed |
| Real Postgres matrix and auth matrix, CI's Supabase CLI | `4af8fced` | 605 and 13 passed through the corrected gate script |
| Web lint, tests, build, Playwright | `4af8fced` | 2207 passed, 0 failed |
| No file outside `ios/`, two docs and evidence changed after `4af8fced` | `0408469` | confirmed by diff |
| Doc-reading tests, links, whitespace, modularity | `2520da49` | pass |
| iOS Debug and Release simulator builds | `2520da49`, Debug again at `0408469` | succeed |
| Release binary free of harness and preview launch strings; client flags default false | `2520da49` | pass |
| Full iOS UI suite, uncontended | `2520da49` | 167 tests, 117 passed, 48 skipped, 2 failed (both pass alone), 0 never-idle waits |
| Baseline full UI suite on integration, contended | `a8c37d3a` | 135 tests, 82 passed, 48 skipped, 5 failed, 49 never-idle waits |
| Split member row restored; group journey three times, receipt journey, boundary probe | `4bb1696a` (#790) | pass |
| Off-centre taps on six fixed controls | `2520da49` | pass |
| Connected walk against a live local backend with flags on | `2520da49` | all journeys pass (`walk/`) |
| Tap-target host check | `0408469` | 127 controls, 44 reviewed, 0 unreviewed |
| Signed Debug device build 3423, "Cuadrao Preview" | `0408469` | built and codesign verified; not installed (iPhone unavailable) |

After `2520da49` the only source change is
`ios/ArgusFoundation/Cuadrao/Planning/CuadraoGroupExpenseEditor.swift` restored
to its `cc68b341` content, plus one reviewed-list line. No full suite was
rerun for that one-file restore.

Not verified: any install, launch or journey on a physical phone; frame
hitches (needs the phone); universal links; TestFlight; hosted anything.

## Shared Mac

The lead was the only scheduler. Simulator tests, traces and device builds ran
under one lock. Three full UI suites overlapped from 20:23 to about 22:00 CT on
October 3 (baseline, #790, Household); their timings are contended and their
logs are kept. After that, two full suites ran, each alone, on the candidate.

## Unresolved security finding: Supabase default grants

Status: unresolved, recommended severity Medium (latent), founder to confirm
and file. Detail and a ready issue body: `reports/W6-default-grants.md`.
A database built fresh on the newer Supabase Postgres image (17.6.1.171) gives
`anon` and `authenticated` full default privileges on new `public` tables; the
CI image (17.6.1.140) does not. Seventeen early tables gain select, insert,
update and delete. All have RLS, and cross-user requests were blocked, but a
signed-in user could set `is_admin` on their own profile, reset their own usage
counter and insert a conversation without the API. The hosted project is
stricter than both (no `public` default grant row; read-only catalog check).
No fix is written. It rises to High if any database with real users is built
fresh on the newer defaults.

## Owned follow-ups (not fixed here)

- Beta gate is enforced by the server only at `/invites/access` and
  `POST /invites`; gate before `ARGUS_BETA_INVITE_GATE_ENABLED`.
- Account-scoped 404 reuses `household_not_found`; GoTrue timeout surfaces as
  401 instead of 503; revoked and unused expired invites return their quota.
- Deletion `_delete_auth_user` trusts GoTrue "not found"; the SQL-built test
  world cannot catch a misdirected Admin call. Placeholder comment says "no
  password" but GoTrue stores a generated one.
- `ARGUS_BETA_INVITES_ENABLED` and `ARGUS_BETA_INVITE_GATE_ENABLED` are not
  declared in `render.yaml` or the release profile (add to #804).
- Handoff acceptance lines (about L579 and L622) say `account_deletion_request`
  is retired; the code keeps it as the flag-off fallback. Founder to amend.
- After #790 and #808 both land: `cuadrao-profile-hidden-rows-backend.md` names
  `hiddenProfileRoutes` (now `unfinishedProfileRoutes`), and "no native flow"
  should read "no connected native flow".
- Board queue contradiction; review-gallery hand-drawn Apple button.
- Split member row is label-only by decision; a wider row beside money fields
  is a design call.
- Voice lock test flake; group journey failed once in-suite, cause unknown;
  never-idle after a context-menu alert not reproduced.
- Household minor review items (three) and the deletion UI, which stays a
  DEBUG fixture.
- Draft texts for three unfiled Lane 6 notes and the #789 closing note:
  `reports/W3.md`. Terms research for #781: `reports/W5-terms-research.md`.

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
