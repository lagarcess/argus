"""The hub's ``SourceAdapter`` for Gmail: provider-side revocation.

Disconnect posts the refresh token to Google's revocation endpoint, which ends
the grant. A token Google no longer knows (``invalid_token``) is already
revoked, so that counts as success; any other failure raises and the hub
reports it while still deleting the local credential. The connection's sender
allowlist is deleted either way: it has no use once the mailbox is gone.
"""

from __future__ import annotations

from argus.domain.ingestion.connections import SourceConnection
from argus.domain.ingestion.gmail.client import GmailClient, GmailError
from argus.domain.ingestion.gmail.senders import SenderRepository


class GmailRevocationUnavailable(RuntimeError):
    pass


class GmailAdapter:
    source = "gmail"

    def __init__(self, client: GmailClient, senders: SenderRepository) -> None:
        self.client = client
        self.senders = senders

    def revoke(self, connection: SourceConnection, credential: str | None) -> None:
        try:
            if not credential:
                raise GmailRevocationUnavailable("no readable refresh token")
            try:
                self.client.revoke(credential)
            except GmailError as exc:
                if exc.status == 400 and "invalid_token" in exc.reasons:
                    return
                raise GmailRevocationUnavailable(exc.reason) from None
        finally:
            self.senders.delete(connection_id=connection.id)
