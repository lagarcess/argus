"""Real-Postgres contract for atomic personalization-memory confirmation."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from argus.memory.contracts import (
    MemoryCandidate,
    MemoryCategory,
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
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import CanonicalMemoryStore, ProposalHistorySnapshot
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
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

NOW = datetime(2026, 7, 29, 19, 0, tzinfo=timezone.utc)
SOURCE_UPDATED_AT = NOW - timedelta(hours=2)
SAVED_DECISION_SCOPE = frozenset(
    {
        MemoryCategory.EXPLICIT_DECISION_NOTE,
        MemoryCategory.PAST_SESSION_ANCHOR,
    }
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


def _seed_canonical_decision(connection: Any, owner_id: str) -> dict[str, str]:
    ids = {
        "conversation_id": str(uuid.uuid4()),
        "message_id": str(uuid.uuid4()),
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
            values (%s, %s, %s, 'user_renamed', %s, %s)
            """,
            (
                ids["conversation_id"],
                owner_id,
                "Lower-drawdown idea",
                SOURCE_UPDATED_AT,
                SOURCE_UPDATED_AT,
            ),
        )
        cursor.execute(
            """
            insert into public.messages (
              id, conversation_id, user_id, role, content, created_at
            )
            values (%s, %s, %s, 'user', %s, %s)
            """,
            (
                ids["message_id"],
                ids["conversation_id"],
                owner_id,
                "Remember why I rejected the first version.",
                SOURCE_UPDATED_AT,
            ),
        )
        cursor.execute(
            """
            insert into public.ideas (
              id, user_id, source_conversation_id, title, summary,
              lifecycle, created_at, updated_at
            )
            values (%s, %s, %s, %s, %s, 'decided', %s, %s)
            """,
            (
                ids["idea_id"],
                owner_id,
                ids["conversation_id"],
                "Lower-drawdown ETH thesis",
                "Compare the lower-drawdown version.",
                SOURCE_UPDATED_AT,
                SOURCE_UPDATED_AT,
            ),
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
              %s, %s, 'decided', %s
            )
            """,
            (
                ids["idea_version_id"],
                owner_id,
                ids["idea_id"],
                ids["conversation_id"],
                "ETH lower-drawdown v1",
                "One material experiment.",
                SOURCE_UPDATED_AT,
            ),
        )
        cursor.execute(
            """
            update public.ideas
               set active_version_id = %s,
                   updated_at = %s
             where id = %s
            """,
            (
                ids["idea_version_id"],
                SOURCE_UPDATED_AT,
                ids["idea_id"],
            ),
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
              %s, %s, '{}'::jsonb, %s, %s
            )
            """,
            (
                ids["evidence_id"],
                owner_id,
                ids["idea_id"],
                ids["idea_version_id"],
                ids["conversation_id"],
                "ETH lower-drawdown evidence",
                "The lower-drawdown version preserved more capital.",
                SOURCE_UPDATED_AT,
                SOURCE_UPDATED_AT,
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
              %s, %s, %s, %s, %s, %s, 'rejected', %s, %s, %s
            )
            """,
            (
                ids["decision_id"],
                owner_id,
                ids["idea_id"],
                ids["idea_version_id"],
                ids["evidence_id"],
                ids["conversation_id"],
                "Rejected because the first version exceeded my drawdown limit.",
                SOURCE_UPDATED_AT,
                SOURCE_UPDATED_AT,
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
        name=f"memory-task-3-{uuid.uuid4()}",
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        owner_id = _seed_identity(connection)
        other_owner_id = _seed_identity(connection)
        sources = _seed_canonical_decision(connection, owner_id)
        unrelated_sources = _seed_canonical_decision(connection, owner_id)
        other_sources = _seed_canonical_decision(connection, other_owner_id)
    try:
        yield {
            "pool": pool,
            "owner": RegisteredMemoryOwner(owner_id=owner_id),
            "other_owner": RegisteredMemoryOwner(owner_id=other_owner_id),
            "sources": sources,
            "unrelated_sources": unrelated_sources,
            "other_sources": other_sources,
        }
    finally:
        pool.close()
        with psycopg.connect(DSN, autocommit=True) as connection:
            connection.execute(
                "delete from auth.users where id = any(%s::uuid[])",
                ([owner_id, other_owner_id],),
            )


def _saved_decision_candidate(
    owner: RegisteredMemoryOwner,
    sources: dict[str, str],
    *,
    candidate_id: str | None = None,
    opt_in_scope: frozenset[MemoryCategory] = SAVED_DECISION_SCOPE,
    created_at: datetime = NOW,
) -> MemoryCandidate:
    label = "Remember the lower-drawdown decision"
    value = "I rejected the first version because its drawdown was too high."
    future_benefit = "Argus can revisit and compare this saved decision later."
    primary = MemoryProvenance(
        source_kind=MemorySourceKind.DECISION_NOTE,
        source_id=sources["decision_id"],
        source_version=SOURCE_UPDATED_AT.isoformat().replace("+00:00", "Z"),
    )
    provenance_refs = (
        primary,
        MemoryProvenance(
            source_kind=MemorySourceKind.EVIDENCE_ARTIFACT,
            source_id=sources["evidence_id"],
            source_version=SOURCE_UPDATED_AT.isoformat().replace("+00:00", "Z"),
        ),
        MemoryProvenance(
            source_kind=MemorySourceKind.IDEA,
            source_id=sources["idea_id"],
            source_version="idea-v1",
        ),
        MemoryProvenance(
            source_kind=MemorySourceKind.IDEA_VERSION,
            source_id=sources["idea_version_id"],
            source_version="idea-version-v1",
        ),
        MemoryProvenance(
            source_kind=MemorySourceKind.CONVERSATION,
            source_id=sources["conversation_id"],
            source_version="conversation-v1",
        ),
        MemoryProvenance(
            source_kind=MemorySourceKind.MESSAGE,
            source_id=sources["message_id"],
            source_version="message-v1",
        ),
    )
    sensitivity = bind_sensitivity_assessment(
        SensitivityAssessment(status=SensitivityStatus.CLEAR),
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        label=label,
        value=value,
        future_benefit=future_benefit,
    )
    return MemoryCandidate(
        id=candidate_id or f"candidate-{uuid.uuid4()}",
        owner_id=owner.owner_id,
        category=MemoryCategory.EXPLICIT_DECISION_NOTE,
        source=SavedDecisionSource(
            label=label,
            value=value,
            provenance=primary,
        ),
        future_benefit=future_benefit,
        provenance_refs=provenance_refs,
        trigger=MemoryProposalTrigger.SAVED_DECISION,
        sensitivity=sensitivity,
        proposed_context=MemoryOperationContext.ORDINARY,
        opt_in_scope=opt_in_scope,
        created_at=created_at,
    )


def _add_candidate(
    store: PostgresCanonicalMemoryStore,
    owner: RegisteredMemoryOwner,
    candidate: MemoryCandidate,
    *,
    prompted_at: datetime = NOW,
    expected_prompt_at: datetime | None = None,
) -> None:
    assert store.add_candidate_with_prompt(
        owner,
        candidate,
        proactive_prompt_at=prompted_at,
        expected_history=ProposalHistorySnapshot(
            last_proactive_prompt_at=expected_prompt_at,
            last_declined_at=None,
        ),
    )


def _canonical_snapshot(
    owner_id: str,
    sources: dict[str, str],
) -> dict[str, Any]:
    statements = {
        "conversation": (
            "select to_jsonb(row) from (select * from public.conversations"
            " where id = %s and user_id = %s) as row",
            sources["conversation_id"],
        ),
        "message": (
            "select to_jsonb(row) from (select * from public.messages"
            " where id = %s and user_id = %s) as row",
            sources["message_id"],
        ),
        "idea": (
            "select to_jsonb(row) from (select * from public.ideas"
            " where id = %s and user_id = %s) as row",
            sources["idea_id"],
        ),
        "idea_version": (
            "select to_jsonb(row) from (select * from public.idea_versions"
            " where id = %s and user_id = %s) as row",
            sources["idea_version_id"],
        ),
        "evidence": (
            "select to_jsonb(row) from (select * from public.evidence_artifacts"
            " where id = %s and user_id = %s) as row",
            sources["evidence_id"],
        ),
        "decision": (
            "select to_jsonb(row) from (select * from public.decision_notes"
            " where id = %s and user_id = %s) as row",
            sources["decision_id"],
        ),
    }
    with psycopg.connect(DSN, autocommit=True) as connection:
        return {
            name: connection.execute(statement, (source_id, owner_id)).fetchone()[0]
            for name, (statement, source_id) in statements.items()
        }


def _owner_memory_counts(owner_id: str) -> tuple[int, ...]:
    tables = (
        "memory_settings",
        "memory_candidates",
        "memory_consent_actions",
        "memory_records",
        "memory_provenance",
        "memory_prompt_history",
        "memory_reconciliations",
    )
    with psycopg.connect(DSN, autocommit=True) as connection:
        return tuple(
            connection.execute(
                f"select count(*) from public.{table} where owner_id = %s",
                (owner_id,),
            ).fetchone()[0]
            for table in tables
        )


def _with_provenance(
    candidate: MemoryCandidate,
    provenance_refs: tuple[MemoryProvenance, ...],
) -> MemoryCandidate:
    return MemoryCandidate.model_validate(
        {
            field_name: (
                candidate.source.model_copy(
                    update={"provenance": provenance_refs[0]},
                )
                if field_name == "source"
                else provenance_refs
                if field_name == "provenance_refs"
                else getattr(candidate, field_name)
            )
            for field_name in MemoryCandidate.model_fields
        }
    )


class _ConfirmationServicePostgresStore(PostgresCanonicalMemoryStore):
    """Task 3 adapter seam before later reconciliation methods land."""

    def wait_for_reconciliation_turn(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        reconciliation_generation: int,
    ) -> bool:
        return False

    def finish_record_reconciliation(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        reconciliation_generation: int,
    ) -> bool:
        return True


def test_service_saved_decision_confirmation_derives_canonical_evidence(
    database: dict[str, Any],
) -> None:
    """Catches rejecting the service's real single-primary provenance shape."""

    store = _ConfirmationServicePostgresStore(database["pool"])
    owner = database["owner"]
    sources = database["sources"]
    primary = MemoryProvenance(
        source_kind=MemorySourceKind.DECISION_NOTE,
        source_id=sources["decision_id"],
        source_version=SOURCE_UPDATED_AT.isoformat().replace("+00:00", "Z"),
    )
    source = SavedDecisionSource(
        label="Remember the lower-drawdown decision",
        value="I rejected the first version because its drawdown was too high.",
        provenance=primary,
    )
    sensitivity = SensitivityAssessment(status=SensitivityStatus.CLEAR)
    generated_ids = iter(("candidate-service", "receipt-service", "record-service"))
    service = MemoryService(
        store=cast(CanonicalMemoryStore, store),
        config=MemoryServiceConfig(available=True),
        clock=lambda: NOW,
        id_factory=generated_ids.__next__,
        correlation_id_factory=lambda: "correlation-service",
    )
    subject = MemorySubject(
        owner_id=owner.owner_id,
        kind=MemoryAccountKind.REGISTERED,
    )
    before_sources = _canonical_snapshot(owner.owner_id, sources)

    proposal = service.propose_saved_decision(
        subject,
        source,
        sensitivity=sensitivity,
        context=MemoryOperationContext.ORDINARY,
    )

    assert proposal is not None
    assert proposal.candidate.id == "candidate-service"
    assert proposal.candidate.provenance_refs == (primary,)

    result = service.confirm(
        subject,
        proposal.candidate.id,
        sensitivity=sensitivity,
        context=MemoryOperationContext.ORDINARY,
    )

    assert result.created is True
    assert result.record is not None
    assert result.consent_receipt is not None
    canonical_evidence = MemoryProvenance(
        source_kind=MemorySourceKind.EVIDENCE_ARTIFACT,
        source_id=sources["evidence_id"],
        source_version=SOURCE_UPDATED_AT.isoformat().replace("+00:00", "Z"),
    )
    assert result.record.provenance == primary
    assert result.record.provenance_refs == (primary, canonical_evidence)
    assert result.consent_receipt.requested_scope == SAVED_DECISION_SCOPE
    assert result.consent_receipt.granted_scope == SAVED_DECISION_SCOPE
    assert result.consent_receipt.effective_scope == SAVED_DECISION_SCOPE
    assert store.get_candidate(owner, proposal.candidate.id) is None
    assert store.enabled_categories(owner) == SAVED_DECISION_SCOPE
    assert _owner_memory_counts(owner.owner_id) == (2, 0, 1, 1, 2, 1, 1)
    assert _canonical_snapshot(owner.owner_id, sources) == before_sources


