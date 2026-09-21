"""Planning behavioral acceptance and canonical ledger integration."""
import json
import sqlite3
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError
from server.platform import planning
from server.platform.common import Context, PlatformError
from server.platform.ledger_contracts import CATEGORIES
from server.platform.planning_contracts import (
    AllocationInput,
    BillInput,
    BudgetInput,
    GoalInput,
    ScenarioInput,
    ScenarioInputs,
)
from server.store import Store


@pytest.fixture
def context():
    return Context("user-test", "household-test", "owner", "session-test")


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path / "planning.sqlite")
    planning.initialize(result)
    return result


@pytest.mark.parametrize("anchor,cadence,after,expected", [
    ("2026-01-31", "monthly", "2026-01-31", "2026-02-28"),
    ("2026-01-31", "monthly", "2026-02-28", "2026-03-31"),
    ("2024-02-29", "yearly", "2027-02-28", "2028-02-29"),
    ("2026-01-31", "quarterly", "2026-04-30", "2026-07-31"),
    ("2026-12-28", "weekly", "2026-12-28", "2027-01-04"),
])
def test_recurrence_keeps_calendar_anchor(anchor, cadence, after, expected):
    assert planning.next_occurrence(date.fromisoformat(anchor), cadence, date.fromisoformat(after)).isoformat() == expected


@pytest.mark.parametrize("timing", ["begin", "end"])
def test_zero_rates_cash_flow_windows_and_depletion(timing):
    result = planning.calculate_scenario(ScenarioInputs(currency="USD", initial_balance="100", monthly_contribution="10", contribution_end_month=2, monthly_withdrawal="50", withdrawal_start_month=3, horizon_years=1, timing=timing))
    assert result["months"][1]["balance"] == "120.00"
    assert result["depletion_month"] == 5
    assert result["months"][4]["unfunded_withdrawal"] == "30.00"
    assert result["total_contributions"] == "20.00"
    assert result["total_withdrawals"] == "120.00"
    assert result["ending_balance"] == result["real_ending_balance"] == "0.00"


def test_effective_annual_return_inflation_fees_and_timing():
    result = planning.calculate_scenario(ScenarioInputs(currency="USD", initial_balance="100", annual_return_pct="10", inflation_pct="10", horizon_years=1))
    assert result["ending_balance"] == "110.00"
    assert result["real_ending_balance"] == "100.00"
    base = dict(currency="USD", monthly_contribution="100", annual_return_pct="10", annual_fee_pct="1", horizon_years=1)
    begin = planning.calculate_scenario(ScenarioInputs(**base, timing="begin"))
    end = planning.calculate_scenario(ScenarioInputs(**base, timing="end"))
    assert Decimal(begin["ending_balance"]) > Decimal(end["ending_balance"])
    assert Decimal(begin["total_fees"]) > 0
    negative = planning.calculate_scenario(ScenarioInputs(currency="USD", initial_balance="100", annual_return_pct="-50", inflation_pct="-10", horizon_years=1))
    assert negative["ending_balance"] == "50.00"
    assert Decimal(negative["real_ending_balance"]) > Decimal(negative["ending_balance"])


@pytest.mark.parametrize("change", [{"initial_balance": "-1"}, {"monthly_contribution": "-1"}, {"annual_return_pct": "-100"}, {"inflation_pct": "NaN"}, {"horizon_years": 101}, {"withdrawal_start_month": 3, "withdrawal_end_month": 2}])
def test_scenario_boundary_rejects_invalid_assumptions(change):
    with pytest.raises((ValidationError, PlatformError)):
        ScenarioInputs(currency="USD", **change)


