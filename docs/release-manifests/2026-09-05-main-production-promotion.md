# Private Alpha Production Promotion, 2026-09-05

## Candidate

- Candidate SHA: `e3b98690b238bb292e161a9a25554cd9cfdbc19d`
- Source branch: `codex/private-alpha-next`
- Promotion target: `main`
- Landing method: founder-owned GitHub merge commit, never squash or rebase
- Approver: founder
- Current production readback: `7d8ace45e4ac717ffbfaf222cf66544c3355df6f` on the API and app; Workflow ready version `7d8ace4`.
- Rollback target: `c7802b37f39772a1216514e37fb6ff2b63142181`
- Baseline selection: the founder explicitly requested `c7802b37f39772a1216514e37fb6ff2b63142181`. Live Render and fetched `origin/main` instead show `7d8ace45e4ac717ffbfaf222cf66544c3355df6f`. Clarification was requested before the baseline ran; without a revised instruction, the original named SHA was retained. This is a historical baseline comparison and does not establish non-regression against the currently deployed build.
- Commits ahead: 59 from current production, 86 from the dispatch's older baseline.
- Measured-tree relationship: evidence and manifest additions only are planned after measurement. No product changes are authorized in this promotion.

## What ships

- #544: atomic guest and shared research allowance claim.
- #543: durable pre-start backtest failure receipts.
- #547: guest conversion modal restored.
- #548: workflow-proof operation scope and historical seed-row reclassification.
- #549: eval assertions cover the delivered result of a turn.
- #550: asset-preflight rename.
- #551: localized readers for persisted artifacts and execution assumptions.

Flags and release configuration changes: none.

## Production Migration Gate

Intended order: candidate smoke, production migration gate, review and apply only the two pinned SQL files in repository order, read back affected objects, rerun the gate to pass, open promotion PR, founder merge, checkout landed SHA, rerun steps 1 and 2 and the landed-ref gate, then request founder-directed deployment. No deploy-capable operation precedes schema parity.

- Before report: `docs/reports/evidence/2026-09-05-main-promotion/production-migration-gate-before.json`
- Before status: `blocked`, solely `missing_candidate_migrations`.
- Before ledger: 68 rows; latest version `20260822000000`.
- After report: `docs/reports/evidence/2026-09-05-main-promotion/production-migration-gate-after.json`
- After status: `pass`, checked `2026-09-05T05:04:23.779023Z`.
- After ledger: 70 rows; latest version `20260905000000`.
- Missing migrations, current name drift, and current content drift after application: zero.
- Historical ledger variance: unchanged and matched the gate's committed reconciliation; 68 candidate files, 70 applied rows, seven historical unmatched applied identities, five historical unmatched candidate identities.
- Production target: project `lgdhvepyrzbnscqssgqq`, session pooler `aws-1-us-east-2.pooler.supabase.com`.
- Transport: `sslmode=verify-full`, CA at `~/.argus/prod-ca-2021.crt`.
- Gate access: read-only. Application was a separate, founder-authorized operation.
- Landing verification: `not_requested_pre_landing`; no deployment is authorized by this pre-landing report.

### Migration classification and application

| Repository order | File SHA-256 | Automated classification | Reviewed classification |
| --- | --- | --- | --- |
| `20260903000000_claim_research_usage.sql` | `ba47070ad1ca3eff0f0a1ef790376b0c2b522cca3b009e25fa7d08b3306cd298` | contract-replacing | additive: the exact function did not exist in production |
| `20260905000000_workflow_proof_jobs_leave_conversations.sql` | `ffb79be4bed36fb343ae4e81830e120c2b6620f1944fa0099774890578134759` | destructive, due to DROP CONSTRAINT | compatible constraint expansion and bounded data correction |

The first migration creates `public.claim_research_usage(text,text,text,integer,integer)`. It validates inputs, locks the shared daily counter before the optional guest counter, and increments both or neither. The function is security definer, has fixed `search_path=public` and UTC timezone, and grants execution only to `service_role` and the owner. Existing counter rows are not changed by applying the function definition. The live readback confirmed the function and grants.

The second migration atomically replaces `backtest_jobs_operation_scope_check` with a validated constraint retaining all three old scopes and adding `workflows.proof`. It changes only rows whose `launch_payload.created_by` is `workflows.proof_cli`: scope becomes `workflows.proof`, `conversation_id` becomes null, and `updated_at` advances. Existing chat writers remain accepted, and activity readers already join jobs to conversations. No table, row, run, message, result, settlement function, RLS policy, or existing valid scope is removed. These facts form the expand-first compatibility plan for the still-running old code.

