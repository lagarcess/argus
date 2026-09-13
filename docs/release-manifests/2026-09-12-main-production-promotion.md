# Private Alpha Production Promotion, 2026-09-12

Status: Founder approved promotion with sharing off. The two release-contract flags are false; all seven migrations remain included. Remaining browser acceptance and a fresh ten-pair A/B are authorized within the existing caps. Preflight found a separate exact-SHA requirement for the full scorecard, in addition to the A/B product-tree requirement; that provenance conflict remains unresolved. No validator change, paid rerun, merge or Step 8 is claimed.

## Candidate

- Candidate SHA: `4fd587bf24ce39b794c2228d61f94693826d0da2`
- Candidate branch: `codex/production-promotion-20260912`
- Validation status: Founder approved promotion with sharing off. The two release-contract flags are false; all seven migrations remain included. Remaining browser acceptance and a fresh ten-pair A/B are authorized within the existing caps. Preflight found a separate exact-SHA requirement for the full scorecard, in addition to the A/B product-tree requirement; that provenance conflict remains unresolved. No validator change, paid rerun, merge or Step 8 is claimed.
- Validation surface: separate local acceptance worktree, disposable Supabase, production web build, and deliberately constructed production-mode environment.
- Promotion target: `main`
- Release captain: Codex in the founder-supervised promotion task.
- Approver: founder, in this task.
- Rollback target: `ee9c3491fa6219502f1e94abc5d9e661a06839d9`, verified live on API and app; workflow ready version `ee9c349`. The theme column must be restored before deploying this old build after the approved drop, with separate approval.
- Decision record: founder instructions in this task, 2026-09-12; fixed-cut promotion approved as a one-time exception to full-roadmap completion.

## Production Migration Gate

- Gate command: `scripts/ops/production_migration_gate.py`
- Gate report durable attachment or committed path: `docs/reports/evidence/2026-09-12-main-promotion/production-migration-gate-before.json`
- Gate checked at: `2026-09-13T02:38:15.471757Z`
- Gate candidate SHA: `df7aee12955f667e31057464d62c72287fb12247`
- Gated candidate parents and intended landing method:
- Landed `origin/main` SHA:
- Gate-to-landed-SHA identity: exact / invalidated and rerun
- Landed-ref verification: `--verify-landed-ref origin/main`, status and SHA
- Sanitized production project and database host:
- Database transport: `sslmode=verify-full`, production CA, GSS disabled
- Candidate migrations, with version, name, file SHA-256, statement count, and
  statement-array SHA-256:
- Applied production migrations, with version, name, statement count, and
  statement-array SHA-256:
- Latest applied production migration:
- Missing migrations:
- Unexpected applied migrations:
- Migration name drift:
- Migration content drift, including missing statement history:
- Safety classifications and live requirements for every missing migration:
- Classification basis and human live-schema review:
- Gate result: expected `status=blocked`, sole stop reason `missing_candidate_migrations`, with exactly the seven listed versions in repository order. The theme drop is destructive. No new name or content drift; the historical ledger variance matches the gate's committed reconciliation and is advisory. `status=pass` remains required before deploy.
- Gate human-approval state: seven listed migrations approved in principle, including the destructive theme drop with no backup; application awaits the post-merge approval stop in this task.
- Gate apply result: `not_performed_by_gate`
- Gate ledger readback:
- Human apply performed: no.
- If applied, repository order and ledger before/after:
- If applied, affected-object readback:
- Confirm the gate never applies migrations: `database_access=read_only`, `migration_apply=never`, `apply_result=not_performed_by_gate`.

## Deploy Proof

- API service: `argus-api`
- API deploy status:
- API deployed SHA:
- Web service: `argus-app`
- Web deploy status:
- Web deployed SHA:
- Workflow service: `argus-backtests`
- Workflow version status:
- Workflow released SHA:
- Workflow version id:
- Checked at:

## Environment Proof

- Expected mode: Environment C uses the measured Render literals, production API mode, live providers, disposable local Supabase, and the production web build. The complete key record appears below.
- Release profile hash:
- Effective locales and capabilities:
- api_web_env_fingerprint:
- workflow_env_fingerprint:
- workflow_env_status:
- autodeploy_fingerprint:
- autodeploy_status:
- all three services use `checksPass`: not requested; founder requires manual mode on all three, verified `off` in `production-readback-before.json`.
- workflow_runtime_provider_mode:
- workflow_runtime_proof:
- env_fingerprint script output:
- workflow_task:
- real_workflow_task:
- Backtest service mode:
- Workflow service proof:
  - `argus-backtests` latest deploy/status:
  - workflow autodeploy verified: `off`.
  - workflow provider mode verified: `live_provider`
  - effective runtime provider mode verified: `live_provider`
  - effective runtime proof status:
  - required workflow secrets present with redacted proof:
  - active workflow task verified:
  - real workflow task verified:
- Feature flags:
- Guest staged mode:
  - `ARGUS_GUEST_ACCESS_ENABLED`:
  - `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED`:
  - `NEXT_PUBLIC_GUEST_ACCESS_ENABLED`:
  - permanent account allowlist verified:
- Anonymous Auth / abuse controls:
  - anonymous Auth enabled:
  - CAPTCHA posture:
  - provider anonymous-user rate limit:
  - Argus per-IP guest-attempt limit:
- Guest cleanup:
  - operator-run command:
  - explicit target:
  - dry-run selected:
  - real selected/deleted/preserved/failed:
  - cleanup lag:
- Render config audit command:
- Secret rotation / least-privilege owner:

## Gate Evidence

- Local smoke command: `.github/local-smoke.sh --expected-sha df7aee12955f667e31057464d62c72287fb12247`, in Environment A after one direct timed readiness request.
- Local smoke result: the one unchanged rerun passed. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/local-smoke-rerun-status.json` and `local-smoke-rerun.log` in the same directory.
- Warmup command:
- Warmup result:
- Canary evidence artifact: `private-alpha-canary-evidence`
- Authoritative Spanish release canary:
  - JSON evidence:
  - Exact candidate SHA verified:
  - Finalized evidence/result labels:
  - Decision-note label and reload hydration:
  - Omnisearch source identity:
- Browser signup/login proof: local synthetic signup, first profile save, reload persistence, home country and English Usage passed at the measured head. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/local-acceptance/browser-free-checks.json`, `profile-readback.json`, and screenshots `browser/01-en-guest-greeting.png` through `browser/06-en-usage-labels.png` under that same directory. No paid chat turn is claimed by this free evidence.
- Guest exact-head browser evidence:
  - local candidate SHA:
  - 20-check matrix result:
  - same-UUID new-account conversion:
  - atomic existing-account claim:
  - zero cross-owner results:
  - usage/API/database agreement:
  - chart-interaction zero-write ledger:
  - console status:
- Guest load calibration:
  - synthetic p50/p95 and sample size:
  - error rate:
  - queue/backpressure result:
  - anonymous-session creation volume:
  - cleanup lag:
  - provider-reported cost per completed result:
  - unsupported production projections:
  - Failed-capture replay, if failed:
  - Exit status:

## Release Decision

- Public tester exposure approved: no new exposure approval claimed; founder owns each stop.
- Known caveats:
- Rollback trigger:
- Rollback command or owner:
- Guest rollback order verified:
- Follow-up owner:

## Privacy Notes

- No raw conversation, user, run, or job ids.
- Canary labels are stable hashes for audit correlation only.
- The release profile contains no credentials, account ids, deploy ids, or
  candidate SHA; record its hash with the candidate evidence instead.
- Failed-capture artifacts are sanitized replay inputs, not raw transcripts.
- Service-role credentials, cookies, prompts, and route receipt payloads are not
  copied into this manifest.