def test_confirmation_atomically_persists_saved_decision_and_supporting_provenance(
    database: dict[str, Any],
) -> None:
    """Catches partial confirmation or mutation of canonical source artifacts."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    sources = database["sources"]
    candidate = _saved_decision_candidate(owner, sources)
    _add_candidate(store, owner, candidate)
    before_sources = _canonical_snapshot(owner.owner_id, sources)
    clock_calls: list[datetime] = []
    id_calls: list[str] = []
    ids = iter(("receipt-confirmed", "record-confirmed"))

    def clock() -> datetime:
        clock_calls.append(NOW)
        return NOW

    def id_factory() -> str:
        generated = next(ids)
        id_calls.append(generated)
        return generated

    mutation = store.confirm_candidate(
        owner,
        candidate.id,
        clock=clock,
        id_factory=id_factory,
    )

    assert clock_calls == [NOW]
    assert id_calls == ["receipt-confirmed", "record-confirmed"]
    assert mutation.reconciliation_generation == 1
    assert mutation.result.created is True
    assert mutation.result.consent_receipt is not None
    assert mutation.result.record is not None
    receipt = mutation.result.consent_receipt
    record = mutation.result.record
    assert receipt.id == "receipt-confirmed"
    assert receipt.action == "candidate_confirmation"
    assert receipt.candidate_id == candidate.id
    assert receipt.requested_scope == SAVED_DECISION_SCOPE
    assert receipt.granted_scope == SAVED_DECISION_SCOPE
    assert receipt.effective_scope == SAVED_DECISION_SCOPE
    assert receipt.recorded_at == NOW
    assert receipt.idempotency_key == candidate.id
    assert record.id == "record-confirmed"
    assert record.candidate_id == candidate.id
    assert record.category is MemoryCategory.EXPLICIT_DECISION_NOTE
    assert record.label == candidate.source.label
    assert record.value == candidate.source.value
    assert record.provenance == candidate.source.provenance
    assert record.provenance_refs == candidate.provenance_refs
    assert record.consent_receipt == receipt
    assert record.created_at == NOW
    assert record.updated_at == NOW
    assert record.revision == 1
    assert store.get_candidate(owner, candidate.id) is None
    assert store.enabled_categories(owner) == SAVED_DECISION_SCOPE
    assert _canonical_snapshot(owner.owner_id, sources) == before_sources

    with psycopg.connect(DSN, autocommit=True) as connection:
        assert connection.execute(
            """
            select action, candidate_id, requested_scope, granted_scope,
                   effective_scope, recorded_at, idempotency_key
              from public.memory_consent_actions
             where owner_id = %s and id = %s
            """,
            (owner.owner_id, receipt.id),
        ).fetchone() == (
            "candidate_confirmation",
            candidate.id,
            ["explicit_decision_note", "past_session_anchor"],
            ["explicit_decision_note", "past_session_anchor"],
            ["explicit_decision_note", "past_session_anchor"],
            NOW,
            candidate.id,
        )
        assert connection.execute(
            """
            select candidate_id, consent_action_id, category, label, value,
                   revision, created_at, updated_at
              from public.memory_records
             where owner_id = %s and id = %s
            """,
            (owner.owner_id, record.id),
        ).fetchone() == (
            candidate.id,
            receipt.id,
            MemoryCategory.EXPLICIT_DECISION_NOTE.value,
            candidate.source.label,
            candidate.source.value,
            1,
            NOW,
            NOW,
        )
        assert connection.execute(
            """
            select ordinal, source_kind, source_id, source_version
              from public.memory_provenance
             where owner_id = %s and record_id = %s
             order by ordinal
            """,
            (owner.owner_id, record.id),
        ).fetchall() == [
            (
                ordinal,
                provenance.source_kind.value,
                provenance.source_id,
                provenance.source_version,
            )
            for ordinal, provenance in enumerate(candidate.provenance_refs)
        ]
        assert connection.execute(
            """
            select generation, operation, status, completed_at
              from public.memory_reconciliations
             where owner_id = %s and record_id = %s
            """,
            (owner.owner_id, record.id),
        ).fetchall() == [(1, "create", "pending", None)]


def test_missing_and_replayed_confirmation_are_inert_before_clock_or_ids(
    database: dict[str, Any],
) -> None:
    """Catches replay paths that allocate identities or create another record."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    candidate = _saved_decision_candidate(owner, database["sources"])

    missing = store.confirm_candidate(
        owner,
        candidate.id,
        clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
        id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
    )
    assert missing.result.created is False
    assert missing.reconciliation_generation is None

    _add_candidate(store, owner, candidate)
    first = store.confirm_candidate(
        owner,
        candidate.id,
        clock=lambda: NOW,
        id_factory=iter(("receipt-first", "record-first")).__next__,
    )
    assert first.result.created is True
    before_replay = _owner_memory_counts(owner.owner_id)

    replay = store.confirm_candidate(
        owner,
        candidate.id,
        clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
        id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
    )
    assert replay.result.created is False
    assert replay.reconciliation_generation is None
    assert _owner_memory_counts(owner.owner_id) == before_replay


