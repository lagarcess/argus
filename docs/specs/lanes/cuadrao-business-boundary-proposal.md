# Cuadrao Business pilot: ownership boundary proposal

Status: **proposed, not implemented**, October 7, 2026. This proposal belongs to the
[Business owner pilot](https://github.com/lagarcess/argus/pull/900). The founder
holds the `space-model` decision (#819). No Personal or Household reader
changes until it is approved.

## Recommendation

Build the **smallest additive slice of #819**: a Business space owned by the
person, with `owner_space_id` on the two Business root tables. Do not build a
separate business principal identity (option A).

Two independent reviews, run on different models against the same code, each
reached this recommendation on their own. Their evidence is below.

## Why not option A (business principal)

| Problem | Evidence |
| --- | --- |
| It can't be created as designed. `refuse_placeholder_email` refuses every `@cuadrao.invalid` user that isn't a registered placeholder. Registering one makes Lane 6 refuse to delete it. | `20261004090000_account_deletion.sql:384-404`, `src/argus/domain/account_deletion/service.py:527-531` |
| One missed check exposes another person's data. A principal id and a person id have the same type, so a route that trusts a client-supplied business id can read anyone's Personal ledger. | services take a bare `user_id`, e.g. `recording/postgres_repository.py:93-96` |
| Deleting the person orphans the principal's data. Lane 6 deletes and revokes only `user_id = person`, so the principal's receipts, Storage files and sealed provider tokens would stay unrevoked. | `account_deletion/service.py:731-747` |
| It is not a simple backfill into #819. #819 step 3 makes `user_id` mean `created_by`, a person, so every principal-owned row would have to be re-keyed. | `docs/specs/cuadrao-master-plan.md` §B2.3 |
| Activity would be attributed to the principal instead of the person who acted. | `20260928200000_financial_accounts_first_slice.sql:63-66` (`recorded_by`) |

## The slice

One migration, sorted after the consumer's pending files:

- `spaces(id, kind check (kind = 'business'), name, created_by -> auth.users on delete cascade, created_at, closed_at, unique (id, created_by))`
- `space_memberships(space_id -> spaces on delete cascade, person_id -> auth.users on delete cascade, role check (role = 'owner'), valid_from, valid_until)`. One active owner per space.
- A nullable `owner_space_id` on `financial_accounts` and `financial_source_connections`, with a composite FK `(owner_space_id, user_id) -> spaces(id, created_by)`. A forged space id can therefore never point at another person's space.
- RLS on, explicit grants, entries in `tests/test_client_grants_postgres.py`, and census rows.

**Rule: `owner_space_id is null` means Personal.** Personal readers filter
`is null` and Business readers filter `= :space`. No personal-space backfill is
needed for the pilot. #819 later backfills personal spaces and switches the
filter to equality. The free-text `space_id` column is not used.

## Readers that change

These are seven required SQL sites, counted reader by reader. Everything else
either inherits from them or is scoped through an account or connection.

| # | Reader | Why it changes |
| --- | --- | --- |
| 1 | `recording/postgres_repository.py:89-104` `list_accounts` | Feeds account lists, activity options, purchases, history and import review. |
| 2 | `recording/money_postgres.py:27-33` `load_owner` | Feeds home and search through `planning/storage.py:201`, and money writes. |
| 3 | `recording/canonical_groups.py:203-212` group query | Without it, Personal money reads would fail once a Business expense exists, because groups resolve against accounts that were filtered out. |
| 4 | `ingestion/connections_postgres.py:98-106` `list` | Feeds connections and the documents list. |
| 5 | `ingestion/reconcile/store_postgres.py:102-110` `events()` | Import events store only `user_id`, so this filters through observation and connection. |
| 6 | the same file, `:92-100` `nearby()` | Stops duplicate matching across spaces. |
| 7 | `recording/postgres_repository.py:106,265` get or `_load` by id | Also blocks granting a Business account to a household and stops Personal writers using a Business account id. |

There is also one writer fix. Document upload's `external_ref` must include the
space (`documents/service.py:153-154`). Otherwise the same file uploaded in
Personal and in Business would come back as the other space's document.

These need no change: search, home, purchases and detail (they inherit from
readers 1 and 2), household projections (they only see granted accounts), and
document reads, observations, loop, asset, plans, budgets, goals and debts
(scoped by connection or account, or owned only by the person).

## Business access

- One resolver, `resolve_business_space(person_id) -> space_id`, from an active owner membership. Every Business route uses it. No route accepts a space id from the client.
- Services receive `(session person, space)`. `user_id` stays the person, so the composite FK contains any forged space.
- `business_conversations(conversation_id, space_id)` marks a conversation as Business. The read-only expense tool checks the membership again on every call. Argus `/chat` Recents leaves marked conversations out.
- WhatsApp sender links point at the space. Receipts land under the person's `user_id` with `owner_space_id` set.
- Storage (#778) keeps `{user_id}/{connection_id}/{sha256}`, so the person's folder still covers Business sources.
- The person's own session could read their own Business rows through PostgREST, since `auth.uid() = user_id`. That is the same owner, no client uses that path, and employees later need #819 step 2 member-based RLS under either option.

## Delete account and owned business data

This is a single confirmed flow for a sole-owner pilot.

1. **Explain.** Settings opens "Delete account and business data". It names what will be deleted: the person's Personal and Household-owned records (unchanged Lane 6 behavior), plus the Business space's accounts, expenses, receipts and their original files, the WhatsApp link, and Business conversations. Household data the person shared follows the existing placeholder rule.
2. **Offer export first.** A "Download my business data" action returns a ZIP with:
   - `expenses.csv`: date, merchant, amount, currency, category and account;
   - `accounts.csv`;
   - the original receipt files.

   It is generated on request by the API from the same readers the Business screens use. Nothing is stored, and the link is never public. Export is optional and doesn't block deletion.
3. **Confirm.** The existing destructive confirmation, adding the space's name and a summary of counts, for example "3 accounts, 41 expenses, 38 receipts".
4. **Delete.** Lane 6 runs unchanged. Every Business table cascades from the person through `user_id` and `spaces.created_by`. The #778 `storage` step deletes the person's folder, which includes Business sources. The WhatsApp link rows cascade. The user is never left blocked: a Storage failure keeps the run pending and retried, as Lane 6 already does.

Nothing is kept silently. Closing a business without deleting the account is a later feature, not part of this pilot.

## Verification once approved

- Real-Postgres isolation:
  - two owners, each with Personal and Business data;
  - each of readers 1-7 returns only its space;
  - a forged space id gets 404;
  - a Personal expense keeps working after a Business expense exists (reader 3);
  - the same file uploaded in both spaces creates two documents.
- Deletion: export, then delete. Every Business row, Storage file and WhatsApp link is gone, and another person's data is untouched. Run with the Lane 6 census drift test.
- A flag-off journey stays byte-identical for `/chat` and `/financial-*`.

## Open items

- The founder's `space-model` lock for this slice (#819).
- Hosted Realtime publication membership hasn't been checked. No migration publishes these tables.
