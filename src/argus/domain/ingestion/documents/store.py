"""Owner-scoped source drafts and immutable preparation checkpoints."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Protocol

from argus.domain.ingestion.connections import (
    LIVE,
    ConnectionNotFound,
    InMemoryConnectionRepository,
)
from argus.domain.ingestion.documents.models import DocumentDraft, ExtractionBatch


class DocumentStore(Protocol):
    def get(self, *, user_id: str, connection_id: str) -> ExtractionBatch | None: ...
    def draft(self, *, user_id: str, connection_id: str) -> DocumentDraft | None: ...
    def source(self, *, user_id: str, connection_id: str) -> bytes | None: ...
    def capture(self, *, user_id: str, draft: DocumentDraft, content: bytes) -> bool: ...
    def update(
        self,
        *,
        user_id: str,
        draft: DocumentDraft,
        expected_version: int,
        holder: str | None = None,
    ) -> bool: ...
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
        self._drafts: dict[tuple[str, str], str] = {}
        self._sources: dict[tuple[str, str], bytes] = {}
        self._lock = threading.RLock()

    def _live(
        self,
        user_id: str,
        connection_id: str,
        holder: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        try:
            row = self.connections.get(user_id=user_id, connection_id=connection_id)
        except ConnectionNotFound:
            return False
        return (
            row.source == "statement"
            and row.status in LIVE
            and (
                holder is None
                or (
                    row.lease_holder == holder
                    and row.lease_until is not None
                    and now is not None
                    and row.lease_until > now
                )
            )
        )

    def get(self, *, user_id: str, connection_id: str) -> ExtractionBatch | None:
        with self.connections._lock, self._lock:
            raw = (
                self._rows.get((user_id, connection_id))
                if self._live(user_id, connection_id)
                else None
            )
            return ExtractionBatch.model_validate_json(raw) if raw is not None else None

    def draft(self, *, user_id: str, connection_id: str) -> DocumentDraft | None:
        with self.connections._lock, self._lock:
            raw = (
                self._drafts.get((user_id, connection_id))
                if self._live(user_id, connection_id)
                else None
            )
            return DocumentDraft.model_validate_json(raw) if raw is not None else None

    def source(self, *, user_id: str, connection_id: str) -> bytes | None:
        with self.connections._lock, self._lock:
            return (
                self._sources.get((user_id, connection_id))
                if self._live(user_id, connection_id)
                else None
            )

    def capture(self, *, user_id: str, draft: DocumentDraft, content: bytes) -> bool:
        with self.connections._lock, self._lock:
            if not self._live(user_id, draft.connection_id):
                return False
            key = (user_id, draft.connection_id)
            if key not in self._drafts:
                if key in self._rows:
                    draft = draft.model_copy(update={"status": "review_ready"})
                self._drafts[key] = draft.model_dump_json()
                self._sources[key] = content
            return True

    def update(
        self,
        *,
        user_id: str,
        draft: DocumentDraft,
        expected_version: int,
        holder: str | None = None,
    ) -> bool:
        with self.connections._lock, self._lock:
            raw = self._drafts.get((user_id, draft.connection_id))
            previous = DocumentDraft.model_validate_json(raw) if raw else None
            if (
                not self._live(user_id, draft.connection_id, holder, draft.updated_at)
                or previous is None
                or previous.version != expected_version
            ):
                return False
            lease = self.connections.get(
                user_id=user_id, connection_id=draft.connection_id
            ).lease_until
            if (
                draft.error_code == "document_preparation_interrupted"
                and lease is not None
                and lease > draft.updated_at
            ):
                return False
            self._drafts[(user_id, draft.connection_id)] = draft.model_dump_json()
            return True

    def save(
        self,
        *,
        user_id: str,
        connection_id: str,
        holder: str,
        now: datetime,
        batch: ExtractionBatch,
    ) -> bool:
        with self.connections._lock, self._lock:
            if not self._live(user_id, connection_id, holder, now):
                return False
            self._rows.setdefault((user_id, connection_id), batch.model_dump_json())
            return True

    def forget(self, *, user_id: str, connection_id: str) -> None:
        with self._lock:
            key = (user_id, connection_id)
            self._rows.pop(key, None)
            self._drafts.pop(key, None)
            self._sources.pop(key, None)
