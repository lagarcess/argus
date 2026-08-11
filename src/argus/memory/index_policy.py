"""Deterministic gate deciding what a derivative index may ever see.

Second barrier behind the sensitivity assessor and `MemoryPolicy`, decided from
the record itself so a corrupted store cannot feed an index. Reads typed
structure only, never natural language.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from argus.memory.contracts import MemoryCategory, MemoryRecord
from argus.memory.policy import SAFE_MEMORY_CATEGORIES
from argus.memory.subject import RegisteredMemoryOwner

# What cannot be stored can never be indexed.
INDEXABLE_CATEGORIES: frozenset[MemoryCategory] = SAFE_MEMORY_CATEGORIES


class IndexRefusal(str, Enum):
    """Why a record may not enter a derivative index."""

    UNCONFIRMED = "unconfirmed"
    OWNER_MISMATCH = "owner_mismatch"
    CATEGORY_NOT_INDEXABLE = "category_not_indexable"
    EMPTY_CONTENT = "empty_content"


class IndexDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    allowed: bool
    refusal: IndexRefusal | None = None


_ALLOWED = IndexDecision(allowed=True)


def index_eligibility(
    owner: RegisteredMemoryOwner,
    record: MemoryRecord,
) -> IndexDecision:
    """Decide whether one canonical record may be projected into an index."""

    if record.owner_id != owner.owner_id:
        return IndexDecision(allowed=False, refusal=IndexRefusal.OWNER_MISMATCH)
    if not _is_confirmed(record):
        return IndexDecision(allowed=False, refusal=IndexRefusal.UNCONFIRMED)
    if record.category not in INDEXABLE_CATEGORIES:
        return IndexDecision(
            allowed=False,
            refusal=IndexRefusal.CATEGORY_NOT_INDEXABLE,
        )
    if not index_text(record):
        return IndexDecision(allowed=False, refusal=IndexRefusal.EMPTY_CONTENT)
    return _ALLOWED


def _is_confirmed(record: MemoryRecord) -> bool:
    """A record is confirmed only when its own consent receipt covers it."""

    receipt = record.consent_receipt
    return (
        receipt.owner_id == record.owner_id
        and receipt.candidate_id == record.candidate_id
        and record.category in receipt.effective_scope
    )


def index_text(record: MemoryRecord) -> str:
    """The exact confirmed text a derivative index is allowed to vectorize."""

    label = record.label.strip()
    value = record.value.strip()
    if not value:
        return ""
    return f"{label}\n{value}" if label else value
