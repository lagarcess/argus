"""Captured domain writes cannot repopulate reset or deleted household state."""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from server.platform import identity as identity_module
from server.platform import ledger, planning, services
from server.platform.common import PlatformError, get_context
from server.platform.identity import COOKIE, DEMO_PASSWORD, Identity
from server.store import Store

CREATE_CASES = [
    pytest.param(
        "/accounts",
        "p_accounts",
        {
            "name": "New reserve",
            "kind": "savings",
            "currency": "USD",
            "opening_balance": "100",
            "idempotency_key": "lifecycle-account",
        },
        id="ledger",
    ),
    pytest.param(
        "/budgets",
        "p_plans",
        {"category": "groceries", "currency": "USD", "month": "2026-09", "limit": "100"},
        id="planning",
    ),
    pytest.param(
        "/membership",
        "p_service_memberships",
        {"plan_id": "monthly", "request_key": "lifecycle-membership"},
        id="services",
    ),
    pytest.param(
        "/credit/accounts",
        "p_credit_accounts",
        {
            "name": "Local card",
            "currency": "USD",
            "balance": "100",
            "credit_limit": "1000",
            "apr_pct": "10",
            "minimum_payment": "10",
            "as_of": "2026-09-20",
        },
        id="credit",
    ),
    pytest.param(
        "/tax/organizers",
        "p_tax_organizers",
        {"country": "DO", "currency": "DOP", "year": 2026},
        id="tax-estate",
    ),
]


@pytest.fixture
def client(tmp_path):
    store = Store(tmp_path / "domain-lifecycle.sqlite")
    identity = Identity(store)
    identity.initialize()
    ledger.initialize(store)
    planning.initialize(store)
    services.initialize(store)
    for name, domain in (
        ("planning", planning),
        ("ledger", ledger),
        ("services", services),
    ):
        identity.register_data_domain(
            name,
            export=domain.export_data,
            clear=domain.clear_data,
            usage=domain.usage_data,
        )
    app = FastAPI()
    app.state.store, app.state.identity = store, identity
    for router in (
        identity_module.router,
        ledger.router,
        planning.router,
        services.router,
    ):
        app.include_router(router)

    @app.exception_handler(PlatformError)
    async def platform_error(_, error):
        return JSONResponse({"code": error.code}, status_code=error.status)

    with TestClient(app) as browser:
        result = browser.post(
            "/api/platform/session/login",
            json={"user_id": "user-other", "password": DEMO_PASSWORD},
        )
        assert result.status_code == 200
        yield browser


def authenticated_context(client):
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", f"{COOKIE}={client.cookies.get(COOKIE)}".encode())],
        }
    )
    return client.app.state.identity.context(request)


def count_records(client, table, household_id):
    with client.app.state.store.connection() as db:
        return db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE household_id=?", (household_id,)
        ).fetchone()[0]


@pytest.mark.parametrize("path,table,body", CREATE_CASES)
@pytest.mark.parametrize(
    "change,code,status",
    [
        ("reset", "household_data_changed", 409),
        ("delete", "authentication_required", 401),
    ],
)
def test_captured_context_cannot_repopulate_cleared_domain(
    client, path, table, body, change, code, status
):
    captured = authenticated_context(client)
    if change == "reset":
        cleared = client.post(
            "/api/platform/settings/data/reset",
            json={"confirmation": "RESET THIS HOUSEHOLD"},
        )
    else:
        cleared = client.request(
            "DELETE",
            "/api/platform/settings/account",
            json={
                "confirmation": "DELETE MY LOCAL ACCOUNT",
                "current_password": DEMO_PASSWORD,
            },
        )
    assert cleared.status_code == 200, cleared.text
    before = count_records(client, table, captured.household_id)
    # Reuse an actually authenticated request's captured context to model a
    # handler admitted before the clear; the domain guard itself remains real.
    client.app.dependency_overrides[get_context] = lambda: captured
    rejected = client.post("/api/platform" + path, json=body)
    assert rejected.status_code == status, rejected.text
    assert rejected.json()["code"] == code
    assert count_records(client, table, captured.household_id) == before
    if change == "reset":
        fresh = authenticated_context(client)
        assert fresh.data_generation == captured.data_generation + 1
        client.app.dependency_overrides[get_context] = lambda: fresh
        accepted = client.post("/api/platform" + path, json=body)
        assert accepted.status_code == 200, accepted.text
        assert count_records(client, table, captured.household_id) == before + 1
