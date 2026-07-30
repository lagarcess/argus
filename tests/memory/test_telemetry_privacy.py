from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from argus.memory.contracts import (
    MemoryCandidateDraft,
    MemoryCategory,
    MemoryEdit,
    MemoryOperationContext,
    MemoryProposalTrigger,
    MemoryProvenance,
    MemorySourceKind,
    MemoryUsePurpose,
    ProviderReconciliationStatus,
    SensitivityAssessment,
    SensitivityStatus,
)
from argus.memory.policy import PolicyOutcome
from argus.memory.provider import (
    MemoryRetrievalProvider,
    ProviderCleanupResult,
    ProviderProjectionResult,
    ProviderSearchResult,
    ProviderSearchStatus,
)
from argus.memory.service import MemoryService, MemoryServiceConfig
from argus.memory.store import InMemoryCanonicalMemoryStore
from argus.memory.subject import (
    MemoryAccountKind,
    MemorySubject,
    RegisteredMemoryOwner,
)
from argus.memory.telemetry import (
    MemoryDomainEvent,
    MemoryEvalTraceSink,
    MemoryEventSink,
    MemoryOperation,
    MemoryOutcome,
    MemoryPolicyTrace,
    MemoryProviderReceiptSink,
    PolicyReasonCode,
    ProviderCallReceipt,
    ProviderCallStatus,
    ProviderOperation,
)
from pydantic import ValidationError

NOW = datetime(2026, 7, 29, 20, 0, tzinfo=timezone.utc)
SUBJECT = MemorySubject(
    owner_id="066068f8-ee7b-4fa3-92c2-f9acdfe1c5ab",
    kind=MemoryAccountKind.REGISTERED,
)
CLEAR = SensitivityAssessment(status=SensitivityStatus.CLEAR)

VALID_EVENT_PAIRS = {
    (MemoryOperation.PROPOSE_SAVED_DECISION, MemoryOutcome.CANDIDATE_CREATED),
    (MemoryOperation.PROPOSE_SAVED_DECISION, MemoryOutcome.SUPPRESSED),
    (MemoryOperation.PROPOSE_SAVED_DECISION, MemoryOutcome.NO_CHANGE),
    (MemoryOperation.PROPOSE_SAVED_DECISION, MemoryOutcome.UNAVAILABLE),
    (MemoryOperation.PROPOSE, MemoryOutcome.CANDIDATE_CREATED),
    (MemoryOperation.PROPOSE, MemoryOutcome.SUPPRESSED),
    (MemoryOperation.PROPOSE, MemoryOutcome.NO_CHANGE),
    (MemoryOperation.PROPOSE, MemoryOutcome.UNAVAILABLE),
    (MemoryOperation.ENABLE, MemoryOutcome.ENABLED),
    (MemoryOperation.CONFIRM, MemoryOutcome.CONFIRMED),
    (MemoryOperation.CONFIRM, MemoryOutcome.SUPPRESSED),
    (MemoryOperation.CONFIRM, MemoryOutcome.NO_CHANGE),
    (MemoryOperation.CONFIRM, MemoryOutcome.UNAVAILABLE),
    (MemoryOperation.DECLINE, MemoryOutcome.DECLINED),
    (MemoryOperation.DECLINE, MemoryOutcome.NO_CHANGE),
    (MemoryOperation.INSPECT, MemoryOutcome.INSPECTED),
    (MemoryOperation.RETRIEVE, MemoryOutcome.RETRIEVED),
    (MemoryOperation.RETRIEVE, MemoryOutcome.SUPPRESSED),
    (MemoryOperation.RETRIEVE, MemoryOutcome.UNAVAILABLE),
    (MemoryOperation.EXPLAIN, MemoryOutcome.EXPLAINED),
    (MemoryOperation.EXPLAIN, MemoryOutcome.NO_CHANGE),
    (MemoryOperation.EDIT, MemoryOutcome.EDITED),
    (MemoryOperation.EDIT, MemoryOutcome.NO_CHANGE),
    (MemoryOperation.DELETE, MemoryOutcome.DELETED),
    (MemoryOperation.DELETE, MemoryOutcome.NO_CHANGE),
    (MemoryOperation.DISABLE, MemoryOutcome.DISABLED),
    (MemoryOperation.DISABLE, MemoryOutcome.NO_CHANGE),
    (MemoryOperation.RESET, MemoryOutcome.RESET),
    (MemoryOperation.RESET, MemoryOutcome.NO_CHANGE),
}

