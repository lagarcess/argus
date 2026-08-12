from __future__ import annotations

import hashlib
import json
import ssl
from email import message_from_string
from unittest.mock import MagicMock

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.schemas import Language
from argus.domain.access_approval_email import (
    ACCESS_WELCOME_CONTENT_VERSION,
    AccessWelcomeSendResult,
    build_access_welcome_email,
    send_access_welcome_email,
)
from fastapi.testclient import TestClient

client = TestClient(app)


class _FakeSMTP:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.context = context
        self.login_args: tuple[str, str] | None = None
        self.mail_from: str | None = None
        self.recipient: str | None = None
        self.message: str | None = None
        self.data_receipt = b"Queued. resend-message-id"

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
        return 250, self.data_receipt


@pytest.mark.parametrize(
    (
        "language",
        "subject",
        "welcome_line",
        "product_line",
        "first_action",
        "cta_line",
        "button_label",
        "fallback_line",
        "support_line",
    ),
    [
        (
            "en",
            "Welcome to Argus",
            "Welcome to Argus. Your access has been granted.",
            "Argus is AI-powered investing and trading idea validation for everyone.",
            "Start by describing an investing idea in plain language and running "
            "your first historical test.",
            "Create your Argus account:",
            "Create your Argus account",
            "If the button does not work, open this link:",
            "Questions? Contact support@get-argus.com.",
        ),
        (
            "es-419",
            "Bienvenido a Argus",
            "Bienvenido a Argus. Tu acceso fue aprobado.",
            "Argus usa IA para validar ideas de inversión y trading para todos.",
            "Empieza por describir una idea de inversión en lenguaje sencillo y "
            "realizar tu primera prueba histórica.",
            "Crea tu cuenta de Argus:",
            "Crea tu cuenta de Argus",
            "Si el botón no funciona, abre este enlace:",
            "¿Tienes preguntas? Escribe a support@get-argus.com.",
        ),
    ],
)
def test_access_welcome_content_is_literal_bilingual_and_transactional(
    language: Language,
    subject: str,
    welcome_line: str,
    product_line: str,
    first_action: str,
    cta_line: str,
    button_label: str,
    fallback_line: str,
    support_line: str,
) -> None:
    signup_url = "https://app.example/?auth=signup"

    content = build_access_welcome_email(
        language=language,
        signup_url=signup_url,
    )

    assert content.subject == subject
    assert content.plain_text == (
        f"{welcome_line}\n\n"
        f"{product_line}\n\n"
        f"{first_action}\n\n"
        f"{cta_line}\n"
        f"{signup_url}\n\n"
        f"{support_line}"
    )
    for literal in (
        welcome_line,
        product_line,
        first_action,
        button_label,
        fallback_line,
        signup_url,
        support_line,
    ):
        assert literal in content.html
    assert content.plain_text.count(first_action) == 1
    assert content.html.count(first_action) == 1
    combined = f"{content.plain_text}\n{content.html}".lower()
    assert "unsubscribe" not in combined
    assert "cancelar la suscripción" not in combined
    assert "confirm your email" not in combined
    assert "confirma tu correo" not in combined
    assert "\u2014" not in combined


