# Private Alpha Release Manifest: CI/CD SOTA Candidate

Status: Release gate passed; founder tester-exposure approval pending
Created: 2026-06-18T03:57:26Z
Updated: 2026-06-18T07:28:53Z

## Candidate

- Candidate SHA: `91262e3dbe32e44a963cd9868e370cc2ee33f7a7`
- Candidate branch: `codex/private-alpha-next`
- Pull request: `https://github.com/lagarcess/argus/pull/118`
- Promotion target: `main`
- Release captain: Codex
- Approver: Founder review pending
- Rollback target: `b92e39e84a398fcc051ad1e61966fcbbdb5730c1`
- Decision record: PR #118 is a release candidate. Do not merge to `main` or
  invite testers until the founder approves.

## Scope

This candidate implements the Private Alpha CI/CD SOTA gate for the issue #117
failure class: a stream-visible generic failure, duplicate retry affordance, and
late persisted artifact that could hydrate as contradictory state after reload.

The branch also includes post-gate stabilizers:

- indicator/asset disambiguation for abbreviated indicator edits such as RSI and MACD;
- text-only composer paste/drop enforcement with localized toast feedback;
- removal of hardcoded quick-take language/prose rejection heuristics;
- manual failed-canary capture and local replay support.

The future `docs/specs/private-alpha-next-decision-memo.md` work is not part of
this candidate.

## Deploy Proof

- API service: `argus-api`
- API deploy status: `live`
- API deployed SHA: `91262e3dbe32e44a963cd9868e370cc2ee33f7a7`
- API deploy id: `dep-d8ppmau8mjfs739b1h2g`
- API deploy finished: `2026-06-18T07:20:46.37549Z`
- Web service: `argus-app`
- Web deploy status: `live`
- Web deployed SHA: `91262e3dbe32e44a963cd9868e370cc2ee33f7a7`
- Web deploy id: `dep-d8ppoo36sc1c73d0l79g`
- Web deploy finished: `2026-06-18T07:23:00.612258Z`
- Checked at: `2026-06-18T07:28:53Z`

## Environment Proof

- Expected mode: `real-workflow` for live private-alpha canaries
- api_web_env_fingerprint: `b7051661f128d6030d7a3de3b3149a67ff7e2853e6d34d2f6db51db2b2748173`
- env_fingerprint script output: `.github/render-env-sync.sh release-config-audit --expect-mode real-workflow`
- workflow_task: `argus-backtests/workflow_proof`
- real_workflow_task: `argus-backtests/run_backtest_job`
- Backtest service mode: real workflow dispatch/execution enabled from `argus-api`
- Workflow service proof:
  - `argus-backtests` workflow id: `wfl-d8hpsmuq1p3s73duv3q0`
  - latest listed workflow version: `wfv-d8pob30js32c738tue30`, status `ready`
  - active workflow task verified: warmup release-config audit reported `argus-backtests/workflow_proof`
  - real workflow task verified: English and Spanish canaries each completed a
    `backtest_job` result through `argus-backtests/run_backtest_job`
- Feature flags: strategies, collections, omnisearch, exploratory suggestions,
  and private-alpha onboarding disabled on the live web/API surfaces
- Render config audit command: `.github/render-env-sync.sh release-config-audit --expect-mode real-workflow`
- Secret rotation / least-privilege owner: Founder/operator confirmation pending before tester exposure

## Gate Evidence

- Local smoke command: `.github/local-smoke.sh --expected-sha "$(git rev-parse HEAD)"`
- Local smoke result: `verification_status=ready`, `workflow_probe=ready`,
  API/web ready, `readiness_status=degraded` acceptable for local synthetic smoke
- Local smoke env fingerprint: `a79f24ce086e50beb80e0086fd41a3f62240c4faa63fc9fc093b638404b60fe0`
- Warmup command: `.github/warmup-render.sh --expect-mode real-workflow`
- Warmup result: passed after cold readiness retries; API health, product
  readiness, frontend, stale queued/running job scan, and release-config audit
  all passed
- Script syntax command: `bash -n .github/canary-render.sh .github/warmup-render.sh .github/render-env-sync.sh`
- Script syntax result: passed
- Runtime/release verification command: `poetry run pytest tests/agent_runtime/test_execute_recovery.py -q --no-cov`
- Runtime/release verification result: `60 passed`
- CI/CD verification command: `poetry run pytest tests/test_environment_scripts.py tests/test_ci_workflow.py tests/test_private_alpha_release_docs.py tests/test_render_canary_script.py tests/test_canary_capture_replay.py -q --no-cov`
- CI/CD verification result: `74 passed`
- Ruff command: `poetry run ruff check src/argus/agent_runtime/stages/explain.py scripts/ops/canary_capture_replay.py tests/agent_runtime/test_execute_recovery.py tests/test_canary_capture_replay.py tests/test_render_canary_script.py tests/test_private_alpha_release_docs.py`
- Ruff result: passed
- Canary evidence artifact: local release evidence files in `temp/release-evidence/`; GitHub artifact name remains `private-alpha-canary-evidence`
- English canary:
  - JSON evidence: `temp/release-evidence/canary-en.json`
  - Status: `passed`
  - Conversation label: `conversation_06f020ae4a93`
  - Backtest job label: `backtest_job_d5b84c54827f`
  - Result label: `backtest_run_c4d1aca36bf8`
  - Failed-capture replay, if failed: not applicable
  - Exit status: `0`
- Spanish canary:
  - JSON evidence: `temp/release-evidence/canary-es-419.json`
  - Status: `passed`
  - Conversation label: `conversation_92893241792a`
  - Backtest job label: `backtest_job_bcb67b685267`
  - Result label: `backtest_run_98159c891969`
  - Failed-capture replay, if failed: not applicable
  - Exit status: `0`
- Browser QA, if applicable: not rerun in this live-gate pass. The release gate
  used local smoke plus authenticated live English/Spanish canaries.

## Release Decision

- Public tester exposure approved: No
- Known caveats:
  - Founder PR review and tester-exposure approval are still pending.
  - The live canary protects the issue #117 failure class, but it does not use
    the exact SNDK prompt.
  - Render workflow version metadata does not expose a commit id in the current
    CLI/API output; real workflow task execution was verified by completed
    English and Spanish canary jobs.
- Rollback trigger: deployed SHA mismatch, failed warmup, failed bilingual
  canary, env drift, workflow task mismatch, or any reload contradiction
  evidence.
- Rollback command or owner: Founder/operator. Use Render rollback/manual deploy
  to restore `b92e39e84a398fcc051ad1e61966fcbbdb5730c1`; use
  `.github/render-env-sync.sh api-safe-off` if workflow mode must be disabled.
- Follow-up owner: Founder/operator for go/no-go; Codex release captain for PR
  review fixes only.

## Privacy Notes

- No raw conversation, user, run, or job ids are included.
- Canary labels are stable SHA-256 prefixes for audit correlation only.
- Failed-capture artifacts are sanitized replay inputs, not raw transcripts.
- Service-role credentials, cookies, prompts, and route receipt payloads are not
  copied into this manifest.