VALID_RECEIPT_TRIPLES = {
    (
        ProviderOperation.PROJECT,
        ProviderCallStatus.SUCCEEDED,
        ProviderReconciliationStatus.SYNCHRONIZED,
    ),
    (
        ProviderOperation.PROJECT,
        ProviderCallStatus.SUCCEEDED,
        ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
    ),
    (
        ProviderOperation.PROJECT,
        ProviderCallStatus.UNAVAILABLE,
        ProviderReconciliationStatus.NOT_APPLICABLE,
    ),
    (
        ProviderOperation.PROJECT,
        ProviderCallStatus.UNAVAILABLE,
        ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
    ),
    (
        ProviderOperation.PROJECT,
        ProviderCallStatus.FAILED,
        ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
    ),
    (
        ProviderOperation.SEARCH,
        ProviderCallStatus.SUCCEEDED,
        ProviderReconciliationStatus.NOT_APPLICABLE,
    ),
    (
        ProviderOperation.SEARCH,
        ProviderCallStatus.UNAVAILABLE,
        ProviderReconciliationStatus.NOT_APPLICABLE,
    ),
    (
        ProviderOperation.SEARCH,
        ProviderCallStatus.FAILED,
        ProviderReconciliationStatus.NOT_APPLICABLE,
    ),
    (
        ProviderOperation.DELETE,
        ProviderCallStatus.SUCCEEDED,
        ProviderReconciliationStatus.SYNCHRONIZED,
    ),
    (
        ProviderOperation.DELETE,
        ProviderCallStatus.SUCCEEDED,
        ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
    ),
    (
        ProviderOperation.DELETE,
        ProviderCallStatus.UNAVAILABLE,
        ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
    ),
    (
        ProviderOperation.DELETE,
        ProviderCallStatus.FAILED,
        ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
    ),
    (
        ProviderOperation.RESET,
        ProviderCallStatus.SUCCEEDED,
        ProviderReconciliationStatus.SYNCHRONIZED,
    ),
    (
        ProviderOperation.RESET,
        ProviderCallStatus.UNAVAILABLE,
        ProviderReconciliationStatus.NOT_APPLICABLE,
    ),
    (
        ProviderOperation.RESET,
        ProviderCallStatus.UNAVAILABLE,
        ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
    ),
    (
        ProviderOperation.RESET,
        ProviderCallStatus.FAILED,
        ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
    ),
}

VALID_POLICY_REASONS = {
    PolicyOutcome.ALLOWED: PolicyReasonCode.ALLOWED,
    PolicyOutcome.ALLOWED_OPT_IN: PolicyReasonCode.OPT_IN_REQUIRED,
    PolicyOutcome.DENIED_CATEGORY: PolicyReasonCode.CATEGORY_DENIED,
    PolicyOutcome.DENIED_SCOPE: PolicyReasonCode.SCOPE_DENIED,
    PolicyOutcome.DENIED_ASSISTED_FIRST_OPT_IN: (
        PolicyReasonCode.ASSISTED_FIRST_OPT_IN_DENIED
    ),
    PolicyOutcome.SUPPRESSED_CONTEXT: PolicyReasonCode.CONTEXT_RESTRICTED,
    PolicyOutcome.SUPPRESSED_SENSITIVITY: PolicyReasonCode.SENSITIVITY_RESTRICTED,
    PolicyOutcome.SUPPRESSED_COOLDOWN: PolicyReasonCode.COOLDOWN_ACTIVE,
    PolicyOutcome.SUPPRESSED_DISMISSAL: PolicyReasonCode.RECENTLY_DECLINED,
}
VALID_POLICY_OPERATIONS = {
    MemoryOperation.PROPOSE_SAVED_DECISION,
    MemoryOperation.PROPOSE,
    MemoryOperation.CONFIRM,
}


def test_memory_package_exports_the_three_typed_telemetry_planes() -> None:
    """Catches an incubation adapter depending on private telemetry modules."""
    import argus.memory as memory

    assert memory.MemoryDomainEvent is MemoryDomainEvent
    assert memory.ProviderCallReceipt is ProviderCallReceipt
    assert memory.MemoryPolicyTrace is MemoryPolicyTrace
    assert memory.MemoryEventSink is MemoryEventSink
    assert memory.MemoryProviderReceiptSink is MemoryProviderReceiptSink
    assert memory.MemoryEvalTraceSink is MemoryEvalTraceSink


def test_domain_event_exhaustively_rejects_unapproved_operation_outcome_pairs() -> None:
    """Catches a lifecycle outcome being attached to the wrong operation."""
    assert {
        (operation, outcome)
        for operation in MemoryOperation
        for outcome in MemoryOutcome
        if _accepts_event(operation, outcome)
    } == VALID_EVENT_PAIRS


def _accepts_event(
    operation: MemoryOperation,
    outcome: MemoryOutcome,
) -> bool:
    try:
        MemoryDomainEvent(
            correlation_id="correlation-matrix",
            operation=operation,
            outcome=outcome,
        )
    except ValidationError:
        return False
    return True


def test_provider_receipt_exhaustively_rejects_unapproved_status_combinations() -> None:
    """Catches raw call status and domain reconciliation truth becoming incoherent."""
    assert {
        (operation, status, reconciliation)
        for operation in ProviderOperation
        for status in ProviderCallStatus
        for reconciliation in ProviderReconciliationStatus
        if _accepts_receipt(operation, status, reconciliation)
    } == VALID_RECEIPT_TRIPLES


