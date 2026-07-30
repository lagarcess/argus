"""Real-Postgres contract for inspectable personalization-memory controls."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from argus.memory.contracts import (
    MemoryCategory,
    MemoryConsentActionReceipt,
    MemoryConsentSettings,
    MemoryProvenance,
    MemoryRecord,
    MemorySourceKind,
)
from argus.memory.postgres_store import PostgresCanonicalMemoryStore
from argus.memory.subject import (
    PersonalizationMemoryUnavailable,
    RegisteredMemoryOwner,
)
from faker import Faker
from psycopg_pool import ConnectionPool

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")
fake = Faker()

NOW = datetime(2026, 7, 29, 21, 0, tzinfo=timezone.utc)
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


def _seed_identity(connection: Any) -> str:
    owner_id = str(uuid.uuid4())
    email = fake.unique.email()
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id, email, is_anonymous) values (%s, %s, false)",
            (owner_id, email),
        )
        cursor.execute(
            "insert into public.profiles (id, email) values (%s, %s)",
            (owner_id, email),
        )
    return owner_id


def _seed_canonical_sources(connection: Any, owner_id: str) -> dict[str, str]:
    ids = {
        "conversation_id": str(uuid.uuid4()),
        "idea_id": str(uuid.uuid4()),
        "idea_version_id": str(uuid.uuid4()),
        "evidence_id": str(uuid.uuid4()),
        "decision_id": str(uuid.uuid4()),
    }
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.conversations (
              id, user_id, title, title_source, created_at, updated_at
            )
            values (%s, %s, 'Memory control source', 'user_renamed', %s, %s)
            """,
            (ids["conversation_id"], owner_id, NOW, NOW),
        )
        cursor.execute(
            """
            insert into public.ideas (
              id, user_id, source_conversation_id, title, summary,
              lifecycle, created_at, updated_at
            )
            values (%s, %s, %s, 'Control idea', 'Control summary',
                    'decided', %s, %s)
            """,
            (ids["idea_id"], owner_id, ids["conversation_id"], NOW, NOW),
        )
        cursor.execute(
            """
            insert into public.idea_versions (
              id, user_id, idea_id, source_conversation_id, version_number,
              canonical_spec, strategy_snapshot, title, summary, lifecycle,
              created_at
            )
            values (
              %s, %s, %s, %s, 1, '{}'::jsonb, '{}'::jsonb,
              'Control version', 'Control version summary', 'decided', %s
            )
            """,
            (
                ids["idea_version_id"],
                owner_id,
                ids["idea_id"],
                ids["conversation_id"],
                NOW,
            ),
        )
        cursor.execute(
            "update public.ideas set active_version_id = %s where id = %s",
            (ids["idea_version_id"], ids["idea_id"]),
        )
        cursor.execute(
            """
            insert into public.evidence_artifacts (
              id, user_id, idea_id, idea_version_id, source_conversation_id,
              artifact_type, lifecycle, title, digest, payload,
              created_at, updated_at
            )
            values (
              %s, %s, %s, %s, %s, 'backtest', 'decided',
              'Control evidence', 'Canonical evidence is unchanged.',
              '{}'::jsonb, %s, %s
            )
            """,
            (
                ids["evidence_id"],
                owner_id,
                ids["idea_id"],
                ids["idea_version_id"],
                ids["conversation_id"],
                NOW,
                NOW,
            ),
        )
        cursor.execute(
            """
            insert into public.decision_notes (
              id, user_id, idea_id, idea_version_id, evidence_artifact_id,
              source_conversation_id, decision_state, note,
              created_at, updated_at
            )
            values (
              %s, %s, %s, %s, %s, %s, 'watching',
              'Canonical decision is unchanged.', %s, %s
            )
            """,
            (
                ids["decision_id"],
                owner_id,
                ids["idea_id"],
                ids["idea_version_id"],
                ids["evidence_id"],
                ids["conversation_id"],
                NOW,
                NOW,
            ),
        )
    return ids