- Guest evidence contains no Auth UUID, raw conversation/artifact/job/run ids,
  customer email, tokens, cookies, headers, screenshots of credentials, or
  customer transcript dumps. The local profile screenshots contain a synthetic
  reserved-domain QA email only. Historical guest replay reports contain only
  case and turn numbers, outcomes, refusal codes and named capabilities, with
  allowance counts recorded separately.

## Fixed Cut and Measurement Identity

- Integration cut: `3d379d3d9020027ccfd1f2a4c617626520af8a44`.
- Fetched integration at cut: `3d379d3d9020027ccfd1f2a4c617626520af8a44`.
- Fetched main at cut: `17a07497abbb2ff9159b9694832a6668421e0e88`.
- `git merge-base --is-ancestor origin/main 3d379d3d` exited 0 at the cut.
- Never merge integration into this branch again. Later integration work is excluded.
- Founder lands the promotion with a merge commit, never squash or rebase. Codex never merges.
- The first commit changes the two sharing flags in `render.yaml` and the release profile to `true`. Code defaults remain off. Existing contract tests derive the values; no separate false-valued pin was found.
- Measured head: `df7aee12955f667e31057464d62c72287fb12247`. The founder-approved template commit supersedes the first contract head before any paid measurement.
- Later evidence commits touch only `docs/` unless an approved finding round requires a product fix.
- Product-tree identity will compare `src/`, `web/app/`, `web/components/`, `web/lib/`, `web/public/`, `render.yaml`, and `supabase/` to the measured head, matching the prior promotion record. Also record all non-doc Git-tree changes, including `workflows/`, tests, lockfiles, and the release profile.

## Sharing-Off Decision, 2026-09-13

