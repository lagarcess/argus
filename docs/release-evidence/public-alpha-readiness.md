# Public Alpha Readiness Evidence

This file is the durable evidence index for the public-alpha candidate. Local
checks recorded here do not claim a hosted launch. Exact-SHA Render canary and
founder approval remain required before tester exposure.

## Waitlist rollback floor

Commit `061ba50e` is the fail-closed behavior and minimum safe rollback floor
while the deployed schema can contain `requested` access rows. Prefer a forward fix.

Before any authorized rollback of application code below `061ba50e`, use this
exact sequence:

1. Enable Render API maintenance mode or otherwise block all public API traffic.
   While the block is active, send a syntactically valid
   `POST /api/v1/auth/access-requests` probe to
   `https://argus-ohr5.onrender.com/api/v1/auth/access-requests` and to the
   equivalent path on every configured custom API domain. Each surface must
   not return HTTP `202`; record every tested surface and status. If no custom
   API domain is configured, record that fact rather than assuming it. If
   maintenance/write blocking cannot be verified, or any required probe fails,
   stop the rollback.
2. Keep all public API traffic and writes blocked. Begin the cleanup
   transaction and acquire an `ACCESS EXCLUSIVE` table lock before reading or
   changing rows. The lock waits for pre-block in-flight inserts to finish, so
   the subsequent cleanup cannot race with a request accepted before the
   traffic block.
3. In that same transaction, disable every active requested row, capture the
   `active_requested_rows` readback, assert it is `0`, and commit. If the
   readback or assertion fails, stop; do not weaken the gate or continue the
   rollback.

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

4. After the cleanup transaction commits, keep maintenance enabled and deploy
   the rollback of application code below `061ba50e`.
5. With traffic still blocked, verify the rollback SHA is live and verify the
   access-request write route is absent or blocked on both the onrender API URL
   and every configured custom API domain. None may return HTTP `202`.
6. Only after both post-deploy checks pass may the operator reopen API traffic.

Do not execute this SQL as part of repository verification. It is a
production-state change reserved for an explicitly authorized rollback.
