"""Connection-fenced, immutable document extraction checkpoints."""

from __future__ import annotations

from datetime import datetime

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from argus.domain.ingestion.documents.models import ExtractionBatch


class PostgresDocumentStore:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def get(self, *, user_id: str, connection_id: str) -> ExtractionBatch | None:
        with self._pool.connection() as connection:
            row = connection.execute(
                "select batch from public.financial_document_extractions "
                "where user_id=%s and connection_id=%s",
                (user_id, connection_id),
            ).fetchone()
        return ExtractionBatch.model_validate(row[0]) if row else None

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
                "and status <> 'disconnected' and lease_holder=%s "
                "and lease_until > %s for update",
                (connection_id, user_id, holder, now),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "insert into public.financial_document_extractions "
                "(connection_id,user_id,batch,created_at) values (%s,%s,%s,%s) "
                "on conflict (connection_id) do nothing",
                (connection_id, user_id, Jsonb(batch.model_dump(mode="json")), now),
            )
        return True

    def forget(self, *, user_id: str, connection_id: str) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                "delete from public.financial_document_extractions "
                "where user_id=%s and connection_id=%s",
                (user_id, connection_id),
            )
