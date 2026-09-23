"""Small isolated ledger fixture for the local guest experience."""

from datetime import datetime, timedelta
from random import Random

from .common import Context, assert_active_context, identifier
from .seed import ANCHOR, MERCHANTS, STAMP


def seed_guest_ledger(db, context: Context) -> None:
    """Called inside Identity's transaction after the owned guest exists."""
    assert_active_context(db, context)
    if db.execute(
        "SELECT 1 FROM p_accounts WHERE household_id=? LIMIT 1",
        (context.household_id,),
    ).fetchone():
        raise ValueError("Guest fixture requires an empty household")
    accounts = [
        ("Cuenta diaria", "checking", "DOP", 12500000),
        ("Reserva familiar", "savings", "DOP", 28000000),
        ("Travel savings", "savings", "USD", 240000),
    ]
    ids = []
    for position, (name, kind, currency, opening) in enumerate(accounts):
        account_id = identifier("account")
        ids.append(account_id)
        recorded_at = (
            datetime.fromisoformat(STAMP) + timedelta(seconds=position)
        ).isoformat()
        db.execute(
            """INSERT INTO p_accounts
            (id,household_id,owner_id,name,institution,kind,currency,opening_minor,
             source_kind,recorded_at,as_of) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                account_id, context.household_id, context.user_id, name,
                "Demo bank", kind, currency, opening, "synthetic", recorded_at,
                str(ANCHOR),
            ),
        )
    rng = Random(20260921)
    rows = []
    categories = tuple(MERCHANTS)
    for _ in range(120):
        category = rng.choice(categories)
        day = ANCHOR - timedelta(days=rng.randrange(60))
        rows.append(
            (
                identifier("transaction"), context.household_id, ids[0],
                str(day), rng.choice(MERCHANTS[category]),
                "", -rng.randrange(12500, 245000),
                "DOP", category, "expense", "posted", "synthetic", STAMP,
            )
        )
    for days_ago in (5, 35):
        rows.append(
            (
                identifier("transaction"), context.household_id, ids[0],
                str(ANCHOR - timedelta(days=days_ago)), "Demo payroll",
                "Synthetic monthly income", 14500000, "DOP", "income",
                "income", "posted", "synthetic", STAMP,
            )
        )
    db.executemany(
        """INSERT INTO p_transactions
        (id,household_id,account_id,date,merchant,description,amount_minor,
         currency,category,kind,status,source_kind,recorded_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
