from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_POLL_SECONDS = 2.0
COMPLETED_STATUSES = {"completed", "succeeded"}
FAILED_STATUSES = {"failed", "canceled", "cancelled", "expired"}


def _task_id(explicit: str | None = None) -> str:
    value = (
        explicit
        or os.getenv("ARGUS_BACKTEST_WORKFLOW_TASK")
        or os.getenv("ARGUS_RENDER_WORKFLOW_PROOF_TASK")
        or "argus-backtests/workflow_proof"
    ).strip()
    if "/" not in value:
        raise RuntimeError(
            "ARGUS_RENDER_WORKFLOW_PROOF_TASK must use "
            "{workflow-slug}/workflow_proof format."
        )
    return value


def _positive_float(value: str | None, *, default: float) -> float:
    if value is None or not value.strip():
        return default
    try:
        return max(0.1, float(value))
    except ValueError:
        return default


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    if hasattr(value, "__dict__"):
        return {
            key: _json_safe(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def _task_run_id(value: dict[str, Any]) -> str:
    task_run_id = str(value.get("id") or "").strip()
    if not task_run_id:
        raise RuntimeError("Render workflow proof dispatch did not return a task run id.")
    return task_run_id


def trigger_proof(
    *,
    task_id: str,
    job_id: str,
    nonce: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> Any:
    from argus.api.chat.backtest_jobs import RenderTaskRunClient, RenderWorkflowDispatcher

    dispatcher = RenderWorkflowDispatcher(task_id=task_id)
    task_run = dispatcher.dispatch(job_id=job_id, nonce=nonce)
    task_run_id = _task_run_id(task_run)
    client = RenderTaskRunClient()
    deadline = time.monotonic() + timeout_seconds

    while True:
        details = client.get_task_run(task_run_id)
        status = str(details.get("status") or "").strip().lower()
        if status in COMPLETED_STATUSES:
            return details
        if status in FAILED_STATUSES:
            raise RuntimeError(
                f"Render workflow proof task {task_run_id} finished with status {status}."
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Render workflow proof task {task_run_id} did not finish within "
                f"{timeout_seconds:g} seconds."
            )
        time.sleep(poll_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trigger a Render proof workflow.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--task-id")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=_positive_float(
            os.getenv("ARGUS_RENDER_WORKFLOW_PROOF_TIMEOUT_SECONDS"),
            default=DEFAULT_TIMEOUT_SECONDS,
        ),
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=_positive_float(
            os.getenv("ARGUS_RENDER_WORKFLOW_PROOF_POLL_SECONDS"),
            default=DEFAULT_POLL_SECONDS,
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = trigger_proof(
        task_id=_task_id(args.task_id),
        job_id=args.job_id,
        nonce=args.nonce,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    json.dump(_json_safe(result), sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
