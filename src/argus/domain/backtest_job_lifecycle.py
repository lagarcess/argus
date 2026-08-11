"""One statement of the job lifecycle as the confirmation card sees it.

The consumption design needs two decisions to agree forever: when the
worker may still write success, and when a dead run may give its card
back. Both derive from this module's single classification, and the
walk-every-state tests assert they cannot disagree, on real Postgres
included. This tightens a spine invariant so it can carry the consumption
feature; it does not fix a pre-existing bug. Before cards were consumed at
admission, the unguarded success write was correct self-healing for
re-claimable failures, and it stays exactly that for every state a worker
legitimately holds.
"""

from __future__ import annotations

from typing import Any

WORKER_HELD_STATUSES = ("queued", "running")
_KNOWN_DEAD_STATUSES = ("canceled", "cancelled", "expired")

JOB_MAY_SUCCEED = "may_succeed"
JOB_HAS_RESULT = "has_result"
JOB_DEAD = "dead"
JOB_UNKNOWN = "unknown"


def classify_job_for_card(*, status: Any, retryable: Any) -> str:
    """The one lifecycle statement both sides derive from.

    ``may_succeed`` while a worker legitimately holds the job, mid-flight
    or as a re-claimable failure; ``has_result`` once success happened;
    ``dead`` when no future write can produce a result; ``unknown`` for
    anything this vocabulary cannot describe. Unknown fails closed on
    every side: success is refused and the card stays consumed.
    """
    normalized = str(status or "").strip().casefold()
    if normalized in WORKER_HELD_STATUSES:
        return JOB_MAY_SUCCEED
    if normalized == "failed":
        return JOB_MAY_SUCCEED if bool(retryable) else JOB_DEAD
    if normalized == "succeeded":
        return JOB_HAS_RESULT
    if normalized in _KNOWN_DEAD_STATUSES:
        return JOB_DEAD
    return JOB_UNKNOWN


def job_success_write_sql_predicate() -> str:
    """The SQL clause equivalent of ``classify == may_succeed``.

    The worker's success write embeds this exact fragment at runtime, so
    the database enforces the same statement this module makes; a
    source-contract test pins the worker to the generator and a Postgres
    test walks every state asserting the fragment and the classifier
    agree.
    """
    held = ", ".join(f"'{status}'" for status in WORKER_HELD_STATUSES)
    return f"(status in ({held}) or (status = 'failed' and retryable))"


def job_success_write_postgrest_filter() -> str:
    """The PostgREST or-filter equivalent of ``classify == may_succeed``.

    The API gateway's success write is a second implementation of the same
    statement; generating its filter beside the classifier keeps the two
    from drifting, and the walk-every-state Postgres test covers both
    encodings.
    """
    held = ",".join(WORKER_HELD_STATUSES)
    return f"status.in.({held}),and(status.eq.failed,retryable.is.true)"