def test_saved_receipts_are_immutable_and_household_scoped(store, context):
    payload = ScenarioInput(name="Baseline", template="retirement", inputs=ScenarioInputs(currency="USD", initial_balance="100", horizon_years=1))
    before = planning.save_scenario(store, context, payload)
    after = planning.save_scenario(store, context, payload.model_copy(update={"inputs": payload.inputs.model_copy(update={"annual_return_pct": Decimal("10")})}))
    comparison = planning.compare_scenarios(store, context, before["id"], after["id"])
    assert comparison["delta_ending_balance"] == "10.00"
    assert planning.get_scenario(store, context, before["id"]) == before
    with store.connection(write=True) as connection, pytest.raises(sqlite3.IntegrityError, match="immutable_scenario"):
        connection.execute("UPDATE p_scenarios SET document=? WHERE id=?", (json.dumps(after), before["id"]))
    other = Context("user-other", "household-other", "owner", "session-other")
    with pytest.raises(PlatformError, match="scenario_not_found"):
        planning.get_scenario(store, other, before["id"])


def test_plan_edits_and_viewer_guard_and_reset_survives_restart(store, context):
    payload = GoalInput(name="Reserve", target_date=date(2028, 1, 1), target_amount="1000", currency="USD")
    goal = planning.save_goal(store, context, payload)
    updated = planning.save_goal(store, context, payload.model_copy(update={"target_amount": Decimal("2000")}), goal["id"])
    assert updated["target_amount"] == "2000"
    viewer = Context(context.user_id, context.household_id, "viewer", context.session_id)
    with pytest.raises(PlatformError, match="read_only_household"):
        planning.save_goal(store, viewer, payload)
    demo = Context("user-demo", "household-demo", "owner", "session-demo")
    with store.connection(write=True) as connection:
        planning.clear_data(connection, demo)
    planning.initialize(store)
    assert planning.list_scenarios(store, demo)["items"] == []


def test_templates_all_use_same_calculator():
    templates = planning.scenario_templates("DOP")["items"]
    assert len(templates) == 7
    for template in templates:
        result = planning.calculate_scenario(ScenarioInputs.model_validate(template["inputs"]))
        assert len(result["months"]) == template["inputs"]["horizon_years"] * 12
        assert result["currency"] == "DOP"


@pytest.fixture
def ledger_store(tmp_path):
    from server.platform import ledger
    result = Store(tmp_path / "ledger-planning.sqlite")
    ledger.initialize(result)
    planning.initialize(result)
    return result


@pytest.fixture
def accounts(ledger_store, context):
    from server.platform.ledger import create_account
    from server.platform.ledger_contracts import AccountCreate
    return [create_account(AccountCreate(name="Reserve " + currency, kind="savings", currency=currency, opening_balance="1000", idempotency_key="reserve-" + currency), ledger_store, context) for currency in ("USD", "EUR")]


def test_goals_reserve_live_ledger_balances_and_release_on_archive(ledger_store, context, accounts):
    from server.platform import ledger
    from server.platform.ledger_contracts import TransactionCreate
    payload = GoalInput(name="Reserve", target_date=date(2028, 1, 1), target_amount="1000", currency="USD")
    first, second = [planning.save_goal(ledger_store, context, payload) for _ in range(2)]
    allocation = AllocationInput(allocations=[{"account_id": accounts[0]["id"], "amount": "700"}])
    result = planning.allocate_goal(ledger_store, context, first["id"], allocation)
    assert result["allocated"] == "700.00"
    with pytest.raises(PlatformError, match="allocation_exceeds_balance"):
        planning.allocate_goal(ledger_store, context, second["id"], allocation)
    with pytest.raises(PlatformError, match="allocation_currency_mismatch"):
        planning.allocate_goal(ledger_store, context, second["id"], AllocationInput(allocations=[{"account_id": accounts[1]["id"], "amount": "100"}]))
    ledger.record_transaction(ledger_store, context, TransactionCreate(account_id=accounts[0]["id"], date=date(2026, 9, 20), merchant="Market", amount="-400", category="groceries", idempotency_key="groceries-test"))
    changed = next(item for item in planning.list_goals(ledger_store, context)["items"] if item["id"] == first["id"])
    assert changed["allocations"][0]["underfunded"] is True
    assert changed["allocations"][0]["account_balance"] == "600.00"
    planning.archive_plan(ledger_store, context, first["id"], "goal")
    released = planning.allocate_goal(ledger_store, context, second["id"], AllocationInput(allocations=[{"account_id": accounts[0]["id"], "amount": "600"}]))
    assert released["allocated"] == "600.00"
    ledger.set_account_deleted(ledger_store, context, accounts[0]["id"], True)
    changed = planning.list_goals(ledger_store, context)["items"][0]
    assert changed["allocations"][0]["account_unavailable"] is True


