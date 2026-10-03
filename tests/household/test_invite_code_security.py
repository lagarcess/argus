"""#789: keyed code digests, code entropy, fail-closed secret, lookup limits.

No database here, so these run in backend-checks. The real-Postgres side
(private digest table, rotation, rehash, client exposure) is in
tests/test_invite_code_security_postgres.py.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from argus.api import households as surface
from argus.api import invite_limits
from argus.api import state as api_state
from argus.api.main import app
from argus.api.routers.ops import _invite_code_check
from argus.api.shortcuts_limits import WeightedWindow
from argus.domain.household.errors import InvitationNotFound, InviteCodesUnavailable
from argus.domain.household.invite_codes import (
    CODE_ALPHABET,
    CODE_LENGTH,
    CodeHasher,
    InviteSettings,
    format_code,
    new_code,
    normalize_code,
)
from argus.domain.household.repository import (
    FinancialAccountLookup,
    InMemoryHouseholdRepository,
)
from argus.domain.recording.repository import InMemoryFinancialAccountRepository
from fastapi.testclient import TestClient

from tests.household.conftest import ALICE, TEST_CODE_SECRET

SECRET_A = "a" * 40
SECRET_B = "b" * 40


# -- Digests ------------------------------------------------------------------


def test_digest_is_keyed_versioned_and_names_its_key():
    a = CodeHasher.from_secrets(SECRET_A)
    b = CodeHasher.from_secrets(SECRET_B)
    code = new_code()
    digest = a.digest(code)
    version, key_id, mac = digest.split(".")
    assert version == "v2" and len(key_id) == 8 and len(mac) == 64
    assert key_id == a.current.key_id and SECRET_A not in digest
    # The same code under another secret is a different digest: a stolen table
    # cannot be matched without the secret, and one secret cannot find another's.
    assert b.digest(code) != digest
    assert a.digest(code) == digest  # deterministic, so it can be looked up
    import hmac

    expected = hmac.new(
        SECRET_A.encode(), f"argus-invite-code:v2:{code}".encode(), hashlib.sha256
    ).hexdigest()
    assert mac == expected  # HMAC-SHA-256 under the secret, nothing else
    assert b.digest(code).split(".")[2] != mac

    assert (
        hashlib.sha256(f"argus-invite-code:v1:{code}".encode()).hexdigest() not in digest
    )
    assert "secret" not in repr(a.current) and SECRET_A not in repr(a)


def test_rotation_looks_up_under_current_then_previous():
    rotated = CodeHasher.from_secrets(SECRET_B, SECRET_A)
    code = new_code()
    assert rotated.candidates(code) == [
        CodeHasher.from_secrets(SECRET_B).digest(code),
        CodeHasher.from_secrets(SECRET_A).digest(code),
    ]
    assert rotated.digest(code) == rotated.candidates(code)[0]
    same = CodeHasher.from_secrets(SECRET_A, SECRET_A)
    assert same.previous is None and len(same.candidates(code)) == 1


@pytest.mark.parametrize("secret", [None, "", "   ", "short-secret"])
def test_missing_or_short_secret_fails_closed(secret, monkeypatch):
    with pytest.raises(InviteCodesUnavailable):
        CodeHasher.from_secrets(secret)
    if secret is None:
        monkeypatch.delenv("ARGUS_INVITE_CODE_SECRET", raising=False)
    else:
        monkeypatch.setenv("ARGUS_INVITE_CODE_SECRET", secret)
    with pytest.raises(InviteCodesUnavailable):
        CodeHasher.from_env()
    # No unkeyed fallback: the repository refuses to make or look up a code.
    repo = InMemoryHouseholdRepository(
        FinancialAccountLookup(InMemoryFinancialAccountRepository())
    )
    household = repo.create_household(user_id="u1", name="Casa")
    with pytest.raises(InviteCodesUnavailable):
        repo.create_invitation(user_id="u1", household_id=household.id)
    with pytest.raises(InviteCodesUnavailable):
        repo.preview_invitation(user_id="u2", code="ABCD-EFGH-JKMN")


def test_short_previous_secret_also_fails_closed():
    with pytest.raises(InviteCodesUnavailable):
        CodeHasher.from_secrets(SECRET_A, "too-short")


# -- Entropy ------------------------------------------------------------------


def test_code_has_sixty_bits_in_a_typeable_shape():
    assert len(CODE_ALPHABET) == 32 and CODE_LENGTH == 12
    assert math.log2(len(CODE_ALPHABET) ** CODE_LENGTH) == 60
    code = new_code()
    shown = format_code(code)
    assert len(shown) == 14 and shown[4] == shown[9] == "-"
    assert normalize_code(shown.lower().replace("-", " ")) == code
    assert normalize_code("ABCD-EFGH") is None  # #788's 8-character shape


# -- Fail closed at startup and readiness -------------------------------------


@pytest.fixture
def secretless_client(surface_env, gateway, monkeypatch) -> Iterator[TestClient]:  # noqa: ANN001
    monkeypatch.delenv("ARGUS_INVITE_CODE_SECRET", raising=False)
    with (
        patch.object(api_state, "supabase_gateway", gateway),
        patch("argus.api.dependencies.auth_session_is_active", return_value=True),
        TestClient(app) as test_client,
    ):
        yield test_client


def test_households_stay_off_without_the_secret(secretless_client):
    assert surface.households_service() is None
    response = secretless_client.get(
        "/api/v1/households", headers={"Authorization": f"Bearer {ALICE}"}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "households_unavailable"


def test_readiness_fails_when_a_code_flag_is_on_without_the_secret(monkeypatch):
    for flag in (
        "ARGUS_HOUSEHOLDS_ENABLED",
        "ARGUS_BETA_INVITES_ENABLED",
        "ARGUS_BETA_INVITE_GATE_ENABLED",
    ):
        monkeypatch.delenv(flag, raising=False)
    monkeypatch.delenv("ARGUS_INVITE_CODE_SECRET", raising=False)
    assert _invite_code_check() is None  # every code flag off: no extra check
    monkeypatch.setenv("ARGUS_BETA_INVITE_GATE_ENABLED", "true")
    check = _invite_code_check()
    assert check["status"] == "degraded"
    assert check["reason"] == "invite_code_secret_unusable"
    monkeypatch.setenv("ARGUS_INVITE_CODE_SECRET", TEST_CODE_SECRET)
    assert _invite_code_check()["status"] == "ready"


def test_secret_removed_after_start_answers_503(client, alice, bob, monkeypatch):
    hid = alice.create_household({"name": "Casa"}).json()["household_id"]
    monkeypatch.delenv("ARGUS_INVITE_CODE_SECRET")
    created = alice.invite(hid)
    assert created.status_code == 503
    assert created.json()["code"] == "invite_codes_unavailable"
    by_code = bob.write("/household-invitations/preview", {"code": "ABCD-EFGH-JKMN"})
    assert by_code.status_code == 503


# -- Lookup rate limits -------------------------------------------------------


def _ip(address: str) -> dict[str, str]:
    return {"CF-Connecting-IP": address}


def _post(api, path, body, *, ip):  # noqa: ANN001, ANN202
    return api._client.post(  # noqa: SLF001
        "/api/v1" + path,
        json=body,
        headers=api._headers | _ip(ip) | {"Idempotency-Key": new_code()},  # noqa: SLF001
    )


def _guess() -> dict[str, str]:
    return {"code": format_code(new_code()), "display_name": "Guess"}


def _invite_code(api) -> str:  # noqa: ANN001
    hid = api.create_household({"name": "Casa"}).json()["household_id"]
    return api.invite(hid).json()["invitation"]["code"]


@pytest.mark.parametrize(
    "path", ["/household-invitations/accept", "/household-invitations/preview"]
)
def test_failed_guesses_trip_the_account_limit_with_retry_after(alice, bob, path):
    code = _invite_code(alice)
    limit = invite_limits.FAILED_PER_ACCOUNT[0][0]
    for _ in range(limit):
        assert _post(bob, path, _guess(), ip="198.51.100.1").status_code == 404
    # Blocked before the lookup: even a real code from a fresh IP is refused.
    blocked = _post(bob, path, {"code": code, "display_name": "Bob"}, ip="198.51.100.9")
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "invite_rate_limited"
    assert 0 < int(blocked.headers["Retry-After"]) <= 3600
    # Another account behind the same IP is unaffected (IP budget is larger).
    mine = _post(alice, path, {"code": code, "display_name": "Alice"}, ip="198.51.100.1")
    assert mine.status_code != 429


def test_failed_guesses_trip_the_ip_limit_and_spare_other_ips(alice, bob, monkeypatch):
    # Raise the account budget so the IP budget is the one that trips.
    monkeypatch.setattr(
        invite_limits, "FAILED_PER_ACCOUNT", ((1000, 3600, WeightedWindow()),)
    )
    code = _invite_code(alice)
    limit = invite_limits.FAILED_PER_IP[0][0]
    path = "/household-invitations/accept"
    for _ in range(limit):
        assert _post(bob, path, _guess(), ip="203.0.113.7").status_code == 404
    assert _post(bob, path, _guess(), ip="203.0.113.7").status_code == 429
    same_ip_other_account = _post(alice, path, _guess(), ip="203.0.113.7")
    assert same_ip_other_account.status_code == 429
    # A valid code still works for the same account from another IP.
    accepted = _post(bob, path, {"code": code, "display_name": "Bob"}, ip="203.0.113.8")
    assert accepted.status_code == 200, accepted.text


def test_token_guesses_count_too(alice, bob):
    for _ in range(invite_limits.FAILED_PER_ACCOUNT[0][0]):
        response = _post(
            bob,
            "/household-invitations/accept",
            {"token": "x" * 43, "display_name": "Bob"},
            ip="198.51.100.2",
        )
        assert response.status_code == 404
    again = _post(
        bob, "/household-invitations/accept", {"token": "y" * 43}, ip="198.51.100.3"
    )
    assert again.status_code == 429


def test_found_but_closed_invites_cost_no_failure(alice, bob):
    code = _invite_code(alice)
    assert alice.write("/household-invitations/accept", {"code": code}).status_code in {
        200,
        409,
    }
    for _ in range(invite_limits.FAILED_PER_ACCOUNT[0][0] + 2):
        # Used up for Bob (consumed by Alice): found, so not a failed guess.
        response = _post(
            bob, "/household-invitations/preview", {"code": code}, ip="198.51.100.4"
        )
        assert response.status_code == 200


def test_request_budget_caps_lookups_of_any_outcome(alice, bob):
    code = _invite_code(alice)
    for _ in range(invite_limits.REQUESTS_PER_MINUTE):
        response = _post(
            bob, "/household-invitations/preview", {"code": code}, ip="192.0.2.10"
        )
        assert response.status_code == 200
    capped = _post(bob, "/household-invitations/preview", {"code": code}, ip="192.0.2.11")
    assert capped.status_code == 429 and "Retry-After" in capped.headers


class _FakeInviteStore:
    """Beta preview and redeem without Postgres: every lookup misses."""

    def __init__(self, founder: str) -> None:
        self.settings = InviteSettings(founder_user_id=founder)
        self.calls = 0

    def preview(self, *, token, code):  # noqa: ANN001, ANN201
        self.calls += 1
        raise InvitationNotFound()

    def redeem(self, *, user_id, token, code):  # noqa: ANN001, ANN201
        self.calls += 1
        raise InvitationNotFound()


@pytest.mark.parametrize("path", ["/invites/preview", "/invites/redeem"])
def test_beta_lookups_are_limited_with_no_founder_bypass(
    client, alice, identities, monkeypatch, path
):
    monkeypatch.setenv("ARGUS_BETA_INVITES_ENABLED", "true")
    # Alice is the founder; the limit still applies to her.
    store = _FakeInviteStore(founder=identities[ALICE]["id"])
    surface.configure_invites_store(store)
    try:
        limit = invite_limits.FAILED_PER_ACCOUNT[0][0]
        for _ in range(limit):
            assert (
                _post(
                    alice, path, {"code": format_code(new_code())}, ip="192.0.2.20"
                ).status_code
                == 404
            )
        refused = _post(alice, path, {"code": format_code(new_code())}, ip="192.0.2.21")
        assert (
            refused.status_code == 429 and refused.json()["code"] == "invite_rate_limited"
        )
        assert store.calls == limit  # the refused attempt never reached the store
    finally:
        surface.configure_invites_store(None)


def test_limiter_keys_use_the_trusted_client_ip_helper():
    request = MagicMock()
    request.headers = {"CF-Connecting-IP": "198.51.100.77", "X-Forwarded-For": "10.0.0.1"}
    request.client.host = "127.0.0.1"
    ip_key, user_key = invite_limits._keys(request, "user-1")  # noqa: SLF001
    assert (
        ip_key == "invite-code:ip:198.51.100.77" and user_key == "invite-code:user:user-1"
    )