The founder chose to promote with sharing off after the live findings in [#604](https://github.com/lagarcess/argus/issues/604#issuecomment-5655111583). Only `ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED` and `NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED` change from `true` to `false` in `render.yaml` and the release profile. Their existing contract tests derive and compare the profile and Blueprint values; no separate true-valued test pin exists. Code defaults, runtime code, eval fixtures and all seven migrations remain unchanged. The earlier sharing-on records below are historical evidence, not the intended release configuration.

The full native candidate scorecard remains measurement evidence for the unchanged code exercised in Environment B: that job uses its explicit env file and does not read `render.yaml` or exercise sharing. Its original bytes and recorded measured SHA remain unchanged. This does **not** yet establish that the release validator accepts the scorecard for the new product head. `tests/test_private_alpha_release_docs.py:546` requires the scorecard's `provenance.candidate_sha` to equal the manifest candidate SHA. `eval_measured_code_unchanged` at `tests/release_promotion_evidence_support.py:94` is used for the baseline comparison at lines 160-164; it is not an alternative to the earlier exact-SHA assertion.

The founder authorized a fresh ten-pair interleaved A/B at the sharing-off product head, both sides, retaining HTTP statuses and waiting 15 minutes after three consecutive research delivery failures. The combined $12.50 tracked-cost-plus-reserve cap remains cumulative. The unchanged A/B validator includes `render.yaml` in its product-tree comparison. No paid attempt has started under this decision. An exact-SHA preflight for the full scorecard is required before that spend.

The original measured head and scorecard bytes remain unchanged in their historical records. Sharing-off commit `4fd587bf24ce39b794c2228d61f94693826d0da2` is the new product head named above and is the intended head for the remaining browser walk and authorized A/B. The retained full scorecard still records its real measured head `df7aee12955f667e31057464d62c72287fb12247`; its provenance has not been rewritten. CI green, exact-head Codex review and zero unresolved threads are still required before Step 7. No Step 8 action is authorized.

### Sharing-Off Preflight Stop

The approved sharing-off product commit is `4fd587bf24ce39b794c2228d61f94693826d0da2`. All 16 existing release-profile and Render-profile contract tests passed in 23.34 seconds. The native import-derived comparison reports no changed eval imports; runtime, frontend, workflows, tests and all seven migrations are byte-identical to the original measured head. The full scorecard remains measurement evidence for that unchanged runtime, but the unchanged release validator does not accept it at the new candidate SHA.

A temporary manifest naming the new product head reproduced `AssertionError` at `tests/test_private_alpha_release_docs.py:546`: `assert provenance.get("candidate_sha") == candidate_match.group(1)`. The same preflight reports `eval_imported_code_unchanged=true` and `same_product_tree=false`. No provider calls were made. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/sharing-off/provenance-preflight.json`.

The requested issue is [#608](https://github.com/lagarcess/argus/issues/608), with the hand-listed A/B paths, import-derived baseline comparison and separate full-scorecard exact-SHA assertion recorded together. No validator fix was attempted. A fresh A/B alone cannot resolve the full-scorecard assertion. The remaining browser walk and paid A/B were not started after this blocking preflight. The old sharing-on demo was stopped as part of the rebuild preparation; its owned API/web processes, containers, volumes and ports were removed while unrelated stacks were preserved. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/sharing-off/demo-cleanup.json`.

No new browser or eval spend occurred under this decision. Cumulative browser cost remains $0.67845263918 tracked plus $0.16 reserve, below $3. Eval cost remains $6.0129416335 tracked plus $1.16 reserve, below $12.50. `docs/reports/evidence/2026-09-12-main-promotion/sharing-off/browser-budget-at-stop.json` records the browser total. Fresh CI/review and Step 7 are not complete. No merge, live environment change, migration application or Step 8 action occurred.

## Founder Scope and Approval Stops

- Promote only the fixed cut. Do not add unfinished board items.
- Acceptance replay is approved. User words stay in private scratch outside the repository and are deleted afterward. Reports contain only case and turn numbers, outcomes, refusal codes and named capabilities, plus separate allowance counts.
- Usage labels approved: Usage, Conversation, Searches with sources, Simulations; Uso, Conversación, Búsquedas con fuentes, Simulaciones.
- Founder decision superseded: promote with sharing off. Both release-contract flags are false. No live environment change or Blueprint sync is permitted without separate approval.
- Each post-merge operation needs founder approval here: migrations, live sharing values, three explicit deployments, and post-deploy checks. Ask before creating a production shared link.
- Stop for any Supabase or Render access failure, unexpected production readback, migration or environment mismatch, spending stop, or blocking finding. Report the exact access error without a workaround.
- At most two small blocking fix rounds. Stop before model-facing text or routing changes and on any real blocking sharing finding.

## Approved Migration Order

Apply only after founder merge and the application approval stop, immediately before deployment. The gate reads only. Use its `_split_supabase_statements` for ledger rows, then rerun until `status=pass`.

1. `20260908120000_decision_notes_attach_to_computations`
2. `20260908205041_add_refusal_observations`
3. `20260909183646_share_answer_receipt_selections`
4. `20260909225701_retire_research_rail_ledger_status`
5. `20260910003000_lift_receipt_selection_cap`
6. `20260911120000_add_profile_home_country`
7. `20260911214608_drop_profiles_theme` (destructive)

The founder explicitly approved no backup, overriding PR #595's backup step. Between the theme drop and completed deployment, signups and profile saves on the old build fail. Rolling code back before #584 requires restoration of the theme column first, with separate approval; discarded preference values cannot be recovered from a backup in this promotion.

## Environment and Spending Ledger

| Job | Environment | Stop | Spent | Result |
| --- | --- | --- | --- | --- |
| Free gates | A: development setup with the explicit canonical-root override | Free | $0 | Smoke, mocked harness, modularity and parity passed; mocked harness passed 259 checks; unchanged release validator checked after A/B evidence |
| Candidate and production baseline eval | B: identical explicit eval env file and both provider modes live | $12.50 combined, tracked cost plus reserve | $6.0129416335 tracked + $1.16 reserve = $7.1729416335 guarded | Ten pairs complete; native failures deployed 0/10, candidate 6/10; founder merge disposition pending |
| Unattended browser walk | C: clean detached worktree, disposable Supabase, production build | $3.00 | $0.1330577 tracked + $0.10 reserve = $0.2330577 guarded | Stopped at P1 sharing blocker; 21 records, 17 pass and 4 fail; full walk incomplete |
| Historical guest replay | C: fresh guest per conversation, ordered user turns | $4.00 | $1.7073169653 tracked + $0.18 reserve = $1.8873169653 guarded | 38/38 assessed; 38 pass, 0 fail, 0 allowance |

Environment A's pre-existing root `.env` symlink resolves through the integration worktree to the exact founder-named real file. `web/.env.local` is absent. No environment file is written through or replaced.

Environment C has no `.env` or `web/.env.local`. API and web launched from empty environments with only declared Render keys, the approved substitutions, process basics, and the localhost QA captcha token. Before the production web build and server starts, both services passed the key-by-key literal, declared-key, forbidden-production-value, and absent-env-file checks. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/local-acceptance/environment-proof.json`. The disposable stack was reset from the measured branch migrations; startup readiness passed with the runtime, Supabase, and live asset catalog ready. Evidence: `stack-proof.json` and `startup-health.json` in that directory.

Local differences to cover after deployment: in-process backtests instead of `argus-backtests`, no Turnstile widget, no PostHog, no emails, and localhost origins. The API retains production key routing and shadow job rows; only if jobs stay queued may shadow mode be turned off and recorded as another local difference.

## Historical Step 3 Budget Stop

- Promotion PR: https://github.com/lagarcess/argus/pull/603, targeting `main` with the fixed integration cut. This is a blocked promotion, not a terminal release audit.
- Baseline eval scorecard: `docs/reports/evidence/2026-09-12-main-promotion/baseline-eval-scorecard-ee9c3491.json`. Original bytes retained, SHA-256 `ec7e3301fbc796c38265313a61282a882d2564bcd761e7084ffcc05c91c7792a`.
- Baseline: 59 passed, 3 failed, no infrastructure errors, all 62 fixtures and 73 user turns. Both provider modes are `live_provider`; the native provenance confirms the production SHA, Python 3.10.20, clean worktree, and holiday-alignment probe.
- Candidate: 47 completed cases passed, 24 cases remain unmeasured or incomplete. The process stopped during `dca_capital_semantics_spanish_period_exceeds_window_issue_455` with exit code `-15`. No native candidate scorecard was written, and none was reconstructed or fabricated from partial events.
- Comparison: not accepted. The complete baseline has three failures: `action_chip_change_asset_bare_ticker_append_issue_190`, `asset_discovery_not_result_followup_issue_244`, and `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run`. Their checks remain in `baseline-summary.json`. Partial candidate successes cannot establish the complete comparison. No candidate failure triggered a judge replay or case rerun.
- Fixture relationship: 62 common cases, with 59 unchanged. Three forward-looking cases retain their inputs but change expected outcomes and the prose rubric to research with sources. The candidate adds nine cases and removes none. Evidence: `eval-fixture-comparison.json` in the same directory.
- Environment identity: each run used a separate clean detached worktree and the identical explicit process environment, real env-file path, and live provider modes. The env-file content hash remained unchanged after both processes stopped. Evidence: `eval-environment-source-provenance.json` and `eval-pair-process-record.json` in the same directory.
- Cost: baseline `$1.390784977984`; partial candidate `$1.344450851416`; combined tracked `$2.7352358294`. This includes OpenRouter usage receipts, validated Perplexity Agent usage, and `$0.05` of documented Perplexity Search request fees. It is not a complete provider invoice because 34 non-skipped receipts lack prices.
- Guard: `$0.10` for in-flight work plus `$0.02` per unpriced non-skipped receipt. Its final `$0.78` reserve is a conservative operational allowance, not an asserted provider charge. Tracked cost plus reserve reached `$3.5152358294` and terminated the candidate. The report does not claim that actual spend reached `$3.50`.
- Evidence: `docs/reports/evidence/2026-09-12-main-promotion/eval-budget-stop.json`, plus `eval-run/events.jsonl`, the unchanged observer and guardian source, and sanitized process logs under that evidence directory.
- Initial PR CI: frontend, guest-release-gates, ownership, and Supabase Preview checks passed. Backend reported 7,861 passed, 585 skipped, and one failure: the required durable candidate live scorecard is absent. That evidence requirement remains unmet; no validator was weakened. The aggregate `ci` check is not green.
- Stop-record validation: 23 release evidence checks passed; the one missing-candidate-scorecard requirement failed, as expected for this incomplete run. Evidence: `release-docs-budget-stop.log` in the same directory.
- Review: the initial Codex summary completed at PR head `2d99bcb4edc6c9e817a524fa295c8d67776ff549`, with no formal review or inline thread and no explicit `Reviewed commit` receipt. It does not satisfy the founder's exact-head review requirement. No terminal audit or clean-review claim is made.
- Local free acceptance: six screenshots, profile persistence readback, startup readiness, scratch migration reset, and all 85 environment keys are retained under `local-acceptance/`. Paid browser and replay spend are both `$0`. Customer message content was never pulled; the replay inventory selected aggregate counts only.
- Cleanup: owned API/web processes stopped, owned ports closed, and `supabase stop --no-backup --workdir <owned scratch>` succeeded. The unrelated running stack remained intact. Evidence: `local-acceptance/cleanup.json`.
- Superseded proposal: the stop report requested a `$6.50` combined eval cap. The founder instead approved `$7.50` on tracked cost plus reserve for exactly one fresh full candidate run, retaining the baseline and environment. Browser and replay caps remain `$3` and `$4`.

## Step 3 Approved Fresh Candidate Run (Historical Result)

The founder approved one fresh full candidate run after the stop record at `0e6227386ab76813fd55d0c838f896abe7e70e41`. The combined cap is `$7.50` on tracked cost plus reserve, including the original baseline and interrupted candidate costs. The reserve is not spend. If this guard stops the fresh run, stop and report; no further full run is authorized.

- Live eval scorecard: `docs/reports/evidence/2026-09-12-main-promotion/candidate-eval-scorecard-df7aee12.json`
- Full candidate result: 70 passed, one failed, zero infrastructure errors as classified by the native harness. The native scorecard is retained unchanged.
- Candidate-only failed case: `messy_spanish_future_performance_nvda_cruce_dorado`. Research recorded `research_unavailable_timeout`, no publication and no sources. The assistant disclosed the unavailable data search. The native checks failed `research.published` and `prose_judge:scenario_framing`.
- Recorded-text judge replay: the exact retained answer and rendered context were passed to the candidate's `judge_prose_quality`; `scenario_framing` failed again. No user message was regenerated in that replay.
- One permitted case rerun: passed with no failed checks or infrastructure errors, published research, three rows and five sources, and a passing prose judge. No second full candidate run or further case rerun was started.
- The full scorecard's failure remains visible. Supplemental evidence is `docs/reports/evidence/2026-09-12-main-promotion/eval-run/recorded-judge-replay.json` and `docs/reports/evidence/2026-09-12-main-promotion/eval-run/single-case-rerun.json`.
- Release-doc validation: 23 passed, one failed in 11.11 seconds. The failing test is `test_main_promotion_manifests_require_live_eval_scorecard_evidence`, now because `tests/release_promotion_evidence_support.py:236` requires both sides of a targeted interleaved A/B, with at least ten attempts per side. This rule entered at `5d408acf` before main at the cut. It has not been changed or bypassed. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/release-docs-completed-scorecard.log` and `docs/reports/evidence/2026-09-12-main-promotion/release-policy-stop.json`.
- Classification: release-policy conflict, not an established product regression. The research timeout did not recur in the one allowed case rerun. No ten-pair measurement, further full run, or extra case rerun was started. Fix rounds used: zero.
- Final cost including the original baseline, partial candidate, fresh full candidate, recorded judge and permitted case rerun: tracked `$4.88888657926`, reserve `$1.02`, guarded total `$5.90888657926` of `$7.50`. Fresh full candidate cost alone is `$1.8923231143`. The reserve is not spend. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/approved-eval-comparison.json` and `eval-run/all-attempt-events.jsonl` in the same directory.
- Declined proposal: the founder declined a validator change and explicitly made the existing release rule authoritative. The later targeted A/B authorization and results below supersede this policy-conflict stop. The validator remains unchanged.

Preflight confirmed the measured head, all 71 fixtures and 84 user turns, a clean detached worktree, local module imports, unchanged observer bytes, and the identical process environment and env-file content hash. The completed baseline is retained byte-for-byte. The new guardian appends to the original cost ledger, records the starting event boundary to separate this attempt, and uses an exclusive launch marker to prevent a second launch.

The replay cohort was counted read-only before pricing using both date boundaries. The New York product day is `2026-08-12T04:00:00Z` through `2026-08-13T04:00:00Z`: 12 guest conversations from 12 people, with 25 user turns across their complete histories. The UTC day is midnight to midnight: 14 guest conversations from 14 people, with 35 full-history user turns. Canary and internal accounts are excluded. The initial plan selected New York alone; the founder later selected the deduplicated union of New York and UTC, recorded below; both counts were reported to the founder before any replay price estimate. Customer message text has not been selected. After reporting both counts, the higher completed-eval tracked cost per user turn (`$0.0225276561`) gives a rounded-up New York estimate of `$0.57`, or `$0.79` for the UTC comparison. These are tracked-cost estimates, excluding unknown receipt costs and the separate guard reserve; the replay stop remains `$4`. No replay has run. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/replay-price-estimate.json`.

At head `0e622738`, PR #603's red CI is the single release-doc test waiting on the complete candidate scorecard. With that scorecard now present locally, the same test reaches the ten-pair policy requirement and fails there. The completed Codex review summary belongs to `2d99bcb4edc6c9e817a524fa295c8d67776ff549`. A fresh Codex review will be requested at the final head; the earlier summary does not satisfy that requirement.

The owned local stack restarted and reset from the measured migrations. Its initial port check encountered the old browser connection in `FIN_WAIT_2`, with no active listener. The scratch launcher now uses normal reusable-address bind semantics for this availability check; no product code, port, or other stack changed. The production web rebuild and empty-environment assertions passed, followed by API health, web health, and readiness. Paid browser turns remain pending the release-policy decision. After the stop, owned API/web/guard processes were stopped and `supabase stop --no-backup --workdir <owned scratch>` succeeded. All owned ports closed, no owned containers remain, and the unrelated stack remained intact. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/local-acceptance/cleanup-release-gate.json`; restart and environment proofs are adjacent. No customer text was pulled.

## Step 3 Targeted Interleaved A/B

Completed ten paired rounds in the identical Environment B, retaining the first four pairs and every native result. The founder superseded the earlier failure-gap stop and required completion under the unchanged `$12.50` cumulative cost-plus-reserve cap. The validator remains unchanged. No additional full eval run or single-case retry was started.

- Case: `messy_spanish_future_performance_nvda_cruce_dorado`.
- Deployed side: `ee9c3491fa6219502f1e94abc5d9e661a06839d9`; candidate side: `df7aee12955f667e31057464d62c72287fb12247`.
- Baseline A/B evidence: `docs/reports/evidence/2026-09-12-main-promotion/targeted-ab-baseline.json`.
- Candidate A/B evidence: `docs/reports/evidence/2026-09-12-main-promotion/targeted-ab-candidate.json`.
- Native whole-case failure rates: deployed `0/10 (0%)`; candidate `6/10 (60%)`. Research timeout counts: deployed `0`, candidate `1`. Timeouts count as failed attempts; no failure was discarded or rewritten.
- Each side records clean-worktree provenance, exact source SHA, fixture and case hashes, provider modes, Python version and live holiday-alignment probe. Inputs are identical; committed expectations differ. Production expects an honest future-performance limitation; candidate expects research with cited scenarios. These native rates do not imply identical rubrics.
- First-pair projected combined guard was `$6.4607520213`, checked before attempt three. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/targeted-ab/first-pair-projection.json`. Its first candidate attempt failed cheaply with a provider HTTP error, so it was an uncertain forecast; the hard cumulative guard remained active.
- Historical stop: the first four pairs stopped at deployed `0/4`, candidate `3/4`. The founder then classified the finding and authorized the remaining six pairs. The historical record remains in `docs/reports/evidence/2026-09-12-main-promotion/targeted-ab/status.json` and `docs/reports/evidence/2026-09-12-main-promotion/targeted-ab-verification.json`; the completed record is `docs/reports/evidence/2026-09-12-main-promotion/targeted-ab/resume-status.json`.
- Finding and cause: forward-looking questions now depend on research. The provider-error path has no retry, so an error window immediately becomes a disclosed search-unavailable answer. Founder-provided evidence records other requests with `research_unavailable_http_error` at `06:27Z` and `06:30Z`, before the A/B, and confirms candidate attempts 1 and 3 occurred in the same broader provider-error window. Unchanged inputs also published research. These are **provider-side research delivery failures, not candidate request defects**. Their earlier HTTP status values were not retained and are not inferred. Candidate attempt 4 gave the same future-performance limitation production gives and passed its prose judge, so the founder classified it as **no worse than production**; its native typed failure remains visible.
- Continued attempts: candidate 6 recorded `research_unavailable_timeout` with no response status; candidate 9 recorded `research_unavailable_http_error` with HTTP **500**. Candidate 10 returned the same production-style future-performance limitation, with its prose judge passing. Comparing it with deployed attempt 10 supports the same no-worse category as attempt 4; native typed failures remain counted. Overall, candidate published research in 4/10 attempts, had three provider HTTP failures and one research timeout, and gave the production-style limitation in two attempts. No cooldown was required.
- **First follow-up: research retry on provider errors**, with usage/cost accounting preserved and disclosed unavailability if delivery still fails. No retry, routing or model-facing text change was made. The founder decides at the merge stop whether to promote with this follow-up pending. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/founder-research-disposition.json` and `docs/reports/evidence/2026-09-12-main-promotion/targeted-ab-finding.json`.
- HTTP status capture on continued attempts uses a read-only native-client observer, identical on both sides, with no new environment keys or product changes. HTTP error responses after resumption: `[{"attempt":9,"http_errors":[{"kind":"research_http_error","attempt":9,"http_status":500,"method":"POST","time":1789284822.287584}]}]`. A timeout without an HTTP response has no HTTP status. The observer's free check covered HTTP 429 and 503 and did not enter the live cost ledger. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/targeted-ab/http-observer-free-check.json`.
- The guardian enforces a 900-second pause before the next pair after three consecutive candidate research delivery failures. Recorded cooldowns: `0`. Full timestamps, if any, remain in the resumed status artifact.
- Combined eval tracked cost: `$6.0129416335`. Separate reserve: `$1.16`. Guarded total: `$7.1729416335` of `$12.50`. All previous baseline, partial candidate, full candidate, judge and permitted retry costs remain included. The reserve is not spend.
- Integrity proof: `docs/reports/evidence/2026-09-12-main-promotion/targeted-ab-completion-verification.json`. All 20 native attempt hashes, both native full-scorecard hashes, environment-source hash, alternating order, native clean worktrees, ledger totals and all non-doc Git paths verified. Fix rounds used: zero.
- Prior free mocked harness: 259 passed. At `fc2eaa99`, PR #603's only backend CI failure was the release-doc test waiting on ten attempts per side; 7,861 backend tests passed. Completion evidence is now present for the unchanged validator. All 24 release evidence checks passed in 28.07 seconds, recorded in `docs/reports/evidence/2026-09-12-main-promotion/release-docs-completed-ab.log`. Final acceptance-head CI and a fresh Codex review are still required; the earlier summary belongs to `2d99bcb`.

| Round | Deployed | Candidate |
| --- | --- | --- |
| 1 | pass | fail (`research_unavailable_http_error`) |
| 2 | pass | pass |
| 3 | pass | fail (`research_unavailable_http_error`) |
| 4 | pass | fail (no worse than production; prose passed) |
| 5 | pass | pass |
| 6 | pass | fail (`research_unavailable_timeout`) |
| 7 | pass | pass |
| 8 | pass | pass |
| 9 | pass | fail (`research_unavailable_http_error`); HTTP 500 |
| 10 | pass | fail (production-style limitation; prose passed) |

## Replay Union and Historical Browser Approval Stop

The cohort and price were reported before execution. New York has 12 guest conversations / 25 full-history user turns; UTC has 14 / 35. Their deduplicated union has 15 conversations from 15 people and 38 user turns, spanning `2026-08-12T00:00:00Z` through `2026-08-13T04:00:00Z`. Canary and internal accounts are excluded. Read-only extraction confirmed exactly 15 conversations and 38 user messages. Production identities were not serialized.

The higher completed full-eval tracked cost per turn (`$0.0225276561`) gave the reported rounded-up estimate of `$0.86`, excluding unpriced receipt costs and the separate reserve. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/replay-union-counts.json` and `docs/reports/evidence/2026-09-12-main-promotion/replay-union-price-estimate.json`. Actual replay tracked cost was `$1.7073169653`, above that estimate; with `$0.18` reserve, the guard was `$1.8873169653` of `$4`. The reserve is not spend. The hard guard remained active throughout.

- Replay result: `completed`, **38 pass, 0 fail, 0 allowance**, across 38 assessed turns. Each input and user-visible response was privately read against the board's rule: no refusal naming a capability the person did not ask about. An allowance message would be counted separately. These outcomes assess that refusal rule; they do not replace browser acceptance of rendered controls.
- A separate research delivery failure occurred at case 12, turn 3: provider HTTP **429**, with disclosed search unavailability. It did not name an unrelated unavailable capability, so it passes the stated refusal rule. It is retained as a delivery failure, not an Argus user allowance. No retry was performed. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/replay/replay-delivery-observations.json`. This also supports the already named first follow-up, research retry on provider errors.
- Every conversation received a fresh local guest. User messages ran in order in Environment C. Original interactive action payloads were not replayed; the authorized unit is the stored user message. No synthetic replacement questions or paid retry were added.
- The API and production web build used the measured Render literals and only the approved substitutions. Both `.env` and `web/.env.local` were absent. Readiness, API and web health passed before extraction. The initial local launcher used a wrong readiness URL and received HTTP 404 before extracting any customer text; the harness URL was corrected to the repository-owned `/internal/readiness`. No product code, environment value or timeout changed.
- Automatic approval review initially rejected the replay's provider authorization. Read-only checks confirmed the explicitly approved cohort, Environment C providers and private handling; re-review accepted the same authorized action. No alternate destination or execution workaround was used.
- Inputs and SSE frames remained in private scratch outside the repository. The owned API/web processes stopped, `supabase stop --no-backup --workdir <owned scratch>` succeeded, the disposable database and private inputs/frames/logs were removed, owned ports closed and unrelated stacks remained intact. Public evidence contains numbered verdicts and operational metadata only.
- Results and cost: `docs/reports/evidence/2026-09-12-main-promotion/replay/replay-results.json`; environment: `docs/reports/evidence/2026-09-12-main-promotion/replay/environment-proof.json`; startup: `docs/reports/evidence/2026-09-12-main-promotion/replay/replay-startup-health.json`; cleanup: `docs/reports/evidence/2026-09-12-main-promotion/replay/cleanup-replay.json`; research provider error statuses, without customer text: `docs/reports/evidence/2026-09-12-main-promotion/replay/replay-provider-error-statuses.json`.
- Free validation: all 259 mocked harness checks passed in 34.45 seconds. The unchanged release-evidence validator passed all 24 checks after receiving ten attempts on each A/B side. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/mocked-completed-ab.log` and `docs/reports/evidence/2026-09-12-main-promotion/release-docs-completed-ab.log`.
- Final checkpoint verification: `docs/reports/evidence/2026-09-12-main-promotion/replay-completion-verification.json`. All 24 release-evidence checks passed again on the completed replay record in 27.68 seconds, with the native validator unchanged. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/release-docs-replay-complete.log`.
- At this historical checkpoint, browser spend was `$0` of `$3`. The founder subsequently approved the unattended walk recorded below. Fresh Codex review remains required at the final acceptance head; the earlier summary is on `2d99bcb`. No terminal audit or merge-ready claim is made.

| Case | Turn | Outcome | Refusal code | Named capability |
| --- | --- | --- | --- | --- |
| 1 | 1 | pass | none | none |
| 1 | 2 | pass | none | none |
| 1 | 3 | pass | none | none |
| 2 | 1 | pass | none | none |
| 2 | 2 | pass | none | none |
| 2 | 3 | pass | none | none |
| 2 | 4 | pass | none | none |
| 2 | 5 | pass | none | none |
| 2 | 6 | pass | none | none |
| 2 | 7 | pass | none | none |
| 2 | 8 | pass | none | none |
| 2 | 9 | pass | none | none |
| 3 | 1 | pass | none | none |
| 4 | 1 | pass | none | none |
| 4 | 2 | pass | none | none |
| 5 | 1 | pass | none | none |
| 5 | 2 | pass | none | none |
| 5 | 3 | pass | none | none |
| 6 | 1 | pass | none | none |
| 7 | 1 | pass | none | none |
| 8 | 1 | pass | none | none |
| 9 | 1 | pass | none | none |
| 9 | 2 | pass | none | none |
| 10 | 1 | pass | none | none |
| 10 | 2 | pass | none | none |
| 10 | 3 | pass | none | none |
| 10 | 4 | pass | none | none |
| 11 | 1 | pass | none | none |
| 12 | 1 | pass | none | none |
| 12 | 2 | pass | none | none |
| 12 | 3 | pass | none | none |
| 12 | 4 | pass | none | none |
| 13 | 1 | pass | none | none |
| 14 | 1 | pass | none | none |
| 14 | 2 | pass | none | none |
| 15 | 1 | pass | none | none |
| 15 | 2 | pass | none | none |
| 15 | 3 | pass | none | none |

## Unattended Browser Walk: Sharing Stop, 2026-09-13

The founder approved the full English and Spanish walk unattended, with a $3 cap and no fix round. Environment C was rebuilt and started from the audited empty environment at the measured head. Its own Supabase stack was reset from the measured migrations. All environment assertions passed; shadow jobs stayed enabled and both observed jobs succeeded. The browser record is the acceptance evidence.

**P1, new blocking sharing finding:** the chat-header selector showed **0 of 0 selected**. The completed backtest was labeled not complete, while the sourced Breakdown was labeled unsafe. Native read-only reproduction shows both saved jobs pass the completion predicate and all result/artifact links match. Separately, `audit_text` rejects an ordinary public Coca-Cola publisher link as `unsafe_text`: its long URL path matches the secret-shaped text guard. This answer-selection path is absent at the deployed baseline. The full cause of the separate completed-result eligibility mismatch remains open. No fallback flag or product code was changed. Evidence: `browser-walk/en-20-sharing-selection.png`, its `.txt`, `sharing-diagnosis.json`, and the read-only reproduction `diagnose_browser_sharing.py`, under `docs/reports/evidence/2026-09-12-main-promotion/`.

The founder's Step 6 rule requires a stop for a real blocking sharing finding. Accordingly, local link creation, signed-out phone viewing, revocation, the remaining clarification check and the remaining Spanish walk were not executed. No link exists. The fallback decision is a sharing-off promotion, with the remaining acceptance still owed, or holding for a sharing fix. This record authorizes neither option and is not a Step 7 merge-ready audit.

Other findings and outcomes:

- **P2, non-blocking:** the English result follow-up repeated four next steps in prose and again under Try next. Its gap, cost dollars and worst-drop dates matched the saved run. The new follow-up owner is in this bundle; deployed occurrence was not replayed, so no baseline behavioral claim is made. No model-facing text was changed. Evidence: `duplicate-next-steps-finding.json`, `en-14-result-follow-up.png`, and `.txt`.
- **P2, new observability defect:** `result_summary` now uses the `readout` tier, but the database check still allows only utility, chat, structured and context. Native error: `new row for relation "route_receipts" violates check constraint "route_receipts_tier_check"`. The Quick take reached the user; its route receipt and downstream cost-ledger persistence failed. The separate process observer retained spend. Evidence: `readout-receipt-finding.json`.
- **Provider delivery:** English valuation research failed with HTTP 500. Its single approved retry began 132.374 seconds after the recorded failure and timed out without an HTTP response status. Both disclosed lookup unavailability and quoted no live figures. No second retry ran. This adds evidence to the already founder-classified research-delivery finding. **Research retry on provider errors remains the first follow-up**, subject to the founder's promotion decision.
- **Existing Spanish confirmation wording:** the founder confirmed that the English confirmation summary in Spanish conversations already exists on the deployed build. This stopped walk did not reach that surface, so it is recorded as founder-provided baseline evidence, not a new or newly reproduced finding.
- English signup, first country save, reload, Usage, two sequential card edits, a monthly-contribution backtest, Quick take, Breakdown, exact result facts, feedback save/dismissal, decision save/reload and the result's rail navigation passed. The rail appears after the transcript reaches its normal length threshold; a saved decision changes the result tick to Decision saved. Local persistence confirmed one profile, one feedback row, one completed run and one decision. Both guest greetings passed. A same-chat clarification setup inherited the prior period and did not ask a question; that did not satisfy the required clarification check, which remained owed at the sharing stop.

**Spend:** $0.1330577 tracked + $0.10 reserve = $0.2330577 guarded of $3. The reserve is not spend. The unchanged eval total remains $6.0129416335 tracked + $1.16 reserve = $7.1729416335 of $12.50; historical replay remains $1.70731696526 + $0.18 reserve = $1.88731696526 of $4. Evidence: `budget-final.json` and `cost-events.json` in the browser-walk directory.

**Environment and cleanup:** `environment-proof.json` carries the key-by-key record; `startup-proof.json` and `restart-proof.json` bind the build to the measured head. The approved differences remain in-process backtests, localhost origins, no Turnstile widget, no PostHog and no real application email. Feedback saved once; its expected local email warning is covered by that difference. Owned API/web processes stopped, `supabase stop --no-backup --workdir <owned scratch>` passed, all owned ports closed and owned containers/volumes were removed. Unrelated stacks were preserved. Raw API/web logs were deleted after retaining sanitized findings and cost evidence. See `cleanup-browser.json`. Historical replay inputs remained deleted throughout.

The table below is the full walk record at the stop. Every executed row has a screenshot and captured visible text. A not-run row has no fabricated screenshot or acceptance claim. Screenshot and text links resolve into the committed browser-walk directory. `steps.json` retains timestamps, exact expectations and dispositions; `not-run.json` enumerates the remaining scope.

| Language / step | Expected | Visible text that matters | Result and reason | Evidence |
| --- | --- | --- | --- | --- |
| en-01-guest-greeting | Empty guest chat shows an English greeting and enabled composer. | What should we look into? | PASS: English greeting and composer are visible. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-01-guest-greeting.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-01-guest-greeting.txt) |
| es-01-guest-greeting | Empty guest chat shows the Spanish greeting and composer. | ¿Qué te gustaría investigar? | PASS: Greeting, suggestions and composer are Spanish. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/es-01-guest-greeting.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/es-01-guest-greeting.txt) |
| en-02-signed-in-greeting | A new local account reaches the empty signed-in English chat. | What should we look into?; Search; Settings | PASS: Signup reached the English chat with signed-in sidebar controls. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-02-signed-in-greeting.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-02-signed-in-greeting.txt) |
| en-03-first-profile-save-country | First home-country save succeeds and derives USD. | Country United States; Currency USD | PASS: United States and USD are shown after the first country save. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-03-first-profile-save-country.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-03-first-profile-save-country.txt) |
| en-04-profile-reload | Saved country and derived currency survive a reload. | Country United States; Currency USD | PASS: United States and USD persisted after reload. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-04-profile-reload.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-04-profile-reload.txt) |
| en-05-usage | Usage labels read Usage, Conversation, Searches with sources, Simulations. | Usage; Conversation; Searches with sources; Simulations | PASS: All four approved English labels are visible. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-05-usage.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-05-usage.txt) |
| en-06-confirmation | The DCA draft preserves starting capital and monthly contribution and discloses any date adjustment. | $200 monthly; $5,000; Jul 27, 2020 → Dec 31, 2024 | PASS: Card shows $5,000, $200 monthly and the disclosed available-data start. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-06-confirmation.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-06-confirmation.txt) |
| en-07-first-card-edit | Changing starting capital preserves the recurring contribution. | $200 monthly; $6,000 | PASS: $6,000 starting capital is saved with $200 monthly unchanged. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-07-first-card-edit.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-07-first-card-edit.txt) |
| en-08-second-card-edit | A costs edit preserves the earlier capital edit and monthly contribution. | $6,000; $200 monthly; 10 bps fee + 5 bps slippage | PASS: 10 bps fee and 5 bps slippage are saved with $6,000 and $200 monthly intact. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-08-second-card-edit.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-08-second-card-edit.txt) |
| en-09-result-quick-take-feedback | A result, Quick take and one feedback ask appear after the backtest. | Simulation Complete; Quick take; How is Argus doing? | PASS: Result and Quick take are present with one How is Argus doing prompt. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-09-result-quick-take-feedback.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-09-result-quick-take-feedback.txt) |
| en-10-feedback-rated | Rating the feedback ask saves and acknowledges it. | Thanks for telling us. | PASS: The prompt changed to Thanks for telling us after Good. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-10-feedback-rated.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-10-feedback-rated.txt) |
| en-11-result-details | Expanded result details preserve contributions, assumptions and net costs. | $16,800; Starting capital $6,000; Contribution $200 monthly | PASS: Details show $16,800 contributed, $6,000 starting capital, $200 monthly and modeled costs. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-11-result-details.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-11-result-details.txt) |
| en-12-breakdown | Breakdown gives a sourced holding experience grounded in the result. | Breakdown; 54 purchases and no sales; 3 sources | PASS: Breakdown preserved DCA amounts, 38.1-point gap and April 21, 2022 to October 5, 2023 worst-drop dates with three sources. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-12-breakdown.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-12-breakdown.txt) |
| en-13-breakdown-dates | The lower Breakdown shows exact worst-drop dates and benchmark gap. | April 21, 2022; October 5, 2023; 38.1 percentage points | PASS: Dates and the 38.1-percentage-point gap are visible in the Breakdown. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-13-breakdown-dates.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-13-breakdown-dates.txt) |
| en-14-result-follow-up | The follow-up states gap, dollar costs and worst-drop dates with one next-steps list. | $25.17 in total: $16.78 in fees and $8.39 in slippage; four prose steps plus Try next | FAIL: Facts are correct, but next steps appear twice: a prose list and the matching Try next controls. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-14-result-follow-up.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-14-result-follow-up.txt) |
| en-15-decision-saved | A decision saves on the result. | Decision: Watching | PASS: The result now reads Decision: Watching. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-15-decision-saved.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-15-decision-saved.txt) |
| en-16-feedback-and-decision-reload | After another reply and reload, feedback stays dismissed and decision and Breakdown persist. | Decision: Watching; Breakdown; feedback ask absent | PASS: No feedback ask returned; Decision: Watching and the finished Breakdown survived reload. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-16-feedback-and-decision-reload.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-16-feedback-and-decision-reload.txt) |
| en-17-research-attempt-1 | The valuation and outlook question publishes research with sources. | I couldn't complete the data lookup just now, so I won't quote live figures. | FAIL: The turn disclosed that data lookup could not complete and published no live figures. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-17-research-attempt-1.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-17-research-attempt-1.txt) |
| en-18-research-attempt-2 | One retry after two minutes publishes the requested research. | I couldn't complete the data lookup just now, so I won't quote live figures. | FAIL: The single retry timed out and again disclosed lookup unavailability. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-18-research-attempt-2.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-18-research-attempt-2.txt) |
| en-19-result-rail | A long conversation shows a tick that navigates to its saved result. | Decision saved: KO · DCA Accumulation | PASS: The KO result appears as Decision saved after its decision was added, and the tick navigates to it. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-19-result-rail.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-19-result-rail.txt) |
| en-20-sharing-selection | Completed result and sourced answers can be selected in the chat-header sharing dialog. | 0 of 0 selected; This answer is not complete yet; The text contains private information or codes. | FAIL: The dialog shows 0 of 0 selected; every answer is disabled, including the completed result and sourced Breakdown. | [image](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-20-sharing-selection.png) / [text](../reports/evidence/2026-09-12-main-promotion/browser-walk/en-20-sharing-selection.txt) |
| en / Clarifying reply preserves an earlier fact | Clarifying reply preserves an earlier fact | Not observed | NOT RUN: The same-chat setup inherited the prior period and did not ask a question. A fresh-chat clarification was still owed when the sharing stop occurred. | No capture after the blocking stop |
| en / Sharing preview and local link creation | Sharing preview and local link creation | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| en / Signed-out phone-width shared answer | Signed-out phone-width shared answer | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| en / Revoke local link | Revoke local link | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| en / Revoked link stops working | Revoked link stops working | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Signed-in empty greeting | Signed-in empty greeting | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / New account first profile save | New account first profile save | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Home country persistence | Home country persistence | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Usage labels | Usage labels | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Backtest confirmation | Backtest confirmation | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / First card edit | First card edit | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Second edit retains first | Second edit retains first | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Result and Quick take | Result and Quick take | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Breakdown with sources | Breakdown with sources | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Conversation after result: one next-step list, gap, dollar costs, worst-drop dates | Conversation after result: one next-step list, gap, dollar costs, worst-drop dates | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Feedback ask once | Feedback ask once | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Feedback rating and no return | Feedback rating and no return | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Clarifying reply preserves an earlier fact | Clarifying reply preserves an earlier fact | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Forward-looking or valuation research with sources | Forward-looking or valuation research with sources | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Decision saved on result | Decision saved on result | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Result rail tick | Result rail tick | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Pick answers from chat header | Pick answers from chat header | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Sharing preview and local link creation | Sharing preview and local link creation | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Signed-out phone-width shared answer | Signed-out phone-width shared answer | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Revoke local link | Revoke local link | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |
| es-419 / Revoked link stops working | Revoked link stops working | Not observed | NOT RUN: Stopped at the confirmed English sharing blocker under Step 6. | No capture after the blocking stop |

