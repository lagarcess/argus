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
    from argus.domain.ingestion.documents.models import DocumentDraft

    legacy_capture = DocumentDraft(
        connection_id=row.id,
        filename="legacy.pdf",
        media_type="application/pdf",
        sha256="b" * 64,
        size_bytes=12,
        created_at=now,
        updated_at=now,
    )
    assert store.capture(
        user_id=users["owner"], draft=legacy_capture, content=b"%PDF-fixture"
    )
    assert store.source(user_id=users["owner"], connection_id=row.id) == b"%PDF-fixture"
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


def test_capture_survives_new_store_handles_and_disconnect_hides_source(
    pool: ConnectionPool, users: dict[str, str]
) -> None:
    from argus.domain.ingestion.documents.models import DocumentDraft

    now = datetime.now(timezone.utc)
    repo = PostgresConnectionRepository(pool)
    owner, other = users["owner"], users["other"]
    connection = repo.create(
        user_id=owner,
        source="statement",
        external_ref=str(uuid4()),
        label="Document",
        now=now,
    )
    draft = DocumentDraft(
        connection_id=connection.id,
        filename="synthetic.pdf",
        media_type="application/pdf",
        sha256="a" * 64,
        size_bytes=12,
        created_at=now,
        updated_at=now,
    )
    source = b"%PDF-fixture"
    assert PostgresDocumentStore(pool).capture(user_id=owner, draft=draft, content=source)
    with ConnectionPool(shared.DSN, min_size=0, max_size=2) as restarted:
        store = PostgresDocumentStore(restarted)
        assert store.draft(user_id=owner, connection_id=connection.id) == draft
        assert store.source(user_id=owner, connection_id=connection.id) == source
        assert store.source(user_id=other, connection_id=connection.id) is None
        changed = draft.model_copy(
            update={"version": 2, "status": "queued", "consent": True}
        )
        assert store.update(user_id=owner, draft=changed, expected_version=1)
        assert not store.update(user_id=owner, draft=changed, expected_version=1)
        repo.disconnect(user_id=owner, connection_id=connection.id, now=now)
        assert store.source(user_id=owner, connection_id=connection.id) is None
        assert store.draft(user_id=owner, connection_id=connection.id) is None
        assert not store.capture(user_id=owner, draft=draft, content=source)
        assert not store.update(user_id=owner, draft=changed, expected_version=2)
        store.forget(user_id=owner, connection_id=connection.id)
    with pool.connection() as sql:
        assert sql.execute(
            "select count(*) from public.financial_document_extractions where connection_id=%s",
            (connection.id,),
        ).fetchone() == (0,)
