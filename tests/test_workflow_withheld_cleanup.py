"""The worker side of withheld-result cleanup.

A refused link removes the just-committed finalized tuple; a removal
failure persists the durable ``result_cleanup_pending`` marker and fails
the task run, whose Render retry re-enters the entry reconciler. The
fakes come from the execution suite so the refusal behaves exactly as
the lifecycle predicate does on real Postgres.
"""

from __future__ import annotations

import pytest
from argus.domain.backtest_job_lifecycle import RESULT_CLEANUP_PENDING_KEY

from tests.test_render_workflow_execution import (
    FakeBacktestJobGateway,
    FakeBacktestTool,
    _job_row,
    _request_payload,
    _successful_tool_result,
)


def _refused_link_job():
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND

    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    gateway = FakeBacktestJobGateway(job)
    gateway.refuse_result_link_once = True
    return job, gateway


def _run(job, gateway, **overrides):
    from workflows.backtest_job import run_backtest_job

    return run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=overrides.get(
            "backtest_tool", FakeBacktestTool(_successful_tool_result())
        ),
        workflow_run_id="local-run",
        run_id_factory=lambda: "run-workflow",
    )


def test_run_backtest_job_removes_the_run_row_when_the_link_is_refused() -> None:
    """A refused attach must not leave a completed run row behind: History
    and latest-result reads carry no link check, so the worker removes the
    just-committed run and reports the refusal instead of the run id."""
    job, gateway = _refused_link_job()
    result = _run(job, gateway)
    assert result["status"] == "canceled"
    assert result["result_run_id"] is None
    assert result["result_link_refused"] is True
    assert "result_cleanup_reconciled" not in result
    assert gateway.deleted_runs == ["run-workflow"]
    assert gateway.row["result_run_id"] is None


def test_run_backtest_job_fails_the_task_when_cleanup_fails() -> None:
    """A failed tuple removal persists the durable pending marker and
    fails the task run, whose retry is the reconciliation mechanism; it
    must not route through the generic failure handler, which would
    overwrite the job's standing terminal state with a re-claimable
    failure."""
    from workflows.backtest_job import WithheldCleanupError

    job, gateway = _refused_link_job()
    gateway.fail_run_cleanup_once = True

    with pytest.raises(WithheldCleanupError):
        _run(job, gateway)

    assert gateway.deleted_runs == []
    assert gateway.row["status"] == "canceled"
    marker = gateway.row["execution_metadata"][RESULT_CLEANUP_PENDING_KEY]
    assert marker["run_id"] == "run-workflow"
    assert marker["failed_at"]
    assert "failed" not in gateway.transitions


def test_run_backtest_job_reconciles_a_pending_cleanup_marker_at_entry() -> None:
    """The retry of a failed cleanup lands here: a job carrying the
    pending marker gets the removal finished and the marker completed
    before anything treats it as startable work, terminal status
    included."""
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    job["status"] = "canceled"
    job["execution_metadata"] = {
        **job["execution_metadata"],
        RESULT_CLEANUP_PENDING_KEY: {
            "run_id": "run-withheld",
            "failed_at": "2026-08-11T00:00:00+00:00",
        },
    }
    gateway = FakeBacktestJobGateway(job)

    result = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        workflow_run_id="retry-run",
    )

    assert result["status"] == "canceled"
    assert result["result_run_id"] is None
    assert result["result_link_refused"] is True
    assert result["result_cleanup_reconciled"] is True
    assert gateway.deleted_runs == ["run-withheld"]
    marker = gateway.row["execution_metadata"][RESULT_CLEANUP_PENDING_KEY]
    assert marker["completed_at"]
    assert gateway.transitions == []
