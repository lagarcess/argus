"""One household ledger for balances, cash flow, imports and planning inputs."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
from dataclasses import asdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from ..store import Store
from .common import (
    Context,
    Evidence,
    PlatformError,
    assert_active_context,
    decimal_amount,
    get_context,
    get_store,
    identifier,
    minor_units,
    now,
    require_editor,
)
from .ledger_contracts import (
    CATEGORIES,
    AccountCreate,
    AccountPatch,
    Connect,
    Idempotent,
    ImportCommit,
    ImportPreview,
    Split,
    Sync,
    TransactionCreate,
    TransactionPatch,
)
from .seed import ANCHOR, seed
from .statement_identity import IDENTITY_VERSION, Identity, Resolution, resolve_sequence
from .statement_parser import (
    DEFAULT_LIMITS,
    PARSER_VERSION,
    parse_delimited,
    statement_amount,
    statement_date,
)

router = APIRouter(prefix='/api/platform')
DB = Annotated[Store, Depends(get_store)]
CTX = Annotated[Context, Depends(get_context)]
SCHEMA = '''
CREATE TABLE IF NOT EXISTS p_ledger_manifest(id TEXT PRIMARY KEY,recorded_at TEXT NOT NULL,transaction_count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS p_connections(
 id TEXT PRIMARY KEY,household_id TEXT NOT NULL,connector_id TEXT NOT NULL,status TEXT NOT NULL,
 last_good_at TEXT,last_attempt_at TEXT,error_code TEXT,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS p_accounts(
 id TEXT PRIMARY KEY,household_id TEXT NOT NULL,owner_id TEXT NOT NULL,name TEXT NOT NULL,
 institution TEXT NOT NULL,kind TEXT NOT NULL,currency TEXT NOT NULL,opening_minor INTEGER NOT NULL,
 connection_id TEXT REFERENCES p_connections(id),deleted_at TEXT,source_kind TEXT NOT NULL,
 recorded_at TEXT NOT NULL,as_of TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS p_accounts_household ON p_accounts(household_id,deleted_at,currency);
CREATE TABLE IF NOT EXISTS p_transactions(
 id TEXT PRIMARY KEY,household_id TEXT NOT NULL,account_id TEXT NOT NULL REFERENCES p_accounts(id),
 date TEXT NOT NULL,merchant TEXT NOT NULL,description TEXT NOT NULL,amount_minor INTEGER NOT NULL,
 currency TEXT NOT NULL,category TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,
 notes TEXT NOT NULL DEFAULT '',transfer_id TEXT,reversal_of TEXT UNIQUE REFERENCES p_transactions(id),
 deleted_at TEXT,source_kind TEXT NOT NULL,recorded_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS p_transactions_household_date ON p_transactions(household_id,deleted_at,date,id);
CREATE INDEX IF NOT EXISTS p_transactions_account ON p_transactions(account_id,status,deleted_at);
CREATE INDEX IF NOT EXISTS p_transactions_transfer ON p_transactions(transfer_id);
CREATE TABLE IF NOT EXISTS p_transaction_splits(
 transaction_id TEXT NOT NULL REFERENCES p_transactions(id),position INTEGER NOT NULL,
 category TEXT NOT NULL,amount_minor INTEGER NOT NULL,PRIMARY KEY(transaction_id,position));
CREATE TABLE IF NOT EXISTS p_ledger_commands(
 household_id TEXT NOT NULL,key TEXT NOT NULL,payload_hash TEXT NOT NULL,response TEXT NOT NULL,
 PRIMARY KEY(household_id,key));
CREATE TABLE IF NOT EXISTS p_imports(
 id TEXT PRIMARY KEY,household_id TEXT NOT NULL,account_id TEXT NOT NULL REFERENCES p_accounts(id),
 document TEXT NOT NULL,created_at TEXT NOT NULL,receipt TEXT);
CREATE TABLE IF NOT EXISTS p_import_rows(
 transaction_id TEXT PRIMARY KEY REFERENCES p_transactions(id),import_id TEXT NOT NULL REFERENCES p_imports(id),
 household_id TEXT NOT NULL,account_id TEXT NOT NULL,line INTEGER NOT NULL,source_id TEXT,fingerprint TEXT NOT NULL,
 UNIQUE(household_id,account_id,source_id));
CREATE VIEW IF NOT EXISTS p_ledger_lines AS
 SELECT t.*,COALESCE(s.category,t.category) line_category,
 COALESCE(s.amount_minor,t.amount_minor) line_minor FROM p_transactions t
 LEFT JOIN p_transaction_splits s ON s.transaction_id=t.id;
'''
CONNECTORS = [
    {'id': 'demo-bank', 'name': 'Clara Bank Demo', 'countries': ['US', 'DO', 'ES', 'GB'], 'currencies': ['USD', 'DOP', 'EUR', 'GBP'], 'mode': 'simulated'},
    {'id': 'demo-credit', 'name': 'Clara Credit Demo', 'countries': ['US', 'DO'], 'currencies': ['USD', 'DOP'], 'mode': 'simulated'},
    {'id': 'demo-investment', 'name': 'Clara Invest Demo', 'countries': ['US', 'ES'], 'currencies': ['USD', 'EUR'], 'mode': 'simulated'},
]


def initialize(store: Store):
    with store.connection(write=True) as connection:
        connection.executescript(SCHEMA)
    with store.connection(write=True) as connection:
        seed(connection)


def evidence(record_id, kind, as_of, recorded_at=None, *, method=None, inputs=None):
    return Evidence(id=record_id, kind=kind, title='Local synthetic fixture' if kind == 'synthetic' else 'Local ledger record' if kind == 'user' else 'Calculated from local ledger records', as_of=as_of, recorded_at=recorded_at or now(), method=method, inputs=inputs or []).model_dump(mode='json')


def _currency(currency):
    if currency is not None:
        minor_units(Decimal(0), currency)


def _month(month):
    try:
        first = date.fromisoformat(month + '-01')
    except ValueError:
        raise PlatformError('invalid_month') from None
    next_month = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return str(first), str(next_month)


def _command(connection, ctx, key, operation, payload, action):
    require_editor(ctx)
    digest = hashlib.sha256(json.dumps([operation, payload], sort_keys=True, default=str).encode()).hexdigest()
    previous = connection.execute('SELECT payload_hash,response FROM p_ledger_commands WHERE household_id=? AND key=?', (ctx.household_id, key)).fetchone()
    if previous:
        if previous['payload_hash'] != digest:
            raise PlatformError('idempotency_conflict', 409)
        return json.loads(previous['response'])
    result = action()
    connection.execute('INSERT INTO p_ledger_commands VALUES(?,?,?,?)', (ctx.household_id, key, digest, json.dumps(result)))
    return result


def _account(connection, household_id, account_id, *, active=True):
    row = connection.execute('SELECT * FROM p_accounts WHERE id=? AND household_id=?' + (' AND deleted_at IS NULL' if active else ''), (account_id, household_id)).fetchone()
    if row is None:
        raise PlatformError('account_not_found', 404)
    return row


def account_balance(connection: sqlite3.Connection, household_id: str, account_id: str) -> dict:
    """Connection-level helper for atomic planning operations; positive value is an asset."""
    account = _account(connection, household_id, account_id)
    totals = connection.execute("SELECT COALESCE(SUM(amount_minor),0) delta,MAX(date) ledger_as_of,MAX(recorded_at) ledger_recorded_at FROM p_transactions WHERE household_id=? AND account_id=? AND status='posted' AND deleted_at IS NULL", (household_id, account_id)).fetchone()
    balance = account['opening_minor'] + totals['delta']
    return {**_account_document(dict(account) | dict(totals), balance), 'balance_minor': balance}


def _account_document(row, balance):
    row = dict(row)
    as_of = max(row['as_of'], row.get('ledger_as_of') or row['as_of'])
    recorded_at = max(row['recorded_at'], row.get('ledger_recorded_at') or row['recorded_at'])
    keys = ('id', 'name', 'institution', 'kind', 'currency', 'owner_id', 'connection_id', 'deleted_at')
    return {**{key: row[key] for key in keys}, 'balance': decimal_amount(balance, row['currency']), 'opening_balance': decimal_amount(row['opening_minor'], row['currency']), 'source': evidence(row['id'], 'calculated', as_of, recorded_at, method='Opening balance plus all posted nondeleted ledger changes; negative balances reduce net worth.', inputs=[f"opening_source_kind={row['source_kind']}", f"opening_minor={row['opening_minor']}", f"posted_change_minor={balance-row['opening_minor']}", f"account_id={row['id']}"])}


def _balances(connection, ctx, currency=None, include_deleted=False, *, limit=None, offset=0):
    _currency(currency)
    where = 'a.household_id=?' + ('' if include_deleted else ' AND a.deleted_at IS NULL')
    params = [ctx.household_id]
    if currency:
        where += ' AND a.currency=?'
        params.append(currency)
    page = ' LIMIT ? OFFSET ?' if limit is not None else ''
    query_params = [*params, limit, offset] if limit is not None else params
    rows = connection.execute(f'''SELECT a.*,a.opening_minor+COALESCE(SUM(t.amount_minor),0) balance_minor,MAX(t.date) ledger_as_of,MAX(t.recorded_at) ledger_recorded_at
       FROM p_accounts a LEFT JOIN p_transactions t ON t.account_id=a.id AND t.household_id=a.household_id
       AND t.status='posted' AND t.deleted_at IS NULL WHERE {where} GROUP BY a.id ORDER BY a.id{page}''', query_params).fetchall()
    return [_account_document(row, row['balance_minor']) for row in rows]


def account_balances(store: Store, ctx: Context, currency: str | None = None) -> list[dict]:
    with store.connection() as connection:
        return _balances(connection, ctx, currency)


@router.get('/accounts')
def accounts(store: DB, ctx: CTX, currency: str | None = None, include_deleted: bool = False, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    with store.connection() as connection:
        items = _balances(connection, ctx, currency, include_deleted, limit=limit, offset=offset)
        where = 'household_id=?' + ('' if include_deleted else ' AND deleted_at IS NULL') + (' AND currency=?' if currency else '')
        params = [ctx.household_id, currency] if currency else [ctx.household_id]
        total = connection.execute(f'SELECT COUNT(*) FROM p_accounts WHERE {where}', params).fetchone()[0]
    return {'items': items, 'total': total, 'limit': limit, 'offset': offset}


@router.get('/accounts/{account_id}')
def get_account(account_id: str, store: DB, ctx: CTX):
    with store.connection() as connection:
        result = account_balance(connection, ctx.household_id, account_id)
    result.pop('balance_minor')
    return result


@router.post('/accounts')
def create_account(payload: AccountCreate, store: DB, ctx: CTX):
    opening = minor_units(payload.opening_balance, payload.currency)
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        def action():
            record_id, stamp = identifier('acct'), now().isoformat()
            connection.execute('INSERT INTO p_accounts(id,household_id,owner_id,name,institution,kind,currency,opening_minor,source_kind,recorded_at,as_of) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (record_id, ctx.household_id, ctx.user_id, payload.name, payload.institution, payload.kind, payload.currency, opening, 'user', stamp, stamp[:10]))
            return _account_document(_account(connection, ctx.household_id, record_id), opening)
        return _command(connection, ctx, payload.idempotency_key, 'create_account', payload.model_dump(mode='json'), action)


@router.patch('/accounts/{account_id}')
def patch_account(account_id: str, payload: AccountPatch, store: DB, ctx: CTX):
    require_editor(ctx)
    changes = payload.model_dump(exclude_none=True)
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        _account(connection, ctx.household_id, account_id)
        for key, value in changes.items():
            connection.execute(f'UPDATE p_accounts SET {key}=? WHERE id=? AND household_id=?', (value, account_id, ctx.household_id))
        result = account_balance(connection, ctx.household_id, account_id)
        result.pop('balance_minor')
        return result


def set_account_deleted(store, ctx, account_id, deleted: bool):
    require_editor(ctx)
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        _account(connection, ctx.household_id, account_id, active=False)
        connection.execute('UPDATE p_accounts SET deleted_at=? WHERE id=? AND household_id=?', (now().isoformat() if deleted else None, account_id, ctx.household_id))
        if deleted:
            return {'id': account_id, 'deleted': True}
        result = account_balance(connection, ctx.household_id, account_id)
        result.pop('balance_minor')
        return result


@router.delete('/accounts/{account_id}')
def delete_account(account_id: str, store: DB, ctx: CTX):
    return set_account_deleted(store, ctx, account_id, True)


@router.post('/accounts/{account_id}/restore')
def restore_account(account_id: str, store: DB, ctx: CTX):
    return set_account_deleted(store, ctx, account_id, False)


def active_transaction_predicate(alias: str = 't') -> str:
    """Shared visibility for internal SQL aliases; callers scope the household."""
    return f'''{alias}.deleted_at IS NULL AND EXISTS (
        SELECT 1 FROM p_accounts AS transaction_account
        WHERE transaction_account.id={alias}.account_id
          AND transaction_account.household_id={alias}.household_id
          AND transaction_account.deleted_at IS NULL)'''


def _filters(ctx, *, account_id=None, currency=None, category=None, q=None, date_from=None, date_to=None, status=None, merchant=None, spending_only=False, lines=False):
    _currency(currency)
    conditions = ['t.household_id=?', active_transaction_predicate()]
    params = [ctx.household_id]
    if date_from and date_to and str(date_from) > str(date_to):
        raise PlatformError('invalid_date_range')
    for value, column in [(account_id, 'account_id'), (currency, 'currency'), (status, 'status')]:
        if value:
            conditions.append(f't.{column}=?')
            params.append(value)
    if category:
        if category not in CATEGORIES:
            raise PlatformError('invalid_category')
        conditions.append('t.line_category=?' if lines else 'EXISTS (SELECT 1 FROM p_ledger_lines l WHERE l.id=t.id AND l.line_category=?)')
        params.append(category)
    if merchant:
        conditions.append('t.merchant=?')
        params.append(merchant)
    if spending_only:
        conditions.append("t.status='posted' AND t.kind IN ('expense','refund')")
    if q:
        conditions.append("(t.merchant LIKE ? ESCAPE '\\' OR t.description LIKE ? ESCAPE '\\' OR t.notes LIKE ? ESCAPE '\\')")
        escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        params += [f'%{escaped}%'] * 3
    for value, sign in [(date_from, '>='), (date_to, '<=')]:
        if value:
            conditions.append(f't.date{sign}?')
            params.append(str(value))
    return ' AND '.join(conditions), params


def _transaction_document(row, splits):
    keys = ('id', 'account_id', 'date', 'merchant', 'description', 'currency', 'category', 'kind', 'status', 'notes', 'transfer_id', 'reversal_of')
    return {**{key: row[key] for key in keys}, 'account_name': row['account_name'], 'amount': decimal_amount(row['amount_minor'], row['currency']), 'splits': [{'category': s['category'], 'amount': decimal_amount(s['amount_minor'], row['currency'])} for s in splits], 'source': evidence(row['id'], row['source_kind'], row['date'], row['recorded_at'])}


def _transaction(connection, ctx, transaction_id, active=True):
    row = connection.execute('SELECT t.*,a.name account_name FROM p_transactions t JOIN p_accounts a ON a.id=t.account_id WHERE t.id=? AND t.household_id=?' + (' AND ' + active_transaction_predicate() if active else ''), (transaction_id, ctx.household_id)).fetchone()
    if row is None:
        raise PlatformError('transaction_not_found', 404)
    return row


def _transaction_response(connection, ctx, transaction_id):
    row = _transaction(connection, ctx, transaction_id)
    splits = connection.execute('SELECT * FROM p_transaction_splits WHERE transaction_id=? ORDER BY position', (transaction_id,)).fetchall()
    return _transaction_document(row, splits)


def _aggregate(connection, ctx, **filters):
    where, params = _filters(ctx, **filters, lines=True)
    rows = connection.execute(f'''SELECT t.currency,COUNT(DISTINCT t.id) transaction_count,
      COALESCE(SUM(CASE WHEN t.status='posted' AND t.kind='income' THEN t.line_minor ELSE 0 END),0) income,
      COALESCE(SUM(CASE WHEN t.status='posted' AND t.kind IN ('expense','refund') THEN -t.line_minor ELSE 0 END),0) spending,
      MAX(t.date) as_of,MAX(t.recorded_at) recorded_at
      FROM p_ledger_lines t JOIN p_accounts a ON a.id=t.account_id WHERE {where} GROUP BY t.currency ORDER BY t.currency''', params).fetchall()
    return [{'currency': row['currency'], 'income': decimal_amount(row['income'], row['currency']), 'spending': decimal_amount(row['spending'], row['currency']), 'net': decimal_amount(row['income']-row['spending'], row['currency']), 'transaction_count': row['transaction_count'], 'source': evidence('ledger-cashflow', 'calculated', row['as_of'], row['recorded_at'], method='Posted income minus expenses net of refunds; pending, transfers and adjustments excluded. Split category lines replace parent categories.', inputs=[json.dumps(filters, sort_keys=True, default=str), f"income_minor={row['income']}", f"spending_minor={row['spending']}", f"transaction_count={row['transaction_count']}"])} for row in rows]


def list_transactions(store, ctx, *, limit=50, offset=0, sort='date_desc', **filters):
    orders = {'date_desc': 't.date DESC,t.id DESC', 'date_asc': 't.date ASC,t.id ASC', 'amount_desc': 't.amount_minor DESC,t.id DESC', 'amount_asc': 't.amount_minor ASC,t.id ASC'}
    if sort not in orders or not 1 <= limit <= 100 or offset < 0:
        raise PlatformError('invalid_pagination')
    if sort.startswith('amount') and not filters.get('currency'):
        raise PlatformError('amount_sort_requires_currency')
    with store.connection() as connection:
        where, params = _filters(ctx, **filters)
        query = f'FROM p_transactions t JOIN p_accounts a ON a.id=t.account_id WHERE {where}'
        total = connection.execute(f'SELECT COUNT(*) {query}', params).fetchone()[0]
        rows = connection.execute(f'SELECT t.*,a.name account_name {query} ORDER BY {orders[sort]} LIMIT ? OFFSET ?', [*params, limit, offset]).fetchall()
        splits = {}
        if rows:
            split_rows = connection.execute('SELECT * FROM p_transaction_splits WHERE transaction_id IN (' + ','.join('?' for _ in rows) + ') ORDER BY position', [r['id'] for r in rows]).fetchall()
            for split in split_rows:
                splits.setdefault(split['transaction_id'], []).append(split)
        return {'items': [_transaction_document(row, splits.get(row['id'], [])) for row in rows], 'total': total, 'limit': limit, 'offset': offset, 'aggregates': _aggregate(connection, ctx, **filters)}


# Static CSV routes precede the transaction-id routes.
@router.get('/transactions/sample.csv')
def sample_csv():
    return Response('date,merchant,description,amount,currency,category,kind\n2026-09-20,Local Market,Groceries,-45.50,USD,groceries,expense\n', media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="argus-transactions-sample.csv"'})


def _csv_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else text


@router.get('/transactions/export.csv')
def export_csv(store: DB, ctx: CTX, account_id: str | None = None, currency: str | None = None, category: str | None = None, q: str | None = Query(None, max_length=200), date_from: date | None = None, date_to: date | None = None, status: Literal['posted', 'pending'] | None = None, merchant: str | None = Query(None, max_length=160), spending_only: bool = False):
    filters = dict(account_id=account_id, currency=currency, category=category, q=q, date_from=date_from, date_to=date_to, status=status, merchant=merchant, spending_only=spending_only)
    with store.connection() as connection:
        where, params = _filters(ctx, **filters)
        rows = connection.execute(f'SELECT t.* FROM p_transactions t JOIN p_accounts a ON a.id=t.account_id WHERE {where} ORDER BY t.date DESC,t.id DESC LIMIT 20001', params).fetchall()
    if len(rows) > 20000:
        raise PlatformError('export_too_large')
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['date', 'merchant', 'description', 'amount', 'currency', 'category', 'kind'])
    for row in rows:
        # Amount is a validated generated numeric literal, never raw user text.
        writer.writerow([row['date'], _csv_cell(row['merchant']), _csv_cell(row['description']), decimal_amount(row['amount_minor'], row['currency']), row['currency'], row['category'], row['kind']])
    return Response(output.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename="clara-transactions.csv"'})


@router.get('/transactions')
def transactions(store: DB, ctx: CTX, account_id: str | None = None, currency: str | None = None, category: str | None = None, q: str | None = Query(None, max_length=200), date_from: date | None = None, date_to: date | None = None, status: Literal['posted', 'pending'] | None = None, sort: Literal['date_desc', 'date_asc', 'amount_desc', 'amount_asc'] = 'date_desc', limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), merchant: str | None = Query(None, max_length=160), spending_only: bool = False):
    return list_transactions(store, ctx, limit=limit, offset=offset, sort=sort, account_id=account_id, currency=currency, category=category, q=q, date_from=date_from, date_to=date_to, status=status, merchant=merchant, spending_only=spending_only)


def _validate_categories(category, kind, splits, total, currency):
    expected = 'income' if kind == 'income' else 'transfer' if kind == 'transfer' else 'expense'
    if category not in CATEGORIES or (kind != 'adjustment' and CATEGORIES[category] != expected):
        raise PlatformError('invalid_category')
    if splits:
        if kind in ('income', 'transfer', 'adjustment'):
            raise PlatformError('split_kind_unsupported')
        amounts = [minor_units(split.amount, currency) for split in splits]
        if sum(amounts) != total or any(amount == 0 or (amount > 0) != (total > 0) for amount in amounts):
            raise PlatformError('split_total_mismatch')
        if any(CATEGORIES.get(split.category) != 'expense' for split in splits):
            raise PlatformError('invalid_category')


def _write_splits(connection, transaction_id, splits, currency):
    connection.execute('DELETE FROM p_transaction_splits WHERE transaction_id=?', (transaction_id,))
    connection.executemany('INSERT INTO p_transaction_splits VALUES(?,?,?,?)', [(transaction_id, position, split.category, minor_units(split.amount, currency)) for position, split in enumerate(splits)])


def _insert_transaction(connection, ctx, payload, currency, *, amount=None, transfer_id=None, account_id=None, reversal_of=None):
    record_id = identifier('txn')
    connection.execute('INSERT INTO p_transactions(id,household_id,account_id,date,merchant,description,amount_minor,currency,category,kind,status,notes,transfer_id,reversal_of,source_kind,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (record_id, ctx.household_id, account_id or payload.account_id, str(payload.date), payload.merchant, payload.description, minor_units(payload.amount, currency) if amount is None else amount, currency, payload.category, payload.kind, payload.status, payload.notes, transfer_id, reversal_of, 'user', now().isoformat()))
    _write_splits(connection, record_id, payload.splits, currency)
    return record_id


def post_transaction(connection, ctx: Context, payload: TransactionCreate) -> dict:
    """Post inside the caller's write transaction so bill and ledger receipts agree."""
    def action():
        account = _account(connection, ctx.household_id, payload.account_id)
        amount = minor_units(payload.amount, account['currency'])
        _validate_categories(payload.category, payload.kind, payload.splits, amount, account['currency'])
        transfer_id = None
        if payload.to_account_id:
            target = _account(connection, ctx.household_id, payload.to_account_id)
            if target['currency'] != account['currency']:
                raise PlatformError('cross_currency_transfer_unsupported')
            if target['id'] == account['id']:
                raise PlatformError('same_account_transfer')
            transfer_id = identifier('transfer')
            _insert_transaction(connection, ctx, payload, account['currency'], amount=-amount, transfer_id=transfer_id, account_id=target['id'])
        transaction_id = _insert_transaction(connection, ctx, payload, account['currency'], transfer_id=transfer_id)
        return _transaction_response(connection, ctx, transaction_id)
    return _command(connection, ctx, payload.idempotency_key, 'transaction', payload.model_dump(mode='json'), action)