def test_confirmation_unions_category_into_two_category_requested_scope(
    database: dict[str, Any],
) -> None:
    """Catches confirmation that trusts an opt-in scope missing its category."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    candidate = _saved_decision_candidate(
        owner,
        database["sources"],
        opt_in_scope=frozenset({MemoryCategory.PAST_SESSION_ANCHOR}),
    )
    _add_candidate(store, owner, candidate)

    result = store.confirm_candidate(
        owner,
        candidate.id,
        clock=lambda: NOW,
        id_factory=iter(("receipt-union", "record-union")).__next__,
    ).result

    assert result.created is True
    assert result.consent_receipt is not None
    assert result.consent_receipt.requested_scope == SAVED_DECISION_SCOPE
    assert result.consent_receipt.granted_scope == SAVED_DECISION_SCOPE
    assert result.consent_receipt.effective_scope == SAVED_DECISION_SCOPE


def test_confirmation_grants_only_scope_not_already_enabled(
    database: dict[str, Any],
) -> None:
    """Catches confirmation receipts that overstate newly granted consent."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    store.enable_categories(
        owner,
        frozenset({MemoryCategory.EXPLICIT_DECISION_NOTE}),
        clock=lambda: NOW - timedelta(minutes=1),
        id_factory=lambda: "receipt-enable-explicit",
        idempotency_key="enable-explicit",
    )
    candidate = _saved_decision_candidate(owner, database["sources"])
    _add_candidate(store, owner, candidate)

    result = store.confirm_candidate(
        owner,
        candidate.id,
        clock=lambda: NOW,
        id_factory=iter(("receipt-grant-delta", "record-grant-delta")).__next__,
    ).result

    assert result.consent_receipt is not None
    assert result.consent_receipt.requested_scope == SAVED_DECISION_SCOPE
    assert result.consent_receipt.granted_scope == frozenset(
        {MemoryCategory.PAST_SESSION_ANCHOR}
    )
    assert result.consent_receipt.effective_scope == SAVED_DECISION_SCOPE


