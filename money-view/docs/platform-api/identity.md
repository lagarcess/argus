# Local identity and settings API

All paths start with `/api/platform`. JSON uses snake_case. Authentication uses
the `clara_session` HttpOnly, SameSite=Strict cookie (Secure on HTTPS). No implicit
login. Expired/revoked/missing cookies return `401 {"code":"authentication_required"}`.
Cross-origin writes are refused. These are local fixture credentials, never bank
credentials. No email, password recovery email, provider auth, or public sharing.

## Session and household

| Method/path | Body | Result |
| --- | --- | --- |
| GET `/demo/personas` | none | `{items:[{user_id,display_name,households:[{id,name,role}]}],default_password:"Clara-demo-2026!",local_only:true}`; only active fixture users are listed |
| POST `/session/login` | `{user_id:"user-demo",password:"Clara-demo-2026!",household_id?:"household-demo"}` | 200 session snapshot + cookie; wrong credentials 401 |
| GET `/session` | none | session snapshot below |
| POST `/session/logout` | none | `{logged_out:true}`; idempotent, revokes this cookie |
| GET `/settings/sessions` | none | `{items:[{id,created_at,expires_at,last_seen_at,current}]}` active sessions for this user |
| POST `/settings/sessions/revoke` | `{scope:"others"\|"all"}` | `{revoked:number,logged_out:boolean}` |
| DELETE `/settings/sessions/{id}` | none | `{revoked:true,logged_out:boolean}`; only own sessions |
| POST `/settings/password` | `{current_password,new_password}` | `{changed:true,logged_out:true}`; password 10..128 chars, all sessions revoked |
| GET `/households` | none | `{items:[{id,name,role,country,currency_override,effective_currency}]}` |
| POST `/households/switch` | `{household_id}` | session snapshot; membership required |
| PATCH `/household` | `{name?,country?,currency_override?}` | current household object; owner only |
| GET `/household/members` | none | `{items:[{user_id,display_name,preferred_name,avatar_color,role}]}` |
| POST `/household/members` | `{display_name,password,role:"owner"\|"editor"\|"viewer"}` | 201 `{user_id,display_name,role,local_only:true}`; owner creates a local login, no invitation |
| PATCH `/household/members/{user_id}` | `{role}` | member object; owner only, last owner protected |
| DELETE `/household/members/{user_id}` | none | `{removed:true,local_account_deleted:boolean,personal_household_data_deleted:true,shared_household_data_preserved:true}`; owner only, last owner protected; removal deletes personal records for this household and deletes the local identity if no memberships remain |

Session snapshot: `{user:{id,display_name,preferred_name,avatar_color},household:{id,name,country,currency_override,effective_currency,role},preferences:{locale,timezone,appearance,sidebar_compact,notifications:{bills,account_changes,product_updates}},session:{id,created_at,expires_at},supported_currencies:string[],local_only:true}`.

Fixtures: `household-demo` has `user-demo` owner, `user-partner` editor and
`user-viewer` viewer. `user-other` owns `household-other`. All initially use the
documented fixture password; changing it actually changes login. Deleted fixtures
are never automatically restored. Viewer can edit personal settings and memories
but cannot change shared household data or invoke household reset.

## Preferences, memory, data and help

