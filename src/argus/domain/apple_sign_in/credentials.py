"""Capture and revoke the Apple refresh token account deletion needs.

Capture runs right after a native Sign in with Apple. The app sends Apple's
one-time authorization code; the API exchanges it with Apple, checks that the
token belongs to the Apple identity linked to the signed-in Supabase user, and
keeps only the refresh token, sealed by ``SecretBox`` and bound to
``apple_sign_in:<user_id>``. One row per person; a later sign-in replaces it.
An older token is not revoked on replacement: revoking any token ends the
person's whole Apple authorization for the app, including the new one.

Apple has already consumed the one-time code by the time anything can go
wrong locally, so a token that can't be kept is never just dropped: on a
subject mismatch or a storage failure, capture revokes it at Apple right away
(best effort). The person's next Apple sign-in then asks again and yields a
fresh code, instead of leaving an Apple authorization nothing can revoke.

Revoke is what the account-deletion lane calls. It opens the stored token,
asks Apple to revoke it, and deletes the row only after Apple answers 200, and
only if the row still holds the token that was revoked. Apple's
``invalid_grant`` means the token is already dead (revoked from the person's
Apple ID settings, or expired), so that counts as revoked too. Revoke always
sends the stored client id with a secret signed for it, so a client mismatch
is not how it arises here, and no retry could ever turn an ``invalid_grant``
token into a 200: keeping it would only block deletion forever. Any other
failure leaves the row in place: that row is the pending revoke, retried by
calling again.

``discard_unreadable`` is the way out when the token can't be opened, because
``ARGUS_INGESTION_SECRET_KEY`` was rotated. Nothing can revoke it then, and
the restrict key would otherwise keep that user undeletable forever. It
deletes the row only if it is still unreadable, and never touches a token it
could still revoke. No route exposes either; Lane 6 calls them. The user id
always comes from the caller's verified session, never from a body. Nothing
here logs a token.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock, Thread
from typing import Protocol

from loguru import logger

from argus.domain.apple_sign_in.client import (
    DISCARD_TIMEOUT_SECONDS,
    AppleAuthClient,
    AppleError,
)
from argus.domain.ingestion.secrets import SecretBox, SecretUnreadable

SOURCE = "apple_sign_in"
# The most a compensating revoke may add to the person's capture request. The
# Apple client bounds the body; this bounds everything, slow headers included.
DISCARD_DEADLINE_SECONDS = 2 * DISCARD_TIMEOUT_SECONDS


class AppleIdentityMismatch(RuntimeError):
    """The code's Apple subject is not the signed-in user's Apple identity."""


class AppleCaptureNotStored(RuntimeError):
    """The exchanged token couldn't be stored; it was revoked instead."""


