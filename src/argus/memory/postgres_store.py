"""Private Postgres persistence for scoped personalization-memory state."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

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
    CanonicalOwnerReset,
    CanonicalRecordMutation,
    ProposalHistorySnapshot,
    ProviderCleanupTarget,
    ReconciliationClaim,
)
from argus.memory.subject import (
    PersonalizationMemoryUnavailable,
    RegisteredMemoryOwner,
)

_ALL_MEMORY_CATEGORIES = tuple(sorted(MemoryCategory, key=lambda item: item.value))
_CANDIDATE_CAS_ATTEMPTS = 2
_CONTROL_READ_LIMIT = 100
_RECONCILIATION_WAIT_ATTEMPTS = 20
_RECONCILIATION_WAIT_SECONDS = 0.05
_DEFAULT_RECONCILIATION_LEASE = timedelta(seconds=30)
_READ_COMMITTED = "set transaction isolation level read committed"
_SERIALIZABLE = "set transaction isolation level serializable"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PostgresCanonicalMemoryStore:
    """Direct-database adapter with canonical registered-owner revalidation."""

    def __init__(
        self,
        pool: ConnectionPool[Any],
        *,
        reconciliation_clock: Callable[[], datetime] = _utc_now,
        reconciliation_token_factory: Callable[[], str] | None = None,
        reconciliation_lease: timedelta = _DEFAULT_RECONCILIATION_LEASE,
        reconciliation_wait_attempts: int = _RECONCILIATION_WAIT_ATTEMPTS,
        reconciliation_wait_seconds: float = _RECONCILIATION_WAIT_SECONDS,
        reconciliation_sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if reconciliation_lease <= timedelta(0):
            raise ValueError("reconciliation lease must be positive")
        if reconciliation_wait_attempts < 1:
            raise ValueError("reconciliation wait attempts must be positive")
        if reconciliation_wait_seconds < 0:
            raise ValueError("reconciliation wait seconds must not be negative")
        self._pool = pool
        self._reconciliation_clock = reconciliation_clock
        self._reconciliation_token_factory = reconciliation_token_factory or (
            lambda: str(uuid4())
        )
        self._reconciliation_lease = reconciliation_lease
        self._reconciliation_wait_attempts = reconciliation_wait_attempts
        self._reconciliation_wait_seconds = reconciliation_wait_seconds
        self._reconciliation_sleeper = reconciliation_sleeper

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
    def _lock_owner(
        cursor: Cursor[Any],
        owner_id: UUID,
    ) -> None:
        cursor.execute(
            """
            select pg_advisory_xact_lock(
              pg_catalog.hashtextextended(%s, 0)
            )
            """,
            (f"argus:memory-owner:{owner_id}",),
        )

    @staticmethod
    def _lock_record(
        cursor: Cursor[Any],
        owner_id: UUID,
        record_id: str,
    ) -> None:
        cursor.execute(
            """
            select pg_advisory_xact_lock(
              pg_catalog.hashtextextended(%s, 0)
            )
            """,
            (f"argus:memory-record:{owner_id}:{record_id}",),
        )

    @staticmethod
    def _lock_provider_refs(
        cursor: Cursor[Any],
        owner_id: UUID,
        provider_refs: tuple[str, ...],
    ) -> None:
        for provider_ref in sorted(set(provider_refs)):
            cursor.execute(
                """
                select pg_advisory_xact_lock(
                  pg_catalog.hashtextextended(%s, 0)
                )
                """,
                (f"argus:memory-provider-ref:{owner_id}:{provider_ref}",),
            )

    @staticmethod
    def _provider_ref_is_reserved(
        cursor: Cursor[Any],
        owner_id: UUID,
        provider_ref: str,
    ) -> bool:
        cursor.execute(
            """
            select exists (
              select 1
                from public.memory_provider_cleanup
               where owner_id = %s
                 and provider_ref = %s
                 and status = 'pending'
            )
            """,
            (owner_id, provider_ref),
        )
        row = cursor.fetchone()
        assert row is not None
        return bool(row[0])

    @staticmethod
    def _reconciliation_claim_is_live(
        cursor: Cursor[Any],
        owner_id: UUID,
        record_id: str,
        claim: ReconciliationClaim,
    ) -> bool:
        cursor.execute(
            """
            select exists (
              select 1
                from public.memory_reconciliations
               where owner_id = %s
                 and record_id = %s
                 and generation = %s
                 and operation = %s
                 and status = 'running'
                 and claim_token = %s
                 and lease_expires_at > statement_timestamp()
            )
            """,
            (
                owner_id,
                record_id,
                claim.generation,
                claim.operation,
                claim.claim_token,
            ),
        )
        row = cursor.fetchone()
        assert row is not None
        return bool(row[0])

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

    def list_consent_receipts(
        self,
        owner: RegisteredMemoryOwner,
    ) -> tuple[MemoryConsentActionReceipt, ...]:
        with self._transaction(owner) as (cursor, owner_id):
            cursor.execute(
                """
                select id
                  from public.memory_consent_actions
                 where owner_id = %s
                 order by recorded_at desc, id desc
                 limit %s
                """,
                (owner_id, _CONTROL_READ_LIMIT),
            )
            receipt_ids = tuple(row[0] for row in cursor.fetchall())
            return tuple(
                self._read_consent_receipt(cursor, owner_id, receipt_id)
                for receipt_id in receipt_ids
            )

    def list_records(
        self,
        owner: RegisteredMemoryOwner,
    ) -> tuple[MemoryRecord, ...]:
        with self._transaction(owner) as (cursor, owner_id):
            cursor.execute(
                """
                select id, consent_action_id
                  from public.memory_records
                 where owner_id = %s
                 order by created_at desc, id desc
                 limit %s
                """,
                (owner_id, _CONTROL_READ_LIMIT),
            )
            identities = tuple(cursor.fetchall())
            return tuple(
                self._read_record(
                    cursor,
                    owner_id,
                    record_id,
                    consent_receipt=self._read_consent_receipt(
                        cursor,
                        owner_id,
                        consent_action_id,
                    ),
                )
                for record_id, consent_action_id in identities
            )

    def get_record(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> MemoryRecord | None:
        with self._transaction(owner) as (cursor, owner_id):
            return self._read_record_if_present(cursor, owner_id, record_id)

    @classmethod
    def _read_record_if_present(
        cls,
        cursor: Cursor[Any],
        owner_id: UUID,
        record_id: str,
    ) -> MemoryRecord | None:
        cursor.execute(
            """
            select consent_action_id
              from public.memory_records
             where owner_id = %s and id = %s
            """,
            (owner_id, record_id),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return cls._read_record(
            cursor,
            owner_id,
            record_id,
            consent_receipt=cls._read_consent_receipt(
                cursor,
                owner_id,
                row[0],
            ),
        )

    def edit_record(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        *,
        value: str | None,
        label: str | None,
        clock: Callable[[], datetime] | None = None,
    ) -> CanonicalRecordMutation | None:
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            self._lock_record(cursor, owner_id, record_id)
            cursor.execute(
                """
                select consent_action_id
                  from public.memory_records
                 where owner_id = %s and id = %s
                 for update
                """,
                (owner_id, record_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            current = self._read_record(
                cursor,
                owner_id,
                record_id,
                consent_receipt=self._read_consent_receipt(
                    cursor,
                    owner_id,
                    row[0],
                ),
            )
            next_value = current.value if value is None else value
            next_label = current.label if label is None else label
            if next_value == current.value and next_label == current.label:
                raise ValueError("memory edit must change value or label")
            if not next_value or len(next_value) > 4_096:
                raise ValueError(
                    "memory value must contain between 1 and 4096 characters"
                )
            if not next_label.strip() or len(next_label) > 120:
                raise ValueError("memory label must contain between 1 and 120 characters")
            updated_at = (clock or _utc_now)()
            if updated_at <= current.updated_at:
                raise ValueError(
                    "memory edit time must be later than the current update time"
                )
            updated = MemoryRecord.model_validate(
                {
                    **current.model_dump(),
                    "label": next_label,
                    "value": next_value,
                    "revision": current.revision + 1,
                    "updated_at": updated_at,
                }
            )
            cursor.execute(
                """
                update public.memory_records
                   set label = %s,
                       value = %s,
                       revision = %s,
                       updated_at = %s
                 where owner_id = %s and id = %s
                """,
                (
                    updated.label,
                    updated.value,
                    updated.revision,
                    updated.updated_at,
                    owner_id,
                    record_id,
                ),
            )
            generation = self._next_reconciliation_generation(
                cursor,
                owner_id,
                record_id,
            )
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
                values (%s, %s, %s, 'update', 'pending', %s)
                """,
                (owner_id, record_id, generation, updated.updated_at),
            )
            cursor.execute(
                """
                select provider_ref
                  from public.memory_provider_projections
                 where owner_id = %s and record_id = %s
                """,
                (owner_id, record_id),
            )
            projection = cursor.fetchone()
            return CanonicalRecordMutation(
                before=current,
                after=updated,
                provider_ref=None if projection is None else projection[0],
                reconciliation_generation=generation,
            )

    def delete_record(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> CanonicalRecordMutation | None:
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            cursor.execute(
                """
                select 1
                  from public.memory_records
                 where owner_id = %s and id = %s
                """,
                (owner_id, record_id),
            )
            if cursor.fetchone() is None:
                return None
        self._wait_for_record_reconciliation(owner, record_id)
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            self._lock_record(cursor, owner_id, record_id)
            cursor.execute(
                """
                select consent_action_id
                  from public.memory_records
                 where owner_id = %s and id = %s
                 for update
                """,
                (owner_id, record_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if self._has_pending_reconciliation(cursor, owner_id, record_id):
                raise TimeoutError(
                    "memory control timed out waiting for provider reconciliation"
                )
            current = self._read_record(
                cursor,
                owner_id,
                record_id,
                consent_receipt=self._read_consent_receipt(
                    cursor,
                    owner_id,
                    row[0],
                ),
            )
            cursor.execute(
                """
                select provider_ref, generation
                  from public.memory_provider_projections
                 where owner_id = %s and record_id = %s
                """,
                (owner_id, record_id),
            )
            projection = cursor.fetchone()
            provider_ref = None if projection is None else projection[0]
            cursor.execute(
                """
                select distinct provider_ref
                  from public.memory_provider_cleanup
                 where owner_id = %s
                   and record_id = %s
                   and status = 'pending'
                 order by provider_ref
                """,
                (owner_id, record_id),
            )
            cleanup_refs = {item[0] for item in cursor.fetchall()}
            if projection is not None and provider_ref not in cleanup_refs:
                cursor.execute(
                    """
                    select coalesce(max(generation), 0)
                      from public.memory_provider_cleanup
                     where owner_id = %s
                       and record_id = %s
                       and provider_ref = %s
                    """,
                    (owner_id, record_id, provider_ref),
                )
                prior_cleanup_row = cursor.fetchone()
                assert prior_cleanup_row is not None
                prior_cleanup_generation = prior_cleanup_row[0]
                cleanup_generation = max(
                    projection[1],
                    prior_cleanup_generation + 1,
                )
                cursor.execute(
                    """
                    insert into public.memory_provider_cleanup (
                      owner_id,
                      record_id,
                      provider_ref,
                      generation,
                      status,
                      created_at
                    )
                    values (%s, %s, %s, %s, 'pending', %s)
                    """,
                    (
                        owner_id,
                        record_id,
                        provider_ref,
                        cleanup_generation,
                        _utc_now(),
                    ),
                )
                cleanup_refs.add(provider_ref)
            generation = self._next_reconciliation_generation(
                cursor,
                owner_id,
                record_id,
            )
            cursor.execute(
                """
                delete from public.memory_records
                 where owner_id = %s and id = %s
                """,
                (owner_id, record_id),
            )
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
                values (%s, %s, %s, 'delete', 'pending', %s)
                """,
                (owner_id, record_id, generation, _utc_now()),
            )
            return CanonicalRecordMutation(
                before=current,
                after=None,
                provider_ref=provider_ref,
                reconciliation_generation=generation,
                cleanup_refs=tuple(sorted(cleanup_refs)),
            )

    def claim_reconciliation_turn(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        reconciliation_generation: int,
    ) -> ReconciliationClaim | None:
        if record_id != "" and (not record_id.strip() or len(record_id) > 128):
            raise ValueError("record id must contain 1 to 128 characters")
        if reconciliation_generation < 1:
            raise ValueError("reconciliation generation must be positive")
        self._owner_uuid(owner)
        for attempt in range(self._reconciliation_wait_attempts):
            claim, prior_unfinished = self._claim_reconciliation_once(
                owner,
                record_id,
                reconciliation_generation,
            )
            if claim is not None or not prior_unfinished:
                return claim
            if attempt + 1 < self._reconciliation_wait_attempts:
                self._reconciliation_sleeper(self._reconciliation_wait_seconds)
        return None

    def _claim_reconciliation_once(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        reconciliation_generation: int,
    ) -> tuple[ReconciliationClaim | None, bool]:
        now = self._reconciliation_clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("reconciliation clock must return an aware datetime")
        lease_expires_at = now + self._reconciliation_lease

        with self._confirmation_transaction(owner) as (cursor, owner_id):
            self._lock_owner(cursor, owner_id)
            if record_id != "":
                cursor.execute(
                    """
                    select exists (
                      select 1
                        from public.memory_reconciliations
                       where owner_id = %s
                         and operation = 'reset'
                    )
                    """,
                    (owner_id,),
                )
                reset_row = cursor.fetchone()
                assert reset_row is not None
                if reset_row[0]:
                    return None, False
                self._lock_record(cursor, owner_id, record_id)
            cursor.execute(
                """
                select operation,status,claim_token,lease_expires_at
                  from public.memory_reconciliations
                 where owner_id = %s
                   and record_id = %s
                   and generation = %s
                 for update
                """,
                (owner_id, record_id, reconciliation_generation),
            )
            row = cursor.fetchone()
            if row is None or row[1] in ("succeeded", "failed"):
                return None, False
            cursor.execute(
                """
                select exists (
                  select 1
                    from public.memory_reconciliations
                   where owner_id = %s
                     and record_id = %s
                     and generation < %s
                     and status in ('pending', 'running')
                )
                """,
                (owner_id, record_id, reconciliation_generation),
            )
            prior_row = cursor.fetchone()
            assert prior_row is not None
            if prior_row[0]:
                return None, True

            operation, status, old_claim_token, old_lease_expires_at = row
            if (
                status == "running"
                and old_lease_expires_at is not None
                and old_lease_expires_at > now
            ):
                return None, False
            claim_token = self._reconciliation_token_factory()
            if not isinstance(claim_token, str):
                raise ValueError("reconciliation claim token must be text")
            claim_token = claim_token.strip()
            if not claim_token or len(claim_token) > 128:
                raise ValueError(
                    "reconciliation claim token must contain 1 to 128 characters"
                )
            cursor.execute(
                """
                update public.memory_reconciliations
                   set status = 'running',
                       claim_token = %s,
                       lease_expires_at = %s,
                       attempt_count = attempt_count + 1,
                       error_code = null,
                       completed_at = null
                 where owner_id = %s
                   and record_id = %s
                   and generation = %s
                   and status = %s
                   and claim_token is not distinct from %s
                   and lease_expires_at is not distinct from %s
             returning operation
                """,
                (
                    claim_token,
                    lease_expires_at,
                    owner_id,
                    record_id,
                    reconciliation_generation,
                    status,
                    old_claim_token,
                    old_lease_expires_at,
                ),
            )
            updated = cursor.fetchone()
            if updated is None:
                return None, False
            return (
                ReconciliationClaim(
                    record_id=record_id,
                    generation=reconciliation_generation,
                    operation=operation,
                    claim_token=claim_token,
                ),
                False,
            )

    def finish_reconciliation_claim(
        self,
        owner: RegisteredMemoryOwner,
        claim: ReconciliationClaim,
        *,
        succeeded: bool,
        error_code: str | None,
        completed_at: datetime,
    ) -> bool:
        if completed_at.tzinfo is None or completed_at.utcoffset() is None:
            raise ValueError("reconciliation completion time must be aware")
        if succeeded:
            if error_code is not None:
                raise ValueError("successful reconciliation forbids an error code")
            status = "succeeded"
        else:
            if error_code is None or not error_code.strip() or len(error_code) > 128:
                raise ValueError(
                    "failed reconciliation requires a 1 to 128 character error code"
                )
            status = "failed"
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            self._lock_owner(cursor, owner_id)
            if claim.record_id != "":
                self._lock_record(cursor, owner_id, claim.record_id)
            cursor.execute(
                """
                update public.memory_reconciliations
                   set status = %s,
                       claim_token = null,
                       lease_expires_at = null,
                       error_code = %s,
                       completed_at = %s
                 where owner_id = %s
                   and record_id = %s
                   and generation = %s
                   and operation = %s
                   and status = 'running'
                   and claim_token = %s
                   and lease_expires_at > statement_timestamp()
             returning 1
                """,
                (
                    status,
                    error_code,
                    completed_at,
                    owner_id,
                    claim.record_id,
                    claim.generation,
                    claim.operation,
                    claim.claim_token,
                ),
            )
            return cursor.fetchone() is not None

    def compare_and_set_provider_ref(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        *,
        expected_record: MemoryRecord,
        expected_provider_ref: str | None,
        reconciliation_claim: ReconciliationClaim,
        provider_ref: str,
    ) -> bool:
        if not provider_ref:
            raise ValueError("provider ref must not be empty")
        if len(provider_ref) > 1_024:
            raise ValueError("provider ref must not exceed 1024 characters")
        effective_at = self._reconciliation_clock()
        if effective_at.tzinfo is None or effective_at.utcoffset() is None:
            raise ValueError("reconciliation clock must return an aware datetime")
        try:
            with self._confirmation_transaction(owner) as (cursor, owner_id):
                self._lock_owner(cursor, owner_id)
                cursor.execute(
                    """
                    select exists (
                      select 1
                        from public.memory_reconciliations
                       where owner_id = %s
                         and operation = 'reset'
                    )
                    """,
                    (owner_id,),
                )
                reset_row = cursor.fetchone()
                assert reset_row is not None
                if reset_row[0]:
                    return False
                self._lock_record(cursor, owner_id, record_id)
                if (
                    reconciliation_claim.record_id != record_id
                    or not self._reconciliation_claim_is_live(
                        cursor,
                        owner_id,
                        record_id,
                        reconciliation_claim,
                    )
                ):
                    return False
                current_record = self._read_record_if_present(
                    cursor,
                    owner_id,
                    record_id,
                )
                if current_record != expected_record:
                    return False
                cursor.execute(
                    """
                    select provider_ref
                      from public.memory_provider_projections
                     where owner_id = %s and record_id = %s
                     for update
                    """,
                    (owner_id, record_id),
                )
                projection_row = cursor.fetchone()
                current_provider_ref = (
                    None if projection_row is None else projection_row[0]
                )
                if current_provider_ref != expected_provider_ref:
                    return False
                self._lock_provider_refs(
                    cursor,
                    owner_id,
                    tuple(
                        ref
                        for ref in (current_provider_ref, provider_ref)
                        if ref is not None
                    ),
                )
                if not self._reconciliation_claim_is_live(
                    cursor,
                    owner_id,
                    record_id,
                    reconciliation_claim,
                ):
                    return False
                if self._provider_ref_is_reserved(
                    cursor,
                    owner_id,
                    provider_ref,
                ):
                    return False
                if (
                    current_provider_ref is not None
                    and current_provider_ref != provider_ref
                ):
                    self._insert_provider_cleanup_target(
                        cursor,
                        owner_id,
                        record_id,
                        current_provider_ref,
                        minimum_generation=reconciliation_claim.generation,
                    )
                if projection_row is None:
                    cursor.execute(
                        """
                        insert into public.memory_provider_projections (
                          owner_id,
                          record_id,
                          provider_ref,
                          generation,
                          updated_at
                        )
                        values (%s, %s, %s, %s, %s)
                        """,
                        (
                            owner_id,
                            record_id,
                            provider_ref,
                            reconciliation_claim.generation,
                            effective_at,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        update public.memory_provider_projections
                           set provider_ref = %s,
                               generation = %s,
                               updated_at = %s
                         where owner_id = %s and record_id = %s
                        """,
                        (
                            provider_ref,
                            reconciliation_claim.generation,
                            effective_at,
                            owner_id,
                            record_id,
                        ),
                    )
                return True
        except errors.UniqueViolation:
            return False

    def set_provider_ref(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> bool:
        if not provider_ref or len(provider_ref) > 1_024:
            raise ValueError("provider ref must contain 1 to 1024 characters")
        if not record_id.strip() or len(record_id) > 128:
            raise ValueError("record id must contain 1 to 128 characters")
        try:
            with self._confirmation_transaction(owner) as (cursor, owner_id):
                self._lock_owner(cursor, owner_id)
                cursor.execute(
                    """
                    select exists (
                      select 1
                        from public.memory_reconciliations
                       where owner_id = %s
                         and operation = 'reset'
                    )
                    """,
                    (owner_id,),
                )
                reset_row = cursor.fetchone()
                assert reset_row is not None
                if reset_row[0]:
                    return False
                self._lock_record(cursor, owner_id, record_id)
                cursor.execute(
                    """
                    select 1
                      from public.memory_records
                     where owner_id = %s and id = %s
                    """,
                    (owner_id, record_id),
                )
                if cursor.fetchone() is None:
                    return False
                cursor.execute(
                    """
                    select provider_ref,generation
                      from public.memory_provider_projections
                     where owner_id = %s and record_id = %s
                     for update
                    """,
                    (owner_id, record_id),
                )
                projection = cursor.fetchone()
                self._lock_provider_refs(
                    cursor,
                    owner_id,
                    tuple(
                        ref
                        for ref in (
                            None if projection is None else str(projection[0]),
                            provider_ref,
                        )
                        if ref is not None
                    ),
                )
                if self._provider_ref_is_reserved(
                    cursor,
                    owner_id,
                    provider_ref,
                ):
                    return False
                if projection is not None and projection[0] == provider_ref:
                    return True
                cursor.execute(
                    """
                    select record_id
                      from public.memory_provider_projections
                     where owner_id = %s
                       and provider_ref = %s
                       and record_id <> %s
                     for update
                    """,
                    (owner_id, provider_ref, record_id),
                )
                if cursor.fetchone() is not None:
                    return False
                cursor.execute(
                    """
                    select coalesce(max(generation), 1)
                      from public.memory_reconciliations
                     where owner_id = %s and record_id = %s
                    """,
                    (owner_id, record_id),
                )
                generation_row = cursor.fetchone()
                assert generation_row is not None
                generation = int(generation_row[0])
                if projection is not None:
                    generation = max(generation, int(projection[1]))
                    self._insert_provider_cleanup_target(
                        cursor,
                        owner_id,
                        record_id,
                        str(projection[0]),
                        minimum_generation=generation,
                    )
                    cursor.execute(
                        """
                        update public.memory_provider_projections
                           set provider_ref = %s,
                               generation = %s,
                               updated_at = %s
                         where owner_id = %s and record_id = %s
                        """,
                        (
                            provider_ref,
                            generation,
                            self._reconciliation_clock(),
                            owner_id,
                            record_id,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        insert into public.memory_provider_projections (
                          owner_id,
                          record_id,
                          provider_ref,
                          generation,
                          updated_at
                        )
                        values (%s, %s, %s, %s, %s)
                        """,
                        (
                            owner_id,
                            record_id,
                            provider_ref,
                            generation,
                            self._reconciliation_clock(),
                        ),
                    )
                return True
        except errors.UniqueViolation:
            return False

    def get_provider_ref(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> str | None:
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            cursor.execute(
                """
                select provider_ref
                  from public.memory_provider_projections
                 where owner_id = %s and record_id = %s
                """,
                (owner_id, record_id),
            )
            row = cursor.fetchone()
            return None if row is None else row[0]

    def track_provider_cleanup_target(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> bool:
        if not record_id.strip() or len(record_id) > 128:
            raise ValueError("record id must contain 1 to 128 characters")
        if not provider_ref or len(provider_ref) > 1_024:
            raise ValueError("provider ref must contain 1 to 1024 characters")
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            self._lock_record(cursor, owner_id, record_id)
            self._lock_provider_refs(cursor, owner_id, (provider_ref,))
            cursor.execute(
                """
                select record_id
                  from public.memory_provider_projections
                 where owner_id = %s and provider_ref = %s
                 for update
                """,
                (owner_id, provider_ref),
            )
            projected = cursor.fetchone()
            if projected is not None and projected[0] != record_id:
                return False
            self._insert_provider_cleanup_target(
                cursor,
                owner_id,
                record_id,
                provider_ref,
                minimum_generation=(
                    1
                    if projected is None
                    else self._provider_projection_generation(
                        cursor,
                        owner_id,
                        record_id,
                    )
                ),
            )
            return True

    def resolve_provider_cleanup_target(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> bool:
        if not record_id.strip() or len(record_id) > 128:
            raise ValueError("record id must contain 1 to 128 characters")
        if not provider_ref or len(provider_ref) > 1_024:
            raise ValueError("provider ref must contain 1 to 1024 characters")
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            self._lock_record(cursor, owner_id, record_id)
            self._lock_provider_refs(cursor, owner_id, (provider_ref,))
            cursor.execute(
                """
                update public.memory_provider_cleanup
                   set status = 'resolved',
                       resolved_at = statement_timestamp()
                 where owner_id = %s
                   and record_id = %s
                   and provider_ref = %s
                   and status = 'pending'
             returning 1
                """,
                (owner_id, record_id, provider_ref),
            )
            resolved = cursor.fetchall()
            if not resolved:
                return False
            cursor.execute(
                """
                delete from public.memory_provider_projections
                 where owner_id = %s
                   and record_id = %s
                   and provider_ref = %s
                """,
                (owner_id, record_id, provider_ref),
            )
            return True

    def list_provider_cleanup_targets(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str | None = None,
    ) -> tuple[ProviderCleanupTarget, ...]:
        if record_id is not None and (not record_id.strip() or len(record_id) > 128):
            raise ValueError("record id must contain 1 to 128 characters")
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            if record_id is None:
                cursor.execute(
                    """
                    select record_id,provider_ref,max(created_at) as newest_created_at
                      from public.memory_provider_cleanup
                     where owner_id = %s
                       and status = 'pending'
                     group by record_id,provider_ref
                     order by newest_created_at desc,record_id,provider_ref
                     limit %s
                    """,
                    (owner_id, _CONTROL_READ_LIMIT),
                )
            else:
                cursor.execute(
                    """
                    select record_id,provider_ref,max(created_at) as newest_created_at
                      from public.memory_provider_cleanup
                     where owner_id = %s
                       and status = 'pending'
                       and record_id = %s
                     group by record_id,provider_ref
                     order by newest_created_at desc,record_id,provider_ref
                     limit %s
                    """,
                    (owner_id, record_id, _CONTROL_READ_LIMIT),
                )
            return tuple(
                ProviderCleanupTarget(record_id=row[0], provider_ref=row[1])
                for row in cursor.fetchall()
            )

    @staticmethod
    def _provider_projection_generation(
        cursor: Cursor[Any],
        owner_id: UUID,
        record_id: str,
    ) -> int:
        cursor.execute(
            """
            select generation
              from public.memory_provider_projections
             where owner_id = %s and record_id = %s
            """,
            (owner_id, record_id),
        )
        row = cursor.fetchone()
        return 1 if row is None else int(row[0])

    @staticmethod
    def _insert_provider_cleanup_target(
        cursor: Cursor[Any],
        owner_id: UUID,
        record_id: str,
        provider_ref: str,
        *,
        minimum_generation: int,
    ) -> None:
        cursor.execute(
            """
            select 1
              from public.memory_provider_cleanup
             where owner_id = %s
               and record_id = %s
               and provider_ref = %s
               and status = 'pending'
             limit 1
            """,
            (owner_id, record_id, provider_ref),
        )
        if cursor.fetchone() is not None:
            return
        cursor.execute(
            """
            select greatest(
              %s,
              coalesce(max(generation) + 1, 1)
            )
              from public.memory_provider_cleanup
             where owner_id = %s
               and record_id = %s
               and provider_ref = %s
            """,
            (minimum_generation, owner_id, record_id, provider_ref),
        )
        generation_row = cursor.fetchone()
        assert generation_row is not None
        cursor.execute(
            """
            insert into public.memory_provider_cleanup (
              owner_id,
              record_id,
              provider_ref,
              generation,
              status,
              created_at
            )
            values (%s, %s, %s, %s, 'pending', statement_timestamp())
            """,
            (
                owner_id,
                record_id,
                provider_ref,
                int(generation_row[0]),
            ),
        )

    def inflight_reconciliation_generations(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> tuple[int, ...]:
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            cursor.execute(
                """
                select generation
                  from public.memory_reconciliations
                 where owner_id = %s
                   and record_id = %s
                   and status in ('pending', 'running')
                 order by generation
                """,
                (owner_id, record_id),
            )
            return tuple(int(row[0]) for row in cursor.fetchall())

    def disable(self, owner: RegisteredMemoryOwner) -> bool:
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            self._lock_all_categories(cursor, owner_id)
            changed = False
            for table in (
                "memory_settings",
                "memory_candidates",
                "memory_prompt_history",
            ):
                cursor.execute(
                    f"delete from public.{table} where owner_id = %s",
                    (owner_id,),
                )
                changed = changed or cursor.rowcount > 0
            return changed

    def reset(self, owner: RegisteredMemoryOwner) -> CanonicalOwnerReset:
        self._owner_uuid(owner)
        self._wait_for_owner_record_reconciliation(owner)
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            self._lock_owner(cursor, owner_id)
            self._lock_all_categories(cursor, owner_id)
            record_ids = tuple(
                record_id
                for record_id in self._logical_record_ids(cursor, owner_id)
                if record_id
            )
            for record_id in record_ids:
                self._lock_record(cursor, owner_id, record_id)
            has_prior_reset = self._owner_has_reset_reconciliation(cursor, owner_id)
            if not has_prior_reset and self._owner_has_pending_record_reconciliation(
                cursor, owner_id
            ):
                raise TimeoutError(
                    "memory control timed out waiting for provider reconciliation"
                )
            counts = self._owner_memory_counts(cursor, owner_id)
            cursor.execute(
                """
                select exists (
                  select 1
                    from public.memory_provider_projections
                   where owner_id = %s
                )
                or exists (
                  select 1
                    from public.memory_provider_cleanup
                   where owner_id = %s and status = 'pending'
                )
                """,
                (owner_id, owner_id),
            )
            provider_state_row = cursor.fetchone()
            assert provider_state_row is not None
            provider_state_existed = bool(provider_state_row[0])
            changed = any(counts[:6])
            cursor.execute(
                """
                insert into public.memory_provider_cleanup (
                  owner_id,
                  record_id,
                  provider_ref,
                  generation,
                  status,
                  created_at
                )
                select
                  projection.owner_id,
                  projection.record_id,
                  projection.provider_ref,
                  greatest(
                    projection.generation,
                    coalesce(
                      (
                        select max(cleanup.generation) + 1
                          from public.memory_provider_cleanup as cleanup
                         where cleanup.owner_id = projection.owner_id
                           and cleanup.record_id = projection.record_id
                           and cleanup.provider_ref = projection.provider_ref
                      ),
                      1
                    )
                  ),
                  'pending',
                  %s
                  from public.memory_provider_projections as projection
                 where projection.owner_id = %s
                   and not exists (
                     select 1
                       from public.memory_provider_cleanup as pending_cleanup
                      where pending_cleanup.owner_id = projection.owner_id
                        and pending_cleanup.record_id = projection.record_id
                        and pending_cleanup.provider_ref = projection.provider_ref
                        and pending_cleanup.status = 'pending'
                   )
                on conflict do nothing
                """,
                (_utc_now(), owner_id),
            )
            cursor.execute(
                """
                delete from public.memory_reconciliations
                 where owner_id = %s and record_id <> ''
                """,
                (owner_id,),
            )
            cursor.execute(
                "delete from public.memory_records where owner_id = %s",
                (owner_id,),
            )
            cursor.execute(
                "delete from public.memory_candidates where owner_id = %s",
                (owner_id,),
            )
            cursor.execute(
                "delete from public.memory_settings where owner_id = %s",
                (owner_id,),
            )
            cursor.execute(
                "delete from public.memory_prompt_history where owner_id = %s",
                (owner_id,),
            )
            cursor.execute(
                "delete from public.memory_consent_actions where owner_id = %s",
                (owner_id,),
            )
            cursor.execute(
                """
                delete from public.memory_provider_cleanup
                 where owner_id = %s and status = 'resolved'
                """,
                (owner_id,),
            )
            reset_generation: int | None = None
            if provider_state_existed:
                cursor.execute(
                    """
                    select generation
                      from public.memory_reconciliations
                     where owner_id = %s
                       and record_id = ''
                       and operation = 'reset'
                       and status in ('pending', 'running')
                     order by generation desc
                     limit 1
                    """,
                    (owner_id,),
                )
                unfinished = cursor.fetchone()
                if unfinished is not None:
                    reset_generation = int(unfinished[0])
                else:
                    cursor.execute(
                        """
                        select coalesce(max(generation), 0) + 1
                          from public.memory_reconciliations
                         where owner_id = %s
                           and record_id = ''
                        """,
                        (owner_id,),
                    )
                    generation_row = cursor.fetchone()
                    assert generation_row is not None
                    reset_generation = int(generation_row[0])
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
                        values (%s, '', %s, 'reset', 'pending', statement_timestamp())
                        """,
                        (owner_id, reset_generation),
                    )
            else:
                cursor.execute(
                    """
                    delete from public.memory_reconciliations
                     where owner_id = %s and record_id = ''
                    """,
                    (owner_id,),
                )
                cursor.execute(
                    "delete from public.memory_provider_projections where owner_id = %s",
                    (owner_id,),
                )
                cursor.execute(
                    "delete from public.memory_provider_cleanup where owner_id = %s",
                    (owner_id,),
                )
            return CanonicalOwnerReset(
                changed=changed,
                provider_state_existed=provider_state_existed,
                reconciliation_generation=reset_generation,
            )

    def complete_owner_reset(
        self,
        owner: RegisteredMemoryOwner,
        reconciliation_claim: ReconciliationClaim,
    ) -> bool:
        if (
            reconciliation_claim.operation != "reset"
            or reconciliation_claim.record_id != ""
        ):
            return False
        self._owner_uuid(owner)
        with self._confirmation_transaction(owner) as (cursor, owner_id):
            self._lock_owner(cursor, owner_id)
            self._lock_all_categories(cursor, owner_id)
            record_ids = tuple(
                record_id
                for record_id in self._logical_record_ids(cursor, owner_id)
                if record_id
            )
            for record_id in record_ids:
                self._lock_record(cursor, owner_id, record_id)
            if not self._reconciliation_claim_is_live(
                cursor,
                owner_id,
                "",
                reconciliation_claim,
            ):
                return False
            cursor.execute(
                "delete from public.memory_provider_projections where owner_id = %s",
                (owner_id,),
            )
            cursor.execute(
                "delete from public.memory_provider_cleanup where owner_id = %s",
                (owner_id,),
            )
            cursor.execute(
                """
                delete from public.memory_reconciliations
                 where owner_id = %s
                   and record_id = ''
                   and operation = 'reset'
                """,
                (owner_id,),
            )
            return True

    @staticmethod
    def _next_reconciliation_generation(
        cursor: Cursor[Any],
        owner_id: UUID,
        record_id: str,
    ) -> int:
        cursor.execute(
            """
            select coalesce(max(generation), 0) + 1
              from public.memory_reconciliations
             where owner_id = %s and record_id = %s
            """,
            (owner_id, record_id),
        )
        generation_row = cursor.fetchone()
        assert generation_row is not None
        return int(generation_row[0])

    @staticmethod
    def _has_pending_reconciliation(
        cursor: Cursor[Any],
        owner_id: UUID,
        record_id: str,
    ) -> bool:
        cursor.execute(
            """
            select exists (
              select 1
                from public.memory_reconciliations
               where owner_id = %s
                 and record_id = %s
                 and status in ('pending', 'running')
            )
            """,
            (owner_id, record_id),
        )
        pending_row = cursor.fetchone()
        assert pending_row is not None
        return bool(pending_row[0])

    @staticmethod
    def _owner_has_pending_record_reconciliation(
        cursor: Cursor[Any],
        owner_id: UUID,
    ) -> bool:
        cursor.execute(
            """
            select exists (
              select 1
                from public.memory_reconciliations
               where owner_id = %s
                 and record_id <> ''
                 and status in ('pending', 'running')
            )
            """,
            (owner_id,),
        )
        pending_row = cursor.fetchone()
        assert pending_row is not None
        return bool(pending_row[0])

    @staticmethod
    def _owner_has_reset_reconciliation(
        cursor: Cursor[Any],
        owner_id: UUID,
    ) -> bool:
        cursor.execute(
            """
            select exists (
              select 1
                from public.memory_reconciliations
               where owner_id = %s
                 and record_id = ''
                 and operation = 'reset'
            )
            """,
            (owner_id,),
        )
        reset_row = cursor.fetchone()
        assert reset_row is not None
        return bool(reset_row[0])

    def _wait_for_record_reconciliation(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
    ) -> None:
        for attempt in range(_RECONCILIATION_WAIT_ATTEMPTS):
            with self._confirmation_transaction(owner) as (cursor, owner_id):
                pending = self._has_pending_reconciliation(
                    cursor,
                    owner_id,
                    record_id,
                )
            if not pending:
                return
            if attempt + 1 < _RECONCILIATION_WAIT_ATTEMPTS:
                time.sleep(_RECONCILIATION_WAIT_SECONDS)
        raise TimeoutError("memory control timed out waiting for provider reconciliation")

    def _wait_for_owner_record_reconciliation(
        self,
        owner: RegisteredMemoryOwner,
    ) -> None:
        for attempt in range(self._reconciliation_wait_attempts):
            with self._confirmation_transaction(owner) as (cursor, owner_id):
                if self._owner_has_reset_reconciliation(cursor, owner_id):
                    return
                pending = self._owner_has_pending_record_reconciliation(
                    cursor,
                    owner_id,
                )
            if not pending:
                return
            if attempt + 1 < self._reconciliation_wait_attempts:
                self._reconciliation_sleeper(self._reconciliation_wait_seconds)
        raise TimeoutError("memory control timed out waiting for provider reconciliation")

    @staticmethod
    def _logical_record_ids(
        cursor: Cursor[Any],
        owner_id: UUID,
    ) -> tuple[str, ...]:
        cursor.execute(
            """
            select record_id
              from (
                select id as record_id
                  from public.memory_records
                 where owner_id = %s
                union
                select record_id
                  from public.memory_reconciliations
                 where owner_id = %s
                union
                select record_id
                  from public.memory_provider_projections
                 where owner_id = %s
                union
                select record_id
                  from public.memory_provider_cleanup
                 where owner_id = %s
              ) as logical_records
             order by record_id
            """,
            (owner_id, owner_id, owner_id, owner_id),
        )
        return tuple(row[0] for row in cursor.fetchall())

    @staticmethod
    def _owner_memory_counts(
        cursor: Cursor[Any],
        owner_id: UUID,
    ) -> tuple[int, ...]:
        cursor.execute(
            """
            select
              (select count(*) from public.memory_settings
                where owner_id = %s),
              (select count(*) from public.memory_candidates
                where owner_id = %s),
              (select count(*) from public.memory_consent_actions
                where owner_id = %s),
              (select count(*) from public.memory_records
                where owner_id = %s),
              (select count(*) from public.memory_provenance
                where owner_id = %s),
              (select count(*) from public.memory_prompt_history
                where owner_id = %s),
              (select count(*) from public.memory_reconciliations
                where owner_id = %s),
              (select count(*) from public.memory_provider_projections
                where owner_id = %s),
              (select count(*) from public.memory_provider_cleanup
                where owner_id = %s)
            """,
            (owner_id,) * 9,
        )
        counts_row = cursor.fetchone()
        assert counts_row is not None
        return tuple(int(value) for value in counts_row)

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
