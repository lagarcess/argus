# Cuadrao Business space slice: implementation plan

**Status:** approved plan, revision 2, with the founder's decisions in section 8 (October 8, 2026). S1 to S3 are implemented and unmerged in the isolation PR, which depends on the Business API PR [#913](https://github.com/lagarcess/argus/pull/913). S4 and S5 are not started.
**Serves:** #819 (smallest additive slice), the [boundary proposal](cuadrao-business-boundary-proposal.md) and the Business owner pilot (#900).
**Code base read:** `claude/business-pilot-flow` at `92599473a` (Business API #904, Storage #778, preparation jobs #823, WhatsApp, web #901). Line numbers are against that commit.
**Approved by the founder (October 8):** separate Personal and Business spaces for the pilot, compatible with #819, so a connected Personal plus Business experience can come later without copying financial records. WhatsApp: the owner sends or forwards receipts from their own number to Cuadrao's one receiving number. A verified link ties that sending number to their Business space. Only owner-initiated submissions are processed, and their conversations are never read. One confirmed account-and-business deletion with an optional export.

## Design

A `spaces` row of kind `business` belongs to one person (`created_by`). Rows that belong to it carry `owner_space_id`, pinned to their own `user_id` by a composite FK, so a forged space id can never point at another person's space. `owner_space_id is null` means Personal, with no Personal backfill. `user_id` stays the person, so Lane 6 deletion and Storage paths keep their key.

**Split-brain check.** Who else holds "which space owns this row"?
- Only root rows store it: accounts, connections, import events and conversations.
- Children inherit through their root.
- Import events store a copy of their connection's space. A trigger forces the two to agree (M5).
- The predicate text lives in one function, `owner_scope.sql_predicate`.
- The resolver is the only code that turns a person into a space.
- `scope` is a required keyword with no default, so the type checker finds every caller.

**#819 compatibility.** Records point at `spaces(id)`, never at a membership or a person-as-business. #819 can later add a Personal space per person (switching the null rule to equality inside `sql_predicate`), add `space_memberships` by backfilling one owner row from `created_by`, and link Personal and Business views. None of that copies or re-keys a financial record.

## Where receipt capture sits in the Business roadmap

The [connected-flow spec](../cuadrao-business-connected-flow-spec.md) (#912) owns the Business roadmap and its stages. This plan delivers part of stage B1 and nothing beyond it.

| Stage | What it covers | Status |
| --- | --- | --- |
| B1, capture with verified space isolation | Web and WhatsApp intake, review, one expense, reload, search and source retrieval, in an isolated Business space | In progress, default-off: [#913](https://github.com/lagarcess/argus/pull/913) and the isolation PR |
| E0, offline fiscal engine | Synthetic customer and invoice input becomes a deterministic unsigned XML artifact with local validation evidence, per the [E0 plan](../cuadrao-business-e0-implementation-plan.md) | Approved. Starts after this B1 slice is finished (founder, October 8) |
| B2, connected period pilot | One period of invoices, collections and expenses, plus the accountant package | Not started |
| L, authorized live fiscal processing | Signing, submission and customer delivery, each authorized separately. No supplier is chosen | Not started |

Two constraints carry forward from this slice:
- The space model keeps every later record (invoice, payment, fiscal document, accountant grant) attachable to the same Business space without copying.
- The pilot export already includes every original receipt with its status, so it can feed the accountant package later.

## 1. Migration

One file: `supabase/migrations/20261008140000_business_spaces.sql`, sorted after `20261008130000_whatsapp_intake.sql`.

| Step | SQL outline | Why |
| --- | --- | --- |
| M1 | `create table public.spaces (id uuid primary key default gen_random_uuid(), kind text not null check (kind = 'business'), name text not null check (char_length(name) between 1 and 80), created_by uuid not null references auth.users(id) on delete cascade, created_at timestamptz not null default now(), closed_at timestamptz, unique (id, created_by));` | `unique (id, created_by)` is the target of every composite FK |
| M2 | `create unique index spaces_one_open_business_idx on public.spaces (created_by) where kind = 'business' and closed_at is null;` | One Business space per owner. Create is `insert ... on conflict do nothing` then select, so a double tap converges |
| M3 | On `financial_accounts`, `financial_source_connections`, `conversations`: `add column owner_space_id uuid`, `foreign key (owner_space_id, user_id) references public.spaces(id, created_by) on delete cascade`, index `(owner_space_id) where owner_space_id is not null` | Null rows are unchecked under MATCH SIMPLE. CASCADE, not RESTRICT: the space and the rows both cascade from the person in one `delete from auth.users`. `conversations.user_id` references `profiles` (`20260424000001_alpha_core.sql:28-40`), whose id is the auth user id |
| M4 | `financial_import_events`: the same column and composite FK, against its existing `unique (id, user_id)` (`20261002120300_financial_import_reconciliation.sql:10-36`) | Section 2 explains why the event stores it |
| M5 | Trigger `import_observation_same_space` on `financial_import_observations` before insert or update: raise unless the connection's `owner_space_id is not distinct from` the event's | Forces the event copy to agree with its connection. It also stops duplicate matching from merging a Business receipt into a Personal event, even if a matcher regresses |
| M6 | `whatsapp_sender_links`: `add column destination_space_id uuid not null`, `foreign key (destination_space_id, destination_owner_id) references public.spaces(id, created_by) on delete cascade`. Correct the header comment at `20261008130000:4-6`, which says "business principal" | This is the founder's link from number to space. Link codes and inbound messages keep only `destination_owner_id`. With one space per owner, the space is resolved from the owner at redemption and capture. The `not null` needs zero rows. Hosted has never applied this table, and local databases reset |
| M7 | Trigger `whatsapp_capture_same_space` on `whatsapp_inbound_messages` before insert or update, when `connection_id is not null`: raise unless that connection has `user_id = destination_owner_id` and `owner_space_id` equal to the owner's active sender link space. If the link is revoked between receipt and settle, intake does not reach the trigger: before writing `connection_id` it re-reads the active link in the settle transaction, and with none it settles the row as `rejected` with `error_code = 'sender_link_revoked'` and creates no connection | Database check that a WhatsApp receipt lands in its owner's Business space. The trigger only fires on a code defect, never on a normal revoke |
| M8 | Trigger `refuse_business_account_grant` on `household_account_grants` (`20261001090000_household_membership.sql:71`) before insert or update: raise when the account has `owner_space_id is not null` | Today `_load` lets a Business account be granted to a household |
| M9 | `create or replace function argus_private.deletion_place_unit` (`20261004090000_account_deletion.sql:955`) with the body unchanged except one statement before the account copy at `:1070-1076`: raise `business_account_in_copy` if any `deletion_unit_ids` account has `owner_space_id is not null`. The real-PG deletion tests must pass with unchanged outcomes | The copy names its columns, so a copied Business account would silently become a Personal account of the placeholder. M8 stops it at the source, and this guard stops it here |
| M10 | Replace `public.create_financial_account` (`20260928200000_financial_accounts_first_slice.sql:91-170`): drop the old signature and create it with `p_owner_space_id uuid default null`. Store it, and include it (null included) in the idempotency fingerprint. Re-grant `execute` to `service_role` only | The default keeps pre-S2 code working after S1 applies: its calls resolve to the new function as Personal, instead of failing with "function does not exist". The required keyword lives in Python (S2), where the caller knows the intent. The fingerprint lives only in SQL, so a Personal key replayed from Business is a conflict. Dropping the old signature leaves no overload |
| M11 | RLS on for `spaces`, no client policies. `revoke all on public.spaces from public, anon, authenticated; grant all on public.spaces to service_role;` (pattern of `20261008130000:80-85`). Do not add `owner_space_id` to the connections column grant (`20261002120000_financial_source_connections.sql:67-70`). Accounts expose it through the table-level grant (`20260928200000:322`): same owner, no client path | #811 explicit grants |
| M12 | `comment on` each new table, column and trigger, stating the null rule and the #819 successor | Schema readers see the rule where it lives |

**Deferred: `space_memberships`.** With one owner it would repeat `created_by` and add a second owner fact. #819 adds it by backfilling one owner row per space. That is additive and copies no record, because records reference `spaces`.

**Tests that change in the same PR.**

| File | Change |
| --- | --- |
| `tests/account_deletion_census.py`, `docs/specs/lanes/account-deletion-fk-census.md` | Rows for `spaces.created_by`, the four `(owner_space_id, user_id)` keys and the sender link key, all CASCADE. The drift test (`tests/test_account_deletion_fk_census_postgres.py:683`) fails until they exist |
| `tests/test_client_grants_postgres.py:58-210` | `spaces` in the service-role-only list. Connections column grant still excludes `owner_space_id` |
| `tests/test_whatsapp_intake_postgres.py` | M6 FK and M7 trigger reject a cross-person or Personal connection |

**Not in this migration:** no Personal backfill, no use of the free-text `financial_accounts.space_id`, no Realtime publication (none exists), and no Storage path change. `{user_id}/{connection_id}/{sha256}` already falls under the Lane 6 folder erase.

## 2. Readers and writers

**Shape.** One new module, `src/argus/domain/owner_scope.py`:

```python
@dataclass(frozen=True)
class Personal: ...
@dataclass(frozen=True)
class BusinessSpace:
    space_id: str
OwnerScope = Personal | BusinessSpace
PERSONAL = Personal()
def sql_predicate(scope: OwnerScope, column: str) -> tuple[str, tuple]: ...
```

`BusinessScope` (`business/scope.py:13-16`) becomes `(person_id, owner: BusinessSpace)`. Today's `space_id: str | None` admits "Business with no space". Every root reader and writer and `ImportStore.transaction` take `scope: OwnerScope` as a **required** keyword. Personal callers pass `PERSONAL` explicitly. Plaid, Gmail and household callers are Personal by construction.

**Import events: stored column, not `exists()`.** Users review events, and Business `receipts()` reads them. An accepted event can outlive its observations, because observations cascade from their connection (`20261002120300:47-60`). Under `exists()` that event would vanish from both spaces. With the column, the space is set once when the event is created, from the transaction's scope. M5 keeps it equal to every observation's connection.

| # | Site | R/W | Change | Why |
| --- | --- | --- | --- | --- |
| R1 | `recording/postgres_repository.py:89` `list_accounts` | R | `scope` predicate | Account lists, activity options, purchases, history, import review, Business accounts |
| R2 | `recording/postgres_repository.py:265` `_load` | R/W | `scope` predicate | Every account writer loads through it. A Personal writer cannot touch a Business id |
| R3 | `recording/money_postgres.py:27` `load_owner` | R | `scope` | Feeds `planning/storage.py:201`: home, search and overview totals |
| R4 | `recording/canonical_groups.py:203-210` | R | keep groups whose memberships resolve to in-scope accounts | Otherwise Personal reads fail once a Business expense exists |
| R5 | `ingestion/connections_postgres.py:88` `get` | R | `scope` | Business `receipt_id` is a connection id (`business/service.py:138`) |
| R6 | `ingestion/connections_postgres.py:98` `list` | R | `scope` | Documents list and Business `receipts()` (`business/service.py:126`) |
| R7 | `ingestion/reconcile/store_postgres.py:78,92,102` `event`, `nearby`, `events` | R | transaction scope predicate on the event column | Events and duplicate matching stay in one space |
| R8 | `ingestion/reconcile/store_postgres.py:243` `transaction(user_id)` | R/W | `transaction(user_id, *, scope)` | All callers: `reconcile/service.py:95,103,121,159,223,240,258`, `intake.py:62,76`, `recording.py:100,197,243,269,342,363`, `business/service.py:260` |
| R9 | `reconcile/service.py:114-119`, `reconcile/recording.py:388-397` | R | `list_accounts(scope=...)` | Business review and confirm accept any of the person's accounts today |
| R10 | `business/service.py:98,123,126,138,142,155,171,183,187,204,219,243,260,283,312` | R/W | pass `scope.owner` | Each Business call drops the space today |
| R11 | `business/receipts.py` `receipt_ids` (`business/service.py:261`) | R | inherits the scoped activities and transaction | Covered by the isolation test |
| W1 | Repository create calling SQL `create_financial_account` (M10) | W | required `scope` keyword in Python, passed as `p_owner_space_id` | Business accounts are created in the space |
| W2 | `ingestion/connections_postgres.py:44` `create` | W | required `scope` | Every upload creates a connection |
| W3 | `ingestion/documents/service.py:215-218` `external_ref` and `connections.create` | W | Personal keeps `sha256(f"{user_id}:{digest}")` exactly. Business uses `sha256(f"{user_id}:{space_id}:{digest}")` | Global unique `(source, external_ref)` (`20261002120000:49-51`) would return the other space's document. Personal refs stay byte-identical |
| W4 | `api/whatsapp.py:100` `documents.upload(user_id=owner_id, ...)` | W | pass the scope resolved from the owner's active sender link | WhatsApp captures land in Business. M7 is the database check |
| W5 | `business/service.py:283` money write | W | inherits R2 | A Personal account id posted to Business is 404 |
| W6 | `financial_import_account_links` writer (`20261002120300:72-82`) | W | the linked account loads through R2 with the transaction scope | Its FK is `(account_id, user_id)` only |
| D1 | `recording/repository.py:185,194`, `ingestion/connections.py:260`, `planning/storage.py:187` in-memory doubles | R/W | same filter | Tests must not pass where Postgres fails |

**No change, by inheritance:** financial search and overview (both read `planning/storage.read`, which is R3 and R4), `get_any_account` (household-only, M8), document reads, observations, plans, budgets, goals and debts. **WhatsApp readers stay owner-keyed on purpose:** codes, links and inbound rows are found by sender hash and owner. The space only matters at capture (W4, M7).

**Business access.**

| Path | File | Change |
| --- | --- | --- |
| Resolver | `business/scope.py:19` | `resolve_business_scope(person)` returns the open space or `None`. Business routes return 404 `business_space_missing`, except `POST /business/space` |
| Start | `api/routers/business.py` (new `POST /space`) | Idempotent create with `name` |
| Routes | `api/routers/business.py:121-348` | Unchanged. They already call the resolver |
| Jobs | `workflows/document_job.py`, preparation sweep | No change. Jobs are keyed by `connection_id`, so the draft inherits the connection's space |
| WhatsApp | `api/whatsapp.py:234-247` `require_whatsapp_surface` | Add `business_pilot_enabled()`. Link redemption stores `destination_space_id` from the resolver. No space means no link |

## 3. Separate chat histories and finance-only Business chat

**Mechanism: the conversation column (M3).** `supabase_gateway.py:530` `create_conversation` and `api/chat/computed_answers.py:301` `_new_conversation` take a required `owner_space_id`. A continuation copies the space of its source conversation. A public excerpt fork (`postgres_public_excerpt_forks.py:148`) is Personal. The client names a surface (`POST /conversations {surface}`, `GET /conversations?surface=business`), never a space, and the server resolves it.

| Reader | File:line | Change |
| --- | --- | --- |
| Recents | `postgres_keyset_reader.py:60-79`, `supabase_gateway.py:547` | `scope` predicate (in the SQL cache key) |
| Chat and message search | `postgres_search_reader.py`: every `public.conversations` join (`171, 194, 1620, 1698, 1738, 1768, 1805, 1835, 1868, 2026, 2067, 2165, 2471, 2489, 2512, 2527, 2547, 2561, 2649`) | `scope` predicate through one fragment. A test lists every `public.conversations` occurrence in the file and fails if one lacks the fragment. Message search (`1733-1738`, `2507-2512`) reads Business chat text, and the finance-only tool set does not stop that |
| History, previews | `postgres_history_reader.py:276-290`, `conversation_previews.py:18` | inherit from the listed conversation |
| Delete all | `routers/conversations.py:394` to `supabase_gateway.py:678` `soft_delete_all_conversations` | `scope` predicate. Deleting all in `/chat` leaves Business chats alone, and the reverse |

**Business chat runs a finance-only tool set.** It creates no decisions, ideas, evidence or backtest runs. That keeps the artifact readers free of Business rows with no change to them. Those are the decision reader (`supabase_decisions.py:35-114`) and the run, idea, evidence and decision joins in `postgres_search_reader.py:1765-2657`.

| Layer | Where | Rule |
| --- | --- | --- |
| Catalog | `capability_registry.py:72-93` `get_tool_catalog`, the only assembly point | Gains a required `surface`. Business returns only Business-declared tools. In the pilot that is an empty catalog until the read-only expense tool exists (Q4). The turn derives the surface from the stored conversation, never from the request, and passes it to `src/argus/agent_runtime/graph/workflow.py:179` `tool_catalog` |
| Artifact routes | `routers/decisions.py:29` and the evidence, receipt-fork and sharing routes | One dependency, `require_personal_conversation`, returns 404 for a Business conversation |
| Memory | `api/chat/memory_recall.py:32` `memory_recalls_for_turn`; writes at `routers/personalization_memory.py:148,186` | Business turns skip recall. Saved-decision memory needs a decision, which Business cannot create. `propose_memory` refuses provenance that names a Business conversation |
| Model-facing text | Business catalog schema | A different tool list is a model-facing change. AGENTS.md Never-Violate 12 requires a committed scorecard for the Business surface. Personal is unchanged |

## 4. Deletion and export

**Lane 6, unchanged in code.** `delete from auth.users` cascades the space, Business accounts, connections, import events, conversations and sender links. Through them it removes activities, documents, jobs and observations. The Storage step erases `{user_id}/`. M8 and M9 keep Business accounts out of the household copy. `POST /api/v1/account/delete {confirm: true}` stays the only delete command. A Business space never blocks it, and export never gates it.

| Step | Behavior |
| --- | --- |
| Explain | `ProfileDeleteRequestDialog.tsx` shows the Business block when `GET /business/space` reports a space |
| Export | Optional button to `GET /api/v1/business/export` |
| Confirm | Existing destructive confirm, plus the space name and counts |
| Delete | Unchanged Lane 6 run. A Storage failure stays pending and retried |

**Export contract.**
- `GET /api/v1/business/export`, behind the Business flag, session owner only, scope from the resolver.
- Returns `application/zip` with `Content-Disposition: attachment; filename="cuadrao-negocio-YYYY-MM-DD.zip"` and `Cache-Control: no-store`.
- The build takes `pg_try_advisory_lock(hashtextextended('business_export:' || space_id, 0))` on a dedicated pooled connection, separate from the read connections. That connection holds the session lock for the whole build, and `pg_advisory_unlock` runs in `finally` before the connection returns to the pool. This works across API instances. A second request gets 409 `export_in_progress`.
- The ZIP is written to a spooled temp file, which is streamed after the lock is released. Nothing is stored, and no link is public.

| Entry | Source | Columns |
| --- | --- | --- |
| `expenses.csv` | `BusinessService.expenses(scope, date.min, date.max)` | `date, merchant, amount, currency, category, account, receipt_file` |
| `accounts.csv` | Business account list, archived included | `account, type, currency, archived` |
| `recibos/<date>_<receipt_id>.<ext>` | `BusinessService.source` (proxied bytes) | original file |

UTF-8 with BOM, quoted fields, plain decimal amounts. A missing source leaves `receipt_file` empty and does not fail the export.

**Copy** (`settings.profile.request_deletion.business.*`, es-419 first, needs founder approval).

| Key | es-419 | en |
| --- | --- | --- |
| `title` | Eliminar cuenta y datos del negocio | Delete account and business data |
| `body` | También se eliminarán {{name}}: sus cuentas, gastos, recibos con sus archivos originales, el WhatsApp vinculado y los chats del negocio. | This also deletes {{name}}: its accounts, expenses, receipts with their original files, the linked WhatsApp and the business chats. |
| `counts` | {{accounts}} cuentas, {{expenses}} gastos, {{receipts}} recibos | {{accounts}} accounts, {{expenses}} expenses, {{receipts}} receipts |
| `export` | Descargar mis datos del negocio | Download my business data |
| `export_hint` | Es opcional. Recibirás un archivo ZIP con tus gastos, cuentas y recibos. | Optional. You get a ZIP file with your expenses, accounts and receipts. |

## 5. Tests

`tests/test_business_space_isolation_postgres.py` seeds owners A and B, each with Personal and Business accounts, connections, expenses, receipts and conversations.

| Case | Asserts (literal ids and counts) |
| --- | --- |
| Reader matrix | R1 to R9 for A-Personal, A-Business, B-Personal, B-Business return exactly their seeded ids |
| Forged space | A's `user_id` with B's space fails each composite FK. A's Business routes with B's ids return 404 |
| Personal after Business | After a Business expense, A's Personal home, search, overview and a new Personal expense still work (R4) |
| Same file twice | Personal and Business uploads give two connections and two documents. The Personal ref equals the old formula |
| Import matching | A same-amount, same-date Business receipt and Personal event do not merge. A forced cross-space observation raises (M5) |
| WhatsApp | Redemption stores the space. A capture creates a Business connection. A Personal connection on a captured row raises (M7) |
| Job sweep | A job for a Business connection yields a draft only Business `receipts()` lists |
| Household | Granting a Business account raises (M8). A deletion unit holding a Business account raises (M9) |
| Conversations | Business chats and their message text appear only in Business Recents and search. Delete-all is per surface. A continuation keeps its space |
| Finance-only chat | A Business turn's tool schema list equals the literal Business list. A fake model proposing a backtest leaves zero decisions, ideas, evidence and runs. `POST .../decision` on a Business conversation is 404 |
| Memory | A Business turn recalls nothing and proposes nothing |
| Export then delete | ZIP entries and row counts are literal. A concurrent export gets 409. Then Lane 6 deletes A: zero Business rows and Storage objects remain, and B is untouched |
| Idempotency | A Personal account key replayed from Business is a conflict |
| Census | Drift test passes |
| Flag off | Recorded `/chat` and `/financial-*` responses for a fixed fixture are byte-identical before and after |

## 6. Sequencing

Existing order: #904 API, then #905 Storage (closed for preview billing), then `claude/business-pilot-jobs` (#823), then `claude/business-pilot-whatsapp`. #901 web and #900 docs sit beside them. This slice starts after WhatsApp lands, because M6 and M7 touch its tables.

| PR | Content | Default-off proof |
| --- | --- | --- |
| S1 | Migration M1 to M12, census, grants, trigger tests | Pre-S2 code keeps running: `create_financial_account` defaults the space to null, and no writer sets a space. No row changes |
| S2 | `owner_scope.py`, required `scope` on R1 to R9, W1 to W6, D1, all Personal callers pass `PERSONAL` | Type check clean. Flag-off byte identity |
| S3 | Resolver, `POST /business/space`, R10 and R11, WhatsApp wiring, isolation matrix | Behind `ARGUS_BUSINESS_PILOT_ENABLED` |
| S4 | Conversation surface, finance-only catalog, artifact-route guard, memory gate, scorecard | Default surface Personal. `/chat` byte identity |
| S5 | Export, deletion dialog block, locale keys, OpenAPI and `docs/API_CONTRACT.md` | Flag off hides both |

S3 imports the scoped signatures from S2, so S2 cannot be reverted while S3 stands. The revert would fail the type check.

## 7. Rollout and rollback

**Hosted apply order** (each step is its own founder approval):
1. Read-only ledger and catalog read of the target.
2. Apply `20261008100000`, `20261008110000`, `20261008130000` and `20261008140000` in order through the #894 migration-list tool on a named non-hosted database.
3. Staging proof.
4. Production.

Code deploys after the schema. The flag stays off until a separate enable decision.

**Revert gate.** `scripts/ops/business_space_rows.sql` counts `owner_space_id is not null` on accounts, connections, import events and conversations, and counts `spaces`. Any revert of S1 or S2 records a zero result from the target environment first. With a nonzero count, the only path is a forward fix: reverting the readers would show Business rows in Personal.

| Revert | Meaning |
| --- | --- |
| S5, S4, S3 | Safe. Flag off hides Business. Rows keep their space |
| S2 | Only with a zero gate result, and only after S3 is reverted |
| S1 | Down migration only with a zero gate result |

| Risk | Mitigation |
| --- | --- |
| Opening a migration PR creates a billed Supabase preview branch (#905 closure) | Confirm previews are off before opening S1 |
| A future reader forgets the scope | Required keyword, so a new caller fails the type check. Triggers M5, M7, M8 and M9 back up the database |
| A future tool writes chat artifacts in Business | The catalog is per surface, and the artifact routes are guarded. A new Business tool needs its own declaration and scorecard |
| `create_financial_account` signature change | The new parameter defaults to null, so old callers resolve to it. S2 makes scope required in Python |

## 8. Founder decisions (October 8)

| # | Question | Decision |
| --- | --- | --- |
| Q1 | The Business space name | Defaults to "Mi negocio" or "My business", and the owner can rename it |
| Q2 | Do the deletion counts include archived accounts and receipts not yet confirmed? | Yes, both |
| Q3 | What does the export include? | Every retained receipt with its status. An export failure never blocks deletion |
| Q4 | Business chat before the read-only expense tool exists | Ordinary Business chat keeps working under strict isolation. It tells general answers apart from answers based on saved expenses, and ships with the read-only expense tool |
| Q5 | The import event space copy and `space_memberships` | Import records carry their space. Memberships are deferred, and the server enforces the sole owner |
