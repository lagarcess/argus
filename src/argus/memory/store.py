"""Canonical memory storage for the walking skeleton.

Every accessor is owner-scoped by ``user_id``; cross-user reads are
structurally impossible through this API. The in-memory implementation is the
skeleton stand-in for the future Supabase-owned tables (program slice S4).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from argus.memory.contracts import MemoryCandidate, MemoryCategory, MemoryRecord
from argus.memory.policy import UserMemorySettings


class CanonicalMemoryStore(Protocol):
    def get_settings(self, user_id: str) -> UserMemorySettings: ...

    def set_enabled(self, user_id: str, enabled: bool) -> UserMemorySettings: ...

    def add_candidate(self, candidate: MemoryCandidate) -> None: ...

    def get_candidate(
        self, user_id: str, candidate_id: str
    ) -> MemoryCandidate | None: ...

    def list_candidates(self, user_id: str) -> list[MemoryCandidate]: ...

    def discard_candidate(self, user_id: str, candidate_id: str) -> None: ...

    def last_prompted_at(
        self, user_id: str, category: MemoryCategory
    ) -> datetime | None: ...

    def mark_prompted(
        self, user_id: str, category: MemoryCategory, at: datetime
    ) -> None: ...

    def add_record(self, record: MemoryRecord) -> None: ...

    def get_record(self, user_id: str, record_id: str) -> MemoryRecord | None: ...

    def list_records(self, user_id: str) -> list[MemoryRecord]: ...

    def replace_record(self, record: MemoryRecord) -> None: ...

    def delete_record(self, user_id: str, record_id: str) -> bool: ...

    def delete_all_records(self, user_id: str) -> int: ...


class InMemoryCanonicalMemoryStore:
    """Deterministic, owner-scoped dict-backed store."""

    def __init__(self) -> None:
        self._settings: dict[str, UserMemorySettings] = {}
        self._candidates: dict[str, dict[str, MemoryCandidate]] = {}
        self._records: dict[str, dict[str, MemoryRecord]] = {}
        self._prompted: dict[tuple[str, MemoryCategory], datetime] = {}

    def get_settings(self, user_id: str) -> UserMemorySettings:
        return self._settings.get(user_id, UserMemorySettings())

    def set_enabled(self, user_id: str, enabled: bool) -> UserMemorySettings:
        settings = UserMemorySettings(enabled=enabled)
        self._settings[user_id] = settings
        return settings

    def add_candidate(self, candidate: MemoryCandidate) -> None:
        self._candidates.setdefault(candidate.user_id, {})[candidate.id] = candidate

    def get_candidate(self, user_id: str, candidate_id: str) -> MemoryCandidate | None:
        return self._candidates.get(user_id, {}).get(candidate_id)

    def list_candidates(self, user_id: str) -> list[MemoryCandidate]:
        return list(self._candidates.get(user_id, {}).values())

    def discard_candidate(self, user_id: str, candidate_id: str) -> None:
        self._candidates.get(user_id, {}).pop(candidate_id, None)

    def last_prompted_at(self, user_id: str, category: MemoryCategory) -> datetime | None:
        return self._prompted.get((user_id, category))

    def mark_prompted(self, user_id: str, category: MemoryCategory, at: datetime) -> None:
        self._prompted[(user_id, category)] = at

    def add_record(self, record: MemoryRecord) -> None:
        self._records.setdefault(record.user_id, {})[record.id] = record

    def get_record(self, user_id: str, record_id: str) -> MemoryRecord | None:
        return self._records.get(user_id, {}).get(record_id)

    def list_records(self, user_id: str) -> list[MemoryRecord]:
        return list(self._records.get(user_id, {}).values())

    def replace_record(self, record: MemoryRecord) -> None:
        rows = self._records.get(record.user_id, {})
        if record.id not in rows:
            raise KeyError(record.id)
        rows[record.id] = record

    def delete_record(self, user_id: str, record_id: str) -> bool:
        return self._records.get(user_id, {}).pop(record_id, None) is not None

    def delete_all_records(self, user_id: str) -> int:
        removed = len(self._records.get(user_id, {}))
        self._records[user_id] = {}
        self._candidates[user_id] = {}
        return removed
