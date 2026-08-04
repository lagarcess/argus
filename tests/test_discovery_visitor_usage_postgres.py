"""Real-Postgres proofs for visitor-scoped discovery usage counters.

Skip-gated on ``ARGUS_DISPOSABLE_DATABASE_URL``: point it at a disposable
Supabase-Postgres database with every ``supabase/migrations`` file applied,
never at production. Two prior metering defects shipped green because the
in-memory store accepted writes the real schema rejected, so anything that
touches these counters must be proven here.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)

psycopg = pytest.importorskip("psycopg")


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _fresh_key() -> str:
    return f"visitor:{secrets.token_hex(16)}"


def _day_window(now: datetime) -> tuple[str, str]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def _settle(cursor, visitor_key: str, *, limit: int = 2) -> dict:
    start, end = _day_window(datetime.now(timezone.utc))
    cursor.execute(
        "select public.settle_visitor_usage(%s, %s, %s::jsonb)",
        (
            visitor_key,
            "discovery_searches",
            json.dumps(
                [
                    {
                        "period": "day",
                        "limit": limit,
                        "period_start": start,
                        "period_end": end,
                    }
                ]
            ),
        ),
    )
    return cursor.fetchone()[0]


def _used_count(cursor, visitor_key: str) -> int | None:
    cursor.execute(
        "select used_count from public.visitor_usage_counters"
        " where visitor_key = %s and resource = %s and period = %s",
        (visitor_key, "discovery_searches", "day"),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def test_settlement_inserts_without_any_profile_row() -> None:
    """The table is deliberately not FK-bound: a visitor has no profile.

    This is the exact write that failed twice against usage_counters.
    """
    key = _fresh_key()
    with _connect() as connection, connection.cursor() as cursor:
        result = _settle(cursor, key)
        assert result["settled"] is True
        assert _used_count(cursor, key) == 1


def test_settlement_increments_within_the_same_window() -> None:
    key = _fresh_key()
    with _connect() as connection, connection.cursor() as cursor:
        _settle(cursor, key)
        result = _settle(cursor, key)
        assert result["windows"][0]["used_count"] == 2
        assert _used_count(cursor, key) == 2


def test_distinct_visitors_are_counted_separately() -> None:
    first, second = _fresh_key(), _fresh_key()
    with _connect() as connection, connection.cursor() as cursor:
        _settle(cursor, first)
        _settle(cursor, first)
        _settle(cursor, second)
        assert _used_count(cursor, first) == 2
        assert _used_count(cursor, second) == 1


def test_the_global_ceiling_key_persists_like_any_visitor() -> None:
    """The ceiling charges into this table precisely because usage_counters
    would reject its non-uuid subject; prove the write lands."""
    key = f"global:proof-{secrets.token_hex(8)}"
    with _connect() as connection, connection.cursor() as cursor:
        _settle(cursor, key, limit=500)
        assert _used_count(cursor, key) == 1


def test_purge_removes_only_expired_windows() -> None:
    expired, current = _fresh_key(), _fresh_key()
    now = datetime.now(timezone.utc)
    yesterday_start = (now - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "insert into public.visitor_usage_counters"
            " (visitor_key, resource, period, period_start, period_end,"
            "  used_count, limit_count)"
            " values (%s, %s, %s, %s, %s, 1, 2)",
            (
                expired,
                "discovery_searches",
                "day",
                yesterday_start.isoformat(),
                (yesterday_start + timedelta(days=1)).isoformat(),
            ),
        )
        _settle(cursor, current)
        cursor.execute("select public.purge_expired_visitor_usage(now())")
        assert _used_count(cursor, expired) is None
        assert _used_count(cursor, current) == 1


def test_empty_visitor_key_is_rejected() -> None:
    with _connect() as connection, connection.cursor() as cursor:
        with pytest.raises(psycopg.errors.RaiseException):
            _settle(cursor, "   ")