@pytest.fixture
def database() -> Iterator[dict[str, Any]]:
    pool = ConnectionPool(
        conninfo=DSN,
        kwargs={"autocommit": True},
        min_size=0,
        max_size=8,
        open=True,
        timeout=2,
        name=f"memory-task-4-{uuid.uuid4()}",
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        owner_id = _seed_identity(connection)
        other_owner_id = _seed_identity(connection)
        sources = _seed_canonical_sources(connection, owner_id)
        other_sources = _seed_canonical_sources(connection, other_owner_id)
    try:
        yield {
            "pool": pool,
            "owner": RegisteredMemoryOwner(owner_id=owner_id),
            "other_owner": RegisteredMemoryOwner(owner_id=other_owner_id),
            "sources": sources,
            "other_sources": other_sources,
        }
    finally:
        pool.close()
        with psycopg.connect(DSN, autocommit=True) as connection:
            connection.execute(
                "delete from auth.users where id = any(%s::uuid[])",
                ([owner_id, other_owner_id],),
            )


def _seed_record(
    connection: Any,
    owner: RegisteredMemoryOwner,
    sources: dict[str, str],
    *,
    ordinal: int = 0,
    record_id: str | None = None,
    category: MemoryCategory = MemoryCategory.EXPLICIT_DECISION_NOTE,
    created_at: datetime | None = None,
) -> MemoryRecord:
    created_at = created_at or NOW
    record_id = record_id or f"record-{ordinal:03d}-{uuid.uuid4()}"
    candidate_id = f"candidate-{ordinal:03d}-{uuid.uuid4()}"
    receipt_id = f"receipt-{ordinal:03d}-{uuid.uuid4()}"
    label = f"Remember decision {ordinal:03d}"
    value = f"Decision memory value {ordinal:03d}"
    primary = MemoryProvenance(
        source_kind=MemorySourceKind.DECISION_NOTE,
        source_id=sources["decision_id"],
        source_version=NOW.isoformat().replace("+00:00", "Z"),
    )
    supporting = MemoryProvenance(
        source_kind=MemorySourceKind.EVIDENCE_ARTIFACT,
        source_id=sources["evidence_id"],
        source_version="evidence-v1",
    )
    receipt = MemoryConsentActionReceipt(
        id=receipt_id,
        action="candidate_confirmation",
        owner_id=owner.owner_id,
        candidate_id=candidate_id,
        requested_scope=frozenset({category}),
        granted_scope=frozenset({category}),
        effective_scope=frozenset({category}),
        recorded_at=created_at,
        idempotency_key=candidate_id,
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.memory_candidates (
              id, owner_id, category, source_label, source_value,
              future_benefit, trigger, proposed_context, opt_in_scope,
              sensitivity_status, sensitivity_flags,
              sensitivity_policy_version, sensitivity_content_digest,
              created_at
            )
            values (
              %s, %s, %s, %s, %s,
              'Revisit this confirmed decision later.',
              'explicit_request', 'ordinary', %s,
              'clear', '{}'::text[], 'argus.memory-sensitivity/v1',
              %s, %s
            )
            """,
            (
                candidate_id,
                owner.owner_id,
                category.value,
                label,
                value,
                [category.value],
                f"sha256:{'0' * 64}",
                created_at,
            ),
        )
        cursor.execute(
            """
            insert into public.memory_consent_actions (
              id, owner_id, action, candidate_id, requested_scope,
              granted_scope, effective_scope, recorded_at, idempotency_key
            )
            values (%s, %s, 'candidate_confirmation', %s, %s, %s, %s, %s, %s)
            """,
            (
                receipt_id,
                owner.owner_id,
                candidate_id,
                [category.value],
                [category.value],
                [category.value],
                created_at,
                candidate_id,
            ),
        )
        cursor.execute(
            """
            insert into public.memory_settings (owner_id, category)
            values (%s, %s)
            on conflict (owner_id, category) do nothing
            """,
            (owner.owner_id, category.value),
        )
        cursor.execute(
            """
            insert into public.memory_records (
              id, owner_id, candidate_id, consent_action_id, category,
              label, value, revision, created_at, updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s)
            """,
            (
                record_id,
                owner.owner_id,
                candidate_id,
                receipt_id,
                category.value,
                label,
                value,
                created_at,
                created_at,
            ),
        )
        for provenance_ordinal, provenance in enumerate((primary, supporting)):
            cursor.execute(
                """
                insert into public.memory_provenance (
                  owner_id, record_id, ordinal,
                  source_kind, source_id, source_version
                )
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    owner.owner_id,
                    record_id,
                    provenance_ordinal,
                    provenance.source_kind.value,
                    provenance.source_id,
                    provenance.source_version,
                ),
            )
        cursor.execute(
            """
            delete from public.memory_candidates
             where owner_id = %s and id = %s
            """,
            (owner.owner_id, candidate_id),
        )
        cursor.execute(
            """
            insert into public.memory_reconciliations (
              owner_id, record_id, generation, operation,
              status, created_at
            )
            values (%s, %s, 1, 'create', 'pending', %s)
            """,
            (owner.owner_id, record_id, created_at),
        )
        cursor.execute(
            """
            update public.memory_reconciliations
               set status='running',
                   claim_token=%s,
                   lease_expires_at=now() + interval '1 hour',
                   attempt_count=1
             where owner_id=%s and record_id=%s and generation=1
            """,
            (f"seed-{record_id}", owner.owner_id, record_id),
        )
        cursor.execute(
            """
            update public.memory_reconciliations
               set status='succeeded',
                   claim_token=null,
                   lease_expires_at=null,
                   completed_at=%s
             where owner_id=%s and record_id=%s and generation=1
            """,
            (created_at, owner.owner_id, record_id),
        )
    return MemoryRecord(
        id=record_id,
        owner_id=owner.owner_id,
        candidate_id=candidate_id,
        category=category,
        label=label,
        value=value,
        provenance=primary,
        provenance_refs=(primary, supporting),
        consent_receipt=receipt,
        created_at=created_at,
        updated_at=created_at,
    )