Before application, 148 seed rows qualified: 143 succeeded and five failed. All had no run, request-message, or confirmation-message link. Their prior scope, conversation link and timestamp were captured with job identity in a private mode-0600 rollback snapshot. That snapshot is not committed. Both transactions used a five-second lock timeout and a thirty-second statement timeout. The scope replacement and row update occurred within the same transaction and table lock, so concurrent readers cannot observe a gap between constraints.

- First migration committed: `2026-09-05T05:03:45.900064Z`, duration 0.732 seconds.
- Second migration committed: `2026-09-05T05:03:46.609486Z`, duration 0.690 seconds, 148 rows updated.
- Each ledger entry stores the exact filename version/name and the gate parser's exact statement array.
- After readback: all 148 rows carry `workflows.proof`, all conversation links are null, and zero rows remain eligible for reclassification.
- The activity reader definition hash was unchanged: `ecf19c500b121dee76ccd2123b5654bc5bb31b9ab95f649ba67611f1c6efb492`.
- Application evidence: `docs/reports/evidence/2026-09-05-main-promotion/production-migration-application.json`
- Before objects and ledger: `docs/reports/evidence/2026-09-05-main-promotion/production-object-readback-before.json`
- After objects and ledger: `docs/reports/evidence/2026-09-05-main-promotion/production-object-readback-after.json`

Rollback: keep the additive function and expanded scope constraint when rolling application code back. Do not reattach proof jobs to chats as a routine code rollback. If a data rollback becomes necessary, the private snapshot records the exact prior fields and requires a separate founder decision. Old Workflow code can seed new mis-scoped proof rows until the Workflow service is released, so the final production activity readback remains required.

## Release Contract

`render.yaml`, `.env.example`, `.github/argus-env.sh`, and `.github/private-alpha-release-profile.json` are unchanged against both the dispatch baseline and current production. Runbook step 5 is not applicable. No Blueprint sync ran.

Live readback at `2026-09-05T05:02:02.966091Z` confirmed `autoDeployTrigger=off` on `argus-api`, `argus-app`, and `argus-backtests`. This is the founder's uniform manual mode. No trigger or branch-protection setting was changed. Main protection requires exactly the `ci` check, strict status checks, and `enforce_admins=true`. The readback is `docs/reports/evidence/2026-09-05-main-promotion/main-branch-protection-before.json`.

Evidence: `docs/reports/evidence/2026-09-05-main-promotion/render-manual-mode-before.json` and `docs/reports/evidence/2026-09-05-main-promotion/render-production-before.json`.

## Gate Evidence

