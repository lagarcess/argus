"""Connected-source state shared by every connector.

One row per person-authorized connection (a Plaid Item, a Gmail mailbox, a
Shortcuts device). It owns what the MVEE requires every connection to show:
status, last successful refresh, and an actionable failure. It also owns the
sync cursor and a short lease so two webhook-triggered syncs of the same
connection never interleave cursor advances.

A failed sync only records the failure: it never clears ``last_success_at``
or the cursor, so existing evidence and its freshness stay truthful.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Literal, Protocol

from argus.domain.ingestion.contract import SourceKind

ConnectionStatus = Literal["active", "needs_reauth", "error", "disconnected"]
LIVE: frozenset[str] = frozenset({"active", "needs_reauth", "error"})
DEFAULT_LEASE = timedelta(minutes=5)


class ConnectionNotFound(LookupError):
    pass


class DuplicateConnection(RuntimeError):
    def __init__(self, existing_id: str) -> None:
        super().__init__("a live connection for this source reference exists")
        self.existing_id = existing_id


@dataclass(frozen=True)
class SourceConnection:
    id: str
    user_id: str
    source: SourceKind
    status: ConnectionStatus
    # Non-secret display label: institution name, masked mailbox, device name.
    label: str | None
    # Provider handle: Plaid item_id, Gmail address digest, Shortcuts device id.
    external_ref: str
    cursor: str | None
    secret: bytes | None
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    last_error_code: str | None
    # A warning that outlives successful syncs (Plaid consent expiring soon).
    # Only re-authorization or disconnect clears it; sync status does not.
    attention_code: str | None
    attention_at: datetime | None
    lease_holder: str | None
    lease_until: datetime | None
    created_at: datetime
    updated_at: datetime
    disconnected_at: datetime | None
    version: int


class ConnectionRepository(Protocol):
    def create(
        self,
        *,
        user_id: str,
        source: SourceKind,
        external_ref: str,
        label: str | None,
        now: datetime,
        secret: bytes | None = None,
        connection_id: str | None = None,
    ) -> SourceConnection: ...

    def get(self, *, user_id: str, connection_id: str) -> SourceConnection: ...

    def list(self, *, user_id: str) -> list[SourceConnection]: ...

    def find_live(
        self, *, source: SourceKind, external_ref: str
    ) -> list[SourceConnection]: ...

    def set_secret(
        self,
        *,
        connection_id: str,
        secret: bytes,
        status: ConnectionStatus,
        now: datetime,
    ) -> SourceConnection: ...

    def lease(
        self,
        *,
        connection_id: str,
        holder: str,
        now: datetime,
        ttl: timedelta = DEFAULT_LEASE,
    ) -> bool: ...

    def release(self, *, connection_id: str, holder: str) -> None: ...

    def record_success(
        self,
        *,
        connection_id: str,
        holder: str,
        expected_cursor: str | None,
        cursor: str | None,
        now: datetime,
    ) -> bool: ...

    def record_failure(
        self, *, connection_id: str, code: str, status: ConnectionStatus, now: datetime
    ) -> SourceConnection: ...

    def flag_attention(
        self, *, connection_id: str, code: str, now: datetime
    ) -> SourceConnection: ...

    def disconnect(
        self, *, user_id: str, connection_id: str, now: datetime
    ) -> SourceConnection: ...


class InMemoryConnectionRepository:
    """Deterministic twin of the Postgres repository for hermetic tests."""

    def __init__(self) -> None:
        self._rows: dict[str, SourceConnection] = {}
        self._lock = threading.Lock()

    def create(
        self,
        *,
        user_id: str,
        source: SourceKind,
        external_ref: str,
        label: str | None,
        now: datetime,
        secret: bytes | None = None,
        connection_id: str | None = None,
    ) -> SourceConnection:
        with self._lock:
            for row in self._rows.values():
                if (
                    row.user_id == user_id
                    and row.source == source
                    and row.external_ref == external_ref
                    and row.status in LIVE
                ):
                    raise DuplicateConnection(row.id)
            row = SourceConnection(
                id=connection_id or str(uuid.uuid4()),
                user_id=user_id,
                source=source,
                status="active",
                label=label,
                external_ref=external_ref,
                cursor=None,
                secret=secret,
                last_success_at=None,
                last_attempt_at=None,
                last_error_code=None,
                attention_code=None,
                attention_at=None,
                lease_holder=None,
                lease_until=None,
                created_at=now,
                updated_at=now,
                disconnected_at=None,
                version=1,
            )
            self._rows[row.id] = row
            return row

    def get(self, *, user_id: str, connection_id: str) -> SourceConnection:
        row = self._rows.get(connection_id)
        if row is None or row.user_id != user_id:
            raise ConnectionNotFound()
        return row

    def list(self, *, user_id: str) -> list[SourceConnection]:
        rows = [r for r in self._rows.values() if r.user_id == user_id]
        return sorted(rows, key=lambda r: (r.created_at, r.id))

    def find_live(
        self, *, source: SourceKind, external_ref: str
    ) -> list[SourceConnection]:
        return [
            r
            for r in self._rows.values()
            if r.source == source and r.external_ref == external_ref and r.status in LIVE
        ]

    def set_secret(
        self,
        *,
        connection_id: str,
        secret: bytes,
        status: ConnectionStatus,
        now: datetime,
    ) -> SourceConnection:
        with self._lock:
            row = self._live(connection_id)
            return self._put(
                replace(
                    row,
                    secret=secret,
                    status=status,
                    last_error_code=None,
                    attention_code=None,
                    attention_at=None,
                ),
                now,
            )

    def lease(
        self,
        *,
        connection_id: str,
        holder: str,
        now: datetime,
        ttl: timedelta = DEFAULT_LEASE,
    ) -> bool:
        with self._lock:
            row = self._rows.get(connection_id)
            if row is None or row.status not in LIVE:
                return False
            held = row.lease_until is not None and row.lease_until > now
            if held and row.lease_holder != holder:
                return False
            self._rows[connection_id] = replace(
                row, lease_holder=holder, lease_until=now + ttl, last_attempt_at=now
            )
            return True

    def release(self, *, connection_id: str, holder: str) -> None:
        with self._lock:
            row = self._rows.get(connection_id)
            if row is not None and row.lease_holder == holder:
                self._rows[connection_id] = replace(
                    row, lease_holder=None, lease_until=None
                )

    def record_success(
        self,
        *,
        connection_id: str,
        holder: str,
        expected_cursor: str | None,
        cursor: str | None,
        now: datetime,
    ) -> bool:
        with self._lock:
            row = self._rows.get(connection_id)
            if (
                row is None
                or row.status not in LIVE
                or row.lease_holder != holder
                or row.cursor != expected_cursor
            ):
                return False
            self._put(
                replace(
                    row,
                    cursor=cursor,
                    status="active",
                    last_success_at=now,
                    last_attempt_at=now,
                    last_error_code=None,
                ),
                now,
            )
            return True

    def record_failure(
        self, *, connection_id: str, code: str, status: ConnectionStatus, now: datetime
    ) -> SourceConnection:
        if status == "disconnected":
            raise ValueError("use disconnect() to end a connection")
        with self._lock:
            row = self._live(connection_id)
            return self._put(
                replace(row, status=status, last_error_code=code, last_attempt_at=now),
                now,
            )

    def flag_attention(
        self, *, connection_id: str, code: str, now: datetime
    ) -> SourceConnection:
        with self._lock:
            row = self._live(connection_id)
            return self._put(replace(row, attention_code=code, attention_at=now), now)

    def disconnect(
        self, *, user_id: str, connection_id: str, now: datetime
    ) -> SourceConnection:
        with self._lock:
            row = self.get(user_id=user_id, connection_id=connection_id)
            if row.status == "disconnected":
                return row
            return self._put(
                replace(
                    row,
                    status="disconnected",
                    secret=None,
                    cursor=None,
                    attention_code=None,
                    attention_at=None,
                    lease_holder=None,
                    lease_until=None,
                    disconnected_at=now,
                ),
                now,
            )

    def _live(self, connection_id: str) -> SourceConnection:
        row = self._rows.get(connection_id)
        if row is None or row.status not in LIVE:
            raise ConnectionNotFound()
        return row

    def _put(self, row: SourceConnection, now: datetime) -> SourceConnection:
        row = replace(row, updated_at=now, version=row.version + 1)
        self._rows[row.id] = row
        return row
