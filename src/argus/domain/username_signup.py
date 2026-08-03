from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg


@contextmanager
def serialized_username_signup(
    database_url: str,
    username: str | None,
) -> Iterator[bool]:
    if username is None:
        yield True
        return
    if not database_url:
        raise RuntimeError("Username signup serialization requires PostgreSQL.")

    normalized = username.strip().casefold()
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (normalized,),
            )
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
            yield bool(row[0])
