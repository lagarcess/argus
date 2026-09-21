"""Ledger acceptance: exact money, full-filter totals, isolation and realistic volume."""
import json
import shutil
from datetime import date
from decimal import Decimal
from time import perf_counter

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from server.platform import ledger
from server.platform.common import Context, PlatformError, get_context
from server.platform.ledger_contracts import TransactionCreate
from server.store import Store

CTX = Context('user-demo', 'household-demo', 'owner', 'test-session')
OTHER = Context('user-other', 'household-other', 'owner', 'other-session')


@pytest.fixture(scope='session')
def seeded(tmp_path_factory):
    path = tmp_path_factory.mktemp('ledger-seed') / 'seed.sqlite'
    ledger.initialize(Store(path))
    return path


@pytest.fixture
def store(tmp_path, seeded):
    path = tmp_path / 'ledger.sqlite'
    shutil.copyfile(seeded, path)
    return Store(path)


@pytest.fixture
def client(store):
    app = FastAPI()
    app.state.store = store
    app.dependency_overrides[get_context] = lambda: CTX
    app.include_router(ledger.router)
    @app.exception_handler(PlatformError)
    async def error(_request, exc):
        return JSONResponse({'code': exc.code}, status_code=exc.status)
    with TestClient(app) as client:
        yield client


def manual(client, key='test-transaction', **changes):
    body = dict(account_id='acct-demo-01', date='2026-09-20', merchant='Fixture merchant', description='Invariant test', amount='-12.50', category='groceries', kind='expense', idempotency_key=key)
    body.update(changes)
    return client.post('/api/platform/transactions', json=body)


def test_fixture_volume_determinism_and_realistic_calendar(store, tmp_path):
    with store.connection() as connection:
        rows = connection.execute('SELECT COUNT(*) n,COUNT(DISTINCT substr(date,1,7)) months,MAX(date) last FROM p_transactions').fetchone()
        assert rows['n'] >= 12000
        assert rows['months'] == 24
        assert rows['last'] == '2026-09-20'
        assert connection.execute('SELECT COUNT(*) FROM p_accounts WHERE household_id=?', (CTX.household_id,)).fetchone()[0] >= 12
        before = [tuple(row) for row in connection.execute('SELECT * FROM p_transactions ORDER BY id LIMIT 5')]
    ledger.initialize(store)
    other = Store(tmp_path / 'repeat.sqlite')
    ledger.initialize(other)
    with other.connection() as connection:
        assert before == [tuple(row) for row in connection.execute('SELECT * FROM p_transactions ORDER BY id LIMIT 5')]


def test_page_bound_full_totals_and_speed(client, store):
    started = perf_counter()
    first = client.get('/api/platform/transactions?currency=DOP&limit=25').json()
    second = client.get('/api/platform/transactions?currency=DOP&limit=25&offset=25').json()
    assert perf_counter() - started < 2
    assert len(first['items']) == len(second['items']) == 25
    assert first['total'] > 3000
    assert not {r['id'] for r in first['items']} & {r['id'] for r in second['items']}
    assert first['aggregates'] == second['aggregates']
    assert len(json.dumps(first)) < 50000
    with store.connection() as connection:
        expense = connection.execute("SELECT -SUM(amount_minor) FROM p_transactions WHERE household_id=? AND currency='DOP' AND status='posted' AND kind IN ('expense','refund')", (CTX.household_id,)).fetchone()[0]
    assert Decimal(first['aggregates'][0]['spending']) == Decimal(expense) / 100
    assert client.get('/api/platform/transactions?limit=101').status_code == 422
    assert client.get('/api/platform/transactions?sort=amount_desc').status_code == 422


def test_filters_exact_scope_and_literal_search(client):
    query = '/api/platform/transactions?account_id=acct-demo-09&currency=DOP&date_from=2026-09-01&date_to=2026-09-20&category=groceries&status=posted&q=Mercado&sort=amount_asc'
    payload = client.get(query).json()
    assert payload['items']
    assert all(row['account_id'] == 'acct-demo-09' and row['category'] == 'groceries' and 'Mercado' in row['merchant'] for row in payload['items'])
    assert client.get('/api/platform/transactions?q=%25').json()['total'] == 0
    assert client.get('/api/platform/transactions?date_from=2026-09-20&date_to=2026-01-01').status_code == 422


def test_household_isolation_read_write_import(client):
    assert client.get('/api/platform/accounts/acct-other-01').status_code == 404
    assert manual(client, account_id='acct-other-01').status_code == 404
    assert client.delete('/api/platform/accounts/acct-other-01').status_code == 404
    assert client.get('/api/platform/transactions?account_id=acct-other-01').json()['total'] == 0
    assert client.post('/api/platform/imports/preview', json={'account_id': 'acct-other-01', 'csv': 'x'}).status_code == 404


def test_viewer_cannot_mutate(client):
    client.app.dependency_overrides[get_context] = lambda: Context('user-viewer', 'household-demo', 'viewer', 'viewer-session')
    assert manual(client).status_code == 403
    assert client.delete('/api/platform/accounts/acct-demo-01').status_code == 403
    assert client.get('/api/platform/accounts').status_code == 200


