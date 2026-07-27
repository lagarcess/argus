# Issue #246 Cost-Ledger Closure Evidence

Status: **complete — hosted schema repaired and issue closed**

Verified at: `2026-07-27T22:31:24Z`

Repository base/final SHA: `507e86226e1747e0af250876b58719eb5e99c261`

Environment: hosted Supabase project `lgdhvepyrzbnscqssgqq`
(`Argus`, `us-east-2`)

## Root Cause

The repository migration
`supabase/migrations/20260702000001_add_cost_ledger_entries.sql` was correct,
but the hosted project had never applied it. Direct SQL returned no table,
hosted migration history had no `20260702000001` row, and PostgREST returned
`PGRST205`. No commit had removed the ledger.

## Exact Repair

The operator applied only the exact checked-in migration in one transaction
and recorded the matching migration history:

- version: `20260702000001`
- name: `add_cost_ledger_entries`
- recorded statements: the exact migration bundle

No blanket migration push, unrelated migration replay, competing migration,
application deployment, or existing-row mutation occurred.

## Hosted Verification

- Direct SQL and the Supabase table inventory resolve
  `public.cost_ledger_entries`.
- PostgREST observes the table without a schema-cache reload.
- RLS is enabled with no public policies.
- `service_role` has `INSERT` and `SELECT` only.
- `anon` and `authenticated` have no table privileges.
- Service-role `UPDATE` and `DELETE` return `403 / 42501`.
- One privacy-safe `manual_reconciliation` row proves append/read behavior. It
  contains no user, conversation, message, run, job, receipt, prompt,
  transcript, or provider payload identifiers.

## Fail-Open Verification

With provider credentials blanked and synthetic market data forced, the
cost-ledger, chat, and workflow failure-injection selection passed:

```text
8 passed in 2.01s
```

Chat and backtest execution therefore remain available if ledger persistence
fails; the loss stays classified as `telemetry_only` and does not expose
database or provider details to users.

## Repository And Closure State

The repository already contained the correct schema and fail-open behavior, so
no code or runbook change, commit, push, or PR was needed for the hosted repair.
GitHub issue #246 is closed with the full operational evidence. Rollback remains
forward repair of schema, grant, or cache configuration; append-only evidence
must not be deleted.
