"""Postgres twin of ``InMemoryAppleCredentialRepository``.

Runs as the API's service role. The table admits no client role at all
(``supabase/migrations/20261003150000_apple_sign_in_credentials.sql``).
"""

from __future__ import annotations

from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from argus.domain.apple_sign_in.credentials import StoredAppleCredential


class PostgresAppleCredentialRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def upsert(
        self,
        *,
        user_id: str,
        client_id: str,
        secret_ciphertext: bytes,
        now: datetime,
        key_id: str | None = None,
    ) -> None:
        with self._pool.connection() as connection:
            connection.execute(
                """insert into public.apple_sign_in_credentials
                    (user_id, client_id, secret_ciphertext, secret_key_fingerprint,
                     captured_at, updated_at)
                values (%s::uuid, %s, %s, %s, %s, %s)
                on conflict (user_id) do update
                set client_id = excluded.client_id,
                    secret_ciphertext = excluded.secret_ciphertext,
                    secret_key_fingerprint = excluded.secret_key_fingerprint,
                    updated_at = excluded.updated_at""",
                (user_id, client_id, secret_ciphertext, key_id, now, now),
            )

    def get(self, *, user_id: str) -> StoredAppleCredential | None:
        with self._pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """select user_id::text, client_id, secret_ciphertext,
                        captured_at, updated_at, secret_key_fingerprint
                    from public.apple_sign_in_credentials where user_id = %s::uuid""",
                    (user_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return StoredAppleCredential(
            user_id=row["user_id"],
            client_id=row["client_id"],
            secret_ciphertext=bytes(row["secret_ciphertext"]),
            captured_at=row["captured_at"],
            updated_at=row["updated_at"],
            key_id=row["secret_key_fingerprint"],
        )

    def delete_if_unchanged(self, *, user_id: str, secret_ciphertext: bytes) -> bool:
        with self._pool.connection() as connection:
            cursor = connection.execute(
                """delete from public.apple_sign_in_credentials
                where user_id = %s::uuid and secret_ciphertext = %s""",
                (user_id, secret_ciphertext),
            )
            return cursor.rowcount == 1