Free checks on this stop record passed: 24 release-evidence tests in 22.30 seconds and 259 mocked harness checks in 34.93 seconds. Logs: `browser-walk/release-docs-tests.log` and `browser-walk/mocked-harness.log`. `browser-walk/verification.json` confirms no non-doc changes, measured-tree byte identity, absent acceptance env files, valid evidence paths and the secret scan.

CI and fresh exact-head review are checked on the docs-only evidence head after this record is committed. Their receipts belong to PR #603; the earlier review on `2d99bcb` is not proof for this head. A green CI or clean code-review result does not close this sharing blocker or the unexecuted acceptance scope.

## Historical Step 2 Stop Record (Superseded by Approved Resumption)

Evidence directory: `docs/reports/evidence/2026-09-12-main-promotion/`.

- `production-readback-before.json`: all three live triggers are `off`; API and app are `live` at `ee9c3491fa6219502f1e94abc5d9e661a06839d9`, workflow is `ready` at `ee9c349`. These values were read only.
- `main-branch-protection-before.json`: required context `ci`, strict checks and admin enforcement on, force pushes and branch deletion off. Nothing changed.
- `setup.log`: required setup completed with the explicit canonical-root override, Python 3.10.20, Poetry 2.1.3 and Bun 1.3.14.
- `mocked-eval.log`: 259 passed, exit 0, 41.93 seconds. Provider credentials blanked and synthetic data selected.
- `release-contract-tests.log`: 87 passed and one failed, exit 1. The new skeleton has no durable live eval scorecard because Step 3 has not run. This is an outstanding evidence requirement, not a product regression. No test was weakened or waived.
- `modularity.log`: no violations. Main is an ancestor, so the candidate is also the would-be merged product tree.
- `local-smoke.log`: exit 28 after API health and workflow probe passed. Exact error: `curl: (28) Operation timed out after 20010 milliseconds with 0 bytes received`. Product readiness did not complete. Cause is unclassified; no retry, timeout change or product fix has been made. The smoke processes exited and no listener remains on their ports 8126 or 3126.
- `environment-parity-before.json`: Render literals, release-profile keys and contract arrays agree for API and web. The template inventory found undocumented settings: `ARGUS_STRUCTURED_REASONING_EFFORT`, `ARGUS_CAPABILITY_REASONING_EFFORT`, `ARGUS_ENV`, `ARGUS_APP_ENV`, `ARGUS_RENDER_WORKFLOW_PROOF_TIMEOUT_SECONDS`, `ARGUS_RENDER_WORKFLOW_PROOF_POLL_SECONDS`, and `ARGUS_WORKFLOW_PROOF_USER_ID`. These are documentation gaps, not an established product regression. Their absence from the live release contract means the production defaults still apply. The initial static inventory is not exhaustive; dynamic task-timeout keys remain to be covered by the resumed full parity pass.
- `DATABASE_URL` is intentionally derived and documented; `MEM0_TELEMETRY` is forced off internally; `RENDER_TASK_RUN_ID` is platform-supplied. These are not requested configuration changes.
- `measured-tree-identity.json`: the product paths from the prior promotion and every non-doc Git path are unchanged from the measured head. This stop-record commit contains docs and evidence only.
- `preflight-status.json`: gate outcomes, zero spend, no live mutations and local cleanup record.

