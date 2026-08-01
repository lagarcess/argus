from __future__ import annotations

import hashlib
import html
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from argus.api.schemas import Language

_SMTP_HOST = "smtp.resend.com"
_SMTP_PORT = 465
_SMTP_USERNAME = "resend"
_SMTP_TIMEOUT_SECONDS = 10.0
_SENDER_ADDRESS = "noreply@get-argus.com"
_SENDER_HEADER = "Argus <noreply@get-argus.com>"
_MAX_RECEIPT_LENGTH = 256


def _localized_content(
    language: Language,
    signup_url: str,
) -> tuple[str, str, str]:
    safe_url = html.escape(signup_url, quote=True)
    if language == "es-419":
        subject = "Tu acceso a Argus fue aprobado"
        plain = (
            "Tu acceso a Argus fue aprobado.\n\n"
            "Ya puedes crear tu cuenta de Argus en el formulario de registro:\n"
            f"{signup_url}\n\n"
            "Argus"
        )
        rich = (
            "<p>Tu acceso a Argus fue aprobado.</p>"
            "<p>Ya puedes crear tu cuenta de Argus en el formulario de registro:</p>"
            f'<p><a href="{safe_url}">Crear tu cuenta de Argus</a></p>'
            "<p>Argus</p>"
        )
        return subject, plain, rich
    if language != "en":
        raise ValueError("Unsupported approval email language.")
    subject = "Your Argus access is approved"
    plain = (
        "Your Argus access is approved.\n\n"
        "You can now create your Argus account using the signup form:\n"
        f"{signup_url}\n\n"
        "Argus"
    )
    rich = (
        "<p>Your Argus access is approved.</p>"
        "<p>You can now create your Argus account using the signup form:</p>"
        f'<p><a href="{safe_url}">Create your Argus account</a></p>'
        "<p>Argus</p>"
    )
    return subject, plain, rich


def _idempotency_key(
    *,
    recipient: str,
    language: Language,
    signup_url: str,
) -> str:
    material = "\n".join(
        (
            "argus-access-approval/v1",
            recipient,
            language,
            signup_url,
        )
    )
    return f"sha256:{hashlib.sha256(material.encode('utf-8')).hexdigest()}"


def _require_accepted(code: int) -> None:
    if code not in {250, 251}:
        raise RuntimeError("Approval email SMTP delivery was not accepted.")


def send_access_approval_email(
    *,
    recipient: str,
    language: Language,
    signup_url: str,
) -> str:
    password = (os.getenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD") or "").strip()
    if not password:
        raise RuntimeError("Approval email SMTP configuration is unavailable.")

    normalized_recipient = recipient.strip().lower()
    if not normalized_recipient:
        raise ValueError("Approval email recipient is required.")
    subject, plain, rich = _localized_content(language, signup_url)

    message = MIMEMultipart("alternative")
    message["From"] = _SENDER_HEADER
    message["To"] = normalized_recipient
    message["Subject"] = subject
    message["Resend-Idempotency-Key"] = _idempotency_key(
        recipient=normalized_recipient,
        language=language,
        signup_url=signup_url,
    )
    message.attach(MIMEText(plain, "plain", "utf-8"))
    message.attach(MIMEText(rich, "html", "utf-8"))

    with smtplib.SMTP_SSL(
        _SMTP_HOST,
        _SMTP_PORT,
        timeout=_SMTP_TIMEOUT_SECONDS,
        context=ssl.create_default_context(),
    ) as smtp:
        smtp.login(_SMTP_USERNAME, password)
        mail_code, _ = smtp.mail(_SENDER_ADDRESS)
        _require_accepted(mail_code)
        recipient_code, _ = smtp.rcpt(normalized_recipient)
        _require_accepted(recipient_code)
        data_code, raw_receipt = smtp.data(message.as_string())
        _require_accepted(data_code)

    receipt = raw_receipt.decode("utf-8", errors="replace").strip()
    return receipt[:_MAX_RECEIPT_LENGTH] or "accepted"
