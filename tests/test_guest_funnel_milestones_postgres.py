"""Real-Postgres proofs for durable guest funnel milestone idempotency (#376).

Skip-gated on ``ARGUS_DISPOSABLE_DATABASE_URL``. The guarantee is the
``guest_funnel_milestones`` primary key, so the claims that matter are proven
here against the real schema: a duplicate is a silent no-op, and concurrent
claimants on separate connections resolve to exactly one winner rather than to
a lock that only holds inside one process.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta, timezone

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)

psycopg = pytest.importorskip("psycopg")

MILESTONE = "first_result_completed"
CONCURRENT_CLAIMANTS = 8


def _connect():
    return psycopg.connect(DSN, autocommit=True)


def _expiry(days: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _claim(cursor, subject_key: str, *, milestone: str = MILESTONE, expires_at=None):
    cursor.execute(
        "select public.claim_guest_funnel_milestone(%s, %s, %s)",
        (subject_key, milestone, expires_at or _expiry()),
    )
    return cursor.fetchone()[0]


def _row_count(cursor, subject_key: str, *, milestone: str = MILESTONE) -> int:
    cursor.execute(
        "select count(*) from public.guest_funnel_milestones"
        " where subject_key = %s and milestone = %s",
        (subject_key, milestone),
    )
    return int(cursor.fetchone()[0])


@pytest.fixture
def subject_key():
    key = f"visitor:{os.urandom(16).hex()}"
    yield key
    with _connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            "delete from public.guest_funnel_milestones where subject_key = %s",
            (key,),
        )


def test_the_same_milestone_claimed_twice_records_exactly_one_row(
    subject_key: str,
) -> None:
    with _connect() as connection, connection.cursor() as cursor:
        assert _claim(cursor, subject_key) is True
        assert _claim(cursor, subject_key) is False
        assert _row_count(cursor, subject_key) == 1


def test_concurrent_claimants_resolve_to_exactly_one_winner(
    subject_key: str,
) -> None:
    """Separate connections, released together: the primary key is the arbiter,
    not a lock held inside one process."""
    barrier = threading.Barrier(CONCURRENT_CLAIMANTS)
    outcomes: list[bool] = []
    failures: list[BaseException] = []
    guard = threading.Lock()

    def claim_once() -> None:
        try:
            with _connect() as connection, connection.cursor() as cursor:
                barrier.wait(timeout=30)
                claimed = _claim(cursor, subject_key)
            with guard:
                outcomes.append(claimed)
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            with guard:
                failures.append(exc)

    threads = [
        threading.Thread(target=claim_once, name=f"claimant-{index}")
        for index in range(CONCURRENT_CLAIMANTS)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert not failures, failures
    assert len(outcomes) == CONCURRENT_CLAIMANTS
    assert outcomes.count(True) == 1

    with _connect() as connection, connection.cursor() as cursor:
        assert _row_count(cursor, subject_key) == 1


def test_a_renewed_workspace_does_not_reclaim_the_visitors_milestone(
    subject_key: str,
) -> None:
    """Renewal mints a fresh user id but keeps the visitor key, and the claim is
    keyed on the visitor, so the milestone stays recorded once."""
    with _connect() as connection, connection.cursor() as cursor:
        assert _claim(cursor, subject_key) is True
        # A different process, after the renewal, with the same subject.
        with _connect() as renewed, renewed.cursor() as renewed_cursor:
            assert _claim(renewed_cursor, subject_key) is False
        assert _row_count(cursor, subject_key) == 1


def test_distinct_subjects_and_milestones_each_claim_once(subject_key: str) -> None:
    other_subject = f"{subject_key}-other"
    try:
        with _connect() as connection, connection.cursor() as cursor:
            assert _claim(cursor, subject_key) is True
            assert _claim(cursor, other_subject) is True
            assert _claim(cursor, subject_key, milestone="first_simulation_admitted")
            assert _row_count(cursor, subject_key) == 1
            assert _row_count(cursor, other_subject) == 1
            assert (
                _row_count(cursor, subject_key, milestone="first_simulation_admitted")
                == 1
            )
    finally:
        with _connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "delete from public.guest_funnel_milestones where subject_key = %s",
                (other_subject,),
            )


def test_an_expired_claim_is_taken_over_without_waiting_for_the_purge(
    subject_key: str,
) -> None:
    lapsed = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with _connect() as connection, connection.cursor() as cursor:
        assert _claim(cursor, subject_key, expires_at=lapsed) is True
        assert _claim(cursor, subject_key) is True
        assert _row_count(cursor, subject_key) == 1
        assert _claim(cursor, subject_key) is False


def test_the_purge_drops_only_expired_claims(subject_key: str) -> None:
    expired_subject = f"{subject_key}-expired"
    lapsed = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    with _connect() as connection, connection.cursor() as cursor:
        assert _claim(cursor, subject_key) is True
        assert _claim(cursor, expired_subject, expires_at=lapsed) is True

        cursor.execute("select public.purge_expired_guest_funnel_milestones(now())")
        assert int(cursor.fetchone()[0]) >= 1

        assert _row_count(cursor, expired_subject) == 0
        assert _row_count(cursor, subject_key) == 1


@pytest.mark.parametrize(
    ("subject", "milestone"),
    [("", MILESTONE), ("   ", MILESTONE), ("visitor:abc", ""), ("visitor:abc", "   ")],
)
def test_a_claim_without_a_subject_or_milestone_is_rejected(
    subject: str,
    milestone: str,
) -> None:
    with _connect() as connection, connection.cursor() as cursor:
        with pytest.raises(psycopg.errors.RaiseException):
            _claim(cursor, subject, milestone=milestone)


def test_a_claim_without_an_expiry_is_rejected(subject_key: str) -> None:
    with _connect() as connection, connection.cursor() as cursor:
        with pytest.raises(psycopg.errors.RaiseException):
            cursor.execute(
                "select public.claim_guest_funnel_milestone(%s, %s, null)",
                (subject_key, MILESTONE),
            )


GUEST_ROLE_DENIED_STATEMENTS = {
    "select": "select * from public.guest_funnel_milestones",
    "insert": (
        "insert into public.guest_funnel_milestones"
        " (subject_key, milestone, expires_at)"
        " values ('visitor:probe', 'first_result_completed', now())"
    ),
    "delete": "delete from public.guest_funnel_milestones",
    "claim": (
        "select public.claim_guest_funnel_milestone("
        "'visitor:probe', 'first_result_completed', now())"
    ),
    "purge": "select public.purge_expired_guest_funnel_milestones(now())",
}


@pytest.mark.parametrize("role", ["anon", "authenticated"])
@pytest.mark.parametrize("statement", sorted(GUEST_ROLE_DENIED_STATEMENTS))
def test_guest_roles_cannot_reach_funnel_claims(role: str, statement: str) -> None:
    """The table holds visitor digests and the claim decides what the funnel
    counts, so only service_role may reach either.

    One transaction per statement: `set local role` is scoped to a transaction,
    and a rollback would silently restore the connection's own role.
    """
    with psycopg.connect(DSN) as connection, connection.cursor() as cursor:
        cursor.execute(f"set local role {role}")
        cursor.execute(
            "select set_config('request.jwt.claims', %s, true)",
            (
                json.dumps(
                    {
                        "sub": "00000000-0000-0000-0000-0000000004f1",
                        "role": role,
                        "is_anonymous": role == "authenticated",
                    }
                ),
            ),
        )
        cursor.execute("select current_user")
        assert cursor.fetchone()[0] == role

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(GUEST_ROLE_DENIED_STATEMENTS[statement])
