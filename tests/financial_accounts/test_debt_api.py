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
