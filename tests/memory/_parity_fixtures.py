"""Seeding for the store parity harness.

Both stores start with one owner and confirmed records and no projection.
Postgres uses the same inserts as the other Postgres suites; the deterministic
store goes through the service.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemorySourceKind,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    RegisteredMemoryOwner,
)

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


def seed_postgres_owner(connection: Any) -> str:
    owner_id = str(uuid.uuid4())
    email = f"projection-parity-{owner_id[:8]}@example.com"
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


def seed_postgres_record(connection: Any, owner_id: str) -> str:
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


def _ids() -> Iterator[str]:
    index = 0
    while True:
        index += 1
        yield f"parity-{index:03d}"


def seed_in_memory_records(
    store: Any,
    labels: tuple[str, ...],
) -> tuple[RegisteredMemoryOwner, dict[str, str]]:
    """The same starting shape, built through the service that owns the rules."""

    owner_id = str(uuid.uuid4())
    subject = MemorySubject(owner_id=owner_id, kind=MemoryAccountKind.REGISTERED)
    generated = _ids()
    # Real clock: later edits must not appear to precede creation.
    service = MemoryService(
        store=store,
        config=MemoryServiceConfig(available=True),
        id_factory=lambda: next(generated),
    )
    record_ids: dict[str, str] = {}
    for index, label in enumerate(labels):
        proposal = service.propose(
            subject,
            MemoryCandidateDraft(
                category=MemoryCategory.EXPLICIT_DECISION_NOTE,
                value=f"{label} value that was confirmed.",
                label=f"{label} label",
                future_benefit="Argus can revisit the confirmed choice later.",
                provenance=(
                    MemoryProvenance(
                        source_kind=MemorySourceKind.DECISION_NOTE,
                        source_id=f"decision-parity-{index}",
                        source_version="1",
                    ),
                ),
                trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
                sensitivity=SensitivityAssessment(status=SensitivityStatus.CLEAR),
            ),
            MemoryOperationContext.ORDINARY,
        )
        assert proposal is not None
        confirmation = service.confirm(
            subject,
            proposal.candidate.id,
            context=MemoryOperationContext.ORDINARY,
        )
        assert confirmation.record is not None
        record_ids[label] = confirmation.record.id
    return RegisteredMemoryOwner(owner_id=owner_id), record_ids
