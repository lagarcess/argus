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
6. Run the warmup script:

```bash
.github/warmup-render.sh
```

When the script prints `Argus is warm and ready for testers.`, send the app URL
to testers.

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
