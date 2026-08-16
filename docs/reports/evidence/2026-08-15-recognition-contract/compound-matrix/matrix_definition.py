# Compound-edit acceptance matrix for the recognition-contract lane.
#
# Twelve live edit turns against the same pending AAPL/MSFT/NVDA confirmation
# card, tiered by operation count: six single-operation edits, three
# two-operation edits, three edits with three or more operations including
# messy phrasing and Spanish. Each case asserts only the typed facts the turn
# stated; pass requires every stated fact to land and the turn to reach a
# confirmation-ready stage.
#
# Usage:
#   poetry run python temp/compound_matrix.py <side> <round>
# where <side> is "head" or "baseline" (baseline expects PYTHONPATH pointed at
# the frozen 584e9a01 worktree's src). Results are appended as one JSON file
# per (side, round) under temp/matrix/.
from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
os.environ.setdefault("ARGUS_ASSET_PROVIDER_MODE", "live_provider")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(".env"), override=False)

import argus  # noqa: E402

_EXPECTED_SIDE = sys.argv[2] if len(sys.argv) > 2 else ""
_SIDE_ARG = sys.argv[1] if len(sys.argv) > 1 else ""
_IS_BASELINE = "baseline" in (_SIDE_ARG, _EXPECTED_SIDE)
_ARGUS_PATH = str(Path(argus.__file__).resolve())
if _IS_BASELINE:
    assert "argus-baseline" in _ARGUS_PATH, f"baseline side imported {_ARGUS_PATH}"
else:
    assert "argus-baseline" not in _ARGUS_PATH, f"head side imported {_ARGUS_PATH}"
print(f"import-provenance ok: {_ARGUS_PATH}", file=sys.stderr)

from tests.evals.measurement_eval_harness import (  # noqa: E402
    load_eval_cases,
    run_eval_case,
)


def _assets(outcome: dict) -> set[str]:
    return {str(s).upper() for s in (outcome.get("assets") or [])}


def _capital(outcome: dict) -> float | None:
    value = outcome.get("capital_amount")
    return float(value) if value is not None else None


def _benchmark(outcome: dict) -> str | None:
    value = outcome.get("benchmark_symbol")
    return str(value).upper() if value else None


def _requested_start(outcome: dict) -> str | None:
    window = outcome.get("requested_date_range") or {}
    if isinstance(window, dict):
        return window.get("start")
    return None


def _requested_end(outcome: dict) -> str | None:
    window = outcome.get("requested_date_range") or {}
    if isinstance(window, dict):
        return window.get("end")
    return None


def _confirmed(outcome: dict) -> bool:
    stages = outcome.get("stage_outcomes") or []
    return "ready_for_confirmation" in stages or "await_approval" in stages


