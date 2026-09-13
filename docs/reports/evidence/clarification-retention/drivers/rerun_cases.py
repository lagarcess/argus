"""Rerun named measurement cases live, judge included, and record results."""
import json, os, sys
from pathlib import Path
ROOT = Path(os.environ["ARGUS_REPO_ROOT"])
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=False)
os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"] = "live_provider"
os.environ["ARGUS_ASSET_PROVIDER_MODE"] = "live_provider"
from argus.domain.market_data.assets import clear_asset_cache
from tests.evals.measurement_eval_harness import load_eval_cases, run_eval_case
clear_asset_cache()
wanted = set(sys.argv[2].split(","))
results = []
for case in load_eval_cases():
    if case.id not in wanted:
        continue
    result = run_eval_case(case, run_prose_judge=True)
    cost = sum(float(r.get("usage_cost_usd") or 0.0) for r in result["route_receipts"])
    result["cost_usd"] = round(cost, 6)
    results.append(result)
    print(f"{case.id}: {result['status']} failed_checks={result['failed_checks']} cost=${cost:.4f}", flush=True)
Path(sys.argv[1]).write_text(json.dumps(results, indent=2, default=str))
print("TOTAL", round(sum(r["cost_usd"] for r in results), 4))
