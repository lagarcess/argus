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
from argus.memory.contracts import ProviderReconciliationStatus
from argus.memory.postgres_store import PostgresCanonicalMemoryStore
from argus.memory.provider import (
    ProviderCleanupResult,
    ProviderProjectionResult,
    ProviderSearchResult,
    ProviderSearchStatus,
)
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import ProviderCleanupTarget, ReconciliationClaim
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    RegisteredMemoryOwner,
)
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
        second_record_id = _seed_record(connection, owner_id)
        other_record_id = _seed_record(connection, other_owner_id)
    try:
        yield {
            "pool": pool,
            "owner": RegisteredMemoryOwner(owner_id=owner_id),
            "other_owner": RegisteredMemoryOwner(owner_id=other_owner_id),
            "record_id": record_id,
            "second_record_id": second_record_id,
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


def test_claim_expiring_while_waiting_for_provider_ref_lock_cannot_commit(
    database: dict[str, Any],
) -> None:
    provider_ref = "provider-expired-after-ref-wait"
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "expires-behind-ref-lock",
        reconciliation_lease=timedelta(seconds=1),
    )
    record = store.get_record(database["owner"], database["record_id"])
    assert record is not None
    claim = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert claim is not None
    holder = psycopg.connect(DSN)
    holder.execute(
        """
        select pg_advisory_xact_lock(
          pg_catalog.hashtextextended(%s, 0)
        )
        """,
        ("argus:memory-provider-ref:" f"{database['owner'].owner_id}:{provider_ref}",),
    )
    holder_pid_row = holder.execute("select pg_backend_pid()").fetchone()
    assert holder_pid_row is not None
    holder_pid = int(holder_pid_row[0])

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            commit_attempt = executor.submit(
                store.compare_and_set_provider_ref,
                database["owner"],
                database["record_id"],
                expected_record=record,
                expected_provider_ref=None,
                reconciliation_claim=claim,
                provider_ref=provider_ref,
            )
            deadline = time.monotonic() + 2
            blocked = False
            while time.monotonic() < deadline:
                with psycopg.connect(DSN, autocommit=True) as monitor:
                    blocked_row = monitor.execute(
                        """
                        select exists (
                          select 1
                            from pg_catalog.pg_stat_activity
                           where %s = any(pg_catalog.pg_blocking_pids(pid))
                             and wait_event = 'advisory'
                        )
                        """,
                        (holder_pid,),
                    ).fetchone()
                assert blocked_row is not None
                if blocked_row[0]:
                    blocked = True
                    break
                time.sleep(0.01)
            assert blocked is True
            with psycopg.connect(DSN, autocommit=True) as monitor:
                monitor.execute("select pg_sleep(1.05)")
                expired_row = monitor.execute(
                    """
                    select lease_expires_at <= statement_timestamp()
                      from public.memory_reconciliations
                     where owner_id=%s and record_id=%s and generation=1
                    """,
                    (
                        database["owner"].owner_id,
                        database["record_id"],
                    ),
                ).fetchone()
            assert expired_row == (True,)
            holder.commit()
            committed = commit_attempt.result(timeout=2)
    finally:
        holder.rollback()
        holder.close()

    assert committed is False
    assert store.get_provider_ref(database["owner"], database["record_id"]) is None
    assert store.get_record(database["owner"], database["record_id"]) == record
    assert store.list_provider_cleanup_targets(database["owner"]) == ()


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


def test_provider_projection_admin_seam_is_restart_durable_and_owner_scoped(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])

    assert store.set_provider_ref(
        database["owner"],
        database["record_id"],
        "provider-shared-across-owners",
    )
    assert (
        store.get_provider_ref(database["other_owner"], database["other_record_id"])
        is None
    )
    restarted = PostgresCanonicalMemoryStore(database["pool"])
    assert (
        restarted.get_provider_ref(database["owner"], database["record_id"])
        == "provider-shared-across-owners"
    )
    assert restarted.set_provider_ref(
        database["other_owner"],
        database["other_record_id"],
        "provider-shared-across-owners",
    )


