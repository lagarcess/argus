"""The retention purge callers match the real functions they claim to call.

Skip-gated on ``ARGUS_DISPOSABLE_DATABASE_URL``. The wiring guard proves a purge
is registered and invoked; it cannot prove the call is correct. A wrong function
name, a wrong parameter name, or a misparsed return would leave the job
reporting a clean run while deleting nothing, which is the same failure as
never calling it at all.

The adapter below sends named arguments the way PostgREST does, so a drifted
parameter name fails here rather than in production.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from argus.domain.guest_funnel_milestones import purge_expired_milestones
from argus.domain.visitor_usage import purge_expired_visitor_usage

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)

psycopg = pytest.importorskip("psycopg")


class _RpcResult:
    def __init__(self, data: object) -> None:
        self.data = data


class _RpcCall:
    def __init__(self, connection, name: str, params: dict[str, object]) -> None:
        self._connection = connection
        self._name = name
        self._params = params

    def execute(self) -> _RpcResult:
        names = list(self._params)
        arguments = ", ".join(f"{name} => %({name})s" for name in names)
        with self._connection.cursor() as cursor:
            cursor.execute(
                f"select public.{self._name}({arguments})",
                self._params,
            )
            row = cursor.fetchone()
        return _RpcResult(row[0] if row else None)


class _PostgrestLikeClient:
    """Routes .rpc(name, params).execute() to the real function, by name."""

    def __init__(self, connection) -> None:
        self._connection = connection

    def rpc(self, name: str, params: dict[str, object]) -> _RpcCall:
        return _RpcCall(self._connection, name, params)


@pytest.fixture
def client():
    with psycopg.connect(DSN, autocommit=True) as connection:
        yield _PostgrestLikeClient(connection)


def _seed_expired_milestone(client, subject_key: str) -> None:
    lapsed = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    client.rpc(
        "claim_guest_funnel_milestone",
        {
            "p_subject_key": subject_key,
            "p_milestone": "first_result_completed",
            "p_expires_at": lapsed,
        },
    ).execute()


def test_the_milestone_purge_caller_deletes_expired_claims(client) -> None:
    subject_key = f"visitor:{os.urandom(16).hex()}"
    _seed_expired_milestone(client, subject_key)

    purged = purge_expired_milestones(client)

    assert isinstance(purged, int)
    assert purged >= 1
    assert purge_expired_milestones(client) == 0


def test_the_milestone_purge_caller_spares_live_claims(client) -> None:
    subject_key = f"visitor:{os.urandom(16).hex()}"
    client.rpc(
        "claim_guest_funnel_milestone",
        {
            "p_subject_key": subject_key,
            "p_milestone": "first_result_completed",
            "p_expires_at": (
                datetime.now(timezone.utc) + timedelta(days=30)
            ).isoformat(),
        },
    ).execute()

    purge_expired_milestones(client)

    claimed_again = client.rpc(
        "claim_guest_funnel_milestone",
        {
            "p_subject_key": subject_key,
            "p_milestone": "first_result_completed",
            "p_expires_at": (
                datetime.now(timezone.utc) + timedelta(days=30)
            ).isoformat(),
        },
    ).execute()
    assert claimed_again.data is False


def test_the_visitor_usage_purge_caller_deletes_expired_counters(client) -> None:
    visitor_key = f"visitor:{os.urandom(16).hex()}"
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    client.rpc(
        "settle_visitor_usage",
        {
            "p_visitor_key": visitor_key,
            "p_resource": "discovery_searches",
            "p_windows": psycopg.types.json.Jsonb(
                [
                    {
                        "period": "day",
                        "limit": 2,
                        "period_start": yesterday.isoformat(),
                        "period_end": (yesterday + timedelta(hours=1)).isoformat(),
                    }
                ]
            ),
        },
    ).execute()

    purged = purge_expired_visitor_usage(client)

    assert isinstance(purged, int)
    assert purged >= 1
