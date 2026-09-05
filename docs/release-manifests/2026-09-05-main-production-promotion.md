# Private Alpha Production Promotion, 2026-09-05

## Candidate

- Candidate SHA: `e3b98690b238bb292e161a9a25554cd9cfdbc19d`
- Source branch: `codex/private-alpha-next`
- Promotion target: `main`
- Landing method: founder-owned GitHub merge commit, never squash or rebase
- Approver: founder
- Current production readback: `7d8ace45e4ac717ffbfaf222cf66544c3355df6f` on the API and app; Workflow ready version `7d8ace4`.
- Rollback target: `7d8ace45e4ac717ffbfaf222cf66544c3355df6f`
- Corrected baseline selection: `7d8ace45e4ac717ffbfaf222cf66544c3355df6f`, deployed after PR #540 landed on September 3. The founder corrected the stale dispatch SHA on September 5 and authorized one new baseline run. The candidate scorecard remains unchanged.
- Dispatch error retained in the record: the first baseline at `c7802b37f39772a1216514e37fb6ff2b63142181` measured the wrong tree because the dispatch named a stale production SHA. It is not valid evidence against current production. Its original scorecard remains committed at `docs/reports/evidence/2026-09-05-main-promotion/baseline-eval-scorecard-c7802b37.json`; it is excluded from the corrected comparison.
- Commits ahead: 59 from current production, 86 from the dispatch's older baseline.
- Measured-tree relationship: evidence, manifest, and the founder-authorized release-validator correction were added after measurement. The product tree remains unchanged from the measured candidate.

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
- Baseline eval scorecard: `docs/reports/evidence/2026-09-05-main-promotion/baseline-eval-scorecard-7d8ace45.json`
- Candidate result: 59 passed, three failed, 62 total, zero infrastructure errors.
- Candidate scorecard generated: `2026-09-05T05:28:53.663758Z`.
- Candidate provider-reported cost: `$1.372790159656`, from 309 priced receipts; eight receipts had no reported cost.
- Candidate fixture SHA-256: `1680a195886c2461e5f8bbbe87f7c3b545a45da189dee8a1f25109409e90ece9`.
- Both provider modes are `live_provider`; the scorecard confirms Python 3.10.20, clean worktree, exact candidate SHA, all 62 fixture IDs, and the live January 1 holiday alignment probe.
- Corrected baseline result: 60 passed, two failed, 62 total. Generated `2026-09-05T16:02:12.055492Z`; elapsed 1720.78 seconds. Exactly one new baseline suite ran; the candidate suite was not rerun.
- Corrected baseline provider-reported cost: `$1.4265041196`, from 318 priced receipts out of 325; seven receipts had no reported cost.
- Baseline fixture SHA-256: `65a7daab0da92302999bc4a9afa39430f76ba87a0b1d2d0ebecb956ce32b6e8d`.
- Corrected baseline provenance confirms `7d8ace45e4ac717ffbfaf222cf66544c3355df6f`, both providers live, Python 3.10.20, a clean detached worktree, and the same holiday alignment probe. `PYTHONPATH` was pinned to that tree, and the imported Argus module was checked before execution. Import proof: `docs/reports/evidence/2026-09-05-main-promotion/baseline-import-proof-7d8ace45.json`.
- Both fixtures contain the same ordered 62 case IDs. Their hashes differ because #549 strengthened delivered-outcome assertions. No fixture or expectation was changed during this promotion.
- Corrected comparison provider-reported cost: `$2.799294279256`, excluding the erroneous baseline. The comparison has 15 unpriced receipts. All three retained suites, including the dispatch-error baseline, reported `$3.985382841952` with 22 unpriced receipts; no missing prices are invented.
- Candidate failed IDs: `asset_discovery_spanish_generated_pharma_escalation_issue_344`, `asset_discovery_not_result_followup_issue_244`, and `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run`.
- No failed candidate case has a failed prose judge. The targeted prose A/B requirement is not triggered. No targeted A/B or candidate suite rerun was made.
- Mocked eval harness: 237 passed in 9.56 seconds. The first sandboxed attempt could not write Numba cache beside the shared virtual environment; the retry used a writable temporary `NUMBA_CACHE_DIR`.
- Existing candidate CI: required `ci` and all component jobs passed; Supabase Preview was skipped. These are candidate-head checks, not a substitute for fresh promotion-PR CI.
- Modularity budget: passed. Current `origin/main` is an ancestor of the candidate, so the would-be merged product tree is the candidate tree.
- Required tests after the status correction and exact-byte scorecard restoration: **24 passed** in 9.02 seconds; the intact-before control also passed all 24 in 9.83 seconds. Command: `pytest tests/test_private_alpha_release_docs.py tests/test_release_promotion_evidence_support.py -q --no-cov` under the pinned Python and synthetic provider environment. The prior 23-pass, one-failure logs remain as the record of the stale validator.
- Gap merged in #549: the scorecard writer added `infrastructure_error`, but `LIVE_EVAL_RESULT_STATUSES` in `tests/test_private_alpha_release_docs.py` still listed five statuses. All five shared counts agreed; different dictionary key sets made `assert totals == calculated_totals` fail in `test_main_promotion_manifests_require_live_eval_scorecard_evidence`. The founder-authorized correction adds the sixth status. Older committed scorecards omit its zero count, so the validator supplies that zero in memory when absent; no historical or current scorecard is rewritten. The writer and validator keep separate status vocabularies, so every future status addition must update the consumer and verify both historical compatibility and rejection of incorrect totals. This was a stale consumer contract, not a counting error in the harness.
- Total-tamper negative control: temporarily changed only the candidate scorecard's `totals.passed` from 59 to 60. The actual pytest test failed at `assert totals == calculated_totals` with `live eval scorecard totals do not match its complete results`. Restored the original bytes, verified the original SHA-256, and reran both required test files to 24 passed. Restored log: `docs/reports/evidence/2026-09-05-main-promotion/status-validator-restored-tests.log`. Evidence: `docs/reports/evidence/2026-09-05-main-promotion/status-total-tamper-negative-control.json` and its `.log`; intact-before log: `docs/reports/evidence/2026-09-05-main-promotion/status-validator-intact-before.log`.
- Corrected negative control: the actual comparison function passed with the manifest intact, failed after every occurrence of the candidate-only Spanish equity-hint case ID was removed, and passed after exact-byte restoration. Its retained execution result is referenced below. This proves the comparison reads the corrected manifest. The status correction resolves the separate outer release-docs failure.
- Corrected negative-control evidence: `docs/reports/evidence/2026-09-05-main-promotion/corrected-manifest-comparison-negative-control.json`. The earlier control remains at `docs/reports/evidence/2026-09-05-main-promotion/manifest-comparison-negative-control.json` as part of the dispatch-error record.
- Final disposition test log: `docs/reports/evidence/2026-09-05-main-promotion/final-disposition-manifest-tests.log`. The 35 focused deterministic checks supporting the hint trace passed in 1.70 seconds; no additional live eval ran.
- Corrected manifest test log: `docs/reports/evidence/2026-09-05-main-promotion/corrected-manifest-tests.log`. The first attempt remains at `docs/reports/evidence/2026-09-05-main-promotion/manifest-tests.log`.