def _accepts_receipt(
    operation: ProviderOperation,
    status: ProviderCallStatus,
    reconciliation: ProviderReconciliationStatus,
) -> bool:
    try:
        ProviderCallReceipt(
            correlation_id="correlation-matrix",
            operation=operation,
            status=status,
            reconciliation_status=reconciliation,
        )
    except ValidationError:
        return False
    return True


def test_policy_trace_exhaustively_rejects_unapproved_outcome_reason_pairs() -> None:
    """Catches a deterministic policy outcome carrying a contradictory reason."""
    accepted = {
        (operation, outcome, reason)
        for operation in MemoryOperation
        for outcome in PolicyOutcome
        for reason in PolicyReasonCode
        if _accepts_trace(operation, outcome, reason)
    }
    assert accepted == {
        (operation, outcome, reason)
        for operation in VALID_POLICY_OPERATIONS
        for outcome, reason in VALID_POLICY_REASONS.items()
    }
    with pytest.raises(ValidationError):
        MemoryPolicyTrace(
            correlation_id="correlation-matrix",
            operation=MemoryOperation.PROPOSE,
            outcome=PolicyOutcome.ALLOWED,
            reason_codes=(
                PolicyReasonCode.ALLOWED,
                PolicyReasonCode.CONTEXT_RESTRICTED,
            ),
        )


def _accepts_trace(
    operation: MemoryOperation,
    outcome: PolicyOutcome,
    reason: PolicyReasonCode,
) -> bool:
    try:
        MemoryPolicyTrace(
            correlation_id="correlation-matrix",
            operation=operation,
            outcome=outcome,
            reason_codes=(reason,),
        )
    except ValidationError:
        return False
    return True


def _ids() -> Iterator[str]:
    index = 0
    while True:
        index += 1
        yield f"telemetry-id-{index:03d}"


def _draft(
    *,
    context: MemoryOperationContext = MemoryOperationContext.ORDINARY,
) -> tuple[MemoryCandidateDraft, MemoryOperationContext]:
    return (
        MemoryCandidateDraft(
            category=MemoryCategory.EXPLICIT_DECISION_NOTE,
            value="Keep the lower-drawdown decision.",
            label="Lower drawdown",
            future_benefit="Argus can revisit the confirmed decision.",
            provenance=(
                MemoryProvenance(
                    source_kind=MemorySourceKind.DECISION_NOTE,
                    source_id="decision-telemetry",
                    source_version="1",
                ),
            ),
            trigger=MemoryProposalTrigger.EXPLICIT_REQUEST,
            sensitivity=CLEAR,
        ),
        context,
    )


class _EventSink(MemoryEventSink):
    def __init__(self) -> None:
        self.items: list[MemoryDomainEvent] = []

    def emit(self, event: MemoryDomainEvent) -> None:
        self.items.append(event)


class _ReceiptSink(MemoryProviderReceiptSink):
    def __init__(self) -> None:
        self.items: list[ProviderCallReceipt] = []

    def record(self, receipt: ProviderCallReceipt) -> None:
        self.items.append(receipt)


class _TraceSink(MemoryEvalTraceSink):
    def __init__(self) -> None:
        self.items: list[MemoryPolicyTrace] = []

    def record(self, trace: MemoryPolicyTrace) -> None:
        self.items.append(trace)


def test_proposal_records_one_terminal_policy_trace() -> None:
    """Catches preflight success and terminal opt-in being double-counted."""
    traces = _TraceSink()
    service = _service(trace_sink=traces)
    draft, context = _draft()

    assert service.propose(SUBJECT, draft, context) is not None

    assert [(item.outcome, item.reason_codes) for item in traces.items] == [
        (PolicyOutcome.ALLOWED_OPT_IN, (PolicyReasonCode.OPT_IN_REQUIRED,))
    ]


def test_preflight_suppression_records_one_terminal_policy_trace() -> None:
    """Catches a suppressed proposal emitting a preliminary allowed trace."""
    traces = _TraceSink()
    service = _service(trace_sink=traces)
    draft, context = _draft(context=MemoryOperationContext.EXPORT)

    assert service.propose(SUBJECT, draft, context) is None

    assert [(item.outcome, item.reason_codes) for item in traces.items] == [
        (
            PolicyOutcome.SUPPRESSED_CONTEXT,
            (PolicyReasonCode.CONTEXT_RESTRICTED,),
        )
    ]


def test_post_preflight_cooldown_records_only_its_terminal_policy_trace() -> None:
    """Catches an allowed preflight trace preceding a terminal cooldown trace."""
    traces = _TraceSink()
    service = _service(trace_sink=traces)
    draft, context = _draft()
    proactive = draft.model_copy(update={"trigger": MemoryProposalTrigger.SAVED_DECISION})
    assert service.propose(SUBJECT, proactive, context) is not None
    traces.items.clear()

    assert service.propose(SUBJECT, proactive, context) is None

    assert [(item.outcome, item.reason_codes) for item in traces.items] == [
        (
            PolicyOutcome.SUPPRESSED_COOLDOWN,
            (PolicyReasonCode.COOLDOWN_ACTIVE,),
        )
    ]


