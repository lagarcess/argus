"""Acknowledgement replies: pure composition, sending behind a transport.

Replies are free-form text sent as an answer to the person's own message, so
they always fall inside WhatsApp's 24-hour customer service window. Nothing
here starts a conversation; that would need an approved template, so intake
never sends outside the window.

Spanish comes first. When the owner's language is English, the English line
follows. A sender with no linked owner gets Spanish only.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from argus.domain.ingestion.whatsapp.media import GRAPH_HOST

_RESEND = (
    "No pudimos guardar el archivo. Envíalo de nuevo.",
    "We could not save the file. Please send it again.",
)

REPLIES: dict[str, tuple[str, str]] = {
    "captured": (
        "Recibimos tu recibo. Revísalo en Cuadrao: {review_url}",
        "We received your receipt. Review it in Cuadrao: {review_url}",
    ),
    "linked": (
        "Listo. Este WhatsApp quedó conectado a Cuadrao. Envía la foto o el PDF de un recibo.",
        "Done. This WhatsApp is now connected to Cuadrao. Send a photo or PDF of a receipt.",
    ),
    "whatsapp_link_code_invalid": (
        "Ese código ya no es válido. Crea uno nuevo en Cuadrao.",
        "That code is no longer valid. Create a new one in Cuadrao.",
    ),
    "whatsapp_sender_not_linked": (
        "Este número no está conectado a Cuadrao. Conéctalo desde la app web de Cuadrao.",
        "This number is not connected to Cuadrao. Connect it from the Cuadrao web app.",
    ),
    "whatsapp_receipt_missing": (
        "Envía la foto o el PDF del recibo.",
        "Send a photo or PDF of the receipt.",
    ),
    "whatsapp_media_unsupported": (
        "Cuadrao solo recibe fotos JPG o PNG y archivos PDF.",
        "Cuadrao only accepts JPG or PNG photos and PDF files.",
    ),
    "whatsapp_media_too_large": (
        "El archivo pesa más de {limit_mb} MB. Envía uno más pequeño.",
        "The file is larger than {limit_mb} MB. Send a smaller one.",
    ),
    "whatsapp_media_invalid": (
        "No pudimos leer ese archivo. Envía otra foto o PDF del recibo.",
        "We could not read that file. Send another photo or PDF of the receipt.",
    ),
    "whatsapp_media_expired": _RESEND,
    "whatsapp_media_unavailable": _RESEND,
    "whatsapp_capture_failed": _RESEND,
}


_SAME_REPLY = {
    "whatsapp_media_untrusted": "whatsapp_media_unavailable",
    "whatsapp_processing_failed": "whatsapp_capture_failed",
}


def reply_key(status: str, error_code: str | None) -> str:
    """Captured and linked answer by status; everything else by its error code."""

    key = error_code if status in ("rejected", "failed") and error_code else status
    return _SAME_REPLY.get(key, key)


def review_url(app_origin: str, connection_id: str) -> str:
    return f"{app_origin.rstrip('/')}/biz?receipt={connection_id}"


def compose_reply(
    key: str,
    *,
    language: str | None,
    review_url: str | None = None,
    limit_mb: int = 10,
) -> str:
    spanish, english = REPLIES[key]
    values = {"review_url": review_url or "", "limit_mb": limit_mb}
    lines = [spanish.format(**values)]
    if language == "en":
        lines.append(english.format(**values))
    return "\n\n".join(lines)


def reply_payload(*, to: str, in_reply_to: str, body: str) -> dict[str, Any]:
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "context": {"message_id": in_reply_to},
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }


class ReplyTransport(Protocol):
    async def send(self, payload: dict[str, Any]) -> None: ...


class ReplyFailed(Exception):
    pass


class CloudApiTransport:
    """``POST /{phone-number-id}/messages``; only built when outbound is enabled."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        access_token: str,
        phone_number_id: str,
        graph_api_version: str,
    ) -> None:
        self._client = client
        self._url = f"https://{GRAPH_HOST}/{graph_api_version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def send(self, payload: dict[str, Any]) -> None:
        try:
            response = await self._client.post(
                self._url, json=payload, headers=self._headers, timeout=10.0
            )
        except httpx.HTTPError:
            raise ReplyFailed("transport") from None
        if response.status_code >= 300:
            raise ReplyFailed(str(response.status_code))
