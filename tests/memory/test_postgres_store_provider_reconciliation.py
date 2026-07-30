"""Real-Postgres proof for leased provider-reconciliation claims."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from typing import Any

import pytest
from argus.memory.postgres_store import PostgresCanonicalMemoryStore
from argus.memory.store import ReconciliationClaim
from argus.memory.subject import RegisteredMemoryOwner
from psycopg_pool import ConnectionPool

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")


def _seed_owner(connection: Any) -> str:
    owner_id = str(uuid.uuid4())
    email = f"memory-claim-{owner_id[:8]}@example.com"
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id,email,is_anonymous) values (%s,%s,false)",
            (owner_id, email),
        )
        cursor.execute(
            "insert into public.profiles (id,email) values (%s,%s)",
            (owner_id, email),
        )
    return owner_id


def _seed_record(connection: Any, owner_id: str) -> str:
    suffix = uuid.uuid4().hex
    candidate_id = f"candidate-{suffix}"
    receipt_id = f"receipt-{suffix}"
    record_id = f"record-{suffix}"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.memory_candidates (
              id,owner_id,category,source_label,source_value,future_benefit,
              trigger,proposed_context,opt_in_scope,sensitivity_status,
              sensitivity_flags,sensitivity_policy_version,
              sensitivity_content_digest
            )
            values (
              %s,%s,'workflow_preference','Show assumptions',
              'Show assumptions before results.','Keeps reviews consistent.',
              'explicit_request','ordinary',array['workflow_preference'],
              'clear','{}'::text[],'argus.memory-sensitivity/v1',%s
            )
            """,
            (candidate_id, owner_id, f"sha256:{'7' * 64}"),
        )
        cursor.execute(
            """
            insert into public.memory_consent_actions (
              id,owner_id,action,candidate_id,requested_scope,granted_scope,
              effective_scope,idempotency_key
            )
            values (
              %s,%s,'candidate_confirmation',%s,
              array['workflow_preference'],array['workflow_preference'],
              array['workflow_preference'],%s
            )
            """,
            (receipt_id, owner_id, candidate_id, candidate_id),
        )
        cursor.execute(
            """
            insert into public.memory_records (
              id,owner_id,candidate_id,consent_action_id,category,label,value
            )
            values (
              %s,%s,%s,%s,'workflow_preference',
              'Show assumptions','Show assumptions before results.'
            )
            """,
            (record_id, owner_id, candidate_id, receipt_id),
        )
        cursor.execute(
            """
            insert into public.memory_provenance (
              owner_id,record_id,ordinal,source_kind,source_id,source_version
            )
            values (%s,%s,0,'decision_note',%s,'1')
            """,
            (owner_id, record_id, str(uuid.uuid4())),
        )
        cursor.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,1,'create','pending')
            """,
            (owner_id, record_id),
        )
    return record_id


def _database_now() -> datetime:
    with psycopg.connect(DSN, autocommit=True) as connection:
        row = connection.execute("select statement_timestamp()").fetchone()
    assert row is not None
    database_time = row[0]
    assert isinstance(database_time, datetime)
    return database_time


def _expire_claim_by_database_time(
    *,
    owner: RegisteredMemoryOwner,
    record_id: str,
) -> None:
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute("select pg_sleep(0.15)")
        row = connection.execute(
            """
            select lease_expires_at <= statement_timestamp()
              from public.memory_reconciliations
             where owner_id=%s and record_id=%s and generation=1
            """,
            (owner.owner_id, record_id),
        ).fetchone()
    assert row == (True,)


@pytest.fixture
def database() -> Iterator[dict[str, Any]]:
    pool = ConnectionPool(
        conninfo=DSN,
        kwargs={"autocommit": True},
        min_size=0,
        max_size=8,
        open=True,
        timeout=2,
        name=f"memory-task-5a-{uuid.uuid4()}",
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        owner_id = _seed_owner(connection)
        other_owner_id = _seed_owner(connection)
        record_id = _seed_record(connection, owner_id)
        other_record_id = _seed_record(connection, other_owner_id)
    try:
        yield {
            "pool": pool,
            "owner": RegisteredMemoryOwner(owner_id=owner_id),
            "other_owner": RegisteredMemoryOwner(owner_id=other_owner_id),
            "record_id": record_id,
            "other_record_id": other_record_id,
        }
    finally:
        pool.close()
        with psycopg.connect(DSN, autocommit=True) as connection:
            connection.execute(
                "delete from auth.users where id = any(%s::uuid[])",
                ([owner_id, other_owner_id],),
            )


def test_pending_claim_survives_store_restart(database: dict[str, Any]) -> None:
    tokens = iter(("restart-claim",))
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: next(tokens),
    )

    claim = store.claim_reconciliation_turn(
        database["owner"],
        database["record_id"],
        1,
    )

    assert claim == ReconciliationClaim(
        record_id=database["record_id"],
        generation=1,
        operation="create",
        claim_token="restart-claim",
    )
    restarted_store = PostgresCanonicalMemoryStore(database["pool"])
    assert restarted_store.inflight_reconciliation_generations(
        database["owner"],
        database["record_id"],
    ) == (1,)
    assert restarted_store.finish_reconciliation_claim(
        database["owner"],
        claim,
        succeeded=True,
        error_code=None,
        completed_at=datetime.now(timezone.utc),
    )


def test_live_lease_cannot_be_stolen(database: dict[str, Any]) -> None:
    first = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "live-first",
    )
    second = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "live-second",
    )
    assert (
        first.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
        is not None
    )

    assert (
        second.claim_reconciliation_turn(
            database["owner"],
            database["record_id"],
            1,
        )
        is None
    )


def test_expired_lease_is_reclaimed_with_new_token(database: dict[str, Any]) -> None:
    first = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "expired-first",
        reconciliation_lease=timedelta(milliseconds=100),
    )
    second = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "expired-second",
        reconciliation_lease=timedelta(seconds=1),
    )
    initial = first.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert initial is not None
    time.sleep(0.15)

    reclaimed = second.claim_reconciliation_turn(
        database["owner"], database["record_id"], 1
    )

    assert reclaimed is not None
    assert reclaimed.claim_token == "expired-second"
    with psycopg.connect(DSN, autocommit=True) as connection:
        row = connection.execute(
            """
            select attempt_count,claim_token
              from public.memory_reconciliations
             where owner_id=%s and record_id=%s and generation=1
            """,
            (database["owner"].owner_id, database["record_id"]),
        ).fetchone()
    assert row == (2, "expired-second")


def test_stale_claim_cannot_finish_reclaimed_work(database: dict[str, Any]) -> None:
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "exact-token",
    )
    claim = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert claim is not None
    stale = ReconciliationClaim(
        record_id=claim.record_id,
        generation=claim.generation,
        operation=claim.operation,
        claim_token="stale-token",
    )

    assert not store.finish_reconciliation_claim(
        database["owner"],
        stale,
        succeeded=True,
        error_code=None,
        completed_at=datetime.now(timezone.utc),
    )
    assert store.finish_reconciliation_claim(
        database["owner"],
        claim,
        succeeded=False,
        error_code="provider_reconciliation_required",
        completed_at=datetime.now(timezone.utc),
    )


@pytest.mark.parametrize(
    ("succeeded", "error_code", "expected_status"),
    (
        (True, None, "succeeded"),
        (False, "provider_reconciliation_required", "failed"),
    ),
)
def test_terminal_outcome_erases_claim_bearer_state(
    database: dict[str, Any],
    succeeded: bool,
    error_code: str | None,
    expected_status: str,
) -> None:
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "terminal-bearer",
    )
    claim = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert claim is not None

    assert store.finish_reconciliation_claim(
        database["owner"],
        claim,
        succeeded=succeeded,
        error_code=error_code,
        completed_at=datetime.now(timezone.utc),
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        row = connection.execute(
            """
            select status,claim_token,lease_expires_at
              from public.memory_reconciliations
             where owner_id=%s and record_id=%s and generation=1
            """,
            (database["owner"].owner_id, database["record_id"]),
        ).fetchone()
    assert row == (expected_status, None, None)


def test_database_expired_exact_claim_cannot_finish_with_backdated_evidence(
    database: dict[str, Any],
) -> None:
    lagging_process_time = _database_now()
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_clock=lambda: lagging_process_time,
        reconciliation_token_factory=lambda: "database-expired-finish",
        reconciliation_lease=timedelta(milliseconds=100),
    )
    claim = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert claim is not None
    _expire_claim_by_database_time(
        owner=database["owner"],
        record_id=database["record_id"],
    )

    assert not store.finish_reconciliation_claim(
        database["owner"],
        claim,
        succeeded=True,
        error_code=None,
        completed_at=lagging_process_time,
    )
    assert store.inflight_reconciliation_generations(
        database["owner"], database["record_id"]
    ) == (1,)


def test_database_expired_exact_claim_cannot_commit_with_lagging_process_clock(
    database: dict[str, Any],
) -> None:
    lagging_process_time = _database_now()
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_clock=lambda: lagging_process_time,
        reconciliation_token_factory=lambda: "database-expired-cas",
        reconciliation_lease=timedelta(milliseconds=100),
    )
    record = store.get_record(database["owner"], database["record_id"])
    assert record is not None
    claim = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert claim is not None
    _expire_claim_by_database_time(
        owner=database["owner"],
        record_id=database["record_id"],
    )

    assert not store.compare_and_set_provider_ref(
        database["owner"],
        database["record_id"],
        expected_record=record,
        expected_provider_ref=None,
        reconciliation_claim=claim,
        provider_ref="provider-must-not-commit",
    )
    assert store.get_provider_ref(database["owner"], database["record_id"]) is None


def test_prior_unfinished_generation_blocks_next_claim(
    database: dict[str, Any],
) -> None:
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,2,'update','pending')
            """,
            (database["owner"].owner_id, database["record_id"]),
        )
    tokens = iter(("generation-one", "generation-two"))
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: next(tokens),
    )

    assert (
        store.claim_reconciliation_turn(
            database["owner"],
            database["record_id"],
            2,
        )
        is None
    )
    first = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert first is not None
    assert store.finish_reconciliation_claim(
        database["owner"],
        first,
        succeeded=True,
        error_code=None,
        completed_at=datetime.now(timezone.utc),
    )
    second = store.claim_reconciliation_turn(database["owner"], database["record_id"], 2)
    assert second is not None
    assert second.claim_token == "generation-two"


