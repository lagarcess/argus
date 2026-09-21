"""Credit observations and a fixed-payment Decimal amortization calculator."""

from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter

from .common import CURRENCY_DIGITS, assert_active_context, minor_units, require_editor
from .service_contracts import (
    ContextDependency,
    CreditAccount,
    Payoff,
    StoreDependency,
    evidence,
    new_record,
    record,
    rows,
    save,
)

router = APIRouter()


def calculate_payoff(account, extra):
    currency = account["currency"]
    minor_units(extra, currency)
    quantum = Decimal(1).scaleb(-CURRENCY_DIGITS[currency])
    balance = Decimal(account["balance"])
    payment = Decimal(account["minimum_payment"]) + extra
    rate = Decimal(account["apr_pct"]) / 1200
    interest_total = Decimal(0)
    paid_total = Decimal(0)
    status, months = "horizon_exceeded", None
    if balance == 0:
        status, months = "paid_off", 0
    else:
        for month in range(1, 1201):
            interest = (balance * rate).quantize(quantum, rounding=ROUND_HALF_UP)
            if payment <= interest:
                status = "non_amortizing"
                break
            paid = min(payment, balance + interest)
            balance = balance + interest - paid
            interest_total += interest
            paid_total += paid
            if balance == 0:
                status, months = "paid_off", month
                break
    source = evidence(
        account["id"], account["as_of"], "calculated", "monthly_fixed_payment"
    )
    source["inputs"] = [account["id"]]
    return {
        "account_id": account["id"],
        "currency": currency,
        "monthly_payment": str(payment),
        "status": status,
        "months": months,
        "total_interest": str(interest_total),
        "total_paid": str(paid_total),
        "formula": "interest = round(balance * apr_pct / 1200); payment = min(minimum_payment + extra, balance + interest)",
        "assumptions": [
            "fixed_apr",
            "fixed_monthly_payment",
            "no_fees",
            "no_new_borrowing",
            "1200_month_horizon",
        ],
        "evidence": source,
    }


@router.get("/credit")
def credit(*, store: StoreDependency, context: ContextDependency):
    with store.connection() as db:
        accounts = rows(db, "p_credit_accounts", context.household_id)
        reports = rows(db, "p_credit_reports", context.household_id)
    groups = {}
    for account in accounts:
        totals = groups.setdefault(account["currency"], [Decimal(0), Decimal(0)])
        totals[0] += Decimal(account["balance"])
        totals[1] += Decimal(account["credit_limit"])
    utilization = []
    for currency, (balance, limit) in groups.items():
        sources = [a for a in accounts if a["currency"] == currency]
        source = evidence(
            f"utilization-{currency}",
            min(a["as_of"] for a in sources),
            "calculated",
            "sum(balance) / sum(credit_limit) * 100",
        )
        source["inputs"] = [a["id"] for a in sources]
        utilization.append(
            {
                "currency": currency,
                "balance": str(balance),
                "credit_limit": str(limit),
                "utilization_pct": str((balance / limit * 100).quantize(Decimal("0.01")))
                if limit
                else None,
                "evidence": source,
            }
        )
    return {
        "accounts": accounts,
        "report": reports[0] if reports else None,
        "utilization": utilization,
    }


@router.post("/credit/accounts")
def add_account(
    payload: CreditAccount, *, store: StoreDependency, context: ContextDependency
):
    require_editor(context)
    account = new_record(payload, "credit")
    account["evidence"] = evidence(account["id"], payload.as_of)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        return save(db, "p_credit_accounts", context.household_id, account)


@router.put("/credit/accounts/{account_id}")
def update_account(
    account_id: str,
    payload: CreditAccount,
    *,
    store: StoreDependency,
    context: ContextDependency,
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        record(db, "p_credit_accounts", context.household_id, account_id)
        account = {
            "id": account_id,
            **payload.model_dump(mode="json"),
            "evidence": evidence(account_id, payload.as_of),
        }
        return save(db, "p_credit_accounts", context.household_id, account)


@router.post("/credit/payoff")
def payoff(payload: Payoff, *, store: StoreDependency, context: ContextDependency):
    with store.connection() as db:
        account = record(
            db, "p_credit_accounts", context.household_id, payload.account_id
        )
    return calculate_payoff(account, payload.extra_monthly_payment)
