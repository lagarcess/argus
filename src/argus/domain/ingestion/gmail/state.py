"""OAuth ``state``: sealed, bound to the person, expiring and single-use.

The state carries a random nonce, the PKCE verifier, the person's user id and
an expiry, sealed with the ingestion ``SecretBox`` (AES-256-GCM) whose
associated data names the same person. So:

- a forged or altered state does not open (integrity);
- a state started by one person does not open under another person's session,
  which is what defeats login CSRF (an attacker's code cannot be attached to
  the victim's account);
- the PKCE verifier is unreadable to the browser and to Google, and is never
  stored in a database;
- an expired state is refused, and a ledger refuses a nonce seen twice.

The in-memory ledger is per process. Behind several API instances a replayed
state could reach a fresh instance; it still needs Google's single-use
authorization code issued for the same PKCE challenge, which Google refuses on
a second exchange. A shared ledger is a production follow-up.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal, Protocol

from argus.domain.ingestion.secrets import SecretBox, SecretUnreadable

STATE_TTL = timedelta(minutes=10)
MAX_STATE_CHARS = 1024
_AAD_SOURCE = "gmail_oauth_state"
_LEDGER_CAP = 10_000

StateFailure = Literal["invalid", "expired", "replayed"]


class StateRejected(RuntimeError):
    def __init__(self, reason: StateFailure) -> None:
        super().__init__(f"oauth state {reason}")
        self.reason = reason


class StateLedger(Protocol):
    def consume(self, nonce: str, *, expires_at: datetime, now: datetime) -> bool:
        """True the first time a nonce is presented before it expires."""
        ...


class InMemoryStateLedger:
    def __init__(self) -> None:
        self._seen: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def consume(self, nonce: str, *, expires_at: datetime, now: datetime) -> bool:
        with self._lock:
            for key in [k for k, until in self._seen.items() if until <= now]:
                del self._seen[key]
            if nonce in self._seen:
                return False
            if len(self._seen) >= _LEDGER_CAP:
                # Refuse rather than forget: a full ledger must not reopen replay.
                return False
            self._seen[nonce] = expires_at
            return True


@dataclass(frozen=True)
class PendingAuthorization:
    state: str
    code_challenge: str
    expires_at: datetime
    verifier: str = field(repr=False)


class OAuthStates:
    def __init__(
        self, box: SecretBox, ledger: StateLedger, clock: Callable[[], datetime]
    ) -> None:
        self.box = box
        self.ledger = ledger
        self.clock = clock

    def issue(self, *, user_id: str) -> PendingAuthorization:
        now = self.clock()
        expires_at = now + STATE_TTL
        verifier = _b64(secrets.token_bytes(48))  # 64 chars, RFC 7636 range
        body = json.dumps(
            {
                "n": _b64(secrets.token_bytes(18)),
                "v": verifier,
                "u": user_id,
                "e": int(expires_at.timestamp()),
            },
            separators=(",", ":"),
        )
        sealed = self.box.seal(body, source=_AAD_SOURCE, connection_id=user_id)
        return PendingAuthorization(
            state=_b64(sealed),
            code_challenge=challenge(verifier),
            expires_at=expires_at,
            verifier=verifier,
        )

    def redeem(self, *, user_id: str, state: str) -> str:
        """The PKCE verifier for a valid, unexpired, first-use state."""

        if not state or len(state) > MAX_STATE_CHARS:
            raise StateRejected("invalid")
        try:
            envelope = base64.urlsafe_b64decode(state + "=" * (-len(state) % 4))
            body = json.loads(
                self.box.open(envelope, source=_AAD_SOURCE, connection_id=user_id)
            )
            nonce, verifier, owner, expiry = (
                str(body["n"]),
                str(body["v"]),
                str(body["u"]),
                int(body["e"]),
            )
        except (SecretUnreadable, binascii.Error, ValueError, KeyError, TypeError):
            raise StateRejected("invalid") from None
        if owner != user_id:
            raise StateRejected("invalid")
        now = self.clock()
        expires_at = datetime.fromtimestamp(expiry, tz=now.tzinfo)
        if expires_at <= now:
            raise StateRejected("expired")
        if not self.ledger.consume(nonce, expires_at=expires_at, now=now):
            raise StateRejected("replayed")
        return verifier


def challenge(verifier: str) -> str:
    """PKCE S256: base64url(sha256(verifier)) without padding."""

    return _b64(hashlib.sha256(verifier.encode()).digest())


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")
