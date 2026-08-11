"""Real-Postgres proof for crash-safe owner reset reconciliation."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
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

MEMORY_TABLES = (
    "memory_settings",
    "memory_candidates",
    "memory_consent_actions",
    "memory_records",
    "memory_provenance",
    "memory_prompt_history",
    "memory_reconciliations",
    "memory_provider_projections",
    "memory_provider_cleanup",
)


def _seed_owner(connection: Any) -> RegisteredMemoryOwner:
    owner_id = str(uuid.uuid4())
    email = f"memory-reset-{owner_id[:8]}@example.com"
    connection.execute(
        "insert into auth.users (id,email,is_anonymous) values (%s,%s,false)",
        (owner_id, email),
    )
    connection.execute(
        "insert into public.profiles (id,email) values (%s,%s)",
        (owner_id, email),
    )
    return RegisteredMemoryOwner(owner_id=owner_id)


def _seed_record(connection: Any, owner: RegisteredMemoryOwner) -> str:
    suffix = uuid.uuid4().hex
    candidate_id = f"candidate-{suffix}"
    receipt_id = f"receipt-{suffix}"
    record_id = f"record-{suffix}"
    connection.execute(
        """
        insert into public.memory_candidates (
          id,owner_id,category,source_label,source_value,future_benefit,
          trigger,proposed_context,opt_in_scope,sensitivity_status,
          sensitivity_flags,sensitivity_policy_version,sensitivity_content_digest
        )
        values (
          %s,%s,'explicit_decision_note','Saved decision','Keep watching.',
          'Revisit the saved decision.','explicit_request','ordinary',
          array['explicit_decision_note'],'clear','{}'::text[],
          'argus.memory-sensitivity/v1',%s
        )
        """,
        (candidate_id, owner.owner_id, f"sha256:{'4' * 64}"),
    )
    connection.execute(
        """
        insert into public.memory_consent_actions (
          id,owner_id,action,candidate_id,requested_scope,granted_scope,
          effective_scope,idempotency_key
        )
        values (
          %s,%s,'candidate_confirmation',%s,
          array['explicit_decision_note'],array['explicit_decision_note'],
          array['explicit_decision_note'],%s
        )
        """,
        (receipt_id, owner.owner_id, candidate_id, candidate_id),
    )
    connection.execute(
        """
        insert into public.memory_records (
          id,owner_id,candidate_id,consent_action_id,category,label,value
        )
        values (
          %s,%s,%s,%s,'explicit_decision_note','Saved decision','Keep watching.'
        )
        """,
        (record_id, owner.owner_id, candidate_id, receipt_id),
    )
    return record_id


def _counts(owner: RegisteredMemoryOwner) -> tuple[int, ...]:
    with psycopg.connect(DSN, autocommit=True) as connection:
        return tuple(
            int(
                connection.execute(
                    f"select count(*) from public.{table} where owner_id=%s",
                    (owner.owner_id,),
                ).fetchone()[0]
            )
            for table in MEMORY_TABLES
        )


@pytest.fixture
def database() -> Iterator[dict[str, Any]]:
    pool = ConnectionPool(
        conninfo=DSN,
        kwargs={"autocommit": True},
        min_size=0,
        max_size=6,
        open=True,
        timeout=2,
        name=f"memory-reset-{uuid.uuid4()}",
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        owner = _seed_owner(connection)
        other_owner = _seed_owner(connection)
    try:
        yield {"pool": pool, "owner": owner, "other_owner": other_owner}
    finally:
        pool.close()
        with psycopg.connect(DSN, autocommit=True) as connection:
            connection.execute(
                "delete from auth.users where id=any(%s::uuid[])",
                ([owner.owner_id, other_owner.owner_id],),
            )


def test_sql_accepts_only_reset_sentinel_operation_shape(
    database: dict[str, Any],
) -> None:
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,'',1,'reset','pending')
            """,
            (owner.owner_id,),
        )
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute(
                """
                insert into public.memory_reconciliations (
                  owner_id,record_id,generation,operation,status
                )
                values (%s,'record-not-sentinel',1,'reset','pending')
                """,
                (database["other_owner"].owner_id,),
            )
        with pytest.raises(psycopg.errors.CheckViolation):
            connection.execute(
                """
                insert into public.memory_reconciliations (
                  owner_id,record_id,generation,operation,status
                )
                values (%s,'',2,'delete','pending')
                """,
                (owner.owner_id,),
            )


def test_reset_without_provider_state_has_no_reconciliation_work(
    database: dict[str, Any],
) -> None:
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        _seed_record(connection, owner)
    store = PostgresCanonicalMemoryStore(database["pool"])

    result = store.reset(owner)

    assert result.changed is True
    assert result.provider_state_existed is False
    assert result.reconciliation_generation is None
    assert _counts(owner) == (0,) * len(MEMORY_TABLES)


def test_reset_crash_reuses_generation_and_restart_completion_reaches_zero(
    database: dict[str, Any],
) -> None:
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        record_id = _seed_record(connection, owner)
    first_store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "reset-after-restart",
    )
    assert first_store.set_provider_ref(owner, record_id, "provider-reset-crash")

    initial = first_store.reset(owner)

    assert initial.changed is True
    assert initial.provider_state_existed is True
    assert initial.reconciliation_generation == 1
    assert _counts(owner) == (0, 0, 0, 0, 0, 0, 1, 0, 1)

    restarted_store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "reset-after-restart",
    )
    replay = restarted_store.reset(owner)
    assert replay.changed is False
    assert replay.provider_state_existed is True
    assert replay.reconciliation_generation == 1
    claim = restarted_store.claim_reconciliation_turn(owner, "", 1)
    assert claim == ReconciliationClaim(
        record_id="",
        generation=1,
        operation="reset",
        claim_token="reset-after-restart",
    )
    assert restarted_store.complete_owner_reset(owner, claim)
    assert _counts(owner) == (0,) * len(MEMORY_TABLES)


