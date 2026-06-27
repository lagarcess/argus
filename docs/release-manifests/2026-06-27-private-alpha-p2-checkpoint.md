# Private Alpha Release Manifest

## Candidate

- Candidate SHA: `e13397ed08b3cd89087b7732f4b63ec24085497a`
- Candidate branch: `codex/promote-2026-06-27`
- Promotion target: `main`
- Release captain: Codex release-gate operator
- Approver: `<founder approval pending>`
- Rollback target:
  - `argus-api`: deploy `dep-d8u6h73tqb8s73asnbd0`, commit `8b169e9e42757eab9724d0bafe25d680e2480bbc`, status `live`
  - `argus-app`: deploy `dep-d8u6idm8bjmc73df1e9g`, commit `8b169e9e42757eab9724d0bafe25d680e2480bbc`, status `live`
  - `argus-backtests`: previous ready workflow version `wfv-d8u6g6rtqb8s73asm93g`, commit `8b169e9e42757eab9724d0bafe25d680e2480bbc`
- Decision record: Gate green locally and on Render; founder merge/promotion remains pending.

## Deploy Proof

- API service: `argus-api`
- API deploy status: `live`, deploy `dep-d905jltaeets73doave0`
- API deployed SHA: `e13397ed08b3cd89087b7732f4b63ec24085497a`
- Web service: `argus-app`
- Web deploy status: `live`, deploy `dep-d905ksegvqtc7396t69g`
- Web deployed SHA: `e13397ed08b3cd89087b7732f4b63ec24085497a`
- Checked at: `2026-06-27T23:36:58Z`

## Environment Proof

- Expected mode: `real-workflow`
- api_web_env_fingerprint: `d47886de71628773843a035e827e027e4bc1b74a9e2dc2c1f5b7f9e1f46cdc24`
- workflow_env_fingerprint: `539d242f7d4aa902b3d6b586b578517b38d9adc5564e3f5e7e92518d78bba2cb`
- workflow_env_status: `ready`
- workflow_runtime_provider_mode: `live_provider`
- workflow_runtime_proof: `ready`
- workflow_task: `argus-backtests/workflow_proof`
- real_workflow_task: `argus-backtests/run_backtest_job`
- Feature flags: Omnisearch true; Spanish true; strategies/collections/onboarding/exploratory suggestions false.
- Render config audit command: `.github/render-env-sync.sh release-config-audit --expect-mode real-workflow`

## Gate Evidence

- Local smoke command: `.github/local-smoke.sh --expected-sha "$(git rev-parse HEAD)"`
- Local smoke result: passed on rerun after initializing this reusable worktree dependencies.
- Warmup command: `.github/warmup-render.sh --expect-mode real-workflow`
- Warmup result: passed; stale job scan `ready` with `scanned=0 stale=0 unresolved=0 errors=0`.
- English canary: `temp/release-evidence/canary-en.json`, status `passed`, result `backtest_run_f02b921b9d37`
- Spanish canary: `temp/release-evidence/canary-es-419.json`, status `passed`, result `backtest_run_3c532699c647`
- Provider-path canary: `temp/release-evidence/canary-provider-path.json`, status `passed`, focused symbols `SNDK,AMD,NVDA,GS`, result `backtest_run_9fd5d5d55359`
- Browser QA: deployed bundle proof shows `omnisearchEnabled` compiled as enabled.

## Release Decision

- Public tester exposure approved: pending founder approval.
- Known caveats: first local smoke attempt failed before product path because this worktree had not installed the package into its fresh `.venv`; setup fixed local dependencies and the exact smoke command then passed.
- Rollback trigger: founder/customer-blocking regression, deploy SHA drift, workflow env drift, failed warmup proof, failed strict canary, or manual founder rollback decision.
- Rollback owner: founder/operator.
- Follow-up owner: founder for merge/promotion approval.

## Privacy Notes

- No raw conversation, user, run, or job ids.
- Canary labels are stable hashes for audit correlation only.
- Failed-capture artifacts are sanitized replay inputs, not raw transcripts.
- Service-role credentials, cookies, prompts, and route receipt payloads are not copied into this manifest.
