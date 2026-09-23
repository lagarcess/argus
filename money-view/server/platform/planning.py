"""Household planning. Ledger owns balances and spending; receipts are immutable."""
from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ..store import Store
from .common import (
    CURRENCY_DIGITS,
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
from .planning_contracts import (
    AllocationInput,
    BillInput,
    BudgetInput,
    GoalInput,
    PauseInput,
    PayInput,
    ScenarioInput,
    ScenarioInputs,
)

DB = Annotated[Store, Depends(get_store)]
CTX = Annotated[Context, Depends(get_context)]

router = APIRouter(prefix="/api/platform", tags=["planning"])
SCHEMA = """
CREATE TABLE IF NOT EXISTS p_plans (
 id TEXT PRIMARY KEY, household_id TEXT NOT NULL, kind TEXT NOT NULL,
 document TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS p_plans_household ON p_plans(household_id,kind,status);
CREATE TABLE IF NOT EXISTS p_goal_allocations (
 goal_id TEXT NOT NULL REFERENCES p_plans(id), household_id TEXT NOT NULL,
 account_id TEXT NOT NULL, amount_minor INTEGER NOT NULL CHECK(amount_minor>=0),
 PRIMARY KEY(goal_id,account_id)
);
CREATE TABLE IF NOT EXISTS p_bill_occurrences (
 bill_id TEXT NOT NULL REFERENCES p_plans(id), household_id TEXT NOT NULL,
 due_date TEXT NOT NULL, status TEXT NOT NULL, transaction_id TEXT,
 PRIMARY KEY(bill_id,due_date)
);
CREATE TABLE IF NOT EXISTS p_scenarios (
 id TEXT PRIMARY KEY, household_id TEXT NOT NULL, document TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS p_scenarios_household ON p_scenarios(household_id);
CREATE TABLE IF NOT EXISTS p_planning_seed (id TEXT PRIMARY KEY);
CREATE TRIGGER IF NOT EXISTS p_scenarios_no_update BEFORE UPDATE ON p_scenarios
 BEGIN SELECT RAISE(ABORT,'immutable_scenario'); END;
"""


def evidence(kind: str = "user", title: str = "Recorded planning inputs", as_of: date | None = None):
    return Evidence(id=identifier("source"), kind=kind, title=title,
                    as_of=as_of or now().date(), recorded_at=now()).model_dump(mode="json")


def _plan(connection, context: Context, plan_id: str, kind: str):
    row = connection.execute("SELECT * FROM p_plans WHERE id=? AND household_id=? AND kind=?",
                             (plan_id, context.household_id, kind)).fetchone()
    if not row:
        raise PlatformError("planning_record_not_found", 404)
    return {**json.loads(row["document"]), "id": row["id"], "status": row["status"]}


def _write_plan(connection, context: Context, kind: str, payload, plan_id: str | None = None):
    require_editor(context)
    previous = _plan(connection, context, plan_id, kind) if plan_id else None
    if previous and previous["status"] == "archived":
        raise PlatformError("planning_record_archived", 409)
    result = payload.model_dump(mode="json")
    result["evidence"] = evidence()
    if kind == "bill":
        if previous and any(result[key] != previous[key] for key in ("anchor_date", "cadence")):
            occurrence = connection.execute("SELECT 1 FROM p_bill_occurrences WHERE bill_id=? LIMIT 1", (plan_id,)).fetchone()
            if occurrence:
                raise PlatformError("bill_schedule_has_occurrences", 409)
        result["next_due"] = previous["next_due"] if previous and all(result[k] == previous[k] for k in ("anchor_date", "cadence")) else result["anchor_date"]
    plan_id = plan_id or identifier(kind)
    status = previous["status"] if previous else "active"
    connection.execute("INSERT INTO p_plans VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET document=excluded.document",
                       (plan_id, context.household_id, kind, json.dumps(result), status, now().isoformat()))
    return {**result, "id": plan_id, "status": status}


def _list_plans(store: Store, context: Context, kind: str):
    with store.connection() as connection:
        rows = connection.execute("SELECT id FROM p_plans WHERE household_id=? AND kind=? AND status!='archived' ORDER BY recorded_at,id",
                                  (context.household_id, kind)).fetchall()
        return [_plan(connection, context, row["id"], kind) for row in rows]


def archive_plan(store: Store, context: Context, plan_id: str, kind: str):
    require_editor(context)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        _plan(connection, context, plan_id, kind)
        connection.execute("UPDATE p_plans SET status='archived' WHERE id=? AND household_id=?", (plan_id, context.household_id))
    return {"id": plan_id, "status": "archived"}


def save_budget(store: Store, context: Context, payload: BudgetInput, budget_id: str | None = None):
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        matches = connection.execute("SELECT id,document FROM p_plans WHERE household_id=? AND kind='budget' AND status='active'", (context.household_id,)).fetchall()
        for row in matches:
            saved = json.loads(row["document"])
            if row["id"] != budget_id and all(saved[k] == getattr(payload, k) for k in ("category", "currency", "month")):
                raise PlatformError("budget_already_exists", 409)
        return _write_plan(connection, context, "budget", payload, budget_id)


def _project_budgets(store: Store, context: Context, items):
    from .ledger import spending_summary
    summaries = {}
    for item in items:
        key = (item["month"], item["currency"])
        if key not in summaries:
            summaries[key] = spending_summary(store, context, *key)
        summary = summaries[key]
        categories = summary["categories"]
        actual = sum((Decimal(row["amount"]) for row in categories if row["category"] == item["category"]), Decimal(0))
        item["input_evidence"] = item["evidence"]
        item["actual_evidence"] = summary["source"]
        item["evidence"] = Evidence(id=identifier("source"), kind="calculated", title="Budget compared with current ledger spending", as_of=now().date(), recorded_at=now(), method="Saved budget limit minus category spending from the canonical ledger. Source records retain synthetic or user provenance.", inputs=[item["input_evidence"]["id"], summary["source"]["id"]]).model_dump(mode="json")
        item["actual"] = str(actual)
        item["remaining"] = str(Decimal(item["limit"]) - actual)
    return items


def list_budgets(store: Store, context: Context, month: str | None = None):
    items = [item for item in _list_plans(store, context, "budget") if not month or item["month"] == month]
    return {"items": _project_budgets(store, context, items)}


def get_budget(store: Store, context: Context, budget_id: str):
    with store.connection() as connection:
        item = _plan(connection, context, budget_id, "budget")
    if item["status"] == "archived":
        raise PlatformError("planning_record_not_found", 404)
    return _project_budgets(store, context, [item])[0]


def save_goal(store: Store, context: Context, payload: GoalInput, goal_id: str | None = None):
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        if goal_id:
            previous = _plan(connection, context, goal_id, "goal")
            allocations = connection.execute("SELECT 1 FROM p_goal_allocations WHERE goal_id=? AND amount_minor>0 LIMIT 1", (goal_id,)).fetchone()
            if allocations and previous["currency"] != payload.currency:
                raise PlatformError("allocated_goal_currency_locked", 409)
        return _write_plan(connection, context, "goal", payload, goal_id)


def list_goals(store: Store, context: Context):
    from .ledger import account_balance
    items = _list_plans(store, context, "goal")
    with store.connection() as connection:
        for item in items:
            rows = connection.execute("SELECT * FROM p_goal_allocations WHERE goal_id=? AND household_id=?", (item["id"], context.household_id)).fetchall()
            item["allocations"] = []
            for row in rows:
                try:
                    balance = account_balance(connection, context.household_id, row["account_id"])
                except PlatformError as error:
                    if error.code != "account_not_found":
                        raise
                    balance = None
                reserved = _reserved(connection, context, row["account_id"])
                item["allocations"].append({"account_id": row["account_id"], "amount": decimal_amount(row["amount_minor"], item["currency"]), "account_balance": balance["balance"] if balance else None, "account_evidence": balance["source"] if balance else None, "account_unavailable": balance is None, "underfunded": balance is None or reserved > balance["balance_minor"]})
            allocated = sum(row["amount_minor"] for row in rows)
            item["allocated"] = decimal_amount(allocated, item["currency"])
            item["remaining"] = str(max(Decimal(0), Decimal(item["target_amount"]) - Decimal(item["allocated"])))
    return {"items": items}


def _reserved(connection, context, account_id, exclude_goal=""):
    return connection.execute("SELECT COALESCE(SUM(a.amount_minor),0) FROM p_goal_allocations a JOIN p_plans p ON p.id=a.goal_id WHERE a.household_id=? AND a.account_id=? AND a.goal_id!=? AND p.status='active'", (context.household_id, account_id, exclude_goal)).fetchone()[0]


def allocate_goal(store: Store, context: Context, goal_id: str, payload: AllocationInput):
    from .ledger import account_balance
    require_editor(context)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        goal = _plan(connection, context, goal_id, "goal")
        if goal["status"] != "active":
            raise PlatformError("planning_record_archived", 409)
        for row in payload.allocations:
            balance = account_balance(connection, context.household_id, row.account_id)
            if balance["currency"] != goal["currency"]:
                raise PlatformError("allocation_currency_mismatch")
            amount = minor_units(row.amount, goal["currency"])
            if amount + _reserved(connection, context, row.account_id, goal_id) > balance["balance_minor"]:
                raise PlatformError("allocation_exceeds_balance", 409)
        connection.execute("DELETE FROM p_goal_allocations WHERE goal_id=? AND household_id=?", (goal_id, context.household_id))
        connection.executemany("INSERT INTO p_goal_allocations VALUES(?,?,?,?)", [(goal_id, context.household_id, row.account_id, minor_units(row.amount, goal["currency"])) for row in payload.allocations])
    return next(row for row in list_goals(store, context)["items"] if row["id"] == goal_id)


def next_occurrence(anchor: date, cadence: str, after: date) -> date:
    """Preserve anchor day across short months and leap years."""
    if after < anchor:
        return anchor
    if cadence == "weekly":
        try:
            return anchor + timedelta(days=7 * ((after - anchor).days // 7 + 1))
        except OverflowError:
            raise PlatformError("schedule_date_out_of_range") from None
    step = {"monthly": 1, "quarterly": 3, "yearly": 12}[cadence]
    elapsed = (after.year - anchor.year) * 12 + after.month - anchor.month
    offset = max(0, elapsed // step) * step
    while True:
        year, month = divmod(anchor.year * 12 + anchor.month - 1 + offset, 12)
        if year > 9999:
            raise PlatformError("schedule_date_out_of_range")
        candidate = date(year, month + 1, min(anchor.day, calendar.monthrange(year, month + 1)[1]))
        if candidate > after:
            return candidate
        offset += step


def save_bill(store: Store, context: Context, payload: BillInput, bill_id: str | None = None):
    from .ledger import account_balance
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        account = account_balance(connection, context.household_id, payload.account_id)
        if account["currency"] != payload.currency:
            raise PlatformError("bill_currency_mismatch")
        return _write_plan(connection, context, "bill", payload, bill_id)


def list_bills(store: Store, context: Context):
    return {"items": _list_plans(store, context, "bill")}


def pause_bill(store: Store, context: Context, bill_id: str, paused: bool):
    require_editor(context)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        bill = _plan(connection, context, bill_id, "bill")
        if bill["status"] == "archived":
            raise PlatformError("planning_record_archived", 409)
        status = "paused" if paused else "active"
        connection.execute("UPDATE p_plans SET status=? WHERE id=? AND household_id=?", (status, bill_id, context.household_id))
        return {**bill, "status": status}


def record_occurrence(store: Store, context: Context, bill_id: str, due: date | None, paid: bool):
    from .ledger import post_transaction
    from .ledger_contracts import TransactionCreate
    require_editor(context)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        bill = _plan(connection, context, bill_id, "bill")
        due = due or date.fromisoformat(bill["next_due"])
        previous = connection.execute("SELECT * FROM p_bill_occurrences WHERE bill_id=? AND household_id=? AND due_date=?", (bill_id, context.household_id, due.isoformat())).fetchone()
        if previous:
            if previous["status"] != ("paid" if paid else "skipped"):
                raise PlatformError("bill_occurrence_already_recorded", 409)
            return dict(previous)
        if bill["status"] != "active":
            raise PlatformError("bill_not_active", 409)
        if due.isoformat() != bill["next_due"]:
            raise PlatformError("bill_due_date_mismatch", 409)
        transaction_id = None
        if paid:
            transaction = post_transaction(connection, context, TransactionCreate(account_id=bill["account_id"], date=due, merchant=bill["name"], amount=-Decimal(bill["amount"]), category=bill["category"], kind="expense", idempotency_key=f"bill:{bill_id}:{due.isoformat()}"))
            transaction_id = transaction["id"]
        status = "paid" if paid else "skipped"
        connection.execute("INSERT INTO p_bill_occurrences VALUES(?,?,?,?,?)", (bill_id, context.household_id, due.isoformat(), status, transaction_id))
        bill["next_due"] = next_occurrence(date.fromisoformat(bill["anchor_date"]), bill["cadence"], due).isoformat()
        document = {key: value for key, value in bill.items() if key not in ("id", "status")}
        connection.execute("UPDATE p_plans SET document=? WHERE id=? AND household_id=?", (json.dumps(document), bill_id, context.household_id))
        return {"bill_id": bill_id, "household_id": context.household_id, "due_date": due.isoformat(), "status": status, "transaction_id": transaction_id}


def calculate_scenario(inputs: ScenarioInputs):
    """One deterministic monthly cash-flow owner for every life-event template."""
    with localcontext() as ctx:
        ctx.prec = 50
        monthly_return = (1 + inputs.annual_return_pct / 100) ** (Decimal(1) / 12) - 1
        monthly_inflation = (1 + inputs.inflation_pct / 100) ** (Decimal(1) / 12)
        monthly_fee = inputs.annual_fee_pct / 1200
        balance = inputs.initial_balance
        contributions = withdrawals = fees = Decimal(0)
        depletion = None
        months, years = [], []
        horizon = inputs.horizon_years * 12
        def amount(value):
            digits = CURRENCY_DIGITS[inputs.currency]
            with localcontext() as display_context:
                display_context.prec = max(50, value.adjusted() + digits + 2)
                return format(value.quantize(Decimal(1).scaleb(-digits)), "f")
        for month in range(1, horizon + 1):
            contribution = inputs.monthly_contribution if inputs.contribution_start_month <= month <= (inputs.contribution_end_month or horizon) else Decimal(0)
            requested = inputs.monthly_withdrawal if inputs.withdrawal_start_month <= month <= (inputs.withdrawal_end_month or horizon) else Decimal(0)
            if inputs.timing == "begin":
                balance += contribution
                withdrawal = min(balance, requested)
                balance -= withdrawal
            balance *= 1 + monthly_return
            fee = balance * monthly_fee
            balance -= fee
            if inputs.timing == "end":
                balance += contribution
                withdrawal = min(balance, requested)
                balance -= withdrawal
            unfunded = requested - withdrawal
            if depletion is None and requested > 0 and balance == 0:
                depletion = month
            contributions += contribution
            withdrawals += withdrawal
            fees += fee
            real_balance = balance / monthly_inflation ** month
            months.append({"month": month, "balance": amount(balance), "real_balance": amount(real_balance), "contribution": amount(contribution), "withdrawal": amount(withdrawal), "unfunded_withdrawal": amount(unfunded), "fee": amount(fee)})
            if month % 12 == 0:
                years.append({"year": month // 12, "balance": amount(balance), "real_balance": amount(real_balance)})
        return {"currency": inputs.currency, "ending_balance": amount(balance), "real_ending_balance": amount(real_balance), "total_contributions": amount(contributions), "total_withdrawals": amount(withdrawals), "total_fees": amount(fees), "depletion_month": depletion, "months": months, "years": years, "method": "Effective annual return and inflation converted to monthly rates; fees charged monthly at annual fee divided by 12; explicit cash-flow timing; balances floor at zero. Illustrative assumptions, not a forecast."}


TEMPLATE_INPUTS = {
    "home": dict(horizon_years=5, monthly_contribution="500"),
    "kids": dict(horizon_years=18, monthly_contribution="200"),
    "job": dict(horizon_years=2, initial_balance="15000", monthly_withdrawal="1500", withdrawal_end_month=6),
    "move": dict(horizon_years=2, initial_balance="10000", monthly_contribution="200", monthly_withdrawal="5000", withdrawal_start_month=12, withdrawal_end_month=12),
    "marriage": dict(horizon_years=3, monthly_contribution="400"),
    "retirement": dict(horizon_years=30, initial_balance="100000", monthly_contribution="500", contribution_end_month=120, monthly_withdrawal="1000", withdrawal_start_month=121),
    "sabbatical": dict(horizon_years=3, initial_balance="20000", monthly_withdrawal="2000", withdrawal_start_month=13, withdrawal_end_month=18),
}


def scenario_templates(currency: str = "USD"):
    minor_units(Decimal(0), currency)
    return {"items": [{"id": key, "inputs": ScenarioInputs(currency=currency, **values).model_dump(mode="json")} for key, values in TEMPLATE_INPUTS.items()]}


def save_scenario(store: Store, context: Context, payload: ScenarioInput):
    require_editor(context)
    result = calculate_scenario(payload.inputs)
    receipt = {"id": identifier("scenario"), **payload.model_dump(mode="json"), "result": result, "evidence": evidence("calculated", "Scenario calculated from recorded assumptions")}
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        connection.execute("INSERT INTO p_scenarios VALUES(?,?,?)", (receipt["id"], context.household_id, json.dumps(receipt)))
    return receipt


def list_scenarios(store: Store, context: Context, limit: int = 20, offset: int = 0):
    if not 1 <= limit <= 100 or offset < 0:
        raise PlatformError("invalid_scenario_page")
    with store.connection() as connection:
        total = connection.execute("SELECT COUNT(*) FROM p_scenarios WHERE household_id=?", (context.household_id,)).fetchone()[0]
        rows = connection.execute(
            "SELECT json_remove(document,'$.result.months','$.result.years') AS document "
            "FROM p_scenarios WHERE household_id=? ORDER BY rowid DESC LIMIT ? OFFSET ?",
            (context.household_id, limit, offset),
        ).fetchall()
        return {"items": [json.loads(row["document"]) for row in rows], "total": total, "limit": limit, "offset": offset}


def get_scenario(store: Store, context: Context, scenario_id: str):
    with store.connection() as connection:
        row = connection.execute("SELECT document FROM p_scenarios WHERE id=? AND household_id=?", (scenario_id, context.household_id)).fetchone()
        if not row:
            raise PlatformError("scenario_not_found", 404)
        return json.loads(row["document"])


def compare_scenarios(store: Store, context: Context, before_id: str, after_id: str):
    before, after = get_scenario(store, context, before_id), get_scenario(store, context, after_id)
    if before["inputs"]["currency"] != after["inputs"]["currency"]:
        raise PlatformError("scenario_currency_mismatch")
    return {"before": before, "after": after, "delta_ending_balance": str(Decimal(after["result"]["ending_balance"]) - Decimal(before["result"]["ending_balance"]))}


def export_data(connection, context: Context):
    return {table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} WHERE household_id=?", (context.household_id,))] for table in ("p_plans", "p_goal_allocations", "p_bill_occurrences", "p_scenarios")}


def clear_data(connection, context: Context):
    for table in ("p_goal_allocations", "p_bill_occurrences", "p_plans", "p_scenarios"):
        connection.execute(f"DELETE FROM {table} WHERE household_id=?", (context.household_id,))


def usage_data(connection, context: Context):
    return {"planning_records": connection.execute("SELECT COUNT(*) FROM p_plans WHERE household_id=?", (context.household_id,)).fetchone()[0], "scenarios": connection.execute("SELECT COUNT(*) FROM p_scenarios WHERE household_id=?", (context.household_id,)).fetchone()[0]}


def initialize(store: Store):
    with store.connection(write=True) as connection:
        connection.executescript(SCHEMA)
    with store.connection(write=True) as connection:
        if connection.execute("SELECT 1 FROM p_planning_seed WHERE id='v1'").fetchone():
            return
        connection.execute("INSERT INTO p_planning_seed VALUES('v1')")
        source = evidence("synthetic", "Synthetic planning demo, not actual finances", date(2026, 9, 20))
        for currency, limit, target, contribution in (("DOP", "18000", "300000", "8000"), ("USD", "650", "15000", "400")):
            values = [("budget", BudgetInput(category="groceries", month="2026-09", currency=currency, limit=limit)), ("goal", GoalInput(name="Emergency reserve", target_date=date(2028, 9, 20), currency=currency, target_amount=target, monthly_contribution=contribution))]
            for kind, payload in values:
                document = {**payload.model_dump(mode="json"), "evidence": source}
                connection.execute("INSERT INTO p_plans VALUES(?,?,?,?,?,?)", (identifier(kind), "household-demo", kind, json.dumps(document), "active", now().isoformat()))
        # Ledger initialization precedes planning in app composition.
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "p_accounts" in tables:
            from .ledger import account_balance
            rows = connection.execute("SELECT id FROM p_accounts WHERE household_id=?", ("household-demo",)).fetchall()
            for row in rows:
                account = account_balance(connection, "household-demo", row["id"])
                if account["currency"] == "DOP":
                    document = BillInput(name="Monthly utilities", account_id=row["id"], category="utilities", currency="DOP", amount="2400", anchor_date=date(2026, 9, 30)).model_dump(mode="json")
                    document.update(evidence=source, next_due="2026-09-30")
                    connection.execute("INSERT INTO p_plans VALUES(?,?,?,?,?,?)", (identifier("bill"), "household-demo", "bill", json.dumps(document), "active", now().isoformat()))
                    break
        for template in ("home", "retirement"):
            inputs = ScenarioInputs(currency="DOP", **TEMPLATE_INPUTS[template])
            receipt = {"id": identifier("scenario"), "name": template.title() + " illustration", "template": template, "inputs": inputs.model_dump(mode="json"), "result": calculate_scenario(inputs), "evidence": source}
            connection.execute("INSERT INTO p_scenarios VALUES(?,?,?)", (receipt["id"], "household-demo", json.dumps(receipt)))


@router.get("/budgets")
def budgets(*, month: str | None = None, store: DB, context: CTX):
    return list_budgets(store, context, month)


@router.get("/budgets/{budget_id}")
def budget_read(*, budget_id: str, store: DB, context: CTX):
    return get_budget(store, context, budget_id)


@router.post("/budgets")
def budget_create(*, payload: BudgetInput, store: DB, context: CTX):
    return save_budget(store, context, payload)


@router.put("/budgets/{budget_id}")
def budget_update(*, budget_id: str, payload: BudgetInput, store: DB, context: CTX):
    return save_budget(store, context, payload, budget_id)


@router.delete("/budgets/{budget_id}")
def budget_delete(*, budget_id: str, store: DB, context: CTX):
    return archive_plan(store, context, budget_id, "budget")


@router.get("/goals")
def goals(*, store: DB, context: CTX):
    return list_goals(store, context)


@router.post("/goals")
def goal_create(*, payload: GoalInput, store: DB, context: CTX):
    return save_goal(store, context, payload)


@router.put("/goals/{goal_id}")
def goal_update(*, goal_id: str, payload: GoalInput, store: DB, context: CTX):
    return save_goal(store, context, payload, goal_id)


@router.put("/goals/{goal_id}/allocations")
def goal_allocate(*, goal_id: str, payload: AllocationInput, store: DB, context: CTX):
    return allocate_goal(store, context, goal_id, payload)


@router.delete("/goals/{goal_id}")
def goal_delete(*, goal_id: str, store: DB, context: CTX):
    return archive_plan(store, context, goal_id, "goal")


@router.get("/bills")
def bills(*, store: DB, context: CTX):
    return list_bills(store, context)


@router.post("/bills")
def bill_create(*, payload: BillInput, store: DB, context: CTX):
    return save_bill(store, context, payload)


@router.put("/bills/{bill_id}")
def bill_update(*, bill_id: str, payload: BillInput, store: DB, context: CTX):
    return save_bill(store, context, payload, bill_id)


@router.delete("/bills/{bill_id}")
def bill_delete(*, bill_id: str, store: DB, context: CTX):
    return archive_plan(store, context, bill_id, "bill")


@router.post("/bills/{bill_id}/pause")
def bill_pause(*, bill_id: str, payload: PauseInput, store: DB, context: CTX):
    return pause_bill(store, context, bill_id, payload.paused)


@router.post("/bills/{bill_id}/skip")
def bill_skip(*, bill_id: str, store: DB, context: CTX):
    return record_occurrence(store, context, bill_id, None, False)


@router.post("/bills/{bill_id}/pay")
def bill_pay(*, bill_id: str, payload: PayInput, store: DB, context: CTX):
    return record_occurrence(store, context, bill_id, payload.due_date, True)


@router.get("/scenarios/templates")
def templates(*, currency: str = "USD", context: CTX):
    return scenario_templates(currency)


@router.post("/scenarios/calculate")
def scenario_calculate(*, payload: ScenarioInput, context: CTX):
    return {**calculate_scenario(payload.inputs), "evidence": evidence("calculated", "Scenario calculated from recorded assumptions")}


@router.get("/scenarios/compare")
def scenario_compare(*, before_id: str, after_id: str, store: DB, context: CTX):
    return compare_scenarios(store, context, before_id, after_id)


@router.get("/scenarios")
def scenarios(*, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), store: DB, context: CTX):
    return list_scenarios(store, context, limit, offset)


@router.post("/scenarios")
def scenario_create(*, payload: ScenarioInput, store: DB, context: CTX):
    return save_scenario(store, context, payload)


@router.get("/scenarios/{scenario_id}")
def scenario_get(*, scenario_id: str, store: DB, context: CTX):
    return get_scenario(store, context, scenario_id)
