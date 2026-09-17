# 2026-09-17 production promotion

## Candidate

- Candidate SHA: `e5b6f95f8db1e8629c2219c7dadd749fee637684`
- Candidate branch: `codex/production-promotion-20260917`
- Approved integration cut / original fetched integration: `cfc1988dd80ca1a8007b8f336c107700dd57e009`.
- Last fetched integration: `cfc1988dd80ca1a8007b8f336c107700dd57e009`.
- Last fetched main: `3d189204c6a685b7f3bb1818b38e34a33d1f10de`.
- Reconciliation: none needed at preparation. The would-be merged tree is exactly the candidate tree, `f67f41155f662c016277d236d92913c2fda9cdad`; modularity passes on that tree.
- Checkpoint semantics: this SHA pins the reviewed code-plus-evidence checkpoint, not the commit that subsequently publishes this manifest update. The native eval measured `3cecda6933399e53f6ea00edc8004a88d7eefad4`; only documentation/evidence changed between it and this checkpoint. No descendant is implicitly deploy-cleared. Before deployment, record and gate the exact landed `origin/main` SHA, then bind each service readback to that SHA.
- Scope: the whole approved roadmap cut, plus sharing configuration and promotion evidence. No product code or migration SQL changed in this task.
- Validation status: Live comparison complete; founder explicitly accepted both candidate-only typed failures after reviewing their concrete effects. Awaiting staging disposition before production steps. No production migration, main promotion, or deployment performed.
- Validation surface: local deterministic checks and native provider-backed evals. No separate hosted staging surface was found.
- Promotion target: `main`, through a PR with required `ci` green; all service deploys remain manual.
- Release captain: Codex. Approver: founder, explicit task instruction on 2026-09-17.
- Rollback target: `3d98057c1e722317f0243fb96fb647771ddae484`.

Founder decisions: sharing ON; all four pending migrations approved after backup, without a maintenance window; no spend cap on promotion runs; disable Private Alpha Canary and close #614 as not fixed; deploy all three services, then perform the signed-out sharing walk. Never git stash.

The required staging choice remains pending: checklist step 12 requires an isolated database and three-service validation surface. Initial inventory found only production API/app with previews disabled and no separate Supabase branch. Opening PR #655 subsequently created isolated, data-free Supabase preview `pqpgepkpzvliyutbcwjk`; it is healthy and contains the four release migrations at their expected versions/names. The API/app/Workflow staging deployment still does not exist. The founder was asked whether to provision temporary staging or waive that gate. No waiver has been inferred.

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

Required order: complete acceptance, take the backup before applying SQL, run the production ledger gate, apply only approved missing migrations in repository order, read back ledger and affected objects, require a passing gate, promote main, rerun with `--verify-landed-ref origin/main`, then deploy API, app, workflow in that order.

- Production gate: **not run**, pending staging disposition; the founder explicitly accepted both typed failures. Gate apply behavior remains `never`.
- Production backup: **not taken**. A PostgreSQL 17.6 custom-format backup procedure with verified TLS, restricted file permissions and catalog validation is prepared locally.
- Production SQL applied: **none**. Current production ledger parity and drift are not claimed.
- Production project from the configured target: `lgdhvepyrzbnscqssgqq`.
- Approved file hashes: `docs/reports/evidence/2026-09-17-main-promotion/approved-migration-files.json`.
- Local before/after ledger evidence and affected-object readback are retained in the evidence directory; they are explicitly not production clearance.

| Repository order | Migration | Classification | Approved handling |
| --- | --- | --- | --- |
| 1 | `20260912190000_share_calculation_receipts.sql` | destructive | Widen excerpt kind check; backup, no maintenance window. |
| 2 | `20260913213100_admit_readout_route_receipt_tier.sql` | destructive | Widen receipt tier check to readout; backup, no maintenance window. |
| 3 | `20260913230000_release_research_guest_claim.sql` | contract-replacing | Preserve claim signature, add guest-refund function, retain service-role-only execution. |
| 4 | `20260914120000_share_plain_answer_receipts.sql` | destructive | Widen excerpt kind check to answer; backup, no maintenance window. |

