"""One configuration seam for the Gmail connector.

``GOOGLE_OAUTH_CLIENT_ID``, ``GOOGLE_OAUTH_CLIENT_SECRET`` and
``GOOGLE_OAUTH_REDIRECT_URI`` describe the founder's Google Cloud OAuth web
client. Gmail stays off unless all three are set. The client secret is sent
only in token-endpoint request bodies and is never logged or returned.

The redirect URI is a page of the web app: Google sends the browser there with
``code`` and ``state``, and the app posts both to the authenticated callback
route, so the exchange always happens under the person's own session.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from argus.domain.ingestion.secrets import KEY_ENV

# The narrowest Gmail scope that can read message bodies and attachments.
# No ``openid email``: users.getProfile returns the address under this scope.
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
DEFAULT_LOOKBACK_DAYS = 90
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})


@dataclass(frozen=True)
class GmailConfig:
    client_id: str = ""
    client_secret: str = field(default="", repr=False)
    redirect_uri: str = ""
    lookback_days: int = DEFAULT_LOOKBACK_DAYS

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)


def gmail_config_from_env() -> GmailConfig:
    redirect = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    if redirect:
        parts = urlsplit(redirect)
        secure = parts.scheme == "https" or (
            parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS
        )
        if not secure or not parts.hostname or parts.fragment:
            raise ValueError(
                "GOOGLE_OAUTH_REDIRECT_URI must be an https URL (http only for localhost)"
            )
    return GmailConfig(
        client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip(),
        client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip(),
        redirect_uri=redirect,
    )


def mailbox_ref_key_from_env() -> bytes | None:
    """A digest key derived from the ingestion secret key (HKDF-SHA256).

    Rotating ``ARGUS_INGESTION_SECRET_KEY`` already invalidates stored
    connections, so tying the mailbox digest to it adds no new rotation duty.
    """

    raw = os.getenv(KEY_ENV, "").strip()
    if not raw:
        return None
    try:
        key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (binascii.Error, ValueError):
        return None
    if len(key) != 32:
        return None
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"argus-ingestion:gmail:mailbox-ref",
    ).derive(key)


def normalize_address(address: str) -> str:
    return address.strip().lower()


def mailbox_ref(address: str, key: bytes) -> str:
    """Keyed digest of the mailbox: stable, comparable, not reversible by
    guessing addresses without the server key."""

    digest = hmac.new(
        key, b"gmail-mailbox:" + normalize_address(address).encode(), hashlib.sha256
    )
    return "gm_" + digest.hexdigest()


def masked_label(address: str) -> str:
    """``j***@gmail.com``: enough for the person to recognize the mailbox."""

    local, _, domain = normalize_address(address).partition("@")
    head = local[:1] or "*"
    return f"{head}***@{domain}"[:80]
