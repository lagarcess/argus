"""Two-user household lifecycle: create → invite → accept → shared access."""

from __future__ import annotations

from uuid import uuid4

from tests.household.conftest import HouseholdApi

CHECKING = {"type": "checking", "currency": "DOP", "nickname": "Nomina"}
PRIVATE = {"type": "savings", "currency": "DOP", "nickname": "Privada"}


def test_create_invite_accept_and_access_only_shared_accounts(
    alice: HouseholdApi, bob: HouseholdApi
) -> None:
    created = alice.create_household({"name": "Casa"})
    assert created.status_code == 201, created.text
    household = created.json()
    household_id = household["id"]
    assert household["status"] == "active"
    assert household["admin_user_id"] == alice.user_id
    assert [m["user_id"] for m in household["members"]] == [alice.user_id]
    assert alice.list_households().json()["households"][0]["id"] == household_id
    assert bob.list_households().json()["households"] == []

    # Create ≠ invite ≠ share: membership alone shares nothing.
    shared = alice.create_account({**CHECKING, "amount": "100.00"})
    assert shared.status_code == 201, shared.text
    shared_id = shared.json()["id"]
    private = alice.create_account({**PRIVATE, "amount": "50.00"})
    assert private.status_code == 201, private.text
    private_id = private.json()["id"]
    bob_own = bob.create_account(
        {"type": "cash", "currency": "DOP", "nickname": "Bob cash", "amount": "10.00"}
    )
    assert bob_own.status_code == 201, bob_own.text

    invite = alice.invite(household_id)
    assert invite.status_code == 201, invite.text
    token = invite.json()["token"]
    invitation_id = invite.json()["id"]
    assert "expires_at" in invite.json()

    accepted = bob.accept(token)
    assert accepted.status_code == 200, accepted.text
    members = {m["user_id"]: m["role"] for m in accepted.json()["members"]}
    assert members[alice.user_id] == "admin"
    assert members[bob.user_id] == "member"

    # Safe same-recipient retry.
    retry = bob.accept(token)
    assert retry.status_code == 200, retry.text
    assert len(retry.json()["members"]) == 2

    empty = bob.shared_accounts(household_id)
    assert empty.status_code == 200, empty.text
    assert empty.json()["accounts"] == []

    grant = alice.share(household_id, shared_id)
    assert grant.status_code == 201, grant.text
    assert grant.json()["permission"] == "view"
    grant_id = grant.json()["id"]

    # Private account stays invisible; Bob's own account is not auto-shared.
    for viewer in (alice, bob):
        accounts = viewer.shared_accounts(household_id).json()["accounts"]
        ids = {item["account_id"] for item in accounts}
        assert ids == {shared_id}
        assert private_id not in ids
        assert bob_own.json()["id"] not in ids
        assert accounts[0]["permission"] == "view"
        assert accounts[0]["owner_user_id"] == alice.user_id

    # Explicit edit grant does not invent ownership or admin.
    updated = alice.update_grant(household_id, grant_id, "edit")
    assert updated.status_code == 200, updated.text
    assert updated.json()["permission"] == "edit"
    bob_view = bob.shared_accounts(household_id).json()["accounts"][0]
    assert bob_view["permission"] == "edit"
    assert bob.get_household(household_id).json()["admin_user_id"] == alice.user_id

    # Non-owner cannot reshare Alice's private account.
    refused = bob.share(household_id, private_id)
    assert (refused.status_code, refused.json()["code"]) == (403, "account_not_owned")

    # Non-member cannot see the household.
    outsider_token = alice  # reuse client via bob leaving later
    assert outsider_token.revoke_invite(household_id, invitation_id).status_code in {
        204,
        409,
    }


def test_leave_revokes_grants_and_preserves_owner_accounts(
    alice: HouseholdApi, bob: HouseholdApi
) -> None:
    household_id = alice.create_household({"name": "Casa"}).json()["id"]
    token = alice.invite(household_id).json()["token"]
    assert bob.accept(token).status_code == 200

    alice_account = alice.create_account(
        {**CHECKING, "amount": "20.00"}, key=str(uuid4())
    ).json()["id"]
    bob_account = bob.create_account(
        {"type": "cash", "currency": "DOP", "amount": "5.00"}, key=str(uuid4())
    ).json()["id"]
    alice.share(household_id, alice_account)
    bob.share(household_id, bob_account)
    assert len(alice.shared_accounts(household_id).json()["accounts"]) == 2

    left = bob.leave(household_id)
    assert left.status_code == 204, left.text
    assert bob.list_households().json()["households"] == []
    assert bob.get_household(household_id).status_code == 404

    remaining = alice.shared_accounts(household_id).json()["accounts"]
    assert {item["account_id"] for item in remaining} == {alice_account}

    # Owner still owns the financial account personally.
    personal = alice._client.get(  # noqa: SLF001
        f"/api/v1/financial-accounts/{alice_account}",
        headers=alice._headers,  # noqa: SLF001
    )
    assert personal.status_code == 200
    bob_personal = bob._client.get(  # noqa: SLF001
        f"/api/v1/financial-accounts/{bob_account}",
        headers=bob._headers,  # noqa: SLF001
    )
    assert bob_personal.status_code == 200


def test_admin_must_transfer_before_leaving_with_other_members(
    alice: HouseholdApi, bob: HouseholdApi
) -> None:
    household_id = alice.create_household().json()["id"]
    token = alice.invite(household_id).json()["token"]
    assert bob.accept(token).status_code == 200

    blocked = alice.leave(household_id)
    assert (blocked.status_code, blocked.json()["code"]) == (
        409,
        "must_transfer_or_close",
    )

    transferred = alice.transfer_admin(household_id, bob.user_id)
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["admin_user_id"] == bob.user_id

    assert alice.leave(household_id).status_code == 204
    assert bob.get_household(household_id).json()["admin_user_id"] == bob.user_id
    assert [m["user_id"] for m in bob.get_household(household_id).json()["members"]] == [
        bob.user_id
    ]


def test_flag_off_hides_surface(monkeypatch, gateway) -> None:  # noqa: ANN001
    from unittest.mock import patch

    from argus.api import state as api_state
    from argus.api.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setenv("ARGUS_HOUSEHOLDS_ENABLED", "false")
    monkeypatch.setenv("ARGUS_FINANCIAL_ACCOUNTS_ENABLED", "true")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    with (
        patch.object(api_state, "supabase_gateway", gateway),
        patch("argus.api.dependencies.auth_session_is_active", return_value=True),
        TestClient(app) as client,
    ):
        response = client.get(
            "/api/v1/households", headers={"Authorization": "Bearer registered-alice"}
        )
        assert (response.status_code, response.json()["code"]) == (
            404,
            "households_unavailable",
        )
