"""Settling a research job whose finalizer died with its process.

Codex on PR #396: a thorough run started before a deploy loses its
process-local poller, and the row has neither a Render task run nor a workflow
dispatch, so neither existing reconciliation path could see it. The turn stayed
queued forever and the answer was lost.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tests.test_backtest_jobs_async import (
    _FakeTerminalTaskRunClient,
    _StaleJobScanGateway,
)


def test_stale_scan_settles_a_research_job_whose_poller_died() -> None:
    """Codex's scenario: a thorough run started before a deploy. The poller is
    process-local, so the restart destroys it; the row has no Render task run
    and no workflow dispatch, so neither existing path could see it and the
    turn stayed queued forever."""
    from argus.api.chat.backtest_jobs import scan_stale_backtest_jobs

    gateway = _StaleJobScanGateway()
    gateway.jobs = [
        {
            "id": "job-research-stranded",
            "user_id": "user-1",
            "status": "running",
            "operation_scope": "chat.research",
            "queued_at": "2026-06-06T12:00:00+00:00",
            "created_at": "2026-06-06T12:00:00+00:00",
            "updated_at": "2026-06-06T12:00:00+00:00",
            "launch_payload": {
                "schema_version": "research_job_launch/v1",
                "perplexity_background_id": "bg-123",
            },
            "execution_metadata": {"perplexity_background_id": "bg-123"},
        }
    ]
    task_client = _FakeTerminalTaskRunClient({"id": "unused", "status": "failed"})

    report = scan_stale_backtest_jobs(
        gateway=gateway,
        now=datetime(2026, 6, 6, 12, 30, tzinfo=timezone.utc),
        queued_age_seconds=900,
        running_age_seconds=900,
        limit=20,
        task_run_client=task_client,
    )

    # No Render lookup: a research job never had a task run to reconcile.
    assert task_client.calls == []
    assert report["reconciled_count"] == 1
    assert report["unresolved_count"] == 0
    failed = gateway.failed_updates[0]
    assert failed["job_id"] == "job-research-stranded"
    assert failed["failure_code"] == "research_poller_lost"
    # Retryable and compare-and-set guarded, like every other settlement.
    assert failed["retryable"] is True
    assert failed["expected_status"] == "running"
    assert failed["expected_updated_at"] == "2026-06-06T12:00:00+00:00"


def test_stale_scan_leaves_a_fresh_research_job_alone() -> None:
    """The poller fails a run at its own deadline, so only a row past the
    stale threshold means the process died. Anything younger is still live."""
    from argus.api.chat.backtest_jobs import scan_stale_backtest_jobs

    gateway = _StaleJobScanGateway()
    gateway.jobs = [
        {
            "id": "job-research-live",
            "user_id": "user-1",
            "status": "running",
            "operation_scope": "chat.research",
            "queued_at": "2026-06-06T12:25:00+00:00",
            "created_at": "2026-06-06T12:25:00+00:00",
            "updated_at": "2026-06-06T12:25:00+00:00",
            "launch_payload": {"schema_version": "research_job_launch/v1"},
            "execution_metadata": {},
        }
    ]

    report = scan_stale_backtest_jobs(
        gateway=gateway,
        now=datetime(2026, 6, 6, 12, 30, tzinfo=timezone.utc),
        queued_age_seconds=900,
        running_age_seconds=900,
        limit=20,
        task_run_client=_FakeTerminalTaskRunClient({"id": "x", "status": "failed"}),
    )

    assert report["stale_count"] == 0
    assert gateway.failed_updates == []
