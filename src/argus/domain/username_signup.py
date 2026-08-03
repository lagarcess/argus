from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg


@contextmanager
def serialized_username_signup(
    database_url: str,
    username: str | None,
) -> Iterator[None]:
    if username is None:
        yield
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
        yield
