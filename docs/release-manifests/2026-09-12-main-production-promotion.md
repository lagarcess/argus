# Private Alpha Production Promotion, 2026-09-12

Status: Step 2 resumed after founder approval. Environment parity and the single unchanged smoke rerun passed. The migration gate is blocked only by the seven expected pending migrations. Live acceptance and terminal review remain pending. No live evaluation, browser acceptance, migration application, live configuration change, merge, or deployment has occurred.

## Candidate

- Candidate SHA: `df7aee12955f667e31057464d62c72287fb12247`
- Candidate branch: `codex/production-promotion-20260912`
- Validation status: free gates completed with one pending Step 3 scorecard requirement; not ready for merge.
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

- Expected mode:
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

- Local smoke command:
- Local smoke result:
- Warmup command:
- Warmup result:
- Canary evidence artifact: `private-alpha-canary-evidence`
- Authoritative Spanish release canary:
  - JSON evidence:
  - Exact candidate SHA verified:
  - Finalized evidence/result labels:
  - Decision-note label and reload hydration:
  - Omnisearch source identity:
- Browser signup/login proof:
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
  email, tokens, cookies, headers, screenshots of credentials, or transcript
  dumps. Store only privacy-safe hashes and aggregate/count facts.

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
| Free gates | A: development setup with the explicit canonical-root override | Free | $0 | Smoke, mocked harness, modularity and parity passed; release-doc scorecard check awaits Step 3 |
| Candidate and production baseline eval | B: identical explicit eval env file and both provider modes live | $3.50 combined | $0 | Not started |
| Founder browser walk | C: clean detached worktree, disposable Supabase, production build | $3.00 | $0 | Not started |
| Historical guest replay | C: fresh guest per conversation, ordered user turns | $4.00 | $0 | Count and estimate pending |

Environment A's pre-existing root `.env` symlink resolves through the integration worktree to the exact founder-named real file. `web/.env.local` is absent. No environment file is written through or replaced.

Environment C has no `.env` or `web/.env.local`. API and web launch from empty environments with only declared Render keys, the approved substitutions, process basics, and the localhost QA captcha token. Key-by-key presence, non-secret values, literal parity and forbidden-production-value checks are pending before either server starts.

Local differences to cover after deployment: in-process backtests instead of `argus-backtests`, no Turnstile widget, no PostHog, no emails, and localhost origins. The API retains production key routing and shadow job rows; only if jobs stay queued may shadow mode be turned off and recorded as another local difference.

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