@pytest.mark.parametrize(
    "case",
    (
        "primary_not_decision",
        "stale_decision_revision",
        "stale_evidence_revision",
        "cross_owner_decision",
        "unlinked_owned_evidence",
        "cross_owner_evidence",
        "mismatched_owned_idea",
        "mismatched_owned_idea_version",
        "missing_message",
        "malformed_message",
    ),
)
def test_malformed_stale_cross_owner_or_unlinked_provenance_is_clean_noop(
    database: dict[str, Any],
    case: str,
) -> None:
    """Catches source drift or ownership defects that consume the candidate."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    sources = database["sources"]
    unrelated = database["unrelated_sources"]
    other = database["other_sources"]
    candidate = _saved_decision_candidate(owner, sources)
    refs = list(candidate.provenance_refs)
    if case == "primary_not_decision":
        refs[0] = MemoryProvenance(
            source_kind=MemorySourceKind.EVIDENCE_ARTIFACT,
            source_id=sources["evidence_id"],
            source_version="evidence-v1",
        )
    elif case == "stale_decision_revision":
        refs[0] = refs[0].model_copy(
            update={
                "source_version": (
                    SOURCE_UPDATED_AT - timedelta(microseconds=1)
                ).isoformat()
            }
        )
    elif case == "stale_evidence_revision":
        refs[1] = refs[1].model_copy(
            update={
                "source_version": (
                    SOURCE_UPDATED_AT - timedelta(microseconds=1)
                ).isoformat()
            }
        )
    elif case == "cross_owner_decision":
        refs[0] = refs[0].model_copy(
            update={
                "source_id": other["decision_id"],
                "source_version": SOURCE_UPDATED_AT.isoformat(),
            }
        )
    elif case == "unlinked_owned_evidence":
        refs[1] = refs[1].model_copy(update={"source_id": unrelated["evidence_id"]})
    elif case == "cross_owner_evidence":
        refs[1] = refs[1].model_copy(update={"source_id": other["evidence_id"]})
    elif case == "mismatched_owned_idea":
        refs[2] = refs[2].model_copy(update={"source_id": unrelated["idea_id"]})
    elif case == "mismatched_owned_idea_version":
        refs[3] = refs[3].model_copy(update={"source_id": unrelated["idea_version_id"]})
    elif case == "missing_message":
        refs[-1] = refs[-1].model_copy(update={"source_id": str(uuid.uuid4())})
    elif case == "malformed_message":
        refs[-1] = refs[-1].model_copy(update={"source_id": "not-a-uuid"})
    candidate = _with_provenance(candidate, tuple(refs))
    _add_candidate(store, owner, candidate)
    before = _owner_memory_counts(owner.owner_id)

    result = store.confirm_candidate(
        owner,
        candidate.id,
        clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
        id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
    )

    assert result.result.created is False
    assert result.reconciliation_generation is None
    assert store.get_candidate(owner, candidate.id) == candidate
    assert _owner_memory_counts(owner.owner_id) == before


def test_confirmation_revalidates_database_registered_truth_before_effects(
    database: dict[str, Any],
) -> None:
    """Catches confirmation that trusts only the early typed owner boundary."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    candidate = _saved_decision_candidate(owner, database["sources"])
    _add_candidate(store, owner, candidate)
    before = _owner_memory_counts(owner.owner_id)
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(
            "update auth.users set is_anonymous = true where id = %s",
            (owner.owner_id,),
        )

    with pytest.raises(PersonalizationMemoryUnavailable):
        store.confirm_candidate(
            owner,
            candidate.id,
            clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
            id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
        )

    assert _owner_memory_counts(owner.owner_id) == before


