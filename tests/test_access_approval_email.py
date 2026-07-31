from __future__ import annotations

from email import message_from_string
from unittest.mock import MagicMock

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.domain.access_approval_email import send_access_approval_email
from fastapi.testclient import TestClient

client = TestClient(app)


class _FakeSMTP:
    def __init__(self, host: str, port: int, *, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.login_args: tuple[str, str] | None = None
        self.mail_from: str | None = None
        self.recipient: str | None = None
        self.message: str | None = None

    def __enter__(self) -> "_FakeSMTP":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def mail(self, sender: str) -> tuple[int, bytes]:
        self.mail_from = sender
        return 250, b"sender accepted"

    def rcpt(self, recipient: str) -> tuple[int, bytes]:
        self.recipient = recipient
        return 250, b"recipient accepted"

    def data(self, message: str) -> tuple[int, bytes]:
        self.message = message
        return 250, b"Queued. resend-message-id"


@pytest.mark.parametrize(
    ("language", "subject_fragment", "body_fragment"),
    [
        ("en", "Argus access is approved", "create your Argus account"),
        ("es-419", "acceso a Argus fue aprobado", "crear tu cuenta de Argus"),
    ],
)
def test_approval_email_uses_locked_smtp_and_localized_multipart_contract(
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    subject_fragment: str,
    body_fragment: str,
) -> None:
    instances: list[_FakeSMTP] = []

    def _smtp(host: str, port: int, *, timeout: float) -> _FakeSMTP:
        instance = _FakeSMTP(host, port, timeout=timeout)
        instances.append(instance)
        return instance

    monkeypatch.setenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD", "re_test_password")
    monkeypatch.setattr(
        "argus.domain.access_approval_email.smtplib.SMTP_SSL",
        _smtp,
    )

    receipt = send_access_approval_email(
        recipient="person@example.com",
        language=language,  # type: ignore[arg-type]
        signup_url="https://app.example/?auth=signup",
    )

    assert receipt == "Queued. resend-message-id"
    assert len(instances) == 1
    smtp = instances[0]
    assert (smtp.host, smtp.port) == ("smtp.resend.com", 465)
    assert smtp.login_args == ("resend", "re_test_password")
    assert smtp.mail_from == "noreply@get-argus.com"
    assert smtp.recipient == "person@example.com"
    assert smtp.message is not None

    message = message_from_string(smtp.message)
    assert message["From"] == "Argus <noreply@get-argus.com>"
    assert message["To"] == "person@example.com"
    assert subject_fragment in str(message["Subject"])
    assert message["Resend-Idempotency-Key"].startswith("sha256:")
    assert "person@example.com" not in message["Resend-Idempotency-Key"]
    assert message.get_content_type() == "multipart/alternative"
    payloads = {
        part.get_content_type(): part.get_payload(decode=True).decode(
            part.get_content_charset() or "utf-8"
        )
        for part in message.walk()
        if part.get_content_maintype() != "multipart"
    }
    assert body_fragment in payloads["text/plain"]
    assert body_fragment in payloads["text/html"]
    assert "https://app.example/?auth=signup" in payloads["text/plain"]
    assert "https://app.example/?auth=signup" in payloads["text/html"]


def test_approval_email_hash_is_deterministic_for_normalized_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances: list[_FakeSMTP] = []

    def _smtp(host: str, port: int, *, timeout: float) -> _FakeSMTP:
        instance = _FakeSMTP(host, port, timeout=timeout)
        instances.append(instance)
        return instance

    monkeypatch.setenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD", "re_test_password")
    monkeypatch.setattr(
        "argus.domain.access_approval_email.smtplib.SMTP_SSL",
        _smtp,
    )

    for recipient in ("Person@Example.com", " person@example.COM "):
        send_access_approval_email(
            recipient=recipient,
            language="en",
            signup_url="https://app.example/?auth=signup",
        )

    keys = [
        message_from_string(instance.message or "")["Resend-Idempotency-Key"]
        for instance in instances
    ]
    assert keys[0] == keys[1]


def test_internal_approval_sends_before_requested_to_user_cas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import ops

    events: list[str] = []
    gateway = MagicMock()
    gateway.get_requested_private_alpha_access.return_value = {
        "email": "person@example.com",
        "role": "requested",
        "language": "es-419",
        "disabled_at": None,
    }
    gateway.approve_requested_private_alpha_access.side_effect = (
        lambda **kwargs: events.append("cas") or True
    )
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "ops-token")
    monkeypatch.setenv("ARGUS_APP_ORIGIN", "https://app.example/")
    monkeypatch.setenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD", "re_test_password")

    def _send(**kwargs: object) -> str:
        events.append("send")
        assert kwargs == {
            "recipient": "person@example.com",
            "language": "es-419",
            "signup_url": "https://app.example/?auth=signup",
        }
        return "Queued. resend-message-id"

    monkeypatch.setattr(ops, "send_access_approval_email", _send)

    response = client.post(
        "/internal/access-requests/approve",
        json={"email": " Person@Example.COM "},
        headers={"Authorization": "Bearer ops-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"approved": True}
    assert events == ["send", "cas"]
    gateway.approve_requested_private_alpha_access.assert_called_once_with(
        email="person@example.com"
    )


def test_internal_approval_missing_smtp_secret_never_transitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = MagicMock()
    gateway.get_requested_private_alpha_access.return_value = {
        "email": "person@example.com",
        "role": "requested",
        "language": "en",
        "disabled_at": None,
    }
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "ops-token")
    monkeypatch.setenv("ARGUS_APP_ORIGIN", "https://app.example")
    monkeypatch.delenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD", raising=False)

    response = client.post(
        "/internal/access-requests/approve",
        json={"email": "person@example.com"},
        headers={"Authorization": "Bearer ops-token"},
    )

    assert response.status_code == 503
    assert "ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD" not in response.text
    gateway.approve_requested_private_alpha_access.assert_not_called()


def test_internal_approval_smtp_failure_never_transitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import ops

    gateway = MagicMock()
    gateway.get_requested_private_alpha_access.return_value = {
        "email": "person@example.com",
        "role": "requested",
        "language": "en",
        "disabled_at": None,
    }
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "ops-token")
    monkeypatch.setenv("ARGUS_APP_ORIGIN", "https://app.example")
    monkeypatch.setenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD", "re_test_password")
    monkeypatch.setattr(
        ops,
        "send_access_approval_email",
        MagicMock(side_effect=RuntimeError("smtp unavailable")),
    )

    response = client.post(
        "/internal/access-requests/approve",
        json={"email": "person@example.com"},
        headers={"Authorization": "Bearer ops-token"},
    )

    assert response.status_code == 503
    assert "smtp unavailable" not in response.text
    gateway.approve_requested_private_alpha_access.assert_not_called()


