"""Run named measurement cases once, live, through the harness of the tree named
by I590_TREE, and write a value-free record: status, failed checks, the offered
next-experiment kinds, the assistant text, receipt outcomes and billed cost.
Both provider modes are assigned outright after loading the env file (the
integration .env pins synthetic market data; setdefault would keep it). Paid.
Usage: I590_TREE=<tree> I590_ENV_FILE=<env> python run_case.py <label> <out.json> <case_id>..."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

TREE = Path(os.environ["I590_TREE"]).resolve()
load_dotenv(os.environ["I590_ENV_FILE"], override=False)
os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"] = "live_provider"
os.environ["ARGUS_ASSET_PROVIDER_MODE"] = "live_provider"
os.environ["ARGUS_RESEARCH_RAIL_ENABLED"] = "true"
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(TREE / "src"))
from tests.evals.measurement_eval_harness import (  # noqa: E402
    load_eval_cases,
    run_eval_case,
)

label, out, *case_ids = sys.argv[1:]
cases = {case.id: case for case in load_eval_cases()}
records = []
for case_id in case_ids:
    result = run_eval_case(cases[case_id])
    typed = result.get("typed_outcome") or {}
    offered = typed.get("offered") or {}
    receipts = result["route_receipts"]
    records.append(
        {
            "id": case_id,
            "status": result["status"],
            "failed_checks": result["failed_checks"],
            "infrastructure_errors": result["infrastructure_errors"],
            "semantic_turn_act": typed.get("semantic_turn_act"),
            "intent": typed.get("intent"),
            "result_followup_focus": typed.get("result_followup_focus"),
            "reason_codes": typed.get("reason_codes"),
            "stage_outcomes": typed.get("stage_outcomes"),
            "next_experiment_kinds": offered.get("next_experiment_kinds"),
            "recovery_code": offered.get("recovery_code"),
            "assistant_text": typed.get("assistant_text")
            or typed.get("assistant_response"),
            "receipt_outcomes": [
                {
                    "task": r.get("task"),
                    "schema": r.get("schema_name"),
                    "outcome": r.get("outcome"),
                    "failure_mode": r.get("failure_mode"),
                    "usage_cost_usd": r.get("usage_cost_usd"),
                }
                for r in receipts
            ],
            "billed_cost_usd": round(
                sum(float(r.get("usage_cost_usd") or 0.0) for r in receipts), 6
            ),
        }
    )
    print(
        json.dumps(
            {
                k: records[-1][k]
                for k in (
                    "id",
                    "status",
                    "failed_checks",
                    "next_experiment_kinds",
                    "billed_cost_usd",
                )
            },
            ensure_ascii=False,
        )
    )
Path(out).parent.mkdir(parents=True, exist_ok=True)
Path(out).write_text(
    json.dumps(
        {
            "label": label,
            "tree": str(TREE),
            "candidate_sha": subprocess.check_output(
                ["git", "-C", str(TREE), "rev-parse", "HEAD"], text=True
            ).strip(),
            "market_data_provider_mode": os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"],
            "asset_provider_mode": os.environ["ARGUS_ASSET_PROVIDER_MODE"],
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "records": records,
            "billed_cost_usd": round(sum(r["billed_cost_usd"] for r in records), 6),
        },
        indent=2,
        ensure_ascii=False,
        default=str,
    )
    + "\n"
)
