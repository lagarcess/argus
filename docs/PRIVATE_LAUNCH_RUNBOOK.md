# Private Launch Runbook

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
6. Export local ops and canary secrets:

```bash
export ARGUS_OPS_TOKEN="..."
export ARGUS_CANARY_EMAIL="..."
export ARGUS_CANARY_PASSWORD="..."
export ARGUS_CANARY_SUPABASE_URL="https://lgdhvepyrzbnscqssgqq.supabase.co"
export ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY="..."
```

7. Run the product warmup script:

```bash
.github/warmup-render.sh
```

8. Run the golden-path canary:

```bash
.github/canary-render.sh
```

Only send the app URL to testers after both scripts pass. If warmup fails, do
not invite testers yet. Check Render service status and redeploy only if the
service is stuck. If warmup passes but the canary fails, treat it as an Argus
product-path regression and inspect API logs, Supabase messages, backtest runs,
and route receipts for the canary conversation id.

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
- A messy investing idea reaches the chat runtime.
- A supported backtest completes and shows a result card.
- Reloading the page preserves the conversation and result.
- Feedback can be submitted.

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
