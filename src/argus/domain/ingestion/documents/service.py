"""Capture first; preparation feeds reconciliation without financial writes."""

from __future__ import annotations

import asyncio
import hashlib
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from argus.domain.ingestion.connections import (
    LIVE,
    ConnectionNotFound,
    DuplicateConnection,
    SourceConnection,
)
from argus.domain.ingestion.contract import SourceKind
from argus.domain.ingestion.documents.models import (
    DocumentDraft,
    DraftProposal,
    DraftStatus,
    ExtractionBatch,
)
from argus.domain.ingestion.documents.preparation import validate_source
from argus.domain.ingestion.documents.store import DocumentStore
from argus.domain.ingestion.hub import IngestionHub


def lease_live(connection: SourceConnection, now: datetime) -> bool:
    return connection.lease_until is not None and connection.lease_until > now


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
        self.code, self.retryable = code, retryable


def stored_filename(filename: str) -> str:
    """Without control or format characters (bidi overrides included), so a
    stored name can neither break a log line nor disguise its extension."""

    kept = "".join(c for c in filename if unicodedata.category(c) not in ("Cc", "Cf"))
    return kept[:80] or "document"


@dataclass(frozen=True)
class DocumentOutcome:
    connection_id: str
    replayed: bool
    candidate_count: int
    status: DraftStatus = "saved"


