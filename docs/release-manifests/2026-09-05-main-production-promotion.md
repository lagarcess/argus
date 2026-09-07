# Private Alpha Production Promotion, 2026-09-05

## Candidate

- Candidate SHA: `e3b98690b238bb292e161a9a25554cd9cfdbc19d`
- Source branch: `codex/private-alpha-next`
- Promotion target: `main`
- Landing method: founder-owned GitHub merge commit, never squash or rebase
- Approver: founder
- Pre-promotion production readback: `7d8ace45e4ac717ffbfaf222cf66544c3355df6f` on the API and app; Workflow ready version `7d8ace4`. The landed deployment is recorded under Deploy Proof.
- Rollback target: `7d8ace45e4ac717ffbfaf222cf66544c3355df6f`
- Corrected baseline selection: `7d8ace45e4ac717ffbfaf222cf66544c3355df6f`, deployed after PR #540 landed on September 3. The founder corrected the stale dispatch SHA on September 5 and authorized one new baseline run. The candidate scorecard remains unchanged.
- Dispatch error retained in the record: the first baseline at `c7802b37f39772a1216514e37fb6ff2b63142181` measured the wrong tree because the dispatch named a stale production SHA. It is not valid evidence against current production. Its original scorecard remains committed at `docs/reports/evidence/2026-09-05-main-promotion/baseline-eval-scorecard-c7802b37.json`; it is excluded from the corrected comparison.
- Commits ahead: 59 from current production, 86 from the dispatch's older baseline.
- Measured-tree relationship: the original eval measured the candidate above. The subsequent factual-follow-up correction and its retained model-facing fingerprint are recorded below. The landed product tree is byte-identical to final promotion head `f55429b364f3d96208dcf9e0d960cf46dc4c114e` over `src/`, `web/app/`, `web/components/`, `web/lib/`, `web/public/`, `render.yaml`, and `supabase/`.

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

