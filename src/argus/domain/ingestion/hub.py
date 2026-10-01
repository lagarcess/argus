"""Connection lifecycle shared by every connector: list and disconnect.

Connectors register a ``SourceAdapter`` for provider-side revocation. The hub
owns the order that keeps disconnect truthful: try to revoke at the provider,
always delete the stored credential and cursor, then let reconciliation drop
unreviewed evidence. A provider outage cannot keep a credential alive here; it
is reported so the person can also revoke at the provider.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from loguru import logger

from argus.domain.ingestion.connections import (
    ConnectionRepository,
    SourceConnection,
)
from argus.domain.ingestion.contract import SourceKind
from argus.domain.ingestion.secrets import SecretBox
from argus.domain.ingestion.sink import CandidateSink

Revocation = Literal["revoked", "failed", "not_applicable"]


class SourceAdapter(Protocol):
    source: SourceKind

    def revoke(self, connection: SourceConnection, credential: str | None) -> None:
        """Revoke provider-side access. Raise on failure; never log the credential."""
        ...


class LocalCleanup(Protocol):
    """Optional adapter hook: delete connector-owned local state (a sender
    list, a device token digest) after the connection has ended."""

    def forget(self, connection: SourceConnection) -> None: ...


@dataclass(frozen=True)
class DisconnectOutcome:
    connection: SourceConnection
    provider_revocation: Revocation
    unreviewed_removed: int


class IngestionHub:
    def __init__(
        self,
        connections: ConnectionRepository,
        *,
        box: SecretBox | None,
        sink: CandidateSink | None,
        clock: Callable[[], datetime],
    ) -> None:
        self.connections = connections
        self.box = box
        self.sink = sink
        self.clock = clock
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters[adapter.source] = adapter

    def adapter(self, source: str) -> SourceAdapter | None:
        return self._adapters.get(source)

    def list(self, *, user_id: str) -> list[SourceConnection]:
        return self.connections.list(user_id=user_id)

    def credential(self, connection: SourceConnection) -> str | None:
        if connection.secret is None or self.box is None:
            return None
        return self.box.open(
            connection.secret, source=connection.source, connection_id=connection.id
        )

    def disconnect(self, *, user_id: str, connection_id: str) -> DisconnectOutcome:
        connection = self.connections.get(user_id=user_id, connection_id=connection_id)
        if connection.status == "disconnected":
            return DisconnectOutcome(connection, "not_applicable", 0)
        revocation: Revocation = "not_applicable"
        adapter = self._adapters.get(connection.source)
        if adapter is not None:
            try:
                adapter.revoke(connection, self.credential(connection))
                revocation = "revoked"
            except Exception as exc:
                revocation = "failed"
                logger.warning(
                    "Provider revocation failed; local credential is deleted anyway",
                    source=connection.source,
                    failure_mode=type(exc).__name__,
                )
        ended = self.connections.disconnect(
            user_id=user_id, connection_id=connection_id, now=self.clock()
        )
        cleanup = getattr(adapter, "forget", None)
        if cleanup is not None:
            cleanup(ended)
        removed = 0
        if self.sink is not None:
            removed = self.sink.forget_connection(
                user_id=user_id, connection_id=connection_id
            )
        return DisconnectOutcome(ended, revocation, removed)
