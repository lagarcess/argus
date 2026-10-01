"""Reconciliation storage: one per-person transaction, two backends.

All reconciliation logic runs inside ``ImportStore.transaction(user_id)`` so
submit, review and acceptance for one person serialize, while different
people never wait on each other. The in-memory twin restores its snapshot on
error; Postgres uses a transaction-scoped advisory lock.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import date
from typing import Protocol

from argus.domain.ingestion.reconcile.model import (
    AccountLink,
    EventNotFound,
    ImportEvent,
    Observation,
)


class ImportTx(Protocol):
    def observation(self, connection_id: str, external_id: str) -> Observation | None: ...
    def observations(self, event_id: str) -> list[Observation]: ...
    def connection_observations(self, connection_id: str) -> list[Observation]: ...
    def event(self, event_id: str) -> ImportEvent: ...
    def nearby(self, start: date, end: date) -> list[ImportEvent]: ...
    def events(self, states: tuple[str, ...]) -> list[ImportEvent]: ...
    def activity_links(self) -> dict[str, str]: ...
    def links(self) -> dict[tuple[str, str], str]: ...
    def put_event(self, event: ImportEvent) -> None: ...
    def delete_event(self, event_id: str) -> None: ...
    def put_observation(self, observation: Observation) -> None: ...
    def delete_observation(self, observation_id: str) -> None: ...
    def put_link(self, link: AccountLink) -> None: ...
    def delete_links(self, connection_id: str) -> None: ...
    def account_shared(self, account_id: str) -> bool: ...


class ImportStore(Protocol):
    def transaction(self, user_id: str) -> AbstractContextManager[ImportTx]: ...


class _MemoryTx:
    def __init__(self, store: InMemoryImportStore, user_id: str) -> None:
        self._s = store
        self._user = user_id

    def observation(self, connection_id: str, external_id: str) -> Observation | None:
        return self._s.observations.get((self._user, connection_id, external_id))

    def observations(self, event_id: str) -> list[Observation]:
        return sorted(
            (o for o in self._s.observations.values() if o.event_id == event_id),
            key=lambda o: (o.first_seen_at, o.id),
        )

    def connection_observations(self, connection_id: str) -> list[Observation]:
        return [
            o
            for (user, conn, _), o in self._s.observations.items()
            if user == self._user and conn == connection_id
        ]

    def event(self, event_id: str) -> ImportEvent:
        event = self._s.events.get(event_id)
        if event is None or event.user_id != self._user:
            raise EventNotFound()
        return event

    def nearby(self, start: date, end: date) -> list[ImportEvent]:
        return [
            e
            for e in self._s.events.values()
            if e.user_id == self._user
            and e.anchor_on is not None
            and start <= e.anchor_on <= end
        ]

    def events(self, states: tuple[str, ...]) -> list[ImportEvent]:
        found = [
            e
            for e in self._s.events.values()
            if e.user_id == self._user and e.state in states
        ]
        return sorted(found, key=lambda e: (e.created_at, e.id))

    def activity_links(self) -> dict[str, str]:
        """Recorded activity id to the import event that points at it."""

        return {
            e.activity_id: e.id
            for e in self._s.events.values()
            if e.user_id == self._user and e.activity_id
        }

    def links(self) -> dict[tuple[str, str], str]:
        return {
            (link.connection_id, link.account_key): link.account_id
            for (user, _, _), link in self._s.links.items()
            if user == self._user
        }

    def put_event(self, event: ImportEvent) -> None:
        self._s.events[event.id] = event

    def delete_event(self, event_id: str) -> None:
        self._s.events.pop(event_id, None)

    def put_observation(self, observation: Observation) -> None:
        key = (self._user, observation.connection_id, observation.external_id)
        self._s.observations[key] = observation

    def delete_observation(self, observation_id: str) -> None:
        for key, o in list(self._s.observations.items()):
            if o.id == observation_id:
                del self._s.observations[key]

    def put_link(self, link: AccountLink) -> None:
        self._s.links[(self._user, link.connection_id, link.account_key)] = link

    def delete_links(self, connection_id: str) -> None:
        for key in [
            k for k in self._s.links if k[0] == self._user and k[1] == connection_id
        ]:
            del self._s.links[key]

    def account_shared(self, account_id: str) -> bool:
        # Household sharing exists only in durable mode.
        return False


class InMemoryImportStore:
    def __init__(self) -> None:
        self.events: dict[str, ImportEvent] = {}
        self.observations: dict[tuple[str, str, str], Observation] = {}
        self.links: dict[tuple[str, str, str], AccountLink] = {}
        self._lock = threading.RLock()

    @contextmanager
    def transaction(self, user_id: str) -> Iterator[ImportTx]:
        with self._lock:
            snapshot = (dict(self.events), dict(self.observations), dict(self.links))
            try:
                yield _MemoryTx(self, user_id)
            except BaseException:
                self.events, self.observations, self.links = snapshot
                raise
