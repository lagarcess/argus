# Public Alpha Readiness Evidence

This file is the durable evidence index for the public-alpha candidate. Local
checks recorded here do not claim a hosted launch. Exact-SHA Render canary and
founder approval remain required before tester exposure.

## Live Render capacity and cost

The locked load envelope passed against the real Render API, Render Workflow,
and production Supabase project on candidate
`17098b8173d845aa5033036244a71cdcc3283ddb`. The measured task window ran from
2026-07-31 13:19:39 UTC through 13:33:04 UTC. All temporary identities were
deleted afterward: 15/15 Auth users and 15/15 allowlist rows, with zero cleanup
failures and zero matching identities on the final readback.

| Case | Observed peak | Terminal result | Wall p50 / p95 | Queue p50 / p95 | Run p50 / p95 |
| --- | --- | --- | --- | --- | --- |
| Idle job | 1 running / 0 queued | 1 succeeded | 39.756s / 39.756s | 5.096s / 5.096s | 32.673s / 32.673s |
| Five users | 5 running / 0 queued | 5 succeeded | 50.004s / 63.904s | 5.147s / 5.708s | 38.881s / 50.875s |
| Three jobs, one user | 1 running / 2 queued | 3 succeeded | 68.657s / 101.652s | 36.436s / 66.800s | 32.588s / 37.540s |
| Fifteen users | 5 running / 10 queued | 15 succeeded | 68.914s / 103.037s | 29.006s / 67.518s | 28.249s / 53.177s |
| Invalid envelope | 1 running / 0 queued | 1 failed, `invalid_job_contract`, one retry | 10.018s / 10.018s | 4.292s / 4.292s | 4.803s / 4.803s |
| Transient upstream | 1 running / 0 queued | 1 succeeded after `failed_upstream`, one retry | 43.221s / 43.221s | 4.283s / 4.283s | 38.217s / 38.217s |