def test_bill_payment_is_atomic_idempotent_and_updates_budget(ledger_store, context, accounts):
    from server.platform import ledger
    budget = planning.save_budget(ledger_store, context, BudgetInput(currency="USD", category="utilities", month="2026-09", limit="100"))
    bill = planning.save_bill(ledger_store, context, BillInput(name="Utilities", account_id=accounts[0]["id"], category="utilities", currency="USD", amount="90", anchor_date=date(2026, 9, 30)))
    before = ledger.account_balances(ledger_store, context, "USD")[0]
    first = planning.record_occurrence(ledger_store, context, bill["id"], date(2026, 9, 30), True)
    repeated = planning.record_occurrence(ledger_store, context, bill["id"], date(2026, 9, 30), True)
    assert first == repeated
    after = ledger.account_balances(ledger_store, context, "USD")[0]
    assert Decimal(before["balance"]) - Decimal(after["balance"]) == Decimal("90")
    actual = planning.list_budgets(ledger_store, context, "2026-09")["items"][0]
    assert Decimal(actual["actual"]) == 90 and Decimal(actual["remaining"]) == 10
    assert actual["id"] == budget["id"]
    assert planning.list_bills(ledger_store, context)["items"][0]["next_due"] == "2026-10-30"
    planning.pause_bill(ledger_store, context, bill["id"], True)
    with pytest.raises(PlatformError, match="bill_not_active"):
        planning.record_occurrence(ledger_store, context, bill["id"], date(2026, 10, 30), True)
    planning.pause_bill(ledger_store, context, bill["id"], False)
    skipped = planning.record_occurrence(ledger_store, context, bill["id"], None, False)
    assert skipped["status"] == "skipped"
    assert ledger.account_balances(ledger_store, context, "USD")[0]["balance"] == after["balance"]


def test_duplicate_budget_and_invalid_currency_precision(ledger_store, context):
    budget = BudgetInput(currency="USD", category="groceries", month="2026-09", limit="100")
    planning.save_budget(ledger_store, context, budget)
    with pytest.raises(PlatformError, match="budget_already_exists"):
        planning.save_budget(ledger_store, context, budget)
    with pytest.raises(PlatformError, match="invalid_money_precision"):
        BudgetInput(currency="USD", category="groceries", month="2026-09", limit="1.001")


def test_failed_occurrence_rolls_back_ledger_and_schedule(ledger_store, context, accounts):
    from server.platform import ledger
    bill = planning.save_bill(ledger_store, context, BillInput(name="Last date", account_id=accounts[0]["id"], category="utilities", currency="USD", amount="50", anchor_date=date(9999, 12, 31)))
    before = ledger.account_balances(ledger_store, context, "USD")[0]["balance"]
    with pytest.raises(PlatformError, match="schedule_date_out_of_range"):
        planning.record_occurrence(ledger_store, context, bill["id"], date(9999, 12, 31), True)
    assert ledger.account_balances(ledger_store, context, "USD")[0]["balance"] == before
    with ledger_store.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM p_bill_occurrences WHERE bill_id=?", (bill["id"],)).fetchone()[0] == 0