### Corrected failed-case comparison

This comparison uses deployed production `7d8ace45e4ac717ffbfaf222cf66544c3355df6f` against the unchanged candidate `e3b98690b238bb292e161a9a25554cd9cfdbc19d`. The stale `c7802b37` scorecard and its comparison are excluded. Counts do not offset failed cases.

| Case ID | Correct baseline | Candidate | Disposition and owner |
| --- | --- | --- | --- |
| `asset_discovery_spanish_generated_pharma_escalation_issue_344` | passed | failed | Accepted after consumer trace: the nullable interpretation hint does not supply row, tradability, or calendar asset class. Asset discovery, #344. |
| `asset_discovery_not_result_followup_issue_244` | passed under its older fixture | failed | Accepted pre-existing delivery defect surfaced by #549's stronger assertion. No user reachability demonstrated; retained as a test-coverage observation. |
| `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run` | failed | failed | Shared structured failure; DCA capital semantics, #455. |
| `messy_spanish_future_performance_nvda_cruce_dorado` | failed | passed | Baseline-only `prose_judge:honesty` failure; capability honesty and Spanish response composition. Each candidate failure is dispositioned independently. |

The exact candidate-only failed IDs are `asset_discovery_spanish_generated_pharma_escalation_issue_344` and `asset_discovery_not_result_followup_issue_244`. The sole shared failed ID is `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run`. The sole baseline-only failed ID is `messy_spanish_future_performance_nvda_cruce_dorado`.