The founder's explicit stop rule for an unexpected environment check applies. The migration gate, promotion PR, Step 3 pair, founder browser walk and historical replay have not started. No production user text was extracted. Spend is $0 of $3.50 for the pair, $0 of $3 for the walk, and $0 of $4 for replay. No fix round has been used.

Requested decision: approve a bounded environment-template correction and resumption of Step 2, or accept the documented template gaps for this promotion. This does not authorize a migration, live setting change, deployment, merge, or production sharing link.


## Step 2 Approved Resumption

The founder approved the template correction and one unchanged smoke rerun in this task. Commit `df7aee12955f667e31057464d62c72287fb12247` adds 31 one-line setting descriptions to `.env.example`, including the original seven and the full parity findings. They are comments; parsed template values are unchanged. No real environment file was written. This commit defines the measured head before any paid measurement.

- `environment-parity-after.json`: full pass across 144 runtime/operator keys, including all 15 dynamic task timeout keys. No intended hosted setting is missing from the release contract. Optional undeclared settings retain production code defaults.
- `template-added-keys.json`: complete list of 31 additions and unchanged effective template values. The founder confirmed the original seven gaps predate this bundle.
- `direct-readiness.json`, `direct-readiness.log`, `direct-readiness-api.log`: the one direct timed request in the unchanged smoke environment returned HTTP 503 in 1.178 seconds. The runtime and synthetic asset check were ready; memory-mode Supabase degradation is expected by this smoke.
- `local-smoke-rerun-status.json`, `local-smoke-rerun.log`, `local-smoke-rerun-api.log`, `local-smoke-rerun-web.log`: the single approved rerun at the new measured head passed, exit 0, in 5.394 seconds. Neither timeout changed. Both timeout-owning files are byte-identical to main.
- `free-gates-df7aee12.log`: mocked and release checks totaled 346 passed, one failed in 34.18 seconds. The sole failure is the pending durable live scorecard requirement for this manifest. It must pass after Step 3; no test was weakened.
- `modularity-df7aee12.log`: passed. No newer integration work was included.
- `production-migration-gate-before.json`: expected seven-migration block, read only. Historical reconciliation matches; no additional stop reason. No schema application occurred.
- `measured-tree-identity.json`: product paths and every non-doc Git path match the new measured head. Later evidence commits touch only docs.

