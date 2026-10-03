"""Apple's token and revoke endpoints through a scripted transport."""

from __future__ import annotations

import base64
import os
from datetime import datetime, timezone

import httpx
import pytest
from argus.domain.apple_sign_in.client import AppleAuthClient, AppleError
from argus.domain.apple_sign_in.credentials import (
    SOURCE,
    AppleCredentialService,
    AppleIdentityMismatch,
    AppleRevocationPending,
    InMemoryAppleCredentialRepository,
    RevokeOutcome,
)
from argus.domain.ingestion.secrets import SecretBox

from tests.apple_sign_in_support import (
    BUNDLE_ID,
    SUBJECT,
    FakeApple,
    config,
    generated_key,
)

NOW = datetime(2026, 10, 2, 22, 0, tzinfo=timezone.utc)
USER = "8b0e3f8e-2b4c-4d8e-9a43-3f0c2a1d5e77"


@pytest.fixture
def key():  # noqa: ANN201
    return generated_key()


@pytest.fixture
def apple(key) -> FakeApple:  # noqa: ANN001
    return FakeApple(public_key=key.public_key())


@pytest.fixture
def client(key, apple):  # noqa: ANN001, ANN201
    sleeps: list[float] = []
    made = AppleAuthClient(config(key), transport=apple.transport(), sleep=sleeps.append)
    made.sleeps = sleeps  # type: ignore[attr-defined]
    yield made
    made.close()


def _box() -> SecretBox:
    return SecretBox(os.urandom(32))


def test_exchange_posts_the_code_with_a_fresh_secret_and_reads_the_subject(
    client,
    apple,  # noqa: ANN001
) -> None:
    refresh = apple.grant()
    grant = client.exchange_code("c.one-time-code")

    assert grant.refresh_token == refresh
    assert grant.subject == SUBJECT
    assert refresh not in repr(grant)
    path, form = apple.calls[0]
    assert path == "/auth/token"
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == "c.one-time-code"
    assert form["client_id"] == BUNDLE_ID


@pytest.mark.parametrize(
    ("claims", "reason"),
    [
        ({"aud": "ai.someone.else"}, "unexpected_id_token"),
        ({"sub": ""}, "unexpected_id_token"),
    ],
)
def test_exchange_refuses_an_identity_token_for_another_client(
    client,
    apple,
    claims,
    reason,  # noqa: ANN001
) -> None:
    apple.grant(**claims)
    with pytest.raises(AppleError) as raised:
        client.exchange_code("c.code")
    assert raised.value.reason == reason


def test_exchange_needs_a_refresh_token(client, apple) -> None:  # noqa: ANN001
    apple.token_responses.append((200, {"access_token": "a", "id_token": "x"}))
    with pytest.raises(AppleError) as raised:
        client.exchange_code("c.code")
    assert raised.value.reason == "missing_refresh_token"


def test_a_used_code_is_invalid_grant_and_is_never_retried(client, apple) -> None:  # noqa: ANN001
    apple.token_responses.append((400, {"error": "invalid_grant"}))
    with pytest.raises(AppleError) as raised:
        client.exchange_code("c.used")
    assert raised.value.invalid_grant
    assert len(apple.calls) == 1


def test_an_unavailable_apple_is_not_retried_for_a_single_use_code(
    client,
    apple,  # noqa: ANN001
) -> None:
    apple.token_responses.append((503, {"error": "server_error"}))
    with pytest.raises(AppleError) as raised:
        client.exchange_code("c.code")
    assert raised.value.status == 503 and not raised.value.invalid_grant
    assert len(apple.calls) == 1


@pytest.mark.parametrize("code", ["", "x" * 513, "código"])
def test_a_malformed_code_never_reaches_apple(client, apple, code) -> None:  # noqa: ANN001
    with pytest.raises(AppleError) as raised:
        client.exchange_code(code)
    assert raised.value.reason == "malformed_code"
    assert apple.calls == []


def test_revoke_names_the_refresh_token_and_retries_transient_failures(
    client,
    apple,  # noqa: ANN001
) -> None:
    apple.revoke_responses += [(503, {"error": "server_error"}), (200, None)]
    client.revoke("r.stored", client_id=BUNDLE_ID)

    assert [path for path, _ in apple.calls] == ["/auth/revoke", "/auth/revoke"]
    form = apple.calls[-1][1]
    assert form == {
        "client_id": BUNDLE_ID,
        "client_secret": form["client_secret"],
        "token": "r.stored",
        "token_type_hint": "refresh_token",
    }
    assert client.sleeps == [0.5]


def test_revoke_failures_carry_no_token(client, apple) -> None:  # noqa: ANN001
    apple.revoke_responses.append(
        (400, {"error": "invalid_client", "detail": "r.stored"})
    )
    with pytest.raises(AppleError) as raised:
        client.revoke("r.stored", client_id=BUNDLE_ID)
    assert raised.value.reason == "invalid_client"
    assert "r.stored" not in str(raised.value)


