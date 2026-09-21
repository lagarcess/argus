"""Service journeys prove durable state, exact arithmetic, isolation and local downloads."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from platform_identity_factory import identity_context
from server.platform import services
from server.platform.common import PlatformError, get_context, get_store
from server.platform.credit import calculate_payoff
from server.store import Store


@pytest.fixture
def api(tmp_path, monkeypatch):
    store = Store(tmp_path / "services.sqlite")
    monkeypatch.setattr(
        services, "now", lambda: datetime(2026, 9, 20, tzinfo=timezone.utc)
    )
    context = identity_context(store)
    services.initialize(store)
    app = FastAPI()
    state = {"context": context, "store": store}
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_context] = lambda: state["context"]

    @app.exception_handler(PlatformError)
    async def platform_error(request, error):
        return JSONResponse({"error": error.code}, status_code=error.status)

    app.include_router(services.router)
    with TestClient(app) as client:
        yield client, store, state


def switch(state, household="household-other", role="owner"):
    user_id = (
        "user-viewer"
        if role == "viewer"
        else "user-other"
        if household == "household-other"
        else "user-demo"
    )
    state["context"] = identity_context(
        state["store"], user_id=user_id, household_id=household, role=role
    )


def account(balance="100", apr="0", minimum="10", currency="USD"):
    return {
        "id": "example",
        "balance": balance,
        "apr_pct": apr,
        "minimum_payment": minimum,
        "currency": currency,
        "as_of": "2026-09-18",
    }


@pytest.mark.parametrize(
    "balance,apr,minimum,extra,status,months,paid",
    [
        ("100", "0", "10", "0", "paid_off", 10, "100"),
        ("100", "12", "101", "0", "paid_off", 1, "101.00"),
        ("100", "12", "1", "0", "non_amortizing", None, "0"),
        ("0", "12", "0", "0", "paid_off", 0, "0"),
        ("100", "0", "0", "25", "paid_off", 4, "100"),
        ("100", "0", "0", "0", "non_amortizing", None, "0"),
        ("100000", "0", "1", "0", "horizon_exceeded", None, "1200"),
    ],
)
def test_payoff_arithmetic(balance, apr, minimum, extra, status, months, paid):
    result = calculate_payoff(account(balance, apr, minimum), Decimal(extra))
    assert (result["status"], result["months"], Decimal(result["total_paid"])) == (
        status,
        months,
        Decimal(paid),
    )


def test_credit_update_utilization_scope_and_precision(api):
    client, store, state = api
    result = client.get("/api/platform/credit").json()
    assert result["report"]["evidence"]["kind"] == "synthetic"
    assert result["utilization"][0]["utilization_pct"] == "20.68"
    assert (
        client.post(
            "/api/platform/credit/payoff",
            json={"account_id": "credit-demo", "extra_monthly_payment": "50"},
        ).json()["status"]
        == "paid_off"
    )
    body = {
        "name": "Zero limit",
        "currency": "USD",
        "balance": "100",
        "credit_limit": "0",
        "apr_pct": "0",
        "minimum_payment": "10",
        "as_of": "2026-09-20",
    }
    switch(state)
    item = client.post("/api/platform/credit/accounts", json=body).json()
    assert (
        client.get("/api/platform/credit").json()["utilization"][0]["utilization_pct"]
        is None
    )
    assert (
        client.post(
            "/api/platform/credit/payoff", json={"account_id": "credit-demo"}
        ).status_code
        == 404
    )
    body["balance"] = "101"
    assert (
        client.put(f"/api/platform/credit/accounts/{item['id']}", json=body).json()[
            "balance"
        ]
        == "101"
    )
    assert (
        client.post(
            "/api/platform/credit/accounts", json={**body, "balance": "1.001"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/platform/credit/accounts", json={**body, "currency": "ZZZ"}
        ).status_code
        == 422
    )


def test_tax_complete_export_scenario_and_record_dates(api):
    client, store, state = api
    base = "/api/platform/tax"
    assert (
        client.patch(
            f"{base}/organizers/tax-demo", json={"status": "complete"}
        ).status_code
        == 409
    )
    item = client.post(
        f"{base}/items",
        json={
            "organizer_id": "tax-demo",
            "kind": "expense",
            "title": "=EXEC()",
            "amount": "100",
            "effective_on": "2026-09-20",
        },
    ).json()
    assert item["effective_on"] == "2026-09-20" and item["recorded_at"]
    result = client.post(
        f"{base}/scenario", json={"organizer_id": "tax-demo", "user_rate_pct": "10"}
    ).json()
    assert result["scenario_amount"] == "2240.00"
    assert result["legal_status"] == "worksheet_only"
    assert "'=EXEC()" in client.get(f"{base}/organizers/tax-demo/export?format=csv").text
    assert (
        client.get(f"{base}/organizers/tax-demo/export").json()["organizer"]["country"]
        == "DO"
    )
    assert (
        client.patch(f"{base}/items/document-demo", json={"completed": True}).status_code
        == 200
    )
    assert (
        client.patch(f"{base}/organizers/tax-demo", json={"status": "complete"}).json()[
            "status"
        ]
        == "complete"
    )
    assert (
        client.patch(f"{base}/items/document-demo", json={"completed": False}).status_code
        == 409
    )
    assert (
        client.patch(f"{base}/organizers/tax-demo", json={"status": "open"}).status_code
        == 200
    )
    wrong_year = {
        "organizer_id": "tax-demo",
        "kind": "document",
        "title": "Record",
        "effective_on": "2025-01-01",
    }
    assert client.post(f"{base}/items", json=wrong_year).status_code == 422
    assert (
        client.post(f"{base}/scenario", json={"organizer_id": "tax-demo"}).status_code
        == 422
    )
    switch(state)
    assert client.get(f"{base}/organizers/tax-demo/export").status_code == 404
    first = client.post(
        f"{base}/organizers", json={"country": "DO", "year": 2026, "currency": "DOP"}
    ).json()
    assert (
        client.post(
            f"{base}/organizers", json={"country": "DO", "year": 2026, "currency": "DOP"}
        ).json()
        == first
    )


def test_estate_beneficiary_atomic_validation_and_exports(api):
    client, store, state = api
    base = "/api/platform/estate"
    endpoint = f"{base}/assets/asset-demo/beneficiaries"
    body = {"shares": [{"contact_id": "contact-demo", "share_pct": "100"}]}
    assert client.put(endpoint, json=body).json()["allocated_pct"] == "100"
    assert (
        client.put(
            endpoint,
            json={"shares": [{"contact_id": "contact-demo", "share_pct": "101"}]},
        ).status_code
        == 422
    )
    assert client.put(endpoint, json={"shares": body["shares"] * 2}).status_code == 422
    assert (
        client.put(
            endpoint, json={"shares": [{"contact_id": "missing", "share_pct": "50"}]}
        ).status_code
        == 404
    )
    assert client.get(base).json()["beneficiaries"][0]["allocated_pct"] == "100"
    assert (
        client.post(
            f"{base}/documents",
            json={
                "title": "Insurance",
                "location": "@SUM(A1)",
                "effective_on": "2026-09-20",
            },
        ).status_code
        == 200
    )
    assert "'@SUM(A1)" in client.get(f"{base}/export?format=csv").text
    assert (
        client.get(f"{base}/export").json()["legal_status"]
        == "inventory_only_no_legal_validity"
    )
    assert client.patch(
        f"{base}/checklist/checklist-demo", json={"completed": True}
    ).json()["completed"]
    switch(state)
    assert client.put(endpoint, json=body).status_code == 404
    assert client.get(base).json()["assets"] == []


def test_reservation_idempotency_global_conflict_reschedule_cancel_calendar(api):
    client, store, state = api
    base = "/api/platform/appointments"
    body = {"slot_id": "slot-demo-20260921T1400", "request_key": "reserve-one"}
    first = client.post(base, json=body).json()
    assert client.post(base, json=body).json()["id"] == first["id"]
    assert (
        client.post(base, json={**body, "slot_id": "slot-demo-20260921T1500"}).status_code
        == 409
    )
    switch(state)
    assert (
        client.post(
            base, json={"slot_id": "slot-demo-20260921T1400", "request_key": "other"}
        ).status_code
        == 409
    )
    assert client.get(f"{base}/{first['id']}/calendar").status_code == 404
    assert client.get(base).json()["reservations"] == []
    switch(state, "household-demo")
    path = f"{base}/{first['id']}"
    assert (
        client.patch(path, json={"slot_id": "slot-demo-20260921T1500"}).json()["slot_id"]
        == "slot-demo-20260921T1500"
    )
    assert client.post(base, json=body).json()["slot_id"] == "slot-demo-20260921T1500"
    calendar = client.get(f"{path}/calendar")
    assert (
        "BEGIN:VCALENDAR" in calendar.text and "Local demonstration only" in calendar.text
    )
    assert "ATTENDEE" not in calendar.text and "ORGANIZER" not in calendar.text
    assert client.post(f"{path}/cancel").json()["status"] == "cancelled"
    assert client.post(f"{path}/cancel").json()["status"] == "cancelled"
    assert (
        client.patch(path, json={"slot_id": "slot-demo-20260922T1400"}).status_code == 409
    )
    assert "STATUS:CANCELLED" in client.get(f"{path}/calendar").text
    assert (
        client.post(
            base, json={"slot_id": "slot-demo-20260921T1500", "request_key": "new"}
        ).status_code
        == 200
    )


def test_membership_and_employer_journeys_persist(api):
    client, store, state = api
    base = "/api/platform"
    body = {"plan_id": "annual", "request_key": "membership-one"}
    result = client.post(f"{base}/membership", json=body).json()
    assert result["receipt"]["status"] == "simulated_no_charge"
    assert (
        client.post(f"{base}/membership", json=body).json()["receipt"]["id"]
        == result["receipt"]["id"]
    )
    assert (
        client.post(f"{base}/membership", json={**body, "plan_id": "monthly"}).status_code
        == 409
    )
    assert len(client.get(f"{base}/membership").json()["receipts"]) == 1
    assert (
        client.post(f"{base}/membership/cancel").json()["membership"]["status"]
        == "cancelled"
    )
    assert (
        client.post(f"{base}/employer/enroll", json={"code": "REAL-EMPLOYER"}).status_code
        == 422
    )
    assert (
        client.post(f"{base}/employer/enroll", json={"code": "CLARA-DEMO"}).json()[
            "status"
        ]
        == "enrolled"
    )
    assert (
        client.put(f"{base}/employer/benefit", json={"benefit_id": "learning"}).json()[
            "benefit_id"
        ]
        == "learning"
    )
    services.initialize(store)
    assert client.get(f"{base}/employer").json()["enrollment"]["benefit_id"] == "learning"
    assert client.post(f"{base}/employer/leave").json()["enrollment"]["status"] == "left"
    assert (
        client.put(
            f"{base}/employer/benefit", json={"benefit_id": "planning"}
        ).status_code
        == 409
    )
    switch(state)
    assert client.get(f"{base}/membership").json()["receipts"] == []
    assert client.get(f"{base}/employer").json()["enrollment"] is None


@pytest.mark.parametrize(
    "method,path,body",
    [
        (
            "post",
            "/credit/accounts",
            {
                "name": "Card",
                "balance": "0",
                "credit_limit": "100",
                "minimum_payment": "0",
                "apr_pct": "0",
                "as_of": "2026-09-20",
            },
        ),
        ("post", "/tax/organizers", {"country": "US", "year": 2026}),
        ("patch", "/tax/items/document-demo", {"completed": True}),
        (
            "post",
            "/estate/assets",
            {"name": "Savings", "value": "1", "as_of": "2026-09-20"},
        ),
        ("put", "/estate/assets/asset-demo/beneficiaries", {"shares": []}),
        (
            "post",
            "/appointments",
            {"slot_id": "slot-demo-20260921T1400", "request_key": "viewer"},
        ),
        ("post", "/membership", {"plan_id": "monthly", "request_key": "viewer"}),
        ("post", "/membership/cancel", None),
        ("post", "/employer/enroll", {"code": "CLARA-DEMO"}),
    ],
)
def test_viewer_cannot_mutate(api, method, path, body):
    client, store, state = api
    switch(state, "household-demo", "viewer")
    assert client.request(method, f"/api/platform{path}", json=body).status_code == 403


def test_lifecycle_clears_only_household_and_does_not_reseed(api):
    client, store, state = api
    demo = state["context"]
    switch(state)
    client.post("/api/platform/employer/enroll", json={"code": "CLARA-DEMO"})
    with store.connection(write=True) as db:
        assert services.usage_data(db, demo)["service_records"] > 0
        assert services.export_data(db, demo)["p_credit_accounts"]
        services.clear_data(db, demo)
        assert services.usage_data(db, demo)["service_records"] == 0
        assert services.usage_data(db, state["context"])["service_records"] == 1
    services.initialize(store)
    switch(state, "household-demo")
    assert client.get("/api/platform/credit").json()["report"] is None


def test_identity_composition_membership_export_and_reset_preserve_authority(tmp_path):
    from server.platform.identity import DEMO_PASSWORD, Identity
    from server.platform.identity import router as identity_router

    store = Store(tmp_path / "composed.sqlite")
    identity = Identity(store)
    identity.initialize()
    services.initialize(store)
    identity.register_data_domain(
        "services",
        export=services.export_data,
        clear=services.clear_data,
        usage=services.usage_data,
    )
    app = FastAPI()
    app.state.store = store
    app.state.identity = identity
    app.include_router(identity_router)
    app.include_router(services.router)
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/platform/session/login",
                json={"user_id": "user-demo", "password": DEMO_PASSWORD},
            ).status_code
            == 200
        )
        assert client.get("/api/platform/membership").json()["membership"] is None
        subscribed = client.post(
            "/api/platform/membership",
            json={"plan_id": "annual", "request_key": "composed"},
        )
        assert subscribed.status_code == 200
        exported = client.get("/api/platform/settings/data/export")
        assert exported.status_code == 200
        assert (
            exported.json()["domains"]["services"]["p_service_memberships"][0]["plan_id"]
            == "annual"
        )
        with store.connection() as db:
            authority_before = [
                tuple(row)
                for row in db.execute(
                    "SELECT * FROM p_memberships ORDER BY household_id,user_id"
                )
            ]
        reset = client.post(
            "/api/platform/settings/data/reset",
            json={"confirmation": "RESET THIS HOUSEHOLD"},
        )
        assert reset.status_code == 200
        assert reset.json()["requires_login"] is False
        assert client.get("/api/platform/session").status_code == 200
        assert client.get("/api/platform/membership").json()["membership"] is None
        with store.connection() as db:
            assert [
                tuple(row)
                for row in db.execute(
                    "SELECT * FROM p_memberships ORDER BY household_id,user_id"
                )
            ] == authority_before
        identity.initialize()
        services.initialize(store)
        assert client.get("/api/platform/session").status_code == 200
        assert client.get("/api/platform/membership").json()["receipts"] == []


@pytest.mark.parametrize("restart", [False, True])
def test_future_slot_catalog_replenishes_without_changing_history(
    api, monkeypatch, restart
):
    client, store, state = api
    path = "/api/platform/appointments"
    initial = client.get(path).json()["slots"]
    old_slot = initial[0]
    original = client.post(
        path, json={"slot_id": old_slot["id"], "request_key": "historical"}
    ).json()
    advanced = datetime(2027, 1, 10, tzinfo=timezone.utc)
    monkeypatch.setattr(services, "now", lambda: advanced)
    if restart:
        services.initialize(store)
    catalog = client.get(path).json()
    future = [slot for slot in catalog["slots"] if slot["available"]]
    assert len(future) == 12
    assert all(datetime.fromisoformat(slot["starts_at"]) > advanced for slot in future)
    assert (
        next(slot for slot in catalog["slots"] if slot["id"] == old_slot["id"])[
            "starts_at"
        ]
        == old_slot["starts_at"]
    )
    assert catalog["reservations"] == [original]
    assert (
        client.post(
            path, json={"slot_id": future[0]["id"], "request_key": "new-date"}
        ).status_code
        == 200
    )
    switch(state)
    assert (
        client.post(
            path, json={"slot_id": future[0]["id"], "request_key": "other-household"}
        ).status_code
        == 409
    )
    with store.connection() as db:
        assert db.execute("SELECT count(*) FROM p_service_slots").fetchone()[0] == 13
    assert len(client.get(path).json()["slots"]) == 13


def test_old_membership_request_replay_is_historical_and_preserves_current(api):
    client, store, state = api
    path = "/api/platform/membership"
    annual = {"plan_id": "annual", "request_key": "request-A"}
    original = client.post(path, json=annual).json()
    changed = client.post(
        path, json={"plan_id": "monthly", "request_key": "request-B"}
    ).json()
    assert client.post(path, json=annual).json() == original
    assert client.get(path).json()["membership"] == changed["membership"]
    assert len(client.get(path).json()["receipts"]) == 2
    client.post(f"{path}/cancel")
    assert client.post(path, json=annual).json() == original
    assert client.get(path).json()["membership"]["status"] == "cancelled"


def test_tax_scenario_exposes_effective_recording_and_calculation_dates(api):
    client, store, state = api
    item = client.post(
        "/api/platform/tax/items",
        json={
            "organizer_id": "tax-demo",
            "kind": "income",
            "title": "Recorded income",
            "amount": "100",
            "effective_on": "2026-08-10",
        },
    ).json()
    result = client.post(
        "/api/platform/tax/scenario",
        json={"organizer_id": "tax-demo", "user_rate_pct": "15"},
    ).json()
    assert result["evidence"]["kind"] == "calculated"
    assert result["evidence"]["published_on"] is None
    assert result["evidence"]["as_of"] == item["effective_on"]
    assert set(result["evidence"]["inputs"]) == {
        "tax-demo",
        "income-demo",
        "expense-demo",
        item["id"],
    }
    recorded = next(
        source for source in result["source_records"] if source["id"] == item["id"]
    )
    assert recorded == {
        "id": item["id"],
        "effective_on": item["effective_on"],
        "recorded_at": item["recorded_at"],
        "kind": "user",
    }
    assert result["rate_evidence"]["kind"] == "user"
    assert result["rate_evidence"]["published_on"] is None
    assert result["rate_evidence"]["as_of"] == result["rate_evidence"]["recorded_at"][:10]


def test_beneficiary_allocation_keeps_its_actual_recording_date(api, monkeypatch):
    from server.platform import tax_estate

    client, store, state = api
    recorded = datetime(2026, 9, 22, 13, 42, tzinfo=timezone.utc)
    monkeypatch.setattr(tax_estate, "now", lambda: recorded)
    result = client.put(
        "/api/platform/estate/assets/asset-demo/beneficiaries",
        json={"shares": [{"contact_id": "contact-demo", "share_pct": "75"}]},
    ).json()
    assert result["recorded_at"] == recorded.isoformat()
    assert client.get("/api/platform/estate").json()["beneficiaries"][0] == result
