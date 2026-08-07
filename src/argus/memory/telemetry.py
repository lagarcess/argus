"""Privacy-safe ports for memory lifecycle, provider, and evaluation metadata."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from argus.memory.contracts import MemoryCategory, ProviderReconciliationStatus
from argus.memory.policy import PolicyOutcome


class MemoryOperation(str, Enum):
    PROPOSE_SAVED_DECISION = "propose_saved_decision"
    PROPOSE = "propose"
    ENABLE = "enable"
    CONFIRM = "confirm"
    DECLINE = "decline"
    INSPECT = "inspect"
    RETRIEVE = "retrieve"
    EXPLAIN = "explain"
    EDIT = "edit"
    DELETE = "delete"
    DISABLE = "disable"
    RESET = "reset"


class MemoryOutcome(str, Enum):
    CANDIDATE_CREATED = "candidate_created"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    ENABLED = "enabled"
    INSPECTED = "inspected"
    RETRIEVED = "retrieved"
    EXPLAINED = "explained"
    EDITED = "edited"
    DELETED = "deleted"
    DISABLED = "disabled"
    RESET = "reset"
    SUPPRESSED = "suppressed"
    NO_CHANGE = "no_change"
    UNAVAILABLE = "unavailable"


class ProviderOperation(str, Enum):
    PROJECT = "project"
    SEARCH = "search"
    DELETE = "delete"
    RESET = "reset"


class ProviderCallStatus(str, Enum):
    SUCCEEDED = "succeeded"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class PolicyReasonCode(str, Enum):
    ALLOWED = "allowed"
    OPT_IN_REQUIRED = "opt_in_required"
    CATEGORY_DENIED = "category_denied"
    SCOPE_DENIED = "scope_denied"
    ASSISTED_FIRST_OPT_IN_DENIED = "assisted_first_opt_in_denied"
    CONTEXT_RESTRICTED = "context_restricted"
    SENSITIVITY_RESTRICTED = "sensitivity_restricted"
    COOLDOWN_ACTIVE = "cooldown_active"
    RECENTLY_DECLINED = "recently_declined"


POLICY_REASON_CODES: dict[PolicyOutcome, PolicyReasonCode] = {
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

VALID_MEMORY_EVENT_PAIRS = frozenset(
    {
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
)

VALID_PROVIDER_RECEIPT_TRIPLES = frozenset(
    {
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
)

VALID_POLICY_OPERATIONS = frozenset(
    {
        MemoryOperation.PROPOSE_SAVED_DECISION,
        MemoryOperation.PROPOSE,
        MemoryOperation.CONFIRM,
    }
)


class MemoryDomainEvent(BaseModel):
    """Metadata-only product lifecycle event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: str = Field(min_length=1, max_length=128)
    operation: MemoryOperation
    outcome: MemoryOutcome
    category: MemoryCategory | None = None
    safe_count: int | None = Field(default=None, ge=0, le=10_000, strict=True)

    @model_validator(mode="after")
    def _validate_operation_outcome(self) -> "MemoryDomainEvent":
        if (self.operation, self.outcome) not in VALID_MEMORY_EVENT_PAIRS:
            raise ValueError("memory event operation and outcome are incompatible")
        return self


class ProviderCallReceipt(BaseModel):
    """Metadata-only provider usage and reconciliation receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: str = Field(min_length=1, max_length=128)
    operation: ProviderOperation
    status: ProviderCallStatus
    latency_ms: int | None = Field(default=None, ge=0, strict=True)
    usage_units: int | None = Field(default=None, ge=0, strict=True)
    reported_cost_usd: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        allow_inf_nan=False,
        strict=True,
    )
    reconciliation_status: ProviderReconciliationStatus

    @model_validator(mode="after")
    def _validate_operation_status(self) -> "ProviderCallReceipt":
        triple = (self.operation, self.status, self.reconciliation_status)
        if triple not in VALID_PROVIDER_RECEIPT_TRIPLES:
            raise ValueError(
                "provider operation, call status, and reconciliation are incompatible"
            )
        return self


class MemoryPolicyTrace(BaseModel):
    """Metadata-only deterministic policy/evaluation trace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: str = Field(min_length=1, max_length=128)
    operation: MemoryOperation
    outcome: PolicyOutcome
    reason_codes: tuple[PolicyReasonCode, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_terminal_reason(self) -> "MemoryPolicyTrace":
        expected_reason = POLICY_REASON_CODES[self.outcome]
        if self.operation not in VALID_POLICY_OPERATIONS:
            raise ValueError("memory operation cannot emit a policy trace")
        if self.reason_codes != (expected_reason,):
            raise ValueError("policy outcome requires exactly its terminal reason code")
        return self


class MemoryEventSink(Protocol):
    def emit(self, event: MemoryDomainEvent) -> None: ...


class MemoryProviderReceiptSink(Protocol):
    def record(self, receipt: ProviderCallReceipt) -> None: ...


class MemoryEvalTraceSink(Protocol):
    def record(self, trace: MemoryPolicyTrace) -> None: ...


def reason_codes_for(outcome: PolicyOutcome) -> tuple[PolicyReasonCode, ...]:
    return (POLICY_REASON_CODES[outcome],)
