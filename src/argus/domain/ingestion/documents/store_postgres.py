"""Connection-fenced document sources, drafts and preparation checkpoints."""

from __future__ import annotations

from datetime import datetime

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from argus.domain.ingestion.documents.models import (
    DocumentDraft,
    ExtractionBatch,
    PreparationJob,
)


class PostgresDocumentStore:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def _read(self, column: str, user_id: str, connection_id: str) -> object | None:
        from psycopg import sql

        with self._pool.connection() as connection:
            row = connection.execute(
                sql.SQL(
                    "select d.{} from public.financial_document_extractions d join "
                    "public.financial_source_connections c on c.id=d.connection_id "
                    "where d.user_id=%s and d.connection_id=%s and c.user_id=%s "
                    "and c.source='statement' and c.status <> 'disconnected'"
                ).format(sql.Identifier(column)),
                (user_id, connection_id, user_id),
            ).fetchone()
        return row[0] if row else None

    def get(self, *, user_id: str, connection_id: str) -> ExtractionBatch | None:
        raw = self._read("batch", user_id, connection_id)
        return ExtractionBatch.model_validate(raw) if raw is not None else None

    def draft(self, *, user_id: str, connection_id: str) -> DocumentDraft | None:
        raw = self._read("draft", user_id, connection_id)
        return DocumentDraft.model_validate(raw) if raw is not None else None

    def source(self, *, user_id: str, connection_id: str) -> bytes | None:
        raw = self._read("source_bytes", user_id, connection_id)
        return bytes(raw) if raw is not None else None

    def capture(self, *, user_id: str, draft: DocumentDraft, content: bytes) -> bool:
        with self._pool.connection() as connection, connection.transaction():
            row = connection.execute(
                "select id from public.financial_source_connections where id=%s "
                "and user_id=%s and source='statement' and status <> 'disconnected' for update",
                (draft.connection_id, user_id),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "insert into public.financial_document_extractions "
                "(connection_id,user_id,draft,source_bytes,created_at) values (%s,%s,%s,%s,%s) "
                "on conflict (connection_id) do update set "
                "source_bytes=coalesce(financial_document_extractions.source_bytes,excluded.source_bytes), "
                "draft=coalesce(financial_document_extractions.draft, case "
                "when financial_document_extractions.batch is not null then "
                'excluded.draft || \'{"status":"review_ready"}\'::jsonb else excluded.draft end)',
                (
                    draft.connection_id,
                    user_id,
                    Jsonb(draft.model_dump(mode="json")),
                    content,
                    draft.created_at,
                ),
            )
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
        with self._pool.connection() as connection:
            connection.execute(
                "delete from public.financial_document_extractions where user_id=%s and connection_id=%s",
                (user_id, connection_id),
            )

    def owner(self, *, connection_id: str) -> str | None:
        with self._pool.connection() as connection:
            row = connection.execute(
                "select d.user_id::text from public.financial_document_extractions d "
                "join public.financial_source_connections c on c.id=d.connection_id "
                "and c.user_id=d.user_id where d.connection_id=%s "
                "and c.source='statement' and c.status <> 'disconnected'",
                (connection_id,),
            ).fetchone()
        return row[0] if row else None

    def job(self, *, user_id: str, connection_id: str) -> PreparationJob | None:
        raw = self._read("preparation_job", user_id, connection_id)
        return PreparationJob.model_validate(raw) if raw is not None else None

    def pending(self, *, limit: int) -> list[tuple[str, str]]:
        with self._pool.connection() as connection:
            rows = connection.execute(
                "select d.user_id::text, d.connection_id::text "
                "from public.financial_document_extractions d "
                "join public.financial_source_connections c on c.id=d.connection_id "
                "and c.user_id=d.user_id where c.source='statement' "
                "and c.status <> 'disconnected' and (d.draft->>'status' in "
                "('queued','preparing') or (d.draft->>'status'='needs_attention' "
                "and (d.preparation_job->>'retry')::boolean)) "
                "order by d.created_at, d.connection_id limit %s",
                (limit,),
            ).fetchall()
        return [(row[0], row[1]) for row in rows]

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
        with self._pool.connection() as connection, connection.transaction():
            row = connection.execute(
                "select lease_until from public.financial_source_connections "
                "where id=%s and user_id=%s and source='statement' "
                "and status <> 'disconnected' for update",
                (connection_id, user_id),
            ).fetchone()
            if row is None or (row[0] is not None and row[0] > now):
                return False
            changed = connection.execute(
                "update public.financial_document_extractions "
                "set preparation_job=%s, draft=coalesce(%s::jsonb, draft) "
                "where connection_id=%s and user_id=%s and draft is not null "
                "and preparation_job->>'attempt_id' is not distinct from %s::text "
                "and (%s::integer is null or (draft->>'version')::integer=%s) "
                "returning connection_id",
                (
                    Jsonb(job.model_dump(mode="json")),
                    Jsonb(draft.model_dump(mode="json")) if draft else None,
                    connection_id,
                    user_id,
                    expected_attempt_id,
                    draft.version - 1 if draft else None,
                    draft.version - 1 if draft else None,
                ),
            ).fetchone()
        return changed is not None
