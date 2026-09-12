"""Live run of the measurement cases whose baseline shows a research call.

Founder direction for PR #593 (2026-09-11): the measured cases run with no user
country and the baseline never sent one, so only the cases that reach research
are re-measured, on the lane head, and compared case by case against the
scorecard the prompt fingerprint names. Paid. Value-free records: status,
failed checks, judge verdict, route receipt outcomes, the research outcome,
each research call's shape, location and invoiced cost, and the run's spend.
The run stops before the next case once its measured spend passes the budget.

Usage (repository root, nothing committed while it runs):
    poetry run python docs/reports/evidence/home-country/drivers/research_cases.py <out.json> [<case_id> ...]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[5]
load_dotenv(ROOT / ".env", override=False)
# Assigned, not defaulted: a value the .env already holds must not win.
os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"] = "live_provider"
os.environ["ARGUS_ASSET_PROVIDER_MODE"] = "live_provider"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from argus.domain.market_data.assets import clear_asset_cache  # noqa: E402
from argus.domain.research import perplexity_agent  # noqa: E402
from argus.domain.research.contracts import ResearchUnavailableError  # noqa: E402
from argus.domain.research.search import perplexity_direct  # noqa: E402

from tests.evals.measurement_eval_harness import load_eval_cases, run_eval_case  # noqa: E402

BUDGET_USD = Decimal("0.90")


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def tracked_clean() -> bool:
    return git("status", "--porcelain", "--untracked-files=no") == ""


fingerprint = json.loads((ROOT / ".agent/interpreter_prompt_fingerprint.json").read_text())
baseline_path = ROOT / fingerprint["last_measured"]["scorecard"]
baseline = {row["id"]: row for row in json.loads(baseline_path.read_text())["results"]}


def baseline_shape(case_id: str) -> str | None:
    research = (baseline[case_id].get("typed_outcome") or {}).get("research")
    return research.get("shape") if isinstance(research, dict) else None


out = Path(sys.argv[1])
requested = sys.argv[2:] or sorted(
    (case_id for case_id in baseline if baseline_shape(case_id)),
    key=lambda case_id: (baseline_shape(case_id) == "find", case_id),
)

calls: list[dict[str, Any]] = []
current_case: dict[str, str] = {"id": ""}
run_research = perplexity_agent.PerplexityAgentClient.run_research
submit_background = perplexity_agent.PerplexityAgentClient.submit_background
direct_search = perplexity_direct.PerplexityDirectProvider.search


def _location(spec: Any) -> str | None:
    return spec.location.country if spec.location is not None else None


def observed_run_research(self: Any, prompt: str, spec: Any) -> Any:
    record = {"case": current_case["id"], "kind": "research", "shape": spec.shape, "location": _location(spec)}
    try:
        packet = run_research(self, prompt, spec)
    except ResearchUnavailableError as exc:
        usage = exc.usage
        calls.append({**record, "error": exc.reason, "model": getattr(usage, "model", None), "cost_usd": getattr(usage, "cost_usd", None)})
        raise
    calls.append({**record, "model": packet.usage.model, "cost_usd": packet.usage.cost_usd})
    return packet


def observed_submit_background(self: Any, prompt: str, spec: Any) -> str:
    calls.append({"case": current_case["id"], "kind": "background_submit", "shape": spec.shape, "location": _location(spec), "cost_usd": None})
    return submit_background(self, prompt, spec)


def observed_direct_search(self: Any, *args: Any, **kwargs: Any) -> Any:
    packet = direct_search(self, *args, **kwargs)
    calls.append({"case": current_case["id"], "kind": "discovery_search", "cost_usd": getattr(packet, "cost_usd", None)})
    return packet


perplexity_agent.PerplexityAgentClient.run_research = observed_run_research
perplexity_agent.PerplexityAgentClient.submit_background = observed_submit_background
perplexity_direct.PerplexityDirectProvider.search = observed_direct_search


def cost(values: list[Any]) -> Decimal:
    return sum((Decimal(str(value)) for value in values if value is not None), Decimal("0"))


start = {"head": git("rev-parse", "HEAD"), "tracked_clean": tracked_clean(), "at": datetime.now(timezone.utc).isoformat()}
clear_asset_cache()
cases = {case.id: case for case in load_eval_cases()}
records: list[dict[str, Any]] = []
spent = Decimal("0")
stopped_for_budget: list[str] = []
for index, case_id in enumerate(requested):
    if spent > BUDGET_USD:
        stopped_for_budget = requested[index:]
        break
    current_case["id"] = case_id
    result = run_eval_case(cases[case_id])
    router_cost = cost([receipt.get("usage_cost_usd") for receipt in result["route_receipts"]])
    research_cost = cost([call["cost_usd"] for call in calls if call["case"] == case_id])
    spent += router_cost + research_cost
    judge = result.get("prose_judge") or {}
    base = baseline[case_id]
    records.append(
        {
            "id": case_id,
            "baseline_shape": baseline_shape(case_id),
            "baseline_status": base["status"],
            "candidate_status": result["status"],
            "verdict": "unchanged" if base["status"] == result["status"] else ("regressed" if result["status"] != "passed" else "fixed"),
            "baseline_failed_checks": base["failed_checks"],
            "candidate_failed_checks": result["failed_checks"],
            "infrastructure_errors": result["infrastructure_errors"],
            "judge": {key: judge.get(key) for key in ("pass", "failed_criteria") if key in judge},
            "receipt_outcomes": [
                {"task": receipt.get("task"), "outcome": receipt.get("outcome"), "failure_mode": receipt.get("failure_mode")}
                for receipt in result["route_receipts"]
            ],
            "research": (result.get("typed_outcome") or {}).get("research"),
            "research_calls": [call for call in calls if call["case"] == case_id],
            "router_cost_usd": float(router_cost),
            "research_cost_usd": float(research_cost),
        }
    )
    print(json.dumps({key: records[-1][key] for key in ("id", "baseline_status", "candidate_status", "verdict")}), f"spent={spent:.4f}", flush=True)

end = {"head": git("rev-parse", "HEAD"), "tracked_clean": tracked_clean(), "at": datetime.now(timezone.utc).isoformat()}
document = {
    "purpose": "research cases only, founder direction on PR #593",
    "baseline_scorecard": str(baseline_path.relative_to(ROOT)),
    "baseline_commit": fingerprint["last_measured"]["commit"],
    "provider_modes": {name: os.environ[name] for name in ("ARGUS_MARKET_DATA_PROVIDER_MODE", "ARGUS_ASSET_PROVIDER_MODE")},
    "start": start,
    "end": end,
    "head_unchanged": start["head"] == end["head"] and start["tracked_clean"] and end["tracked_clean"],
    "requested": requested,
    "stopped_for_budget": stopped_for_budget,
    "verdicts": {verdict: sum(1 for record in records if record["verdict"] == verdict) for verdict in ("unchanged", "fixed", "regressed")},
    "locations_sent": sorted({str(call.get("location")) for call in calls if call["kind"] != "discovery_search"}),
    "spend": {
        "router_reported_usd": float(sum((Decimal(str(r["router_cost_usd"])) for r in records), Decimal("0"))),
        "research_reported_usd": float(cost([call["cost_usd"] for call in calls])),
        "research_calls": len(calls),
        "research_calls_without_cost": sum(1 for call in calls if call["cost_usd"] is None),
        "total_reported_usd": float(spent),
    },
    "records": records,
}
out.write_text(json.dumps(document, indent=2, ensure_ascii=False, default=str) + "\n")
print(json.dumps({key: document[key] for key in ("head_unchanged", "verdicts", "locations_sent", "spend", "stopped_for_budget")}, indent=2))
