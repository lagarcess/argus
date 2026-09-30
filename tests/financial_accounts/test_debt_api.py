from uuid import uuid4

from faker import Faker

from financial_accounts.conftest import ALICE, BOB, GUEST


def test_debt_commands_plan_home_search_and_owner_boundary(client):
    fake = Faker()
    headers = {"Authorization": f"Bearer {ALICE}", "Idempotency-Key": str(uuid4())}
    ids = []
    for kind in ["cash", "other_debt"]:
        response = client.post(
            "/api/v1/financial-accounts",
            headers=headers | {"Idempotency-Key": str(uuid4())},
            json={
                "type": kind,
                "currency": "DOP",
                "amount": "1000",
                "as_of": "2026-09-01T12:00:00-04:00",
            },
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    name = fake.word() + " debt"
    body = {
        "debt_account_id": ids[1],
        "name": name,
        "source_account_id": ids[0],
        "amount": "350",
        "schedule": {"cadence": "monthly", "start_date": "2026-10-01"},
    }
    path = "/api/v1/financial-plan/debts"
    created = client.post(path, headers=headers, json=body)
    assert created.status_code == 201, created.text
    progress = created.json()["debt"]
    did = progress["debt"]["id"]
    assert progress["balance"]["amount_minor"] == -100000
    assert progress["payoff"]["reason"] == "terms_missing"
    assert client.post(path, headers=headers, json=body).json()["replayed"]
    for identity, status in [(BOB, 404), (GUEST, 403)]:
        assert (
            client.get(
                path + "/" + did, headers={"Authorization": f"Bearer {identity}"}
            ).status_code
            == status
        )
    plan = client.get("/api/v1/financial-plan", headers=headers)
    assert plan.status_code == 200, plan.text
    assert plan.json()["debts"][0]["debt"]["id"] == did
    home = client.get("/api/v1/financial-home", headers=headers)
    assert home.status_code == 200, home.text
    assert home.json()["debts"][0]["debt"]["id"] == did
    search = client.get(
        "/api/v1/financial-search", headers=headers, params={"kind": "debt", "q": name}
    )
    assert search.status_code == 200, search.text
    assert search.json()["items"][0]["debt"]["debt"]["id"] == did


def test_payment_and_actual_return_remain_readable_in_home_and_plan(client):
    headers = {"Authorization": f"Bearer {ALICE}"}
    accounts = []
    for kind in ["checking", "other_debt"]:
        response = client.post(
            "/api/v1/financial-accounts",
            headers=headers | {"Idempotency-Key": str(uuid4())},
            json={
                "type": kind,
                "currency": "DOP",
                "amount": "1000",
                "as_of": "2026-09-01T12:00:00-04:00",
            },
        )
        assert response.status_code == 201, response.text
        accounts.append(response.json())
    original = None
    for kind, total, principal, interest, fees in [
        ("debt_payment", "350", "300", "40", "10"),
        ("payment_reversal", "100", "80", "15", "5"),
    ]:
        body = {
            "kind": kind,
            "amount": total,
            "principal": principal,
            "interest": interest,
            "fees": fees,
            "occurred_at": "2026-09-02T12:00:00-04:00"
            if original is None
            else "2026-09-03T12:00:00-04:00",
            "source_account_id": accounts[0]["id"],
            "destination_account_id": accounts[1]["id"],
            "expected_versions": {a["id"]: a["version"] for a in accounts},
        }
        if original:
            body["reversal_of_activity_id"] = original
        preview = client.post(
            "/api/v1/financial-activities/preview", headers=headers, json=body
        )
        assert preview.status_code == 200, preview.text
        reviewed = preview.json()["reviewed_request"] | {
            "preview_token": preview.json()["preview_token"]
        }
        saved = client.post(
            "/api/v1/financial-activities",
            headers=headers | {"Idempotency-Key": str(uuid4())},
            json=reviewed,
        )
        assert saved.status_code == 201, saved.text
        original = original or saved.json()["activity"]["activity_id"]
        accounts = saved.json()["accounts"]
        for path in ["/api/v1/financial-home", "/api/v1/financial-plan"]:
            result = client.get(path, headers=headers)
            assert result.status_code == 200, result.text
            home = result.json().get("home", result.json())
            assert kind in {entry["kind"] for entry in home["recent_activity"]}