| Method/path | Body | Result |
| --- | --- | --- |
| GET `/settings` | none | `{profile,preferences,household,memory:{enabled,count},capabilities,supported_currencies:string[]}` |
| PATCH `/settings/profile` | `{display_name?,preferred_name?,avatar_color?}` | profile object; preferred_name blank becomes null, max 40 after trim |
| PATCH `/settings/preferences` | `{locale?,timezone?,appearance?,sidebar_compact?,notifications?}` | preferences; locale `en`/`es-419`, appearance `light`/`dark`/`system`; notification object is partial |
| GET `/settings/memories` | none | `{enabled,items:[{id,content,created_at,updated_at}],local_only:true}`; current user + household |
| PATCH `/settings/memories` | `{enabled:boolean}` | same list shape; disabling retains records but excludes assistant use |
| POST `/settings/memories` | `{content,confirmed:true}` | 201 memory; explicit confirmation required, 1..2000 chars |
| PATCH `/settings/memories/{id}` | `{content,confirmed:true}` | updated memory |
| DELETE `/settings/memories/{id}` | none | `{deleted:true}`; current user + household only |
| POST `/settings/memories/reset` | `{confirmation:"DELETE MY MEMORIES"}` | `{deleted:number}` |
| GET `/settings/memories/export` | none | memory list JSON download |
| GET `/settings/data/export` | none | `{schema_version:1,exported_at,local_only:true,household_id,identity:{profile,preferences,household,members,memories,feedback},domains:{...}}` JSON download; only current household; excludes password hashes/session tokens |
| GET `/settings/usage` | none | `{as_of,local_only:true,metrics:{active_sessions,confirmed_memories,local_feedback},domains:{...}}`; counts actual stored records, no fake quota |
| POST `/settings/data/reset` | `{confirmation:"RESET THIS HOUSEHOLD"}` | `{reset:true,household_id,domains:[...],requires_login:false}`; owner, clears registered household-domain data plus household memories/feedback, resets current user's preferences and household settings; preserves member credentials |
| DELETE `/settings/account` | `{confirmation:"DELETE MY LOCAL ACCOUNT",current_password}` | `{deleted:true,logged_out:true,shared_household_data_preserved:true,private_households_cleared:string[]}`; deletes current user's access and personal data; clears domain records in their sole-member households; last owner of a shared household must transfer ownership first |
| POST `/settings/feedback` | `{kind:"bug"\|"feature"\|"general",message}` | 201 `{id,kind,message,created_at,status:"saved_locally",local_only:true}`; never sends |
| GET `/settings/feedback` | none | `{items:[local feedback receipts]}` |
| GET `/settings/help` | none | `{local_only:true,documents:[{id,title_key,body_key}],shortcuts:[...]}`; keys rendered by frontend's Clara catalog |

Avatar palette: `forest`, `ocean`, `clay`, `gold`, `plum`. Supported country /
default currency: DO/DOP, US/USD, NZ/NZD, ES/EUR, GB/GBP, CA/CAD, JP/JPY, KW/KWD.
Currency overrides support the shared `CURRENCY_DIGITS` catalog. A null override
uses the country policy; no currency conversion or relabeling ledger values.

## Explicit composition hooks

`Identity.register_data_domain(name, export=fn, clear=fn, usage=fn)` registers
domain-owned callbacks taking `(sqlite_connection, Context)` and returning JSON
data (export), nothing (clear), or count map (usage). They participate in the same
transaction and must scope every read/write to `context.household_id`; personalized
resources additionally scope to `context.user_id`. Reset never discovers or deletes
arbitrary tables. Every callback must be present before offering a full reset.

Archive/trash are assistant-owned resources. The captain wires the assistant's
real list/archive/delete/restore APIs into the data controls UI. Settings advertises
registered domain names in `capabilities.data_domains`; no fake archive collection.
`Identity.active_memories(context)` exposes only enabled, confirmed current-user,
current-household records to assistant grounding.

Household export supplies the export callback a bounded read adapter in place of
the raw connection. Its `execute(sql, parameters)` preserves the existing query
and returns a cursor supporting iteration, `fetchone`, `fetchmany`, and `fetchall`.
Each source row is checked before yielding to the caller. One budget is shared
across identity reads and every domain callback: at most 50,000 source rows and
32 MiB of serialized source-row bytes. Exceeding either limit returns
`413 {"code":"household_export_too_large"}` without any partial download. Queries
are not rewritten, and a callback cannot bypass the budget with `fetchall`.
Clear and usage callbacks continue receiving the actual transaction connection.

`Identity.active_memories(context)` reads at most 101 source rows and allows at
most 100 confirmed records / 32 KiB of serialized source rows. Overflow raises
`PlatformError("memory_context_too_large",413)` instead of omitting consented
records. Disabled memories and other users' or households' records never enter
this read. Overflow does not delete or disable stored records.

