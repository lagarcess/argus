# Private Alpha Release Manifest: CI/CD SOTA Candidate

Status: Draft PR candidate; not approved for tester exposure
Created: 2026-06-18T03:57:26Z

## Candidate

- Candidate SHA: `b0c7f559bd9cc4641b4533b5520e1ffd2fc38f4f`
- Candidate branch: `codex/private-alpha-next`
- Promotion target: `main`
- Release captain: Codex
- Approver: Founder review pending
- Rollback target: `6bd54656cdc7c0e5840fac5d04f8148e429d8309` (`origin/codex/private-alpha-next` before this candidate stack)
- Decision record: Draft PR review requested. Do not invite testers until live Render warmup, English canary, Spanish canary, and workflow-service proof pass for this SHA.

## Scope

This candidate implements the Private Alpha CI/CD SOTA gate for the issue #117
failure class: a stream-visible generic failure, duplicate retry affordance, and
late persisted artifact that could hydrate as contradictory state after reload.

The branch also includes two small post-gate stabilizers:

- indicator/asset disambiguation for abbreviated indicator edits such as RSI and MACD;
- text-only composer paste/drop enforcement with localized toast feedback.

The future `docs/specs/private-alpha-next-decision-memo.md` work is not part of
this candidate.

## Deploy Proof

- API service: `argus-api`
- API deploy status: Pending live deployment for this SHA
- API deployed SHA: Pending live deployment for this SHA
- Web service: `argus-app`
- Web deploy status: Pending live deployment for this SHA
- Web deployed SHA: Pending live deployment for this SHA
- Checked at: Local candidate verification only

## Environment Proof

- Expected mode: `proof-shadow` for local smoke; `real-workflow` before tester exposure
- api_web_env_fingerprint: `a79f24ce086e50beb80e0086fd41a3f62240c4faa63fc9fc093b638404b60fe0` from local smoke proof-shadow contract
- env_fingerprint script output: `.github/local-smoke.sh --expected-sha "$(git rev-parse HEAD)" --contract-only`
- workflow_task: `argus-backtests/workflow_proof`
- real_workflow_task: `argus-backtests/run_backtest_job`
- Backtest service mode: Pending live Render proof
- Workflow service proof:
  - `argus-backtests` latest deploy/status: Pending live Render proof
  - active workflow task verified: Pending live Render proof
  - real workflow task verified: Pending live Render proof
- Feature flags: private-alpha defaults disabled for strategies, collections, omnisearch, exploratory suggestions, and private-alpha onboarding in local smoke
- Render config audit command: Pending live run, expected `.github/render-env-sync.sh release-config-audit --expect-mode real-workflow`
- Secret rotation / least-privilege owner: Founder/operator confirmation pending before tester exposure

## Gate Evidence

- Local smoke command: `.github/local-smoke.sh --expected-sha "$(git rev-parse HEAD)"`
- Local smoke result: `verification_status=ready`, `workflow_probe=ready`, API/web ready, `readiness_status=degraded` acceptable for local synthetic smoke
- Local smoke contract-only command: `.github/local-smoke.sh --expected-sha "$(git rev-parse HEAD)" --contract-only`
- Local smoke contract-only result: `verification_status=ready`
- Script syntax command: `bash -n .github/canary-render.sh .github/warmup-render.sh .github/render-env-sync.sh .github/local-smoke.sh`
- Script syntax result: passed
- Backend release slice: `poetry run pytest tests/test_environment_scripts.py tests/test_api_import_boundary.py tests/test_render_canary_script.py tests/test_render_runtime_compatibility.py tests/test_private_launch_hardening.py tests/test_checkpoint_rls_migration.py tests/test_ci_workflow.py tests/test_legacy_orchestrator_retirement.py tests/test_chat_backtest_state_machine.py tests/test_openrouter_policy.py tests/agent_runtime/test_execute_recovery.py tests/section3/test_market_data_provider.py -q --no-cov`
- Backend release slice result: `252 passed`
- CI/CD docs/script tests: `poetry run pytest tests/test_environment_scripts.py tests/test_render_canary_script.py tests/test_ci_workflow.py tests/test_private_alpha_release_docs.py -q --no-cov`
- CI/CD docs/script tests result: `66 passed`
- Frontend tests: `cd web && bun test __tests__`
- Frontend tests result: `261 passed`
- Frontend build: `cd web && bun run build`
- Frontend build result: passed
- Ruff: `poetry run ruff check .github scripts src tests`
- Ruff result: passed
- Warmup command: Pending live deployment and secrets, expected `.github/warmup-render.sh --expect-mode real-workflow`
- Warmup result: Pending
- Canary evidence artifact: `private-alpha-canary-evidence` pending live workflow
- English canary:
  - JSON evidence: Pending
  - Exit status: Pending
- Spanish canary:
  - JSON evidence: Pending
  - Exit status: Pending
- Browser QA, if applicable: Spanish discovery picker and text paste were checked live in the local app earlier in this candidate stack; full Playwright recovery matrix pending release environment.

## Release Decision

- Public tester exposure approved: No
- Known caveats:
  - Live Render deploy proof has not run for this SHA.
  - The live canary protects the issue #117 failure class, but it does not use the exact SNDK prompt.
  - Workflow-service proof must be recorded separately from the API/web env fingerprint.
- Rollback trigger: deployed SHA mismatch, failed warmup, failed bilingual canary, env drift, workflow task mismatch, or any reload contradiction evidence.
- Rollback command or owner: Founder/operator. Use Render rollback/manual deploy to restore the prior approved SHA; use `.github/render-env-sync.sh api-safe-off` if workflow mode must be disabled.
- Follow-up owner: Codex release captain for PR review fixes; founder/operator for live Render deploy and tester go/no-go.

## Privacy Notes

- No raw conversation, user, run, or job ids are included.
- Canary labels must be stable hashes for audit correlation only.
- Service-role credentials, cookies, prompts, and route receipt payloads must not
  be copied into this manifest.
