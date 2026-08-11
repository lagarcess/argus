"""Pure projections over Render workflow task runs.

These read a task-run document from the workflow platform and derive the
typed failure truth the job lifecycle stores; they hold no state and talk
to no service.
"""

from __future__ import annotations

from typing import Any


def _task_run_error(task_run: dict[str, Any]) -> str:
    raw = task_run.get("error")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    attempts = task_run.get("attempts")
    if isinstance(attempts, list):
        for attempt in reversed(attempts):
            if not isinstance(attempt, dict):
                continue
            error = attempt.get("error")
            if isinstance(error, str) and error.strip():
                return error.strip()
    return ""


def _task_run_completed_at(task_run: dict[str, Any]) -> str | None:
    for key in ("completedAt", "completed_at", "finishedAt", "finished_at"):
        raw = task_run.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    attempts = task_run.get("attempts")
    if isinstance(attempts, list):
        for attempt in reversed(attempts):
            if not isinstance(attempt, dict):
                continue
            for key in ("completedAt", "completed_at", "finishedAt", "finished_at"):
                raw = attempt.get(key)
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
    return None


def _workflow_task_failure(task_run: dict[str, Any]) -> tuple[str, str, bool]:
    status = str(task_run.get("status") or "").strip().lower()
    error = _task_run_error(task_run).lower()
    if "timed out" in error or "timeout" in error:
        return (
            "workflow_task_timeout",
            "Backtest execution timed out before finishing.",
            True,
        )
    if status in {"canceled", "cancelled"}:
        return (
            "workflow_task_canceled",
            "Backtest execution was canceled before finishing.",
            False,
        )
    if status == "expired":
        return (
            "workflow_task_expired",
            "Backtest execution expired before finishing.",
            True,
        )
    return (
        "workflow_task_failed",
        "Backtest execution failed before finishing.",
        True,
    )
