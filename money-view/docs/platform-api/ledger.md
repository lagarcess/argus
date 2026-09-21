# Ledger API (stable contract)

All paths start `/api/platform`. Auth/household comes from common Context. Amounts are signed decimal strings; currencies are never added together. Account balance is opening amount plus posted, nondeleted ledger changes. For liabilities a negative balance means debt; net worth uses that signed balance. Transfers and pending entries are excluded from income/spending. Refunds reduce expense. Records include dated `source` Evidence. Seed is explicitly synthetic, as of 2026-09-20.

## Read contracts

`GET /accounts?currency=USD&include_deleted=false&limit=50&offset=0` -> `{items:[{id,name,institution,kind,currency,balance,opening_balance,owner_id,connection_id,deleted_at,source}],total,limit,offset}`. Kinds: checking,savings,credit_card,loan,investment,cash. Demo account ids `acct-demo-01`..`acct-demo-14` (first is USD checking, second USD savings). `GET /accounts/{id}` returns an account.

`GET /transactions?account_id=acct-demo-01&currency=USD&category=groceries&q=market&date_from=2026-09-01&date_to=2026-09-20&status=posted&sort=date_desc&limit=50&offset=0` -> `{items:[{id,account_id,account_name,date,merchant,description,amount,currency,category,kind,status,notes,splits:[{category,amount}],transfer_id,reversal_of,source}],total,limit,offset,aggregates:[{currency,income,spending,net,transaction_count,source}]}`. All filters optional; default posted+pending, active records only. `sort` date_desc/date_asc/amount_desc/amount_asc, id tie break. Max limit 100. Aggregates cover complete filtered result, not page. Kinds expense,income,refund,transfer,adjustment. Splits replace parent category for spending/category filters and must sum exactly to amount.

`GET /overview?month=2026-09&currency=USD` -> `{as_of,account_count,accounts:[account] (max 6),net_worth:[{currency,assets,liabilities,net_worth,source}],cashflow:[{currency,income,spending,net,transaction_count,source}],trend:[{month,currency,income,spending,net,transaction_count,source}],source}`. Omitting currency returns separate groups.

`GET /spending?month=2026-09&currency=USD` -> `{month,currency,income,spending,net,transaction_count,categories:[{category,amount,transaction_count}],merchants:[{merchant,amount,transaction_count}] (top20),source}`. Currency defaults USD; signed expense/refunds are netted, transfers excluded.

`GET /categories` -> `{items:[{id,kind}]}` with IDs groceries,dining,housing,transport,utilities,health,shopping,entertainment,travel,education,insurance,other,income,transfer.

## Writes

All writes require editor/owner. POST creation/import/reversal use body `idempotency_key` (1..120 chars); same key+same input returns original receipt, changed input returns 409. User input numbers accept decimal strings.

- `POST /accounts` `{name:"Weekend savings",institution:"Manual",kind:"savings",currency:"USD",opening_balance:"250.00",idempotency_key:"account-1"}` -> account.
- `PATCH /accounts/{id}` `{name:"Travel savings"}` (name/institution only) -> account.
- `DELETE /accounts/{id}` -> `{id,deleted:true}`; `POST /accounts/{id}/restore` -> account. Softdelete hides account and its transactions from active financial totals; restore restores them.
- `POST /transactions` `{account_id:"acct-demo-01",date:"2026-09-20",merchant:"Local market",description:"Weekly groceries",amount:"-45.50",category:"groceries",kind:"expense",status:"posted",notes:"",idempotency_key:"manual-1"}` -> transaction. Optional `splits:[{category:"groceries",amount:"-30.00"},{category:"health",amount:"-15.50"}]`. Transfer creation additionally requires `to_account_id` with same currency, creates matching opposite entry atomically; return first transaction with shared `transfer_id`.
- `PATCH /transactions/{id}` `{category:"shopping",notes:"Reviewed",description:"Supplies",splits:[]}` -> transaction. Optional fields only. Splits default unchanged if omitted; clearing splits requires `[]`.
- `DELETE /transactions/{id}` -> `{id,deleted:true}`; deletes paired transfer entries together. `POST /transactions/{id}/restore` -> transaction, restores pair together.
- `POST /transactions/{id}/reverse` `{idempotency_key:"undo-1"}` -> transaction with original ID in `reversal_of`, opposite amount, posted. Only nontransfer posted expense/income/refund/adjustment; duplicate reversal returns existing reversal.

## Connections (explicit simulation)

`GET /connectors` -> `{items:[{id,name,countries,currencies,mode:"simulated"}]}`. IDs demo-bank,demo-credit,demo-investment.
`GET /connections` -> `{items:[{id,connector_id,status,last_good_at,last_attempt_at,error_code,mode:"simulated"}]}`.
`POST /connections` `{connector_id:"demo-bank",idempotency_key:"connect-1"}` -> connection (simulated connected). `POST /connections/{id}/sync` `{outcome:"success"|"failure",idempotency_key:"sync-1"}` -> connection. Failure retains last_good_at and all account/transaction data. Success records a simulation refresh timestamp; no invented external rows.