def test_idempotency_and_pending_do_not_change_balance(client):
    balance = client.get('/api/platform/accounts/acct-demo-01').json()['balance']
    first = manual(client, status='pending')
    again = manual(client, status='pending')
    assert first.status_code == 200
    assert first.json() == again.json()
    assert client.get('/api/platform/accounts/acct-demo-01').json()['balance'] == balance
    assert manual(client, amount='-19.00').status_code == 409


@pytest.mark.parametrize('amount,currency,status', [('0.001', 'USD', 422), ('12', 'ZZZ', 422), ('-150.125', 'KWD', 200), ('50.5', 'JPY', 422), ('50', 'JPY', 200)])
def test_currency_precision(client, amount, currency, status):
    response = client.post('/api/platform/accounts', json={'name': 'Precision fixture', 'kind': 'cash', 'currency': currency, 'opening_balance': amount, 'idempotency_key': 'precision'})
    assert response.status_code == status


def test_transfer_conserves_net_worth_and_does_not_change_spending(client, store):
    before = {r['id']: Decimal(r['balance']) for r in ledger.account_balances(store, CTX, 'USD')}
    spending = ledger.spending_summary(store, CTX, '2026-09', 'USD')
    response = manual(client, amount='-125.25', category='transfer', kind='transfer', to_account_id='acct-demo-04')
    assert response.status_code == 200, response.text
    after = {r['id']: Decimal(r['balance']) for r in ledger.account_balances(store, CTX, 'USD')}
    assert after['acct-demo-01'] == before['acct-demo-01'] - Decimal('125.25')
    assert after['acct-demo-04'] == before['acct-demo-04'] + Decimal('125.25')
    assert sum(before.values()) == sum(after.values())
    assert ledger.spending_summary(store, CTX, '2026-09', 'USD')['spending'] == spending['spending']
    assert manual(client, key='cross', amount='-1', category='transfer', kind='transfer', to_account_id='acct-demo-09').status_code == 422
    assert client.delete('/api/platform/transactions/' + response.json()['id']).status_code == 200
    restored = {r['id']: Decimal(r['balance']) for r in ledger.account_balances(store, CTX, 'USD')}
    assert restored == before
    assert client.post('/api/platform/transactions/' + response.json()['id'] + '/restore').status_code == 200


def test_split_category_totals_reversal_and_immutability(client, store):
    baseline = ledger.spending_summary(store, CTX, '2026-09', 'USD')
    item = manual(client).json()
    response = client.patch('/api/platform/transactions/' + item['id'], json={'splits': [{'category': 'groceries', 'amount': '-10'}, {'category': 'health', 'amount': '-2.50'}]})
    assert response.status_code == 200
    filtered = client.get('/api/platform/transactions?category=health&q=Fixture%20merchant').json()
    assert filtered['total'] == 1
    assert filtered['aggregates'][0]['spending'] == '2.50'
    assert client.patch('/api/platform/transactions/' + item['id'], json={'splits': [{'category': 'health', 'amount': '-9'}]}).status_code == 422
    reversal = client.post('/api/platform/transactions/' + item['id'] + '/reverse', json={'idempotency_key': 'reverse-1'}).json()
    assert reversal['amount'] == '12.50'
    assert reversal['reversal_of'] == item['id']
    assert ledger.spending_summary(store, CTX, '2026-09', 'USD')['spending'] == baseline['spending']
    assert client.post('/api/platform/transactions/' + item['id'] + '/reverse', json={'idempotency_key': 'reverse-2'}).json()['id'] == reversal['id']
    assert client.delete('/api/platform/transactions/' + item['id']).status_code == 409
    assert client.patch('/api/platform/transactions/' + reversal['id'], json={'category': 'other'}).status_code == 409


def test_csv_preview_atomic_commit_duplicates_and_injection(client, store):
    csv_text = 'date,merchant,description,amount,currency,category,kind\n2026-09-20,=HYPERLINK(test),Import fixture,-42.00,USD,groceries,expense\n'
    request = {'account_id': 'acct-demo-01', 'csv': csv_text + csv_text.split('\n')[1] + '\n'}
    before = client.get('/api/platform/accounts/acct-demo-01').json()['balance']
    preview = client.post('/api/platform/imports/preview', json=request).json()
    assert preview['duplicate_count'] == 1
    assert preview['valid_count'] == 1
    assert preview['can_commit']
    assert client.get('/api/platform/accounts/acct-demo-01').json()['balance'] == before
    path = '/api/platform/imports/' + preview['id'] + '/commit'
    receipt = client.post(path, json={'idempotency_key': 'csv-1'}).json()
    assert receipt['imported'] == 1
    assert client.post(path, json={'idempotency_key': 'csv-1'}).json() == receipt
    assert client.post(path, json={'idempotency_key': 'csv-2'}).json() == receipt
    assert client.post('/api/platform/imports/preview', json=request).json()['can_commit'] is False
    exported = client.get('/api/platform/transactions/export.csv?q=Import%20fixture').text
    assert "'=HYPERLINK(test)" in exported
    assert Decimal(client.get('/api/platform/accounts/acct-demo-01').json()['balance']) == Decimal(before) - 42


