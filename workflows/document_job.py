"""Render Workflow worker for one document preparation attempt (#823).

The task input is ``[connection_id, attempt_id]``; the owner comes from the
stored row, never from the input. The worker runs the same ``run_attempt`` as
the API's in-process fallback and never dispatches: retries and dead-worker
recovery belong to the API's reconciler sweep.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timezone

from argus.domain.ingestion.connections_postgres import PostgresConnectionRepository
from argus.domain.ingestion.documents.extractor import DocumentExtractor
from argus.domain.ingestion.documents.jobs import run_attempt
from argus.domain.ingestion.documents.service import DocumentsService, Extractor
from argus.domain.ingestion.documents.store_postgres import PostgresDocumentStore
from argus.domain.ingestion.hub import IngestionHub
from argus.domain.ingestion.reconcile.service import ReconciliationService
from argus.domain.ingestion.reconcile.store_postgres import PostgresImportStore
from argus.domain.recording.money_service import MoneyService
from argus.domain.recording.postgres_repository import (
    PostgresFinancialAccountRepository,
)
from argus.domain.recording.service import FinancialAccountService
from psycopg_pool import ConnectionPool

try:
    from workflows.proof import require_database_url
except ModuleNotFoundError:  # pragma: no cover - supports `python workflows/main.py`
    from proof import require_database_url


def _clock() -> datetime:
    return datetime.now(timezone.utc)


def postgres_documents_service(
    pool: ConnectionPool, extractor: Extractor | None = None
) -> DocumentsService:
    """The API's durable document graph: connections, sink and checkpoint."""
    connections = PostgresConnectionRepository(pool)
    sink = ReconciliationService(
        PostgresImportStore(pool),
        MoneyService(FinancialAccountService(PostgresFinancialAccountRepository(pool))),
        _clock,
        connections=connections,
    )
    hub = IngestionHub(connections, box=None, sink=sink, clock=_clock)
    return DocumentsService(
        hub,
        PostgresDocumentStore(pool),
        extractor or DocumentExtractor(),
        jobs_recover_interruptions=True,
    )


def run_document_preparation(
    connection_id: str,
    attempt_id: str,
    *,
    env: Mapping[str, str] | None = None,
    extractor: Extractor | None = None,
) -> dict[str, str]:
    with ConnectionPool(
        require_database_url(env),
        min_size=0,
        max_size=2,
        kwargs={"prepare_threshold": None},
    ) as pool:
        outcome = asyncio.run(
            run_attempt(
                postgres_documents_service(pool, extractor), connection_id, attempt_id
            )
        )
    return {"connection_id": connection_id, "attempt_id": attempt_id, "outcome": outcome}
