"""Provider-neutral derivative projection and ranked-id boundary."""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from argus.memory.contracts import MemoryRecord, ProviderReconciliationStatus
from argus.memory.subject import RegisteredMemoryOwner


class ProviderSearchStatus(str, Enum):
    ANSWERED = "answered"
    UNAVAILABLE = "unavailable"


class ProviderHit(BaseModel):
    """A provider score attached only to a canonical record id."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1)
    score: float = Field(ge=0, allow_inf_nan=False)


class ProviderSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProviderSearchStatus
    hits: tuple[ProviderHit, ...] = ()

    @model_validator(mode="after")
    def _validate_status_shape(self) -> "ProviderSearchResult":
        if self.status is ProviderSearchStatus.UNAVAILABLE and self.hits:
            raise ValueError("unavailable search cannot include hits")
        return self


class ProviderProjectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProviderReconciliationStatus
    provider_ref: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_status_shape(self) -> "ProviderProjectionResult":
        if (self.status is ProviderReconciliationStatus.SYNCHRONIZED) != (
            self.provider_ref is not None
        ):
            raise ValueError("synchronized projection requires exactly one provider ref")
        return self


class ProviderCleanupResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ProviderReconciliationStatus


class MemoryRetrievalProvider(Protocol):
    """Optional derivative system; it never owns memory truth."""

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult: ...

    def search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult: ...

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult: ...

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult: ...


class NoOpMemoryProvider:
    """Absent provider: projection is skipped and retrieval may fall back."""

    def project(
        self,
        owner: RegisteredMemoryOwner,
        record: MemoryRecord,
    ) -> ProviderProjectionResult:
        del owner, record
        return ProviderProjectionResult(
            status=ProviderReconciliationStatus.NOT_APPLICABLE
        )

    def search(
        self,
        owner: RegisteredMemoryOwner,
        query: str,
        limit: int,
    ) -> ProviderSearchResult:
        del owner, query, limit
        return ProviderSearchResult(status=ProviderSearchStatus.UNAVAILABLE)

    def delete(
        self,
        owner: RegisteredMemoryOwner,
        provider_ref: str,
    ) -> ProviderCleanupResult:
        del owner, provider_ref
        return ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE)

    def reset(self, owner: RegisteredMemoryOwner) -> ProviderCleanupResult:
        del owner
        return ProviderCleanupResult(status=ProviderReconciliationStatus.NOT_APPLICABLE)