def test_confirmation_cannot_cross_owner_for_same_candidate_id(
    database: dict[str, Any],
) -> None:
    """Catches owner-scoped lookup that consumes another account's candidate."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    other_owner = database["other_owner"]
    candidate = _saved_decision_candidate(owner, database["sources"])
    _add_candidate(store, owner, candidate)
    owner_before = _owner_memory_counts(owner.owner_id)
    other_before = _owner_memory_counts(other_owner.owner_id)

    result = store.confirm_candidate(
        other_owner,
        candidate.id,
        clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
        id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
    )

    assert result.result.created is False
    assert store.get_candidate(owner, candidate.id) == candidate
    assert _owner_memory_counts(owner.owner_id) == owner_before
    assert _owner_memory_counts(other_owner.owner_id) == other_before


def test_confirmation_identity_collisions_roll_back_every_write(
    database: dict[str, Any],
) -> None:
    """Catches receipt or record collisions that leave partial confirmation."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    first = _saved_decision_candidate(
        owner,
        database["sources"],
        candidate_id="candidate-first",
    )
    _add_candidate(store, owner, first)
    first_result = store.confirm_candidate(
        owner,
        first.id,
        clock=lambda: NOW,
        id_factory=iter(("receipt-shared", "record-shared")).__next__,
    ).result
    assert first_result.created

    second = _saved_decision_candidate(
        owner,
        database["sources"],
        candidate_id="candidate-second",
        created_at=NOW + timedelta(minutes=1),
    )
    _add_candidate(
        store,
        owner,
        second,
        prompted_at=NOW + timedelta(minutes=1),
        expected_prompt_at=NOW,
    )
    before_receipt_collision = _owner_memory_counts(owner.owner_id)
    with pytest.raises(ValueError, match="confirmation identity already exists"):
        store.confirm_candidate(
            owner,
            second.id,
            clock=lambda: NOW + timedelta(minutes=1),
            id_factory=iter(("receipt-shared", "record-second")).__next__,
        )
    assert store.get_candidate(owner, second.id) == second
    assert _owner_memory_counts(owner.owner_id) == before_receipt_collision

    before_record_collision = _owner_memory_counts(owner.owner_id)
    with pytest.raises(ValueError, match="confirmation identity already exists"):
        store.confirm_candidate(
            owner,
            second.id,
            clock=lambda: NOW + timedelta(minutes=1),
            id_factory=iter(("receipt-second", "record-shared")).__next__,
        )
    assert store.get_candidate(owner, second.id) == second
    assert _owner_memory_counts(owner.owner_id) == before_record_collision