def test_confirmation_revalidation_records_one_terminal_policy_trace() -> None:
    """Catches confirmation preflight and revalidation being counted as two decisions."""
    traces = _TraceSink()
    service = _service(trace_sink=traces)
    draft, context = _draft()
    proposal = service.propose(SUBJECT, draft, context)
    assert proposal is not None
    traces.items.clear()

    confirmation = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        sensitivity=CLEAR,
        context=context,
    )

    assert confirmation.created is True
    assert [(item.outcome, item.reason_codes) for item in traces.items] == [
        (PolicyOutcome.ALLOWED_OPT_IN, (PolicyReasonCode.OPT_IN_REQUIRED,))
    ]


class _MeasuredProvider(MemoryRetrievalProvider):
    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: Any,
    ) -> ProviderProjectionResult:
        del owner, record
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            provider_ref="provider-ref-1",
            usage_units=3,
            reported_cost_usd=Decimal("0.0012"),
        )

    def search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult:
        del owner, query, limit
        return ProviderSearchResult(
            status=ProviderSearchStatus.ANSWERED,
            hits=(),
            usage_units=2,
            reported_cost_usd=Decimal("0.0004"),
        )

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        del owner, provider_ref
        return ProviderCleanupResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            usage_units=1,
            reported_cost_usd=Decimal("0.0001"),
        )

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        del owner
        return ProviderCleanupResult(
            status=ProviderReconciliationStatus.SYNCHRONIZED,
            usage_units=1,
            reported_cost_usd=Decimal("0.0001"),
        )


