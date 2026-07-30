"""Private Postgres persistence for scoped personalization-memory state."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from psycopg import Cursor, errors
from psycopg.rows import tuple_row
from psycopg_pool import ConnectionPool

from argus.memory.contracts import (
    ConfirmationResult,
    MemoryCandidate,
    MemoryCategory,
    MemoryConsentActionReceipt,
    MemoryConsentSettings,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemoryRecord,
    MemorySourceKind,
    SavedDecisionSource,
    SensitivityAssessment,
)
from argus.memory.store import (
    CanonicalConfirmationMutation,
    CanonicalEnableMutation,
    ProposalHistorySnapshot,
)
from argus.memory.subject import (
    PersonalizationMemoryUnavailable,
    RegisteredMemoryOwner,
)

_ALL_MEMORY_CATEGORIES = tuple(sorted(MemoryCategory, key=lambda item: item.value))
_CANDIDATE_CAS_ATTEMPTS = 2
_READ_COMMITTED = "set transaction isolation level read committed"
_SERIALIZABLE = "set transaction isolation level serializable"


class PostgresCanonicalMemoryStore:
    """Direct-database adapter with canonical registered-owner revalidation."""

    def __init__(self, pool: ConnectionPool[Any]) -> None:
        self._pool = pool

    @contextmanager
    def _transaction(
        self,
        owner: RegisteredMemoryOwner,
    ) -> Iterator[tuple[Cursor[Any], UUID]]:
        owner_id = self._owner_uuid(owner)
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=tuple_row) as cursor:
                    cursor.execute(_SERIALIZABLE)
                    self._require_registered_owner(cursor, owner_id)
                    yield cursor, owner_id

    @contextmanager
    def _confirmation_transaction(
        self,
        owner: RegisteredMemoryOwner,
    ) -> Iterator[tuple[Cursor[Any], UUID]]:
        owner_id = self._owner_uuid(owner)
        with self._pool.connection() as connection:
            with connection.transaction():
                with connection.cursor(row_factory=tuple_row) as cursor:
                    cursor.execute(_READ_COMMITTED)
                    self._require_registered_owner(cursor, owner_id)
                    yield cursor, owner_id

    @staticmethod
    def _owner_uuid(owner: RegisteredMemoryOwner) -> UUID:
        try:
            return UUID(owner.owner_id)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("memory owner id must be a valid UUID") from exc

    @staticmethod
    def _require_registered_owner(cursor: Cursor[Any], owner_id: UUID) -> None:
        cursor.execute(
            "select argus_private.is_registered_memory_owner(%s)",
            (owner_id,),
        )
        row = cursor.fetchone()
        if row is None or row[0] is not True:
            raise PersonalizationMemoryUnavailable(
                "Personalization memory requires a registered account."
            )

    @staticmethod
    def _lock_category(
        cursor: Cursor[Any],
        owner_id: UUID,
        category: MemoryCategory,
    ) -> None:
        cursor.execute(
            """
            select pg_advisory_xact_lock(
              pg_catalog.hashtextextended(%s, 0)
            )
            """,
            (f"argus:memory:{owner_id}:{category.value}",),
        )

    @classmethod
    def _lock_all_categories(
        cls,
        cursor: Cursor[Any],
        owner_id: UUID,
    ) -> None:
        for category in _ALL_MEMORY_CATEGORIES:
            cls._lock_category(cursor, owner_id, category)

    @staticmethod
    def _read_settings(
        cursor: Cursor[Any],
        owner_id: UUID,
    ) -> MemoryConsentSettings:
        cursor.execute(
            """
            select category
              from public.memory_settings
             where owner_id = %s
             order by category
            """,
            (owner_id,),
        )
        categories = frozenset(MemoryCategory(row[0]) for row in cursor.fetchall())
        return MemoryConsentSettings(
            enabled=bool(categories),
            enabled_categories=categories,
        )

    def enabled_categories(
        self,
        owner: RegisteredMemoryOwner,
    ) -> frozenset[MemoryCategory]:
        return self.get_settings(owner).enabled_categories

    def get_settings(self, owner: RegisteredMemoryOwner) -> MemoryConsentSettings:
        with self._transaction(owner) as (cursor, owner_id):
            return self._read_settings(cursor, owner_id)

    def set_settings(
        self,
        owner: RegisteredMemoryOwner,
        settings: MemoryConsentSettings,
    ) -> MemoryConsentSettings:
        with self._transaction(owner) as (cursor, owner_id):
            self._lock_all_categories(cursor, owner_id)
            current = self._read_settings(cursor, owner_id)
            if not settings.enabled_categories <= current.enabled_categories:
                raise ValueError(
                    "settings replacement cannot enable new memory categories"
                )
            cursor.execute(
                "delete from public.memory_settings where owner_id = %s",
                (owner_id,),
            )
            for category in sorted(
                settings.enabled_categories,
                key=lambda item: item.value,
            ):
                cursor.execute(
                    """
                    insert into public.memory_settings (owner_id, category)
                    values (%s, %s)
                    """,
                    (owner_id, category.value),
                )
            return self._read_settings(cursor, owner_id)

    def enable_categories(
        self,
        owner: RegisteredMemoryOwner,
        categories: frozenset[MemoryCategory],
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
        idempotency_key: str | None,
    ) -> CanonicalEnableMutation:
        try:
            with self._transaction(owner) as (cursor, owner_id):
                self._lock_all_categories(cursor, owner_id)
                if not categories:
                    raise ValueError("enable requires at least one category")
                current = self._read_settings(cursor, owner_id)
                ordered_categories = sorted(categories, key=lambda item: item.value)
                if idempotency_key is not None:
                    cursor.execute(
                        """
                        select requested_scope
                          from public.memory_consent_actions
                         where owner_id = %s
                           and action = 'direct_enable'
                           and idempotency_key = %s
                        """,
                        (owner_id, idempotency_key),
                    )
                    existing = cursor.fetchone()
                    if existing is not None:
                        requested_scope = frozenset(
                            MemoryCategory(category) for category in existing[0]
                        )
                        if requested_scope != categories:
                            raise ValueError(
                                "idempotency key already belongs to another "
                                "consent action"
                            )
                        return CanonicalEnableMutation(settings=current)
                if categories <= current.enabled_categories:
                    return CanonicalEnableMutation(settings=current)

                receipt_id = id_factory()
                cursor.execute(
                    """
                    select 1
                      from public.memory_consent_actions
                     where owner_id = %s and id = %s
                    """,
                    (owner_id, receipt_id),
                )
                if cursor.fetchone() is not None:
                    raise ValueError(f"consent receipt id already exists: {receipt_id}")

                granted_scope = categories - current.enabled_categories
                effective_scope = current.enabled_categories | categories
                receipt = MemoryConsentActionReceipt(
                    id=receipt_id,
                    action="direct_enable",
                    owner_id=str(owner_id),
                    requested_scope=categories,
                    granted_scope=granted_scope,
                    effective_scope=effective_scope,
                    recorded_at=clock(),
                    idempotency_key=idempotency_key or receipt_id,
                )
                cursor.execute(
                    """
                    insert into public.memory_consent_actions (
                      id,
                      owner_id,
                      schema_version,
                      policy_version,
                      action,
                      candidate_id,
                      requested_scope,
                      granted_scope,
                      effective_scope,
                      recorded_at,
                      idempotency_key
                    )
                    values (
                      %s, %s, %s, %s, %s, null, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        receipt.id,
                        owner_id,
                        receipt.schema_version,
                        receipt.policy_version,
                        receipt.action,
                        [category.value for category in ordered_categories],
                        [
                            category.value
                            for category in sorted(
                                receipt.granted_scope,
                                key=lambda item: item.value,
                            )
                        ],
                        [
                            category.value
                            for category in sorted(
                                receipt.effective_scope,
                                key=lambda item: item.value,
                            )
                        ],
                        receipt.recorded_at,
                        receipt.idempotency_key,
                    ),
                )
                for category in sorted(
                    receipt.granted_scope,
                    key=lambda item: item.value,
                ):
                    cursor.execute(
                        """
                        insert into public.memory_settings (owner_id, category)
                        values (%s, %s)
                        on conflict (owner_id, category) do nothing
                        """,
                        (owner_id, category.value),
                    )
                return CanonicalEnableMutation(
                    settings=self._read_settings(cursor, owner_id),
                    consent_receipt=receipt,
                )
        except errors.UniqueViolation as exc:
            raise ValueError("consent action already exists") from exc

    def add_candidate_with_prompt(
        self,
        owner: RegisteredMemoryOwner,
        candidate: MemoryCandidate,
        *,
        proactive_prompt_at: datetime | None,
        expected_history: ProposalHistorySnapshot | None,
    ) -> bool:
        for attempt in range(_CANDIDATE_CAS_ATTEMPTS):
            try:
                return self._add_candidate_with_prompt_once(
                    owner,
                    candidate,
                    proactive_prompt_at=proactive_prompt_at,
                    expected_history=expected_history,
                )
            except errors.SerializationFailure:
                if expected_history is None or attempt == _CANDIDATE_CAS_ATTEMPTS - 1:
                    raise
            except errors.UniqueViolation as exc:
                raise ValueError(f"candidate already exists: {candidate.id}") from exc
        raise AssertionError("candidate CAS retry loop exhausted unexpectedly")

    def _add_candidate_with_prompt_once(
        self,
        owner: RegisteredMemoryOwner,
        candidate: MemoryCandidate,
        *,
        proactive_prompt_at: datetime | None,
        expected_history: ProposalHistorySnapshot | None,
    ) -> bool:
        with self._transaction(owner) as (cursor, owner_id):
            if candidate.owner_id != owner.owner_id:
                raise ValueError("candidate owner must match registered owner")
            is_proactive = candidate.trigger is not MemoryProposalTrigger.EXPLICIT_REQUEST
            if is_proactive != (proactive_prompt_at is not None):
                raise ValueError(
                    "proactive candidates require one atomic prompt-history timestamp"
                )
            if is_proactive != (expected_history is not None):
                raise ValueError(
                    "proactive candidates require the policy history snapshot"
                )
            self._lock_category(cursor, owner_id, candidate.category)
            cursor.execute(
                """
                select 1
                  from public.memory_candidates
                 where owner_id = %s and id = %s
                """,
                (owner_id, candidate.id),
            )
            if cursor.fetchone() is not None:
                raise ValueError(f"candidate already exists: {candidate.id}")
            if expected_history is not None:
                current_history = self._read_history(
                    cursor,
                    owner_id,
                    candidate.category,
                )
                if current_history != expected_history:
                    return False

            self._insert_candidate(cursor, owner_id, candidate)
            if proactive_prompt_at is not None:
                self._upsert_history(
                    cursor,
                    owner_id,
                    candidate.category,
                    proactive_prompt_at=proactive_prompt_at,
                )
            return True

    @staticmethod
    def _insert_candidate(
        cursor: Cursor[Any],
        owner_id: UUID,
        candidate: MemoryCandidate,
    ) -> None:
        cursor.execute(
            """
            insert into public.memory_candidates (
              id,
              owner_id,
              category,
              source_label,
              source_value,
              future_benefit,
              trigger,
              proposed_context,
              opt_in_scope,
              sensitivity_status,
              sensitivity_flags,
              sensitivity_policy_version,
              sensitivity_content_digest,
              created_at
            )
            values (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                candidate.id,
                owner_id,
                candidate.category.value,
                candidate.source.label,
                candidate.source.value,
                candidate.future_benefit,
                candidate.trigger.value,
                candidate.proposed_context.value,
                [
                    category.value
                    for category in sorted(
                        candidate.opt_in_scope,
                        key=lambda item: item.value,
                    )
                ],
                candidate.sensitivity.status.value,
                [
                    flag.value
                    for flag in sorted(
                        candidate.sensitivity.flags,
                        key=lambda item: item.value,
                    )
                ],
                candidate.sensitivity.policy_version,
                candidate.sensitivity.content_digest,
                candidate.created_at,
            ),
        )
        for ordinal, provenance in enumerate(candidate.provenance_refs):
            cursor.execute(
                """
                insert into public.memory_provenance (
                  owner_id,
                  candidate_id,
                  record_id,
                  ordinal,
                  source_kind,
                  source_id,
                  source_version
                )
                values (%s, %s, null, %s, %s, %s, %s)
                """,
                (
                    owner_id,
                    candidate.id,
                    ordinal,
                    provenance.source_kind.value,
                    provenance.source_id,
                    provenance.source_version,
                ),
            )

    def get_candidate(
        self,
        owner: RegisteredMemoryOwner,
        candidate_id: str,
    ) -> MemoryCandidate | None:
        with self._transaction(owner) as (cursor, owner_id):
            return self._read_candidate(cursor, owner_id, candidate_id)

    def list_candidates(
        self,
        owner: RegisteredMemoryOwner,
    ) -> tuple[MemoryCandidate, ...]:
        with self._transaction(owner) as (cursor, owner_id):
            cursor.execute(
                """
                select id
                  from public.memory_candidates
                 where owner_id = %s
                 order by created_at, id
                """,
                (owner_id,),
            )
            candidate_ids = tuple(row[0] for row in cursor.fetchall())
            candidates = tuple(
                self._read_candidate(cursor, owner_id, candidate_id)
                for candidate_id in candidate_ids
            )
            return tuple(candidate for candidate in candidates if candidate is not None)

    @classmethod
    def _read_candidate(
        cls,
        cursor: Cursor[Any],
        owner_id: UUID,
        candidate_id: str,
    ) -> MemoryCandidate | None:
        cursor.execute(
            """
            select
              id,
              owner_id::text,
              category,
              source_label,
              source_value,
              future_benefit,
              trigger,
              proposed_context,
              opt_in_scope,
              sensitivity_status,
              sensitivity_flags,
              sensitivity_policy_version,
              sensitivity_content_digest,
              created_at
              from public.memory_candidates
             where owner_id = %s and id = %s
            """,
            (owner_id, candidate_id),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        cursor.execute(
            """
            select source_kind, source_id, source_version
              from public.memory_provenance
             where owner_id = %s and candidate_id = %s
             order by ordinal
            """,
            (owner_id, candidate_id),
        )
        provenance_refs = tuple(
            MemoryProvenance(
                source_kind=MemorySourceKind(provenance_row[0]),
                source_id=provenance_row[1],
                source_version=provenance_row[2],
            )
            for provenance_row in cursor.fetchall()
        )
        if not provenance_refs:
            raise RuntimeError("persisted memory candidate is missing provenance")
        sensitivity = SensitivityAssessment.model_validate(
            {
                "status": row[9],
                "flags": frozenset(row[10]),
                "policy_version": row[11],
                "content_digest": row[12],
            }
        )
        return MemoryCandidate(
            id=row[0],
            owner_id=row[1],
            category=MemoryCategory(row[2]),
            source=SavedDecisionSource(
                label=row[3],
                value=row[4],
                provenance=provenance_refs[0],
            ),
            future_benefit=row[5],
            provenance_refs=provenance_refs,
            trigger=MemoryProposalTrigger(row[6]),
            sensitivity=sensitivity,
            proposed_context=MemoryOperationContext(row[7]),
            opt_in_scope=frozenset(MemoryCategory(item) for item in row[8]),
            created_at=row[13],
        )

    def discard_candidate(
        self,
        owner: RegisteredMemoryOwner,
        candidate_id: str,
    ) -> bool:
        with self._transaction(owner) as (cursor, owner_id):
            category = self._candidate_category(cursor, owner_id, candidate_id)
            if category is None:
                return False
            self._lock_category(cursor, owner_id, category)
            cursor.execute(
                """
                delete from public.memory_candidates
                 where owner_id = %s and id = %s
                returning id
                """,
                (owner_id, candidate_id),
            )
            return cursor.fetchone() is not None

    def confirm_candidate(
        self,
        owner: RegisteredMemoryOwner,
        candidate_id: str,
        *,
        clock: Callable[[], datetime],
        id_factory: Callable[[], str],
    ) -> CanonicalConfirmationMutation:
        try:
            with self._confirmation_transaction(owner) as (cursor, owner_id):
                self._lock_all_categories(cursor, owner_id)
                cursor.execute(
                    """
                    select 1
                      from public.memory_candidates
                     where owner_id = %s and id = %s
                     for update
                    """,
                    (owner_id, candidate_id),
                )
                if cursor.fetchone() is None:
                    return self._unchanged_confirmation()

                candidate = self._read_candidate(cursor, owner_id, candidate_id)
                if candidate is None:
                    return self._unchanged_confirmation()
                confirmed_provenance = self._confirmed_provenance(
                    cursor,
                    owner_id,
                    candidate,
                )
                if confirmed_provenance is None:
                    return self._unchanged_confirmation()

                cursor.execute(
                    """
                    select 1
                      from public.memory_consent_actions
                     where owner_id = %s
                       and candidate_id = %s
                       and action = 'candidate_confirmation'
                    """,
                    (owner_id, candidate.id),
                )
                if cursor.fetchone() is not None:
                    return self._unchanged_confirmation()

                current = self._read_settings(cursor, owner_id)
                requested_scope = candidate.opt_in_scope | frozenset({candidate.category})
                granted_scope = requested_scope - current.enabled_categories
                effective_scope = current.enabled_categories | requested_scope

                confirmed_at = clock()
                receipt = MemoryConsentActionReceipt(
                    id=id_factory(),
                    action="candidate_confirmation",
                    owner_id=str(owner_id),
                    candidate_id=candidate.id,
                    requested_scope=requested_scope,
                    granted_scope=granted_scope,
                    effective_scope=effective_scope,
                    recorded_at=confirmed_at,
                    idempotency_key=candidate.id,
                )
                record = MemoryRecord(
                    id=id_factory(),
                    owner_id=str(owner_id),
                    candidate_id=candidate.id,
                    category=candidate.category,
                    label=candidate.source.label,
                    value=candidate.source.value,
                    provenance=confirmed_provenance[0],
                    provenance_refs=confirmed_provenance,
                    consent_receipt=receipt,
                    created_at=confirmed_at,
                    updated_at=confirmed_at,
                )

                self._insert_confirmation_receipt(cursor, owner_id, receipt)
                for category in sorted(
                    receipt.granted_scope,
                    key=lambda item: item.value,
                ):
                    cursor.execute(
                        """
                        insert into public.memory_settings (owner_id, category)
                        values (%s, %s)
                        on conflict (owner_id, category) do nothing
                        """,
                        (owner_id, category.value),
                    )
                self._insert_record(cursor, owner_id, record, receipt.id)
                self._copy_record_provenance(cursor, owner_id, record)
                cursor.execute(
                    """
                    insert into public.memory_reconciliations (
                      owner_id,
                      record_id,
                      generation,
                      operation,
                      status,
                      created_at
                    )
                    values (%s, %s, 1, 'create', 'pending', %s)
                    """,
                    (owner_id, record.id, confirmed_at),
                )
                cursor.execute(
                    """
                    delete from public.memory_candidates
                     where owner_id = %s and id = %s
                    returning id
                    """,
                    (owner_id, candidate.id),
                )
                consumed = cursor.fetchone()
                if consumed is None or consumed[0] != candidate.id:
                    raise RuntimeError("confirmed memory candidate was not consumed")

                persisted_receipt = self._read_consent_receipt(
                    cursor,
                    owner_id,
                    receipt.id,
                )
                persisted_record = self._read_record(
                    cursor,
                    owner_id,
                    record.id,
                    consent_receipt=persisted_receipt,
                )
                if persisted_receipt != receipt or persisted_record != record:
                    raise RuntimeError("confirmed memory readback did not round-trip")
                return CanonicalConfirmationMutation(
                    result=ConfirmationResult(
                        created=True,
                        record=persisted_record,
                        consent_receipt=persisted_receipt,
                    ),
                    reconciliation_generation=1,
                )
        except errors.UniqueViolation as exc:
            raise ValueError("confirmation identity already exists") from exc

    @staticmethod
    def _unchanged_confirmation() -> CanonicalConfirmationMutation:
        return CanonicalConfirmationMutation(
            result=ConfirmationResult(created=False),
        )

    @staticmethod
    def _insert_confirmation_receipt(
        cursor: Cursor[Any],
        owner_id: UUID,
        receipt: MemoryConsentActionReceipt,
    ) -> None:
        cursor.execute(
            """
            insert into public.memory_consent_actions (
              id,
              owner_id,
              schema_version,
              policy_version,
              action,
              candidate_id,
              requested_scope,
              granted_scope,
              effective_scope,
              recorded_at,
              idempotency_key
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                receipt.id,
                owner_id,
                receipt.schema_version,
                receipt.policy_version,
                receipt.action,
                receipt.candidate_id,
                [
                    category.value
                    for category in sorted(
                        receipt.requested_scope,
                        key=lambda item: item.value,
                    )
                ],
                [
                    category.value
                    for category in sorted(
                        receipt.granted_scope,
                        key=lambda item: item.value,
                    )
                ],
                [
                    category.value
                    for category in sorted(
                        receipt.effective_scope,
                        key=lambda item: item.value,
                    )
                ],
                receipt.recorded_at,
                receipt.idempotency_key,
            ),
        )

    @staticmethod
    def _insert_record(
        cursor: Cursor[Any],
        owner_id: UUID,
        record: MemoryRecord,
        consent_action_id: str,
    ) -> None:
        cursor.execute(
            """
            insert into public.memory_records (
              id,
              owner_id,
              candidate_id,
              consent_action_id,
              category,
              label,
              value,
              revision,
              created_at,
              updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.id,
                owner_id,
                record.candidate_id,
                consent_action_id,
                record.category.value,
                record.label,
                record.value,
                record.revision,
                record.created_at,
                record.updated_at,
            ),
        )

    @staticmethod
    def _copy_record_provenance(
        cursor: Cursor[Any],
        owner_id: UUID,
        record: MemoryRecord,
    ) -> None:
        for ordinal, provenance in enumerate(record.provenance_refs):
            cursor.execute(
                """
                insert into public.memory_provenance (
                  owner_id,
                  candidate_id,
                  record_id,
                  ordinal,
                  source_kind,
                  source_id,
                  source_version
                )
                values (%s, null, %s, %s, %s, %s, %s)
                """,
                (
                    owner_id,
                    record.id,
                    ordinal,
                    provenance.source_kind.value,
                    provenance.source_id,
                    provenance.source_version,
                ),
            )

    @staticmethod
    def _read_consent_receipt(
        cursor: Cursor[Any],
        owner_id: UUID,
        receipt_id: str,
    ) -> MemoryConsentActionReceipt:
        cursor.execute(
            """
            select
              id,
              schema_version,
              policy_version,
              action,
              owner_id::text,
              candidate_id,
              requested_scope,
              granted_scope,
              effective_scope,
              recorded_at,
              idempotency_key
              from public.memory_consent_actions
             where owner_id = %s and id = %s
            """,
            (owner_id, receipt_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("confirmed consent receipt readback is missing")
        return MemoryConsentActionReceipt(
            id=row[0],
            schema_version=row[1],
            policy_version=row[2],
            action=row[3],
            owner_id=row[4],
            candidate_id=row[5],
            requested_scope=frozenset(MemoryCategory(item) for item in row[6]),
            granted_scope=frozenset(MemoryCategory(item) for item in row[7]),
            effective_scope=frozenset(MemoryCategory(item) for item in row[8]),
            recorded_at=row[9],
            idempotency_key=row[10],
        )

    @staticmethod
    def _read_record(
        cursor: Cursor[Any],
        owner_id: UUID,
        record_id: str,
        *,
        consent_receipt: MemoryConsentActionReceipt,
    ) -> MemoryRecord:
        cursor.execute(
            """
            select
              id,
              owner_id::text,
              candidate_id,
              category,
              label,
              value,
              revision,
              created_at,
              updated_at
              from public.memory_records
             where owner_id = %s and id = %s
            """,
            (owner_id, record_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("confirmed memory record readback is missing")
        cursor.execute(
            """
            select source_kind, source_id, source_version
              from public.memory_provenance
             where owner_id = %s and record_id = %s
             order by ordinal
            """,
            (owner_id, record_id),
        )
        provenance_refs = tuple(
            MemoryProvenance(
                source_kind=MemorySourceKind(item[0]),
                source_id=item[1],
                source_version=item[2],
            )
            for item in cursor.fetchall()
        )
        if not provenance_refs:
            raise RuntimeError("confirmed memory record provenance readback is missing")
        return MemoryRecord(
            id=row[0],
            owner_id=row[1],
            candidate_id=row[2],
            category=MemoryCategory(row[3]),
            label=row[4],
            value=row[5],
            provenance=provenance_refs[0],
            provenance_refs=provenance_refs,
            consent_receipt=consent_receipt,
            revision=row[6],
            created_at=row[7],
            updated_at=row[8],
        )

    @classmethod
    def _confirmed_provenance(
        cls,
        cursor: Cursor[Any],
        owner_id: UUID,
        candidate: MemoryCandidate,
    ) -> tuple[MemoryProvenance, ...] | None:
        linked_decision: tuple[UUID, UUID, UUID, UUID | None, datetime] | None = None
        canonical_evidence: MemoryProvenance | None = None
        if candidate.trigger is MemoryProposalTrigger.SAVED_DECISION:
            primary = candidate.source.provenance
            if primary.source_kind is not MemorySourceKind.DECISION_NOTE:
                return None
            decision_id = cls._source_uuid(primary)
            if decision_id is None:
                return None
            cursor.execute(
                """
                select evidence_artifact_id
                  from public.decision_notes
                 where id = %s and user_id = %s
                """,
                (decision_id, owner_id),
            )
            decision_hint = cursor.fetchone()
            if decision_hint is None:
                return None
            evidence_id = decision_hint[0]
            cursor.execute(
                """
                select idea_id, idea_version_id, updated_at
                  from public.evidence_artifacts
                 where id = %s and user_id = %s
                 for update
                """,
                (evidence_id, owner_id),
            )
            evidence_row = cursor.fetchone()
            if evidence_row is None:
                return None
            canonical_evidence = MemoryProvenance(
                source_kind=MemorySourceKind.EVIDENCE_ARTIFACT,
                source_id=str(evidence_id),
                source_version=cls._stable_source_revision(evidence_row[2]),
            )
            cursor.execute(
                """
                select
                  idea_id,
                  idea_version_id,
                  evidence_artifact_id,
                  source_conversation_id,
                  updated_at
                  from public.decision_notes
                 where id = %s and user_id = %s
                 for update
                """,
                (decision_id, owner_id),
            )
            decision_row = cursor.fetchone()
            if decision_row is None:
                return None
            linked_decision = (
                decision_row[0],
                decision_row[1],
                decision_row[2],
                decision_row[3],
                decision_row[4],
            )
            if linked_decision[2] != evidence_id:
                return None
            if (linked_decision[0], linked_decision[1]) != (
                evidence_row[0],
                evidence_row[1],
            ):
                return None
            source_revision = cls._parse_source_revision(primary.source_version)
            if source_revision is None or source_revision != linked_decision[4]:
                return None
            cursor.execute(
                """
                select 1
                  from public.ideas
                 where id = %s and user_id = %s
                """,
                (linked_decision[0], owner_id),
            )
            if cursor.fetchone() is None:
                return None
            cursor.execute(
                """
                select 1
                  from public.idea_versions
                 where id = %s
                   and user_id = %s
                   and idea_id = %s
                """,
                (linked_decision[1], owner_id, linked_decision[0]),
            )
            if cursor.fetchone() is None:
                return None

        confirmed_refs: list[MemoryProvenance] = []
        for provenance in candidate.provenance_refs:
            source_id = cls._source_uuid(provenance)
            if source_id is None:
                return None
            if linked_decision is not None:
                if provenance.source_kind is MemorySourceKind.EVIDENCE_ARTIFACT:
                    if (
                        canonical_evidence is None
                        or source_id != linked_decision[2]
                        or provenance != canonical_evidence
                    ):
                        return None
                    continue
                elif (
                    provenance.source_kind is MemorySourceKind.IDEA
                    and source_id != linked_decision[0]
                ):
                    return None
                elif (
                    provenance.source_kind is MemorySourceKind.IDEA_VERSION
                    and source_id != linked_decision[1]
                ):
                    return None
            if not cls._source_is_owned(
                cursor,
                owner_id,
                provenance.source_kind,
                source_id,
            ):
                return None
            confirmed_refs.append(provenance)
        if canonical_evidence is not None:
            confirmed_refs.insert(1, canonical_evidence)
        return tuple(confirmed_refs)

    @staticmethod
    def _source_uuid(provenance: MemoryProvenance) -> UUID | None:
        try:
            return UUID(provenance.source_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_source_revision(value: str) -> datetime | None:
        if "T" not in value:
            return None
        normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _stable_source_revision(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _source_is_owned(
        cursor: Cursor[Any],
        owner_id: UUID,
        source_kind: MemorySourceKind,
        source_id: UUID,
    ) -> bool:
        statements = {
            MemorySourceKind.EVIDENCE_ARTIFACT: """
                select 1
                  from public.evidence_artifacts
                 where id = %s and user_id = %s
            """,
            MemorySourceKind.DECISION_NOTE: """
                select 1
                  from public.decision_notes
                 where id = %s and user_id = %s
            """,
            MemorySourceKind.IDEA: """
                select 1
                  from public.ideas
                 where id = %s and user_id = %s
            """,
            MemorySourceKind.IDEA_VERSION: """
                select 1
                  from public.idea_versions
                 where id = %s and user_id = %s
            """,
            MemorySourceKind.CONVERSATION: """
                select 1
                  from public.conversations
                 where id = %s and user_id = %s
            """,
            MemorySourceKind.MESSAGE: """
                select 1
                  from public.messages as message
                  join public.conversations as conversation
                    on conversation.id = message.conversation_id
                 where message.id = %s
                   and message.user_id = %s
                   and conversation.user_id = %s
            """,
        }
        statement = statements[source_kind]
        parameters: tuple[object, ...]
        if source_kind is MemorySourceKind.MESSAGE:
            parameters = (source_id, owner_id, owner_id)
        else:
            parameters = (source_id, owner_id)
        cursor.execute(statement, parameters)
        return cursor.fetchone() is not None

    def decline_candidate_with_history(
        self,
        owner: RegisteredMemoryOwner,
        candidate_id: str,
        *,
        declined_at: datetime | None,
    ) -> bool:
        with self._transaction(owner) as (cursor, owner_id):
            category = self._candidate_category(cursor, owner_id, candidate_id)
            if category is None:
                return False
            self._lock_category(cursor, owner_id, category)
            cursor.execute(
                """
                select trigger
                  from public.memory_candidates
                 where owner_id = %s and id = %s
                 for update
                """,
                (owner_id, candidate_id),
            )
            row = cursor.fetchone()
            if row is None:
                return False
            is_proactive = row[0] != MemoryProposalTrigger.EXPLICIT_REQUEST.value
            if is_proactive and declined_at is None:
                raise ValueError(
                    "proactive declines require one atomic history timestamp"
                )
            if not is_proactive and declined_at is not None:
                raise ValueError(
                    "explicit-request declines cannot write proactive history"
                )
            cursor.execute(
                """
                delete from public.memory_candidates
                 where owner_id = %s and id = %s
                """,
                (owner_id, candidate_id),
            )
            if declined_at is not None:
                self._upsert_history(
                    cursor,
                    owner_id,
                    category,
                    declined_at=declined_at,
                )
            return True

    @staticmethod
    def _candidate_category(
        cursor: Cursor[Any],
        owner_id: UUID,
        candidate_id: str,
    ) -> MemoryCategory | None:
        cursor.execute(
            """
            select category
              from public.memory_candidates
             where owner_id = %s and id = %s
            """,
            (owner_id, candidate_id),
        )
        row = cursor.fetchone()
        return None if row is None else MemoryCategory(row[0])

    def last_proactive_prompt_at(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
    ) -> datetime | None:
        with self._transaction(owner) as (cursor, owner_id):
            return self._read_history(
                cursor,
                owner_id,
                category,
            ).last_proactive_prompt_at

    def mark_proactive_prompt(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
        at: datetime,
    ) -> None:
        with self._transaction(owner) as (cursor, owner_id):
            self._lock_category(cursor, owner_id, category)
            self._upsert_history(
                cursor,
                owner_id,
                category,
                proactive_prompt_at=at,
            )

    def last_declined_at(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
    ) -> datetime | None:
        with self._transaction(owner) as (cursor, owner_id):
            return self._read_history(
                cursor,
                owner_id,
                category,
            ).last_declined_at

    def mark_declined(
        self,
        owner: RegisteredMemoryOwner,
        category: MemoryCategory,
        at: datetime,
    ) -> None:
        with self._transaction(owner) as (cursor, owner_id):
            self._lock_category(cursor, owner_id, category)
            self._upsert_history(
                cursor,
                owner_id,
                category,
                declined_at=at,
            )

    @staticmethod
    def _read_history(
        cursor: Cursor[Any],
        owner_id: UUID,
        category: MemoryCategory,
    ) -> ProposalHistorySnapshot:
        cursor.execute(
            """
            select last_proactive_prompt_at, last_declined_at
              from public.memory_prompt_history
             where owner_id = %s and category = %s
            """,
            (owner_id, category.value),
        )
        row = cursor.fetchone()
        return ProposalHistorySnapshot(
            last_proactive_prompt_at=None if row is None else row[0],
            last_declined_at=None if row is None else row[1],
        )

    @staticmethod
    def _upsert_history(
        cursor: Cursor[Any],
        owner_id: UUID,
        category: MemoryCategory,
        *,
        proactive_prompt_at: datetime | None = None,
        declined_at: datetime | None = None,
    ) -> None:
        event_at = proactive_prompt_at or declined_at
        if event_at is None:
            raise ValueError("proposal history requires an event timestamp")
        current = PostgresCanonicalMemoryStore._read_history(
            cursor,
            owner_id,
            category,
        )
        next_prompt_at = proactive_prompt_at or current.last_proactive_prompt_at
        next_declined_at = declined_at or current.last_declined_at
        update_candidates = tuple(
            value
            for value in (next_prompt_at, next_declined_at, event_at)
            if value is not None
        )
        updated_at = max(update_candidates)
        cursor.execute(
            """
            delete from public.memory_prompt_history
             where owner_id = %s and category = %s
            """,
            (owner_id, category.value),
        )
        cursor.execute(
            """
            insert into public.memory_prompt_history (
              owner_id,
              category,
              last_proactive_prompt_at,
              last_declined_at,
              updated_at
            )
            values (%s, %s, %s, %s, %s)
            """,
            (
                owner_id,
                category.value,
                next_prompt_at,
                next_declined_at,
                updated_at,
            ),
        )
