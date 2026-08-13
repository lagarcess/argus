from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class UsernameSignupPrevalidation:
    auth_user_exists: bool
    username_available: bool


@dataclass(frozen=True)
class GuestSignupPrevalidation:
    auth_user_id: str | None
    auth_user_confirmed: bool
    username_available: bool


@contextmanager
def serialized_username_signup(
    database_url: str,
    email: str,
    username: str | None,
) -> Iterator[UsernameSignupPrevalidation]:
    if username is None:
        yield UsernameSignupPrevalidation(
            auth_user_exists=False,
            username_available=True,
        )
        return
    if not database_url:
        raise RuntimeError("Username signup serialization requires PostgreSQL.")

    normalized_email = email.strip().casefold()
    normalized = username.strip().casefold()
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"signup-email:{normalized_email}",),
            )
            cursor.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"signup-username:{normalized}",),
            )
            cursor.execute(
                "select exists ("
                "select 1 from auth.users "
                "where lower(email) = lower(%s) limit 1"
                ")",
                (normalized_email,),
            )
            auth_user_row = cursor.fetchone()
            if auth_user_row is None:
                raise RuntimeError("Auth user existence query returned no result.")
            cursor.execute(
                "select not exists ("
                "select 1 from public.profiles "
                "where lower(username) = lower(%s) limit 1"
                ")",
                (normalized,),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("Username availability query returned no result.")
            yield UsernameSignupPrevalidation(
                auth_user_exists=bool(auth_user_row[0]),
                username_available=bool(row[0]),
            )


@contextmanager
def serialized_guest_signup(
    database_url: str,
    email: str,
    username: str | None,
) -> Iterator[GuestSignupPrevalidation]:
    if not database_url:
        raise RuntimeError("Guest signup serialization requires PostgreSQL.")

    normalized_email = email.strip().casefold()
    normalized_username = username.strip().casefold() if username is not None else None
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"signup-email:{normalized_email}",),
            )
            if normalized_username is not None:
                cursor.execute(
                    "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"signup-username:{normalized_username}",),
                )
            cursor.execute(
                "select id::text, email_confirmed_at is not null "
                "from auth.users where lower(email) = lower(%s) limit 1",
                (normalized_email,),
            )
            auth_user_row = cursor.fetchone()
            auth_user_id = str(auth_user_row[0]) if auth_user_row else None
            auth_user_confirmed = bool(auth_user_row[1]) if auth_user_row else False

            username_available = True
            if normalized_username is not None:
                cursor.execute(
                    "select id::text from public.profiles "
                    "where lower(username) = lower(%s) limit 1",
                    (normalized_username,),
                )
                username_owner_row = cursor.fetchone()
                username_available = username_owner_row is None or (
                    auth_user_id is not None
                    and str(username_owner_row[0]) == auth_user_id
                )

            yield GuestSignupPrevalidation(
                auth_user_id=auth_user_id,
                auth_user_confirmed=auth_user_confirmed,
                username_available=username_available,
            )