class _RawOutcomeProvider(MemoryRetrievalProvider):
    def __init__(
        self,
        *,
        project: object = ProviderProjectionResult(
            status=ProviderReconciliationStatus.NOT_APPLICABLE
        ),
        search: object = ProviderSearchResult(status=ProviderSearchStatus.UNAVAILABLE),
        delete: object = ProviderCleanupResult(
            status=ProviderReconciliationStatus.NOT_APPLICABLE
        ),
        reset: object = ProviderCleanupResult(
            status=ProviderReconciliationStatus.NOT_APPLICABLE
        ),
    ) -> None:
        self.project_outcome = project
        self.search_outcome = search
        self.delete_outcome = delete
        self.reset_outcome = reset

    @staticmethod
    def _resolve(outcome: object) -> object:
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def project(  # type: ignore[override]
        self,
        owner: RegisteredMemoryOwner,
        record: Any,
    ) -> object:
        del owner, record
        return self._resolve(self.project_outcome)

    def search(  # type: ignore[override]
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> object:
        del owner, query, limit
        return self._resolve(self.search_outcome)

    def delete(  # type: ignore[override]
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> object:
        del owner, provider_ref
        return self._resolve(self.delete_outcome)

    def reset(self, owner: RegisteredMemoryOwner) -> object:  # type: ignore[override]
        del owner
        return self._resolve(self.reset_outcome)


@pytest.mark.parametrize(
    ("outcome", "expected_call", "expected_reconciliation"),
    (
        (
            ProviderProjectionResult(
                status=ProviderReconciliationStatus.SYNCHRONIZED,
                provider_ref="projection-matrix",
            ),
            ProviderCallStatus.SUCCEEDED,
            ProviderReconciliationStatus.SYNCHRONIZED,
        ),
        (
            ProviderProjectionResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
            ProviderCallStatus.UNAVAILABLE,
            ProviderReconciliationStatus.NOT_APPLICABLE,
        ),
        (
            ProviderProjectionResult(
                status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            ),
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            RuntimeError("secret project failure"),
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            None,
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            {"status": "synchronized"},
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            {
                "status": "synchronized",
                "provider_ref": "projection-metrics",
                "usage_units": True,
                "reported_cost_usd": "0.01",
            },
            ProviderCallStatus.SUCCEEDED,
            ProviderReconciliationStatus.SYNCHRONIZED,
        ),
    ),
)
def test_project_receipt_preserves_call_and_effective_reconciliation_truth(
    outcome: object,
    expected_call: ProviderCallStatus,
    expected_reconciliation: ProviderReconciliationStatus,
) -> None:
    """Catches project receipts reporting model parsing instead of domain truth."""
    receipts = _ReceiptSink()
    service = _service(
        provider=_RawOutcomeProvider(project=outcome),
        receipt_sink=receipts,
    )

    _confirm_one(service)

    receipt = receipts.items[-1]
    assert receipt.operation is ProviderOperation.PROJECT
    assert receipt.status is expected_call
    assert receipt.reconciliation_status is expected_reconciliation
    if isinstance(outcome, dict) and "usage_units" in outcome:
        assert receipt.usage_units is None
        assert receipt.reported_cost_usd is None


@pytest.mark.parametrize(
    ("usage", "cost", "expected_usage", "expected_cost"),
    (
        (7, "invalid-cost", 7, None),
        (True, Decimal("0.0042"), None, Decimal("0.0042")),
    ),
)
def test_invalid_optional_provider_metric_does_not_discard_valid_peer_metric(
    usage: object,
    cost: object,
    expected_usage: int | None,
    expected_cost: Decimal | None,
) -> None:
    """Catches one malformed optional metric discarding another valid metric."""
    receipts = _ReceiptSink()
    service = _service(
        provider=_RawOutcomeProvider(
            project={
                "status": "synchronized",
                "provider_ref": "projection-partial-metrics",
                "usage_units": usage,
                "reported_cost_usd": cost,
            }
        ),
        receipt_sink=receipts,
    )

    _confirm_one(service)

    receipt = receipts.items[-1]
    assert receipt.status is ProviderCallStatus.SUCCEEDED
    assert receipt.reconciliation_status is ProviderReconciliationStatus.SYNCHRONIZED
    assert receipt.usage_units == expected_usage
    assert receipt.reported_cost_usd == expected_cost


@pytest.mark.parametrize(
    ("outcome", "expected_call"),
    (
        (
            ProviderSearchResult(status=ProviderSearchStatus.ANSWERED, hits=()),
            ProviderCallStatus.SUCCEEDED,
        ),
        (
            ProviderSearchResult(status=ProviderSearchStatus.UNAVAILABLE),
            ProviderCallStatus.UNAVAILABLE,
        ),
        (RuntimeError("secret search failure"), ProviderCallStatus.FAILED),
        (None, ProviderCallStatus.FAILED),
        ({"unexpected": "shape"}, ProviderCallStatus.FAILED),
        (
            {
                "status": "answered",
                "hits": (),
                "usage_units": True,
                "reported_cost_usd": "0.01",
            },
            ProviderCallStatus.SUCCEEDED,
        ),
    ),
)
def test_search_receipt_preserves_answered_empty_and_fail_open_truth(
    outcome: object,
    expected_call: ProviderCallStatus,
) -> None:
    """Catches optional metrics changing answered-empty or fallback semantics."""
    store = InMemoryCanonicalMemoryStore()
    _confirm_one(_service(store=store))
    receipts = _ReceiptSink()
    service = _service(
        store=store,
        provider=_RawOutcomeProvider(search=outcome),
        receipt_sink=receipts,
    )

    service.retrieve(
        SUBJECT,
        "lower drawdown",
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )

    receipt = receipts.items[-1]
    assert receipt.operation is ProviderOperation.SEARCH
    assert receipt.status is expected_call
    assert receipt.reconciliation_status is ProviderReconciliationStatus.NOT_APPLICABLE
    if isinstance(outcome, dict) and "usage_units" in outcome:
        assert receipt.usage_units is None
        assert receipt.reported_cost_usd is None


@pytest.mark.parametrize(
    ("outcome", "expected_call", "expected_reconciliation"),
    (
        (
            ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED),
            ProviderCallStatus.SUCCEEDED,
            ProviderReconciliationStatus.SYNCHRONIZED,
        ),
        (
            ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
            ProviderCallStatus.UNAVAILABLE,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            ProviderCleanupResult(
                status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            ),
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            RuntimeError("secret delete failure"),
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            None,
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            {"unexpected": "shape"},
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            {
                "status": "synchronized",
                "usage_units": True,
                "reported_cost_usd": "0.01",
            },
            ProviderCallStatus.SUCCEEDED,
            ProviderReconciliationStatus.SYNCHRONIZED,
        ),
    ),
)
def test_delete_receipt_matches_effective_control_reconciliation(
    outcome: object,
    expected_call: ProviderCallStatus,
    expected_reconciliation: ProviderReconciliationStatus,
) -> None:
    """Catches known derivative cleanup receipts disagreeing with control truth."""
    store = InMemoryCanonicalMemoryStore()
    record_id = _confirm_one(_service(store=store))
    owner = RegisteredMemoryOwner(owner_id=SUBJECT.owner_id)
    store.set_provider_ref(owner, record_id, "delete-matrix-ref")
    receipts = _ReceiptSink()
    service = _service(
        store=store,
        provider=_RawOutcomeProvider(delete=outcome),
        receipt_sink=receipts,
    )

    result = service.delete(SUBJECT, record_id)

    receipt = receipts.items[-1]
    assert receipt.operation is ProviderOperation.DELETE
    assert receipt.status is expected_call
    assert receipt.reconciliation_status is expected_reconciliation
    assert result.provider_status is expected_reconciliation
    if isinstance(outcome, dict) and "usage_units" in outcome:
        assert receipt.usage_units is None
        assert receipt.reported_cost_usd is None


class _CleanupResolutionFailureStore(InMemoryCanonicalMemoryStore):
    def resolve_provider_cleanup_target(
        self,
        owner: RegisteredMemoryOwner,
        record_id: str,
        provider_ref: str,
    ) -> bool:
        del owner, record_id, provider_ref
        return False


def test_successful_delete_call_records_required_domain_reconciliation() -> None:
    """Catches truthful successful cleanup receipts being silently discarded."""
    store = _CleanupResolutionFailureStore()
    record_id = _confirm_one(_service(store=store))
    owner = RegisteredMemoryOwner(owner_id=SUBJECT.owner_id)
    store.set_provider_ref(owner, record_id, "delete-resolution-failure-ref")
    receipts = _ReceiptSink()
    service = _service(
        store=store,
        provider=_RawOutcomeProvider(
            delete=ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED)
        ),
        receipt_sink=receipts,
    )

    result = service.delete(SUBJECT, record_id)

    assert result.provider_status is ProviderReconciliationStatus.RECONCILIATION_REQUIRED
    assert len(receipts.items) == 1
    assert receipts.items[0].operation is ProviderOperation.DELETE
    assert receipts.items[0].status is ProviderCallStatus.SUCCEEDED
    assert (
        receipts.items[0].reconciliation_status
        is ProviderReconciliationStatus.RECONCILIATION_REQUIRED
    )


