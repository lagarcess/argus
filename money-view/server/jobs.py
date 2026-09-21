"""Model-free scheduled fixture loader using the same service as HTTP events."""

import argparse
import json

from .providers import FixtureProvider
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
    load_id = service.begin_load(args.scenario, load_id=args.load_id)
    service.finish_load(load_id, FixtureProvider(args.scenario))
    attempt = service.load_status(load_id)
    status = service.home("fixture")["source_status"]
    print(
        json.dumps(
            {"load_id": load_id, "load_status": attempt, "source_status": status},
            sort_keys=True,
        )
    )
    return 0 if attempt["status"] == "succeeded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
