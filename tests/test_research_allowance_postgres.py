"""Real-Postgres concurrency proof for research provider admission.

Skip-gated on ``ARGUS_DISPOSABLE_DATABASE_URL``: point it at a disposable
Supabase-Postgres database with every migration applied, never production.
The in-memory proof reproduces the old read-then-settle race; this proof locks
the production transaction itself under two simultaneous claims.
"""

from __future__ import annotations

import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

psycopg = pytest.importorskip("psycopg")


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _claim(
    visitor_key: str,
    global_key: str,
    *,
    barrier: Barrier | None = None,
) -> dict:
    with _connect() as connection, connection.cursor() as cursor:
        if barrier is not None:
            barrier.wait(timeout=5)
        cursor.execute(
            "select public.claim_research_usage(%s, %s, %s, %s, %s)",
            (visitor_key, "research_searches", global_key, 5000, 3),
        )
        return cursor.fetchone()[0]


def _used_count(visitor_key: str) -> int:
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "select used_count from public.visitor_usage_counters"
            " where visitor_key = %s and resource = %s and period = 'day'",
            (visitor_key, "research_searches"),
        )
        return cursor.fetchone()[0]


def _delete_counts(*visitor_keys: str) -> None:
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "delete from public.visitor_usage_counters" " where visitor_key = any(%s)",
            (list(visitor_keys),),
        )


@pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
def test_same_visitor_concurrent_claims_cannot_share_the_last_slot() -> None:
    visitor_key = f"visitor:research-proof-{secrets.token_hex(12)}"
    global_key = f"global:research-proof-{secrets.token_hex(12)}"
    try:
        assert _claim(visitor_key, global_key)["available"] is True
        assert _claim(visitor_key, global_key)["available"] is True

        simultaneous = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: _claim(visitor_key, global_key, barrier=simultaneous),
                    range(2),
                )
            )

        assert sum(result["available"] is True for result in results) == 1
        denied = next(result for result in results if result["available"] is False)
        assert denied["guest_exhausted"] is True
        assert _used_count(visitor_key) == 3
        assert _used_count(global_key) == 3
    finally:
        _delete_counts(visitor_key, global_key)


def test_claim_function_is_service_role_only() -> None:
    migration = (
        Path(__file__).parents[1]
        / "supabase/migrations/20260903000000_claim_research_usage.sql"
    ).read_text()
    assert "security definer" in migration.lower()
    assert "from public, anon, authenticated" in migration.lower()
    assert "to service_role" in migration.lower()
