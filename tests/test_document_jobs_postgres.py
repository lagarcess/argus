"""Document preparation jobs on real Postgres: one current attempt, lease-fenced."""

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from argus.domain.ingestion.connections_postgres import PostgresConnectionRepository
from argus.domain.ingestion.contract import ImportCandidate, SourceRef
from argus.domain.ingestion.documents.jobs import (
    DISPATCH_WINDOW,
    PreparationJobs,
    run_attempt,
)
from argus.domain.ingestion.documents.models import (
    DocumentDraft,
    ExtractionBatch,
    PreparationJob,
)
from argus.domain.ingestion.documents.service import DocumentsService
from argus.domain.ingestion.documents.store_postgres import PostgresDocumentStore
from argus.domain.ingestion.hub import IngestionHub
from argus.domain.ingestion.sink import SubmitResult
from psycopg_pool import ConnectionPool

from tests import test_financial_accounts_postgres as shared

users = shared.users
pytestmark = pytest.mark.skipif(
    not shared.DSN, reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured"
)


@pytest.fixture
def pool() -> Iterator[ConnectionPool]:
    with ConnectionPool(shared.DSN, min_size=0, max_size=4) as opened:
        yield opened


def draft(connection_id: str, now: datetime, **changes: Any) -> DocumentDraft:
    return DocumentDraft(
        connection_id=connection_id,
        filename="receipt.pdf",
        media_type="application/pdf",
        sha256="c" * 64,
        size_bytes=12,
        consent=True,
        created_at=now,
        updated_at=now,
        **{"status": "queued", **changes},
    )


def test_advance_names_one_current_attempt_and_respects_the_lease(
    pool: ConnectionPool, users: dict[str, str]
) -> None:
    now = datetime.now(timezone.utc)
    repo, store = PostgresConnectionRepository(pool), PostgresDocumentStore(pool)
    owner, other = users["owner"], users["other"]
    row = repo.create(
        user_id=owner, source="statement", external_ref=str(uuid4()), label=None, now=now
    )
    assert store.capture(user_id=owner, draft=draft(row.id, now), content=b"%PDF-x")
    first = PreparationJob(attempt=1, attempt_id="a1", draft_version=1, dispatched_at=now)
    second = first.model_copy(update={"attempt": 2, "attempt_id": "a2"})

    assert store.owner(connection_id=row.id) == owner
    assert (owner, row.id) in store.pending(limit=1000)
    assert not store.advance(
        user_id=other, connection_id=row.id, now=now, expected_attempt_id=None, job=first
    )
    assert store.advance(
        user_id=owner, connection_id=row.id, now=now, expected_attempt_id=None, job=first
    )
    assert not store.advance(
        user_id=owner, connection_id=row.id, now=now, expected_attempt_id=None, job=second
    )
    assert store.job(user_id=owner, connection_id=row.id) == first
    assert store.job(user_id=other, connection_id=row.id) is None

    assert repo.lease(connection_id=row.id, holder="worker", now=now)
    assert not store.advance(
        user_id=owner, connection_id=row.id, now=now, expected_attempt_id="a1", job=second
    ), "a live lease is never superseded"
    later = now + DISPATCH_WINDOW + timedelta(seconds=1)
    stale_version = draft(row.id, later, version=5)
    assert not store.advance(
        user_id=owner,
        connection_id=row.id,
        now=later,
        expected_attempt_id="a1",
        job=second,
        draft=stale_version,
    ), "the draft version is compared and set with the job"
    requeued = draft(row.id, later, version=2)
    assert store.advance(
        user_id=owner,
        connection_id=row.id,
        now=later,
        expected_attempt_id="a1",
        job=second,
        draft=requeued,
    )
    assert store.job(user_id=owner, connection_id=row.id) == second
    assert store.draft(user_id=owner, connection_id=row.id) == requeued

    failed = draft(row.id, later, version=3, status="needs_attention")
    assert store.advance(
        user_id=owner,
        connection_id=row.id,
        now=later,
        expected_attempt_id="a2",
        job=second,
        draft=failed,
    )
    assert (owner, row.id) not in store.pending(limit=1000)
    retry = second.model_copy(update={"retry": True})
    assert store.advance(
        user_id=owner,
        connection_id=row.id,
        now=later,
        expected_attempt_id="a2",
        job=retry,
    )
    assert (owner, row.id) in store.pending(limit=1000)

    repo.disconnect(user_id=owner, connection_id=row.id, now=later)
    assert store.owner(connection_id=row.id) is None
    assert (owner, row.id) not in store.pending(limit=1000)
    store.forget(user_id=owner, connection_id=row.id)


class Clock:
    def __init__(self) -> None:
        self.now = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.now