def test_internal_approval_missing_app_origin_never_sends_or_transitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import ops

    gateway = MagicMock()
    gateway.get_requested_private_alpha_access.return_value = {
        "email": "person@example.com",
        "role": "requested",
        "language": "en",
        "disabled_at": None,
    }
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "ops-token")
    monkeypatch.delenv("ARGUS_APP_ORIGIN", raising=False)
    sender = MagicMock()
    monkeypatch.setattr(ops, "send_access_approval_email", sender)

    response = client.post(
        "/internal/access-requests/approve",
        json={"email": "person@example.com"},
        headers={"Authorization": "Bearer ops-token"},
    )

    assert response.status_code == 503
    sender.assert_not_called()
    gateway.approve_requested_private_alpha_access.assert_not_called()


def test_internal_approval_missing_or_disabled_request_does_not_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import ops

    gateway = MagicMock()
    gateway.get_requested_private_alpha_access.return_value = None
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "ops-token")
    sender = MagicMock()
    monkeypatch.setattr(ops, "send_access_approval_email", sender)

    response = client.post(
        "/internal/access-requests/approve",
        json={"email": "person@example.com"},
        headers={"Authorization": "Bearer ops-token"},
    )

    assert response.status_code == 409
    sender.assert_not_called()
    gateway.approve_requested_private_alpha_access.assert_not_called()


def test_internal_approval_compare_and_set_miss_does_not_return_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import ops

    gateway = MagicMock()
    gateway.get_requested_private_alpha_access.return_value = {
        "email": "person@example.com",
        "role": "requested",
        "language": "en",
        "disabled_at": None,
    }
    gateway.approve_requested_private_alpha_access.return_value = False
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "ops-token")
    monkeypatch.setenv("ARGUS_APP_ORIGIN", "https://app.example")
    sender = MagicMock(return_value="Queued. resend-message-id")
    monkeypatch.setattr(ops, "send_access_approval_email", sender)

    response = client.post(
        "/internal/access-requests/approve",
        json={"email": "person@example.com"},
        headers={"Authorization": "Bearer ops-token"},
    )

    assert response.status_code == 409
    sender.assert_called_once()
    gateway.approve_requested_private_alpha_access.assert_called_once()


def test_internal_approval_invalid_ops_token_is_route_indistinguishable_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = MagicMock()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "ops-token")

    response = client.post(
        "/internal/access-requests/approve",
        json={"email": "person@example.com"},
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 404
    gateway.get_requested_private_alpha_access.assert_not_called()