def _seed_pending_candidate(
    connection: Any,
    owner: RegisteredMemoryOwner,
    sources: dict[str, str],
    *,
    category: MemoryCategory = MemoryCategory.WORKFLOW_PREFERENCE,
) -> str:
    candidate_id = f"pending-{uuid.uuid4()}"
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.memory_candidates (
              id, owner_id, category, source_label, source_value,
              future_benefit, trigger, proposed_context, opt_in_scope,
              sensitivity_status, sensitivity_flags,
              sensitivity_policy_version, sensitivity_content_digest,
              created_at
            )
            values (
              %s, %s, %s, 'Show assumptions first',
              'Show assumptions before explanations.',
              'Future explanations stay consistent.',
              'assisted_stable_preference', 'ordinary', %s,
              'clear', '{}'::text[], 'argus.memory-sensitivity/v1',
              %s, %s
            )
            """,
            (
                candidate_id,
                owner.owner_id,
                category.value,
                [category.value],
                f"sha256:{'1' * 64}",
                NOW,
            ),
        )
        cursor.execute(
            """
            insert into public.memory_provenance (
              owner_id, candidate_id, ordinal,
              source_kind, source_id, source_version
            )
            values (%s, %s, 0, 'decision_note', %s, 'decision-v1')
            """,
            (owner.owner_id, candidate_id, sources["decision_id"]),
        )
        cursor.execute(
            """
            insert into public.memory_settings (owner_id, category)
            values (%s, %s)
            on conflict (owner_id, category) do nothing
            """,
            (owner.owner_id, category.value),
        )
        cursor.execute(
            """
            insert into public.memory_prompt_history (
              owner_id, category, last_proactive_prompt_at,
              last_declined_at, updated_at
            )
            values (%s, %s, %s, %s, %s)
            on conflict (owner_id, category) do update
              set last_proactive_prompt_at = excluded.last_proactive_prompt_at,
                  last_declined_at = excluded.last_declined_at,
                  updated_at = excluded.updated_at
            """,
            (
                owner.owner_id,
                category.value,
                NOW - timedelta(hours=2),
                NOW - timedelta(hours=1),
                NOW,
            ),
        )
    return candidate_id


def _source_snapshot(owner_id: str) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            decision = cursor.execute(
                """
                select id, idea_id, idea_version_id, evidence_artifact_id,
                       decision_state, note, created_at, updated_at
                  from public.decision_notes
                 where user_id = %s
                 order by id
                """,
                (owner_id,),
            ).fetchall()
            evidence = cursor.execute(
                """
                select id, idea_id, idea_version_id, lifecycle, title, digest,
                       payload, created_at, updated_at
                  from public.evidence_artifacts
                 where user_id = %s
                 order by id
                """,
                (owner_id,),
            ).fetchall()
    return tuple(decision), tuple(evidence)


def _table_counts(owner_id: str) -> tuple[int, ...]:
    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            return tuple(
                cursor.execute(
                    f"select count(*) from public.{table} where owner_id = %s",
                    (owner_id,),
                ).fetchone()[0]
                for table in MEMORY_TABLES
            )


def _memory_snapshot(owner_id: str) -> dict[str, tuple[tuple[Any, ...], ...]]:
    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            return {
                table: tuple(
                    cursor.execute(
                        f"select * from public.{table} "
                        "where owner_id = %s order by 1, 2",
                        (owner_id,),
                    ).fetchall()
                )
                for table in MEMORY_TABLES
            }


def _reconciliation_rows(
    owner_id: str,
    record_id: str,
) -> tuple[tuple[Any, ...], ...]:
    with psycopg.connect(DSN, autocommit=True) as connection:
        return tuple(
            connection.execute(
                """
                select generation, operation, status
                  from public.memory_reconciliations
                 where owner_id = %s and record_id = %s
                 order by generation
                """,
                (owner_id, record_id),
            ).fetchall()
        )


def _set_projection(
    owner: RegisteredMemoryOwner,
    record_id: str,
    provider_ref: str,
    *,
    generation: int,
) -> None:
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(
            """
            insert into public.memory_provider_projections (
              owner_id, record_id, provider_ref, generation, updated_at
            )
            values (%s, %s, %s, %s, %s)
            """,
            (owner.owner_id, record_id, provider_ref, generation, NOW),
        )


def _set_cleanup(
    owner: RegisteredMemoryOwner,
    record_id: str,
    provider_ref: str,
    *,
    generation: int,
    status: str = "pending",
) -> None:
    resolved_at = NOW if status == "resolved" else None
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(
            """
            insert into public.memory_provider_cleanup (
              owner_id, record_id, provider_ref, generation,
              status, created_at, resolved_at
            )
            values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                owner.owner_id,
                record_id,
                provider_ref,
                generation,
                status,
                NOW,
                resolved_at,
            ),
        )


