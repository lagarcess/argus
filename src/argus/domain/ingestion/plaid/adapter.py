"""The hub's ``SourceAdapter`` for Plaid: provider-side revocation.

Disconnect calls ``/item/remove`` with the Item's access token, which ends
Plaid's access and billing for the Item. An Item Plaid no longer knows is
already revoked, so that answer counts as success; any other failure raises and
the hub reports it while still deleting the local credential.
"""

from __future__ import annotations

from argus.domain.ingestion.connections import SourceConnection
from argus.domain.ingestion.plaid.client import PlaidClient, PlaidError

_ALREADY_GONE = frozenset({"ITEM_NOT_FOUND", "INVALID_ACCESS_TOKEN"})


class PlaidRevocationUnavailable(RuntimeError):
    pass


class PlaidAdapter:
    source = "plaid"

    def __init__(self, client: PlaidClient) -> None:
        self.client = client

    def revoke(self, connection: SourceConnection, credential: str | None) -> None:
        if not credential:
            raise PlaidRevocationUnavailable("no readable access token")
        try:
            self.client.item_remove(credential)
        except PlaidError as exc:
            if exc.error_code in _ALREADY_GONE:
                return
            raise PlaidRevocationUnavailable(exc.error_code) from None
