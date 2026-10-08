"""Count provider-call reservations per turn in the accepted #600 measurement.

A reservation is every receipt except the clarifier's post-hoc
contract_violation record and the prose judge, which production never calls.
Turns split where the follow-up turn's asset preflight starts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
MEASUREMENT = ROOT / "docs/reports/evidence/current-reason-date-range/accepted-measurement/live-measurement.json"
ALLOWANCE = 7


def followup_ids() -> set[str]:
    ids = set()
    for path in (ROOT / "tests/evals/measurement_cases").glob("*.yaml"):
        for case in yaml.safe_load(path.read_text())["cases"]:
            if case.get("followup_prompt"):
                ids.add(case["id"])
    return ids


def is_reservation(receipt: dict) -> bool:
    if receipt.get("schema_name") == "ArgusProseJudgeResponse":
        return False
    return not (
        receipt["outcome"] == "failed"
        and receipt.get("failure_mode") == "contract_violation"
        and receipt.get("latency_ms") == 0
    )


def split_turns(receipts: list[dict], has_followup: bool) -> list[list[dict]]:
    if not has_followup:
        return [receipts]
    starts = [i for i, r in enumerate(receipts) if r["task"] == "asset_mention_preflight"]
    if len(starts) < 2:
        return [receipts]
    return [receipts[: starts[1]], receipts[starts[1] :]]


def label(receipt: dict) -> str:
    return f"{receipt['task']}:{receipt.get('schema_name')}:{receipt['model'].split('/')[-1]}:{receipt['outcome']}"


def main() -> None:
    results = json.loads(MEASUREMENT.read_text())["results"]
    followups = followup_ids()
    for result in results:
        calls = [r for r in result["route_receipts"] if is_reservation(r)]
        turns = split_turns(calls, result["id"] in followups)
        counts = [len(turn) for turn in turns]
        if max(counts, default=0) <= ALLOWANCE and "-v" not in sys.argv:
            continue
        print(f"{result['id']} status={result['status']} per_turn={counts} total={sum(counts)}")
        for index, turn in enumerate(turns, 1):
            if len(turn) > ALLOWANCE or "-v" in sys.argv:
                for position, receipt in enumerate(turn, 1):
                    flag = "  DENIED" if position > ALLOWANCE else ""
                    print(f"    t{index}.{position} {label(receipt)}{flag}")


if __name__ == "__main__":
    main()