def record_transaction(store: Store, ctx: Context, payload: TransactionCreate) -> dict:
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        return post_transaction(connection, ctx, payload)


@router.post('/transactions')
def create_transaction(payload: TransactionCreate, store: DB, ctx: CTX):
    return record_transaction(store, ctx, payload)


@router.get('/transactions/{transaction_id}')
def transaction_detail(transaction_id: str, store: DB, ctx: CTX):
    with store.connection() as connection:
        return _transaction_response(connection, ctx, transaction_id)


@router.patch('/transactions/{transaction_id}')
def patch_transaction(transaction_id: str, payload: TransactionPatch, store: DB, ctx: CTX):
    require_editor(ctx)
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        row = _transaction(connection, ctx, transaction_id)
        if row['reversal_of'] or connection.execute('SELECT 1 FROM p_transactions WHERE reversal_of=?', (transaction_id,)).fetchone():
            raise PlatformError('reversed_transaction_immutable', 409)
        existing = connection.execute('SELECT * FROM p_transaction_splits WHERE transaction_id=? ORDER BY position', (transaction_id,)).fetchall()
        splits = payload.splits if payload.splits is not None else [Split(category=s['category'], amount=Decimal(decimal_amount(s['amount_minor'], row['currency']))) for s in existing]
        category = payload.category if payload.category is not None else row['category']
        _validate_categories(category, row['kind'], splits, row['amount_minor'], row['currency'])
        for key, value in payload.model_dump(exclude_none=True, exclude={'splits'}).items():
            connection.execute(f'UPDATE p_transactions SET {key}=? WHERE id=? AND household_id=?', (value, transaction_id, ctx.household_id))
        if payload.splits is not None:
            _write_splits(connection, transaction_id, splits, row['currency'])
        return _transaction_response(connection, ctx, transaction_id)


