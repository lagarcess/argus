"""Pure Guest-to-account personalization-memory conversion contract."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from argus.memory.subject import MemoryAccountKind, MemorySubject


class MemoryConversionMode(str, Enum):
    SAME_IDENTITY_LINK = "same_identity_link"
    EXISTING_ACCOUNT_HANDOFF = "existing_account_handoff"


class MemoryStateDigest(BaseModel):
    """Precomputed memory-state counts supplied by a future conversion adapter."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    settings_count: int = Field(default=0, ge=0, strict=True)
    candidate_count: int = Field(default=0, ge=0, strict=True)
    consent_receipt_count: int = Field(default=0, ge=0, strict=True)
    record_count: int = Field(default=0, ge=0, strict=True)
    provenance_count: int = Field(default=0, ge=0, strict=True)
    prompt_history_count: int = Field(default=0, ge=0, strict=True)
    pending_work_count: int = Field(default=0, ge=0, strict=True)
    reconciliation_work_count: int = Field(default=0, ge=0, strict=True)
    provider_projection_count: int = Field(default=0, ge=0, strict=True)

    def is_zero(self) -> bool:
        return not any(self.model_dump().values())


class MemoryConversionPlan(BaseModel):
    """Fail-closed plan: Guest memory is never transferred, mined, or enabled."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    transfer_memory: Literal[False] = False
    mine_guest_history: Literal[False] = False
    initialize_memory_enabled: Literal[False] = False
    preserve_destination_memory: bool


def plan_guest_conversion(
    *,
    mode: MemoryConversionMode,
    source_subject: MemorySubject,
    source_state: MemoryStateDigest,
    destination_subject: MemorySubject,
    destination_state: MemoryStateDigest,
) -> MemoryConversionPlan:
    """Validate conversion zero-state without reading stores, Auth, or history."""

    if not isinstance(mode, MemoryConversionMode):
        raise TypeError("mode must be a MemoryConversionMode")
    if source_subject.kind is not MemoryAccountKind.GUEST:
        raise ValueError("conversion source must be Guest")
    if destination_subject.kind is not MemoryAccountKind.REGISTERED:
        raise ValueError("conversion destination must be registered")
    if not source_state.is_zero():
        raise ValueError("Guest memory state must be zero before conversion")

    same_identity = source_subject.owner_id == destination_subject.owner_id
    if mode is MemoryConversionMode.SAME_IDENTITY_LINK:
        if not same_identity:
            raise ValueError("same-identity link requires matching identity")
        if not destination_state.is_zero():
            raise ValueError(
                "same-identity initial destination memory state must be zero"
            )
        return MemoryConversionPlan(preserve_destination_memory=False)

    if same_identity:
        raise ValueError("existing-account handoff requires a different identity")
    return MemoryConversionPlan(preserve_destination_memory=True)