## CSV

`GET /transactions/sample.csv` returns template with header `date,merchant,description,amount,currency,category,kind`.
`GET /transactions/export.csv` accepts same filters as list, includes all filtered records up to 20,000; exports a formula-safe CSV.
`POST /imports/preview` `{account_id:"acct-demo-01",csv:"date,merchant,description,amount,currency,category,kind\n2026-09-20,Market,Groceries,-45.50,USD,groceries,expense\n"}` -> `{id,account_id,rows:[{line,date,merchant,description,amount,currency,category,kind,duplicate}],errors:[{line,code}],valid_count,duplicate_count,can_commit,source}`. Max1MB/2000 rows. Duplicate fingerprint is account,date,merchant,description,amount,currency; preview cannot commit with validation errors or no new rows.
`POST /imports/{id}/commit` `{idempotency_key:"import-1"}` -> `{id,imported,duplicates,transaction_ids:[...],source}`. All new rows commit atomically, rechecking duplicates under the same write lock. Preview belongs to household; viewers cannot preview/commit.

## Python public query helpers

`account_balances(store: Store, ctx: Context, currency: str | None = None) -> list[dict]`: active account records with balances and source (all accounts, internal bounded fixture scope).
`spending_summary(store: Store, ctx: Context, month: str, currency: str) -> dict`: exactly `/spending` response, used by budgets and assistant.
`overview_summary(store: Store, ctx: Context, month: str = "2026-09", currency: str | None = None) -> dict`: exactly `/overview`.
`record_transaction(store, ctx, payload: TransactionCreate) -> dict`: same transaction write/idempotency behavior for bills; import `TransactionCreate` from ledger_contracts.
`set_account_deleted(store, ctx, account_id, deleted: bool) -> dict`: scoped softdelete/restore hook.
`set_transaction_deleted(store, ctx, transaction_id, deleted: bool) -> dict`: scoped pair-aware softdelete/restore hook.

## Final integration details and verification

- Transactions and CSV export additionally accept `merchant` (exact match) and `spending_only=true` (posted expense/refund lines only). Use both for a merchant drill, with the same month/currency filter as spending. `q` remains broad literal text search. Amount sorting requires `currency` and returns `amount_sort_requires_currency` otherwise.
- Demo currencies are USD, DOP, EUR, NZD. Account 14 is NZD savings. Final fixture has 14 demo accounts, 1 isolated other-household account, and 13,680 demo transactions across October 2024 through September 20, 2026. Fixture manifest is `clara-demo-v1`; deterministic Faker version is pinned by runtime requirements. Categories and fixture prose are identifiers/data, with UI localization owned by views.
- `/overview` includes `investing.net_worth_additions(connection,ctx)` once: separately priced active manual assets. It never includes fictional trading cash/positions. Account counts still count real ledger accounts. Net-worth source inputs include each holding valuation's source and each ledger account's signed balance; account source identifies opening value, synthetic/user provenance, and posted change sum.
- `account_balance(connection: sqlite3.Connection, household_id: str, account_id: str) -> dict` returns one active scoped account, including integer `balance_minor` for atomic planning checks. `post_transaction(connection,ctx,payload:TransactionCreate) -> dict` applies the same validation/idempotency within the caller's write transaction. Both are the sole ledger boundary for bill payments and goal-balance checks.
- `export_data(connection,ctx) -> dict` exports natural household-owned ledger records, including splits. `clear_data(connection,ctx)` clears owned records, retaining the fixture manifest so restart cannot reseed a reset household. `usage_data(connection,ctx) -> {accounts:int,transactions:int}` reports counts. The lifecycle caller owns authorization and the SQLite transaction; clear planning references before clearing accounts.
- Reversed transactions and their reversal rows are immutable; delete/edit returns 409. Reversals preserve the original effective date and category allocation so original-month totals net to zero. A reversal is an accounting correction, not a new bank refund. Paired transfers must be deleted/restored together while both accounts are active.
- CSV duplicate detection includes prior deleted rows. A preview can be replayed or superseded by another preview; commit rechecks all content fingerprints under the SQLite write lock. No mutation happens during preview. Download caps at 20,000 rows; narrow the filter when `export_too_large` is returned.

Verification: `cd money-view && .venv/bin/python -m pytest tests/test_platform_ledger.py -q` covers realistic calendar/volume/determinism, bounded full-filter pagination, exact currency precision, strict household/viewer boundaries, idempotency and rollback, paired transfers, split contributions, reversal immutability, validated atomic CSV import and formula-safe exports, sync failure retention, account trash/restore, reset without reseeding, and investing net-worth integration.