The run used 26 task runs and 28 attempts. Render reported 1,466 seconds
(0.407222 hours) of Standard Workflow compute. At Render's current
[$0.20/hour Standard rate](https://render.com/docs/workflows-limits), the
measured compute cost was $0.081444, before Render's Workflow monthly minimum.

The selected web-service tier is Starter: 512 MB RAM and 0.5 CPU at
[$7/month per service](https://render.com/pricing). `argus-api` and `argus-app`
therefore have a $14/month total fixed Render service cost. The checked-in
Blueprint declares both services as `plan: starter`; live control-plane
readback remains a separate deployment gate. Supabase Pro is also selected at
[$25/month](https://supabase.com/pricing), including daily backups retained for
seven days. The combined fixed platform floor is $39/month, plus metered
Workflow compute and any overage.

## Waitlist paid-control precondition

The checked-in Render Blueprint declares both `argus-api` and `argus-app` as
`plan: starter`. A checked-in plan is not proof of the live instance type, and
it is not yet safe by itself for the requested-role migration or waitlist
exposure. Render documents that [maintenance mode is available only on paid web
services](https://render.com/docs/maintenance-mode), [Free web services cannot
receive private-network traffic](https://render.com/docs/private-network), and
[Free web services do not support shell or SSH
access](https://render.com/docs/ssh). Render's [Free instance
limitations](https://render.com/docs/free) confirm the same operational gaps.

Do not apply
`supabase/migrations/20260731080154_add_requested_private_alpha_access.sql` or
accept access-request traffic until the paid-control readbacks below are
complete. Rollback below `061ba50e` remains forbidden until verified
maintenance, worker quiescence, and private route-absence proof are available.

Before applying that migration or exposing the route:

1. Use an out-of-band service readback to read back a paid API instance type
   from Render's control plane for `argus-api`. Record the returned plan and
   require `serviceDetails.plan != free`.
2. With access-request traffic still unexposed, prove maintenance mode is
   available and can be enabled. Enable it, read back
   `serviceDetails.maintenanceMode.enabled=true`, and require the exact HTTP
   `503` plus configured maintenance-page marker or fingerprint on every public
   API domain.
3. Verify actual private-network, SSH, or local-loopback verification
   capability. Either require HTTP `200` from `/health` through the paid
   service's internal hostname, or open an authenticated Render shell/SSH
   session and require HTTP `200` from the service's local `/health` endpoint.
   Record the successful surface; a documented entitlement without a working
   probe is not proof.

The selected API tier satisfies the planned paid-instance transition only if
these capability checks also pass. If any paid capability is absent, stop: do
not apply the migration and do not expose the route. Only after every paid-control
check passes may the requested-role migration be applied and access-request
traffic be exposed.

## Waitlist rollback floor

Commit `061ba50e` is the fail-closed behavior and minimum safe rollback floor
while the deployed schema can contain `requested` access rows. Prefer a forward fix.

Before any authorized rollback of application code below `061ba50e`, use this
exact sequence:

Render documents that [maintenance mode returns HTTP 503 and the configured
maintenance page on every public request](https://render.com/docs/maintenance-mode),
while the service remains reachable over its private network and SSH. Render
also documents that a [restart keeps the same commit and configuration, and a
zero-downtime deploy completes only after the old instance is shut
down](https://render.com/docs/deploys#zero-downtime-deploys). The control-plane
checks below use Render's documented [restart
endpoint](https://api-docs.render.com/reference/restart-service), [instance
inventory](https://api-docs.render.com/reference/list-instances), and [service
and deploy fields](https://api-docs.render.com/openapi/render-public-api-1.json).

If no private verification surface is available through the private network,
SSH, or local loopback, rollback below `061ba50e` is forbidden. Stop and
forward-fix before changing maintenance state or data.

1. Enable Render maintenance mode. Use an out-of-band Render control-plane
   readback—not the application—to record
   `serviceDetails.maintenanceMode.enabled=true`, the configured maintenance
   page URI, and every configured custom API domain.
2. Derive and record the expected configured maintenance page marker or
   SHA-256 fingerprint. Probe
   `https://argus-ohr5.onrender.com/api/v1/auth/access-requests` and the
   equivalent path on every configured custom API domain. Every response must
   have the exact HTTP `503` maintenance-mode status and the configured marker
   or fingerprint. An arbitrary `403`, `429`, or `503` is not maintenance
   proof. If the control-plane state or expected response signature cannot be
   verified, stop and forward-fix.
3. Keep maintenance enabled. Capture the current live commit and all current
   instance IDs, then trigger a same-SHA Render service restart. Wait until the
   restart deploy is terminal with `status=live`, has a non-empty `finishedAt`,
   and its `commit.id` still equals the captured SHA. Re-read the instance
   inventory and require the set of pre-restart instance IDs to be absent.
   Together with the completed restart deploy, this is the required Render
   evidence that old-instance shutdown/drain is complete and no pre-maintenance
   API worker remains, so pre-block in-flight inserts cannot complete after
   cleanup. If any part cannot be verified, stop and forward-fix; do not clean
   rows.
4. Only after verified worker replacement, keep maintenance enabled and run
   the cleanup transaction below. The table lock does not drain a worker paused
   before its insert. Quiescence comes from maintenance plus the completed
   same-SHA restart. The lock only serializes the cleanup with later database
   work.

```sql
begin;

lock table public.private_alpha_allowlist in access exclusive mode;

update public.private_alpha_allowlist
set
  disabled_at = coalesce(disabled_at, now()),
  updated_at = now()
where role = 'requested'
  and disabled_at is null;

select count(*) as active_requested_rows
from public.private_alpha_allowlist
where role = 'requested'
  and disabled_at is null;

do $$
begin
  if exists (
    select 1
    from public.private_alpha_allowlist
    where role = 'requested'
      and disabled_at is null
  ) then
    raise exception 'active requested access rows remain';
  end if;
end
$$;

commit;
```

5. Capture the `active_requested_rows` readback and assertion. Both must be
   zero before commit. If either fails, stop; do not weaken the gate or
   continue the rollback.
6. After commit, keep maintenance enabled and deploy the rollback of
   application code below `061ba50e`. Read Render deploy metadata and require
   that the exact rollback SHA is live in Render deploy metadata with
   `status=live` and a non-empty `finishedAt`.
7. With maintenance still enabled, use the service's private network, SSH, or
   local loopback surface to send a non-mutating invalid-body probe
   (`POST {}` with `Content-Type: application/json`) to
   `/api/v1/auth/access-requests` and require HTTP `404` route absence. A
   present route, including HTTP `422` or any other application response,
   stops the rollback: keep maintenance enabled, clean up the failed rollback
   state, and forward-fix.
8. Before changing public traffic, re-read the maintenance configuration and
   response signature exactly as in steps 1 and 2. Require
   `serviceDetails.maintenanceMode.enabled=true`, exact HTTP `503`, and the
   same configured page marker or fingerprint on the onrender URL and every
   configured custom domain.
9. Disable maintenance last. Then perform a public invalid-body readback on
   the onrender URL and every configured custom domain and require HTTP `404`
   route absence. If any surface returns another status, immediately re-enable
   maintenance, stop, clean up the failed rollback state, and forward-fix.

Do not execute this SQL as part of repository verification. It is a
production-state change reserved for an explicitly authorized rollback.