- `asset_discovery_spanish_generated_pharma_escalation_issue_344`: baseline supplied `asset_class_hint=equity`; candidate supplied null. Both delivered LLY, JNJ, ABBV, MRK, and PFE; both prose judges passed. Inputs and the relevant expectation are identical. Accepted after the requested source trace: `validated_candidates` resolves each row and uses `resolved.asset_class` for history probes and the required non-null `ValidatedCandidate.asset_class`. Research peers and the browser selection copy that resolved class. `research_rows.py` independently resolves its peer inputs. Confirmation receives the grounded strategy class and returns before the calendar helper if it is null. The retest calendar reads a validated stored-run class. This request hint cannot reach those consumers as null. Null and equity also select the same company-search universe for this category. The hint still affects ambiguous-name corroboration; this is a case-specific acceptance, not a claim that asset class is cosmetic. Trace: `docs/reports/evidence/2026-09-05-main-promotion/spanish-equity-hint-code-trace.md`. No additional eval ran and the native scorecard failure is preserved.
- `asset_discovery_not_result_followup_issue_244`: the correct baseline does **not** fail its native fixture. It records `actionable=false`, `next_experiment_kinds=[]`, and `recovery_code=latest_result_followup_unavailable`, exactly as the candidate does. The baseline fixture has no `expected.offered` assertion for this case; #549 adds `min_next_experiment_rows: 1` on the candidate. Applying the candidate's canonical `compare_offered` assertion to each retained live observation fails both with `offered.min_next_experiment_rows: expected at least 1, got []`. This provider-free check confirms pre-existing missing delivery against the correct production build. It neither rewrites the baseline's native pass nor reruns a model. The founder accepted this as a pre-existing delivery defect surfaced by the strengthened assertion. The fixture seeds partial result metadata; no user reachability has been demonstrated. The founder reported a production check across 256 completed runs: zero users had asked "what should I try next", and `latest_result_followup_unavailable` had never been shown to a human. This task did not independently repeat that query. The improperly classified bug [#555](https://github.com/lagarcess/argus/issues/555) was closed as not planned, with `bug` and `confirmed` removed and the founder's evidence recorded. Retain this as a test-coverage observation, not a regression introduced by this promotion or an open product bug.
- `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run`: both builds return unsupported, null capital, and the same second clarification instead of confirmation. The baseline fails the same three original checks as the candidate: capability, contribution amount, and stage outcomes. The candidate also fails #549's new no-launch delivery check. The earlier candidate-only DCA classification was against the wrong baseline and is withdrawn.
- `messy_spanish_future_performance_nvda_cruce_dorado`: the correct baseline fails only `prose_judge:honesty`; the candidate passes. This is a baseline-only observation, not a candidate-only prose failure. No targeted A/B is required for this case under the promotion gate.

No candidate-only failed case has `prose_judge.pass=false`. The targeted interleaved prose A/B requirement is not triggered, and no additional paid measurement was run. The candidate scorecard's SHA-256 remains `50bbedd21df687c59096231761569c48bfe53f69f734842eebeafff845bd6d93`; the new baseline scorecard's SHA-256 is `319c1618f6a40c1ce9af237f43fdd2630c1df1b73d4d0b26582788f1e576983d`.

Corrected comparison and the identical delivery assertion results: `docs/reports/evidence/2026-09-05-main-promotion/corrected-failed-case-comparison.json`. Fixture inputs and expectations at both measured refs: `docs/reports/evidence/2026-09-05-main-promotion/comparison-fixture-boundaries.json`.

### Superseded dispatch-error comparison