The initial stop record above is retained as history, not an outstanding approval request. Paid spend remains zero for each of the eval pair, browser walk and replay. No production conversation content has been extracted. No fix round has been used.

## Local Production Configuration Key Record

Captured before startup at the measured head. Secret-bearing keys record only presence. Every literal is set, and only the founder-approved substitutions differ. No value contains the production Supabase reference or production app domain. Process basics are PATH and HOME.

### argus-api

| Key | Local value or secret presence |
| --- | --- |
| `ALPACA_API_KEY` | `present` |
| `ALPACA_PAPER_TRADING` | `true` |
| `ALPACA_SECRET_KEY` | `present` |
| `APP_ENV` | `production` |
| `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD` | `absent` |
| `ARGUS_APP_ORIGIN` | `http://localhost:3136` |
| `ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED` | `false` |
| `ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT` | `10` |
| `ARGUS_BACKTEST_JOBS_GLOBAL_RUNNING_LIMIT` | `5` |
| `ARGUS_BACKTEST_JOBS_SHADOW_ENABLED` | `true` |
| `ARGUS_BACKTEST_JOBS_USER_QUEUED_LIMIT` | `2` |
| `ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT` | `1` |
| `ARGUS_BACKTEST_REAL_WORKFLOW_TASK` | `argus-backtests/run_backtest_job` |
| `ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED` | `false` |
| `ARGUS_BACKTEST_WORKFLOW_TASK` | `argus-backtests/workflow_proof` |
| `ARGUS_CHAT_FALLBACK_MODEL` | `qwen/qwen3.5-9b` |
| `ARGUS_CHAT_MODEL` | `deepseek/deepseek-v4-flash` |
| `ARGUS_CHECKPOINTER_MODE` | `postgres` |
| `ARGUS_CONTEXT_FALLBACK_MODEL` | `deepseek/deepseek-v4-flash` |
| `ARGUS_CONTEXT_MODEL` | `openai/gpt-oss-120b` |
| `ARGUS_CONTEXT_PACKETS_ENABLED` | `true` |
| `ARGUS_CONTEXT_PACKET_BUDGET_SECONDS` | `4` |
| `ARGUS_CORS_ALLOW_ORIGINS` | `http://localhost:3136` |
| `ARGUS_DEV_MEMORY_FALLBACK` | `false` |
| `ARGUS_DISCOVERY_SEARCH_PROVIDER` | `perplexity_direct` |
| `ARGUS_ENABLE_EXECUTION_REALISM` | `true` |
| `ARGUS_ENABLE_MEMORY_SEMANTIC_RECALL` | `false` |
| `ARGUS_ENABLE_PERSONALIZATION_MEMORY` | `true` |
| `ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED` | `true` |
| `ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY` | `present` |
| `ARGUS_IN_PLACE_CARD_EDITS_ENABLED` | `true` |
| `ARGUS_MARKET_DATA_PROVIDER_MODE` | `live_provider` |
| `ARGUS_MEMORY_EMBEDDING_DIMENSIONS` | `1024` |
| `ARGUS_MEMORY_EMBEDDING_MODEL` | `pplx-embed-v1-0.6b` |
| `ARGUS_MEMORY_EMBEDDING_TIMEOUT_SECONDS` | `8.0` |
| `ARGUS_MEMORY_VECTOR_COLLECTION` | `argus_memory_vectors` |
| `ARGUS_MOCK_AUTH` | `false` |
| `ARGUS_OPENROUTER_RESULT_SUMMARY_TIMEOUT_SECONDS` | `30` |
| `ARGUS_OPS_TOKEN` | `present` |
| `ARGUS_PERSISTENCE_MODE` | `supabase` |
| `ARGUS_PROD_OPENROUTER_API_KEY` | `present` |
| `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED` | `true` |
| `ARGUS_READINESS_ASSET_TIMEOUT_SECONDS` | `25` |
| `ARGUS_READOUT_FALLBACK_MODEL` | `openai/gpt-5.6-luna` |
| `ARGUS_READOUT_MODEL` | `openai/gpt-5.6-luna` |
| `ARGUS_RESEARCH_GLOBAL_DAILY_CEILING` | `5000` |
| `ARGUS_RESEARCH_RAIL_ENABLED` | `true` |
| `ARGUS_RUNTIME_EVENT_KEEPALIVE_SECONDS` | `15` |
| `ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS` | `180` |
| `ARGUS_STRUCTURED_FALLBACK_MODEL` | `anthropic/claude-haiku-4.5` |
| `ARGUS_STRUCTURED_MODEL` | `x-ai/grok-4.3` |
| `ARGUS_TITLE_AUTOGEN_ENABLED` | `true` |
| `ARGUS_TITLE_AUTOGEN_TIMEOUT_MS` | `250` |
| `ARGUS_UTILITY_FALLBACK_MODEL` | `qwen/qwen3.5-9b` |
| `ARGUS_UTILITY_MODEL` | `google/gemini-2.5-flash-lite` |
| `ARGUS_VISITOR_KEY_SECRET` | `present` |
| `DATABASE_URL` | `present` |
| `HOME` | `/private/tmp/argus-promotion-20260912-supabase/home` |
| `MARKET_DATA_CACHE_TTL` | `43200` |
| `PATH` | `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin` |
| `PERPLEXITY_API_KEY` | `present` |
| `POETRY_VERSION` | `2.1.3` |
| `POSTHOG_PROJECT_TOKEN` | `absent` |
| `POSTHOG_REGION` | `us` |
| `RENDER_API_KEY` | `absent` |
| `SUPABASE_ANON_KEY` | `present` |
| `SUPABASE_JWT_SECRET` | `present` |
| `SUPABASE_SERVICE_ROLE_KEY` | `present` |
| `SUPABASE_URL` | `http://127.0.0.1:56531` |

