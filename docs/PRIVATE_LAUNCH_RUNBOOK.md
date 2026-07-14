# Private Launch Runbook

> [!NOTE]
> Current operational gate for Private Alpha candidate validation. Use
> `docs/specs/private-alpha-next-roadmap.md` and
> `docs/specs/private-alpha-next-decision-memo.md` for product sequencing; use
> this runbook with `docs/specs/private-alpha-ci-cd-sota.md` and
> `docs/release-manifests/TEMPLATE.md` for release gating.
> For CI/CD promotion decisions, the decision memo is a later-context document, not part of this release gate.

> [!NOTE]
> The validated 2026-07-14 private-alpha checkpoint is recorded in
> [`docs/release-manifests/2026-07-14-private-alpha-release-integrity.md`](release-manifests/2026-07-14-private-alpha-release-integrity.md)
> and [#197's closure evidence](https://github.com/lagarcess/argus/issues/197#issuecomment-4965556704).
> It validates the existing branch-deployed private-alpha Render surface; it did
> not merge `main`, deploy production, enable automatic production deployment,
> invite testers, or expose testers.

This runbook is for the first trusted-user internet tests on Render.

## Launch URLs

- App: `https://argus-app-suz5.onrender.com`
- API: `https://argus-ohr5.onrender.com`

## Before Tester Sessions

The promotion target is `main`, but `codex/private-alpha-next` remains the
integration staging branch until the founder approves promotion. Do not merge to
`main`, open a release PR, or deploy production automatically; after founder
approval, promotion still follows the gate below. Every candidate needs a
release manifest before testers are invited; start from
`docs/release-manifests/TEMPLATE.md` and fill it with the exact candidate SHA,
API/web env fingerprint, workflow-service proof, canary evidence, rollback
target, and approver.

Local preflight doctrine:

- Run `.github/setup.sh` first and confirm `poetry run python --version` reports
  the `.python-version` runtime (`3.10.x`; currently `3.10.20`). Python 3.14
  green runs are non-canonical for deployed-runtime proof.
- Do local candidate work from sibling worktrees only, never nested inside
  another Argus checkout, so dotenv cannot inherit a parent `.env` and turn a
  mocked run into a live-provider run.
- For deterministic agent-runtime sweeps, blank live provider keys and set
  `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`. A clean mocked sweep
  is seconds-scale; minutes means stop and investigate live-call leakage.

1. Confirm the local checkout is the candidate commit you intend to promote:

```bash
git status --short
git rev-parse HEAD
```

2. Run the local predeploy smoke gate before any internet-facing canary:

```bash
.github/local-smoke.sh --expected-sha "$(git rev-parse HEAD)"
```

3. In Render, sync the Blueprint from `render.yaml` only when service config
   drift needs reconciliation.
4. Confirm Render is updating the existing `argus-app` and `argus-api` services.
   Stop if Render proposes duplicate services.
5. Confirm both services still have manual deploys enabled.
6. Export local ops and canary secrets, or keep these in the root `.env` file
   and let the scripts load them:

```bash
export ARGUS_OPS_TOKEN="..."
export ARGUS_CANARY_EMAIL="..."
export ARGUS_CANARY_PASSWORD="..."
export ARGUS_CANARY_SUPABASE_URL="https://lgdhvepyrzbnscqssgqq.supabase.co"
export ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY="..."
```

For local founder/operator runs, `.github/canary-render.sh` also accepts
`MOCK_USER_EMAIL` / `MOCK_USER_PASSWORD` and `SUPABASE_URL` /
`SUPABASE_SERVICE_ROLE_KEY` from the root `.env`. The `ARGUS_CANARY_*` names
remain the preferred GitHub Actions secret names.

7. Confirm the API is in real-workflow private-alpha validation mode. This mode
   keeps the API lean and sends `Run backtest` through the durable Render
   Workflow job path:

```bash
.github/render-env-sync.sh api-real-workflow-on
```

Restart `argus-api` after changing Render env values.

8. Manually deploy `argus-api`, then `argus-app` from the candidate commit.

9. Confirm the live `argus-api` and `argus-app` deploy commits match the
   candidate commit you intend to test and that both latest deploys are `live`:

```bash
ARGUS_RELEASE_SHA="$(git rev-parse HEAD)"
.github/render-env-sync.sh api-deploy-status
.github/render-env-sync.sh web-deploy-status
```

If either commit is not `ARGUS_RELEASE_SHA`, stop and deploy the stale service
before running the strict canaries. The canary script enforces the same deployed
SHA/status check with `ARGUS_CANARY_SHA`.

10. Run the product warmup script and verify the API stayed in real workflow
   mode. When Supabase verifier credentials are present, this also runs the
   stale queued/running job scan:

```bash
.github/warmup-render.sh --expect-mode real-workflow
```

11. Run the authoritative Spanish release journey with privacy-safe evidence.
This is the only release canary: it checks the exact deployed SHA, the real
Render workflow, finalized evidence identity, explicit decision capture, reload
hydration, Omnisearch provenance, and the deployed Spanish signup/login browser
path. It uses `ARGUS_CANARY_*` credentials when set and otherwise the local
`MOCK_USER_EMAIL` / `MOCK_USER_PASSWORD` aliases.

```bash
cd web && bun install --frozen-lockfile && bunx playwright install chromium
cd ..
mkdir -p temp/release-evidence
ARGUS_CANARY_SHA="$(git rev-parse HEAD)" \
ARGUS_CANARY_EVIDENCE_PATH=temp/release-evidence/canary-es-419.json \
.github/canary-render.sh
```

If a canary fails after warmup passed, do not redeploy one-off fixes in a loop.
Set `ARGUS_CANARY_CAPTURE_PATH=temp/release-evidence/canary-es-419-failed-capture.json`,
rerun it once to write a sanitized failed-capture artifact, then replay the
captured payload locally before redeploying:

```bash
poetry run python scripts/ops/canary_capture_replay.py \
  temp/release-evidence/canary-es-419-failed-capture.json
```

If the exact candidate reaches the API but returns the normal interpreter
recovery response, keep the failed capture and evidence. Record the safe HTTP
status, route-receipt task/outcome summary, and environment fingerprint first;
do not increase token budgets or switch models as a speculative fix.

Use the replay to identify the macro-pattern and make one coherent fix.
Docker is optional for this step unless the production release path moves to
container images; prefer the local smoke gate plus canary replay first.

Before treating local UI changes as launch-ready, also run the browser recovery
spec against the local app/API environment:

```bash
cd web && bun run test:e2e e2e/chat-action-recovery.spec.ts --project=chromium
```

Only send the app URL to testers after API deploy-status, app deploy-status,
local smoke, warmup, the authoritative Spanish release canary, and the release
manifest all pass against the intended candidate commit. If either deploy-status
reports a different commit, deploy the candidate branch before continuing. If
warmup fails, do not invite testers yet. Check Render service status and redeploy
only if the service is stuck. If warmup passes but the canary fails, treat it as
an Argus product-path regression and inspect the failed-capture replay, API logs,
Supabase messages, backtest runs, and route receipts using the hashed labels and
internal access controls from the canary evidence.

For the daily automated gate, configure GitHub repository secrets with the same
canary variables above plus `RENDER_API_KEY` and `ARGUS_WORKFLOW_DATABASE_URL`,
then use the scheduled or manually dispatched `Private Alpha Canary` workflow.
Set `ARGUS_WORKFLOW_DATABASE_URL` from the `.env`/`.env.example` mapping to
`SUPABASE_POSTGRES_TRANSACTION_POOLER_URL`; do not use the session pooler for
short-lived workflow tasks. That workflow runs the local smoke gate, warmup,
and the authoritative Spanish release journey. The real backtest in that journey
is the live-provider drift check: it runs on `argus-backtests`, while
`release-config-audit --expect-mode real-workflow` proves the workflow env itself
is using `live_provider`. Warmup then runs the deployed `workflow_proof` task and requires
`workflow_runtime_provider_mode=live_provider` and
`workflow_runtime_proof=ready`, proving effective workflow runtime rather than
only saved Render env vars. It uploads the `private-alpha-canary-evidence`
artifact containing Spanish release evidence plus its exit-code file, and it does
not deploy or configure analytics. Secrets are scoped to the operational steps
that need them; install and artifact upload steps do not receive canary
credentials or service-role keys.

After the gate passes, copy the relevant command output and canary evidence into
a candidate manifest based on `docs/release-manifests/TEMPLATE.md`. The
`env_fingerprint` emitted by `.github/render-env-sync.sh release-config-audit`
remains the API/web environment fingerprint; record it as
`api_web_env_fingerprint` and keep the raw script output for traceability. The
workflow proof is recorded separately as `workflow_env_fingerprint` and
`workflow_env_status`. The workflow env proof must show
`workflow_env_status=ready`, `ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider`,
redacted-present required workflow secrets,
`workflow_runtime_provider_mode=live_provider`, and
`workflow_runtime_proof=ready` before tester exposure. The manifest must also
name the candidate SHA, deployed API/web SHAs, `workflow_task`,
`real_workflow_task`, backtest service mode, workflow-service proof for
`argus-backtests`, canary evidence, rollback target, and approver.

If you need to run only the stale job scan during incident triage:

```bash
.github/stale-backtest-jobs.sh --json
```

For privacy-safe aggregate job health over the existing Supabase
`backtest_jobs.execution_metadata` records:

```bash
poetry run python scripts/ops/alpha_readiness_metrics.py --json
```

This report is operational only. It summarizes job statuses, readout provenance,
and timings without emitting user ids, conversation ids, prompt text, or product
analytics events.

## Backtest Workflow Modes

The permanent Render Workflow service is `argus-backtests`. It owns multiple
tasks:

- `argus-backtests/workflow_proof`: proof/canary task for API -> Render Workflow
  -> Supabase lifecycle validation.
- `argus-backtests/run_backtest_job`: real backtest execution task.

Use explicit API modes instead of editing individual flags by hand:

```bash
.github/render-env-sync.sh api-safe-off
.github/render-env-sync.sh api-proof-shadow-on
.github/render-env-sync.sh api-real-workflow-on
```

`api-real-workflow-on` is the controlled private-alpha validation mode: `Run
backtest` creates a durable real job and the UI reads queued/running/succeeded/
failed state from Supabase. `api-proof-shadow-on` is only for proof dispatch
validation. `api-safe-off` is the emergency rollback mode that disables workflow
dispatch/execution and removes the Render API key from `argus-api`.

## Render Environment Ownership

`render.yaml` is allowed to sync non-secret launch configuration: mode flags,
public service URLs, public Supabase URL/anon key values, feature flags, paper
trading mode, CORS origins, and model routing IDs.

Keep true secrets manual in Render:

- `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `OPENROUTER_API_KEY`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ARGUS_OPS_TOKEN`
- `POSTHOG_PROJECT_TOKEN`

Keep `NEXT_PUBLIC_POSTHOG_KEY` present but empty. Product analytics capture is
server-side only through the sanitized observability envelope.

Set `POSTHOG_REGION="US Cloud"` (or normalized `us`) for US Cloud unless the
founder explicitly changes the analytics data-region posture. US Cloud is a
compliance-posture choice for the current private alpha, not an accidental
default. Do not enable frontend PostHog, autocapture, session replay, or person
profiles.

Set `ARGUS_OPS_TOKEN` manually in Render for `argus-api`; it is intentionally
`sync: false`. Keep `ARGUS_OPS_TOKEN` out of frontend environment variables.

## Runtime Tuning Flags

These are optional runtime knobs (not secrets). Defaults are safe for
private-alpha launch; record any override in the release manifest.

- `ARGUS_ENABLE_EXECUTION_REALISM` — models trading fees + slippage end to end.
  The capability is active by default, but modeled costs remain opt-in per
  idea. Runs without stated fees or slippage stay idealized and retain the "No
  fees/slippage" assumptions footer. Set the flag explicitly to
  `false|0|off|no` only as a kill switch; that restores the pre-realism path
  byte-for-byte. Record any kill-switch override in the release manifest.
- `ARGUS_STRUCTURED_REASONING_EFFORT` / `ARGUS_CAPABILITY_REASONING_EFFORT` —
  per-tier OpenRouter reasoning-effort overrides for the structured
  interpretation and capability-conflict calls
  (`xhigh|high|medium|low|minimal|none`). Unset uses the profile default. Lower
  effort saves cost in dev; run production at full effort. Invalid values are
  ignored with a warning.
- Prompt caching is automatic: structured-artifact calls
  (interpretation/repair/field-fidelity/capability-conflict) send a stable
  prefix so OpenRouter can cache it. No env toggle; it activates for those tasks.
- `ARGUS_RUN_LIVE_EVALS=1` — runs the live eval suite under `tests/evals/` (real
  model spend). Unset/`0` keeps evals mocked. Set it for the pre-merge
  landing-gate run and every `main` promotion candidate.

## Smoke Test

Use an allowlisted account and verify:

- Login succeeds.
- A new conversation can be created.
- Cold-start starter chips are visible, feel current, and do not reference 2024
  by default.
- Clicking a cold-start starter chip submits a natural-language prompt into the
  normal chat runtime.
- A Spanish prompt reaches confirmation without coaching or manual translation.
- Confirmation actions stay card-scoped and structured:
  - `Run backtest` starts the supported job path.
  - `Change dates` updates the confirmation/result period before execution, for
    example Jan 1, 2025 to Apr 1, 2025.
  - `Change asset` preserves the explicit period, capital, and benchmark while
    changing the symbol.
  - `Adjust assumptions` preserves the explicit period, symbol, and benchmark
    while changing the assumption being edited.
  - `Cancel` marks the draft canceled and removes the executable action.
- A supported backtest completes and shows a result card.
- The result includes a readable Quick take.
- Explain result opens a deeper card-scoped explanation without replacing the
  Quick take.
- Retry preserves the failed setup and recovers through a structured action, not
  duplicated user text.
- Reloading the page preserves the conversation, job state, and result.
- Feedback can be submitted.

## Founder-Facing Tester Notes

Before sending the URL, make sure tester instructions say:

- Argus Alpha provides educational historical simulations only, not investment,
  tax, legal, brokerage, or execution advice.
- Alpha backtests are intentionally narrow: same-asset runs only, long-only,
  equal-weight multi-symbol logic, max 5 symbols, and daily bars.
- Market or benchmark data can be unavailable. If that happens, retry the same
  setup, change the dates, or choose a different supported asset/benchmark.
- Feedback buttons and the feedback dialog are the primary first-session
  listening channel. PostHog is limited to the approved server-side product
  events and must not receive raw prompts, credentials, balances, holdings,
  audio, route receipts, provider/model metadata, or frontend session data.
- Terms, Privacy Policy, and explicit alpha consent remain a founder-owned gate
  before inviting users outside the private circle.

## Supabase Persistence Check

Before the smoke test, capture current counts:

```sql
select
  (select count(*) from public.conversations) as conversations_total,
  (select count(*) from public.messages) as messages_total,
  (select count(*) from public.backtest_runs) as backtest_runs_total,
  (select count(*) from public.route_receipts where run_id is not null) as run_receipts_total,
  (select count(*) from public.feedback) as feedback_total;
```

After the smoke test, run the same query. A completed backtest should increase
`backtest_runs_total`, and the related route receipts should include a `run_id`.

## Data Cleanup Boundary

Do not delete Supabase profiles, conversations, messages, runs, or receipts as
part of the launch deploy. Cleanup should be a separate task with a dry-run count
and explicit deletion criteria.
