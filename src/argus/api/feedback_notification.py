from __future__ import annotations

import html
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from loguru import logger

from argus.domain.resend_email import send_resend_email
from argus.domain.store import utcnow

FEEDBACK_NOTIFICATION_RECIPIENT = "support@get-argus.com"
_SUBJECT_EXCERPT_LENGTH = 80
_MAX_RECEIPT_LENGTH = 256


@dataclass(frozen=True)
class FeedbackNotification:
    subject: str
    plain_text: str
    html: str


def _context_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def build_feedback_notification(
    *,
    feedback_type: str,
    message: str,
    context: Mapping[str, Any],
    account_kind: str,
    language: str,
) -> FeedbackNotification:
    # The excerpt is user text in a header, so every line break collapses.
    excerpt = " ".join(message.split())[:_SUBJECT_EXCERPT_LENGTH]
    context_lines = [f"  {key}: {_context_text(value)}" for key, value in context.items()]
    plain_text = "\n".join(
        [
            "New feedback was submitted in Argus.",
            "",
            f"Type: {feedback_type}",
            f"Account: {account_kind}",
            f"Language: {language}",
            f"Submitted: {utcnow().isoformat()}",
            "",
            "Message:",
            message,
            "",
            "Context:",
            *(context_lines or ["  none"]),
        ]
    )
    return FeedbackNotification(
        subject=f"Argus feedback ({feedback_type}): {excerpt}",
        plain_text=plain_text,
        html=(
            '<pre style="font-family:Arial,Helvetica,sans-serif;'
            f'white-space:pre-wrap;">{html.escape(plain_text)}</pre>'
        ),
    )


def notify_feedback_submitted(
    *,
    feedback_type: str,
    message: str,
    context: Mapping[str, Any],
    account_kind: str,
    language: str,
) -> None:
    """Email support about one saved submission; delivery never fails it."""

    try:
        notification = build_feedback_notification(
            feedback_type=feedback_type,
            message=message,
            context=context,
            account_kind=account_kind,
            language=language,
        )
        receipt = send_resend_email(
            recipient=FEEDBACK_NOTIFICATION_RECIPIENT,
            subject=notification.subject,
            plain_text=notification.plain_text,
            html=notification.html,
        )
    except Exception as exc:
        logger.warning(
            "Feedback notification failed",
            feedback_type=feedback_type,
            error_type=type(exc).__name__,
        )
        return
    logger.info(
        "Feedback notification sent",
        feedback_type=feedback_type,
        provider_receipt=receipt[:_MAX_RECEIPT_LENGTH],
    )
