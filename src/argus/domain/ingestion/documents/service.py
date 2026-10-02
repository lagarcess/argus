"""Document extraction feeds reviewed evidence, never canonical money writes."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from argus.domain.ingestion.connections import (
    LIVE,
    ConnectionNotFound,
    DuplicateConnection,
    SourceConnection,
)
from argus.domain.ingestion.contract import SourceKind
from argus.domain.ingestion.documents.models import ExtractionBatch
from argus.domain.ingestion.documents.store import DocumentStore
from argus.domain.ingestion.hub import IngestionHub


class Extractor(Protocol):
    async def extract(
        self,
        *,
        content: bytes,
        filename: str,
        media_type: str,
        connection_id: str,
        observed_at: datetime,
    ) -> ExtractionBatch: ...


class DocumentServiceError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class DocumentOutcome:
    connection_id: str
    replayed: bool
    candidate_count: int
    status: Literal["review_ready"] = "review_ready"


class DocumentsService:
    source: SourceKind = "statement"

    def __init__(
        self, hub: IngestionHub, store: DocumentStore, extractor: Extractor
    ) -> None:
        self.hub = hub
        self.store = store
        self.extractor = extractor
        hub.register(self)

    def revoke(self, connection: SourceConnection, credential: str | None) -> None:
        """An uploaded document has no provider grant to revoke."""

    def forget(self, connection: SourceConnection) -> None:
        self.store.forget(user_id=connection.user_id, connection_id=connection.id)

    async def upload(
        self,
        *,
        user_id: str,
        content: bytes,
        filename: str,
        media_type: str,
    ) -> DocumentOutcome:
        if not content:
            raise DocumentServiceError("document_empty")
        digest = hashlib.sha256(content).hexdigest()
        external_ref = hashlib.sha256(f"{user_id}:{digest}".encode()).hexdigest()
        try:
            connection = self.hub.connections.create(
                user_id=user_id,
                source=self.source,
                external_ref=external_ref,
                label=filename,
                now=self.hub.clock(),
            )
        except DuplicateConnection as error:
            if error.elsewhere:
                raise DocumentServiceError("document_unavailable") from None
            connection = self.hub.connections.get(
                user_id=user_id,
                connection_id=error.existing_id,
            )
        return await self._run(connection, content, filename, media_type)

    async def resume(self, *, user_id: str, connection_id: str) -> DocumentOutcome:
        connection = self.hub.connections.get(
            user_id=user_id, connection_id=connection_id
        )
        if connection.source != self.source:
            raise ConnectionNotFound()
        return await self._run(connection, None, "", "")

    async def _run(
        self,
        connection: SourceConnection,
        content: bytes | None,
        filename: str,
        media_type: str,
    ) -> DocumentOutcome:
        if connection.status not in LIVE:
            raise DocumentServiceError("document_disconnected")
        if self.hub.sink is None:
            raise DocumentServiceError("document_unavailable", retryable=True)
        repo = self.hub.connections
        holder = str(uuid.uuid4())
        if not repo.lease(
            connection_id=connection.id, holder=holder, now=self.hub.clock()
        ):
            raise DocumentServiceError("document_busy", retryable=True)
        try:
            batch = self.store.get(
                user_id=connection.user_id, connection_id=connection.id
            )
            replayed = batch is not None
            if batch is None:
                if content is None:
                    raise DocumentServiceError("document_reupload_required")
                batch = await self.extractor.extract(
                    content=content,
                    filename=filename,
                    media_type=media_type,
                    connection_id=connection.id,
                    observed_at=self.hub.clock(),
                )
                self._validate(batch, connection.id)
                if not self.store.save(
                    user_id=connection.user_id,
                    connection_id=connection.id,
                    holder=holder,
                    now=self.hub.clock(),
                    batch=batch,
                ):
                    raise DocumentServiceError("document_lease_lost", retryable=True)
                # An existing checkpoint always wins, including after a crash.
                batch = self.store.get(
                    user_id=connection.user_id, connection_id=connection.id
                )
                if batch is None:
                    raise DocumentServiceError("document_lease_lost", retryable=True)
            self._validate(batch, connection.id)
            if not repo.renew(
                connection_id=connection.id, holder=holder, now=self.hub.clock()
            ):
                raise DocumentServiceError("document_lease_lost", retryable=True)
            try:
                result = self.hub.sink.submit(
                    user_id=connection.user_id,
                    connection_id=connection.id,
                    candidates=batch.candidates,
                )
            except Exception:
                raise DocumentServiceError(
                    "document_delivery_failed", retryable=True
                ) from None
            if result.ignored:
                raise DocumentServiceError("document_disconnected")
            if not repo.record_success(
                connection_id=connection.id,
                holder=holder,
                expected_cursor=connection.cursor,
                cursor="delivered",
                now=self.hub.clock(),
            ):
                raise DocumentServiceError("document_lease_lost", retryable=True)
            return DocumentOutcome(connection.id, replayed, len(batch.candidates))
        except Exception as error:
            code = (
                error.code
                if isinstance(error, DocumentServiceError)
                else "document_extraction_failed"
            )
            try:
                repo.record_failure(
                    connection_id=connection.id,
                    holder=holder,
                    code=code,
                    status="error",
                    now=self.hub.clock(),
                )
            except ConnectionNotFound:
                pass
            raise
        finally:
            repo.release(connection_id=connection.id, holder=holder)

    @staticmethod
    def _validate(batch: ExtractionBatch, connection_id: str) -> None:
        if not batch.candidates:
            raise DocumentServiceError("document_no_evidence")
        keys = set()
        for candidate in batch.candidates:
            if (
                candidate.source.source != "statement"
                or candidate.source.connection_id != connection_id
                or candidate.status == "removed"
                or candidate.source.replaces_external_id is not None
                or candidate.key in keys
            ):
                raise DocumentServiceError("document_invalid_extraction")
            keys.add(candidate.key)
