# Public Alpha Readiness Evidence

This file is the durable evidence index for the public-alpha candidate. Local
checks recorded here do not claim a hosted launch. Exact-SHA Render canary and
founder approval remain required before tester exposure.

## Waitlist rollback floor

Commit `061ba50e` is the fail-closed behavior and minimum safe rollback floor
while the deployed schema can contain `requested` access rows. Prefer a forward fix.

Before any authorized rollback of application code below `061ba50e`, an
operator must run this transaction against the target environment and capture
the returned count:

```sql
begin;

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

The captured `active_requested_rows` readback must be `0` before the operator
may roll back application code below `061ba50e`. If it is not zero, stop; do not
weaken the gate or continue the rollback.

Do not execute this SQL as part of repository verification. It is a
production-state change reserved for an explicitly authorized rollback.
