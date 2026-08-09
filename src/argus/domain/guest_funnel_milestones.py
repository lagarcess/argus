"""Durable once-only claims for guest funnel milestone events.

A milestone is recorded at most once per subject. The guarantee is the
``guest_funnel_milestones`` primary key, not application state, so it survives
process restarts, retries, concurrent requests, and multiple workers. A
duplicate attempt is a silent no-op: a retried request must not fail because
it already succeeded.

The subject is the visitor key that meters guest allowances, never a user id,
because a guest workspace renewal mints a fresh user id.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

GUEST_FUNNEL_MILESTONE_TABLE = "guest_funnel_milestones"

# Outlives the seven-day guest workspace with headroom. Claims are not kept
# forever: a visitor-keyed table with no expiry becomes a durable visitor log.
MILESTONE_RETENTION = timedelta(days=30)


def milestone_expiry(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)) + MILESTONE_RETENTION


def claim_milestone(
    client: Any,
    *,
    subject_key: str,
    milestone: str,
    now: datetime | None = None,
) -> bool:
    """True only for the caller that recorded the milestone."""
    at = now or datetime.now(timezone.utc)
    claimed = client.rpc(
        "claim_guest_funnel_milestone",
        {
            "p_subject_key": subject_key,
            "p_milestone": milestone,
            "p_expires_at": milestone_expiry(at).isoformat(),
        },
    ).execute()
    return bool(getattr(claimed, "data", False))


def purge_expired_milestones(
    client: Any,
    *,
    before: datetime | None = None,
) -> int:
    """Delete claims whose retention has lapsed. Returns the row count."""
    at = before or datetime.now(timezone.utc)
    purged = client.rpc(
        "purge_expired_guest_funnel_milestones",
        {"p_before": at.isoformat()},
    ).execute()
    return int(getattr(purged, "data", 0) or 0)


def claim_memory_milestone(
    claims: dict[tuple[str, str], datetime],
    *,
    subject_key: str,
    milestone: str,
    now: datetime | None = None,
) -> bool:
    """In-memory twin of the database-owned claim.

    Single-process only. The durable guarantee is the primary key; this exists
    so the no-Supabase path behaves the same way.
    """
    at = now or datetime.now(timezone.utc)
    key = (subject_key, milestone)
    expires_at = claims.get(key)
    if expires_at is not None and expires_at > at:
        return False
    claims[key] = milestone_expiry(at)
    return True


def purge_memory_milestones(
    claims: dict[tuple[str, str], datetime],
    *,
    before: datetime | None = None,
) -> int:
    at = before or datetime.now(timezone.utc)
    expired = [key for key, expires_at in claims.items() if expires_at <= at]
    for key in expired:
        del claims[key]
    return len(expired)
