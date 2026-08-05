"""Real-Postgres contract for settings, candidates, and proposal history."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from argus.memory.contracts import (
    MemoryCandidate,
    MemoryCategory,
    MemoryConsentSettings,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemorySourceKind,
    SavedDecisionSource,
    SensitivityAssessment,
    SensitivityStatus,
    bind_sensitivity_assessment,
)
from argus.memory.postgres_store import PostgresCanonicalMemoryStore
from argus.memory.store import ProposalHistorySnapshot
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

NOW = datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)


def _seed_identity(connection: Any, *, anonymous: bool = False) -> str:
    owner_id = str(uuid.uuid4())
    email = None if anonymous else fake.unique.email()
    with connection.cursor() as cursor:
        cursor.execute(
            "insert into auth.users (id, email, is_anonymous) values (%s, %s, %s)",
            (owner_id, email, anonymous),
        )
        cursor.execute(
            "insert into public.profiles (id, email) values (%s, %s)",
            (owner_id, email),
        )
        if anonymous:
            cursor.execute(
                """
                insert into public.guest_workspaces (
                  user_id,
                  created_at,
                  expires_at
                )
                values (%s, %s, %s)
                """,
                (owner_id, NOW, NOW + timedelta(days=7)),
            )
    return owner_id


@pytest.fixture
def database() -> Iterator[dict[str, Any]]:
    pool = ConnectionPool(
        conninfo=DSN,
        kwargs={"autocommit": True},
        min_size=0,
        max_size=4,
        open=True,
        timeout=2,
        name=f"memory-task-2-{uuid.uuid4()}",
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        owner_id = _seed_identity(connection)
        other_owner_id = _seed_identity(connection)
    try:
        yield {
            "pool": pool,
            "owner": RegisteredMemoryOwner(owner_id=owner_id),
            "other_owner": RegisteredMemoryOwner(owner_id=other_owner_id),
        }
    finally:
        pool.close()
        with psycopg.connect(DSN, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "delete from auth.users where id = any(%s::uuid[])",
                    ([owner_id, other_owner_id],),
                )


def _candidate(
    owner: RegisteredMemoryOwner,
    *,
    candidate_id: str | None = None,
    category: MemoryCategory = MemoryCategory.WORKFLOW_PREFERENCE,
    trigger: MemoryProposalTrigger = MemoryProposalTrigger.EXPLICIT_REQUEST,
    created_at: datetime = NOW,
) -> MemoryCandidate:
    label = "Show assumptions first"
    value = "Show assumptions before every result explanation."
    future_benefit = "Keeps future result reviews consistent."
    provenance = MemoryProvenance(
        source_kind=MemorySourceKind.DECISION_NOTE,
        source_id=str(uuid.uuid4()),
        source_version="decision-note-v1",
    )
    sensitivity = bind_sensitivity_assessment(
        SensitivityAssessment(status=SensitivityStatus.CLEAR),
        category=category,
        label=label,
        value=value,
        future_benefit=future_benefit,
    )
    return MemoryCandidate(
        id=candidate_id or f"candidate-{uuid.uuid4()}",
        owner_id=owner.owner_id,
        category=category,
        source=SavedDecisionSource(
            label=label,
            value=value,
            provenance=provenance,
        ),
        future_benefit=future_benefit,
        provenance_refs=(
            provenance,
            MemoryProvenance(
                source_kind=MemorySourceKind.EVIDENCE_ARTIFACT,
                source_id=str(uuid.uuid4()),
                source_version="evidence-v1",
            ),
        ),
        trigger=trigger,
        sensitivity=sensitivity,
        proposed_context=MemoryOperationContext.ORDINARY,
        opt_in_scope=frozenset({category}),
        created_at=created_at,
    )


def _memory_row_counts(owner_id: str) -> tuple[int, ...]:
    tables = (
        "memory_settings",
        "memory_candidates",
        "memory_consent_actions",
        "memory_provenance",
        "memory_prompt_history",
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            return tuple(
                cursor.execute(
                    f"select count(*) from public.{table} where owner_id = %s",
                    (owner_id,),
                ).fetchone()[0]
                for table in tables
            )


def test_settings_default_off_replace_scope_and_isolate_owners(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    other_owner = database["other_owner"]
    enabled = MemoryConsentSettings(
        enabled=True,
        enabled_categories=frozenset(
            {
                MemoryCategory.WORKFLOW_PREFERENCE,
                MemoryCategory.PAST_SESSION_ANCHOR,
            }
        ),
    )

    assert store.get_settings(owner) == MemoryConsentSettings()
    assert store.enabled_categories(owner) == frozenset()
    enabled_result = store.enable_categories(
        owner,
        enabled.enabled_categories,
        clock=lambda: NOW,
        id_factory=lambda: f"receipt-{uuid.uuid4()}",
        idempotency_key="settings-test-enable",
    )
    assert enabled_result.settings == enabled
    assert store.get_settings(owner) == enabled
    assert store.get_settings(other_owner) == MemoryConsentSettings()

    narrowed = MemoryConsentSettings(
        enabled=True,
        enabled_categories=frozenset({MemoryCategory.WORKFLOW_PREFERENCE}),
    )
    assert store.set_settings(owner, narrowed) == narrowed
    assert store.set_settings(owner, MemoryConsentSettings()) == MemoryConsentSettings()
    assert store.get_settings(owner) == MemoryConsentSettings()


def test_settings_replacement_cannot_expand_scope_without_consent_receipt(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    enabled = MemoryConsentSettings(
        enabled=True,
        enabled_categories=frozenset({MemoryCategory.WORKFLOW_PREFERENCE}),
    )

    with pytest.raises(
        ValueError,
        match="settings replacement cannot enable new memory categories",
    ):
        store.set_settings(owner, enabled)

    assert store.get_settings(owner) == MemoryConsentSettings()
    assert _memory_row_counts(owner.owner_id) == (0, 0, 0, 0, 0)


def test_enable_categories_persists_one_scoped_idempotent_receipt(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    receipt_id = f"receipt-{uuid.uuid4()}"
    scope = frozenset({MemoryCategory.EXPLICIT_DECISION_NOTE})

    result = store.enable_categories(
        owner,
        scope,
        clock=lambda: NOW,
        id_factory=lambda: receipt_id,
        idempotency_key="enable-saved-decisions",
    )

    assert result.settings.enabled_categories == scope
    assert result.consent_receipt is not None
    assert result.consent_receipt.id == receipt_id
    assert result.consent_receipt.requested_scope == scope
    assert result.consent_receipt.granted_scope == scope
    assert result.consent_receipt.effective_scope == scope

    repeated = store.enable_categories(
        owner,
        scope,
        clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
        id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
        idempotency_key="enable-saved-decisions",
    )
    assert repeated.settings == result.settings
    assert repeated.consent_receipt is None

    with psycopg.connect(DSN, autocommit=True) as connection:
        with connection.cursor() as cursor:
            assert cursor.execute(
                """
                select requested_scope, granted_scope, effective_scope
                  from public.memory_consent_actions
                 where owner_id = %s
                """,
                (owner.owner_id,),
            ).fetchall() == [
                (
                    ["explicit_decision_note"],
                    ["explicit_decision_note"],
                    ["explicit_decision_note"],
                )
            ]


def test_enable_duplicate_receipt_id_rolls_back_settings(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    duplicate_id = f"receipt-{uuid.uuid4()}"
    initial_scope = frozenset({MemoryCategory.WORKFLOW_PREFERENCE})
    store.enable_categories(
        owner,
        initial_scope,
        clock=lambda: NOW,
        id_factory=lambda: duplicate_id,
        idempotency_key="workflow-opt-in",
    )

    with pytest.raises(ValueError, match="consent receipt id already exists"):
        store.enable_categories(
            owner,
            frozenset({MemoryCategory.PERSONALIZATION_PREFERENCE}),
            clock=lambda: NOW + timedelta(minutes=1),
            id_factory=lambda: duplicate_id,
            idempotency_key="personalization-opt-in",
        )

    assert store.enabled_categories(owner) == initial_scope
    assert _memory_row_counts(owner.owner_id)[:3] == (1, 0, 1)


def test_candidate_round_trip_duplicate_discard_and_owner_isolation(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    other_owner = database["other_owner"]
    candidate_id = f"candidate-{uuid.uuid4()}"
    candidate = _candidate(owner, candidate_id=candidate_id)
    other_candidate = _candidate(other_owner, candidate_id=candidate_id)

    assert store.add_candidate_with_prompt(
        owner,
        candidate,
        proactive_prompt_at=None,
        expected_history=None,
    )
    assert store.get_candidate(owner, candidate_id) == candidate
    assert store.list_candidates(owner) == (candidate,)
    assert store.get_candidate(other_owner, candidate_id) is None
    assert store.list_candidates(other_owner) == ()

    assert store.add_candidate_with_prompt(
        other_owner,
        other_candidate,
        proactive_prompt_at=None,
        expected_history=None,
    )
    with pytest.raises(ValueError, match="candidate already exists"):
        store.add_candidate_with_prompt(
            owner,
            candidate,
            proactive_prompt_at=None,
            expected_history=None,
        )

    assert store.discard_candidate(owner, candidate_id)
    assert not store.discard_candidate(owner, candidate_id)
    assert store.get_candidate(other_owner, candidate_id) == other_candidate


def test_proactive_candidate_compare_and_set_has_no_partial_stale_write(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    first_prompt_at = NOW
    second_prompt_at = NOW + timedelta(days=14)
    first = _candidate(
        owner,
        trigger=MemoryProposalTrigger.ASSISTED_STABLE_PREFERENCE,
    )
    stale = _candidate(
        owner,
        trigger=MemoryProposalTrigger.ASSISTED_STABLE_PREFERENCE,
        created_at=NOW + timedelta(days=7),
    )
    current = _candidate(
        owner,
        trigger=MemoryProposalTrigger.ASSISTED_STABLE_PREFERENCE,
        created_at=second_prompt_at,
    )
    empty_history = ProposalHistorySnapshot(
        last_proactive_prompt_at=None,
        last_declined_at=None,
    )

    assert store.add_candidate_with_prompt(
        owner,
        first,
        proactive_prompt_at=first_prompt_at,
        expected_history=empty_history,
    )
    assert (
        store.last_proactive_prompt_at(owner, MemoryCategory.WORKFLOW_PREFERENCE)
        == first_prompt_at
    )

    assert not store.add_candidate_with_prompt(
        owner,
        stale,
        proactive_prompt_at=NOW + timedelta(days=7),
        expected_history=empty_history,
    )
    assert store.get_candidate(owner, stale.id) is None
    assert (
        store.last_proactive_prompt_at(owner, MemoryCategory.WORKFLOW_PREFERENCE)
        == first_prompt_at
    )

    assert store.add_candidate_with_prompt(
        owner,
        current,
        proactive_prompt_at=second_prompt_at,
        expected_history=ProposalHistorySnapshot(
            last_proactive_prompt_at=first_prompt_at,
            last_declined_at=None,
        ),
    )
    assert store.list_candidates(owner) == (first, current)


def test_concurrent_same_history_candidate_admission_has_one_clean_cas_winner(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    category = MemoryCategory.WORKFLOW_PREFERENCE
    first = _candidate(
        owner,
        trigger=MemoryProposalTrigger.ASSISTED_STABLE_PREFERENCE,
    )
    second = _candidate(
        owner,
        trigger=MemoryProposalTrigger.ASSISTED_STABLE_PREFERENCE,
    )
    expected = ProposalHistorySnapshot(
        last_proactive_prompt_at=None,
        last_declined_at=None,
    )
    lock_identity = f"argus:memory:{owner.owner_id}:{category.value}"

    with psycopg.connect(DSN, autocommit=False) as blocker:
        blocker.execute(
            """
            select pg_advisory_xact_lock(
              pg_catalog.hashtextextended(%s, 0)
            )
            """,
            (lock_identity,),
        )
        blocker_pid = blocker.info.backend_pid
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = tuple(
                executor.submit(
                    store.add_candidate_with_prompt,
                    owner,
                    candidate,
                    proactive_prompt_at=NOW,
                    expected_history=expected,
                )
                for candidate in (first, second)
            )
            deadline = time.monotonic() + 2
            waiting = 0
            with psycopg.connect(DSN, autocommit=True) as observer:
                while waiting != 2 and time.monotonic() < deadline:
                    waiting = observer.execute(
                        """
                        select count(*)
                          from pg_catalog.pg_locks as waiting_lock
                         where waiting_lock.locktype = 'advisory'
                           and waiting_lock.granted is false
                           and (
                             waiting_lock.database,
                             waiting_lock.classid,
                             waiting_lock.objid,
                             waiting_lock.objsubid
                           ) in (
                             select
                               held_lock.database,
                               held_lock.classid,
                               held_lock.objid,
                               held_lock.objsubid
                               from pg_catalog.pg_locks as held_lock
                              where held_lock.pid = %s
                                and held_lock.locktype = 'advisory'
                                and held_lock.granted is true
                           )
                        """,
                        (blocker_pid,),
                    ).fetchone()[0]
            assert waiting == 2
            blocker.commit()
            outcomes = tuple(future.result(timeout=2) for future in futures)

    assert sorted(outcomes) == [False, True]
    assert len(store.list_candidates(owner)) == 1
    assert store.last_proactive_prompt_at(owner, category) == NOW
    assert _memory_row_counts(owner.owner_id) == (0, 1, 0, 2, 1)


def test_decline_candidate_and_history_commit_or_rollback_together(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    prompt_at = NOW
    declined_at = NOW + timedelta(hours=1)
    proactive = _candidate(
        owner,
        trigger=MemoryProposalTrigger.SAVED_DECISION,
    )
    explicit = _candidate(owner)
    history = ProposalHistorySnapshot(
        last_proactive_prompt_at=None,
        last_declined_at=None,
    )
    assert store.add_candidate_with_prompt(
        owner,
        proactive,
        proactive_prompt_at=prompt_at,
        expected_history=history,
    )
    assert store.add_candidate_with_prompt(
        owner,
        explicit,
        proactive_prompt_at=None,
        expected_history=None,
    )

    with pytest.raises(
        ValueError,
        match="explicit-request declines cannot write proactive history",
    ):
        store.decline_candidate_with_history(
            owner,
            explicit.id,
            declined_at=declined_at,
        )
    assert store.get_candidate(owner, explicit.id) == explicit

    with pytest.raises(
        ValueError,
        match="proactive declines require one atomic history timestamp",
    ):
        store.decline_candidate_with_history(
            owner,
            proactive.id,
            declined_at=None,
        )
    assert store.get_candidate(owner, proactive.id) == proactive

    assert store.decline_candidate_with_history(
        owner,
        proactive.id,
        declined_at=declined_at,
    )
    assert store.get_candidate(owner, proactive.id) is None
    assert (
        store.last_declined_at(owner, MemoryCategory.WORKFLOW_PREFERENCE) == declined_at
    )


def test_prompt_and_decline_history_round_trip_by_owner_and_category(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    other_owner = database["other_owner"]
    prompt_at = NOW
    declined_at = NOW + timedelta(minutes=10)

    assert (
        store.last_proactive_prompt_at(owner, MemoryCategory.PERSONALIZATION_PREFERENCE)
        is None
    )
    assert (
        store.last_declined_at(owner, MemoryCategory.PERSONALIZATION_PREFERENCE) is None
    )
    store.mark_proactive_prompt(
        owner,
        MemoryCategory.PERSONALIZATION_PREFERENCE,
        prompt_at,
    )
    store.mark_declined(
        owner,
        MemoryCategory.PERSONALIZATION_PREFERENCE,
        declined_at,
    )

    assert (
        store.last_proactive_prompt_at(owner, MemoryCategory.PERSONALIZATION_PREFERENCE)
        == prompt_at
    )
    assert (
        store.last_declined_at(owner, MemoryCategory.PERSONALIZATION_PREFERENCE)
        == declined_at
    )
    assert (
        store.last_proactive_prompt_at(
            other_owner, MemoryCategory.PERSONALIZATION_PREFERENCE
        )
        is None
    )


def test_database_revalidates_registered_owner_before_every_task_two_operation(
    database: dict[str, Any],
) -> None:
    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    candidate = _candidate(owner)
    store.add_candidate_with_prompt(
        owner,
        candidate,
        proactive_prompt_at=None,
        expected_history=None,
    )
    store.mark_proactive_prompt(owner, candidate.category, NOW)
    before = _memory_row_counts(owner.owner_id)

    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(
            "update auth.users set is_anonymous = true where id = %s",
            (owner.owner_id,),
        )

    settings = MemoryConsentSettings(
        enabled=True,
        enabled_categories=frozenset({candidate.category}),
    )
    replacement = _candidate(owner)
    operations: tuple[Callable[[], object], ...] = (
        lambda: store.get_settings(owner),
        lambda: store.enabled_categories(owner),
        lambda: store.set_settings(owner, settings),
        lambda: store.enable_categories(
            owner,
            frozenset({candidate.category}),
            clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
            id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
            idempotency_key="must-not-run",
        ),
        lambda: store.add_candidate_with_prompt(
            owner,
            replacement,
            proactive_prompt_at=None,
            expected_history=None,
        ),
        lambda: store.get_candidate(owner, candidate.id),
        lambda: store.list_candidates(owner),
        lambda: store.discard_candidate(owner, candidate.id),
        lambda: store.decline_candidate_with_history(
            owner,
            candidate.id,
            declined_at=None,
        ),
        lambda: store.last_proactive_prompt_at(owner, candidate.category),
        lambda: store.mark_proactive_prompt(owner, candidate.category, NOW),
        lambda: store.last_declined_at(owner, candidate.category),
        lambda: store.mark_declined(owner, candidate.category, NOW),
    )
    for operation in operations:
        with pytest.raises(PersonalizationMemoryUnavailable):
            operation()

    assert _memory_row_counts(owner.owner_id) == before


class _ForbiddenPool:
    acquisitions = 0

    def connection(self, *_args: object, **_kwargs: object) -> object:
        self.acquisitions += 1
        raise AssertionError("invalid owner reached the database")


def test_invalid_owner_uuid_is_rejected_before_pool_acquisition() -> None:
    pool = _ForbiddenPool()
    store = PostgresCanonicalMemoryStore(cast(ConnectionPool, pool))
    owner = RegisteredMemoryOwner(owner_id="not-a-uuid")

    with pytest.raises(ValueError, match="valid UUID"):
        store.get_settings(owner)

    assert pool.acquisitions == 0