`supported_currencies` is a required top-level string array in session/login/
household-switch and settings responses, derived directly from
`common.CURRENCY_DIGITS`. Clients must use that array for currency choices. New
profiles start with `appearance:"light"`; existing saved light/dark/system choices
are preserved. An explicit preferences reset restores the new light default.

Errors: owner failures 403 `owner_required`; missing membership 403
`household_access_denied`; missing owned record 404; protected last owner 409
`last_owner_required`; invalid confirmations 422 `confirmation_required`; invalid
password 401 `invalid_credentials`; request/schema validation 422. All mutation
requests are JSON; browser writes with a foreign `Origin` are 403.

`GET /settings` capabilities: `{local_passwords:true,confirmed_memories:true,
data_domains:string[],archive_conversations:boolean,public_sharing:false,
outbound_support:false,notification_delivery:"in_app_only"}`. Archive capability
requires the registered `assistant` domain. Profile has `id`, `display_name`,
`preferred_name`, and `avatar_color`. Help documents use `help.guide.title/body`,
`help.privacy.title/body`, `help.terms.title/body`; the Escape action key is
`help.shortcuts.close`. UI owns the complete local-demo document text.

Account deletion is an account-wide action: it removes this user's sessions,
preferences, memberships, confirmed memories and local feedback in every household.
Shared household financial records remain owned by the remaining members. Each
sole-member household's registered domain records are cleared in the same
transaction before tombstoning its name. User/household IDs remain as inactive
referential tombstones; neither passwords nor profile names remain. Reset and
deletion preserve initialization manifests, so restart does not restore fixtures.

Member removal has an explicit destructive personal-data policy. Confirmation must
explain that it clears the removed member's confirmed memories, memory enable
setting, feedback and sessions for this household. If other memberships remain,
their profile, credentials, preferences and other households' personal records and
sessions stay usable. If this was the final membership, the local account is
tombstoned and all its personal identity records and credentials are deleted using
the same cleanup owner as account deletion. Shared financial records never change
when removing a member. `local_account_deleted` reports which outcome occurred.

Session-read performance: authorization reads the stored session, current
membership role, expiry and revocation state on every request. It never caches
authority. Fresh sessions begin with `last_seen_at == created_at`; ordinary reads
do not acquire a write transaction. Activity timestamps are approximate, updated
only after five minutes using a conditional database update. Concurrent overdue
requests cannot overwrite a newer activity timestamp. Activity throttling does
not delay role changes or revocation.

In-flight write lifecycle: authenticated `Context` captures `data_generation`
(an integer, initially zero) alongside the current membership role. Identity owns
`p_household_generations(household_id,generation)`; a missing row means zero.
Household reset and sole-member household deletion advance this generation in the
same transaction as clearing data. Initialization preserves it, and failed clears
roll back both the deletion and generation change.

Every user-scoped persistence owner must call the shared guard inside its existing
`Store.connection(write=True)` transaction, before saving private state:

```python
with store.connection(write=True) as db:
    assert_active_context(db, context, minimum_role="editor")
    # Perform scoped writes using this same connection.
```

`assert_active_context` defaults to `minimum_role="editor"`; personal settings and
notice state can pass `"viewer"`, while owner-only operations pass `"owner"`.
It reloads the active user, current membership role and household generation from
the database. Deleted users or removed memberships fail with `401
authentication_required`; any changed role fails with `409
household_access_changed`; a changed generation fails with `409
household_data_changed`. Only then does it enforce the minimum role (`403
read_only_household` or `403 owner_required`). These errors leave the attempted
write uncommitted. The guard deliberately does not recheck sessions: work accepted
before logout can finish, provided its user, membership, role and data generation
remain valid.

`common.active_context(db, user_id=..., household_id=..., session_id=...)` is the
canonical current-role/generation loader for authentication and background work.
A background operation captures this context before doing work and validates that
same context before final persistence; refreshing it after a wait would bypass
the fence. After reset, a fresh authenticated request captures the new generation
and can save normally. Account deletion in a shared household and member removal
fence the removed user through current identity/membership checks while preserving
other members' financial records.