def test_reads_are_bounded_newest_first_exact_and_inspectable_when_disabled(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    other_owner = database["other_owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        expected = tuple(
            _seed_record(
                connection,
                owner,
                database["sources"],
                ordinal=index,
                created_at=NOW + timedelta(microseconds=index),
            )
            for index in range(102)
        )
        other = _seed_record(
            connection,
            other_owner,
            database["other_sources"],
            ordinal=999,
        )
        connection.execute(
            "delete from public.memory_settings where owner_id = %s",
            (owner.owner_id,),
        )

    records = store.list_records(owner)
    receipts = store.list_consent_receipts(owner)

    assert records == tuple(reversed(expected[-100:]))
    assert receipts == tuple(record.consent_receipt for record in records)
    assert store.get_record(owner, expected[-1].id) == expected[-1]
    assert store.get_record(owner, other.id) is None
    assert store.list_records(other_owner) == (other,)
    assert store.get_settings(owner) == MemoryConsentSettings()
    assert records[0].provenance_refs == expected[-1].provenance_refs
    assert records[0].consent_receipt == expected[-1].consent_receipt


class _ExplodingPool:
    def connection(self) -> None:
        raise AssertionError("pool touched before UUID validation")


@pytest.mark.parametrize(
    "operation",
    (
        "list_consent_receipts",
        "list_records",
        "get_record",
        "edit_record",
        "delete_record",
        "disable",
        "reset",
    ),
)
def test_controls_validate_owner_uuid_before_pool(operation: str) -> None:
    store = PostgresCanonicalMemoryStore(cast(ConnectionPool[Any], _ExplodingPool()))
    owner = RegisteredMemoryOwner(owner_id="not-a-uuid")

    with pytest.raises(ValueError, match="memory owner id must be a valid UUID"):
        if operation == "get_record":
            store.get_record(owner, "record")
        elif operation == "edit_record":
            store.edit_record(
                owner,
                "record",
                value="changed",
                label=None,
            )
        elif operation == "delete_record":
            store.delete_record(owner, "record")
        else:
            cast(Callable[[RegisteredMemoryOwner], object], getattr(store, operation))(
                owner
            )


@pytest.mark.parametrize(
    "operation",
    (
        "list_consent_receipts",
        "list_records",
        "get_record",
        "edit_record",
        "delete_record",
        "disable",
        "reset",
    ),
)
def test_controls_recheck_database_registered_owner_before_effect(
    database: dict[str, Any],
    operation: str,
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        record = _seed_record(connection, owner, database["sources"])
        connection.execute(
            "update auth.users set is_anonymous = true where id = %s",
            (owner.owner_id,),
        )
    before = _memory_snapshot(owner.owner_id)

    with pytest.raises(PersonalizationMemoryUnavailable):
        if operation == "get_record":
            store.get_record(owner, record.id)
        elif operation == "edit_record":
            store.edit_record(
                owner,
                record.id,
                value="must not change",
                label=None,
                clock=lambda: NOW + timedelta(hours=1),
            )
        elif operation == "delete_record":
            store.delete_record(owner, record.id)
        else:
            cast(Callable[[RegisteredMemoryOwner], object], getattr(store, operation))(
                owner
            )

    assert _memory_snapshot(owner.owner_id) == before


def test_edit_preserves_identity_and_rolls_back_noop_or_invalid_updates(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        original = _seed_record(connection, owner, database["sources"])
    source_before = _source_snapshot(owner.owner_id)

    mutation = store.edit_record(
        owner,
        original.id,
        value="Updated user-confirmed memory value.",
        label=None,
        clock=lambda: NOW + timedelta(hours=1),
    )

    assert mutation is not None
    assert mutation.before == original
    assert mutation.after is not None
    updated = mutation.after
    assert updated.model_dump(
        exclude={"value", "revision", "updated_at"}
    ) == original.model_dump(exclude={"value", "revision", "updated_at"})
    assert updated.value == "Updated user-confirmed memory value."
    assert updated.revision == 2
    assert updated.updated_at > original.updated_at
    assert mutation.reconciliation_generation == 2
    assert _reconciliation_rows(owner.owner_id, original.id) == (
        (1, "create", "succeeded"),
        (2, "update", "pending"),
    )
    assert _source_snapshot(owner.owner_id) == source_before

    before_noop = _memory_snapshot(owner.owner_id)
    with pytest.raises(ValueError, match="memory edit must change value or label"):
        store.edit_record(
            owner,
            original.id,
            value=updated.value,
            label=None,
            clock=lambda: NOW + timedelta(hours=2),
        )
    assert _memory_snapshot(owner.owner_id) == before_noop

    with pytest.raises(ValueError, match="later than the current update time"):
        store.edit_record(
            owner,
            original.id,
            value=None,
            label="Invalid time",
            clock=lambda: updated.updated_at,
        )
    assert _memory_snapshot(owner.owner_id) == before_noop

    with pytest.raises(ValueError):
        store.edit_record(
            owner,
            original.id,
            value=None,
            label=" ",
            clock=lambda: NOW + timedelta(hours=2),
        )
    assert _memory_snapshot(owner.owner_id) == before_noop


def test_concurrent_disjoint_edits_preserve_both_changes(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        original = _seed_record(connection, owner, database["sources"])
    barrier = threading.Barrier(2)
    counter_lock = threading.Lock()
    next_tick = 0

    def clock() -> datetime:
        nonlocal next_tick
        with counter_lock:
            next_tick += 1
            return NOW + timedelta(hours=next_tick)

    def edit_label() -> None:
        barrier.wait()
        assert (
            store.edit_record(
                owner,
                original.id,
                value=None,
                label="Updated label",
                clock=clock,
            )
            is not None
        )

    def edit_value() -> None:
        barrier.wait()
        assert (
            store.edit_record(
                owner,
                original.id,
                value="Updated value",
                label=None,
                clock=clock,
            )
            is not None
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (executor.submit(edit_label), executor.submit(edit_value))
        for future in futures:
            future.result(timeout=5)

    final = store.get_record(owner, original.id)
    assert final is not None
    assert final.label == "Updated label"
    assert final.value == "Updated value"
    assert final.revision == 3
    assert _reconciliation_rows(owner.owner_id, original.id) == (
        (1, "create", "succeeded"),
        (2, "update", "pending"),
        (3, "update", "pending"),
    )


def test_delete_snapshots_cleanup_and_preserves_receipt_and_sources(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        original = _seed_record(connection, owner, database["sources"])
    _set_projection(owner, original.id, "provider-current", generation=1)
    _set_cleanup(owner, original.id, "provider-stale", generation=1)
    source_before = _source_snapshot(owner.owner_id)

    mutation = store.delete_record(owner, original.id)

    assert mutation is not None
    assert mutation.before == original
    assert mutation.after is None
    assert mutation.provider_ref == "provider-current"
    assert mutation.cleanup_refs == ("provider-current", "provider-stale")
    assert mutation.reconciliation_generation == 2
    assert store.get_record(owner, original.id) is None
    assert store.list_consent_receipts(owner) == (original.consent_receipt,)
    assert _source_snapshot(owner.owner_id) == source_before
    assert _reconciliation_rows(owner.owner_id, original.id) == (
        (1, "create", "succeeded"),
        (2, "delete", "pending"),
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        cleanup = connection.execute(
            """
            select provider_ref, generation, status
              from public.memory_provider_cleanup
             where owner_id = %s and record_id = %s
             order by provider_ref
            """,
            (owner.owner_id, original.id),
        ).fetchall()
        assert cleanup == [
            ("provider-current", 1, "pending"),
            ("provider-stale", 1, "pending"),
        ]
        assert (
            connection.execute(
                """
            select count(*) from public.memory_provenance
             where owner_id = %s and record_id = %s
            """,
                (owner.owner_id, original.id),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                """
            select count(*) from public.memory_provider_projections
             where owner_id = %s and record_id = %s
            """,
                (owner.owner_id, original.id),
            ).fetchone()[0]
            == 0
        )


def test_delete_timeout_changes_nothing(
    database: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import argus.memory.postgres_store as postgres_store

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        original = _seed_record(connection, owner, database["sources"])
        connection.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,2,'update','pending')
            """,
            (owner.owner_id, original.id),
        )
    _set_projection(owner, original.id, "provider-current", generation=1)
    before = _memory_snapshot(owner.owner_id)
    monkeypatch.setattr(postgres_store, "_RECONCILIATION_WAIT_ATTEMPTS", 2)
    monkeypatch.setattr(postgres_store, "_RECONCILIATION_WAIT_SECONDS", 0.0)

    with pytest.raises(TimeoutError, match="provider reconciliation"):
        store.delete_record(owner, original.id)

    assert _memory_snapshot(owner.owner_id) == before


def test_disable_clears_only_opt_in_candidate_and_history_state(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        record = _seed_record(connection, owner, database["sources"])
        _seed_pending_candidate(connection, owner, database["sources"])
    _set_projection(owner, record.id, "provider-current", generation=1)
    _set_cleanup(owner, record.id, "provider-stale", generation=1)
    source_before = _source_snapshot(owner.owner_id)

    assert store.disable(owner) is True

    assert store.get_settings(owner) == MemoryConsentSettings()
    assert store.list_candidates(owner) == ()
    assert store.list_records(owner) == (record,)
    assert store.list_consent_receipts(owner) == (record.consent_receipt,)
    assert _table_counts(owner.owner_id) == (0, 0, 1, 1, 2, 0, 1, 1, 1)
    assert _source_snapshot(owner.owner_id) == source_before
    assert store.disable(owner) is False


def test_reset_without_provider_state_reaches_complete_nine_table_zero(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    other_owner = database["other_owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        _seed_record(connection, owner, database["sources"])
        _seed_pending_candidate(connection, owner, database["sources"])
        other = _seed_record(
            connection,
            other_owner,
            database["other_sources"],
            ordinal=1,
        )
    source_before = _source_snapshot(owner.owner_id)

    reset = store.reset(owner)

    assert reset.changed is True
    assert reset.provider_state_existed is False
    assert _table_counts(owner.owner_id) == (0,) * len(MEMORY_TABLES)
    assert store.list_records(other_owner) == (other,)
    assert _source_snapshot(owner.owner_id) == source_before
    assert store.reset(owner).changed is False


def test_reset_retains_only_unresolved_provider_cleanup_obligations(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        record = _seed_record(connection, owner, database["sources"])
        _seed_pending_candidate(connection, owner, database["sources"])
    _set_projection(owner, record.id, "provider-current", generation=1)
    _set_cleanup(owner, record.id, "provider-stale", generation=1)
    _set_cleanup(
        owner,
        record.id,
        "provider-already-resolved",
        generation=1,
        status="resolved",
    )

    reset = store.reset(owner)

    assert reset.changed is True
    assert reset.provider_state_existed is True
    assert _table_counts(owner.owner_id) == (0, 0, 0, 0, 0, 0, 0, 0, 2)
    with psycopg.connect(DSN, autocommit=True) as connection:
        assert connection.execute(
            """
            select provider_ref, status
              from public.memory_provider_cleanup
             where owner_id = %s
             order by provider_ref
            """,
            (owner.owner_id,),
        ).fetchall() == [
            ("provider-current", "pending"),
            ("provider-stale", "pending"),
        ]

    repeated = store.reset(owner)
    assert repeated.changed is True
    assert repeated.provider_state_existed is True
    assert _table_counts(owner.owner_id) == (0, 0, 0, 0, 0, 0, 0, 0, 2)


def test_reset_timeout_changes_nothing(
    database: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import argus.memory.postgres_store as postgres_store

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    with psycopg.connect(DSN, autocommit=True) as connection:
        record = _seed_record(connection, owner, database["sources"])
        connection.execute(
            """
            insert into public.memory_reconciliations (
              owner_id,record_id,generation,operation,status
            )
            values (%s,%s,2,'update','pending')
            """,
            (owner.owner_id, record.id),
        )
    before = _memory_snapshot(owner.owner_id)
    monkeypatch.setattr(postgres_store, "_RECONCILIATION_WAIT_ATTEMPTS", 2)
    monkeypatch.setattr(postgres_store, "_RECONCILIATION_WAIT_SECONDS", 0.0)

    with pytest.raises(TimeoutError, match="provider reconciliation"):
        store.reset(owner)

    assert _memory_snapshot(owner.owner_id) == before
