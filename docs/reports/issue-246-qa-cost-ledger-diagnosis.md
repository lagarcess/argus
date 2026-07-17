# Issue #246 QA Cost-Ledger Diagnosis

Status: **read-only diagnosis complete; QA repair gated**

Verified at: `2026-07-17T01:51:22Z`

Repository base: `bd7cd5e28bb8763a4e349683be68228898e90460`

Environment: Supabase project `lgdhvepyrzbnscqssgqq` (`Argus`, `us-east-2`)

## Read-Only Evidence

- Remote migration history has no `20260702000001` entry.
- `to_regclass('public.cost_ledger_entries')` returns `null`.
- Direct catalog queries return no table, RLS, or table-grant rows for
  `public.cost_ledger_entries`.
- The same service role can select an existing public operational table, which
  rules out a general service-role or public-schema access failure.
- A service-role PostgREST select for `cost_ledger_entries` returns `PGRST205`:
  `Could not find the table 'public.cost_ledger_entries' in the schema cache`.

Direct database and PostgREST evidence agree: the table is physically absent
because the existing repository migration has not been applied to this QA
project. This is not currently a grant-only or stale-cache-only failure.

## Proven Repair Layer

The minimal repair is to apply the existing migration
`supabase/migrations/20260702000001_add_cost_ledger_entries.sql`. Do not create a
second migration and do not reload the PostgREST cache before the table exists.

No QA mutation was performed. Applying the migration requires explicit operator
authority and serialization with the open #230 and #240 database owners.

## Verification After The Gate Opens

After the existing migration is applied:

1. Confirm remote migration history contains `20260702000001`.
2. Confirm the direct table shape matches the checked-in migration and RLS is
   enabled.
3. Confirm `service_role` has only `INSERT` and `SELECT`; `anon` and
   `authenticated` have no table privileges or policies.
4. Insert one privacy-safe probe row with a unique issue correlation id, then
   select that same row through PostgREST.
5. Prove `UPDATE` and `DELETE` are denied for `service_role` without deleting
   the probe row.
6. Reload the PostgREST schema only if direct SQL observes the table while
   PostgREST still returns `PGRST205`, then repeat the same select.

## Fail-Open And Rollback Boundary

Deterministic failure injection covers both API chat receipt persistence and the
workflow-backed backtest path. When the ledger insert raises the recorded
`PGRST205`-style failure, the route receipt remains available, the backtest job
still succeeds, and the structured warning classifies the loss as
`telemetry_only`. No provider-specific failure is exposed to the user.

Rollback is forward repair of migration/grant/cache configuration. Do not use
the migration file's historical drop-table comment operationally and do not
delete append-only cost evidence.

The canonical migration procedure did not change, so no runbook edit is needed.
