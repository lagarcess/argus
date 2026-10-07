# Signup storage proof (local, synthetic addresses)

The marketing route, the real PostgREST (`supabase/postgrest:v16.3`, the image the local Supabase stack uses) and Postgres 17 with the committed migration `20260920000000_cuadrao_early_access_signups.sql`. The roles `anon`, `authenticated` and `service_role` were created as in a Supabase project. Addresses are `@example.com` and synthetic. Captured against code commit `3e6cf00de`; the handler and migration are unchanged since. This is local proof only. It is not hosted proof and it did not touch the hosted Supabase project.

## Visitor journeys through `POST /api/signups`

```
new address            {"status":"registered"} [200]
same, other case/lang  {"status":"registered"} [200]
rows after both        1 row: ana@example.com, language es, consent_version early-access-2026-10
operator removal       UPDATE 1   (email set null, removed_at set)
same visitor again     {"status":"registered"} [200]
rows after             1 row: email null, removed true   <- still one row, not re-registered
```

Anon key against the same PostgREST:

```
GET  /cuadrao_early_access_signups   {"code":"42501", "message":"permission denied for table ..."} [401]
POST /cuadrao_early_access_signups   {"code":"42501", "message":"permission denied for table ..."} [401]
```

## Operator tool (`bun run scripts/signups.ts`)

Three active rows inserted directly (`a`, `b` English, `c`).

```
summary                         {"active":3,"pending":3,"removed":0}
remove B@example.com            Signup removed.
remove stranger@example.com     Signup suppressed.        (never registered; suppression row created)
summary                         {"active":2,"pending":2,"removed":2}
notice --template (dry run)     {"template":"proof","recipients":2,"byLanguage":{"es":2,"en":0},"stamps":true}
                                Dry run. Nothing was sent. Add --send to send.
notice --send (no --expect)     refused: "A full send needs --expect 2 to confirm the recipient count."
rows                            a active, c active, b removed (email null), stranger suppressed (source operator-removal)
```

The removed address `b` is absent from the notice recipients. No message was sent.

## Table constraints

`tests/test_cuadrao_early_access_postgres.py`, run against the same database: 11 passed (repeat ignored, removed address keeps only its digest and blocks re-registration, seven inconsistent rows refused, `anon` and `authenticated` hold no privilege, `service_role` holds select, insert and update but not delete, RLS on with no policy). CI runs it on the full migration chain through the existing `tests/test_*_postgres.py` glob.