def set_transaction_deleted(store, ctx, transaction_id, deleted: bool):
    require_editor(ctx)
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        row = _transaction(connection, ctx, transaction_id, active=False)
        _account(connection, ctx.household_id, row['account_id'])
        if row['reversal_of'] or connection.execute('SELECT 1 FROM p_transactions WHERE reversal_of=?', (transaction_id,)).fetchone():
            raise PlatformError('reversed_transaction_immutable', 409)
        column, value = ('transfer_id', row['transfer_id']) if row['transfer_id'] else ('id', transaction_id)
        if row['transfer_id']:
            for related in connection.execute('SELECT account_id FROM p_transactions WHERE transfer_id=? AND household_id=?', (value, ctx.household_id)):
                _account(connection, ctx.household_id, related['account_id'])
        connection.execute(f'UPDATE p_transactions SET deleted_at=? WHERE {column}=? AND household_id=?', (now().isoformat() if deleted else None, value, ctx.household_id))
        return {'id': transaction_id, 'deleted': True} if deleted else _transaction_response(connection, ctx, transaction_id)


@router.delete('/transactions/{transaction_id}')
def delete_transaction(transaction_id: str, store: DB, ctx: CTX):
    return set_transaction_deleted(store, ctx, transaction_id, True)


@router.post('/transactions/{transaction_id}/restore')
def restore_transaction(transaction_id: str, store: DB, ctx: CTX):
    return set_transaction_deleted(store, ctx, transaction_id, False)