@pytest.mark.parametrize(
    (
        "prior_ref",
        "project_outcome",
        "delete_outcome",
        "expected_call",
        "expected_reconciliation",
    ),
    (
        (
            None,
            ProviderProjectionResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
            ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
            ProviderCallStatus.UNAVAILABLE,
            ProviderReconciliationStatus.NOT_APPLICABLE,
        ),
        (
            "prior-ref",
            ProviderProjectionResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
            ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
            ProviderCallStatus.UNAVAILABLE,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            "prior-ref",
            ProviderProjectionResult(
                status=ProviderReconciliationStatus.SYNCHRONIZED,
                provider_ref="updated-ref",
            ),
            ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED),
            ProviderCallStatus.SUCCEEDED,
            ProviderReconciliationStatus.SYNCHRONIZED,
        ),
        (
            "prior-ref",
            ProviderProjectionResult(
                status=ProviderReconciliationStatus.SYNCHRONIZED,
                provider_ref="updated-ref",
            ),
            ProviderCleanupResult(
                status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            ),
            ProviderCallStatus.SUCCEEDED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
    ),
)
def test_edit_project_receipt_matches_effective_control_reconciliation(
    prior_ref: str | None,
    project_outcome: ProviderProjectionResult,
    delete_outcome: ProviderCleanupResult,
    expected_call: ProviderCallStatus,
    expected_reconciliation: ProviderReconciliationStatus,
) -> None:
    """Catches projection receipts ignoring edit cleanup and pending-target truth."""
    store = InMemoryCanonicalMemoryStore()
    record_id = _confirm_one(_service(store=store))
    owner = RegisteredMemoryOwner(owner_id=SUBJECT.owner_id)
    if prior_ref is not None:
        store.set_provider_ref(owner, record_id, prior_ref)
    receipts = _ReceiptSink()
    service = _service(
        store=store,
        provider=_RawOutcomeProvider(
            project=project_outcome,
            delete=delete_outcome,
        ),
        receipt_sink=receipts,
    )

    result = service.edit(
        SUBJECT,
        record_id,
        MemoryEdit(value="Edited decision.", sensitivity=CLEAR),
    )

    project_receipt = next(
        item
        for item in reversed(receipts.items)
        if item.operation is ProviderOperation.PROJECT
    )
    assert project_receipt.status is expected_call
    assert project_receipt.reconciliation_status is expected_reconciliation
    assert result.provider_status is expected_reconciliation


@pytest.mark.parametrize(
    ("known_derivative", "outcome", "expected_call", "expected_reconciliation"),
    (
        (
            False,
            ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
            ProviderCallStatus.UNAVAILABLE,
            ProviderReconciliationStatus.NOT_APPLICABLE,
        ),
        (
            True,
            ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE),
            ProviderCallStatus.UNAVAILABLE,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            True,
            ProviderCleanupResult(status=ProviderReconciliationStatus.SYNCHRONIZED),
            ProviderCallStatus.SUCCEEDED,
            ProviderReconciliationStatus.SYNCHRONIZED,
        ),
        (
            True,
            ProviderCleanupResult(
                status=ProviderReconciliationStatus.RECONCILIATION_REQUIRED
            ),
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            True,
            RuntimeError("secret reset failure"),
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            True,
            None,
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            True,
            {"unexpected": "shape"},
            ProviderCallStatus.FAILED,
            ProviderReconciliationStatus.RECONCILIATION_REQUIRED,
        ),
        (
            True,
            {
                "status": "synchronized",
                "usage_units": True,
                "reported_cost_usd": "0.01",
            },
            ProviderCallStatus.SUCCEEDED,
            ProviderReconciliationStatus.SYNCHRONIZED,
        ),
    ),
)
def test_reset_receipt_maps_known_derivative_state_to_control_truth(
    known_derivative: bool,
    outcome: object,
    expected_call: ProviderCallStatus,
    expected_reconciliation: ProviderReconciliationStatus,
) -> None:
    """Catches owner reset receipts ignoring whether a derivative copy existed."""
    store = InMemoryCanonicalMemoryStore()
    record_id = _confirm_one(_service(store=store))
    owner = RegisteredMemoryOwner(owner_id=SUBJECT.owner_id)
    if known_derivative:
        store.set_provider_ref(owner, record_id, "reset-matrix-ref")
    receipts = _ReceiptSink()
    service = _service(
        store=store,
        provider=_RawOutcomeProvider(reset=outcome),
        receipt_sink=receipts,
    )

    result = service.reset(SUBJECT)

    if not known_derivative:
        assert receipts.items == []
        assert result.provider_status is ProviderReconciliationStatus.NOT_APPLICABLE
        return
    receipt = receipts.items[-1]
    assert receipt.operation is ProviderOperation.RESET
    assert receipt.status is expected_call
    assert receipt.reconciliation_status is expected_reconciliation
    assert result.provider_status is expected_reconciliation
    if isinstance(outcome, dict) and "usage_units" in outcome:
        assert receipt.usage_units is None
        assert receipt.reported_cost_usd is None


