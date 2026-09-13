"""Run one measurement case live through the harness and record its result."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

TREE = Path(os.environ["OTG_TREE"]).resolve()
load_dotenv(TREE / ".env", override=False)
os.environ.setdefault("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
os.environ.setdefault("ARGUS_ASSET_PROVIDER_MODE", "live_provider")
os.environ["ARGUS_RESEARCH_RAIL_ENABLED"] = "true"
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(TREE / "src"))
from tests.evals.measurement_eval_harness import load_eval_cases, run_eval_case  # noqa: E402

case_id, out = sys.argv[1:3]
case = next(c for c in load_eval_cases() if c.id == case_id)
result = run_eval_case(case)
record = {
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "candidate_sha": subprocess.check_output(["git", "-C", str(TREE), "rev-parse", "HEAD"], text=True).strip(),
    "case": case.raw,
    "result": result,
}
Path(out).write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str))
print(json.dumps({k: result[k] for k in ("id", "status", "failed_checks", "infrastructure_errors")}, indent=2))
print("research:", json.dumps(result["typed_outcome"].get("research")))
print("prose_judge:", json.dumps(result.get("prose_judge"))[:400])