def test_next_generation_bounded_wait_obtains_claim_after_prior_finishes(
    database: dict[str, Any],
) -> None:
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,2,'update','pending')
            """,
            (database["owner"].owner_id, database["record_id"]),
        )
    polling = Event()
    resume_polling = Event()

    def _wait_for_prior(_seconds: float) -> None:
        polling.set()
        if not resume_polling.wait(timeout=2):
            raise TimeoutError("test did not release reconciliation polling")

    tokens = iter(("bounded-first", "bounded-second"))
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: next(tokens),
        reconciliation_wait_attempts=3,
        reconciliation_wait_seconds=0.0,
        reconciliation_sleeper=_wait_for_prior,
    )
    first = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert first is not None

    with ThreadPoolExecutor(max_workers=1) as executor:
        second_future = executor.submit(
            store.claim_reconciliation_turn,
            database["owner"],
            database["record_id"],
            2,
        )
        assert polling.wait(timeout=1)
        assert not second_future.done()
        assert store.finish_reconciliation_claim(
            database["owner"],
            first,
            succeeded=True,
            error_code=None,
            completed_at=datetime.now(timezone.utc),
        )
        resume_polling.set()
        second = second_future.result(timeout=2)

    assert second is not None
    assert second.generation == 2
    assert second.claim_token == "bounded-second"


def test_claim_ordering_is_independent_across_owners(
    database: dict[str, Any],
) -> None:
    tokens = iter(("first-owner", "second-owner"))
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: next(tokens),
    )

    first = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    second = store.claim_reconciliation_turn(
        database["other_owner"], database["other_record_id"], 1
    )

    assert first is not None
    assert second is not None
    assert second.claim_token == "second-owner"


def test_provider_projection_cas_requires_exact_claim(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "cas-exact",
    )
    record = store.get_record(database["owner"], database["record_id"])
    assert record is not None
    claim = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert claim is not None
    stale = ReconciliationClaim(
        record_id=claim.record_id,
        generation=claim.generation,
        operation=claim.operation,
        claim_token="cas-stale",
    )

    assert not store.compare_and_set_provider_ref(
        database["owner"],
        database["record_id"],
        expected_record=record,
        expected_provider_ref=None,
        reconciliation_claim=stale,
        provider_ref="provider-stale",
    )
    assert store.compare_and_set_provider_ref(
        database["owner"],
        database["record_id"],
        expected_record=record,
        expected_provider_ref=None,
        reconciliation_claim=claim,
        provider_ref="provider-current",
    )
    assert (
        store.get_provider_ref(database["owner"], database["record_id"])
        == "provider-current"
    )
