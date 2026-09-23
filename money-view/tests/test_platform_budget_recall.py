"""Exact budget recall keeps the saved month and household boundary."""
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from platform_identity_factory import identity_context
from server.platform import ledger, planning
from server.platform.common import PlatformError, get_context, get_store
from server.platform.ledger_contracts import AccountCreate, TransactionCreate
from server.platform.planning_contracts import BudgetInput
from server.store import Store


@pytest.fixture
def budget_recall(tmp_path):
    store = Store(tmp_path / "budget-recall.sqlite")
    context = identity_context(store)
    ledger.initialize(store)
    planning.initialize(store)
    account = ledger.create_account(AccountCreate(name="Household reserve", kind="savings", currency="EUR", opening_balance="500", idempotency_key="recall-account"), store, context)
    month = "2024-02"
    budget = planning.save_budget(store, context, BudgetInput(category="groceries", currency=account["currency"], month=month, limit="100"))
    ledger.record_transaction(store, context, TransactionCreate(account_id=account["id"], date=date.fromisoformat(month + "-12"), merchant="Market", amount="-25", category="groceries", idempotency_key="recall-spend"))
    app = FastAPI()
    app.include_router(planning.router)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_context] = lambda: context

    @app.exception_handler(PlatformError)
    async def platform_error(request, error):
        return JSONResponse({"error": error.code}, status_code=error.status)

    return store, context, budget, app, TestClient(app)


def test_exact_budget_uses_saved_month_and_canonical_projection(budget_recall):
    store, context, budget, app, client = budget_recall
    app.dependency_overrides[get_context] = lambda: identity_context(store, user_id="recall-viewer", household_id=context.household_id, role="viewer")
    result = client.get(f"/api/platform/budgets/{budget['id']}")
    assert result.status_code == 200
    recalled = result.json()
    listed = next(item for item in planning.list_budgets(store, context, budget["month"])["items"] if item["id"] == budget["id"])
    for field in ("id", "category", "currency", "month", "limit", "actual", "remaining", "input_evidence"):
        assert recalled[field] == listed[field]
    assert recalled["actual"] == "25.00"
    assert recalled["remaining"] == "75.00"
    assert recalled["evidence"]["inputs"] == [recalled["input_evidence"]["id"], recalled["actual_evidence"]["id"]]
    assert not any(item["id"] == budget["id"] for item in planning.list_budgets(store, context, "2026-09")["items"])


@pytest.mark.parametrize("unavailable", ["foreign", "archived", "missing"])
def test_exact_budget_does_not_reveal_unavailable_records(budget_recall, unavailable):
    store, context, budget, app, client = budget_recall
    record_id = budget["id"]
    if unavailable == "foreign":
        app.dependency_overrides[get_context] = lambda: identity_context(store, user_id="other-reader", household_id="other-household")
    elif unavailable == "archived":
        planning.archive_plan(store, context, record_id, "budget")
    else:
        record_id = "missing-budget"
    response = client.get(f"/api/platform/budgets/{record_id}")
    assert response.status_code == 404
    assert response.json() == {"error": "planning_record_not_found"}