def test_failed_reset_retry_gets_new_generation_and_stale_claim_cannot_complete(
    database: dict[str, Any],
) -> None:
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        record_id = _seed_record(connection, owner)
    tokens = iter(("reset-first", "reset-second"))
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: next(tokens),
    )
    assert store.set_provider_ref(owner, record_id, "provider-reset-retry")
    first = store.reset(owner)
    assert first.reconciliation_generation == 1
    first_claim = store.claim_reconciliation_turn(owner, "", 1)
    assert first_claim is not None
    assert store.finish_reconciliation_claim(
        owner,
        first_claim,
        succeeded=False,
        error_code="provider_reconciliation_required",
        completed_at=datetime.now(timezone.utc),
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        assert connection.execute(
            """
            select generation,status,error_code
              from public.memory_reconciliations
             where owner_id=%s and record_id='' and operation='reset'
            """,
            (owner.owner_id,),
        ).fetchall() == [
            (1, "failed", "provider_reconciliation_required"),
        ]

    retry = store.reset(owner)

    assert retry.changed is False
    assert retry.reconciliation_generation == 2
    second_claim = store.claim_reconciliation_turn(owner, "", 2)
    assert second_claim is not None
    assert not store.complete_owner_reset(owner, first_claim)
    assert store.complete_owner_reset(owner, second_claim)
    assert _counts(owner) == (0,) * len(MEMORY_TABLES)


def test_expired_reset_lease_is_reclaimed_by_database_time(
    database: dict[str, Any],
) -> None:
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        record_id = _seed_record(connection, owner)
    first = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "reset-expired",
        reconciliation_lease=timedelta(milliseconds=100),
    )
    assert first.set_provider_ref(owner, record_id, "provider-reset-expired")
    reset = first.reset(owner)
    assert reset.reconciliation_generation == 1
    expired = first.claim_reconciliation_turn(owner, "", 1)
    assert expired is not None
    time.sleep(0.15)
    second = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: "reset-reclaimed",
    )

    reclaimed = second.claim_reconciliation_turn(owner, "", 1)

    assert reclaimed is not None
    assert reclaimed.claim_token == "reset-reclaimed"
    assert not second.complete_owner_reset(owner, expired)
    assert second.complete_owner_reset(owner, reclaimed)


def test_unresolved_reset_blocks_record_projection_claim_but_not_other_owner(
    database: dict[str, Any],
) -> None:
    owner = database["owner"]
    other_owner = database["other_owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        old_record_id = _seed_record(connection, owner)
        other_record_id = _seed_record(connection, other_owner)
    store = PostgresCanonicalMemoryStore(database["pool"])
    assert store.set_provider_ref(owner, old_record_id, "provider-reset-block")
    reset = store.reset(owner)
    assert reset.reconciliation_generation == 1
    with psycopg.connect(DSN, autocommit=True) as connection:
        fresh_record_id = _seed_record(connection, owner)
        connection.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,1,'create','pending')
            """,
            (owner.owner_id, fresh_record_id),
        )
        connection.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,1,'create','pending')
            """,
            (other_owner.owner_id, other_record_id),
        )

    assert store.claim_reconciliation_turn(owner, fresh_record_id, 1) is None
    assert store.claim_reconciliation_turn(other_owner, other_record_id, 1) is not None


def test_reset_retry_supersedes_fresh_work_blocked_by_existing_reset(
    database: dict[str, Any],
) -> None:
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        original_record_id = _seed_record(connection, owner)
    tokens = iter(("reset-failed", "reset-retry"))
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_token_factory=lambda: next(tokens),
        reconciliation_wait_attempts=2,
        reconciliation_wait_seconds=0,
    )
    assert store.set_provider_ref(
        owner,
        original_record_id,
        "provider-reset-cycle",
    )
    first = store.reset(owner)
    assert first.reconciliation_generation == 1
    first_claim = store.claim_reconciliation_turn(owner, "", 1)
    assert first_claim is not None
    assert store.finish_reconciliation_claim(
        owner,
        first_claim,
        succeeded=False,
        error_code="provider_reconciliation_required",
        completed_at=datetime.now(timezone.utc),
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        fresh_record_id = _seed_record(connection, owner)
        connection.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,1,'create','pending')
            """,
            (owner.owner_id, fresh_record_id),
        )
    assert store.claim_reconciliation_turn(owner, fresh_record_id, 1) is None

    retry = store.reset(owner)

    assert retry.changed is True
    assert retry.provider_state_existed is True
    assert retry.reconciliation_generation == 2
    assert store.get_record(owner, fresh_record_id) is None
    assert _counts(owner) == (0, 0, 0, 0, 0, 0, 2, 0, 1)
    retry_claim = store.claim_reconciliation_turn(owner, "", 2)
    assert retry_claim is not None
    assert store.complete_owner_reset(owner, retry_claim)
    assert _counts(owner) == (0,) * len(MEMORY_TABLES)


def test_first_reset_still_waits_for_genuine_pre_reset_work(
    database: dict[str, Any],
) -> None:
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        record_id = _seed_record(connection, owner)
        connection.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,1,'create','pending')
            """,
            (owner.owner_id, record_id),
        )
    store = PostgresCanonicalMemoryStore(
        database["pool"],
        reconciliation_wait_attempts=2,
        reconciliation_wait_seconds=0,
    )
    before = _counts(owner)

    with pytest.raises(TimeoutError, match="provider reconciliation"):
        store.reset(owner)

    assert _counts(owner) == before
