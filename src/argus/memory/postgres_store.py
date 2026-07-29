"""Private Postgres persistence for scoped personalization-memory state."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Cursor, errors
from psycopg.rows import tuple_row
from psycopg_pool import ConnectionPool

from argus.memory.contracts import (
    MemoryCandidate,
    MemoryCategory,
    MemoryConsentActionReceipt,
    MemoryConsentSettings,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemorySourceKind,
    SavedDecisionSource,
    SensitivityAssessment,
)
from argus.memory.store import (
    CanonicalEnableMutation,
    ProposalHistorySnapshot,
)
from argus.memory.subject import (
    PersonalizationMemoryUnavailable,
    RegisteredMemoryOwner,
)

_ALL_MEMORY_CATEGORIES = tuple(sorted(MemoryCategory, key=lambda item: item.value))
_CANDIDATE_CAS_ATTEMPTS = 2
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
