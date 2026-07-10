# Private Alpha Release Manifest — Interpret-surface burn-down candidate

Status: READY FOR FOUNDER APPROVAL. Readiness, deploy, environment, and canary
evidence are complete for the private-alpha Render surface. This is not a
merge-to-main or production approval.

## Candidate

- Candidate SHA: `62e65c0c539f2e3d1753cd680dd9f4f773dc0f08` (two-parent reconciliation merge of integration tip `ddec6e1` and `main` tip `aae1a34`; all conflict resolutions kept integration as the current truth, while non-conflicting #128 changes were retained)
- Candidate branch: `codex/private-alpha-next`
- Promotion target: `main`
- Release captain: Codex (owns the Render/provider promotion ritual)
- Approver: founder
- Rollback target: current `main` tip prior to this promotion
- Decision record: the interpret-surface burn-down (roadmap "Main-promotion burn-down") — issues #160/#151/#171/#150/#187/#188 all fixed and merged

## What this candidate contains (scope)

The full interpret/edit-surface burn-down, in merge order:
- PR #182 — #171 Sig1/Sig2, #160(B), #150 behavior half
- PR #185 — #160(A) composer-declined edits re-enter the typed edit contract
- PR #186 — #151 post-result/confirmation-edit turns materialize the typed card
- PR #187 — benchmark-keep regression (demo-caught)
- PR #190 — #188 chip asset edits operation-agnostic, two P1 desync corners closed, bare-ticker hardened
- Off-spine: PR #169 (regression-sweep CI), PR #183 (typed degraded-fallback + es-419 parity)

Chips and natural language now converge on one typed edit contract on both the
post-result and confirmation surfaces.

The reconciliation merge adds `main` ancestry without replacing the trusted
integration implementation. All 46 conflicted paths retained the integration
version. Relative to `ddec6e1`, the resulting tree adds only the non-runtime
P2.1 capability-audit document from #128; the named #128 runtime/release-tooling
changes were already present and remain intact.

## Gate Evidence (readiness — my part of the handoff)

- Mocked spine sweep on exact candidate `62e65c0`: **1035 passed, 0 failed, 0 xfailed** (`tests/agent_runtime` + `tests/test_spine_guardrails.py`, hermetic `synthetic_unit_fixture`). Modularity budgets green.
- #188 live proof (interpreter-facing live gate, real Grok, run independently pre-merge): chip `remove AAPL` → {MSFT,NVDA}; bare `TSLA` → {AAPL,MSFT,NVDA,TSLA} (preserve, code-guaranteed); `add TSLA` → append; `just TSLA` → {TSLA}; compound `drop AAPL and NVDA and add TSLA and AMD` → {MSFT,TSLA,AMD}.
- Full live eval suite on the pre-reconciliation integration tip (`ddec6e1`), real Grok / render.yaml tiers, `live_provider`: **17 passed, 4 failed** (scorecard `argus-eval-scorecard-20260710T035708Z.json`). The reconciliation tree adds no runtime file relative to that tip; exact-candidate runtime proof was refreshed through the hermetic sweep, clean-checkout suite, and Render canaries below. All 4 live-eval reds are the known model-tier set, none from the interpret surface:
  - `capability_honesty_options_straddle_tsla`, `graceful_recovery_weekly_options_aapl`, `graceful_recovery_spanish_weekly_options_aapl` — grok options-idea nondeterminism (#159 waiver).
  - `graceful_recovery_spanish_offline_clarifier_missing_period_aapl` — Spanish intent-label flip, A/B-proven pre-existing at base (tier drift, #159 territory), not a lane regression.
  - The #160/#151/#187/#188 cases and the new chip-clarify cases (remove/add/replace/compound) all passed live. Zero interpret-surface regressions.
- Clean-checkout suite gate (#134/#135), fresh detached worktree at exact candidate `62e65c0`, no `.env`, full `tests/`, hermetic flags: **1906 passed, 14 failed, 2 skipped**. The failing node set exactly matches the pre-existing baseline — 5 `test_alpha_api_supabase`, 4 `test_chat_runtime_cutover`, 2 `test_render_workflow_execution`, 1 each `test_alpha_orchestration_regression` / `test_canary_capture_replay` / `test_chat_stream_contract`. All outside `agent_runtime`; zero new regressions. PASS.

## Founder decisions required before promotion

- Options-idea waiver: the grok options-straddle / weekly-options cases (EN + ES) are expected model-tier reds (#159). Confirm they are waived per the issue-tagged expected-fail valve, not spine bugs.

## Deploy Proof

- API service: `argus-api`
- API deploy status: `live`
- API deployed SHA: `62e65c0c539f2e3d1753cd680dd9f4f773dc0f08`
- Web service: `argus-app`
- Web deploy status: `live`
- Web deployed SHA: `62e65c0c539f2e3d1753cd680dd9f4f773dc0f08`
- Checked at: `2026-07-10T15:25:41Z`
- Blueprint/service check: existing `argus-api` and `argus-app` matched `render.yaml`; the service inventory contains one of each and both remain manual deploys (`autoDeployTrigger=off`). No duplicate service or Blueprint sync was needed.

## Environment Proof

- Expected mode: `real-workflow`
- `api_web_env_fingerprint`: `17f938e602e214a340033b6c3b669cf17cda5b6ecc78d4969a7a15e1485c3392`
- `workflow_env_fingerprint`: `5b6f4eb0d33920c1089a1a23f7fce9e1b1842a76550409b98fc99170c5f7e291`
- `workflow_env_status`: `ready`
- `workflow_runtime_provider_mode`: `live_provider`
- `workflow_runtime_proof`: `ready`
- `env_fingerprint` script output: `.github/render-env-sync.sh release-config-audit --expect-mode real-workflow` → `status=ready`, `workflow_env_status=ready`
- `workflow_task`: `argus-backtests/workflow_proof`
- `real_workflow_task`: `argus-backtests/run_backtest_job`
- Backtest service mode: `live_provider`
- Workflow service proof:
  - `argus-backtests` latest deploy/status: `ready`, release commit matches candidate
  - workflow version id: `wfv-d98gl7beo5us73dg3pg0`
  - workflow provider mode verified: `live_provider`
  - effective runtime provider mode verified: `live_provider`
  - effective runtime proof status: `ready`
  - required workflow secrets present with redacted proof: yes
  - active workflow task verified: `argus-backtests/workflow_proof`
  - real workflow task verified: `argus-backtests/run_backtest_job`
- Feature flags: API persistence `supabase`, checkpoint `postgres`, mock auth `false`, workflow shadow/dispatch/execution `true/true/true`; web Spanish `true`, strategies/collections/onboarding/exploratory suggestions `false`, omnisearch `true`
- Render config audit command: `.github/render-env-sync.sh release-config-audit --expect-mode real-workflow`
- Secret rotation / least-privilege owner: no rotation performed; founder/operator owns Render secret management; service-role, ops, provider, and workflow credentials remained redacted

## Gate Evidence

- Local smoke command: `.github/local-smoke.sh --expected-sha 62e65c0c539f2e3d1753cd680dd9f4f773dc0f08`
- Local smoke result: `verification_status=ready`; proof-shadow synthetic fixture; candidate SHA matched
- Warmup command: `.github/warmup-render.sh --expect-mode real-workflow`
- Warmup result: `status=ready` after two bounded cold-start readiness retries; stale jobs `0`; workflow runtime `live_provider` / `ready`
- Canary evidence artifact: `private-alpha-canary-evidence`
- English canary:
  - JSON evidence: `temp/release-evidence/canary-en.json`
  - Candidate/deploy proof: API/web/workflow all matched `62e65c0`; API/web `live`, workflow `ready`
  - Failed-capture replay, if failed: not used
  - Exit status: `0` (`passed`)
- Spanish canary:
  - JSON evidence: `temp/release-evidence/canary-es-419.json`
  - Candidate/deploy proof: API/web/workflow all matched `62e65c0`; API/web `live`, workflow `ready`
  - Failed-capture replay, if failed: not used
  - Exit status: `0` (`passed`)
- Provider-path canary:
  - JSON evidence: `temp/release-evidence/canary-provider-path.json`
  - Focused symbol path: `SNDK,AMD,NVDA,GS`
  - Candidate/deploy proof: API/web/workflow all matched `62e65c0`; async workflow required and verified
  - Failed-capture replay, if failed: not used
  - Exit status: `0` (`passed`)
- Browser QA, if applicable: not run; no local UI changes were made in this gate

## Release Decision

- Public tester exposure approved: **NO — awaiting founder approval**
- Known caveats: readiness package retains the founder decision required for the four known #159 model-tier/options reds; PR #191 remains unmerged and no production deploy or secret rotation occurred
- Rollback trigger: any API/web/workflow SHA mismatch, non-live deploy, config/runtime drift, stale or stuck job, failed warmup, or failed strict canary
- Rollback command or owner: founder/operator; emergency API disable is `.github/render-env-sync.sh api-safe-off`, followed by a manual deploy of the rollback target if approved
- Follow-up owner: founder

## Privacy Notes

- No raw conversation, user, run, or job ids.
- Canary labels are stable hashes for audit correlation only.
- Failed-capture artifacts are sanitized replay inputs, not raw transcripts.
- Service-role credentials, cookies, prompts, and route receipt payloads are not
  copied into this manifest.
