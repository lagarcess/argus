from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def _task_id(explicit: str | None = None) -> str:
    value = (
        explicit
        or os.getenv("ARGUS_RENDER_WORKFLOW_PROOF_TASK")
        or "argus-backtests/workflow_proof"
    ).strip()
    if "/" not in value:
        raise RuntimeError(
            "ARGUS_RENDER_WORKFLOW_PROOF_TASK must use "
            "{workflow-slug}/workflow_proof format."
        )
    return value


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


def trigger_proof(*, task_id: str, job_id: str, nonce: str) -> Any:
    from render_sdk import Render

    render = Render()
    return render.workflows.run_task(task_id, [job_id, nonce])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trigger a Render proof workflow.")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--task-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = trigger_proof(
        task_id=_task_id(args.task_id),
        job_id=args.job_id,
        nonce=args.nonce,
    )
    json.dump(_json_safe(result), sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