The founder merged [PR #552](https://github.com/lagarcess/argus/pull/552) at `2026-09-05T19:55:05Z`, producing `ee9c3491fa6219502f1e94abc5d9e661a06839d9`, and explicitly directed this production deployment. The operator checked out that exact landed SHA in detached mode and reran runbook steps 1 and 2. The initial local smoke stopped because an older local Next server occupied port 3100. After the founder directed stopping that server, the same smoke passed with `verification_status=ready`; no source change or timeout adjustment was made. The existing Python 3.10.20 environment was retained, and no env file was written.

The landed-ref migration gate passed at `2026-09-05T20:06:33.330583Z`: `status=pass`, `landing_verification.status=verified`, resolved `origin/main` equal to the checkout SHA, and zero stop reasons. It read the ledger over verified TLS in a read-only session. Both migrations were already applied and were not reapplied. The known historical ledger reconciliation remains unchanged.

Evidence directory: `docs/reports/evidence/2026-09-05-main-promotion/landed-deploy/`. The gate report is `production-migration-gate.json`; the successful local smoke is `local-smoke.txt`, with the original failed attempt retained in `local-smoke-initial-port-conflict.txt`.

Deployment was serial, with each release command waiting for readiness before the next service started:

| Service | Release started (UTC) | Ready version | Ready status | Deploy or version ID |
| --- | --- | --- | --- | --- |
| `argus-api` | `20:08:02` | `ee9c3491fa6219502f1e94abc5d9e661a06839d9` | `live`, finished `20:09:40` | `dep-dae7d8v40ujc73e4cev0` |
| `argus-app` | `20:10:25` | `ee9c3491fa6219502f1e94abc5d9e661a06839d9` | `live`, finished `20:12:14` | `dep-dae7echt0dsc73948hig` |
| `argus-backtests` | `20:12:55` | `ee9c349` | `ready`, release command completed `20:14:44` | `wfv-dae7fi0n74is73cmkslg` |

API and app used pinned Render deploys. Workflow used `.github/render-env-sync.sh workflow-release ee9c3491fa6219502f1e94abc5d9e661a06839d9`. Render exposes the Workflow commit through its version-owned seven-character name, which matches the full API/app SHA. The combined readback at `2026-09-05T20:15:40.958863+00:00` passed for all three before warmup started. Command intervals and service readbacks are retained beside `three-service-ready-versions.json`.

All three triggers remain `off`. No Blueprint sync, operator Render configuration change, branch-protection change, rollback, or product fix was performed. The founder later removed and saved the forbidden API cache key without redeploying, as recorded below. The API's existing real-workflow dispatch/execution flags were read back before deployment rather than rewritten. Final post-verification readbacks in `post-deploy/api-deploy-status-final.txt`, `post-deploy/web-deploy-status-final.txt`, and `post-deploy/workflow-version-status-final.txt` still report the same three ready versions.

## Post-Deploy Verification

The first step 12 attempt stopped on `forbidden argus-api:ENABLE_MARKET_DATA_CACHE unexpected_live_env`, in addition to the expected manual-trigger audit stop. That attempt remains unchanged under `landed-deploy/`. The founder removed the key and then clarified that the removal had not initially been saved. A readback at `2026-09-05T20:39:28.557180+00:00` still found the key; the next readback at `2026-09-05T20:40:21.669417+00:00` confirmed it absent. Both observations are retained. The founder saved configuration without redeploying, and the operator did not redeploy or write configuration. Key absence proves saved Render control-plane state, not a restarted API process environment.

The resumed `.github/warmup-render.sh --expect-mode real-workflow` again exited 1, now solely for `autoDeployTrigger expected=checksPass actual=off` on the three services. Health, forced product readiness, frontend, and Workflow environment checks passed. The stale-job scan reported zero scanned, stale, unresolved, or reconciled jobs. The standalone live Workflow proof was not reached because the audit stopped execution. This is the founder-accepted manual-trigger stop, not a passing warmup process.

Both step 13 surfaces ran in [GitHub Actions run 33990857918](https://github.com/lagarcess/argus/actions/runs/33990857918). Release coherence exited 1 at `failure_stage=warmup`, `failure_reason=warmup_probe_failed`; its retained audit excerpt shows only the same three manual-trigger mismatches. Its Workflow proof, signup-denial, and welcome-delivery phases were not reached. The separate authenticated-browser job passed, including its real Spanish backtest, result rendering, decision, reload, Omnisearch retrieval, three-service version checks, and session revocation. That job recorded zero console errors, zero page errors, and no blocking overlay. The overall workflow is failed because the release-coherence job is red; the browser success does not relabel it.

The browser canary used harness SHA `fc30a73fc5652cf8035b4e49499f9f198bc22219`, the evidence-only merge from PR #557, against deployed SHA `ee9c3491fa6219502f1e94abc5d9e661a06839d9`. Local warmup and manual browser verification retained the landed checkout. No product or harness code changed, and no live eval suite was rerun.

All ten checks are accounted for below. Paths are relative to `docs/reports/evidence/2026-09-05-main-promotion/post-deploy/`. There are seven passes, two accepted manual-trigger stops with nonzero process exits, and one failed acceptance check. The structured index is `verification-status.json`. The two required release-documentation test files passed all 24 tests in 6.63 seconds; the log is `documentation-tests.log`.

| # | Required check | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Step 12 warmup, `--expect-mode real-workflow` | FAIL, accepted manual-trigger audit stop; exit 1, other reached probes pass | `warmup.log`, `warmup.exit`, `api-key-presence-readback.json` |
| 2 | Step 13 release-coherence canary | FAIL, accepted manual-trigger audit stop; exit 1 at warmup | `release-coherence/release-coherence.json`, `release-coherence/audit-excerpt.txt` |
| 3 | Step 13 authenticated-browser journey | PASS | `authenticated-browser/authenticated-browser.json` |
| 4 | English exhausted guest receives an account offer on the third backtest | PASS: two completed cards, third KO run opens Create your account, zero generic backtest failure messages | `browser/english-third-attempt-account-offer.png`, `browser/english-third-attempt-evidence.txt` |
| 5 | Spanish exhausted guest receives an account offer on the third backtest | PASS: same guest with two completed cards, Spanish third-attempt account offer | `browser/spanish-third-attempt-account-offer.png`, `browser/spanish-third-attempt-evidence.txt` |
| 6 | Grounded research answer with sources, English | PASS: rendered Netflix answer and five sources, primary-source spot-check | `browser/english-research-answer.png`, `browser/english-research-sources.png`, `research-grounding.md` |
| 7 | Grounded research answer with sources, Spanish | PASS: rendered Netflix answer and five sources, primary-source spot-check | `browser/spanish-research-answer.png`, `browser/spanish-research-sources.png`, `research-grounding.md` |
| 8 | Real backtest completes and its result card renders | PASS: canary run plus guest META and AAPL runs complete with result cards | `authenticated-browser/authenticated-browser.json`, `browser/english-backtest-1-card.png`, `browser/english-backtest-2-card.png` |
| 9 | Spanish result card, Quick Take, and assumptions contain no English prose | FAIL: visible card and Quick Take pass, but the completed-run assumptions question receives confirmation assumptions and omits requested allocation | `browser/spanish-persisted-meta-card.png`, `browser/spanish-persisted-meta-quick-take.png`, `browser/spanish-assumptions-question-and-answer.png`, `browser/spanish-assumptions-failure-readback.txt` |
| 10 | Canonical activity readback excludes proof seeders and `workflows.proof`, with the attributed 121 historical checking conversations unchanged | PASS: zero proof sources, 121 historical checking conversations unchanged and attributed | `conversation-activity-readback.json` |

### Observed assumptions failure and stop

After the guest completed META and AAPL runs and the third KO attempt reached the conversion offer, its KO confirmation remained pending. In the Spanish view, the operator asked:

> ¿Qué supuestos se usaron en el último backtest de AAPL? Muéstrame las comisiones, el deslizamiento y la asignación.

The visible answer was:

> Para la confirmación, estos son los supuestos: Acciones; Capital inicial: USD 10,000.00; Datos diarios; Sin comisiones; Sin deslizamiento; Referencia: SPY.

This answer is Spanish, but it addresses confirmation assumptions instead of the expressly requested completed AAPL run and omits allocation. It therefore does not establish the completed-run assumptions acceptance. This is an observed production behavior mismatch, not a claim that comparison against the former production code proved a regression. Product verification stopped at this observation. The operator captured the question and answer, read back unchanged ready versions, closed both QA browser sessions, and made no further product turns, repair, issue, rollback, or deployment.

### Evidence scope and remaining limitations

Manual browser prompts and results are synthetic QA material. The guest checks used normal browser sessions and real product actions, without database fixtures, signup, real user conversation content, or real user email. The English guest completed two runs and the same exhausted guest was switched to Spanish to verify the equivalent account offer. An additional Spanish browser context reached the shared visitor limit with no completed runs of its own; its `spanish-visitor-budget-offer.png` is supplemental and is not the two-completed-runs proof.

Visible persisted META card labels and Quick Take were Spanish after reloading history and selecting Spanish. The guest language picker uses `persistProfile={false}`: reloading after a guest language change restored the original English profile. This is a browser-view localization proof, not Spanish guest profile persistence proof. The authenticated Spanish reload is separately covered by the passing canary. A DOM-wide readback retained hidden English chart status text, `Visible period: Jan 3, 2023 to Dec 31, 2024.`, which was not visible in the inspected screenshot. The evidence does not assert comprehensive accessibility localization. Manual browser snapshot console counters are preserved; only the authenticated canary has a verified zero-error assertion.

The production activity readback at `2026-09-05T20:55:48.375941+00:00` used `public.read_conversation_activity_sources` and the canonical projector in a repeatable-read, read-only transaction. It emitted zero proof-seeder or `workflows.proof` sources. All 148 proof jobs remain detached, with 143 succeeded and five failed. Among 570 conversations, the snapshot projected 441 idle, 121 checking, and eight running. All 121 checking conversations were attributed to succeeded, unfinalized historical jobs dated June 6 through July 12, with one lacking a linked run. The count is unchanged under [PR #548's no-backfill decision](https://github.com/lagarcess/argus/pull/548). The running count is a separate point-in-time observation during QA, not a change to the accepted historical checking remainder. No backfill or cleanup was applied.

Production remains deployed at the landed SHA, but the promotion is not fully verified. The founder owns the next action, including whether to roll back. Evidence publication does not authorize another deploy.


## PR #552 Factual Follow-up Review

The Codex P1 at `6fd92c6500921d8e0d72f0faa03f54163c946353` is confirmed. `latest_result_answer_stage_result_if_applicable` supplies a voiced factual answer with `response_intent.kind=beginner_guidance` and `result_fact_bank`; the bare-bank fallback in `artifact_presentation_kind` classifies it as a result and the reader blanks the answer. Commit `5ea47355bd2d3849cca0f0ece176fc7744e93c97` restricts that fallback to absent intent or the legacy `result` intent. Browser reload then exposed the same unconditional fallback in `hydrateMessagesFromApi`, which replaced the preserved API content with a generic Quick Take. Commit `bb3bff50902a1dc221745fb4b0b87ab6b42f5b5d` makes that reader respect the response intent too. Explicit result cards, runs, breakdowns, and assumptions retain their artifact treatment.

The deterministic regression checks reproduce nine backend failures and two frontend language failures before their respective corrections. With both corrections, all 104 focused backend/release checks and all 1,556 frontend tests pass; the legacy artifact controls still pass. Modularity, Ruff, and focused ESLint pass. A standalone `tsc --noEmit` attempt reports repository-wide Bun test-shim diagnostics; it is not reported as green. The required CI frontend build remains the build gate. Evidence is under `docs/reports/evidence/2026-09-05-main-promotion/factual-followup-review/`.

The model-facing fingerprint is unchanged: all 17 measured files match, with aggregate SHA-256 `d31d56eed5b1803af5d4473775924aa880d73f2be2901bbb65d7163d8b6fc939` before and after. No model-facing text or scorecard was changed, and no live eval suite was rerun. The mocked eval harness passed all 237 checks.

Browser proof passes for the specific P1 path in English and Spanish. The baseline runs from an immutable `6fd92c65` source archive. Both languages show an empty live answer and a generic Quick Take after reload. With the complete correction, both accepted answers carry `beginner_guidance` and a root fact bank, display the recorded peak date of December 11, 2024 and value of `$50,694.08`, and retain identical voiced content after reload. Screenshots and public response captures are committed under `factual-followup-review/browser/`. The English live response was captured at `5ea47355` and explicitly retained because the subsequent source delta changes only frontend history hydration; its final reload and the Spanish live/reload captures use the complete `bb3bff50` source. Source hashes and this revalidation are recorded in `browser/proof.json`.

The replay uses eight committed synthetic QA messages and a canonical memory-only QA run, with zero email matches and no production database access. The founder explicitly approved this payload after automatic approval review blocked it. The initial replay without a canonical run was inconclusive. Two later English attempts returned visible prose-guard recoveries; one English and two Spanish correct answers used a different fallback path and were excluded from P1 proof. The fee probe found no typed fee value in this legacy QA run and exposed an English option label in its Spanish recovery. The accepted English answer also contains an em dash. These observations and the failed intermediate reload remain in the evidence; they are not presented as successful localization checks or a completed production promotion. No new issues were opened and no model-facing text was changed.

The follow-up review at `5bc469b24a90110bd1b6a5dae0c980be0a3c27ac` identified the duplicated backend/frontend predicate. Commit `3fd260154db898dba3dbd55a2256248de73d9f42` removes the frontend classifier from the result fallback: the API projects its canonical `artifact_presentation_kind` on every read, and hydration consumes that field. The same two recorded live-provider answers were reloaded in English and Spanish against the restarted API and the committed frontend. Their public content is byte-for-byte unchanged, both have null presentation kind, and the browser retains the requested facts. Revalidation screenshots, public readback, source hashes, and red/green logs are under `factual-followup-review/owner/`. The original live evidence is retained because the answer generator and model-facing text did not change; no additional model calls were made. All 144 backend/transport/release tests, 1,558 frontend tests, and 237 mocked eval checks pass. The prompt fingerprint remains unchanged.

The final-head CI and follow-up Codex review subsequently returned clean before the founder merged. The [clean review](https://github.com/lagarcess/argus/pull/552#issuecomment-5554351480) and [terminal audit](https://github.com/lagarcess/argus/pull/552#issuecomment-5554359421) retain the handoff evidence. The PR remained non-draft throughout the review cycle.

## Release Decision

- Promotion PR: [#552](https://github.com/lagarcess/argus/pull/552), with the P1 correction and bilingual browser evidence recorded above. The final PR head's GitHub checks and follow-up Codex review are the source for the merge handoff; both must be clean.
- Founder merge: completed as `ee9c3491fa6219502f1e94abc5d9e661a06839d9`.
- Deploy direction: explicitly given by the founder after landing.
- Production code deployment: all three services remain ready at the landed SHA. Resumed verification recorded seven passes, two accepted manual-trigger audit stops, and one failed completed-run assumptions check.
- Blueprint sync and autodeploy change: not applicable and not attempted.
- Pre-merge evaluation comparison: both candidate-only failures have accepted dispositions. The Spanish hint cannot reach the named consumers as null; the pre-existing missing Try next delivery remains a test-coverage observation without demonstrated user reachability. DCA is shared. The retained native candidate score remains 59 passed and three failed, and the corrected baseline remains 60 passed and two failed.
- Required documentation tests: passed after correcting the #549 status-vocabulary gap; the total-tamper control still rejects incorrect counts.
- Conversation activity acceptance: post-deploy canonical readback passed: zero proof sources and the same 121 attributed historical checking conversations under the founder-owned no-backfill decision.
- The earlier eval dispositions and factual follow-up browser proof remain accepted. The promotion is deployed but not fully verified. After the founder saved the API key removal, verification resumed and then stopped on the observed assumptions mismatch. No rollback, product repair, or new issue was attempted; the founder decides what happens next.
