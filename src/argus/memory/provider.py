"""Argus-owned retrieval-provider boundary (Mem0-shaped).

Providers hold derivative projections only; canonical truth stays in the
store. Every provider call is optional: callers treat failures as fail-open.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from argus.memory.contracts import MemoryRecord


class ProviderHit(BaseModel):
    """A ranked provider match pointing back at a canonical record."""

    record_id: str
    score: float
    matched_terms: list[str]


class MemoryRetrievalProvider(Protocol):
    def project(self, record: MemoryRecord) -> str | None:
        """Index a confirmed record; ``None`` means it was not indexed."""
        ...

    def search(self, user_id: str, query: str, limit: int) -> list[ProviderHit] | None:
        """Ranked matches; ``None`` means unavailable (callers fall back to
        bounded canonical matching), ``[]`` means answered with no matches."""
        ...

    def delete(self, user_id: str, provider_ref: str) -> None: ...

    def reset(self, user_id: str) -> None: ...


class NoOpMemoryProvider:
    """Absent-provider stand-in: indexes nothing, abstains from answering."""

    def project(self, record: MemoryRecord) -> str | None:
        return None

    def search(self, user_id: str, query: str, limit: int) -> list[ProviderHit] | None:
        return None

    def delete(self, user_id: str, provider_ref: str) -> None:
        return None

    def reset(self, user_id: str) -> None:
        return None


def _tokens(text: str) -> set[str]:
    return {token for token in text.lower().split() if len(token) > 2}


class DeterministicFakeMemoryProvider:
    """Offline stand-in for Mem0: token-overlap ranking, stable ordering."""

    def __init__(self) -> None:
        self._indexed: dict[str, dict[str, MemoryRecord]] = {}

    def project(self, record: MemoryRecord) -> str:
        provider_ref = f"fake-{record.id}"
        self._indexed.setdefault(record.user_id, {})[provider_ref] = record
        return provider_ref

    def search(self, user_id: str, query: str, limit: int) -> list[ProviderHit]:
        query_tokens = _tokens(query)
        hits: list[ProviderHit] = []
        for record in self._indexed.get(user_id, {}).values():
            matched = sorted(
                query_tokens & (_tokens(record.value) | _tokens(record.label))
            )
            if matched:
                hits.append(
                    ProviderHit(
                        record_id=record.id,
                        score=float(len(matched)),
                        matched_terms=matched,
                    )
                )
        hits.sort(key=lambda hit: (-hit.score, hit.record_id))
        return hits[:limit]

    def delete(self, user_id: str, provider_ref: str) -> None:
        self._indexed.get(user_id, {}).pop(provider_ref, None)

    def reset(self, user_id: str) -> None:
        self._indexed[user_id] = {}

    def indexed_refs(self, user_id: str) -> set[str]:
        """Test hook: which provider refs exist for a user."""
        return set(self._indexed.get(user_id, {}))
