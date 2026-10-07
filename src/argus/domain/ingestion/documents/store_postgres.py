"""Connection-fenced document drafts, preparation checkpoints and source references.

A source is written to Storage before its reference commits, so a crash leaves
an unreferenced object under the connection's prefix, never a row pointing at
nothing. ``forget`` and account deletion remove objects by prefix, which also
takes such orphans; an identical retry reuses the same path and adopts it.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from argus.domain.ingestion.documents.models import DocumentDraft, ExtractionBatch
from argus.domain.ingestion.documents.objects import (
    SourceObjects,
    connection_prefix,
    source_path,
)


class PostgresDocumentStore:
    def __init__(self, pool: ConnectionPool, objects: SourceObjects) -> None:
        self._pool = pool
        self.objects = objects

    def _read(self, user_id: str, connection_id: str, *columns: str) -> tuple | None:
        from psycopg import sql

        with self._pool.connection() as connection:
            return connection.execute(
                sql.SQL(
                    "select {} from public.financial_document_extractions d join "
                    "public.financial_source_connections c on c.id=d.connection_id "
                    "where d.user_id=%s and d.connection_id=%s and c.user_id=%s "
                    "and c.source='statement' and c.status <> 'disconnected'"
                ).format(
                    sql.SQL(",").join(sql.Identifier("d", column) for column in columns)
                ),
                (user_id, connection_id, user_id),
            ).fetchone()

    def get(self, *, user_id: str, connection_id: str) -> ExtractionBatch | None:
        row = self._read(user_id, connection_id, "batch")
        return (
            ExtractionBatch.model_validate(row[0]) if row and row[0] is not None else None
        )

    def draft(self, *, user_id: str, connection_id: str) -> DocumentDraft | None:
        row = self._read(user_id, connection_id, "draft")
        return (
            DocumentDraft.model_validate(row[0]) if row and row[0] is not None else None
        )

    def source(self, *, user_id: str, connection_id: str) -> bytes | None:
        row = self._read(user_id, connection_id, "source_path", "source_bytes")
        if row is None:
            return None
        path, legacy = row
        if path is not None:
            return self.objects.get(path)
        return bytes(legacy) if legacy is not None else None

    def capture(self, *, user_id: str, draft: DocumentDraft, content: bytes) -> bool:
        connection_id = draft.connection_id
        row = self._read(user_id, connection_id, "source_path", "source_bytes")
        digest = hashlib.sha256(content).hexdigest()
        path = source_path(user_id=user_id, connection_id=connection_id, sha256=digest)
        attach = row is None or row == (None, None)
        if attach:
            self.objects.put(path, content, draft.media_type)
        with self._pool.connection() as connection, connection.transaction():
            live = connection.execute(
                "select id from public.financial_source_connections where id=%s "
                "and user_id=%s and source='statement' and status <> 'disconnected' for update",
                (connection_id, user_id),
            ).fetchone()
            if live is not None:
                connection.execute(
                    "insert into public.financial_document_extractions "
                    "(connection_id,user_id,draft,created_at) values (%s,%s,%s,%s) "
                    "on conflict (connection_id) do update set "
                    "draft=coalesce(financial_document_extractions.draft, case "
                    "when financial_document_extractions.batch is not null then "
                    'excluded.draft || \'{"status":"review_ready"}\'::jsonb else excluded.draft end)',
                    (
                        connection_id,
                        user_id,
                        Jsonb(draft.model_dump(mode="json")),
                        draft.created_at,
                    ),
                )
                if attach:
                    connection.execute(
                        "update public.financial_document_extractions set "
                        "source_bucket=%s,source_path=%s,source_media_type=%s,"
                        "source_size_bytes=%s,source_sha256=%s "
                        "where connection_id=%s and source_path is null and source_bytes is null",
                        (
                            self.objects.bucket,
                            path,
                            draft.media_type,
                            len(content),
                            digest,
                            connection_id,
                        ),
                    )
        if live is None:
            if attach:
                self.objects.delete(
                    connection_prefix(user_id=user_id, connection_id=connection_id)
                )
            return False
        return True

    def update(
        self,
        *,
        user_id: str,
        draft: DocumentDraft,
        expected_version: int,
        holder: str | None = None,
    ) -> bool:
        with self._pool.connection() as connection, connection.transaction():
            row = connection.execute(
                "select lease_holder,lease_until from public.financial_source_connections "
                "where id=%s and user_id=%s and source='statement' and status <> 'disconnected' for update",
                (draft.connection_id, user_id),
            ).fetchone()
            if row is None or (
                holder is not None
                and (row[0] != holder or row[1] is None or row[1] <= draft.updated_at)
            ):
                return False
            if (
                draft.error_code == "document_preparation_interrupted"
                and row[1] is not None
                and row[1] > draft.updated_at
            ):
                return False
            changed = connection.execute(
                "update public.financial_document_extractions set draft=%s "
                "where connection_id=%s and user_id=%s and (draft->>'version')::integer=%s returning connection_id",
                (
                    Jsonb(draft.model_dump(mode="json")),
                    draft.connection_id,
                    user_id,
                    expected_version,
                ),
            ).fetchone()
        return changed is not None

    def save(
        self,
        *,
        user_id: str,
        connection_id: str,
        holder: str,
        now: datetime,
        batch: ExtractionBatch,
    ) -> bool:
        with self._pool.connection() as connection, connection.transaction():
            row = connection.execute(
                "select id from public.financial_source_connections "
                "where id=%s and user_id=%s and source='statement' "
                "and status <> 'disconnected' and lease_holder=%s and lease_until > %s for update",
                (connection_id, user_id, holder, now),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "insert into public.financial_document_extractions "
                "(connection_id,user_id,batch,created_at) values (%s,%s,%s,%s) "
                "on conflict (connection_id) do update set batch=excluded.batch "
                "where financial_document_extractions.batch is null",
                (connection_id, user_id, Jsonb(batch.model_dump(mode="json")), now),
            )
        return True

    def forget(self, *, user_id: str, connection_id: str) -> None:
        """Objects first: a failure keeps the row, so a retried disconnect
        finds and finishes the cleanup."""
        self.objects.delete(
            connection_prefix(user_id=user_id, connection_id=connection_id)
        )
        with self._pool.connection() as connection:
            connection.execute(
                "delete from public.financial_document_extractions where user_id=%s and connection_id=%s",
                (user_id, connection_id),
            )
