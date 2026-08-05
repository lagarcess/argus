"""Account-kind gate for personalization-memory operations."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MemoryAccountKind(str, Enum):
    REGISTERED = "registered"
    GUEST = "guest"


class MemorySubject(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_id: str = Field(min_length=1)
    kind: MemoryAccountKind


class RegisteredMemoryOwner(BaseModel):
    """Owner token available only after the registered-account gate passes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    owner_id: str = Field(min_length=1)


class PersonalizationMemoryUnavailable(Exception):
    """Personalization memory is unavailable for this subject or environment."""


def require_registered(subject: MemorySubject) -> RegisteredMemoryOwner:
    if subject.kind is not MemoryAccountKind.REGISTERED:
        raise PersonalizationMemoryUnavailable(
            "Personalization memory requires a registered account."
        )
    return RegisteredMemoryOwner(owner_id=subject.owner_id)
