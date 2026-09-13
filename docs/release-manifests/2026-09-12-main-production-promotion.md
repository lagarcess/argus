# Private Alpha Production Promotion, 2026-09-12

Status: the approved full candidate eval completed with 70 passed and one research-timeout failure. The recorded-text judge replay still failed; the one permitted case rerun passed with research and sources. Release-doc validation is blocked by its pre-existing ten-pair prose A/B requirement, which differs from the founder-approved procedure. The native failure is retained. Paid browser acceptance, historical replay, and final CI/review remain pending. Owned local services are stopped. No migration application, live configuration change, merge, or deployment has occurred.

## Candidate

- Candidate SHA: `df7aee12955f667e31057464d62c72287fb12247`
- Candidate branch: `codex/production-promotion-20260912`
- Validation status: blocked at the release-doc policy conflict after the full eval and permitted followups completed. Not ready for merge.
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

## Founder Scope and Approval Stops

- Promote only the fixed cut. Do not add unfinished board items.
- Acceptance replay is approved. User words stay in private scratch outside the repository and are deleted afterward. Reports contain only case and turn numbers, outcomes, refusal codes and named capabilities, plus separate allowance counts.
- Usage labels approved: Usage, Conversation, Searches with sources, Simulations; Uso, Conversación, Búsquedas con fuentes, Simulaciones.
- Sharing is intended on in production. The live two-flag change awaits its post-merge approval stop. No Blueprint sync is permitted.
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
| Free gates | A: development setup with the explicit canonical-root override | Free | $0 | Smoke, mocked harness, modularity and parity passed; release-doc validator requires an unapproved ten-pair procedure |
| Candidate and production baseline eval | B: identical explicit eval env file and both provider modes live | $7.50 combined, tracked cost plus reserve | $4.88888657926 tracked + $1.02 reserve = $5.90888657926 guarded | Full candidate and permitted followups completed; baseline retained; release policy decision pending |
| Founder browser walk | C: clean detached worktree, disposable Supabase, production build | $3.00 | $0 | Free greeting, signup, profile, country and English Usage checks passed; paid steps pending |
| Historical guest replay | C: fresh guest per conversation, ordered user turns | $4.00 | $0 | New York: 12 conversations / 25 turns, estimated $0.57 tracked; UTC: 14 / 35, estimated $0.79; execution pending |

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

## Step 3 Approved Fresh Candidate Run

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
- Requested decision: approve a bounded release-validator change recognizing this promotion's founder-approved judge-then-one-retry procedure, while retaining the native failure and verifying the supplemental evidence.

Preflight confirmed the measured head, all 71 fixtures and 84 user turns, a clean detached worktree, local module imports, unchanged observer bytes, and the identical process environment and env-file content hash. The completed baseline is retained byte-for-byte. The new guardian appends to the original cost ledger, records the starting event boundary to separate this attempt, and uses an exclusive launch marker to prevent a second launch.

The replay cohort was counted read-only before pricing using both date boundaries. The New York product day is `2026-08-12T04:00:00Z` through `2026-08-13T04:00:00Z`: 12 guest conversations from 12 people, with 25 user turns across their complete histories. The UTC day is midnight to midnight: 14 guest conversations from 14 people, with 35 full-history user turns. Canary and internal accounts are excluded. The New York cohort will be replayed; both counts were reported to the founder before any replay price estimate. Customer message text has not been selected. After reporting both counts, the higher completed-eval tracked cost per user turn (`$0.0225276561`) gives a rounded-up New York estimate of `$0.57`, or `$0.79` for the UTC comparison. These are tracked-cost estimates, excluding unknown receipt costs and the separate guard reserve; the replay stop remains `$4`. No replay has run. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/replay-price-estimate.json`.

At head `0e622738`, PR #603's red CI is the single release-doc test waiting on the complete candidate scorecard. With that scorecard now present locally, the same test reaches the ten-pair policy requirement and fails there. The completed Codex review summary belongs to `2d99bcb4edc6c9e817a524fa295c8d67776ff549`. A fresh Codex review will be requested at the final head; the earlier summary does not satisfy that requirement.

The owned local stack restarted and reset from the measured migrations. Its initial port check encountered the old browser connection in `FIN_WAIT_2`, with no active listener. The scratch launcher now uses normal reusable-address bind semantics for this availability check; no product code, port, or other stack changed. The production web rebuild and empty-environment assertions passed, followed by API health, web health, and readiness. Paid browser turns remain pending the release-policy decision. After the stop, owned API/web/guard processes were stopped and `supabase stop --no-backup --workdir <owned scratch>` succeeded. All owned ports closed, no owned containers remain, and the unrelated stack remained intact. Evidence: `docs/reports/evidence/2026-09-12-main-promotion/local-acceptance/cleanup-release-gate.json`; restart and environment proofs are adjacent. No customer text was pulled.

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
