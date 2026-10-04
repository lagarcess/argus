# Client grants on early tables depend on the database image default

Recorded 2026-10-04 at integration `a8c37d3a`. Investigation only. No product change is part of this record.

## Finding

Class: missing explicit privilege statement (authorization depends on an environment default).

For 17 early tables in `public`, the migrations state only part of which client role (`anon`, `authenticated`) may do what. The rest comes from the default privileges of the database image the migrations are replayed on. Images disagree:

| Where the database was built | Default for a new `public` table owned by `postgres` |
|---|---|
| Hosted production project | none: client roles get nothing |
| CI (Supabase CLI 2.109.0) | TRUNCATE, REFERENCES, TRIGGER only |
| Supabase CLI 2.117.0 and later | every privilege for `anon` and `authenticated` |

On a database built from these migrations on a newer image, row-level security becomes the only guard on those tables. The owner policies on them allow a signed-in user to write their own rows, including rows only the backend is meant to write.

## Affected objects

Tables: `backtest_jobs`, `backtest_runs`, `collection_strategies`, `collections`, `context_packets`, `conversations`, `decision_notes`, `evidence_artifacts`, `feedback`, `idea_versions`, `ideas`, `messages` (read only), `profiles`, `route_receipts`, `run_context_packets`, `strategies`, `usage_counters`.

Functions: `is_active_household_member(uuid, uuid)` becomes executable by `anon`; two SECURITY DEFINER trigger functions (`validate_profile_auth_identity`, `protect_guest_workspace_policy_fields`) gain client EXECUTE, which is not reachable through the API layer.

Not affected: every table in `argus_private`; invite digests, device tokens, sign-in credentials, account deletion, household and financial tables (their migrations revoke explicitly); `visitor_usage_counters`; `cost_ledger_entries`; the `auth` schema.

## Consequences where the default is open

Confirmed on a local stack with the newer image, with real sign-ups, through the data API and the product API:

- A registered user can change backend-owned columns on their own profile, including the admin flag. In the product that flag is read in one place: it skips the rate limit on creating share links, a feature that is off in production. It gives no access to other users' data and no operator function.
- A registered user can reset or delete their own usage counters. The product API then admits requests it had refused at the limit. This defeats the per-user simulation and feedback allowances. The research and model-compute ceilings are held in a table without client grants and are not affected.
- A registered user can write rows the product treats as its own output in their own space (for example a simulation result), and the product API serves them back. An attempt to turn such a row into a public share link was refused by the API.
- No cross-user read or write succeeded. Guests (anonymous sessions) could not make these writes.

## Environments

| Environment | Affected |
|---|---|
| Hosted production | No. Catalog re-read on 2026-10-04: no default privileges on `public`; `anon` holds no table privilege; `authenticated` holds SELECT on four tables and column grants on `profiles` that exclude the admin flag; row-level security is on for every `public` table. |
| CI | No, while the CLI stays pinned at 2.109.0 (`.github/workflows/ci.yml`). Five real-Postgres tests fail if the pin moves, which keeps CI on an old image. |
| Developer machines on a newer CLI | Yes. Local data only. |
| Supabase preview branches | Unknown. None exists today. Treat as affected until checked. |
| A new hosted project, a rebuild, or a restore into a new project | Unknown. Treat as affected until its default privileges are read. |

## Severity

Medium, latent. Impact where present: metered limits defeated and own-data integrity lost, no cross-user access. Likelihood on production today: none. It becomes High for any real-user database created fresh from the migrations on an image with open defaults before the fix.

It rises if: a new production database is created before the fix; the hosted default privileges change; more code starts trusting the admin flag; share links are turned on.

## Required fix

1. One privilege-only migration, appended after all existing ones:
   - revoke default privileges on tables, sequences and functions in `public` from `anon` and `authenticated` for objects created by `postgres`;
   - `revoke all` on the 17 tables from `anon` and `authenticated`, then grant back exactly: `authenticated` SELECT on `backtest_jobs`; `authenticated` SELECT on `profiles (id, avatar_theme, country, currency_override, preferred_name)` and UPDATE on `profiles (avatar_theme, country, currency_override, preferred_name)`; nothing else;
   - revoke EXECUTE on `is_active_household_member` from `anon`, and on the two trigger functions from `anon` and `authenticated`;
   - leave `service_role` untouched.
2. One real-Postgres test that owns the whole client grant matrix: every relation, column grant, function and default privilege in `public` and `argus_private` compared with a single allow-list, failing on any difference and on any unlisted relation. Existing scattered grant assertions defer to it.
3. CI runs that matrix on the pinned CLI and on the latest CLI, with a scheduled run on latest, so a changed image default shows as a red check.
4. Follow-ups: narrow the owner policies on backend-written tables; decide whether the profile admin flag should exist; restrict `is_active_household_member` to questions about the caller.

## Gates

- Merge the migration and the test before the CI CLI pin moves and before any new hosted database or preview branch is built from these migrations.
- On hosted the migration changes no existing table privilege. It applies after the pending migrations in the same promotion and does not replace the separate backup and approval gate on the pending destructive migration.
- Before and after applying on hosted: read default privileges, table and column grants for `anon`, `authenticated` and `service_role`, client-executable functions, and row-level security flags; they must match the allow-list. Then confirm the two client paths that rely on a grant still work: saving a profile preference and watching a simulation job finish.

## Acceptance

- The grant matrix test passes on both the pinned and the latest CLI image.
- On both images a signed-in user's direct write to the admin flag, to a usage counter, to a conversation and to a simulation result is refused with a permission error.
- Hosted grants read the same before and after, apart from the household function.
