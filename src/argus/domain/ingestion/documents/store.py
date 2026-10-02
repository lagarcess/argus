"""Immutable extraction checkpoints used to replay candidate delivery."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Protocol

from argus.domain.ingestion.connections import (
    LIVE,
    ConnectionNotFound,
    InMemoryConnectionRepository,
)
from argus.domain.ingestion.documents.models import ExtractionBatch


class DocumentStore(Protocol):
    def get(self, *, user_id: str, connection_id: str) -> ExtractionBatch | None: ...

    def save(
        self,
        *,
        user_id: str,
        connection_id: str,
        holder: str,
        now: datetime,
        batch: ExtractionBatch,
    ) -> bool: ...

    def forget(self, *, user_id: str, connection_id: str) -> None: ...


class InMemoryDocumentStore:
    def __init__(self, connections: InMemoryConnectionRepository) -> None:
        self.connections = connections
        self._rows: dict[tuple[str, str], str] = {}
        self._lock = threading.Lock()

    def get(self, *, user_id: str, connection_id: str) -> ExtractionBatch | None:
        with self._lock:
            raw = self._rows.get((user_id, connection_id))
        return ExtractionBatch.model_validate_json(raw) if raw is not None else None

    def save(
        self,
        *,
        user_id: str,
        connection_id: str,
        holder: str,
        now: datetime,
        batch: ExtractionBatch,
    ) -> bool:
        # This shares the repository's disconnect/lease lock, like FOR UPDATE
        # on the connection row in the durable implementation.
        with self.connections._lock, self._lock:
            try:
                connection = self.connections.get(
                    user_id=user_id, connection_id=connection_id
                )
            except ConnectionNotFound:
                return False
            if (
                connection.source != "statement"
                or connection.status not in LIVE
                or connection.lease_holder != holder
                or connection.lease_until is None
                or connection.lease_until <= now
            ):
                return False
            self._rows.setdefault((user_id, connection_id), batch.model_dump_json())
            return True

    def forget(self, *, user_id: str, connection_id: str) -> None:
        with self._lock:
            self._rows.pop((user_id, connection_id), None)
