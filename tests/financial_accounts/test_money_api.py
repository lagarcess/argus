from uuid import uuid4

import pytest

from financial_accounts.conftest import ALICE, BOB, GUEST


@pytest.mark.parametrize(
    "kind", ["expense", "income", "transfer", "card_payment", "refund"]
)
def test_canonical_http_preview_confirm_reopen_identity_and_home(client, kind):
    headers = {"Authorization": f"Bearer {ALICE}"}
    accounts = []
    for account_type in ("checking", "credit_card" if kind == "card_payment" else "cash"):
        response = client.post(
            "/api/v1/financial-accounts",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={
                "type": account_type,
                "currency": "USD",
                "amount": "100",
                "as_of": "2026-09-01T12:00:00-04:00",
            },
        )
        assert response.status_code == 201, response.text
        accounts.append(response.json())
    body = {
        "kind": kind,
        "amount": "25",
        "occurred_at": "2026-09-02T12:00:00-04:00",
        "expected_versions": {accounts[0]["id"]: 1},
    }
    if kind in ("transfer", "card_payment"):
        body.update(
            source_account_id=accounts[0]["id"], destination_account_id=accounts[1]["id"]
        )
    else:
        body["account_id"] = accounts[0]["id"]
    preview = client.post(
        "/api/v1/financial-activities/preview", headers=headers, json=body
    )
    assert preview.status_code == 200, preview.text
    reviewed = preview.json()["reviewed_request"]
    reviewed["preview_token"] = preview.json()["preview_token"]
    key = str(uuid4())
    result = client.post(
        "/api/v1/financial-activities",
        headers={**headers, "Idempotency-Key": key},
        json=reviewed,
    )
    assert result.status_code == 201, result.text
    activity = result.json()["activity"]
    path = "/api/v1/financial-activities/" + activity["activity_id"]
    assert client.get(path, headers=headers).json() == activity
    assert client.get(path + "/history", headers=headers).json()["items"] == [activity]
    assert client.get(path, headers={"Authorization": f"Bearer {BOB}"}).status_code == 404
    assert (
        client.get(path, headers={"Authorization": f"Bearer {GUEST}"}).status_code == 403
    )
    replay = client.post(
        "/api/v1/financial-activities",
        headers={**headers, "Idempotency-Key": key},
        json=reviewed,
    )
    assert replay.json()["replayed"] and replay.json()["activity"] == activity
    feed = client.get(
        "/api/v1/financial-accounts/" + accounts[0]["id"] + "/activity", headers=headers
    ).json()
    assert feed["items"][0]["activity_id"] == activity["activity_id"]
    home = client.get("/api/v1/financial-home?month=2026-09", headers=headers).json()
    assert home["period"]["month"] == "2026-09" and home["coverage"] == "recorded_only"
    assert len(home["recent_activity"]) == 1
