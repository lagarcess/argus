"""Postgres twin of ``InMemoryAppleCredentialRepository``.

Runs as the API's service role. The table admits no client role at all
(``supabase/migrations/20261003150000_apple_sign_in_credentials.sql``).
"""

from __future__ import annotations

from datetime import datetime

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from argus.domain.apple_sign_in.credentials import (
    AppleCaptureNotStored,
    AppleIdentityMismatch,
    StoredAppleCredential,
)
from argus.domain.apple_sign_in.identity import LinkedAppleIdentity, linked_apple_identity


class PostgresAppleCredentialRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def linked_identity(self, *, user_id: str) -> LinkedAppleIdentity | None:
        with self._pool.connection() as connection:
            return linked_apple_identity(connection, user_id)

    def save_capture(
        self,
        *,
        user_id: str,
        identity: LinkedAppleIdentity,
        expected_ciphertext: bytes | None,
        client_id: str,
        secret_ciphertext: bytes,
        now: datetime,
        key_id: str,
    ) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                connection.execute("set transaction isolation level read committed")
                # Separate statements ensure the identity read sees inserts that
                # committed while the parent lock waited. Its FK fences inserts.
                parent = connection.execute(
                    "select id from auth.users where id = %s::uuid for update",
                    (user_id,),
                ).fetchone()
                if parent is None:
                    raise AppleIdentityMismatch("linked_identity_changed")
                if linked_apple_identity(connection, user_id, lock=True) != identity:
                    raise AppleIdentityMismatch("linked_identity_changed")
                row = connection.execute(
                    "select secret_ciphertext from public.apple_sign_in_credentials "
                    "where user_id = %s::uuid for update",
                    (user_id,),
                ).fetchone()
                current = bytes(row[0]) if row else None
                if current != expected_ciphertext:
                    raise AppleCaptureNotStored("credential_replaced")
                connection.execute(
                    """insert into public.apple_sign_in_credentials
                        (user_id, client_id, secret_ciphertext, secret_key_fingerprint,
                         captured_at, updated_at, apple_subject)
                    values (%s::uuid, %s, %s, %s, %s, %s, %s)
                    on conflict (user_id) do update
                    set client_id = excluded.client_id,
                        secret_ciphertext = excluded.secret_ciphertext,
                        secret_key_fingerprint = excluded.secret_key_fingerprint,
                        updated_at = excluded.updated_at,
                        apple_subject = excluded.apple_subject""",
                    (
                        user_id,
                        client_id,
                        secret_ciphertext,
                        key_id,
                        now,
                        now,
                        identity.subject,
                    ),
                )

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
                    updated_at = excluded.updated_at,
                    apple_subject = null""",
                (user_id, client_id, secret_ciphertext, key_id, now, now),
            )

    def get(self, *, user_id: str) -> StoredAppleCredential | None:
        with self._pool.connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """select user_id::text, client_id, secret_ciphertext,
                        captured_at, updated_at, secret_key_fingerprint, apple_subject
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
            apple_subject=row["apple_subject"],
        )

    def delete_if_unchanged(self, *, user_id: str, secret_ciphertext: bytes) -> bool:
        with self._pool.connection() as connection:
            cursor = connection.execute(
                """delete from public.apple_sign_in_credentials
                where user_id = %s::uuid and secret_ciphertext = %s""",
                (user_id, secret_ciphertext),
            )
            return cursor.rowcount == 1
