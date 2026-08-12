from __future__ import annotations

import hashlib
import html
import os
import smtplib
import ssl
from dataclasses import dataclass
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
_IDEMPOTENCY_NAMESPACE = "argus-access-welcome"

ACCESS_WELCOME_CONTENT_VERSION = "private-alpha-access-welcome/v1"


@dataclass(frozen=True)
class AccessWelcomeEmailContent:
    subject: str
    plain_text: str
    html: str


@dataclass(frozen=True)
class AccessWelcomeSendResult:
    subject: str
    content_version: str
    provider_receipt: str


def build_access_welcome_email(
    *,
    language: Language,
    signup_url: str,
) -> AccessWelcomeEmailContent:
    safe_url = html.escape(signup_url, quote=True)
    if language == "es-419":
        subject = "Bienvenido a Argus"
        html_language = "es-419"
        welcome_line = "Bienvenido a Argus. Tu acceso fue aprobado."
        product_line = (
            "Argus usa IA para validar ideas de inversión y trading para todos."
        )
        first_action = (
            "Empieza por describir una idea de inversión en lenguaje sencillo y "
            "realizar tu primera prueba histórica."
        )
        cta_line = "Crea tu cuenta de Argus:"
        button_label = "Crea tu cuenta de Argus"
        fallback_line = "Si el botón no funciona, abre este enlace:"
        support_line = "¿Tienes preguntas? Escribe a support@get-argus.com."
    elif language == "en":
        subject = "Welcome to Argus"
        html_language = "en"
        welcome_line = "Welcome to Argus. Your access has been granted."
        product_line = (
            "Argus is AI-powered investing and trading idea validation for everyone."
        )
        first_action = (
            "Start by describing an investing idea in plain language and running "
            "your first historical test."
        )
        cta_line = "Create your Argus account:"
        button_label = "Create your Argus account"
        fallback_line = "If the button does not work, open this link:"
        support_line = "Questions? Contact support@get-argus.com."
    else:
        raise ValueError("Unsupported access welcome email language.")

    plain_text = (
        f"{welcome_line}\n\n"
        f"{product_line}\n\n"
        f"{first_action}\n\n"
        f"{cta_line}\n"
        f"{signup_url}\n\n"
        f"{support_line}"
    )

    rich = (
        "<!doctype html>"
        f'<html lang="{html_language}">'
        '<body style="margin:0;padding:0;background:#f4f4f4;">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;'
        f'color:transparent;">{welcome_line}</div>'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="background:#f4f4f4;border-collapse:collapse;">'
        '<tr><td align="center" style="padding:32px 16px;">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="max-width:600px;background:#ffffff;border:1px solid #c9c9cd;'
        'border-radius:20px;border-collapse:separate;overflow:hidden;">'
        '<tr><td style="background:#191c1f;padding:22px 28px;color:#ffffff;">'
        '<table role="presentation" cellspacing="0" cellpadding="0" border="0" '
        'style="border-collapse:collapse;"><tr>'
        '<td valign="middle" style="padding:0 12px 0 0;">'
        '<img src="https://arguschat.ai/icons/argus-192.png" width="36" '
        'height="36" alt="" style="display:block;width:36px;height:36px;'
        'border:0;outline:none;text-decoration:none;"></td>'
        '<td valign="middle" style="font-family:\'Space Grotesk\',Arial,Helvetica,'
        "sans-serif;font-size:21px;font-weight:700;letter-spacing:0.12em;"
        'line-height:1;color:#ffffff;">ARGUS</td>'
        "</tr></table></td></tr>"
        '<tr><td style="padding:32px 28px 28px;color:#191c1f;'
        "font-family:'Inter',Arial,Helvetica,sans-serif;font-size:16px;"
        'line-height:1.55;">'
        "<h1 style=\"margin:0 0 16px;font-family:'Space Grotesk','Inter',"
        "Arial,Helvetica,sans-serif;font-size:28px;font-weight:500;"
        f'letter-spacing:-0.01em;line-height:1.2;">{welcome_line}</h1>'
        f'<p style="margin:0 0 16px;">{product_line}</p>'
        f'<p style="margin:0 0 16px;">{first_action}</p>'
        '<p style="margin:26px 0 20px;">'
        f'<a href="{safe_url}" style="display:inline-block;background:#191c1f;'
        "color:#ffffff;text-decoration:none;font-weight:700;padding:13px 22px;"
        f'border-radius:9999px;">{button_label}</a></p>'
        '<p style="margin:20px 0 6px;font-size:13px;color:#5f6368;">'
        f"{fallback_line}</p>"
        '<p style="margin:0;padding:12px;background:#f4f4f4;border-radius:10px;'
        'font-size:13px;line-height:1.45;word-break:break-all;">'
        f'<a href="{safe_url}" style="color:#3036b3;">{safe_url}</a></p>'
        "</td></tr>"
        '<tr><td style="padding:20px 28px;border-top:1px solid #e1e1e4;'
        "color:#5f6368;font-family:'Inter',Arial,Helvetica,sans-serif;"
        f'font-size:13px;line-height:1.5;">{support_line}</td></tr>'
        "</table></td></tr></table>"
        "</body></html>"
    )
    return AccessWelcomeEmailContent(
        subject=subject,
        plain_text=plain_text,
        html=rich,
    )


def _idempotency_key(
    *,
    claim_token: str,
) -> str:
    material = "\n".join((_IDEMPOTENCY_NAMESPACE, claim_token))
    return f"sha256:{hashlib.sha256(material.encode('utf-8')).hexdigest()}"


def _require_accepted(code: int) -> None:
    if code not in {250, 251}:
        raise RuntimeError("Access welcome email SMTP delivery was not accepted.")


def send_access_welcome_email(
    *,
    recipient: str,
    language: Language,
    signup_url: str,
    claim_token: str,
) -> AccessWelcomeSendResult:
    password = (os.getenv("ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD") or "").strip()
    if not password:
        raise RuntimeError("Access welcome email SMTP configuration is unavailable.")

    normalized_recipient = recipient.strip().lower()
    if not normalized_recipient:
        raise ValueError("Access welcome email recipient is required.")
    normalized_claim_token = claim_token.strip().casefold()
    if not normalized_claim_token:
        raise ValueError("Access welcome email claim token is required.")
    content = build_access_welcome_email(language=language, signup_url=signup_url)

    message = MIMEMultipart("alternative")
    message["From"] = _SENDER_HEADER
    message["To"] = normalized_recipient
    message["Subject"] = content.subject
    message["Resend-Idempotency-Key"] = _idempotency_key(
        claim_token=normalized_claim_token,
    )
    message.attach(MIMEText(content.plain_text, "plain", "utf-8"))
    message.attach(MIMEText(content.html, "html", "utf-8"))

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
    return AccessWelcomeSendResult(
        subject=content.subject,
        content_version=ACCESS_WELCOME_CONTENT_VERSION,
        provider_receipt=receipt[:_MAX_RECEIPT_LENGTH] or "accepted",
    )