class Extractor:
    def __init__(self) -> None:
        self.calls = 0
        self.release = asyncio.Event()

    async def extract(self, **kwargs: Any) -> ExtractionBatch:
        self.calls += 1
        amount = "129.50"
        if self.calls == 1:
            await self.release.wait()
            amount = "999.00"
        candidate = ImportCandidate(
            source=SourceRef(
                source="statement",
                connection_id=kwargs["connection_id"],
                external_id="document:p1:r1",
                observed_at=kwargs["observed_at"],
            ),
            evidence="transaction",
            amount=amount,
            currency="DOP",
            direction="outflow",
        )
        return ExtractionBatch(candidates=(candidate,))


@pytest.mark.asyncio
async def test_dead_worker_recovers_once_and_its_late_result_is_refused(
    pool: ConnectionPool, users: dict[str, str]
) -> None:
    clock, extractor, sink = Clock(), Extractor(), Mock()
    sink.submit.return_value = SubmitResult(1, 0, 0)
    repo = PostgresConnectionRepository(pool)
    hub = IngestionHub(repo, box=None, sink=sink, clock=clock)
    service = DocumentsService(
        hub, PostgresDocumentStore(pool), extractor, jobs_recover_interruptions=True
    )
    dispatched: list[tuple[str, str]] = []
    jobs = PreparationJobs(service, lambda *attempt: dispatched.append(attempt))
    owner = users["owner"]
    captured = await service.upload(
        user_id=owner,
        content=b"%PDF-" + uuid4().bytes,
        filename="receipt.pdf",
        media_type="application/pdf",
        consent=True,
    )
    connection = captured.connection_id

    jobs.start(user_id=owner, connection_id=connection)
    jobs.start(user_id=owner, connection_id=connection)
    [first] = [attempt for target, attempt in dispatched if target == connection]
    dead = asyncio.create_task(run_attempt(service, connection, first))
    while extractor.calls == 0:
        await asyncio.sleep(0.01)

    clock.now += DISPATCH_WINDOW - timedelta(seconds=1)
    assert connection not in jobs.sweep().redispatched
    clock.now += timedelta(seconds=2)
    assert connection in jobs.sweep().redispatched
    [_, second] = [attempt for target, attempt in dispatched if target == connection]

    assert await run_attempt(service, connection, first) == (
        "document_attempt_superseded"
    ), "a late duplicate of the superseded attempt never reaches the provider"
    assert await run_attempt(service, connection, second) == "prepared"
    extractor.release.set()
    assert await dead == "document_lease_lost"

    prepared = service.get(user_id=owner, connection_id=connection)
    batch = service.store.get(user_id=owner, connection_id=connection)
    assert prepared.status == "review_ready"
    assert [c.amount for c in batch.candidates] == ["129.5"]
    assert extractor.calls == 2
    sink.submit.assert_called_once()
    assert service.store.job(user_id=owner, connection_id=connection).attempt == 2
    assert connection not in jobs.sweep().redispatched
    service.forget(hub.connections.get(user_id=owner, connection_id=connection))


def test_workflow_worker_prepares_the_dispatched_attempt(
    pool: ConnectionPool, users: dict[str, str]
) -> None:
    from workflows.document_job import (
        postgres_documents_service,
        run_document_preparation,
    )

    class Prepared:
        calls = 0

        async def extract(self, **kwargs: Any) -> ExtractionBatch:
            Prepared.calls += 1
            candidate = ImportCandidate(
                source=SourceRef(
                    source="statement",
                    connection_id=kwargs["connection_id"],
                    external_id="document:p1:r1",
                    observed_at=kwargs["observed_at"],
                ),
                evidence="transaction",
                amount="42.00",
                currency="DOP",
                direction="outflow",
            )
            return ExtractionBatch(candidates=(candidate,))

    api = postgres_documents_service(pool, Prepared())
    outcomes: list[dict[str, str]] = []
    jobs = PreparationJobs(
        api,
        lambda connection_id, attempt_id: outcomes.append(
            asyncio.run(
                run_document_preparation(
                    connection_id,
                    attempt_id,
                    env={"ARGUS_WORKFLOW_DATABASE_URL": shared.DSN},
                    extractor=Prepared(),
                )
            )
        ),
    )
    owner = users["owner"]
    captured = asyncio.run(
        api.upload(
            user_id=owner,
            content=b"%PDF-" + uuid4().bytes,
            filename="receipt.pdf",
            media_type="application/pdf",
            consent=True,
        )
    )

    jobs.start(user_id=owner, connection_id=captured.connection_id)

    assert [outcome["outcome"] for outcome in outcomes] == ["prepared"]
    assert Prepared.calls == 1
    assert api.get(user_id=owner, connection_id=captured.connection_id).status == (
        "review_ready"
    )
    with pool.connection() as connection:
        events = connection.execute(
            "select count(distinct event_id) from public.financial_import_observations "
            "where user_id=%s and connection_id=%s",
            (owner, captured.connection_id),
        ).fetchone()
    assert events == (1,)
    api.forget(
        api.hub.connections.get(user_id=owner, connection_id=captured.connection_id)
    )