def _service(
    *,
    store: InMemoryCanonicalMemoryStore | None = None,
    provider: MemoryRetrievalProvider | None = None,
    event_sink: MemoryEventSink | None = None,
    receipt_sink: MemoryProviderReceiptSink | None = None,
    trace_sink: MemoryEvalTraceSink | None = None,
    correlation_id_factory: Any = lambda: "correlation-1",
) -> MemoryService:
    generated_ids = _ids()
    ticks = iter((10.0, 10.005) * 20)
    return MemoryService(
        store=store or InMemoryCanonicalMemoryStore(),
        provider=provider,
        config=MemoryServiceConfig(available=True),
        clock=lambda: NOW,
        id_factory=lambda: next(generated_ids),
        event_sink=event_sink,
        provider_receipt_sink=receipt_sink,
        eval_trace_sink=trace_sink,
        correlation_id_factory=correlation_id_factory,
        monotonic=lambda: next(ticks),
    )


def _confirm_one(service: MemoryService) -> str:
    draft, context = _draft()
    proposal = service.propose(SUBJECT, draft, context)
    assert proposal is not None
    confirmation = service.confirm(
        SUBJECT,
        proposal.candidate.id,
        sensitivity=CLEAR,
        context=context,
    )
    assert confirmation.created is True
    assert confirmation.record is not None
    return confirmation.record.id


