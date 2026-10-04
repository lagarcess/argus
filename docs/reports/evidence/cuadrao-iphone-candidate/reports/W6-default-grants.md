# W6: default grants on `public` differ by Supabase image (security finding, investigation only)

Status: investigated, no product change. Severity recommendation: **Medium, latent**. Not exploitable on the hosted project today. High impact on any database built by replaying the migrations on an image with the classic Supabase defaults.

Integration head a8c37d3a182fbdb3228f6003272418e65286bc1a. Raw dumps, scripts and diffs: `~/.claude/orchestrate/cuadrao-iphone-candidate/baseline/default-grants/`.

## Summary of facts

1. The claim is true. On a fresh `supabase db reset`, CLI 2.118.0 (postgres 17.6.1.171) gives new `postgres`-owned tables in `public` full privileges for `anon` and `authenticated`. CLI 2.109.0 (postgres 17.6.1.140, CI's pin) gives them only TRUNCATE, REFERENCES, TRIGGER and MAINTAIN.
2. 17 tables gain client privileges on the newer image. All 17 have RLS enabled and at least one policy. No table in `argus_private`, no digest, token, deletion or household table gains anything; those migrations revoke explicitly.
3. On the newer image RLS still blocks every cross-user read and write I tried. It does not block a signed-in user from writing their own rows directly through PostgREST. A real signed-up user set `profiles.is_admin = true` on their own profile and reset their own `usage_counters` row (`used_count` 0, `limit_count` 1000000), then deleted it.
4. The hosted project has the safe behaviour today, and is stricter than both local images: `pg_default_acl` has no row for `public`, `anon` holds no table privilege, and `authenticated` holds table-level SELECT on four tables only.
5. The `auth.mfa_recovery_codes.code_hash` observation is a test artefact, not an exposure. No client role holds any privilege on that table on either image, and the `auth` schema is not served by PostgREST (HTTP 406 `PGRST106`).

## 1. Method

Stack: local project `argus-qa`, owned by W6 from 21:15 CDT (W4.md line 1 said "owned by W6"). Started from worktree `.claude/worktrees/cuadrao-gate` (same migrations as a8c37d3a; that branch changes only the pytest gate script and its test).

```bash
SB=/private/tmp/claude-501/w4-cli/node_modules/.bin/supabase      # CLI 2.109.0
D=~/.claude/orchestrate/cuadrao-iphone-candidate/baseline/default-grants
$SB db reset                          && $D/dump.sh $D/cli2109-pg17.6.1.140 && python3 $D/probe.py $D/cli2109-pg17.6.1.140/postgrest_probe.tsv
$SB stop --no-backup && supabase start && supabase db reset     # CLI 2.118.0
$D/dump.sh $D/cli2118-pg17.6.1.171    && python3 $D/probe.py $D/cli2118-pg17.6.1.171/postgrest_probe.tsv
python3 $D/probe_rls.py > $D/cli2118-pg17.6.1.171/postgrest_rls_probe.tsv
supabase stop --no-backup && $SB start && $SB db reset           # back to CLI 2.109.0, fresh
```

All resets exit 0, 111 migrations applied, latest 20261004090000, on both images.

`dump.sh` writes, per image: `default_acl.tsv`, `schema_usage.tsv`, `relations.tsv` (every non-system schema: owner, relrowsecurity, relforcerowsecurity, policy count, effective privileges of anon and authenticated), `role_table_grants.tsv`, `column_only_grants.tsv`, `policies.tsv`, `functions.tsv` (EXECUTE for each client role, SECURITY DEFINER flag), `sequences.tsv`, `versions.txt`, `migrations.txt`. `probe.py` signs up one real user through GoTrue and sends select, insert, update and delete to every relation in `public` through PostgREST at `127.0.0.1:54331`, once with the anon key and once with the user's JWT (736 requests per image). `probe_rls.py` signs up two real users, seeds rows for both as `postgres`, and tries cross-user and own-row requests.

## 2. Diff between images

Images: 2.109.0 runs `postgres:17.6.1.140`, `gotrue:v2.192.0`, `postgrest:v14.14`. 2.118.0 runs `postgres:17.6.1.171`, `gotrue:v2.197.0`.

`pg_default_acl`, owner `postgres`, schema `public` (the only rows that differ; `diff-default_acl.txt`):

| objtype | 17.6.1.140 (CI) | 17.6.1.171 |
|---|---|---|
| tables (r) | `anon=Dxtm, authenticated=Dxtm, service_role=Dxtm` | `anon=arwdDxtm, authenticated=arwdDxtm, service_role=arwdDxtm` |
| functions (f) | `postgres=X` only | `anon=X, authenticated=X, service_role=X` |
| sequences (S) | `anon=w, authenticated=w, service_role=w` | `anon=rwU, authenticated=rwU, service_role=rwU` |

The `supabase_admin` rows for `public` grant everything to all three roles on both images and do not matter here, because migrations run as `postgres`.

Other diffs:
- `policies.tsv`: 0 changed lines. RLS flags: unchanged. Every table in `public` and `argus_private` has `relrowsecurity = true` on both images. `relforcerowsecurity` is true only on `argus_memory_vectors` and the nine `memory_*` tables. The one view, `public.refusal_log`, has no client grant on either image.
- `functions.tsv`: three `public` functions gain EXECUTE. `is_active_household_member(uuid,uuid)` (SECURITY DEFINER) becomes executable by `anon`; the migration revokes from `public` and grants to `authenticated`, but the default ACL grants `anon` directly. `protect_guest_workspace_policy_fields()` and `validate_profile_auth_identity()` (both SECURITY DEFINER trigger functions) become executable by both roles; trigger functions cannot be called through `/rpc`.
- `sequences.tsv`: no `public` sequence exists. The only change is the `net` schema, which the newer image no longer has.
- `column_only_grants.tsv`: the nine column grants on `profiles` drop out of the list on the newer image only because the table-level grant now covers them.
- `schema_usage.tsv`: `argus_private` USAGE is false for both client roles on both images. `auth` USAGE is true for both on both.
- `auth` schema: 0 privileges for `anon` or `authenticated` on any `auth` table on either image. GoTrue v2.197 adds `auth.mfa_recovery_codes`, `mfa_recovery_code_sets`, `scim_*`, `webauthn_*` and others, all without client grants.
- Not caused by the newer image, but worth knowing: on the CI image `anon` and `authenticated` already hold TRUNCATE, REFERENCES and TRIGGER on all 17 tables below (`relations.tsv`). PostgREST has no TRUNCATE verb, so this is not reachable through the API. Hosted has none of these.

## 3. Affected tables

`affected_relations.tsv`. All are in `public`, RLS enabled, not forced.

| Table | anon gains | authenticated gains | Policies | Through PostgREST on 17.6.1.171 |
|---|---|---|---|---|
| profiles | S I U D | S I U D | 9 (owner select, owner update, restrictive guest and column rules) | owner can read whole row and update any column, including `is_admin` (proved) |
| usage_counters | S I U D | S I U D | 1 `owner_all` (roles public) | owner can update and delete own counters (proved) |
| conversations | S I U D | S I U D | 2 (`owner_all`, restrictive guest) | owner can insert, update, delete own rows (insert proved, 201) |
| messages | S | S | 2 (`owner_all`, restrictive guest) | owner can read own rows; insert, update, delete stay denied (42501 permission denied) |
| backtest_jobs | S I U D | I U D | 2 (owner select, restrictive guest select) | no insert/update/delete policy, so writes fail RLS; select own rows as before |
| backtest_runs, collection_strategies, collections, context_packets, decision_notes, evidence_artifacts, feedback, idea_versions, ideas, route_receipts, run_context_packets, strategies | S I U D | S I U D | 1 `owner_all` each (roles public, `user_id = auth.uid()`) | owner can read, insert, update, delete own rows; nobody else's |

S I U D = SELECT, INSERT, UPDATE, DELETE.

Generic probe, 17 tables, newer image (`probe_changes.tsv`, 258 changed outcomes, none outside these 17 tables):
- anon key: select 200 with 0 rows on all 17. Update and delete 200 with 0 rows on 16, 401 `42501 permission denied` on `messages`. Insert `42501 new row violates row-level security policy` on 15, permission denied on `messages`, `23503` from the profile trigger on `profiles`.
- user JWT: same shape with 403 in place of 401.
- CI image: every one of these requests returns `42501 permission denied for table ...`, except `authenticated` select on `backtest_jobs` (200, granted by migration).

Row-level probe, newer image, two real users A and B with seeded rows (`cli2118-pg17.6.1.171/postgrest_rls_probe.tsv`):

| Request | HTTP | Result |
|---|---|---|
| anon GET conversations, profiles, usage_counters | 200 | 0 rows each |
| anon PATCH and DELETE A's conversation | 200 | 0 rows affected |
| anon POST `/rpc/is_active_household_member` | 200 | `false` (callable by anon; a membership oracle if both UUIDs are known) |
| B GET conversations | 200 | 1 row, B's own |
| B GET A's profile | 200 | 0 rows |
| B PATCH or DELETE A's conversation, PATCH A's usage counter | 200 | 0 rows affected |
| B POST a conversation with `user_id` = A | 403 | 42501 RLS violation |
| **B PATCH own profile `is_admin = true`** | **200** | **1 row, `is_admin: true`** |
| **B PATCH own usage counter `used_count = 0, limit_count = 1000000`** | **200** | **1 row updated** |
| B POST own conversation | 201 | row created without the API |
| B DELETE own usage counter | 200 | 1 row deleted |
| B DELETE own profile | 200 | 0 rows (no delete policy) |

Database after: B `is_admin = true`, B has no usage counter, A's conversation, title and counter untouched. `profiles.is_admin` is read by the API as an admin bypass (for example `src/argus/api/routers/evidence_receipts.py:118`).

Special attention items:
- RLS disabled or no policy plus a grant: none. Every table without a policy has no client grant on either image.
- Secrets and digests: `argus_private.invite_code_digests`, `account_deletion_*`, `account_placeholders`, `public.apple_sign_in_credentials`, `financial_shortcut_device_tokens`, `financial_source_connections`, `household_invitations`: no change, no client table privilege on either image. `argus_private` is not exposed (`supabase/config.toml` `[api] schemas = ["public", "graphql_public"]`); a request with `Accept-Profile: argus_private` returns 406 `PGRST106`.
- `auth.mfa_recovery_codes.code_hash`: `test_no_client_role_can_ever_read_a_code_digest` selects every column named like `code_hash` in `information_schema.columns` as seen by the test's own connection, in any schema. It fails because GoTrue v2.197 added a column with that name, not because a client can read it. `anon` and `authenticated` hold no privilege on the table, and `Accept-Profile: auth` returns 406. The hosted project already has `auth.mfa_recovery_codes`, so this test would also fail against the hosted schema shape.

## 4. Hosted state: KNOWN (read-only)

Read through the Supabase MCP with three catalog-only SELECTs on project `lgdhvepyrzbnscqssgqq` ("Argus", database 17.6.1.063). Nothing was changed. Details in `baseline/default-grants/hosted-catalog-readonly.md`.

- `pg_default_acl` has no row for schema `public`. New `public` tables get no client privilege unless a migration grants one.
- `anon` holds no table privilege on any `public` relation. `authenticated` holds table-level SELECT on `backtest_jobs`, `chat_turn_lifecycles`, `conversation_read_states`, `guest_workspaces`, and column grants on `profiles` (SELECT on id, avatar_theme, country, currency_override, preferred_name; UPDATE on the last four). Not `is_admin`.
- All 44 `public` tables have RLS enabled. Client-executable `public` functions: `set_updated_at()` and `argus_search_symbol_casefold(text)` only.
- `argus_private` exists with no relation and no client USAGE. Hosted has none of the Cuadrao tables, so the later migrations are not applied there.
- No client role can select any `auth` table.
- Not readable from the catalog: the dashboard's exposed-schema list. Not checked: Supabase preview branches (I called no branch tool).

So hosted is a third behaviour: stricter than the CI image (no TRUNCATE, REFERENCES, TRIGGER for clients) and far stricter than the 17.6.1.171 image.

## 5. Root cause

Split-brain between migration intent and platform default (AGENTS.md Split-Brain Rule). The fact "which client role may do what to this table" is held in two places with nothing forcing agreement: the migrations, which for the 17 early tables state only part of it (for example `20260717000001` revokes insert, update, delete on `messages` and says nothing about select), and the image's `pg_default_acl`, which fills in the rest and differs across hosted, CI and current CLI. Later migrations already state the whole fact (`revoke all ... from anon, authenticated`, with the comment in `20260909183646`: "Backend access must not depend on environment-specific default privileges"), which is why only the early tables move.

The same class shows in two smaller places: functions that revoke from `public` but not from `anon` and `authenticated` by name, and RLS policies written `for all` to role `public` on tables that only the service role is meant to write. Those policies are safe only while the grant is absent.

## 6. Proposed fix (not written)

One migration, plus one test owner:

1. `alter default privileges for role postgres in schema public revoke all on tables from anon, authenticated;` and the same for sequences and functions (functions also from `public`). This makes every later table start closed on every image.
2. For the 17 tables: `revoke all on table ... from anon, authenticated;` then re-grant exactly what is intended (today: `authenticated` SELECT on `backtest_jobs`, and the nine column grants on `profiles`). A table-level revoke also drops column grants, so the re-grant must follow in the same migration. On hosted this is a no-op for privileges.
3. `revoke all on function` from `anon` (and `authenticated` where not intended) for `is_active_household_member`, `protect_guest_workspace_policy_fields`, `validate_profile_auth_identity`.
4. Keep `service_role` grants explicit on the same tables, as `20260909183646` already does for its table; check hosted `service_role` grants before applying.
5. One real-Postgres test that owns the whole client grant matrix: it reads every `public` and `argus_private` relation and function from the catalog and compares anon and authenticated privileges with one allow-list. The existing five tests keep passing on both images after step 2. Narrow `test_no_client_role_can_ever_read_a_code_digest` to columns a client role can actually select (`has_column_privilege`), so a new GoTrue column cannot fail it.
6. Optional: tighten the `owner_all` policies on service-written tables (`usage_counters`, `route_receipts`, `backtest_runs`, ...) to the roles and commands the product needs, so the grant is not the only guard. This is a larger change and can be its own issue.

Smallest safe version is steps 1 to 3 and 5.

## 7. Severity recommendation

**Medium, latent. Not exploitable on hosted now.**

- Exploitable now on hosted: no. Hosted has no client table privilege on any of the 17 tables beyond SELECT on `backtest_jobs`, and no `public` default ACL.
- Exploitable after a platform image upgrade of the existing project: not shown. Default ACLs apply only when an object is created, so the 44 existing tables keep their grants. A change would matter only for tables created afterwards, and recent migrations revoke explicitly. I did not verify whether a Supabase upgrade rewrites `pg_default_acl`.
- Exploitable on any database built fresh from these migrations on an image with the classic defaults: yes, proved locally. That covers local stacks on CLI 2.118 and later, CI once the CLI pin moves, and plausibly a new hosted project, a rebuild, or a Supabase preview branch. There, any signed-in user can make themselves admin and remove their usage limits through the public REST endpoint with the public anon key and their own token. No cross-user read or write was possible.

What would raise it to High: any reachable environment with real users or paid providers that was built on the newer defaults (a preview branch with production keys, a new project for the Cuadrao launch); or the hosted `pg_default_acl` gaining a `public` row for anon or authenticated; or a plan to recreate the hosted project. What would lower it to Low: the migration in section 6 merged before the CLI pin moves and before any new hosted database is created.

Note for the candidate: the Cuadrao migrations are not on hosted yet. When they are applied to the current hosted project, its default ACL gives their tables no client privilege, and they revoke explicitly anyway.

## 8. Ready-to-file issue (not filed)

Title: Client grants on 17 early `public` tables depend on the Supabase image default; a fresh database on newer images lets a user set `is_admin` and reset usage

```markdown
## What is wrong

The migrations for 17 early `public` tables do not fully state which client role may do what. The rest comes from the image's default privileges (`pg_default_acl` for role `postgres` in `public`), and three environments disagree:

| Environment | Default for new `public` tables |
|---|---|
| Hosted project (17.6.1.063) | no default: anon and authenticated get nothing |
| CI, Supabase CLI 2.109.0 (postgres 17.6.1.140) | anon and authenticated get TRUNCATE, REFERENCES, TRIGGER, MAINTAIN |
| Supabase CLI 2.118.0 (postgres 17.6.1.171) | anon and authenticated get everything |

On a database built from our migrations on 17.6.1.171, `anon` and `authenticated` hold SELECT, INSERT, UPDATE, DELETE on: backtest_runs, collection_strategies, collections, context_packets, conversations, decision_notes, evidence_artifacts, feedback, idea_versions, ideas, profiles, route_receipts, run_context_packets, strategies, usage_counters; INSERT, UPDATE, DELETE on backtest_jobs; SELECT on messages. RLS is then the only guard, and the `owner_all` policies allow a user to write their own rows.

Proved with real requests through local PostgREST as a signed-up user:
- `PATCH /rest/v1/profiles?id=eq.<self>` with `{"is_admin": true}` returns 200 and the row is admin.
- `PATCH /rest/v1/usage_counters?user_id=eq.<self>` with `{"used_count": 0, "limit_count": 1000000}` returns 200; DELETE also works.
- `POST /rest/v1/conversations` creates a row without the API.
- `anon` can call `/rpc/is_active_household_member`.

Cross-user reads and writes were blocked by RLS in every case tried. No table in `argus_private` and no digest, token or deletion table is affected.

## Hosted today

Not exploitable. Catalog read on 2026-10-03: no `public` row in `pg_default_acl`; `anon` has no table privilege; `authenticated` has SELECT on backtest_jobs, chat_turn_lifecycles, conversation_read_states, guest_workspaces and column grants on profiles (not `is_admin`).

## Why it matters

Any database created fresh from these migrations on a newer image is open in the way above: local stacks on CLI 2.118+, CI when the pin moves (five real-Postgres tests already fail there), and possibly a new hosted project, a rebuild or a preview branch.

## Root cause

Split-brain: the grant fact is shared between the migrations and the platform default, with nothing forcing agreement. Later migrations already `revoke all ... from anon, authenticated`; the early ones do not.

## Proposed fix

1. One migration: `alter default privileges for role postgres in schema public revoke all on tables, sequences, functions from anon, authenticated`.
2. Same migration: `revoke all` on the 17 tables from anon and authenticated, then re-grant the intended privileges (authenticated SELECT on backtest_jobs; the nine column grants on profiles). Keep service_role grants explicit.
3. Revoke EXECUTE from anon on `is_active_household_member`, and from anon and authenticated on `protect_guest_workspace_policy_fields` and `validate_profile_auth_identity`.
4. One real-Postgres test that compares the whole anon and authenticated privilege matrix for `public` and `argus_private` with a single allow-list.
5. Narrow `test_no_client_role_can_ever_read_a_code_digest` to columns a client role can select; it currently fails on GoTrue v2.197 because `auth.mfa_recovery_codes.code_hash` exists, though no client can read it.
6. Follow-up: narrow `owner_all` policies on service-written tables so the grant is not the only guard.

## Acceptance

- The real-Postgres matrix passes on both CLI 2.109.0 and 2.118.0 images.
- On both images, the requests listed above return `42501 permission denied`.
- Hosted grants are unchanged after the migration (verify with the catalog queries in the evidence folder).

## Evidence

`~/.claude/orchestrate/cuadrao-iphone-candidate/reports/W6-default-grants.md` and `baseline/default-grants/` (dump.sh, probe.py, probe_rls.py, per-image dumps, diffs, hosted catalog facts). Integration head a8c37d3a.
```

## 9. What was not done

- No migration written, no product file changed, no issue filed.
- Preview branches and the dashboard's exposed-schema setting on hosted were not checked.
- Whether a Supabase platform upgrade changes `pg_default_acl` on an existing project was not verified.
- `/rpc` was tried only for `is_active_household_member`. Other functions were classified from the catalog (no other `public` function changes EXECUTE between images).
- The real-Postgres pytest matrix was not rerun (W4 has both results recorded at this head).

## 10. Stack state at handoff

`argus-qa` is running on CLI 2.109.0 images (`postgres:17.6.1.140`, `gotrue:v2.192.0`), freshly reset at about 21:20 CDT: 111 migrations, latest 20261004090000, 0 auth users. It was started from `.claude/worktrees/cuadrao-gate` with `supabase stop --no-backup` between images, so earlier local data volumes are gone. W4.md line 1 set to "SUPABASE: free (last owner W6)".
