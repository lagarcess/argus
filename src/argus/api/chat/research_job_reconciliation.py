"""Settling a research job whose finalizer is gone.

A research run is finalized by a process-local asyncio poller, and that poller
already fails the run at its own deadline. So a row still queued or running
past the stale threshold means the process itself died, which is what a deploy
does. Such a row has no Render task run and no workflow dispatch, so neither
path in the stale scanner can see it, and before this it sat queued forever
while the user watched a turn that would never end.

This settles it; it does not recover it. Everything needed to resume is
durable on the job row (the provider background id and the original request),
but resuming would make a database janitor spend money on provider calls and
persist an assistant message outside a request, metering included. That is its
own change, tracked as a condition on enabling the rail rather than smuggled
into a reconciler.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

RESEARCH_POLLER_LOST_CODE = "research_poller_lost"
_ACTIVE_STATUSES = frozenset({"queued", "running"})


def is_stranded_research_job(job: dict[str, Any]) -> bool:
    """Whether this stale row is a research run with no finalizer left."""
    # Deferred: the scanner imports this module at import time, and the
    # research job module reaches back into API state through its own chain.
    from argus.api.chat.research_jobs import RESEARCH_OPERATION_SCOPE

    scope = str(job.get("operation_scope") or "").strip()
    if scope != RESEARCH_OPERATION_SCOPE:
        return False
    return str(job.get("status") or "").strip().lower() in _ACTIVE_STATUSES


def fail_stranded_research_job(
    *,
    gateway: Any,
    user_id: str,
    job: dict[str, Any],
) -> dict[str, Any]:
    """Mark it failed and retryable, under the same compare-and-set every
    other job settlement uses, so a poller that is somehow still alive cannot
    lose a completed answer to this."""
    reconciled_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata = dict(job.get("execution_metadata") or {})
    metadata["research_reconciliation"] = {
        "status": "failed",
        "failure_code": RESEARCH_POLLER_LOST_CODE,
        "reconciled_at": reconciled_at,
    }
    job_id = str(job.get("id") or "")
    failed = gateway.mark_backtest_job_failed(
        user_id=user_id,
        job_id=job_id,
        failure_code=RESEARCH_POLLER_LOST_CODE,
        failure_detail=(
            "Research run lost its finalizer before completing, most likely a "
            "restart. The question can be asked again."
        ),
        retryable=True,
        finished_at=reconciled_at,
        execution_metadata=metadata,
        expected_status=str(job.get("status") or "").strip().lower(),
        expected_updated_at=str(job.get("updated_at") or "").strip() or None,
    )
    if failed:
        return dict(failed)
    get_job = getattr(gateway, "get_backtest_job", None)
    current = get_job(user_id=user_id, job_id=job_id) if get_job else None
    return dict(current or job)