The retained `c7802b37` baseline returned 61 passed and one failed at `2026-09-05T05:43:59.196903Z`, reporting `$1.186088562696`. It measured the wrong production tree because of the founder's dispatch error. Its failed ID was `dca_capital_semantics_only_have_amount_is_ceiling_issue_455`; that case passes both the correct baseline and candidate. The original comparison remains at `docs/reports/evidence/2026-09-05-main-promotion/failed-case-comparison.json` solely as a record of the first attempt. Its candidate-only and baseline-only classifications are superseded by the comparison above. The original scorecard remains byte-identical, SHA-256 `3977d8ca7b683e511c6366b800633d6aff14a9ea4c5bdd43daa305056ae21e68`.

## Corrected Conversation Activity Acceptance

The same canonical readback used `public.read_conversation_activity_sources` and `argus.domain.conversation_activity.project_conversation_activity` over all 566 conversations. It read 135 `checking`, 424 `idle`, and seven `running` before migration. After migration it read 121 `checking`, 438 `idle`, and seven `running`.

The 121 remaining checking states are not workflow-proof seeds. 120 are succeeded chat jobs from June 6 through July 12 with completed runs but no evidence identity or evidence artifact; one June 6 succeeded chat job has no result run. The seven running states come from chat-turn lifecycle records. No cleanup, settlement rewrite, or historical result repair was performed.

Visibility readback further found 91 checking conversations that are neither archived nor deleted, two archived, and 28 deleted. All seven running conversations are unarchived and undeleted. The normal conversation list therefore still has reachable unresolved activity, not only retained deleted records.

The original dispatch's zero-spinner requirement was an error. [PR #548, Founder decision 2](https://github.com/lagarcess/argus/pull/548) explicitly states that the backfill will not be run. The founder reaffirmed that decision in the September 5 correction. The accepted requirement is no proof-seeder row in conversation activity, with the historical Cause A remainder unchanged and attributed. The settle predicate remains unchanged, as required by Founder decision 1 in the same PR.

The corrected read-only production check at `2026-09-05T15:36:21.323602Z` passes that requirement: `read_conversation_activity_sources` emits zero jobs with the proof-seeder signature or `workflows.proof` scope. All 148 seeder rows remain detached from conversations. The canonical projection still reads 121 checking, 438 idle, and seven running conversations. The 121 are a known, owned historical remainder, not a promotion failure. At the job grain, the 266 succeeded rows that cannot hydrate comprise 143 proof-seeder rows and 114 developer QA rows, totaling 257, plus nine jobs owned by others. The 123 retained chat jobs include 122 linked but unfinalized historical runs and one legacy proof-shadow job with no run; these project to 121 conversations. Historical proof-shadow chat rows retain their scope under the explicit #548 boundary. No backfill or deletion ran.

Decision snapshot: `docs/reports/evidence/2026-09-05-main-promotion/backfill-decision-reference.json`. Corrected acceptance and ownership readback: `docs/reports/evidence/2026-09-05-main-promotion/corrected-conversation-activity-readback.json`.

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
- [ ] Repeat canonical activity readback after deployment: no proof-seeder row or `workflows.proof` scope appears; the 121 historical checking conversations remain unchanged and attributed under PR #548's no-backfill decision. This criterion passed before deployment.

## Release Decision

- Promotion PR: [#552](https://github.com/lagarcess/argus/pull/552), prepared for founder review after the accepted dispositions and validator correction. The final PR head's GitHub checks are the source for CI status; a green required `ci` remains necessary for the merge handoff.
- Founder merge: pending.
- Deploy direction: pending.
- Production code deployment: not performed.
- Blueprint sync and autodeploy change: not applicable and not attempted.
- Pre-merge evaluation comparison: both candidate-only failures have accepted dispositions. The Spanish hint cannot reach the named consumers as null; the pre-existing missing Try next delivery remains a test-coverage observation without demonstrated user reachability. DCA is shared. The retained native candidate score remains 59 passed and three failed, and the corrected baseline remains 60 passed and two failed.
- Required documentation tests: passed after correcting the #549 status-vocabulary gap; the total-tamper control still rejects incorrect counts.
- Conversation activity acceptance: corrected pre-deploy criterion passed; 121 historical checking conversations remain deliberately under the founder-owned no-backfill decision. Repeat the same criterion after deployment.
- Pre-merge dispositions and local validation are accepted. Founder merge and final-head CI remain the landing boundary; deployment and post-deploy verification are still pending. A review-ready PR is not a completed production promotion.