def test_confirmation_id_factory_failure_rolls_back_and_keeps_candidate(
    database: dict[str, Any],
) -> None:
    """Catches identity allocation failure that partially grants consent."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    candidate = _saved_decision_candidate(owner, database["sources"])
    _add_candidate(store, owner, candidate)
    before = _owner_memory_counts(owner.owner_id)
    calls = 0

    def id_factory() -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("record id unavailable")
        return "receipt-before-failure"

    with pytest.raises(RuntimeError, match="record id unavailable"):
        store.confirm_candidate(
            owner,
            candidate.id,
            clock=lambda: NOW,
            id_factory=id_factory,
        )

    assert calls == 2
    assert store.get_candidate(owner, candidate.id) == candidate
    assert _owner_memory_counts(owner.owner_id) == before


def test_clock_constraint_and_readback_failures_each_roll_back_confirmation(
    database: dict[str, Any],
) -> None:
    """Catches failures at each allocation/write/readback phase leaving state."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    candidate = _saved_decision_candidate(owner, database["sources"])
    _add_candidate(store, owner, candidate)
    before = _owner_memory_counts(owner.owner_id)

    with pytest.raises(RuntimeError, match="clock unavailable"):
        store.confirm_candidate(
            owner,
            candidate.id,
            clock=lambda: (_ for _ in ()).throw(RuntimeError("clock unavailable")),
            id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
        )
    assert store.get_candidate(owner, candidate.id) == candidate
    assert _owner_memory_counts(owner.owner_id) == before

    with pytest.raises(psycopg.errors.CheckViolation):
        store.confirm_candidate(
            owner,
            candidate.id,
            clock=lambda: NOW,
            id_factory=iter(("receipt-before-constraint", "r" * 129)).__next__,
        )
    assert store.get_candidate(owner, candidate.id) == candidate
    assert _owner_memory_counts(owner.owner_id) == before

    with pytest.raises(
        RuntimeError,
        match="confirmed memory readback did not round-trip",
    ):
        store.confirm_candidate(
            owner,
            candidate.id,
            clock=lambda: NOW.replace(tzinfo=None),
            id_factory=iter(("receipt-before-readback", "record-readback")).__next__,
        )
    assert store.get_candidate(owner, candidate.id) == candidate
    assert _owner_memory_counts(owner.owner_id) == before


