from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from argus.domain.ingestion.contract import (
    AccountHint,
    BalanceScope,
    Direction,
    EvidenceKind,
    ImportCandidate,
    KindHint,
    UncertainField,
)


class DocumentExtractionError(Exception):
    def __init__(self, code: str, retryable: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
        self.metadata: dict[str, object] = {}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExtractedObservation(_Frozen):
    page: int = Field(ge=1, le=8)
    row: int = Field(ge=1, le=300)
    evidence: EvidenceKind
    status: Literal["pending", "posted", "unknown"] = "unknown"
    account: AccountHint = AccountHint()
    occurred_on: date | None = None
    posted_on: date | None = None
    amount: str | None = Field(default=None, pattern=r"^[0-9]{1,18}(?:\.[0-9]{1,8})?$")
    currency: str | None = None
    direction: Direction = "unknown"
    kind_hint: KindHint = "unknown"
    merchant: str | None = None
    description: str | None = None
    balance_scope: BalanceScope | None = None
    due_on: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    uncertain: frozenset[UncertainField] = frozenset()


class ExtractionResult(_Frozen):
    complete: bool = Field(strict=True)
    readable: bool = Field(strict=True)
    pages_read: tuple[int, ...] = Field(max_length=8)
    observations: tuple[ExtractedObservation, ...] = Field(max_length=300)


class ExtractionBatch(_Frozen):
    candidates: tuple[ImportCandidate, ...]
    metadata: dict[str, object] = Field(default_factory=dict)
