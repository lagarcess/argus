# Private Launch Runbook

> [!NOTE]
> Current operational gate for the controlled private-alpha readiness sprint. For
> sprint scope and no-touch boundaries, see
> `docs/specs/private-alpha-controlled-readiness-panel.md`.

This runbook is for the first trusted-user internet tests on Render.

## Launch URLs

- App: `https://argus-app-suz5.onrender.com`
- API: `https://argus-ohr5.onrender.com`

## Before Tester Sessions

1. Merge the private-launch hardening PR into `main`.
2. In Render, sync the Blueprint from `render.yaml`.
3. Confirm Render is updating the existing `argus-app` and `argus-api` services.
   Stop if Render proposes duplicate services.
4. Confirm both services still have manual deploys enabled.
5. Manually deploy `argus-api`, then `argus-app`.
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

7. Confirm the API is in real workflow tester mode. This mode keeps the API
   lean and sends `Run backtest` through the durable Render Workflow job path:

```bash
.github/render-env-sync.sh api-real-workflow-on
```

Restart `argus-api` after changing Render env values.

8. Run the product warmup script and verify the API stayed in real workflow
   mode. When Supabase verifier credentials are present, this also runs the
   stale queued/running job scan:

```bash
.github/warmup-render.sh --expect-mode real-workflow
```

9. Run the golden-path canary:

```bash
.github/canary-render.sh
```

After the readiness branch is deployed, rerun the same strict canary in Spanish:

```bash
ARGUS_CANARY_LANGUAGE=es-419 ARGUS_CANARY_PROMPT='Prueba una estrategia de comprar y mantener AAPL y MSFT con pesos iguales desde el 1 de enero de 2025 hasta el 5 de junio de 2026 con 10000 dolares' .github/canary-render.sh
```

Before treating local UI changes as launch-ready, also run the browser recovery
spec against the local app/API environment:

```bash
cd web && bun run test:e2e e2e/chat-action-recovery.spec.ts --project=chromium
```

Only send the app URL to testers after both scripts pass. If warmup fails, do
not invite testers yet. Check Render service status and redeploy only if the
service is stuck. If warmup passes but the canary fails, treat it as an Argus
product-path regression and inspect API logs, Supabase messages, backtest runs,
and route receipts for the canary conversation id.

For the daily automated gate, configure GitHub repository secrets with the same
canary variables above plus `RENDER_API_KEY`, then use the scheduled or manually
dispatched `Private Alpha Canary` workflow. That workflow runs
`.github/warmup-render.sh --expect-mode real-workflow` and
`.github/canary-render.sh`; it does not deploy or configure analytics.

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

`api-real-workflow-on` is the controlled private-alpha tester mode: `Run
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

Keep `NEXT_PUBLIC_POSTHOG_KEY` present but empty until PostHog is intentionally
enabled.

Set `ARGUS_OPS_TOKEN` manually in Render for `argus-api`; it is intentionally
`sync: false`. Keep `ARGUS_OPS_TOKEN` out of frontend environment variables.

## Smoke Test

Use an allowlisted account and verify:

- Login succeeds.
- A new conversation can be created.
- Cold-start starter chips are visible, feel current, and do not reference 2024
  by default.
- Clicking a cold-start starter chip submits a natural-language prompt into the
  normal chat runtime.
- A Spanish prompt reaches confirmation without coaching or manual translation.
- A date edit from an active confirmation updates the confirmation/result period
  before execution, for example Jan 1, 2025 to Apr 1, 2025.
- A supported backtest completes and shows a result card.
- The result includes a readable Quick take.
- Explain result opens a deeper card-scoped explanation without replacing the
  Quick take.
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
  listening channel. PostHog/product analytics stay disabled until the
  privacy-safe event taxonomy, redaction, and consent posture are approved.
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
