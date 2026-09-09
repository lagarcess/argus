"""Run an explicit, bounded schedule of partial A/B measurement cases."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

CASES = (
    "natural_language_establishes_modeled_costs_issue_271",
    "capability_honesty_golden_cross_control_aapl",
    "dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455",
    "messy_spanish_btc_hold_q1_2024",
    "graceful_recovery_spanish_weekly_options_aapl",
    "asset_discovery_trending_crypto_exact_issue_344",
    "ordinary_conversation_macro_curiosity_en",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    schedule = [
        {"index": 0, "repetition": repetition + 1, "arm": arm, "case": case}
        for repetition in range(args.repetitions)
        for case_index, case in enumerate(CASES)
        for arm in (
            ("baseline", "candidate")
            if (repetition + case_index) % 2 == 0
            else ("candidate", "baseline")
        )
    ]
    for index, item in enumerate(schedule, 1):
        item["index"] = index
    if args.dry_run:
        print(json.dumps(schedule, indent=2))
        return
    if os.environ.get("ARGUS_RUN_LIVE_EVALS") != "1":
        raise SystemExit("Live opt-in required")
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "schedule.json").open("x") as stream:
        json.dump(schedule, stream, indent=2)
        stream.write("\n")
    environment = {
        **os.environ,
        "ARGUS_RUN_LIVE_EVALS": "1",
        "ARGUS_EVAL_ENV_FILE": str(args.candidate / ".env"),
        "ARGUS_RESEARCH_RAIL_ENABLED": "true",
        "ARGUS_MARKET_DATA_PROVIDER_MODE": "live_provider",
        "ARGUS_ASSET_PROVIDER_MODE": "live_provider",
        "ARGUS_ENABLE_PERSONALIZATION_MEMORY": "false",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    for item in schedule:
        label = f"{item['index']:02d}-{item['arm']}-r{item['repetition']}"
        repository = getattr(args, item["arm"])
        destination = args.output / f"{label}.json"
        command = [
            str(args.candidate / ".venv/bin/python"),
            "/private/tmp/registry-case-probe.py",
            "--repository", str(repository),
            "--environment", str(args.candidate / ".env"),
            "--case", item["case"],
            "--label", label,
            "--output", str(destination),
        ]
        print(json.dumps({"started": item, "output": str(destination)}), flush=True)
        with (args.output / f"{label}.log").open("x") as log:
            result = subprocess.run(command, env=environment, stdout=log, stderr=log)
        if result.returncode:
            raise SystemExit(f"Probe {label} stopped with exit {result.returncode}; inspect log before any retry")
        data = json.loads(destination.read_text())
        measured = data["results"][0]
        print(json.dumps({
            "completed": label,
            "status": measured["status"],
            "failed_checks": measured["failed_checks"],
            "elapsed_seconds": data["elapsed_seconds"],
            "provider_usage": data["provider_usage"],
        }), flush=True)
    print("Interleaved partial probes complete; this is not a full-suite scorecard.", flush=True)


if __name__ == "__main__":
    main()