class DocumentsService:
    source: SourceKind = "statement"

    def __init__(
        self,
        hub: IngestionHub,
        store: DocumentStore,
        extractor: Extractor,
        *,
        jobs_recover_interruptions: bool = False,
    ) -> None:
        self.hub, self.store, self.extractor = hub, store, extractor
        # With preparation jobs on, the job reconciler decides what an expired
        # attempt becomes; a read never settles it.
        self.jobs_recover_interruptions = jobs_recover_interruptions
        hub.register(self)

    def revoke(self, connection: SourceConnection, credential: str | None) -> None:
        """An uploaded document has no provider grant to revoke."""

    def forget(self, connection: SourceConnection) -> None:
        self.store.forget(user_id=connection.user_id, connection_id=connection.id)

    def _connection(self, user_id: str, connection_id: str) -> SourceConnection:
        row = self.hub.connections.get(user_id=user_id, connection_id=connection_id)
        if row.source != self.source:
            raise ConnectionNotFound()
        if row.status not in LIVE:
            raise DocumentServiceError("document_disconnected")
        return row

    def get(self, *, user_id: str, connection_id: str) -> DocumentDraft:
        connection = self._connection(user_id, connection_id)
        draft = self.store.draft(user_id=user_id, connection_id=connection_id)
        if draft is None:
            if self.store.get(user_id=user_id, connection_id=connection_id) is None:
                raise DocumentServiceError("document_source_unavailable")
            return DocumentDraft(
                connection_id=connection_id,
                filename="document",
                media_type="",
                sha256="",
                size_bytes=0,
                source_available=False,
                status="review_ready",
                created_at=connection.created_at,
                updated_at=connection.updated_at,
            )
        if (
            draft.status == "preparing"
            and not self.jobs_recover_interruptions
            and not lease_live(connection, self.hub.clock())
        ):
            draft = self._update(
                user_id,
                draft,
                status="needs_attention",
                error_code="document_preparation_interrupted",
            )
        return draft

    def source_bytes(self, *, user_id: str, connection_id: str) -> bytes:
        self._connection(user_id, connection_id)
        content = self.store.source(user_id=user_id, connection_id=connection_id)
        if content is None:
            raise DocumentServiceError("document_source_unavailable")
        return content

    def _update(
        self,
        user_id: str,
        draft: DocumentDraft,
        *,
        holder: str | None = None,
        **changes: object,
    ) -> DocumentDraft:
        updated = self.revise(draft, **changes)
        if not self.store.update(
            user_id=user_id, draft=updated, expected_version=draft.version, holder=holder
        ):
            raise DocumentServiceError("document_version_conflict", retryable=True)
        return updated

    def revise(self, draft: DocumentDraft, **changes: object) -> DocumentDraft:
        return draft.model_copy(
            update={
                **changes,
                "version": draft.version + 1,
                "updated_at": self.hub.clock(),
            }
        )

    def update_proposal(
        self, *, user_id: str, connection_id: str, version: int, proposal: DraftProposal
    ) -> DocumentDraft:
        draft = self.get(user_id=user_id, connection_id=connection_id)
        if version != draft.version or draft.status == "preparing":
            raise DocumentServiceError("document_version_conflict", retryable=True)
        return self._update(user_id, draft, proposal=proposal)

    async def upload(
        self,
        *,
        user_id: str,
        content: bytes,
        filename: str,
        media_type: str,
        consent: bool = False,
        proposal: DraftProposal | None = None,
    ) -> DocumentOutcome:
        validate_source(content, media_type)
        digest = hashlib.sha256(content).hexdigest()
        external_ref = hashlib.sha256(f"{user_id}:{digest}".encode()).hexdigest()
        replayed = False
        try:
            connection = self.hub.connections.create(
                user_id=user_id,
                source=self.source,
                external_ref=external_ref,
                label="Document",
                now=self.hub.clock(),
            )
        except DuplicateConnection as error:
            if error.elsewhere:
                raise DocumentServiceError("document_unavailable") from None
            connection = self._connection(user_id, error.existing_id)
            replayed = True
        draft = DocumentDraft(
            connection_id=connection.id,
            filename=stored_filename(filename),
            media_type=media_type,
            proposal=proposal or DraftProposal(),
            sha256=digest,
            size_bytes=len(content),
            consent=consent,
            status="queued" if consent else "saved",
            created_at=self.hub.clock(),
            updated_at=self.hub.clock(),
        )
        if not self.store.capture(user_id=user_id, draft=draft, content=content):
            raise DocumentServiceError("document_disconnected")
        return self.outcome(
            user_id=user_id, connection_id=connection.id, replayed=replayed
        )

    def outcome(
        self, *, user_id: str, connection_id: str, replayed: bool
    ) -> DocumentOutcome:
        draft = self.get(user_id=user_id, connection_id=connection_id)
        batch = self.store.get(user_id=user_id, connection_id=connection_id)
        return DocumentOutcome(
            connection_id, replayed, len(batch.candidates) if batch else 0, draft.status
        )

    def queue(
        self, *, user_id: str, connection_id: str, consent: bool
    ) -> DocumentOutcome:
        draft = self.get(user_id=user_id, connection_id=connection_id)
        if draft.status == "preparing":
            raise DocumentServiceError("document_busy", retryable=True)
        batch = self.store.get(user_id=user_id, connection_id=connection_id)
        if batch is None:
            if not consent:
                raise DocumentServiceError("document_extraction_consent_required")
            if not draft.source_available:
                raise DocumentServiceError("document_source_unavailable")
            self._update(user_id, draft, status="queued", consent=True, error_code=None)
        return self.outcome(
            user_id=user_id, connection_id=connection_id, replayed=batch is not None
        )

    async def background_prepare(self, *, user_id: str, connection_id: str) -> None:
        try:
            await self.resume(
                user_id=user_id, connection_id=connection_id, queued_only=True
            )
        except Exception:
            return

    async def resume(
        self,
        *,
        user_id: str,
        connection_id: str,
        queued_only: bool = False,
        attempt_id: str | None = None,
    ) -> DocumentOutcome:
        connection = self._connection(user_id, connection_id)
        draft = self.get(user_id=user_id, connection_id=connection_id)
        batch = self.store.get(user_id=user_id, connection_id=connection_id)
        if batch is None and (
            not draft.consent or (queued_only and draft.status != "queued")
        ):
            raise DocumentServiceError("document_preparation_not_queued")
        if draft.status == "preparing":
            raise DocumentServiceError("document_busy", retryable=True)
        holder = str(uuid.uuid4())
        repo = self.hub.connections
        if not repo.lease(
            connection_id=connection_id, holder=holder, now=self.hub.clock()
        ):
            raise DocumentServiceError("document_busy", retryable=True)
        if attempt_id is not None:
            # Checked under the lease: a reconciler cannot supersede a held lease.
            job = self.store.job(user_id=user_id, connection_id=connection_id)
            if job is None or job.attempt_id != attempt_id:
                repo.release(connection_id=connection_id, holder=holder)
                raise DocumentServiceError("document_attempt_superseded")
        replayed = batch is not None
        try:
            if batch is None:
                draft = self._update(
                    user_id, draft, holder=holder, status="preparing", error_code=None
                )
                content = await asyncio.to_thread(
                    self.source_bytes, user_id=user_id, connection_id=connection_id
                )
                # Committed before the provider can be reached: without it an
                # attempt provably never called the provider and may be retried.
                if attempt_id is not None and not self.store.mark_provider_call(
                    user_id=user_id,
                    connection_id=connection_id,
                    attempt_id=attempt_id,
                    holder=holder,
                    now=self.hub.clock(),
                ):
                    raise DocumentServiceError("document_lease_lost", retryable=True)
                batch = await self.extractor.extract(
                    content=content,
                    filename=draft.filename,
                    media_type=draft.media_type,
                    connection_id=connection_id,
                    observed_at=self.hub.clock(),
                )
                self._validate(batch, connection_id)
                if not self.store.save(
                    user_id=user_id,
                    connection_id=connection_id,
                    holder=holder,
                    now=self.hub.clock(),
                    batch=batch,
                ):
                    raise DocumentServiceError("document_lease_lost", retryable=True)
            self._validate(batch, connection_id)
            if not repo.renew(
                connection_id=connection_id, holder=holder, now=self.hub.clock()
            ):
                raise DocumentServiceError("document_lease_lost", retryable=True)
            if batch.candidates:
                if self.hub.sink is None:
                    raise DocumentServiceError("document_delivery_failed", retryable=True)
                try:
                    result = self.hub.sink.submit(
                        user_id=user_id,
                        connection_id=connection_id,
                        candidates=batch.candidates,
                    )
                except Exception:
                    raise DocumentServiceError(
                        "document_delivery_failed", retryable=True
                    ) from None
                if result.ignored:
                    raise DocumentServiceError("document_disconnected")
            if draft.source_available:
                draft = self._update(
                    user_id,
                    draft,
                    holder=holder,
                    status="needs_attention" if batch.issues else "review_ready",
                    error_code=batch.issues[0].code if batch.issues else None,
                )
            if not repo.record_success(
                connection_id=connection_id,
                holder=holder,
                expected_cursor=connection.cursor,
                cursor="delivered",
                now=self.hub.clock(),
            ):
                raise DocumentServiceError("document_lease_lost", retryable=True)
            return DocumentOutcome(
                connection_id, replayed, len(batch.candidates), draft.status
            )
        except Exception as error:
            from argus.domain.ingestion.documents.models import DocumentExtractionError

            code = (
                error.code
                if isinstance(error, (DocumentServiceError, DocumentExtractionError))
                else "document_extraction_failed"
            )
            try:
                if draft.source_available:
                    self._update(
                        user_id,
                        draft,
                        holder=holder,
                        status="needs_attention",
                        error_code=code,
                    )
                repo.record_failure(
                    connection_id=connection_id,
                    holder=holder,
                    code=code,
                    status="error",
                    now=self.hub.clock(),
                )
            except (ConnectionNotFound, DocumentServiceError):
                pass
            raise
        finally:
            repo.release(connection_id=connection_id, holder=holder)

    @staticmethod
    def _validate(batch: ExtractionBatch, connection_id: str) -> None:
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