class AppleRevocationPending(RuntimeError):
    """Apple did not confirm the revoke; the sealed token stays for a retry."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"apple revocation pending: {reason}")
        self.reason = reason


class RevokeOutcome(str, Enum):
    REVOKED = "revoked"
    # Apple answered invalid_grant: the token was already dead, row removed.
    ALREADY_REVOKED = "already_revoked"
    NOTHING_STORED = "nothing_stored"


class DiscardOutcome(str, Enum):
    # The row was unreadable under the current key and is gone.
    DISCARDED = "discarded"
    NOTHING_STORED = "nothing_stored"
    # The token opens, so it can and must be revoked instead; nothing deleted.
    READABLE = "readable"


@dataclass(frozen=True)
class StoredAppleCredential:
    user_id: str
    client_id: str
    secret_ciphertext: bytes = field(repr=False)
    captured_at: datetime
    updated_at: datetime


class AppleCredentialRepository(Protocol):
    def upsert(
        self, *, user_id: str, client_id: str, secret_ciphertext: bytes, now: datetime
    ) -> None: ...

    def get(self, *, user_id: str) -> StoredAppleCredential | None: ...

    def delete_if_unchanged(self, *, user_id: str, secret_ciphertext: bytes) -> bool:
        """Delete only while the row still holds this exact envelope."""
        ...


class InMemoryAppleCredentialRepository:
    def __init__(self) -> None:
        self._rows: dict[str, StoredAppleCredential] = {}
        self._lock = Lock()

    def upsert(
        self, *, user_id: str, client_id: str, secret_ciphertext: bytes, now: datetime
    ) -> None:
        with self._lock:
            existing = self._rows.get(user_id)
            self._rows[user_id] = StoredAppleCredential(
                user_id=user_id,
                client_id=client_id,
                secret_ciphertext=secret_ciphertext,
                captured_at=existing.captured_at if existing else now,
                updated_at=now,
            )

    def get(self, *, user_id: str) -> StoredAppleCredential | None:
        with self._lock:
            return self._rows.get(user_id)

    def delete_if_unchanged(self, *, user_id: str, secret_ciphertext: bytes) -> bool:
        with self._lock:
            row = self._rows.get(user_id)
            if row is None or row.secret_ciphertext != secret_ciphertext:
                return False
            del self._rows[user_id]
            return True


class AppleCredentialService:
    def __init__(
        self,
        repository: AppleCredentialRepository,
        *,
        box: SecretBox,
        client: AppleAuthClient,
        clock: Callable[[], datetime],
        discard_deadline: float = DISCARD_DEADLINE_SECONDS,
    ) -> None:
        self.repository = repository
        self._box = box
        self._client = client
        self._clock = clock
        self._discard_deadline = discard_deadline

    def close(self) -> None:
        self._client.close()

    def capture(
        self, *, user_id: str, apple_subject: str, authorization_code: str
    ) -> None:
        """Raises ``AppleError`` (Apple refused or is unreachable),
        ``AppleIdentityMismatch`` or ``AppleCaptureNotStored``; nothing is
        stored in any of those cases."""

        grant = self._client.exchange_code(authorization_code)
        if grant.subject != apple_subject:
            self._discard(grant.refresh_token, reason="identity_mismatch")
            raise AppleIdentityMismatch("apple subject does not match the user")
        try:
            self.repository.upsert(
                user_id=user_id,
                client_id=self._client.config.client_id,
                secret_ciphertext=self._box.seal(
                    grant.refresh_token, source=SOURCE, connection_id=user_id
                ),
                now=self._clock(),
            )
        except Exception as exc:  # noqa: BLE001 - any storage failure loses the token
            self._discard(grant.refresh_token, reason="storage_unavailable")
            raise AppleCaptureNotStored(type(exc).__name__) from None

    def _discard(self, refresh_token: str, *, reason: str) -> None:
        """Revoke a token that won't be stored, so none is left unrevocable.

        This runs inside the person's capture request, so it gets one short
        attempt, on a worker thread the request waits for at most
        ``discard_deadline`` seconds. It never raises: the caller's own outcome
        (409 or 503) stands.
        """

        worker = Thread(
            target=self._revoke_unstored,
            args=(refresh_token, reason),
            name="apple-discard-revoke",
            daemon=True,
        )
        worker.start()
        worker.join(self._discard_deadline)
        if worker.is_alive():
            logger.warning(
                "Apple token discard still waiting on Apple; request released",
                reason=reason,
            )

    def _revoke_unstored(self, refresh_token: str, reason: str) -> None:
        try:
            self._client.revoke(
                refresh_token,
                client_id=self._client.config.client_id,
                timeout=DISCARD_TIMEOUT_SECONDS,
                attempts=1,
            )
        except AppleError as exc:
            logger.warning(
                "Apple token discarded without revoke",
                reason=reason,
                apple_reason=exc.reason,
            )
        except Exception as exc:  # noqa: BLE001 - never turn the outcome into a 500
            logger.warning(
                "Apple token discarded without revoke",
                reason=reason,
                error=type(exc).__name__,
            )

    def revoke(self, *, user_id: str) -> RevokeOutcome:
        """Raises ``AppleRevocationPending`` while the token is kept for retry."""

        row = self.repository.get(user_id=user_id)
        if row is None:
            return RevokeOutcome.NOTHING_STORED
        try:
            token = self._box.open(
                row.secret_ciphertext, source=SOURCE, connection_id=user_id
            )
        except SecretUnreadable:
            raise AppleRevocationPending("credential_unreadable") from None
        outcome = RevokeOutcome.REVOKED
        try:
            self._client.revoke(token, client_id=row.client_id)
        except AppleError as exc:
            if not exc.invalid_grant:
                raise AppleRevocationPending(exc.reason) from None
            outcome = RevokeOutcome.ALREADY_REVOKED
        self.repository.delete_if_unchanged(
            user_id=user_id, secret_ciphertext=row.secret_ciphertext
        )
        if self.repository.get(user_id=user_id) is not None:
            # A sign-in replaced the token while this revoke was in flight.
            # Apple ended the whole authorization, but only a confirmed revoke
            # of the token now stored may clear it, so the caller retries.
            raise AppleRevocationPending("credential_replaced")
        return outcome

    def discard_unreadable(self, *, user_id: str) -> DiscardOutcome:
        """Delete this user's row only while its token can't be opened.

        For Lane 6 after ``revoke`` raised ``credential_unreadable`` (the key
        was rotated). Apple's authorization for the app then stays until the
        person removes it in their Apple ID settings; no token here could end
        it. Compare-and-delete, so a token captured meanwhile is kept and
        reported ``READABLE``.
        """

        for _ in range(3):
            row = self.repository.get(user_id=user_id)
            if row is None:
                return DiscardOutcome.NOTHING_STORED
            try:
                self._box.open(
                    row.secret_ciphertext, source=SOURCE, connection_id=user_id
                )
            except SecretUnreadable:
                pass
            else:
                return DiscardOutcome.READABLE
            if self.repository.delete_if_unchanged(
                user_id=user_id, secret_ciphertext=row.secret_ciphertext
            ):
                logger.warning(
                    "Unreadable Apple credential discarded without revoke",
                    outcome=DiscardOutcome.DISCARDED.value,
                )
                return DiscardOutcome.DISCARDED
        # Replaced on every pass: hand the decision back to revoke.
        raise AppleRevocationPending("credential_replaced")