### argus-app

| Key | Local value or secret presence |
| --- | --- |
| `ARGUS_APP_ORIGIN` | `http://localhost:3136` |
| `HOME` | `/private/tmp/argus-promotion-20260912-supabase/home` |
| `NEXT_PUBLIC_APP_ENV` | `production` |
| `NEXT_PUBLIC_ARGUS_API_URL` | `http://localhost:8136/api/v1` |
| `NEXT_PUBLIC_ARGUS_LOCAL_QA_CAPTCHA_TOKEN` | `present` |
| `NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL` | `support@get-argus.com` |
| `NEXT_PUBLIC_ARGUS_TURNSTILE_SITE_KEY` | `absent` |
| `NEXT_PUBLIC_ENABLE_SPANISH` | `true` |
| `NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED` | `true` |
| `NEXT_PUBLIC_MOCK_AUTH` | `false` |
| `NEXT_PUBLIC_OMNISEARCH_ENABLED` | `true` |
| `NEXT_PUBLIC_POSTHOG_KEY` | `absent` |
| `NEXT_PUBLIC_RESEARCH_RAIL_ENABLED` | `true` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `present` |
| `NEXT_PUBLIC_SUPABASE_URL` | `http://127.0.0.1:56531` |
| `PATH` | `/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin` |