Local readback: 79/79 migrations match with no missing, unexpected, name or content drift. Both widened constraints are present. Claim/release functions are SECURITY DEFINER and executable by service_role, not anon/authenticated. Rollback retains widened checks and compatible functions; do not narrow checks after new-kind rows exist.

## Deploy Proof

No release deploy has been attempted. Initial readback is retained in `docs/reports/evidence/2026-09-17-main-promotion/deploy-before.json`; fresh readback at 2026-09-17 23:10 UTC is `docs/reports/evidence/2026-09-17-main-promotion/final-hosted-readback.json`. No service changed.

| Service | Observed deployed commit | Status |
| --- | --- | --- |
| `argus-api` | `3d98057c1e722317f0243fb96fb647771ddae484` | live |
| `argus-app` | `3d98057c1e722317f0243fb96fb647771ddae484` | live |
| `argus-backtests` | `3d98057` ready-version prefix | ready, version `wfv-dajijpbm8hqs738ed7i0` |

Render MCP was reached through the repository-configured endpoint and credential. It exposes API/app deployment tools but no Workflow operations; the repository's Workflow release command uses Render's Workflow API through its CLI. This capability gap is recorded, not represented as a completed deploy.

## Environment Proof

- Expected mode: `real-workflow`.
- Release profile hash: `71659a53a4c39b129c62ab0cb42068205be3a78d60c229f95898fe64353f3733`.
- `ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED=true` and `NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED=true` agree in Blueprint, release profile and declared environment example. Live sharing has not been enabled.
- API/app were observed with `autoDeployTrigger=off`; the profile retains manual mode for all three services.
- Hosted environment fingerprints, workflow effective-provider proof, warmup, guest controls/cleanup and post-deploy audit remain pending. No existing identity or guest workspace was modified for QA.

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
| Hosted staging / production acceptance | Not performed. |
| Required hosted CI / final review | PR #655: all real push CI jobs passed at `e5b6f95f`; draft-event jobs skipped. First Codex review identified the stale candidate pin; this documentation update addresses it. Delta review and final-head CI remain pending. |

Resolved setup failures: the initial SciPy 1.15.3 macOS wheel could not import `scipy.linalg`; the official macosx_12_0_arm64 wheel at the same locked version fixed both imports. Supabase CLI 2.117.0 created broader local grants and caused four permission-test failures (391 other cases passed). Rebuilding only the disposable stack with CI-pinned 2.109.0 restored expected grants and the full matrix passed. The first browser-storage attempt collided with local port 3100; a separate port passed. No product code was changed for these setup failures.

Canary: workflow 298408697 was read back `disabled_manually`; issue #614 was closed with `state_reason=not_planned` on 2026-09-17. **Not fixed.** The founder retired the canary for this release. No canary success or scheduled follow-up is claimed.

## Release Decision

- Decision: **IN PROGRESS; NOT YET PROMOTED**. Founder explicitly accepted both candidate-only typed failures for the pinned cut after the full comparison. Staging disposition remains pending.
- Pending: staging choice, production backup/migrations/gate, release PR/CI/review, landed-ref gate, three-service deploy and hosted verification.
- Signed-out sharing walk: not performed because this candidate is not deployed. Planned check: one money question, publish its answer, open in a fresh signed-out session, start a follow-up; retain observed text and screenshots, then verify revocation if completing the full sharing acceptance gate.
- Tester invitations/public exposure changes: none.
- Rollback owner: founder/Codex within the explicit promotion authority; restore the prior code and sharing posture while retaining compatible widened schema.
- Cleanup: owned local Supabase stack and baseline checkout remain available for the ongoing release; operator dotenv link is temporarily outside automatic discovery and will be restored.

## Privacy Notes

No production conversation, user, run or job rows were read. No production backup or browser transcript has been published. Native eval evidence contains authored fixture scenarios and the harness's retained/redacted output, not customer conversations. Credentials remain in ignored local files; the evidence directory was scanned against operator credential values with zero matches. Backup contents, tokens, cookies and auth storage must never be committed.
