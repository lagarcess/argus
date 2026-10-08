"""Webhook signatures, keyed digests and one-time link codes.

Phone numbers, provider message ids and link codes are only ever stored as
HMAC-SHA256 digests under ``ARGUS_WHATSAPP_SENDER_KEY``. A plain hash of a
phone number is reversible by enumeration; a keyed one is not without the key.
Logs carry ``ref``, a short prefix of a digest, and never the value itself.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

SIGNATURE_PREFIX = "sha256="
LINK_WORD = "CUADRAO"
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"
CODE_LENGTH = 8


def signature_matches(app_secret: str, header: str | None, body: bytes) -> bool:
    """``X-Hub-Signature-256`` is HMAC-SHA256 of the raw body under the app secret."""

    if not header or not header.startswith(SIGNATURE_PREFIX):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    supplied = header[len(SIGNATURE_PREFIX) :].strip().lower()
    return hmac.compare_digest(expected.encode(), supplied.encode("utf-8", "replace"))


class WhatsAppKeys:
    def __init__(self, sender_key: str) -> None:
        self._key = sender_key.encode()

    def _digest(self, domain: str, value: str) -> bytes:
        return hmac.new(
            self._key, f"argus-whatsapp-{domain}:v1:{value}".encode(), hashlib.sha256
        ).digest()

    def sender(self, wa_id: str) -> bytes:
        return self._digest("sender", wa_id)

    def message(self, provider_message_id: str) -> bytes:
        return self._digest("message", provider_message_id)

    def code(self, code: str) -> bytes:
        return self._digest("link-code", code)


def ref(digest: bytes) -> str:
    return digest.hex()[:12]


def last4(wa_id: str) -> str:
    return wa_id[-4:]


def mint_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def link_message(code: str) -> str:
    return f"{LINK_WORD} {code}"


def link_code_in(text: str) -> str | None:
    """The code when ``text`` is exactly the link protocol token, else ``None``.

    This is a fixed two-word protocol the web app writes for the person, not an
    interpretation of what they meant.
    """

    parts = text.split()
    if len(parts) != 2 or parts[0].upper() != LINK_WORD:
        return None
    code = parts[1].upper()
    if len(code) != CODE_LENGTH or any(ch not in CODE_ALPHABET for ch in code):
        return None
    return code


def looks_like_link_attempt(text: str) -> bool:
    parts = text.split()
    return bool(parts) and parts[0].upper() == LINK_WORD