def test_provider_projection_admin_replacement_tracks_old_ref_once(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    assert store.set_provider_ref(
        database["owner"], database["record_id"], "provider-admin-old"
    )

    assert store.set_provider_ref(
        database["owner"], database["record_id"], "provider-admin-new"
    )
    assert store.set_provider_ref(
        database["owner"], database["record_id"], "provider-admin-new"
    )

    assert (
        store.get_provider_ref(database["owner"], database["record_id"])
        == "provider-admin-new"
    )
    assert store.list_provider_cleanup_targets(
        database["owner"], database["record_id"]
    ) == (
        ProviderCleanupTarget(
            record_id=database["record_id"],
            provider_ref="provider-admin-old",
        ),
    )


def test_same_owner_provider_ref_collision_is_rejected_without_mutation(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    assert store.set_provider_ref(
        database["owner"], database["record_id"], "provider-owner-unique"
    )

    assert not store.set_provider_ref(
        database["owner"],
        database["second_record_id"],
        "provider-owner-unique",
    )

    assert (
        store.get_provider_ref(database["owner"], database["record_id"])
        == "provider-owner-unique"
    )
    assert store.get_provider_ref(database["owner"], database["second_record_id"]) is None
    assert store.list_provider_cleanup_targets(database["owner"]) == ()


def test_cleanup_tracking_rejects_ref_projected_by_different_record(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    assert store.set_provider_ref(
        database["owner"], database["record_id"], "provider-reused"
    )

    assert not store.track_provider_cleanup_target(
        database["owner"],
        database["second_record_id"],
        "provider-reused",
    )
    assert store.list_provider_cleanup_targets(database["owner"]) == ()


def test_provider_projection_cas_replacement_tracks_prior_ref_idempotently(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "replace-cas",
    )
    assert store.set_provider_ref(
        database["owner"], database["record_id"], "provider-cas-old"
    )
    record = store.get_record(database["owner"], database["record_id"])
    assert record is not None
    claim = store.claim_reconciliation_turn(database["owner"], database["record_id"], 1)
    assert claim is not None

    assert store.compare_and_set_provider_ref(
        database["owner"],
        database["record_id"],
        expected_record=record,
        expected_provider_ref="provider-cas-old",
        reconciliation_claim=claim,
        provider_ref="provider-cas-new",
    )

    assert store.list_provider_cleanup_targets(
        database["owner"], database["record_id"]
    ) == (
        ProviderCleanupTarget(
            record_id=database["record_id"],
            provider_ref="provider-cas-old",
        ),
    )


def test_cleanup_list_is_bounded_unique_deterministic_pending_and_restart_durable(
    database: dict[str, Any],
) -> None:
    with psycopg.connect(DSN, autocommit=True) as connection:
        for index in range(101):
            connection.execute(
                """
                insert into public.memory_provider_cleanup (
                  owner_id,record_id,provider_ref,generation,status,created_at
                )
                values (%s,%s,%s,1,'pending',%s)
                """,
                (
                    database["owner"].owner_id,
                    database["record_id"],
                    f"provider-list-{index:03d}",
                    datetime(2026, 7, 29, tzinfo=timezone.utc) + timedelta(seconds=index),
                ),
            )
        connection.execute(
            """
            insert into public.memory_provider_cleanup (
              owner_id,record_id,provider_ref,generation,status,created_at
            )
            values (%s,%s,'provider-list-resolved',1,'pending',now())
            """,
            (database["owner"].owner_id, database["record_id"]),
        )
        connection.execute(
            """
            update public.memory_provider_cleanup
               set status='resolved',resolved_at=now()
             where owner_id=%s
               and record_id=%s
               and provider_ref='provider-list-resolved'
            """,
            (database["owner"].owner_id, database["record_id"]),
        )
        connection.execute(
            """
            insert into public.memory_provider_cleanup (
              owner_id,record_id,provider_ref,generation,status,created_at
            )
            values (%s,%s,'provider-list-100',2,'pending',now())
            """,
            (database["owner"].owner_id, database["record_id"]),
        )
    restarted = PostgresCanonicalMemoryStore(database["pool"])

    targets = restarted.list_provider_cleanup_targets(
        database["owner"], database["record_id"]
    )

    assert len(targets) == 100
    assert targets[0] == ProviderCleanupTarget(
        record_id=database["record_id"],
        provider_ref="provider-list-100",
    )
    assert targets[-1] == ProviderCleanupTarget(
        record_id=database["record_id"],
        provider_ref="provider-list-001",
    )
    assert len(set(targets)) == 100
    assert all(target.provider_ref != "provider-list-resolved" for target in targets)
    assert restarted.list_provider_cleanup_targets(database["other_owner"]) == ()


def test_cleanup_resolution_is_idempotent_and_removes_only_matching_projection(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    assert store.set_provider_ref(
        database["owner"], database["record_id"], "provider-resolve"
    )
    assert store.track_provider_cleanup_target(
        database["owner"], database["record_id"], "provider-resolve"
    )
    assert store.set_provider_ref(
        database["owner"], database["second_record_id"], "provider-keep"
    )

    assert store.resolve_provider_cleanup_target(
        database["owner"], database["record_id"], "provider-resolve"
    )
    assert not store.resolve_provider_cleanup_target(
        database["owner"], database["record_id"], "provider-resolve"
    )

    assert store.get_provider_ref(database["owner"], database["record_id"]) is None
    assert (
        store.get_provider_ref(database["owner"], database["second_record_id"])
        == "provider-keep"
    )
    assert store.list_provider_cleanup_targets(database["owner"]) == ()


def test_pending_cleanup_reserves_ref_against_same_and_different_record_set(
    database: dict[str, Any],
) -> None:
    scheduler = PostgresCanonicalMemoryStore(database["pool"])
    contender = PostgresCanonicalMemoryStore(database["pool"])
    assert scheduler.track_provider_cleanup_target(
        database["owner"], database["record_id"], "provider-reserved-set"
    )

    same_record_assigned = contender.set_provider_ref(
        database["owner"], database["record_id"], "provider-reserved-set"
    )
    different_record_assigned = contender.set_provider_ref(
        database["owner"],
        database["second_record_id"],
        "provider-reserved-set",
    )
    other_owner_assigned = contender.set_provider_ref(
        database["other_owner"],
        database["other_record_id"],
        "provider-reserved-set",
    )

    assert same_record_assigned is False
    assert different_record_assigned is False
    assert other_owner_assigned is True
    assert scheduler.list_provider_cleanup_targets(database["owner"]) == (
        ProviderCleanupTarget(
            record_id=database["record_id"],
            provider_ref="provider-reserved-set",
        ),
    )
    assert scheduler.resolve_provider_cleanup_target(
        database["owner"], database["record_id"], "provider-reserved-set"
    )
    assert contender.set_provider_ref(
        database["owner"], database["record_id"], "provider-reserved-set"
    )


def test_pending_cleanup_reserves_ref_against_exact_claim_cas_until_resolved(
    database: dict[str, Any],
) -> None:
    scheduler = PostgresCanonicalMemoryStore(database["pool"])
    contender = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "reserved-cas",
    )
    assert scheduler.track_provider_cleanup_target(
        database["owner"], database["record_id"], "provider-reserved-cas"
    )
    record = contender.get_record(database["owner"], database["second_record_id"])
    assert record is not None
    claim = contender.claim_reconciliation_turn(
        database["owner"], database["second_record_id"], 1
    )
    assert claim is not None

    assert not contender.compare_and_set_provider_ref(
        database["owner"],
        database["second_record_id"],
        expected_record=record,
        expected_provider_ref=None,
        reconciliation_claim=claim,
        provider_ref="provider-reserved-cas",
    )
    assert scheduler.list_provider_cleanup_targets(database["owner"]) == (
        ProviderCleanupTarget(
            record_id=database["record_id"],
            provider_ref="provider-reserved-cas",
        ),
    )
    assert scheduler.resolve_provider_cleanup_target(
        database["owner"], database["record_id"], "provider-reserved-cas"
    )
    assert contender.compare_and_set_provider_ref(
        database["owner"],
        database["second_record_id"],
        expected_record=record,
        expected_provider_ref=None,
        reconciliation_claim=claim,
        provider_ref="provider-reserved-cas",
    )


@pytest.mark.parametrize("operation", ("insert", "update"))
def test_database_rejects_raw_projection_assignment_to_pending_cleanup_ref(
    database: dict[str, Any],
    operation: str,
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    assert store.track_provider_cleanup_target(
        database["owner"], database["record_id"], "provider-raw-reserved"
    )
    if operation == "update":
        assert store.set_provider_ref(
            database["owner"],
            database["second_record_id"],
            "provider-raw-prior",
        )
    with psycopg.connect(DSN, autocommit=True) as connection:
        with pytest.raises(psycopg.errors.CheckViolation, match="reserved"):
            if operation == "insert":
                connection.execute(
                    """
                    insert into public.memory_provider_projections (
                      owner_id,record_id,provider_ref,generation
                    )
                    values (%s,%s,'provider-raw-reserved',1)
                    """,
                    (
                        database["owner"].owner_id,
                        database["second_record_id"],
                    ),
                )
            else:
                connection.execute(
                    """
                    update public.memory_provider_projections
                       set provider_ref='provider-raw-reserved',
                           generation=generation+1,
                           updated_at=now()
                     where owner_id=%s and record_id=%s
                    """,
                    (
                        database["owner"].owner_id,
                        database["second_record_id"],
                    ),
                )


class _BlockingCleanupProvider:
    def __init__(self, store: PostgresCanonicalMemoryStore) -> None:
        self._store = store
        self.delete_started = Event()
        self.allow_delete = Event()
        self.delete_calls: list[tuple[RegisteredMemoryOwner, str]] = []
        self.deleted_live_projection = False

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: object,
    ) -> ProviderProjectionResult:
        del owner, record
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.NOT_APPLICABLE
        )

    def search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult:
        del owner, query, limit
        return ProviderSearchResult(status=ProviderSearchStatus.UNAVAILABLE)

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        self.delete_calls.append((owner, provider_ref))
        self.delete_started.set()
        if not self.allow_delete.wait(timeout=5):
            raise TimeoutError("test did not release provider cleanup")
        self.deleted_live_projection = any(
            self._store.get_provider_ref(owner, record.id) == provider_ref
            for record in self._store.list_records(owner)
        )
        return ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        del owner
        return ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE)


def test_service_cleanup_reservation_prevents_deleting_reassigned_live_ref(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "service-delete-claim",
    )
    initial_claim = store.claim_reconciliation_turn(
        database["owner"], database["record_id"], 1
    )
    assert initial_claim is not None
    assert store.finish_reconciliation_claim(
        database["owner"],
        initial_claim,
        succeeded=True,
        error_code=None,
        completed_at=datetime.now(timezone.utc),
    )
    assert store.set_provider_ref(
        database["owner"], database["record_id"], "provider-service-reserved"
    )
    provider = _BlockingCleanupProvider(store)
    service = MemoryService(
        store=store,
        provider=provider,
        config=MemoryServiceConfig(available=True),
    )
    subject = MemorySubject(
        owner_id=database["owner"].owner_id,
        kind=MemoryAccountKind.REGISTERED,
    )
    contender = PostgresCanonicalMemoryStore(database["pool"])

    with ThreadPoolExecutor(max_workers=1) as executor:
        deletion = executor.submit(service.delete, subject, database["record_id"])
        assert provider.delete_started.wait(timeout=2)
        ref_reassigned = contender.set_provider_ref(
            database["owner"],
            database["second_record_id"],
            "provider-service-reserved",
        )
        provider.allow_delete.set()
        result = deletion.result(timeout=5)

    assert ref_reassigned is False
    assert provider.delete_calls == [(database["owner"], "provider-service-reserved")]
    assert provider.deleted_live_projection is False
    assert result.provider_status is ProviderReconciliationStatus.SYNCHRONIZED


def test_settled_projection_ids_exclude_records_awaiting_cleanup(
    database: dict[str, Any],
) -> None:
    """Catches the bulk projection read drifting from per-record truth.

    Retrieval decides whether an empty index answer is authoritative from this
    set, so a wrong answer here either buries a memory or lets a coincidental
    token match override a real finding.
    """
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    record_id = database["record_id"]

    assert store.settled_projection_record_ids(owner) == frozenset()

    record = store.get_record(owner, record_id)
    assert record is not None
    claim = store.claim_reconciliation_turn(owner, record_id, 1)
    assert claim is not None
    assert store.compare_and_set_provider_ref(
        owner,
        record_id,
        expected_record=record,
        expected_provider_ref=None,
        reconciliation_claim=claim,
        provider_ref="projected-bulk-read",
    )

    projected = store.settled_projection_record_ids(owner)

    assert projected == frozenset({record_id})
    # Agrees with the per-record read it replaces in bulk.
    assert store.get_provider_ref(owner, record_id) == "projected-bulk-read"

    # An edit whose projection failed leaves the old pointer in place and the
    # old ref queued for cleanup. The row is still there, but it now describes
    # superseded text, so it must stop counting as coverage.
    assert store.track_provider_cleanup_target(
        owner,
        record_id,
        "projected-bulk-read",
    )

    assert store.settled_projection_record_ids(owner) == frozenset()
    assert store.get_provider_ref(owner, record_id) == "projected-bulk-read"
