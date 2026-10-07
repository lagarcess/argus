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
from argus.domain.ingestion.documents.models import (
    DocumentDraft,
    ExtractionBatch,
    PreparationJob,
)


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
    def owner(self, *, connection_id: str) -> str | None: ...
    def job(self, *, user_id: str, connection_id: str) -> PreparationJob | None: ...
    def pending(self, *, limit: int) -> list[tuple[str, str]]:
        """Owner and connection of drafts awaiting preparation or a retry."""
        ...

    def advance(
        self,
        *,
        user_id: str,
        connection_id: str,
        now: datetime,
        expected_attempt_id: str | None,
        job: PreparationJob,
        draft: DocumentDraft | None = None,
    ) -> bool:
        """Replace the job (and draft) only while no lease is live, the current
        attempt is ``expected_attempt_id`` and the draft version is unchanged."""
        ...


class InMemoryDocumentStore:
    def __init__(self, connections: InMemoryConnectionRepository) -> None:
        self.connections = connections
        self._rows: dict[tuple[str, str], str] = {}
        self._drafts: dict[tuple[str, str], str] = {}
        self._sources: dict[tuple[str, str], bytes] = {}
        self._jobs: dict[tuple[str, str], str] = {}
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
            self._jobs.pop(key, None)

    def owner(self, *, connection_id: str) -> str | None:
        with self.connections._lock, self._lock:
            row = self.connections._rows.get(connection_id)
            if row is None or not self._live(row.user_id, connection_id):
                return None
            return row.user_id if (row.user_id, connection_id) in self._drafts else None

    def job(self, *, user_id: str, connection_id: str) -> PreparationJob | None:
        with self.connections._lock, self._lock:
            raw = (
                self._jobs.get((user_id, connection_id))
                if self._live(user_id, connection_id)
                else None
            )
            return PreparationJob.model_validate_json(raw) if raw is not None else None

    def pending(self, *, limit: int) -> list[tuple[str, str]]:
        with self.connections._lock, self._lock:
            rows = []
            for key, raw in self._drafts.items():
                draft = DocumentDraft.model_validate_json(raw)
                job = self._jobs.get(key)
                retry = job is not None and PreparationJob.model_validate_json(job).retry
                if self._live(*key) and (
                    draft.status in {"queued", "preparing"}
                    or (draft.status == "needs_attention" and retry)
                ):
                    rows.append((draft.created_at, key))
            return [key for _, key in sorted(rows)[:limit]]

    def advance(
        self,
        *,
        user_id: str,
        connection_id: str,
        now: datetime,
        expected_attempt_id: str | None,
        job: PreparationJob,
        draft: DocumentDraft | None = None,
    ) -> bool:
        key = (user_id, connection_id)
        with self.connections._lock, self._lock:
            if not self._live(user_id, connection_id) or key not in self._drafts:
                return False
            lease = self.connections.get(
                user_id=user_id, connection_id=connection_id
            ).lease_until
            current = self._jobs.get(key)
            current_id = (
                PreparationJob.model_validate_json(current).attempt_id
                if current is not None
                else None
            )
            previous = DocumentDraft.model_validate_json(self._drafts[key])
            if (
                (lease is not None and lease > now)
                or current_id != expected_attempt_id
                or (draft is not None and draft.version != previous.version + 1)
            ):
                return False
            if draft is not None:
                self._drafts[key] = draft.model_dump_json()
            self._jobs[key] = job.model_dump_json()
            return True
