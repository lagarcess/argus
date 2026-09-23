"""Read-only display currency provenance; ledger records retain their currency."""

from .common import PlatformError


def resolve_currency_context(db, context, home, *, account_id=None):
    account = None
    ledger_available = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='p_accounts'"
    ).fetchone()
    if ledger_available:
        if account_id is not None:
            account = db.execute(
                """SELECT id,currency FROM p_accounts
                WHERE household_id=? AND id=? AND deleted_at IS NULL""",
                (context.household_id, account_id),
            ).fetchone()
        else:
            account = db.execute(
                """SELECT id,currency FROM p_accounts
                WHERE household_id=? AND deleted_at IS NULL
                ORDER BY recorded_at,id LIMIT 1""",
                (context.household_id,),
            ).fetchone()
    if account_id is not None and account is None:
        raise PlatformError("account_not_found", 404)
    if home["currency_override"] is not None:
        currency, source = home["currency_override"], "explicit_override"
    elif account is not None:
        currency = account["currency"]
        source = "selected_account" if account_id is not None else "default_account"
    else:
        currency, source = home["effective_currency"], "household_default"
        if currency is None:
            source = "unknown"
    return {
        "currency": currency,
        "source": source,
        "account_id": account["id"] if account is not None else None,
    }
