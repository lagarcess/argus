# 2026-09-17 production promotion

## Candidate

- Candidate SHA: `a9286b21886eb03df7a21f2f4b7d5e79af570679`.
- Candidate branch: `main`; promoted through PR [#655](https://github.com/lagarcess/argus/pull/655).
- Approved integration cut, original base and current integration: `cfc1988dd80ca1a8007b8f336c107700dd57e009`.
- Pre-merge PR head: `0c47cf6ddf61568f6f496535bfa51885461bf49a`.
- Landed parents: `3d189204c6a685b7f3bb1818b38e34a33d1f10de` and `0c47cf6ddf61568f6f496535bfa51885461bf49a`.
- Landed tree: `4eb020142aae2505b5c45e17c7c8f9cae735d173`, identical to the CI-tested pre-merge candidate. Integration did not advance; no reconciliation or semantic overlap occurred. Modularity passed on this merged tree.
- Scope: full approved roadmap cut plus sharing configuration and release evidence. No product code or migration SQL changed in this promotion task.
- Native live-eval measured SHA remains `3cecda6933399e53f6ea00edc8004a88d7eefad4`. Later changes are documentation/evidence only. Clean scoped Codex review at `2523e3a3`, zero unresolved threads; captain reviewed the subsequent documentation/waiver delta with no findings. Both candidate CI runs passed at `0c47cf6d`; main CI [35297005285](https://github.com/lagarcess/argus/actions/runs/35297005285) passed at `a9286b21886eb03df7a21f2f4b7d5e79af570679`.
- Deployment complete: API/app live, Workflow ready; production migration gate passed before and after landing. Production sharing walk completed with the accepted follow-up misread and an additional raw calculation-label display defect recorded below.
- Release captain: Codex. Approver: founder, explicit instructions on 2026-09-17 America/Chicago; production operations occurred on 2026-09-18 UTC.
- Rollback target: `3d98057c1e722317f0243fb96fb647771ddae484`. Retain widened compatible schema when rolling code back.
- This manifest's publication commit records the deployment of `a9286b21886eb03df7a21f2f4b7d5e79af570679`; it is not itself a new deployment candidate. Production main was read back at the landed SHA after the walk.

Founder decisions: sharing ON; backup and hosted staging explicitly waived; three prior observed typed/follow-up failures accepted; all three service deploys authorized; canaries skipped and #614 closed as not fixed. No spend cap. Never git stash.

## Production authorization after local acceptance

Founder accepted the local walk and explicitly resumed production promotion on 2026-09-17 (America/Chicago):

- **Database backup waived for this promotion. No backup will be taken.** This explicitly replaces the earlier backup-before-SQL requirement for these four approved migrations.
- **Hosted staging services waived.** The completed disposable Docker rehearsal is accepted for this promotion; no staging services will be provisioned.
- **Shared-link follow-up misread accepted as a known gap, not a blocker.** The $450/month reply asking for investment assets remains unfixed; this waiver is additional to the two earlier accepted typed failures.
- Production migration gate/readback, four migration applications, landing the approved `cfc1988d` roadmap cut plus already-approved sharing configuration on main, and manual deployment of API, app and backtests are explicitly authorized. Preserve existing reviewed code/eval lineage; record the actual landed commit and re-gate it before deploying.
- Repeat one production money/share/signed-out/follow-up walk. Canaries stay skipped. No git stash.

Status: production promotion completed under these explicit waivers. The previous local stop is superseded. Deployment and schema proof are recorded below.

## Disposable Docker Validation (prior checkpoint)

- Exact clean app/API source: `cfc1988dd80ca1a8007b8f336c107700dd57e009`; both sharing flags enabled through environment overrides. Next.js production build passed. API/app ran locally against a fresh Docker Supabase database with real Auth/Postgres persistence. Workflow dispatch was disabled; no staging services provisioned.
- Four migrations applied once in repository order after initializing the earlier 75. Final readback **79/79**, no missing/unexpected migrations, name or content drift. Widened checks and SECURITY DEFINER/service-role-only claim/release permissions matched. See `docs/reports/evidence/2026-09-17-main-promotion/local-sharing-walk/migrations-after.json` and `objects-after.json`.
- Money question: starting at $1,200, saving $300 monthly without interest until $3,000. Correct answer: **six months**. Normal local signup preserved the guest answer and exposed the owner sharing control; preview and publication succeeded.
- Signed-out public link: separate browser session with **zero cookies and no auth-token storage keys** displayed the question, answer and calculation inputs. English and Spanish public pages passed; Spanish UI/calculation labels localized while immutable authored text stayed English.
- Follow-up: “What if I save $450 per month instead?” opened a distinct guest chat with the shared snapshot attached, but replied “Which asset or assets would you invest in monthly with that $450, and over what time period would you like to test it?” Expected four months. **Follow-up answer continuity failed.** No retry/fix was performed. At this checkpoint it was not covered by the earlier two-case waiver; the subsequent production authorization explicitly accepted it.
- Console: public English/Spanish pages each had zero errors and a font preload warning. Initial signed-out chat logged four 401s; the reader's guest-chat transition logged three 401s before successful guest/fork/stream requests. Signed-in sharing had zero errors. Font preload warnings remained; no uncaught JS exception appeared.
- Evidence/report/screenshots: `docs/reports/evidence/2026-09-17-main-promotion/local-sharing-walk/README.md`. Two user questions, 13 provider receipts, **$0.04288399 reported**. No canary run.
- Cleanup: all three owned browser sessions closed; API/web listeners stopped; owned Supabase containers and data volumes removed. Exact-build worktree and local credential/status files removed after evidence preservation. No production change or git stash.


## Live Eval Evidence

- Live eval scorecard: `docs/reports/evidence/2026-09-17-main-promotion/candidate-scorecard-3cecda69.json`
- Live eval measured SHA: `3cecda6933399e53f6ea00edc8004a88d7eefad4`
- Candidate result: **70 passed, 3 failed**, zero expected failures, unexpected passes, skipped cases, or infrastructure errors. Native pytest exit 1 because of the three failures.
- Candidate fixture identity: 73 cases; SHA-256 `ca6ff99bf46bc1ea4a7f02088e54ed27fef685b1c02eb711f935456e47dcbe22`.
- Candidate usage: 381 route receipts; 359 with reported cost totaling **$1.575079614852**; 22 have no reported cost. This is not a complete billed-spend total.
- Candidate duration: native pytest **2379.17 seconds**.
- Baseline eval scorecard: `docs/reports/evidence/2026-09-17-main-promotion/baseline-scorecard-3d98057c.json`
- Baseline result: **68 passed, 3 failed**, zero other statuses; native pytest exit 1, **2203.35 seconds**. 363 route receipts, 342 reported costs totaling **$1.555157101776**, 21 costs unreported. Native schema-v2 original is retained unchanged as `docs/reports/evidence/2026-09-17-main-promotion/baseline-native-original-schema2.json`.
- Full case comparison: `docs/reports/evidence/2026-09-17-main-promotion/full-suite-comparison.json`.
- Baseline measured SHA: `3d98057c1e722317f0243fb96fb647771ddae484`; 71 native fixtures, digest `a48b14730a14578639e41dd27a15f27e3981208298fa7e68e477da7b159bcf6b`.
- Candidate-only additions are the English and Spanish explicit-end-date/year-qualifier cases; both passed. Existing fixture differences are only a DCA comment, not changed assertions.
- Targeted A/B baseline: `docs/reports/evidence/2026-09-17-main-promotion/spanish-scenario-ab-baseline.json`, measured SHA `3d98057c1e722317f0243fb96fb647771ddae484`; empty-table defect **0/10 (0%)**.
- Targeted A/B candidate: `docs/reports/evidence/2026-09-17-main-promotion/spanish-scenario-ab-candidate.json`, measured SHA `3cecda6933399e53f6ea00edc8004a88d7eefad4`; empty-table defect **0/10 (0%)**.
- A/B order: `docs/reports/evidence/2026-09-17-main-promotion/targeted-execution-order.json`; ten serial rounds, baseline then candidate, no manual retries. All 20 native attempts, original judge output, and text-based defect reviews are embedded in the side documents.
- The baseline published research in 4/10 attempts, had 5 research-publication failures and 1 routing refusal. The candidate published in 5/10, had 3 publication failures and 2 routing refusals. Among published answers the specific defect was also 0/4 baseline and 0/5 candidate. This small sample does not prove equivalence or general reliability.
- A/B reported receipt cost: baseline **$0.08631723848** (2 unreported), candidate **$0.18516206244** (7 unreported); sum of native case durations **2177.61 seconds**. All promotion live measurements total **$3.401716017548 reported**, 827 route receipts with 52 unreported costs. Provider billing may include costs not represented here.
- Candidate A/B attempt 7's judge alleges English fallback and a raw recovery code, but the retained answer is Spanish and contains no such code. These allegations are not confirmed defects; its research publication did fail.

Candidate failures and current comparison:

| Case | Observation | Disposition |
| --- | --- | --- |
| `compound_benchmark_start_date_preserves_confirmation_issue_339` | The requested April 1 start remained March 2, including the launch payload. | Baseline passed; candidate-only typed failure. Founder explicitly accepted this failure for the pinned cut on 2026-09-17; retained as unresolved product debt. |
| `dca_capital_semantics_only_have_amount_is_ceiling_issue_455` | Expected `capital_amount` in missing fields; actual list empty. Both builds stop for unsupported-budget clarification, with no launch payload; candidate alone records $5,000 as supplied capital. | Baseline passed; candidate-only typed failure. Founder explicitly accepted this failure for the pinned cut on 2026-09-17; retained as unresolved product debt. |
| `messy_spanish_future_performance_nvda_cruce_dorado` | `scenario_framing` failed: prose promised a scenario table but left it empty; the card did carry low/base/high values. | Baseline also fails the case, but on routing: it declines a future scenario and offers historical tests. Baseline prose passes. Ten paired attempts found the original empty-table defect 0/10 on each side. No measured increase established for that specific prose defect; research/routing failures retained separately. |

Baseline-only failures: `capability_honesty_future_performance_btc_regression` and `capability_honesty_future_performance_nvda_golden_cross` both expected published research but received `published=false`; the candidate passed both. Research-answer publication owns the existing failures; no recurrence rate is inferred from one run.

Typed side-by-side facts: `docs/reports/evidence/2026-09-17-main-promotion/typed-failure-comparison.json`. These are observed failures, not a root-cause diagnosis or a claimed recurrence rate. Founder answer after reviewing both failures: "Explicitly accept both failures". This overrides the runbook's default no-promotion rule for these two cases only; it does not claim a fix. Runtime interpretation/edit and DCA contract owners need founder-assigned follow-up; historical #339 and #455 remain closed and were not reopened.

The native driver and configuration observer are retained under the evidence directory. Both trees passed offline checks for native imports, SHA, fixture inventory and actual resolved model/flag parity before measurement. The older baseline lacks configuration-bearing scorecards, so the external observer preserves its original artifact and records actual configuration before/after; it does not insert desired profile values as evidence.

Literal candidate invocation (from the candidate root):

```bash
.venv/bin/python /private/tmp/argus-promotion-observer-7e84/native_driver.py \
  --tree /Users/garces/.codex/worktrees/7e84/private-alpha-next \
  --expected-sha 3cecda6933399e53f6ea00edc8004a88d7eefad4
```

The driver invokes the native `tests/evals/test_measurement_eval_live.py` with `--confcutdir=tests/evals -q --no-cov -s`. This excludes the general mocked fixture that would force release flags to other values. Both sides use `APP_ENV=development` for a native local run, explicit live market/asset providers, and their own release-profile models/booleans. No production database credential is supplied to these evals. Before the paid run, an initial startup attempt stopped on hosted traffic-class routing before any LLM request; its first typed action case and startup failure are retained locally. No paid suite retry was performed.

## Production Migration Gate

- Production target: `lgdhvepyrzbnscqssgqq`, verified session-pooler target with `sslmode=verify-full` and the configured CA certificate.
- **Backup: explicitly waived by founder; no backup taken. Hosted staging: explicitly waived.**
- Before gate at `41a9ebef`: expected exit 1, only `missing_candidate_migrations`, exactly the four approved files. Historical ledger fingerprint matched the checked-in reconciliation.
- Applied all four files in repository order in one transaction at **2026-09-18 01:41:15 UTC**, with canonical version/name/statement-array ledger entries, 10-second lock timeout and 120-second statement timeout. SQL and ledger entries committed atomically. No SQL text changed. Initial operator-script field lookup failed before opening a connection; corrected before the sole application transaction.
- After gate at `0c47cf6d`: exit 0, `status=pass`, no missing migrations or new name/content drift.
- After landing: gate with `--verify-landed-ref origin/main` at `a9286b21886eb03df7a21f2f4b7d5e79af570679` passed at **01:51:34 UTC**, before any deploy-capable operation.
- Final comparison: 79 candidate files, 81 production ledger rows, zero missing, zero current name/content drift. Seven historical ledger-only rows and five historical candidate-only identities account for the row surplus; they match the committed historical reconciliation. No historical ledger rows were rewritten.
- Evidence: `docs/reports/evidence/2026-09-17-main-promotion/production/production-{before,apply,after,landed}.json`, `production-objects-after.json`, and the existing approved-file hash record.

| Order | Migration | Result | Handling |
| --- | --- | --- | --- |
| 1 | `20260912190000_share_calculation_receipts` | committed | Widen excerpt kind check; backup waived, no maintenance window. |
| 2 | `20260913213100_admit_readout_route_receipt_tier` | committed | Widen tier check for readout; backup waived, no maintenance window. |
| 3 | `20260913230000_release_research_guest_claim` | committed | Compatible claim replacement and guest-refund function; backup waived. |
| 4 | `20260914120000_share_plain_answer_receipts` | committed | Widen excerpt kind check for plain answers; backup waived, no maintenance window. |

Object readback matched the local rehearsal: excerpt kinds include backtest/research_answer/calculation/answer/mixed; route tiers include utility/chat/structured/context/readout. Claim and release functions are SECURITY DEFINER, executable by service_role, not anon/authenticated. Do not narrow these checks during code rollback after new-kind rows exist.

## Deploy Proof

All three services were released from landed main `a9286b21886eb03df7a21f2f4b7d5e79af570679`.

| Service | Deployed commit proof | Deployment/version | Terminal status |
| --- | --- | --- | --- |
| `argus-api` | full SHA `a9286b21886eb03df7a21f2f4b7d5e79af570679` | `dep-dam9irgu01pc73erp4i0` | live, 01:54:39 UTC |
| `argus-app` | full SHA `a9286b21886eb03df7a21f2f4b7d5e79af570679` | `dep-dam9iumk1f9s73eoe450` | live, 01:54:52 UTC |
| `argus-backtests` | release explicitly pinned to the same full SHA; ready version reports `a9286b2` | `wfv-dam9k6942hec738qgjf0` | ready; release command exited 0 |

Render MCP environment updates started API then app deployments automatically, twelve seconds apart. Both finished before the Workflow release began. This overlapped the API/app builds rather than waiting for API completion before starting the app; no version mismatch resulted. Render MCP has no Workflow operation, so the repository's `workflow-release <full SHA>` command used Render CLI/API for backtests. Workflow API exposes a commit prefix, not an independent full-SHA field; retain the explicit release-command receipt alongside ready-version proof.

Resolved operations: the first MCP writes/deploy request failed without mutation because the workspace was unspecified. Retried with the verified `argus-prod` workspace `tea-d5rdkfk9c44c73e7a1ig`. A separate API trigger added redundant queued deploy `dep-dam9j1fa9cic73dddgtg`; it was cancelled. CLI cancellation initially found an expired saved login, then succeeded with the existing valid MCP credential. The active API/app/Workflow deployments did not fail.

Evidence directory: `docs/reports/evidence/2026-09-17-main-promotion/production/`, including `api-status.json`, `web-status.json`, `production-workflow-status.txt`, `production-workflow-release.txt`, `production-merge.json`, and `api-redundant-cancelled.json`.

## Environment Proof

- Release mode: `real-workflow`.
- Release profile hash: `71659a53a4c39b129c62ab0cb42068205be3a78d60c229f95898fe64353f3733`.
- Both sharing flags are `true` in Blueprint, release profile, declared example contract and hosted API/app environment. The production browser exercised the enabled build.
- Before audit found only the two sharing flags off. After MCP updates, release-config audit passed: `status=ready`, `workflow_env_status=ready`, `autodeploy_status=ready`; all three deploy triggers remain manual.
- Environment fingerprint: `294a506ff6963905cc936d234f7ae4604baced5e88c52f6497b562a141952518`.
- Workflow environment fingerprint: `3a20406b42ea9f6fc3640cac1478502e483eb1a6602fd1d7399db12bcf259747`.
- `warmup-render.sh --expect-mode real-workflow` exited 0: API health, protected readiness, frontend response, stale-job scan, environment audit and deployed Workflow runtime proof passed. Effective provider proof: `live_provider`, `ready`. This was the runbook warmup, not either skipped canary suite.
- Production CAPTCHA remained enabled. Temporary registered and guest QA identities were least privilege, sessions revoked and accounts deleted after the walk. The synthetic shared link was revoked and its public payload removed from readback.

## Gate Evidence

Evidence summary: `docs/reports/evidence/2026-09-17-main-promotion/verification.txt`.

| Gate | Result |
| --- | --- |
| Required setup | Passed, Python 3.10.20, Poetry/Bun pinned by setup. |
| Ownership | No branch-specific policy; explicit skip. |
| Ruff / modularity | Passed; would-be merged tree equals candidate tree. |
| Full backend | 8,958 passed, 614 opt-in skips; one failure because the new manifest had no live evidence yet. Final focused document/evidence gates passed: 162 tests, zero skips. The actual new manifest and both A/B identities/configurations also passed direct validation. |
| Mocked evals | 272 passed. |
| Frontend lint / tests / build | Passed; 2,061 tests. |
| Browser storage disclosure | 2 passed. |
| Full local smoke | `verification_status=ready`; workflow dispatch stays off. |
| Real migration gate tests | 49 passed, zero skips. |
| Real PostgreSQL matrix | 395 passed, zero skips. |
| Real anonymous Auth matrix | 12 passed, zero skips. |
| Local Docker / production walk | Local rehearsal accepted with waived follow-up gap. Production share/create/read/follow-up/revoke walk completed; known misread recurred; raw calculation-label display defect recorded. |
| Required CI / review | Both candidate CI runs passed at `0c47cf6d`; landed main CI passed at `a9286b21`. Scoped Codex review at `2523e3a3` retained with zero unresolved threads; later documentation/waiver delta reviewed clean by captain. |

Resolved setup failures: the initial SciPy 1.15.3 macOS wheel could not import `scipy.linalg`; the official macosx_12_0_arm64 wheel at the same locked version fixed both imports. Supabase CLI 2.117.0 created broader local grants and caused four permission-test failures (391 other cases passed). Rebuilding only the disposable stack with CI-pinned 2.109.0 restored expected grants and the full matrix passed. The first browser-storage attempt collided with local port 3100; a separate port passed. No product code was changed for these setup failures.

Canary: workflow 298408697 was read back `disabled_manually`; issue #614 was closed with `state_reason=not_planned` on 2026-09-17. **Not fixed.** The founder retired the canary for this release. No canary success or scheduled follow-up is claimed.

## Release Decision

- Decision: **DEPLOYED; KNOWN GAPS AND OBSERVED DISPLAY DEFECT RECORDED.** Founder authorized production and accepted the two native typed failures plus the shared-link follow-up misread. These remain unfixed. No product-code patch or paid question retry was made during deployment.
- **Production walk:** asked the same $1,200 + $300/month savings question; received the correct six-month answer. Previewed and published it, opened it in an independent browser with zero cookies/auth-storage keys, and sent “What if I save $450 per month instead?” The new guest chat carried the snapshot, then replied: “Got it, $450 per month. To run that test, which asset or assets would you like to invest in, and over what date range?” Expected four months. This reproduces the explicitly accepted gap.
- Additional display defect: `months_to_goal: 6` appeared in prose and persisted into the shared page, beside the otherwise correct result. Recorded for follow-up, not claimed fixed or separately founder-waived.
- English and Spanish public views worked. Spanish chrome, calculation labels and follow-up composer localized; immutable authored question/answer stayed English. Owner-side revocation returned success; anonymous readback was HTTP 200 with `status=revoked` and `payload=null`, and the Spanish browser showed the tombstone.
- Console: owner zero errors/five font preload warnings; public English before follow-up zero errors/one font warning; final reader five errors/six warnings, comprising three pre-auth API 401s plus two Cloudflare challenge console errors, with font/challenge warnings. Guest/fork/stream still succeeded. Spanish page zero errors/one font warning before revocation. No uncaught application exception observed.
- Browser evidence: `docs/reports/evidence/2026-09-17-main-promotion/production/sharing-walk/`; report `production/README.md`. Two production questions, 13 cost-ledger entries, all priced, **$0.04631143 reported**. Workflow/build compute is not included in that LLM ledger total.
- Canaries: both skipped by founder direction; workflow remains `disabled_manually`; #614 remains CLOSED / NOT_PLANNED, not fixed. No scheduled canary follow-up created.
- Cleanup: test share revoked; both test sessions globally signed out; registered/anonymous QA accounts deleted and absence confirmed; all three browser sessions closed. Only synthetic QA data was targeted. No tester invitations or email delivery. No git stash.
- Rollback: restore `3d98057c1e722317f0243fb96fb647771ddae484` and the prior sharing posture if directed, keeping the compatible widened schema. No rollback was performed.

The earlier preproduction checkpoint remains historical evidence, superseded by this final deployment record. This manifest is published on the promotion-record branch; main remains pinned to the deployed commit.

## Privacy Notes

Production reads were limited to schema/ledger/release metadata and the two synthetic QA conversations' ownership/cost aggregates. No existing customer conversation or model output was read. Screenshots and snapshots contain only authored QA prompts and responses. Credential values, auth cookies, storage state, passwords and private session handoffs are excluded from committed evidence and removed locally after cleanup. Third-party challenge URLs in console/request evidence have their path identifiers redacted. No database backup was taken because the founder explicitly waived it.