@pytest.mark.parametrize(
    ("language", "subject", "product_line", "first_action"),
    [
        (
            "en",
            "Welcome to Argus",
            "Argus is AI-powered investing and trading idea validation for everyone.",
            "Start by describing an investing idea in plain language and running "
            "your first historical test.",
        ),
        (
            "es-419",
            "Bienvenido a Argus",
            "Argus usa IA para validar ideas de inversión y trading para todos.",
            "Empieza por describir una idea de inversión en lenguaje sencillo y "
            "realizar tu primera prueba histórica.",
        ),
    ],
)
def test_access_welcome_sender_preserves_smtp_and_multipart_contract(
    monkeypatch: pytest.MonkeyPatch,
    language: Language,
    subject: str,
    product_line: str,
    first_action: str,
) -> None:
    instances: list[_FakeSMTP] = []

    def _smtp(
        host: str,
        port: int,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> _FakeSMTP:
        instance = _FakeSMTP(host, port, timeout=timeout, context=context)
        instances.append(instance)
        return instance

    monkeypatch.setenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD", "re_test_password")
    monkeypatch.setattr(
        "argus.domain.access_approval_email.smtplib.SMTP_SSL",
        _smtp,
    )

    result = send_access_welcome_email(
        recipient=" Person@Example.COM ",
        language=language,
        signup_url="https://app.example/?auth=signup",
    )

    assert result == AccessWelcomeSendResult(
        subject=subject,
        content_version="private-alpha-access-welcome/v1",
        provider_receipt="Queued. resend-message-id",
    )
    assert result.content_version == ACCESS_WELCOME_CONTENT_VERSION
    assert len(instances) == 1
    smtp = instances[0]
    assert (smtp.host, smtp.port) == ("smtp.resend.com", 465)
    assert smtp.login_args == ("resend", "re_test_password")
    assert smtp.context.verify_mode == ssl.CERT_REQUIRED
    assert smtp.context.check_hostname is True
    assert smtp.mail_from == "noreply@get-argus.com"
    assert smtp.recipient == "person@example.com"
    assert smtp.message is not None

    message = message_from_string(smtp.message)
    assert message["From"] == "Argus <noreply@get-argus.com>"
    assert message["To"] == "person@example.com"
    assert str(message["Subject"]) == subject
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
    assert set(payloads) == {"text/plain", "text/html"}
    assert product_line in payloads["text/plain"]
    assert product_line in payloads["text/html"]
    assert payloads["text/plain"].count(first_action) == 1
    assert payloads["text/html"].count(first_action) == 1
    assert "support@get-argus.com" in payloads["text/plain"]
    assert "support@get-argus.com" in payloads["text/html"]
    assert "background-color: #191c1f" in payloads["text/html"]
    assert "border-radius: 9999px" in payloads["text/html"]
    assert "https://app.example/?auth=signup" in payloads["text/plain"]
    assert "https://app.example/?auth=signup" in payloads["text/html"]
    assert "\u2014" not in payloads["text/plain"] + payloads["text/html"]


def test_access_welcome_hash_uses_versioned_namespace_and_normalized_recipient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances: list[_FakeSMTP] = []

    def _smtp(
        host: str,
        port: int,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> _FakeSMTP:
        instance = _FakeSMTP(host, port, timeout=timeout, context=context)
        instances.append(instance)
        return instance

    monkeypatch.setenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD", "re_test_password")
    monkeypatch.setattr(
        "argus.domain.access_approval_email.smtplib.SMTP_SSL",
        _smtp,
    )

    for recipient in ("Person@Example.com", " person@example.COM "):
        send_access_welcome_email(
            recipient=recipient,
            language="en",
            signup_url="https://app.example/?auth=signup",
        )

    keys = [
        message_from_string(instance.message or "")["Resend-Idempotency-Key"]
        for instance in instances
    ]
    assert keys[0] == keys[1]
    material = "\n".join(
        (
            "argus-access-welcome/v1",
            "person@example.com",
            "en",
            "https://app.example/?auth=signup",
        )
    )
    assert keys[0] == f"sha256:{hashlib.sha256(material.encode('utf-8')).hexdigest()}"


def test_access_welcome_receipt_is_bounded_to_256_characters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _smtp(
        host: str,
        port: int,
        *,
        timeout: float,
        context: ssl.SSLContext,
    ) -> _FakeSMTP:
        instance = _FakeSMTP(host, port, timeout=timeout, context=context)
        instance.data_receipt = b"x" * 300
        return instance

    monkeypatch.setenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD", "re_test_password")
    monkeypatch.setattr(
        "argus.domain.access_approval_email.smtplib.SMTP_SSL",
        _smtp,
    )

    result = send_access_welcome_email(
        recipient="person@example.com",
        language="en",
        signup_url="https://app.example/?auth=signup",
    )

    assert result.provider_receipt == "x" * 256


def test_access_welcome_html_escapes_the_signup_url() -> None:
    unsafe_url = 'https://app.example/?next="><script>alert(1)</script>&auth=signup'

    content = build_access_welcome_email(language="en", signup_url=unsafe_url)

    assert "<script>alert(1)</script>" not in content.html
    assert (
        "https://app.example/?next=&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;"
        "&amp;auth=signup"
    ) in content.html


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


def test_internal_canary_denial_signal_requires_ops_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gateway = MagicMock()
    gateway.private_alpha_email_allowed.return_value = False
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "ops-token")

    missing = client.post(
        "/internal/canary/requested-signup-denial",
        json={"email": "person@example.com"},
    )
    wrong = client.post(
        "/internal/canary/requested-signup-denial",
        json={"email": "person@example.com"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    authorized = client.post(
        "/internal/canary/requested-signup-denial",
        json={"email": "person@example.com"},
        headers={"Authorization": "Bearer ops-token"},
    )

    assert missing.status_code == wrong.status_code == 404
    assert authorized.status_code == 200
    assert authorized.json() == {"denied": True}
    gateway.private_alpha_email_allowed.assert_called_once_with("person@example.com")


@pytest.mark.parametrize("authorization", [None, "Bearer wrong-token"])
@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"{",
        json.dumps({"email": "not-an-email"}).encode(),
        json.dumps({"email": f"{'a' * 321}@example.com"}).encode(),
        json.dumps({"email": "person@example.com"}).encode(),
    ],
)
def test_internal_approval_checks_ops_auth_before_parsing_any_body(
    monkeypatch: pytest.MonkeyPatch,
    authorization: str | None,
    body: bytes,
) -> None:
    from argus.api.routers import ops

    gateway = MagicMock()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "ops-token")
    sender = MagicMock()
    monkeypatch.setattr(ops, "send_access_approval_email", sender)
    headers = {"Content-Type": "application/json"}
    if authorization is not None:
        headers["Authorization"] = authorization

    response = client.post(
        "/internal/access-requests/approve",
        content=body,
        headers=headers,
    )

    assert response.status_code == 404
    gateway.get_requested_private_alpha_access.assert_not_called()
    gateway.approve_requested_private_alpha_access.assert_not_called()
    sender.assert_not_called()