def test_csv_validation_prevents_partial_writes(client):
    body = {'account_id': 'acct-demo-01', 'csv': 'date,merchant,description,amount,currency,category,kind\n2026-09-20,Market,Valid,-12,USD,groceries,expense\n2026-09-20,Market,Invalid,-12.001,USD,groceries,expense\n'}
    preview = client.post('/api/platform/imports/preview', json=body).json()
    assert len(preview['errors']) == 1
    assert not preview['can_commit']
    assert client.post('/api/platform/imports/' + preview['id'] + '/commit', json={'idempotency_key': 'bad-csv'}).status_code == 422
    assert client.get('/api/platform/transactions?q=Valid').json()['total'] == 0


def test_failed_sync_retains_last_good_balance(client):
    created = client.post('/api/platform/connections', json={'connector_id': 'demo-bank', 'idempotency_key': 'connect'}).json()
    before = client.get('/api/platform/accounts/acct-demo-01').json()['balance']
    failed = client.post('/api/platform/connections/' + created['id'] + '/sync', json={'outcome': 'failure', 'idempotency_key': 'sync'}).json()
    assert failed['status'] == 'failed'
    assert failed['last_good_at'] == created['last_good_at']
    assert failed['error_code'] == 'simulated_refresh_failed'
    assert client.get('/api/platform/accounts/acct-demo-01').json()['balance'] == before


def test_account_softdelete_restore_and_lifecycle_preserves_other_household(client, store):
    before = client.get('/api/platform/accounts/acct-demo-01').json()
    assert client.delete('/api/platform/accounts/acct-demo-01').status_code == 200
    assert client.get('/api/platform/transactions?account_id=acct-demo-01').json()['total'] == 0
    assert client.post('/api/platform/accounts/acct-demo-01/restore').json()['balance'] == before['balance']
    with store.connection(write=True) as connection:
        exported = ledger.export_data(connection, CTX)
        assert len(exported['p_transactions']) >= 12000
        ledger.clear_data(connection, CTX)
    ledger.initialize(store)
    assert ledger.account_balances(store, CTX) == []
    assert len(ledger.account_balances(store, OTHER)) == 1


def test_public_transaction_can_rollback_with_callers_business_write(store):
    command = TransactionCreate(account_id='acct-demo-01', date=date(2026, 9, 20), merchant='Atomic bill', amount=Decimal('-10'), category='utilities', idempotency_key='atomic')
    with pytest.raises(RuntimeError):
        with store.connection(write=True) as connection:
            ledger.post_transaction(connection, CTX, command)
            raise RuntimeError('caller state failed')
    assert ledger.list_transactions(store, CTX, q='Atomic bill')['total'] == 0


def test_overview_combines_manual_assets_once_and_is_bounded(client, store):
    from server.platform import investing
    ledger_only = client.get('/api/platform/overview?currency=USD').json()
    assert len(ledger_only['accounts']) <= 6
    assert ledger_only['account_count'] == 8
    assert len(ledger_only['trend']) == 6
    investing.initialize(store)
    response = client.get('/api/platform/overview?currency=USD')
    assert response.status_code == 200, response.text
    combined = response.json()
    with store.connection() as connection:
        additions = investing.net_worth_additions(connection, CTX)
    added = sum(Decimal(item['amount']) for item in additions if item['currency'] == 'USD')
    assert Decimal(combined['net_worth'][0]['net_worth']) == Decimal(ledger_only['net_worth'][0]['net_worth']) + added
    assert combined['account_count'] == ledger_only['account_count']
    assert len(response.content) < 50000


def test_merchant_drill_returns_only_contributing_posted_lines(client):
    manual(client, key='spend', merchant='Exact merchant')
    manual(client, key='income', merchant='Exact merchant', amount='100', category='income', kind='income')
    manual(client, key='pending', merchant='Exact merchant', status='pending')
    manual(client, key='other', merchant='Other merchant', description='Exact merchant')
    response = client.get('/api/platform/transactions?merchant=Exact%20merchant&spending_only=true').json()
    assert response['total'] == 1
    assert response['aggregates'][0]['spending'] == '12.50'


def test_fixture_liabilities_and_cash_have_realistic_signs(store):
    for account in ledger.account_balances(store, CTX):
        balance = Decimal(account['balance'])
        assert balance < 0 if account['kind'] in ('credit_card', 'loan') else balance > 0


def test_account_pagination_is_sql_bounded(client):
    first = client.get('/api/platform/accounts?limit=2&offset=0').json()
    second = client.get('/api/platform/accounts?limit=2&offset=2').json()
    assert first['total'] == second['total'] == 14
    assert len(first['items']) == len(second['items']) == 2
    assert not {a['id'] for a in first['items']} & {a['id'] for a in second['items']}