@pytest.mark.parametrize(
    "forbidden_field",
    (
        "value",
        "label",
        "query",
        "transcript",
        "user_id",
        "owner_id",
        "source_id",
        "artifact_id",
        "provider_error",
        "balance",
        "holding",
        "credential",
        "broker",
        "metadata",
    ),
)
@pytest.mark.parametrize(
    ("model", "payload"),
    (
        (
            MemoryDomainEvent,
            {
                "correlation_id": "correlation-1",
                "operation": MemoryOperation.CONFIRM,
                "outcome": MemoryOutcome.CONFIRMED,
            },
        ),
        (
            ProviderCallReceipt,
            {
                "correlation_id": "correlation-1",
                "operation": ProviderOperation.PROJECT,
                "status": ProviderCallStatus.SUCCEEDED,
                "reconciliation_status": ProviderReconciliationStatus.SYNCHRONIZED,
            },
        ),
        (
            MemoryPolicyTrace,
            {
                "correlation_id": "correlation-1",
                "operation": MemoryOperation.PROPOSE,
                "outcome": PolicyOutcome.ALLOWED,
                "reason_codes": (PolicyReasonCode.ALLOWED,),
            },
        ),
    ),
)
def test_telemetry_models_reject_content_identity_and_arbitrary_metadata(
    model: type[Any],
    payload: dict[str, object],
    forbidden_field: str,
) -> None:
    """Catches a telemetry contract widening into raw or identifying memory data."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate({**payload, forbidden_field: "must-not-cross"})


@pytest.mark.parametrize("field", ("latency_ms", "usage_units"))
@pytest.mark.parametrize("bad_value", (True, 1.0, "1", -1))
def test_provider_receipt_requires_strict_nonnegative_integer_metrics(
    field: str,
    bad_value: object,
) -> None:
    """Catches coercive or negative usage metrics entering the cost seam."""
    with pytest.raises(ValidationError):
        ProviderCallReceipt.model_validate(
            {
                "correlation_id": "correlation-1",
                "operation": ProviderOperation.SEARCH,
                "status": ProviderCallStatus.SUCCEEDED,
                "reconciliation_status": ProviderReconciliationStatus.NOT_APPLICABLE,
                field: bad_value,
            }
        )


@pytest.mark.parametrize(
    "bad_cost",
    (
        True,
        1,
        1.0,
        "1.00",
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("Infinity"),
    ),
)
def test_provider_receipt_requires_strict_nonnegative_finite_decimal_cost(
    bad_cost: object,
) -> None:
    """Catches coerced, negative, or non-finite provider costs."""
    with pytest.raises(ValidationError):
        ProviderCallReceipt.model_validate(
            {
                "correlation_id": "correlation-1",
                "operation": ProviderOperation.SEARCH,
                "status": ProviderCallStatus.SUCCEEDED,
                "reconciliation_status": ProviderReconciliationStatus.NOT_APPLICABLE,
                "reported_cost_usd": bad_cost,
            }
        )


@pytest.mark.parametrize("bad_count", (True, 1.0, "1", -1))
def test_domain_event_requires_a_strict_nonnegative_safe_count(
    bad_count: object,
) -> None:
    """Catches unsafe count coercion at the product-event boundary."""
    with pytest.raises(ValidationError):
        MemoryDomainEvent.model_validate(
            {
                "correlation_id": "correlation-1",
                "operation": MemoryOperation.RETRIEVE,
                "outcome": MemoryOutcome.RETRIEVED,
                "safe_count": bad_count,
            }
        )


def test_lifecycle_provider_and_policy_sinks_are_separate_metadata_only_planes() -> None:
    """Catches content leakage or one catch-all analytics callback."""
    store = InMemoryCanonicalMemoryStore()
    events = _EventSink()
    receipts = _ReceiptSink()
    traces = _TraceSink()
    service = _service(
        store=store,
        provider=_MeasuredProvider(),
        event_sink=events,
        receipt_sink=receipts,
        trace_sink=traces,
    )

    record_id = _confirm_one(service)
    service.retrieve(
        SUBJECT,
        "lower drawdown",
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )
    deleted = service.delete(SUBJECT, record_id)
    assert deleted.provider_status is ProviderReconciliationStatus.SYNCHRONIZED
    _confirm_one(service)
    reset = service.reset(SUBJECT)
    assert reset.provider_status is ProviderReconciliationStatus.SYNCHRONIZED

    assert {item.operation for item in receipts.items} == {
        ProviderOperation.PROJECT,
        ProviderOperation.SEARCH,
        ProviderOperation.DELETE,
        ProviderOperation.RESET,
    }
    assert all(type(item) is MemoryDomainEvent for item in events.items)
    assert all(type(item) is ProviderCallReceipt for item in receipts.items)
    assert all(type(item) is MemoryPolicyTrace for item in traces.items)
    assert any(
        item.operation is MemoryOperation.CONFIRM
        and item.outcome is MemoryOutcome.CONFIRMED
        for item in events.items
    )
    assert any(
        item.operation is MemoryOperation.PROPOSE
        and item.outcome is PolicyOutcome.ALLOWED_OPT_IN
        and item.reason_codes == (PolicyReasonCode.OPT_IN_REQUIRED,)
        for item in traces.items
    )
    assert any(item.usage_units == 3 for item in receipts.items)
    assert any(item.reported_cost_usd == Decimal("0.0012") for item in receipts.items)

    forbidden = {
        "value",
        "label",
        "query",
        "transcript",
        "user_id",
        "owner_id",
        "source_id",
        "artifact_id",
        "provider_error",
        "balance",
        "holding",
        "credential",
        "broker",
        "metadata",
    }
    for item in (*events.items, *receipts.items, *traces.items):
        assert forbidden.isdisjoint(item.model_dump())


class _ExplodingSink:
    def emit(self, event: MemoryDomainEvent) -> None:
        del event
        raise RuntimeError("secret event sink detail")

    def record(self, item: object) -> None:
        del item
        raise RuntimeError("secret receipt or trace sink detail")


def test_sink_and_correlation_failures_do_not_change_canonical_behavior() -> None:
    """Catches telemetry outages becoming memory-domain outages."""
    store = InMemoryCanonicalMemoryStore()
    exploding = _ExplodingSink()
    service = _service(
        store=store,
        provider=_MeasuredProvider(),
        event_sink=exploding,  # type: ignore[arg-type]
        receipt_sink=exploding,  # type: ignore[arg-type]
        trace_sink=exploding,  # type: ignore[arg-type]
    )
    record_id = _confirm_one(service)
    assert service.delete(SUBJECT, record_id).provider_status is (
        ProviderReconciliationStatus.SYNCHRONIZED
    )

    def explode_correlation() -> str:
        raise RuntimeError("secret correlation detail")

    service_without_correlation = _service(
        provider=_MeasuredProvider(),
        event_sink=exploding,  # type: ignore[arg-type]
        receipt_sink=exploding,  # type: ignore[arg-type]
        trace_sink=exploding,  # type: ignore[arg-type]
        correlation_id_factory=explode_correlation,
    )
    assert _confirm_one(service_without_correlation)


class _ExplodingSearchProvider(_MeasuredProvider):
    def search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult:
        del owner, query, limit
        raise RuntimeError("secret provider diagnostic")


def test_provider_exception_receipt_is_typed_and_cannot_expose_raw_error() -> None:
    """Catches provider exception text crossing the usage/cost boundary."""
    store = InMemoryCanonicalMemoryStore()
    setup = _service(store=store)
    _confirm_one(setup)
    receipts = _ReceiptSink()
    service = _service(
        store=store,
        provider=_ExplodingSearchProvider(),
        receipt_sink=receipts,
    )

    service.retrieve(
        SUBJECT,
        "lower drawdown",
        MemoryUsePurpose.REVISIT_SAVED_DECISION,
    )

    failed = receipts.items[-1]
    assert failed.operation is ProviderOperation.SEARCH
    assert failed.status is ProviderCallStatus.FAILED
    assert "secret provider diagnostic" not in repr(failed)
