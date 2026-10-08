"""Positive control: one real-clock sweeper in a separate process over the proof database,
the condition the earlier diagnosis blames. Dispatch only records; no worker or provider runs."""
import os, sys, time
from datetime import datetime, timezone
from unittest.mock import Mock

from psycopg_pool import ConnectionPool
from argus.domain.ingestion.connections_postgres import PostgresConnectionRepository
from argus.domain.ingestion.documents.jobs import PreparationJobs
from argus.domain.ingestion.documents.service import DocumentsService
from argus.domain.ingestion.documents.store_postgres import PostgresDocumentStore
from argus.domain.ingestion.hub import IngestionHub
from tests.document_sources_support import source_objects


class NoExtractor:
    async def extract(self, **_):
        raise AssertionError("the control never prepares")


pool = ConnectionPool(os.environ["ARGUS_DISPOSABLE_DATABASE_URL"], min_size=0, max_size=2)
hub = IngestionHub(PostgresConnectionRepository(pool), box=None, sink=Mock(), clock=lambda: datetime.now(timezone.utc))
service = DocumentsService(hub, PostgresDocumentStore(pool, source_objects()), NoExtractor(), jobs_recover_interruptions=True)
jobs = PreparationJobs(service, lambda connection_id, attempt_id: print("dispatched", connection_id, attempt_id, flush=True))
deadline = time.monotonic() + float(sys.argv[1])
while time.monotonic() < deadline:
    report = jobs.sweep()
    if report.redispatched or report.outcome_unknown or report.exhausted:
        print("sweep", report, flush=True)
    time.sleep(0.02)
pool.close()
