# Argus Narrow MVP Private Beta Runbook

Last updated: 2026-04-16

## 1) Invite Flow (Private Beta)

1. Confirm candidate has accepted beta terms and has a verified email.
2. In Supabase Dashboard, add user to `auth.users` via invite link (email magic link or SSO allowlist).
3. Ensure a `profiles` row exists for the user with default beta-safe values:
   - `subscription_tier = free`
   - `backtest_quota = 50`
   - `remaining_quota = 50`
   - `onboarding_completed = false`
   - `onboarding_step = profile`
4. Ask user to complete onboarding from `/onboarding` and verify redirect to `/builder`.
5. Validate first-run funnel telemetry is present:
   - `onboarding_complete`
   - `draft_success` or `draft_fail`
   - `draft_saved`
   - `backtest_success` or `backtest_fail`
   - `logout`

## 2) Manual Tier Bump (Operator Procedure)

Use this only for support-approved private beta users.

### SQL patch

```sql
update profiles
set
  subscription_tier = 'plus',
  backtest_quota = 500,
  remaining_quota = greatest(remaining_quota, 500)
where id = '<USER_UUID>';
```

### Post-change validation

1. `GET /api/v1/auth/session` for user shows updated `subscription_tier`.
2. Web profile reflects new tier without requiring full re-auth (soft refresh okay).
3. User can run allowed lookback/symbol limits for bumped tier.

## 3) Rollback + Support Steps

### Rollback a bad tier change

```sql
update profiles
set
  subscription_tier = 'free',
  backtest_quota = 50,
  remaining_quota = least(remaining_quota, 50)
where id = '<USER_UUID>';
```

### Draft/backtest support fallback

1. If AI draft fails or quota exhausted, direct user to manual builder path.
2. Confirm user can still save a draft from builder and run manual backtest.
3. If backtest fails due transient engine issue, capture:
   - user id
   - strategy id (if any)
   - timestamp (UTC)
   - endpoint response body

### Logout support fallback

If remote session revoke fails, local logout must still clear cookies/session:
1. Trigger logout from Profile.
2. Verify app returns to logged-out landing route.
3. Verify local session state is cleared in browser and protected routes redirect to auth.

## 4) Incident Escalation Notes

Escalate to backend on-call when any of the following are seen:
- Funnel telemetry missing for 2+ critical checkpoints in a single user flow.
- History/detail metric mismatch (same simulation shows different `win_rate` units).
- Repeated logout failures where local state is not cleared.