def test_existing_confirmation_receipt_cannot_create_alternative_record(
    database: dict[str, Any],
) -> None:
    """Catches partial-state replay that mints a new record for one candidate."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    candidate = _saved_decision_candidate(owner, database["sources"])
    _add_candidate(store, owner, candidate)
    with psycopg.connect(DSN, autocommit=True) as connection:
        connection.execute(
            """
            insert into public.memory_consent_actions (
              id, owner_id, action, candidate_id, requested_scope,
              granted_scope, effective_scope, idempotency_key
            )
            values (
              'receipt-existing', %s, 'candidate_confirmation', %s,
              array['explicit_decision_note'],
              array['explicit_decision_note'],
              array['explicit_decision_note'],
              %s
            )
            """,
            (owner.owner_id, candidate.id, candidate.id),
        )
    before = _owner_memory_counts(owner.owner_id)

    result = store.confirm_candidate(
        owner,
        candidate.id,
        clock=lambda: (_ for _ in ()).throw(AssertionError("clock called")),
        id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
    )

    assert result.result.created is False
    assert store.get_candidate(owner, candidate.id) == candidate
    assert _owner_memory_counts(owner.owner_id) == before


def test_concurrent_confirmation_has_exactly_one_create_and_one_clean_noop(
    database: dict[str, Any],
) -> None:
    """Catches serialization leakage or duplicate records under confirmation race."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    candidate = _saved_decision_candidate(owner, database["sources"])
    _add_candidate(store, owner, candidate)

    def confirm(suffix: str) -> bool:
        mutation = store.confirm_candidate(
            owner,
            candidate.id,
            clock=lambda: NOW,
            id_factory=iter(
                (f"receipt-concurrent-{suffix}", f"record-concurrent-{suffix}")
            ).__next__,
        )
        return mutation.result.created

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = tuple(executor.submit(confirm, suffix) for suffix in ("a", "b"))
        outcomes = tuple(future.result(timeout=3) for future in futures)

    assert sorted(outcomes) == [False, True]
    with psycopg.connect(DSN, autocommit=True) as connection:
        assert (
            connection.execute(
                "select count(*) from public.memory_records where owner_id = %s",
                (owner.owner_id,),
            ).fetchone()[0]
            == 1
        )
        assert (
            connection.execute(
                """
            select count(*)
              from public.memory_consent_actions
             where owner_id = %s and action = 'candidate_confirmation'
            """,
                (owner.owner_id,),
            ).fetchone()[0]
            == 1
        )


