"""Plaid webhook verification, exactly as Plaid documents it.

1. The ``Plaid-Verification`` header is a JWS. Its header must say ``ES256``;
   any other algorithm (including ``none`` and HMAC) is refused before any key
   lookup.
2. The ``kid`` names a key fetched from ``/webhook_verification_key/get`` and
   cached. A cached key is refreshed after ``KEY_TTL``; a key whose
   ``expired_at`` is set is refused.
3. The signature is checked with that key, ES256 only.
4. ``iat`` must be within five minutes of now (old or far-future tokens fail).
5. ``request_body_sha256`` must equal the SHA-256 of the exact raw body bytes,
   compared in constant time.

Every refusal raises the same ``WebhookRejected`` so a caller cannot tell why;
the reason is logged as a short code. A token seen before inside its validity
window is reported as a duplicate so the caller can skip repeated work.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import jwt
from loguru import logger

from argus.domain.ingestion.plaid.client import UNREACHABLE, PlaidError

ALGORITHM = "ES256"
MAX_AGE = timedelta(minutes=5)
KEY_TTL = timedelta(hours=1)
MAX_TOKEN_CHARS = 4096
MAX_BODY_BYTES = 64 * 1024
_MAX_CACHED_KEYS = 32
_MAX_SEEN = 2048


class WebhookRejected(Exception):
    """Not a verified Plaid webhook. Deliberately carries no reason."""


class VerificationUnavailable(Exception):
    """Plaid's key endpoint could not be reached; the sender should retry."""


@dataclass(frozen=True)
class VerifiedWebhook:
    payload: dict[str, Any]
    duplicate: bool


class WebhookVerifier:
    def __init__(
        self,
        fetch_key: Callable[[str], dict[str, Any]],
        *,
        clock: Callable[[], datetime],
        key_ttl: timedelta = KEY_TTL,
    ) -> None:
        self._fetch_key = fetch_key
        self._clock = clock
        self._key_ttl = key_ttl
        self._keys: dict[str, tuple[dict[str, Any], datetime]] = {}
        self._seen: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def verify(self, token: str | None, body: bytes) -> VerifiedWebhook:
        if not token or len(token) > MAX_TOKEN_CHARS or len(body) > MAX_BODY_BYTES:
            raise _reject("malformed")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise _reject("malformed") from None
        if header.get("alg") != ALGORITHM:
            raise _reject("algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str) or not 0 < len(kid) <= 128:
            raise _reject("kid")
        jwk = self._key(kid)
        if jwk.get("expired_at") is not None:
            raise _reject("expired_key")
        try:
            key = jwt.PyJWK(jwk, algorithm=ALGORITHM).key
            claims = jwt.decode(
                token,
                key=key,
                algorithms=[ALGORITHM],
                options={"verify_iat": False, "verify_exp": False, "verify_aud": False},
            )
        except (jwt.PyJWTError, ValueError, TypeError):
            raise _reject("signature") from None
        now = self._clock()
        iat = claims.get("iat")
        if not isinstance(iat, int) or isinstance(iat, bool):
            raise _reject("iat")
        issued = datetime.fromtimestamp(iat, tz=now.tzinfo)
        if issued < now - MAX_AGE or issued > now + MAX_AGE:
            raise _reject("iat")
        claimed = claims.get("request_body_sha256")
        actual = hashlib.sha256(body).hexdigest()
        if not isinstance(claimed, str) or not hmac.compare_digest(
            claimed.encode(), actual.encode()
        ):
            raise _reject("body_hash")
        try:
            payload = json.loads(body)
        except ValueError:
            raise _reject("body") from None
        if not isinstance(payload, dict):
            raise _reject("body")
        return VerifiedWebhook(payload, self._remember(token, issued + MAX_AGE, now))

    def _key(self, kid: str) -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            cached = self._keys.get(kid)
        if cached is not None and cached[1] > now:
            return cached[0]
        try:
            jwk = self._fetch_key(kid)
        except PlaidError as exc:
            if exc.error_code == UNREACHABLE or (exc.status or 0) >= 500:
                raise VerificationUnavailable() from None
            raise _reject("unknown_key") from None
        with self._lock:
            if len(self._keys) >= _MAX_CACHED_KEYS:
                self._keys.pop(next(iter(self._keys)))
            self._keys[kid] = (jwk, now + self._key_ttl)
        return jwk

    def _remember(self, token: str, until: datetime, now: datetime) -> bool:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._lock:
            for seen, expiry in list(self._seen.items()):
                if expiry <= now:
                    del self._seen[seen]
            if digest in self._seen:
                return True
            if len(self._seen) >= _MAX_SEEN:
                self._seen.pop(next(iter(self._seen)))
            self._seen[digest] = until
            return False


def _reject(reason: str) -> WebhookRejected:
    logger.info("Plaid webhook rejected", reason=reason)
    return WebhookRejected()
