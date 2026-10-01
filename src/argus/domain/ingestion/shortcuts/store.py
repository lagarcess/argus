"""Where device-token digests live: one row per Shortcuts connection.

The digest is not a provider credential, so it does not use the connection's
sealed ``secret`` column (the hub would try to open it). It lives beside the
connection, is deleted on revoke, and is only consulted for a connection the
shared repository still reports as live, so a disconnected device is refused
even if a delete were ever missed.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Protocol


class DeviceTokenStore(Protocol):
    def put(
        self, *, connection_id: str, user_id: str, digest: bytes, now: datetime
    ) -> None:
        """Create or replace the digest for this connection."""
        ...

    def get(self, *, connection_id: str) -> bytes | None: ...

    def delete(self, *, connection_id: str) -> None: ...


class InMemoryDeviceTokenStore:
    def __init__(self) -> None:
        self._rows: dict[str, tuple[str, bytes]] = {}
        self._lock = threading.Lock()

    def put(
        self, *, connection_id: str, user_id: str, digest: bytes, now: datetime
    ) -> None:
        with self._lock:
            self._rows[connection_id] = (user_id, bytes(digest))

    def get(self, *, connection_id: str) -> bytes | None:
        row = self._rows.get(connection_id)
        return row[1] if row else None

    def delete(self, *, connection_id: str) -> None:
        with self._lock:
            self._rows.pop(connection_id, None)


class PostgresDeviceTokenStore:
    def __init__(self, pool) -> None:  # noqa: ANN001 - psycopg_pool.ConnectionPool
        self._pool = pool

    def put(
        self, *, connection_id: str, user_id: str, digest: bytes, now: datetime
    ) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """insert into public.financial_shortcut_device_tokens
                    (connection_id, user_id, token_sha256, created_at)
                values (%s::uuid, %s::uuid, %s, %s)
                on conflict (connection_id) do update
                    set token_sha256 = excluded.token_sha256,
                        created_at = excluded.created_at""",
                (connection_id, user_id, digest, now),
            )

    def get(self, *, connection_id: str) -> bytes | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                """select token_sha256 from public.financial_shortcut_device_tokens
                where connection_id = %s::uuid""",
                (connection_id,),
            ).fetchone()
        return bytes(row[0]) if row else None

    def delete(self, *, connection_id: str) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """delete from public.financial_shortcut_device_tokens
                where connection_id = %s::uuid""",
                (connection_id,),
            )