def test_service_discards_expired_postgres_candidate_without_record_creation(
    database: dict[str, Any],
) -> None:
    """Catches a store-owned TTL or expired candidate becoming a record."""

    store = PostgresCanonicalMemoryStore(database["pool"])
    owner = database["owner"]
    created_at = NOW - timedelta(days=2)
    candidate = _saved_decision_candidate(
        owner,
        database["sources"],
        created_at=created_at,
    )
    _add_candidate(
        store,
        owner,
        candidate,
        prompted_at=created_at,
    )
    service = MemoryService(
        store=cast(CanonicalMemoryStore, store),
        config=MemoryServiceConfig(
            available=True,
            candidate_ttl=timedelta(days=1),
        ),
        clock=lambda: NOW,
        id_factory=lambda: (_ for _ in ()).throw(AssertionError("id called")),
    )
    subject = MemorySubject(
        owner_id=owner.owner_id,
        kind=MemoryAccountKind.REGISTERED,
    )

    result = service.confirm(
        subject,
        candidate.id,
        sensitivity=SensitivityAssessment(status=SensitivityStatus.CLEAR),
        context=MemoryOperationContext.ORDINARY,
    )

    assert result.created is False
    assert store.get_candidate(owner, candidate.id) is None
    with psycopg.connect(DSN, autocommit=True) as connection:
        assert (
            connection.execute(
                "select count(*) from public.memory_records where owner_id = %s",
                (owner.owner_id,),
            ).fetchone()[0]
            == 0
        )