def test_unreachable_apple_is_bounded(key) -> None:  # noqa: ANN001
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    sleeps: list[float] = []
    made = AppleAuthClient(
        config(key), transport=httpx.MockTransport(down), sleep=sleeps.append
    )
    with pytest.raises(AppleError) as raised:
        made.revoke("r", client_id=BUNDLE_ID)
    assert raised.value.reason == "unreachable"
    assert len(sleeps) == 2


# The capture/revoke service, against the in-memory twin -----------------------


@pytest.fixture
def service(client):  # noqa: ANN001, ANN201
    return AppleCredentialService(
        InMemoryAppleCredentialRepository(), box=_box(), client=client, clock=lambda: NOW
    )


def test_capture_keeps_only_the_sealed_refresh_token(service, apple) -> None:  # noqa: ANN001
    refresh = apple.grant()
    service.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.code")

    row = service.repository.get(user_id=USER)
    assert row is not None and row.client_id == BUNDLE_ID
    assert refresh.encode() not in row.secret_ciphertext
    assert (
        service._box.open(row.secret_ciphertext, source=SOURCE, connection_id=USER)
        == refresh
    )
    assert refresh not in repr(row)


def test_capture_for_another_apple_id_stores_nothing(service, apple) -> None:  # noqa: ANN001
    apple.grant(sub="000999.other")
    with pytest.raises(AppleIdentityMismatch):
        service.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.code")
    assert service.repository.get(user_id=USER) is None


def test_a_later_sign_in_replaces_the_token_without_revoking_it(service, apple) -> None:  # noqa: ANN001
    apple.grant()
    service.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.1")
    second = apple.grant()
    service.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.2")

    row = service.repository.get(user_id=USER)
    assert (
        service._box.open(row.secret_ciphertext, source=SOURCE, connection_id=USER)
        == second
    )
    assert all(path == "/auth/token" for path, _ in apple.calls)


def test_revoke_deletes_the_row_only_after_apple_confirms(service, apple) -> None:  # noqa: ANN001
    refresh = apple.grant()
    service.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.code")

    assert service.revoke(user_id=USER) is RevokeOutcome.REVOKED
    assert apple.calls[-1][1]["token"] == refresh
    assert service.repository.get(user_id=USER) is None
    assert service.revoke(user_id=USER) is RevokeOutcome.NOTHING_STORED


def test_a_failed_revoke_keeps_the_sealed_token_as_the_pending_revoke(
    service,
    apple,  # noqa: ANN001
) -> None:
    apple.grant()
    service.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.code")
    apple.revoke_responses += [(503, {"error": "server_error"})] * 3

    with pytest.raises(AppleRevocationPending) as raised:
        service.revoke(user_id=USER)
    assert raised.value.reason == "server_error"
    assert service.repository.get(user_id=USER) is not None

    assert service.revoke(user_id=USER) is RevokeOutcome.REVOKED
    assert service.repository.get(user_id=USER) is None


def test_a_token_replaced_mid_revoke_stays_pending(service, apple) -> None:  # noqa: ANN001
    apple.grant()
    service.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.1")
    replacement = apple.grant()

    real_revoke = service._client.revoke

    def revoke_then_sign_in_again(token: str, *, client_id: str) -> None:
        real_revoke(token, client_id=client_id)
        service.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.2")

    service._client.revoke = revoke_then_sign_in_again
    with pytest.raises(AppleRevocationPending) as raised:
        service.revoke(user_id=USER)
    assert raised.value.reason == "credential_replaced"
    row = service.repository.get(user_id=USER)
    assert (
        service._box.open(row.secret_ciphertext, source=SOURCE, connection_id=USER)
        == replacement
    )


def test_a_credential_sealed_under_another_key_is_pending_not_dropped(
    client,
    apple,  # noqa: ANN001
) -> None:
    repository = InMemoryAppleCredentialRepository()
    writer = AppleCredentialService(
        repository, box=_box(), client=client, clock=lambda: NOW
    )
    apple.grant()
    writer.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.code")
    rotated = AppleCredentialService(
        repository, box=_box(), client=client, clock=lambda: NOW
    )

    with pytest.raises(AppleRevocationPending) as raised:
        rotated.revoke(user_id=USER)
    assert raised.value.reason == "credential_unreadable"
    assert repository.get(user_id=USER) is not None
    assert [path for path, _ in apple.calls] == ["/auth/token"]


def test_a_sealed_token_does_not_open_for_another_user(service, apple) -> None:  # noqa: ANN001
    from argus.domain.ingestion.secrets import SecretUnreadable

    apple.grant()
    service.capture(user_id=USER, apple_subject=SUBJECT, authorization_code="c.code")
    row = service.repository.get(user_id=USER)
    with pytest.raises(SecretUnreadable):
        service._box.open(
            row.secret_ciphertext,
            source=SOURCE,
            connection_id=base64.b16encode(os.urandom(16)).decode(),
        )