# Card facts: AAPL/MSFT/NVDA, 2024 calendar year, SPY benchmark, $1,000.
MATRIX = [
    # --- tier 1: one operation ---
    ("t1_remove", "en", "remove AAPL", [
        ("assets", lambda o: _assets(o) == {"MSFT", "NVDA"}),
    ]),
    ("t1_add", "en", "add TSLA", [
        ("assets", lambda o: _assets(o) == {"AAPL", "MSFT", "NVDA", "TSLA"}),
    ]),
    ("t1_replace", "en", "replace MSFT with GOOGL", [
        ("assets", lambda o: _assets(o) == {"AAPL", "GOOGL", "NVDA"}),
    ]),
    ("t1_benchmark", "en", "change the benchmark to QQQ", [
        ("benchmark", lambda o: _benchmark(o) == "QQQ"),
        ("assets_kept", lambda o: _assets(o) == {"AAPL", "MSFT", "NVDA"}),
    ]),
    ("t1_date", "en", "change the dates to 2023", [
        ("start", lambda o: _requested_start(o) == "2023-01-01"),
        ("end", lambda o: _requested_end(o) == "2023-12-31"),
        ("assets_kept", lambda o: _assets(o) == {"AAPL", "MSFT", "NVDA"}),
    ]),
    ("t1_capital", "en", "make it $5,000", [
        ("capital", lambda o: _capital(o) == 5000),
        ("assets_kept", lambda o: _assets(o) == {"AAPL", "MSFT", "NVDA"}),
    ]),
    # --- tier 2: two operations ---
    ("t2_remove_add", "en", "remove AAPL and add TSLA", [
        ("assets", lambda o: _assets(o) == {"MSFT", "NVDA", "TSLA"}),
    ]),
    ("t2_bench_date", "en",
     "change the benchmark to QQQ and change the start to April 1, 2024", [
        ("benchmark", lambda o: _benchmark(o) == "QQQ"),
        ("start", lambda o: _requested_start(o) == "2024-04-01"),
        ("assets_kept", lambda o: _assets(o) == {"AAPL", "MSFT", "NVDA"}),
    ]),
    ("t2_es_remove_capital", "es-419", "quita AAPL y cambia el capital a $2,500", [
        ("assets", lambda o: _assets(o) == {"MSFT", "NVDA"}),
        ("capital", lambda o: _capital(o) == 2500),
    ]),
    # --- tier 3: three or more operations, messy phrasing, Spanish ---
    ("t3_remove_add_date", "en",
     "remove AAPL, add TSLA, and change the start to April 1, 2024", [
        ("assets", lambda o: _assets(o) == {"MSFT", "NVDA", "TSLA"}),
        ("start", lambda o: _requested_start(o) == "2024-04-01"),
    ]),
    ("t3_messy_four_ops", "en",
     "ok so ummm drop AAPL, throw in TSLA and GOOGL instead, "
     "make the benchmark QQQ and lets do $10k", [
        ("assets", lambda o: _assets(o) == {"MSFT", "NVDA", "TSLA", "GOOGL"}),
        ("benchmark", lambda o: _benchmark(o) == "QQQ"),
        ("capital", lambda o: _capital(o) == 10000),
    ]),
    ("t3_es_four_ops", "es-419",
     "quita AAPL, agrega TSLA, cambia el benchmark a QQQ y usa $5,000", [
        ("assets", lambda o: _assets(o) == {"MSFT", "NVDA", "TSLA"}),
        ("benchmark", lambda o: _benchmark(o) == "QQQ"),
        ("capital", lambda o: _capital(o) == 5000),
    ]),
]


def main() -> None:
    side = sys.argv[1]
    round_label = sys.argv[2]
    template = next(
        case
        for case in load_eval_cases()
        if case.id == "action_chip_change_asset_remove_aapl_issue_188"
    )
    results = []
    for case_id, language, prompt, checks in MATRIX:
        case = dataclasses.replace(
            template,
            id=f"matrix_{case_id}",
            followup_prompt=prompt,
            user_language=language,
            ui_language=language,
            prose_judge_criteria=(),
        )
        result = run_eval_case(case, run_prose_judge=False)
        outcome = result["typed_outcome"]
        failed = [name for name, check in checks if not check(outcome)]
        if not _confirmed(outcome):
            failed.append("stage_not_confirmation_ready")
        results.append(
            {
                "case": case_id,
                "tier": case_id.split("_")[0],
                "language": language,
                "prompt": prompt,
                "passed": not failed,
                "failed_checks": failed,
                "observed": {
                    "assets": sorted(_assets(outcome)),
                    "benchmark": _benchmark(outcome),
                    "capital": _capital(outcome),
                    "start": _requested_start(outcome),
                    "end": _requested_end(outcome),
                    "stage_outcomes": outcome.get("stage_outcomes"),
                    "intent": outcome.get("intent"),
                    "reason_codes_present": bool(outcome.get("semantic_turn_act")),
                },
            }
        )
        status = "PASS" if not failed else f"FAIL {failed}"
        print(f"[{side} r{round_label}] {case_id}: {status}", flush=True)
    dest = Path(f"temp/matrix/{side}_round{round_label}.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(results, indent=1))
    tally = sum(1 for r in results if r["passed"])
    print(f"[{side} r{round_label}] total {tally}/{len(results)} -> {dest}")


if __name__ == "__main__":
    main()
