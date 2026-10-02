"""Document checkpoints are private, immutable and fenced by the live lease."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from argus.domain.ingestion.connections_postgres import PostgresConnectionRepository
from argus.domain.ingestion.contract import ImportCandidate, SourceRef
from argus.domain.ingestion.documents.models import ExtractionBatch
from argus.domain.ingestion.documents.store_postgres import PostgresDocumentStore
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


def test_checkpoint_is_immutable_and_owner_scoped(
    pool: ConnectionPool, users: dict[str, str]
) -> None:
    now = datetime.now(timezone.utc)
    repo, store = PostgresConnectionRepository(pool), PostgresDocumentStore(pool)
    row = repo.create(
        user_id=users["owner"],
        source="statement",
        external_ref=str(uuid4()),
        label=None,
        now=now,
    )
    holder = str(uuid4())
    assert repo.lease(connection_id=row.id, holder=holder, now=now)
    candidate = ImportCandidate(
        source=SourceRef(
            source="statement", connection_id=row.id, external_id="p1:r1", observed_at=now
        ),
        evidence="unclassified",
    )
    batch = ExtractionBatch(candidates=(candidate,))
    assert store.save(
        user_id=users["owner"], connection_id=row.id, holder=holder, now=now, batch=batch
    )
    changed = batch.model_copy(update={"metadata": {"changed": True}})
    assert store.save(
        user_id=users["owner"],
        connection_id=row.id,
        holder=holder,
        now=now,
        batch=changed,
    )
    assert store.get(user_id=users["owner"], connection_id=row.id) == batch
    assert store.get(user_id=users["other"], connection_id=row.id) is None
    assert not store.save(
        user_id=users["other"], connection_id=row.id, holder=holder, now=now, batch=batch
    )
    assert not store.save(
        user_id=users["owner"],
        connection_id=row.id,
        holder=holder,
        now=now + timedelta(minutes=6),
        batch=batch,
    )
    repo.disconnect(user_id=users["owner"], connection_id=row.id, now=now)
    store.forget(user_id=users["owner"], connection_id=row.id)
    assert not store.save(
        user_id=users["owner"], connection_id=row.id, holder=holder, now=now, batch=batch
    )
    assert store.get(user_id=users["owner"], connection_id=row.id) is None


def test_clients_have_no_checkpoint_access(pool: ConnectionPool) -> None:
    with pool.connection() as connection:
        for role in ("anon", "authenticated"):
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                allowed = connection.execute(
                    "select has_table_privilege(%s,'public.financial_document_extractions',%s)",
                    (role, privilege),
                ).fetchone()
                assert allowed == (False,)