@router.post('/transactions/{transaction_id}/reverse')
def reverse_transaction(transaction_id: str, payload: Idempotent, store: DB, ctx: CTX):
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        def action():
            row = _transaction(connection, ctx, transaction_id)
            if row['kind'] == 'transfer' or row['status'] != 'posted' or row['reversal_of']:
                raise PlatformError('transaction_cannot_reverse')
            existing = connection.execute('SELECT id FROM p_transactions WHERE reversal_of=?', (transaction_id,)).fetchone()
            if existing:
                return _transaction_response(connection, ctx, existing['id'])
            reversal_id = identifier('txn')
            connection.execute('''INSERT INTO p_transactions(id,household_id,account_id,date,merchant,description,amount_minor,currency,category,kind,status,notes,reversal_of,source_kind,recorded_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (reversal_id, ctx.household_id, row['account_id'], row['date'], row['merchant'], 'Reversal: ' + row['description'], -row['amount_minor'], row['currency'], row['category'], row['kind'], 'posted', '', transaction_id, 'user', now().isoformat()))
            connection.execute('INSERT INTO p_transaction_splits SELECT ?,position,category,-amount_minor FROM p_transaction_splits WHERE transaction_id=?', (reversal_id, transaction_id))
            return _transaction_response(connection, ctx, reversal_id)
        return _command(connection, ctx, payload.idempotency_key, 'reverse:' + transaction_id, {}, action)


def _spending(connection, ctx, month, currency):
    _currency(currency)
    first, next_month = _month(month)
    filters = {'currency': currency, 'date_from': first, 'date_to': str(date.fromordinal(date.fromisoformat(next_month).toordinal()-1)), 'status': 'posted'}
    totals = _aggregate(connection, ctx, **filters)
    summary = totals[0] if totals else {'currency': currency, 'income': decimal_amount(0, currency), 'spending': decimal_amount(0, currency), 'net': decimal_amount(0, currency), 'transaction_count': 0, 'source': evidence('ledger-empty', 'calculated', min(str(ANCHOR), filters['date_to']), method='No posted records in this filter.', inputs=[json.dumps(filters)])}
    where, params = _filters(ctx, **filters, lines=True)
    where += " AND t.kind IN ('expense','refund')"
    categories = connection.execute(f'SELECT t.line_category category,-SUM(t.line_minor) amount,COUNT(DISTINCT t.id) transaction_count FROM p_ledger_lines t JOIN p_accounts a ON a.id=t.account_id WHERE {where} GROUP BY t.line_category ORDER BY amount DESC,category', params).fetchall()
    merchants = connection.execute(f'SELECT t.merchant,-SUM(t.line_minor) amount,COUNT(DISTINCT t.id) transaction_count FROM p_ledger_lines t JOIN p_accounts a ON a.id=t.account_id WHERE {where} GROUP BY t.merchant ORDER BY amount DESC,t.merchant LIMIT 20', params).fetchall()
    return {'month': month, **summary, 'categories': [{'category': row['category'], 'amount': decimal_amount(row['amount'], currency), 'transaction_count': row['transaction_count']} for row in categories], 'merchants': [{'merchant': row['merchant'], 'amount': decimal_amount(row['amount'], currency), 'transaction_count': row['transaction_count']} for row in merchants]}


def spending_summary(store: Store, ctx: Context, month: str, currency: str) -> dict:
    with store.connection() as connection:
        return _spending(connection, ctx, month, currency)


@router.get('/spending')
def spending(store: DB, ctx: CTX, month: str = '2026-09', currency: str = 'USD'):
    return spending_summary(store, ctx, month, currency)


def overview_summary(store: Store, ctx: Context, month: str = '2026-09', currency: str | None = None) -> dict:
    first, next_month = _month(month)
    with store.connection() as connection:
        account_items = _balances(connection, ctx, currency)
        groups = {}
        for account in account_items:
            code = account['currency']
            group = groups.setdefault(code, {'assets': Decimal(0), 'liabilities': Decimal(0), 'inputs': [], 'as_of': str(ANCHOR)})
            group['as_of'] = max(group['as_of'], account['source']['as_of'])
            balance = Decimal(account['balance'])
            group['assets' if balance >= 0 else 'liabilities'] += abs(balance)
            group['inputs'].append(f"{account['id']}:{account['balance']}:{code}")
        # Separate manual assets have their own valuation owner, never a simulated trading book.
        from .investing import net_worth_additions
        for holding in net_worth_additions(connection, ctx):
            code = holding['currency']
            if currency and code != currency:
                continue
            group = groups.setdefault(code, {'assets': Decimal(0), 'liabilities': Decimal(0), 'inputs': [], 'as_of': str(ANCHOR)})
            group['as_of'] = max(group['as_of'], holding['source']['as_of'])
            amount = Decimal(holding['amount'])
            group['assets' if amount >= 0 else 'liabilities'] += abs(amount)
            group['inputs'].append(json.dumps(holding, sort_keys=True, default=str))
        net_worth = [{'currency': code, 'assets': str(group['assets']), 'liabilities': str(group['liabilities']), 'net_worth': str(group['assets']-group['liabilities']), 'source': evidence('net-worth:' + code, 'calculated', group['as_of'], method='Signed active ledger balances plus separately priced manual assets. Liabilities reduce net worth. Simulated trading books excluded; no FX conversion.', inputs=group['inputs'])} for code, group in sorted(groups.items())]
        cashflow = _aggregate(connection, ctx, currency=currency, date_from=first, date_to=str(date.fromordinal(date.fromisoformat(next_month).toordinal()-1)))
        trend = []
        # Six complete selected calendar windows. Each summary is computed by SQL, never a page slice.
        anchor = date.fromisoformat(first)
        for delta in range(5, -1, -1):
            year, index = divmod(anchor.year * 12 + anchor.month - 1 - delta, 12)
            trend_month = f'{year:04d}-{index+1:02d}'
            start, end = _month(trend_month)
            values = _aggregate(connection, ctx, currency=currency, date_from=start, date_to=str(date.fromordinal(date.fromisoformat(end).toordinal()-1)))
            trend.extend({'month': trend_month, **value} for value in values)
        as_of = max([str(ANCHOR), *[group['as_of'] for group in groups.values()]])
        return {'as_of': as_of, 'account_count': len(account_items), 'accounts': account_items[:6], 'net_worth': net_worth, 'cashflow': cashflow, 'trend': trend, 'source': evidence('household-overview', 'calculated', as_of, method='Current account balances and selected-month cash flow. Synthetic fixture anchor; user records retain their own effective dates.', inputs=[f'month={month}', f'currency={currency}', f'active_accounts={len(account_items)}'])}


@router.get('/overview')
def overview(store: DB, ctx: CTX, month: str = '2026-09', currency: str | None = None):
    return overview_summary(store, ctx, month, currency)


@router.get('/categories')
def categories():
    return {'items': [{'id': key, 'kind': value} for key, value in CATEGORIES.items()]}


@router.get('/connectors')
def connectors():
    return {'items': CONNECTORS}


def _connection(connection, ctx, connection_id):
    row = connection.execute('SELECT * FROM p_connections WHERE id=? AND household_id=?', (connection_id, ctx.household_id)).fetchone()
    if row is None:
        raise PlatformError('connection_not_found', 404)
    return {key: row[key] for key in ('id', 'connector_id', 'status', 'last_good_at', 'last_attempt_at', 'error_code')} | {'mode': 'simulated'}


@router.get('/connections')
def connections(store: DB, ctx: CTX):
    with store.connection() as connection:
        ids = connection.execute('SELECT id FROM p_connections WHERE household_id=? ORDER BY id', (ctx.household_id,)).fetchall()
        return {'items': [_connection(connection, ctx, row['id']) for row in ids]}


@router.post('/connections')
def connect(payload: Connect, store: DB, ctx: CTX):
    if payload.connector_id not in {connector['id'] for connector in CONNECTORS}:
        raise PlatformError('connector_not_found', 404)
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        def action():
            record_id, stamp = identifier('connection'), now().isoformat()
            connection.execute('INSERT INTO p_connections VALUES(?,?,?,?,?,?,?,?)', (record_id, ctx.household_id, payload.connector_id, 'connected', stamp, stamp, None, stamp))
            institution = {'demo-bank': 'Banco Clara', 'demo-credit': 'Clara Credit', 'demo-investment': 'Clara Invest'}[payload.connector_id]
            connection.execute('UPDATE p_accounts SET connection_id=? WHERE household_id=? AND institution=? AND deleted_at IS NULL AND connection_id IS NULL', (record_id, ctx.household_id, institution))
            return _connection(connection, ctx, record_id)
        return _command(connection, ctx, payload.idempotency_key, 'connect', payload.model_dump(mode='json'), action)


@router.post('/connections/{connection_id}/sync')
def sync(connection_id: str, payload: Sync, store: DB, ctx: CTX):
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        def action():
            current = _connection(connection, ctx, connection_id)
            stamp = now().isoformat()
            connection.execute('UPDATE p_connections SET status=?,last_good_at=?,last_attempt_at=?,error_code=? WHERE id=? AND household_id=?', ('connected' if payload.outcome == 'success' else 'failed', stamp if payload.outcome == 'success' else current['last_good_at'], stamp, None if payload.outcome == 'success' else 'simulated_refresh_failed', connection_id, ctx.household_id))
            return _connection(connection, ctx, connection_id)
        return _command(connection, ctx, payload.idempotency_key, 'sync:' + connection_id, payload.model_dump(mode='json'), action)


CSV_FIELDS = ['date', 'merchant', 'description', 'amount', 'currency', 'category', 'kind']
IMPORT_EXPIRY = timedelta(minutes=30)


def _fingerprint(row, amount):
    return (row['date'], row['merchant'], row['description'], amount, row['currency'])


def _import_identities(connection, ctx, account_id):
    return [Identity(
        key='record:' + row['id'], fingerprint=_fingerprint(row, row['amount_minor']),
        source_id=row['source_id'],
        source_fingerprint=tuple(json.loads(row['fingerprint'])) if row['fingerprint'] else None,
    ) for row in connection.execute('''SELECT t.id,t.date,t.merchant,t.description,t.amount_minor,t.currency,p.source_id,p.fingerprint
        FROM p_transactions t LEFT JOIN p_import_rows p ON p.transaction_id=t.id
        WHERE t.household_id=? AND t.account_id=? ORDER BY t.id''', (ctx.household_id, account_id))]


def _import_candidates(rows):
    return [Identity('line:' + str(item['line']),
                     _fingerprint(item, minor_units(Decimal(item['amount']), item['currency'])),
                     item.get('source_id')) for item in rows]


def _normalize_statement_row(raw, payload, currency):
    mapping = payload.mapping
    def cell(field):
        column = getattr(mapping, field)
        return raw[column].strip() if column else ''
    if cell('currency') and cell('currency') != currency:
        raise PlatformError('import_currency_mismatch')
    if mapping.amount:
        amount = statement_amount(cell('amount'), payload.decimal_separator)
    else:
        debit = statement_amount(cell('debit'), payload.decimal_separator) if cell('debit') else Decimal(0)
        credit = statement_amount(cell('credit'), payload.decimal_separator) if cell('credit') else Decimal(0)
        if debit < 0 or credit < 0 or (debit and credit):
            raise PlatformError('invalid_debit_credit')
        amount = credit - debit
    kind = cell('kind') or ('expense' if amount < 0 else payload.positive_kind)
    if not kind:
        raise PlatformError('statement_positive_kind_required')
    source_id = cell('source_id') or None
    if source_id and len(source_id) > 160:
        raise PlatformError('invalid_source_id')
    return {
        'date': statement_date(cell('date'), payload.date_format),
        'merchant': cell('merchant'), 'description': cell('description'),
        'amount': amount, 'currency': currency, 'source_id': source_id,
        'kind': kind, 'category': cell('category') or ('income' if kind == 'income' else 'other'),
    }


def _parse_import_rows(table, payload, currency):
    if payload.mode == 'legacy' and list(table.headers) != CSV_FIELDS:
        raise PlatformError('invalid_csv_headers')
    if payload.mapping and any(column not in table.headers for column in payload.mapping.model_dump().values() if column):
        raise PlatformError('invalid_column_mapping')
    rows, errors = [], []
    for record in table.rows:
        try:
            if len(record.cells) != len(table.headers):
                raise PlatformError('invalid_csv_row')
            raw = dict(zip(table.headers, record.cells, strict=True))
            normalized = _normalize_statement_row(raw, payload, currency) if payload.mode == 'statement' else {**raw, 'source_id': None}
            if normalized['currency'] != currency:
                raise PlatformError('import_currency_mismatch')
            parsed = TransactionCreate(account_id=payload.account_id, date=normalized['date'], merchant=normalized['merchant'], description=normalized['description'], amount=normalized['amount'], category=normalized['category'], kind=normalized['kind'], idempotency_key=f'preview-{record.line}')
            amount = minor_units(parsed.amount, currency)
            _validate_categories(parsed.category, parsed.kind, [], amount, currency)
            if parsed.kind == 'transfer':
                raise PlatformError('csv_transfer_unsupported')
            rows.append({'line': record.line, 'date': str(parsed.date), 'merchant': parsed.merchant, 'description': parsed.description,
                         'amount': decimal_amount(amount, currency), 'currency': currency, 'category': parsed.category, 'kind': parsed.kind, 'source_id': normalized['source_id']})
        except (ValueError, InvalidOperation, PlatformError) as exc:
            errors.append({'line': record.line, 'code': exc.code if isinstance(exc, PlatformError) else 'invalid_csv_row'})
    return rows, errors


def _preview_digest(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


@router.post('/imports/preview')
def preview_import(payload: ImportPreview, store: DB, ctx: CTX):
    require_editor(ctx)
    # Resolve the owned destination before parsing. No parser holds the writer lock.
    with store.connection() as connection:
        assert_active_context(connection, ctx)
        account = dict(_account(connection, ctx.household_id, payload.account_id))
    if payload.file_name and not payload.file_name.lower().endswith(('.csv', '.tsv')):
        raise PlatformError('unsupported_statement_file')
    table = parse_delimited(payload.csv, delimiter=payload.delimiter, header_row=payload.header_row)
    if payload.mode == 'statement' and payload.mapping is None:
        return {'stage': 'mapping', 'headers': list(table.headers), 'sample_rows': [list(row.cells) for row in table.rows[:5]],
                'row_count': len(table.rows), 'currency': account['currency'], 'file_digest': table.file_digest,
                'limits': asdict(DEFAULT_LIMITS)}
    rows, errors = _parse_import_rows(table, payload, account['currency'])
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        _account(connection, ctx.household_id, payload.account_id)
        resolutions = resolve_sequence(_import_candidates(rows), _import_identities(connection, ctx, account['id']), legacy=payload.mode == 'legacy')
        for item, resolution in zip(rows, resolutions, strict=True):
            if resolution.error:
                errors.append({'line': item['line'], 'code': resolution.error})
            item.update(duplicate=resolution.duplicate_status == 'exact',
                        duplicate_status=resolution.duplicate_status,
                        duplicate_of=resolution.duplicate_of, match_snapshot=resolution.match_snapshot)
        record_id, stamp = identifier('import'), now()
        duplicates = sum(item['duplicate'] for item in rows)
        document = {'id': record_id, 'stage': 'review', 'mode': payload.mode, 'account_id': account['id'], 'rows': rows, 'errors': errors,
                    'valid_count': len(rows)-duplicates, 'duplicate_count': duplicates,
                    'review_count': sum(item['duplicate_status'] == 'possible' for item in rows),
                    'can_commit': bool(rows) and not errors and len(rows)>duplicates,
                    'file_digest': table.file_digest, 'parser_version': PARSER_VERSION, 'identity_version': IDENTITY_VERSION,
                    'mapping': payload.mapping.model_dump() if payload.mapping else None,
                    'format': {key: getattr(payload, key) for key in ('delimiter', 'header_row', 'date_format', 'decimal_separator', 'positive_kind')},
                    'created_by': ctx.user_id, 'data_generation': ctx.data_generation,
                    'expires_at': (stamp + IMPORT_EXPIRY).isoformat(),
                    'source': evidence(record_id, 'user', max((item['date'] for item in rows), default=stamp.date().isoformat()), stamp.isoformat(),
                                       method='Validated statement preview; no account changes yet.', inputs=[table.file_digest, PARSER_VERSION])}
        document['preview_digest'] = _preview_digest(document)
        connection.execute('INSERT INTO p_imports VALUES(?,?,?,?,?,NULL)', (record_id, ctx.household_id, account['id'], json.dumps(document), stamp.isoformat()))
        return document


@router.post('/imports/{import_id}/commit')
def commit_import(import_id: str, payload: ImportCommit, store: DB, ctx: CTX):
    with store.connection(write=True) as connection:
        assert_active_context(connection, ctx)
        row = connection.execute('SELECT * FROM p_imports WHERE id=? AND household_id=?', (import_id, ctx.household_id)).fetchone()
        if row is None:
            raise PlatformError('import_not_found', 404)
        preview = json.loads(row['document'])
        statement = preview.get('mode') == 'statement'
        decisions = {decision.line: decision.action for decision in payload.decisions}
        if len(decisions) != len(payload.decisions):
            raise PlatformError('invalid_import_decisions')
        if statement and payload.preview_digest != preview.get('preview_digest'):
            raise PlatformError('import_preview_changed', 409)
        canonical_decisions = [{'line': line, 'action': action} for line, action in sorted(decisions.items())]
        command_payload = {'preview_digest': payload.preview_digest, 'decisions': canonical_decisions} if statement else {}
        def action():
            if row['receipt']:
                receipt = json.loads(row['receipt'])
                if statement and receipt.get('decisions') != canonical_decisions:
                    raise PlatformError('import_decisions_changed', 409)
                return receipt
            account = _account(connection, ctx.household_id, row['account_id'])
            if preview.get('expires_at') and now() >= datetime.fromisoformat(preview['expires_at']):
                raise PlatformError('import_preview_expired', 409)
            if preview.get('data_generation', ctx.data_generation) != ctx.data_generation:
                raise PlatformError('household_data_changed', 409)
            if not preview['can_commit']:
                raise PlatformError('import_not_committable')
            review_lines = {item['line'] for item in preview['rows'] if item.get('duplicate_status') == 'possible'}
            if statement and not review_lines.issubset(decisions):
                raise PlatformError('import_review_required')
            if set(decisions) - review_lines:
                raise PlatformError('invalid_import_decisions')
            if statement and preview.get('identity_version') != IDENTITY_VERSION:
                raise PlatformError('import_preview_changed', 409)
            candidates = _import_candidates(preview['rows'])
            existing = _import_identities(connection, ctx, row['account_id'])
            frozen = [Resolution(item.get('duplicate_status', 'new'), item.get('duplicate_of'), item.get('match_snapshot', '')) for item in preview['rows']]
            resolutions = resolve_sequence(candidates, existing, legacy=not statement, frozen=frozen,
                                           decisions={'line:' + str(line): choice for line, choice in decisions.items()})
            transaction_ids, duplicates = [], 0
            for item, candidate, resolution in zip(preview['rows'], candidates, resolutions, strict=True):
                if resolution.error:
                    raise PlatformError(resolution.error, 409)
                if resolution.action == 'skip':
                    duplicates += 1
                    continue
                fingerprint, source_id = candidate.fingerprint, candidate.source_id
                transaction = TransactionCreate(account_id=account['id'], date=item['date'], merchant=item['merchant'], description=item['description'], amount=Decimal(item['amount']), category=item['category'], kind=item['kind'], idempotency_key=f'{import_id}:{item["line"]}')
                transaction_id = _insert_transaction(connection, ctx, transaction, account['currency'])
                transaction_ids.append(transaction_id)
                connection.execute('INSERT INTO p_import_rows(transaction_id,import_id,household_id,account_id,line,source_id,fingerprint) VALUES(?,?,?,?,?,?,?)',
                                   (transaction_id, import_id, ctx.household_id, account['id'], item['line'], source_id, json.dumps(fingerprint)))
            stamp = now().isoformat()
            receipt = {'id': import_id, 'imported': len(transaction_ids), 'duplicates': duplicates, 'transaction_ids': transaction_ids,
                       'decisions': canonical_decisions, 'preview_digest': preview.get('preview_digest'),
                       'source': evidence(import_id, 'user', preview['source']['as_of'], stamp, method='Confirmed atomic statement import.',
                                          inputs=[*transaction_ids, preview.get('file_digest', ''), preview.get('parser_version', 'legacy')])}
            connection.execute('UPDATE p_imports SET receipt=? WHERE id=? AND household_id=?', (json.dumps(receipt), import_id, ctx.household_id))
            return receipt
        return _command(connection, ctx, payload.idempotency_key, 'import:' + import_id, command_payload, action)


def export_data(connection, ctx):
    """Natural owned records for a user-requested private data download."""
    result = {table: [dict(row) for row in connection.execute(f'SELECT * FROM {table} WHERE household_id=?', (ctx.household_id,))] for table in ['p_accounts', 'p_transactions', 'p_connections', 'p_imports', 'p_import_rows']}
    result['p_transaction_splits'] = [dict(row) for row in connection.execute('SELECT s.* FROM p_transaction_splits s JOIN p_transactions t ON t.id=s.transaction_id WHERE t.household_id=?', (ctx.household_id,))]
    return result


def clear_data(connection, ctx):
    """Caller owns authorization and transaction; retained manifest prevents reseeding."""
    connection.execute('DELETE FROM p_transaction_splits WHERE transaction_id IN (SELECT id FROM p_transactions WHERE household_id=?)', (ctx.household_id,))
    connection.execute('UPDATE p_transactions SET reversal_of=NULL WHERE household_id=?', (ctx.household_id,))
    for table in ['p_import_rows', 'p_imports', 'p_transactions', 'p_accounts', 'p_connections', 'p_ledger_commands']:
        connection.execute(f'DELETE FROM {table} WHERE household_id=?', (ctx.household_id,))


def usage_data(connection, ctx):
    return {'accounts': connection.execute('SELECT COUNT(*) FROM p_accounts WHERE household_id=?', (ctx.household_id,)).fetchone()[0], 'transactions': connection.execute('SELECT COUNT(*) FROM p_transactions WHERE household_id=?', (ctx.household_id,)).fetchone()[0]}
