"""Model-free scheduled fixture loader using the same service as HTTP events."""

import argparse
import json
import time
from uuid import uuid4

from .platform.jobs_runtime import enqueue_job, get_job_internal, worker_tick
from .platform.runtime import initialize
from .service import PlacementService
from .store import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--provider", choices=["fixture"], default="fixture")
    subcommands = parser.add_subparsers(dest="command", required=True)
    load = subcommands.add_parser("load")
    load.add_argument(
        "--scenario",
        choices=[
            "baseline",
            "same_winner",
            "leader_changed",
            "inflation_crossed",
            "failure",
        ],
        default="baseline",
    )
    load.add_argument(
        "--load-id", help="Reuse a logical attempt id when retrying a scheduled job"
    )
    args = parser.parse_args(argv)
    service = PlacementService(Store(args.database))
    initialize(service.store)
    load_id = args.load_id or str(uuid4())
    job = enqueue_job(
        service.store,
        None,
        "deposit_load",
        {"scenario": args.scenario, "load_id": load_id},
        load_id,
    )
    # Waiting belongs to this scheduled CLI, never to an HTTP request handler.
    while job["status"] in ("queued", "running"):
        if worker_tick(service.store) is None:
            time.sleep(0.05)
        job = get_job_internal(service.store, job["id"])
    attempt = service.load_status(load_id)
    status = service.source_status()
    print(
        json.dumps(
            {
                "load_id": load_id,
                "job_id": job["id"],
                "load_status": attempt,
                "source_status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if job["status"] == "succeeded" and attempt["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
