"""Re-run named measurement cases once through the harness of the tree named
by D10_TREE (the lane head, or the pinned base without this lane's changes),
so a flaky verdict is told apart from a regression. Value-free records: status,
failed checks, judge verdict and receipt outcomes. Paid.
Usage: python rerun_cases.py <label> <out.json> <case_id> [<case_id> ...]"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

TREE = Path(os.environ["D10_TREE"]).resolve()
load_dotenv(os.environ.get("D10_ENV_FILE") or TREE / ".env", override=False)
os.environ.setdefault("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
os.environ.setdefault("ARGUS_ASSET_PROVIDER_MODE", "live_provider")
os.environ["ARGUS_RESEARCH_RAIL_ENABLED"] = "true"
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(TREE / "src"))
from tests.evals.measurement_eval_harness import load_eval_cases, run_eval_case  # noqa: E402

label, out, *case_ids = sys.argv[1:]
cases = {c.id: c for c in load_eval_cases()}
records = []
for case_id in case_ids:
    case = cases[case_id]
    result = run_eval_case(case)
    judge = result.get("prose_judge") or {}
    records.append(
        {
            "id": case_id,
            "status": result["status"],
            "failed_checks": result["failed_checks"],
            "infrastructure_errors": result["infrastructure_errors"],
            "judge": {k: judge.get(k) for k in ("pass", "failed_criteria", "rubric_version") if k in judge},
            "receipt_outcomes": [
                {"task": r.get("task"), "schema": r.get("schema_name"), "outcome": r.get("outcome"), "failure_mode": r.get("failure_mode")}
                for r in result["route_receipts"]
            ],
            "research": (result.get("typed_outcome") or {}).get("research"),
        }
    )
    print(json.dumps({k: records[-1][k] for k in ("id", "status", "failed_checks")}, ensure_ascii=False))
Path(out).write_text(
    json.dumps(
        {
            "label": label,
            "tree": str(TREE),
            "candidate_sha": subprocess.check_output(["git", "-C", str(TREE), "rev-parse", "HEAD"], text=True).strip(),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "records": records,
        },
        indent=2,
        ensure_ascii=False,
        default=str,
    )
    + "\n"
)