def test_http_scenario_and_role_boundary(store, context):
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient
    from server.platform.common import get_context, get_store
    app = FastAPI()
    app.include_router(planning.router)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_context] = lambda: context
    @app.exception_handler(PlatformError)
    async def platform_error(request, error):
        return JSONResponse({"error": error.code}, status_code=error.status)
    client = TestClient(app)
    payload = {"name": "Baseline", "template": "home", "inputs": {"currency": "USD", "initial_balance": "100", "horizon_years": 1}}
    calculated = client.post("/api/platform/scenarios/calculate", json=payload)
    assert calculated.status_code == 200
    assert calculated.json()["evidence"]["kind"] == "calculated"
    saved = client.post("/api/platform/scenarios", json=payload)
    assert saved.status_code == 200
    receipt = saved.json()
    assert client.get("/api/platform/scenarios/" + receipt["id"]).json() == receipt
    assert client.put("/api/platform/scenarios/" + receipt["id"], json=payload).status_code == 405
    app.dependency_overrides[get_context] = lambda: Context(context.user_id, context.household_id, "viewer", context.session_id)
    listed = client.get("/api/platform/scenarios?limit=1&offset=0")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1 and listed.json()["limit"] == 1
    assert "months" not in listed.json()["items"][0]["result"]
    assert client.get("/api/platform/scenarios?limit=101").status_code == 422
    assert client.post("/api/platform/scenarios", json=payload).status_code == 403


def test_extreme_valid_assumptions_stay_finite_and_currency_precision():
    result = planning.calculate_scenario(ScenarioInputs(currency="USD", initial_balance="1000000000000", horizon_years=100, annual_return_pct="100", inflation_pct="-99"))
    assert Decimal(result["real_ending_balance"]).is_finite()
    for currency, expected in (("JPY", "100"), ("KWD", "100.000")):
        result = planning.calculate_scenario(ScenarioInputs(currency=currency, initial_balance="100", horizon_years=1))
        assert result["ending_balance"] == expected


@pytest.mark.parametrize("category", [key for key, kind in CATEGORIES.items() if kind != "expense"])
@pytest.mark.parametrize("model,values", [
    (BudgetInput, {"month": "2026-09", "limit": "100"}),
    (BillInput, {"name": "Utilities", "account_id": "account-test", "amount": "90", "anchor_date": "2026-09-30"}),
])
def test_bills_and_budgets_reject_nonexpense_categories(category, model, values):
    with pytest.raises(ValidationError, match="invalid_category"):
        model(currency="USD", category=category, **values)


def test_saved_scenario_list_pages_compact_summaries_and_keeps_full_details(store, context):
    payload = ScenarioInput(name="Long horizon", template="retirement", inputs=ScenarioInputs(currency="USD", initial_balance="100", horizon_years=100))
    receipts = [planning.save_scenario(store, context, payload) for _ in range(5)]
    other = Context("user-other", "household-other", "owner", "session-other")
    planning.save_scenario(store, other, payload)
    pages = [planning.list_scenarios(store, context, limit=2, offset=offset) for offset in (0, 2, 4)]
    assert [item["id"] for page in pages for item in page["items"]] == [receipt["id"] for receipt in reversed(receipts)]
    for offset, page in zip((0, 2, 4), pages, strict=True):
        assert page["total"] == len(receipts)
        assert page["limit"] == 2 and page["offset"] == offset
        for summary in page["items"]:
            assert "months" not in summary["result"] and "years" not in summary["result"]
    assert planning.list_scenarios(store, context, limit=2, offset=6)["items"] == []
    selected = planning.get_scenario(store, context, pages[0]["items"][0]["id"])
    assert selected == receipts[-1]
    assert len(selected["result"]["months"]) == payload.inputs.horizon_years * 12
    assert len(json.dumps(pages[0])) < len(json.dumps(selected)) / 10


@pytest.mark.parametrize("limit,offset", [(0, 0), (101, 0), (20, -1)])
def test_saved_scenario_page_bounds(store, context, limit, offset):
    with pytest.raises(PlatformError, match="invalid_scenario_page"):
        planning.list_scenarios(store, context, limit, offset)