- Setup: `.github/setup.sh` completed. Its canonical-root override pointed to this checkout, preserving the existing root env link and leaving missing `web/.env.local` untouched.
- Python: `3.10.20`, using the founder-specified virtual environment for eval and database operations.
- Local smoke: `.github/local-smoke.sh --expected-sha e3b98690b238bb292e161a9a25554cd9cfdbc19d`, `verification_status=ready`, `workflow_probe=ready`.
- Local ports: API 8125, app 3125, using documented environment overrides.
- Initial smoke attempts: default app port 3100 was occupied; the first alternate-port readiness request timed out at 20 seconds. A diagnostic using the same environment returned the expected readiness payload in 1.391 seconds; the unchanged smoke rerun passed. No timeout or runtime code was changed.
- Local readiness reported `degraded` solely for memory-mode `supabase:gateway_unavailable`, the explicit accepted condition in the smoke script. Runtime and asset checks were ready.
- Local smoke evidence: `docs/reports/evidence/2026-09-05-main-promotion/local-smoke-e3b98690.log`
- Live eval scorecard: `docs/reports/evidence/2026-09-05-main-promotion/candidate-eval-scorecard-e3b98690.json`
- Baseline eval scorecard: `docs/reports/evidence/2026-09-05-main-promotion/baseline-eval-scorecard-c7802b37.json`
- Candidate result: 59 passed, three failed, 62 total, zero infrastructure errors.
- Candidate scorecard generated: `2026-09-05T05:28:53.663758Z`.
- Candidate provider-reported cost: `$1.372790159656`, from 309 priced receipts; eight receipts had no reported cost.
- Candidate fixture SHA-256: `1680a195886c2461e5f8bbbe87f7c3b545a45da189dee8a1f25109409e90ece9`.
- Both provider modes are `live_provider`; the scorecard confirms Python 3.10.20, clean worktree, exact candidate SHA, all 62 fixture IDs, and the live January 1 holiday alignment probe.
- Baseline result: 61 passed, one failed, 62 total. Generated `2026-09-05T05:43:59.196903Z`.
- Baseline provider-reported cost: `$1.186088562696`, from 333 priced receipts; seven receipts had no reported cost.
- Baseline fixture SHA-256: `65a7daab0da92302999bc4a9afa39430f76ba87a0b1d2d0ebecb956ce32b6e8d`.
- Baseline provenance confirms `c7802b37f39772a1216514e37fb6ff2b63142181`, both providers live, Python 3.10.20, clean worktree, and the same holiday alignment probe. Both runs pin `PYTHONPATH` to their own source tree.
- Both fixtures contain the same ordered 62 case IDs. Their hashes differ because #549 strengthened delivered-outcome assertions. No fixture or expectation was changed during this promotion.
- Combined provider-reported cost: `$2.558878722352`. This sum does not invent prices for the 15 receipts with no reported cost.
- Candidate failed IDs: `asset_discovery_spanish_generated_pharma_escalation_issue_344`, `asset_discovery_not_result_followup_issue_244`, and `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run`.
- No failed candidate case has a failed prose judge. The targeted prose A/B requirement is not triggered. No additional paid run was made.
- Mocked eval harness: 237 passed in 9.56 seconds. The first sandboxed attempt could not write Numba cache beside the shared virtual environment; the retry used a writable temporary `NUMBA_CACHE_DIR`.
- Existing candidate CI: required `ci` and all component jobs passed; Supabase Preview was skipped. These are candidate-head checks, not a substitute for fresh promotion-PR CI.
- Modularity budget: passed. Current `origin/main` is an ancestor of the candidate, so the would-be merged product tree is the candidate tree.
- Required manifest tests: **23 passed, one failed** in 8.60 seconds. Command: `pytest tests/test_private_alpha_release_docs.py tests/test_release_promotion_evidence_support.py -q --no-cov` under the pinned Python and mocked provider environment.
- Failing test: `test_main_promotion_manifests_require_live_eval_scorecard_evidence`. The scorecard writer includes the new `infrastructure_error` total, even when zero; `LIVE_EVAL_RESULT_STATUSES` in `tests/test_private_alpha_release_docs.py` still enumerates the older five statuses. Exact total-dictionary equality rejects the valid retained candidate scorecard. The failure is a writer/consumer contract mismatch; the scorecard and validator were left unchanged.
- Required negative control: the actual comparison function passed with the manifest intact, failed after every occurrence of the candidate-only Spanish DCA case ID was removed, and passed after exact-byte restoration. This directly proves the comparison function reads this manifest. It does not turn the failing outer release-docs test into a pass.
- Negative-control evidence: `docs/reports/evidence/2026-09-05-main-promotion/manifest-comparison-negative-control.json`.
- Full test log: `docs/reports/evidence/2026-09-05-main-promotion/manifest-tests.log`.

### Candidate failed checks

All three failed candidate IDs passed the requested historical baseline. The baseline-only failed ID is `dca_capital_semantics_only_have_amount_is_ceiling_issue_455`; the candidate passes it. There are no shared failed IDs. Totals are not used to offset any failed case.

Comparison evidence: `docs/reports/evidence/2026-09-05-main-promotion/failed-case-comparison.json`.

| Case ID | Failed check and observed outcome | Owning surface |
| --- | --- | --- |
| `asset_discovery_spanish_generated_pharma_escalation_issue_344` | `asset_discovery.asset_class_hint` expected `equity`, received null. Five verified pharmaceutical equity rows were delivered and the prose judge passed. | Asset discovery interpretation, #344 |
| `asset_discovery_not_result_followup_issue_244` | `offered.min_next_experiment_rows` expected at least one row, received none. The delivered recovery code was `latest_result_followup_unavailable`. | Result follow-up and delivered Try next outcomes, #244 / #520 |
| `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run` | Expected executable DCA with contribution amount 13000 and a confirmation. Received `unsupported`, null capital, a second clarification, and no launch payload. The recovery reason was `unsupported_dca_contribution_ceiling`. | DCA capital interpretation and clarification, #455 |

Dispositions:

- `asset_discovery_spanish_generated_pharma_escalation_issue_344`: unresolved candidate-only structured failure. Baseline supplied the required equity hint; candidate did not. Both delivered the same five pharmaceutical equity symbols. No model-variance waiver or prose disposition is claimed.
- `asset_discovery_not_result_followup_issue_244`: pre-existing delivery failure exposed by the stronger assertion. Both retained scorecards show `actionable=false`, no next-experiment kinds, and `recovery_code=latest_result_followup_unavailable`. The baseline passed because its fixture did not yet require a delivered next-experiment row. The candidate's red assertion makes an existing defect visible; it is not evidence that this promotion removed a previously delivered row.
- `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run`: unresolved candidate-only structured failure. Baseline interpreted the follow-up as a monthly contribution of 13000 with zero starting capital and reached confirmation. Candidate kept the amount as a total-budget constraint and returned unsupported recovery. No model-variance waiver is claimed.
- `dca_capital_semantics_only_have_amount_is_ceiling_issue_455`: baseline-only failure, owned by DCA capital semantics. The baseline asked for capital and cadence using `missing_sizing_amount_schedule`, while the expected ceiling-specific recovery passed on the candidate. This single-run improvement does not cancel either unresolved candidate-only failure.

The pre-merge evaluation decision is **blocked** by the two unresolved candidate-only structured failures. In addition, the requested baseline is older than verified production, so this comparison cannot establish non-regression against the currently deployed build. The promotion remains a Draft handoff, with no merge or deploy authority inferred from documentation-test or CI results.

No failing case has a failed prose judge. No targeted A/B was required or run, and neither suite was rerun to replace these results.

## Known Production Acceptance Gap

The same canonical readback used `public.read_conversation_activity_sources` and `argus.domain.conversation_activity.project_conversation_activity` over all 566 conversations. It read 135 `checking`, 424 `idle`, and seven `running` before migration. After migration it read 121 `checking`, 438 `idle`, and seven `running`.

The 121 remaining checking states are not workflow-proof seeds. 120 are succeeded chat jobs from June 6 through July 12 with completed runs but no evidence identity or evidence artifact; one June 6 succeeded chat job has no result run. The seven running states come from chat-turn lifecycle records. No cleanup, settlement rewrite, or historical result repair was performed.

Visibility readback further found 91 checking conversations that are neither archived nor deleted, two archived, and 28 deleted. All seven running conversations are unarchived and undeleted. The normal conversation list therefore still has reachable unresolved activity, not only retained deleted records.

The requested zero-spinner acceptance is not met by the migration readback. This gap must remain visible in the promotion decision and in the post-deploy report.

Evidence: `docs/reports/evidence/2026-09-05-main-promotion/remaining-conversation-activity.json` and `docs/reports/evidence/2026-09-05-main-promotion/conversation-activity-visibility.json`.

## Deploy Proof

Pending founder merge and deploy direction. The founder must merge the promotion PR using a merge commit. After landing, place the checkout at the landed SHA, rerun runbook steps 1 and 2, and run `production_migration_gate.py --candidate-sha <landed> --verify-landed-ref origin/main`. Require `status=pass` and landing verification `verified` before deployment.

Then deploy API, app, and Workflow serially, waiting for each to become live. Release Workflow with `.github/render-env-sync.sh workflow-release <landed>`. Read back matching ready versions for all three before warmup and canaries.

## Post-Deploy Verification

All items are pending deployment and must be reported separately from the eval.

- [ ] All three services ready at the landed SHA.
- [ ] Step 12 warmup with `--expect-mode real-workflow`.
- [ ] Step 13 release-coherence canary; preserve and record the expected manual-trigger audit stop.
- [ ] Step 13 authenticated-browser journey.
- [ ] English guest with both free backtests used receives the account offer on the third attempt.
- [ ] Spanish guest with both free backtests used receives the account offer on the third attempt.
- [ ] Grounded research answer with sources in English.
- [ ] Grounded research answer with sources in Spanish.
- [ ] A real backtest completes and its result card renders.
- [ ] Spanish result card, Quick Take, and assumptions contain no English prose.
- [ ] Canonical conversation activity readback confirms zero permanent spinners; currently unmet, with 121 checking and seven running before deployment.

## Release Decision

- Promotion PR: Draft handoff; not ready to merge.
- Founder merge: pending.
- Deploy direction: pending.
- Production code deployment: not performed.
- Blueprint sync and autodeploy change: not applicable and not attempted.
- Pre-merge evaluation: blocked by unresolved structured candidate-only failures and the historical-baseline limitation.
- Required documentation tests: blocked by the scorecard writer/consumer status-contract mismatch.
- Production acceptance: zero-spinner requirement remains unmet.
- Promotion verification: incomplete. Do not merge or deploy this Draft as a completed promotion.
