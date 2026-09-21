"""Deterministic, explicitly synthetic local ledger fixture, never live bank data."""
from calendar import monthrange
from datetime import date
from random import Random

from faker import Faker

ANCHOR = date(2026, 9, 20)
STAMP = '2026-09-20T12:00:00+00:00'
ACCOUNTS = [
    ('Everyday checking', 'Banco Clara', 'checking', 'USD', 1800000),
    ('Emergency reserve', 'Banco Clara', 'savings', 'USD', 2400000),
    ('Travel savings', 'Banco Clara', 'savings', 'USD', 850000),
    ('Rewards card', 'Clara Credit', 'credit_card', 'USD', -215000),
    ('Home loan', 'Clara Credit', 'loan', 'USD', -14500000),
    ('Long-term investments', 'Clara Invest', 'investment', 'USD', 4820000),
    ('Partner checking', 'Banco Clara', 'checking', 'USD', 1250000),
    ('Cash wallet', 'Manual', 'cash', 'USD', 45000),
    ('Cuenta diaria', 'Banco Clara', 'checking', 'DOP', 12500000),
    ('Ahorro familiar', 'Banco Clara', 'savings', 'DOP', 28000000),
    ('Tarjeta local', 'Clara Credit', 'credit_card', 'DOP', -540000),
    ('European investments', 'Clara Invest', 'investment', 'EUR', 1630000),
    ('Euro checking', 'Banco Clara', 'checking', 'EUR', 650000),
    ('Kiwi savings', 'Banco Clara', 'savings', 'NZD', 410000),
]
MERCHANTS = {
    'groceries': ['Mercado Central', 'Fresh Market', 'La Despensa'],
    'dining': ['Café Lucía', 'Mesa Verde', 'Panadería Sol'],
    'transport': ['Metro Pass', 'Shell Station', 'City Transit'],
    'shopping': ['Casa Hogar', 'Book Corner', 'Everyday Goods'],
    'health': ['Farmacia Familiar', 'Wellness Clinic'],
    'entertainment': ['Cinema Central', 'Music Studio'],
    'utilities': ['Home Internet', 'Electric Company'],
    'travel': ['Coastal Hotel', 'Rail Tickets'],
}


def seed(connection):
    if connection.execute("SELECT 1 FROM p_ledger_manifest WHERE id='clara-demo-v1'").fetchone():
        return
    if connection.execute('SELECT 1 FROM p_accounts LIMIT 1').fetchone():
        return
    rng = Random(20260920)
    fake = Faker('en_US')
    fake.seed_instance(20260920)
    for n, (name, institution, kind, currency, opening) in enumerate(ACCOUNTS, 1):
        connection.execute(
            'INSERT INTO p_accounts(id,household_id,owner_id,name,institution,kind,currency,opening_minor,source_kind,recorded_at,as_of) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (f'acct-demo-{n:02d}', 'household-demo', 'user-partner' if n == 7 else 'user-demo', name, institution, kind, currency, opening, 'synthetic', STAMP, str(ANCHOR)),
        )
    connection.execute(
        'INSERT INTO p_accounts(id,household_id,owner_id,name,institution,kind,currency,opening_minor,source_kind,recorded_at,as_of) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
        ('acct-other-01', 'household-other', 'user-other', 'Separate household account', 'Manual', 'checking', 'USD', 90000, 'synthetic', STAMP, str(ANCHOR)),
    )
    rows = []
    sequence = 0
    def add(account, day, merchant, amount, category, kind='expense', status='posted', transfer=None, description=None):
        nonlocal sequence
        sequence += 1
        currency = ACCOUNTS[account - 1][3]
        rows.append((f'txn-demo-{sequence:06d}', 'household-demo', f'acct-demo-{account:02d}', str(day), merchant, description or fake.sentence(nb_words=4), amount, currency, category, kind, status, '', transfer, 'synthetic', STAMP))
    for month_index in range(24):
        year, month = divmod(2024 * 12 + 9 + month_index, 12)
        month += 1
        last = min(monthrange(year, month)[1], 20 if (year, month) == (2026, 9) else 31)
        for _ in range(550):
            account = rng.choices([1, 4, 7, 8, 9, 11, 13, 14], [22, 18, 16, 3, 20, 10, 8, 3])[0]
            category = rng.choices(list(MERCHANTS), [30, 22, 16, 10, 5, 8, 5, 4])[0]
            merchant = rng.choice(MERCHANTS[category])
            day = date(year, month, rng.randint(1, last))
            amount = rng.randint(250, 4800) * (55 if ACCOUNTS[account - 1][3] == 'DOP' else 1)
            refund = rng.random() < .025
            status = 'pending' if day >= date(2026, 9, 18) and rng.random() < .30 else 'posted'
            add(account, day, merchant, amount if refund else -amount, category, 'refund' if refund else 'expense', status)
        for account, amount, employer in [(1, 660000, 'Northstar Design payroll'), (7, 390000, 'Cedar Labs payroll'), (9, 27000000, 'Estudio Caribe nómina'), (13, 290000, 'Europa payroll'), (14, 80000, 'Consulting income')]:
            for day in [1, 15]:
                add(account, date(year, month, day), employer, amount // 2, 'income', 'income', description='Scheduled synthetic income')
        for a, b, amount in [(1, 4, 190000), (9, 11, 7300000), (1, 2, 20000), (1, 5, 120000), (1, 8, 42500)]:
            transfer = f'transfer-demo-{month_index}-{a}-{b}'
            for account, sign in [(a, -1), (b, 1)]:
                add(account, date(year, month, 16), 'Account transfer', sign * amount, 'transfer', 'transfer', transfer=transfer, description='Paired synthetic account transfer')
    connection.executemany(
        'INSERT INTO p_transactions(id,household_id,account_id,date,merchant,description,amount_minor,currency,category,kind,status,notes,transfer_id,source_kind,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows,
    )
    connection.execute('INSERT INTO p_ledger_manifest(id,recorded_at,transaction_count) VALUES(?,?,?)', ('clara-demo-v1', STAMP, len(rows)))
