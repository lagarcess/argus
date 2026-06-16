from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

from argus.api.chat.backtest_jobs import (
    DEFAULT_STALE_QUEUED_SECONDS,
    DEFAULT_STALE_RUNNING_SECONDS,
    scan_stale_backtest_jobs,
)
from argus.domain.supabase_gateway import SupabaseGateway
from dotenv import load_dotenv


def _copy_first_env(target: str, candidates: Sequence[str]) -> None:
    if os.getenv(target):
        return
    for candidate in candidates:
        value = os.getenv(candidate)
        if value:
            os.environ[target] = value
            return


def _prepare_supabase_env() -> None:
    _copy_first_env(
        "SUPABASE_URL",
        (
            "ARGUS_STALE_JOBS_SUPABASE_URL",
            "ARGUS_CANARY_SUPABASE_URL",
            "SUPABASE_PROJECT_URL",
        ),
    )
    _copy_first_env(
        "SUPABASE_SERVICE_ROLE_KEY",
        (
            "ARGUS_STALE_JOBS_SUPABASE_SERVICE_ROLE_KEY",
            "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY",
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan queued/running backtest jobs and reconcile terminal Render task runs.",
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--queued-age-seconds",
        type=int,
        default=DEFAULT_STALE_QUEUED_SECONDS,
    )
    parser.add_argument(
        "--running-age-seconds",
        type=int,
        default=DEFAULT_STALE_RUNNING_SECONDS,
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = _build_parser().parse_args(argv)
    _prepare_supabase_env()

    report = scan_stale_backtest_jobs(
        gateway=SupabaseGateway.from_env(),
        queued_age_seconds=args.queued_age_seconds,
        running_age_seconds=args.running_age_seconds,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print(
            "stale backtest job scan: "
            f"status={report['status']} "
            f"scanned={report['scanned_count']} "
            f"stale={report['stale_count']} "
            f"reconciled={report['reconciled_count']} "
            f"unresolved={report['unresolved_count']} "
            f"errors={report['error_count']}"
        )
        for job in report["unresolved_jobs"]:
            print(
                "unresolved stale job: "
                f"id={job.get('id')} "
                f"status={job.get('status')} "
                f"age_seconds={job.get('age_seconds')} "
                f"task_run_id={job.get('task_run_id') or '<missing>'}"
            )

    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
