"""Case-by-case comparison of a live scorecard against the fingerprint's
baseline scorecard (AGENTS.md Never-Violate 12).
Usage: python compare_baseline.py <candidate_scorecard.json> <out.json>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

fingerprint = json.loads(Path(".agent/interpreter_prompt_fingerprint.json").read_text())
baseline_path = Path(fingerprint["last_measured"]["scorecard"])
baseline = json.loads(baseline_path.read_text())
candidate = json.loads(Path(sys.argv[1]).read_text())


def by_id(scorecard: dict) -> dict[str, dict]:
    return {r["id"]: r for r in scorecard["results"]}


base, cand = by_id(baseline), by_id(candidate)
rows = []
for case_id in sorted(set(base) | set(cand)):
    b, c = base.get(case_id), cand.get(case_id)
    row = {
        "id": case_id,
        "baseline_status": b["status"] if b else "absent",
        "candidate_status": c["status"] if c else "absent",
        "baseline_failed_checks": b["failed_checks"] if b else None,
        "candidate_failed_checks": c["failed_checks"] if c else None,
    }
    if b and c:
        row["verdict"] = (
            "unchanged" if b["status"] == c["status"]
            else "regressed" if c["status"] != "passed"
            else "fixed"
        )
    else:
        row["verdict"] = "added" if c else "removed"
    rows.append(row)
summary = {
    "baseline_scorecard": str(baseline_path),
    "baseline_commit": fingerprint["last_measured"]["commit"],
    "candidate_sha": candidate["provenance"]["candidate_sha"],
    "baseline_totals": baseline["totals"],
    "candidate_totals": candidate["totals"],
    "verdicts": {v: sum(1 for r in rows if r["verdict"] == v) for v in ("unchanged", "fixed", "regressed", "added", "removed")},
    "regressed": [r["id"] for r in rows if r["verdict"] == "regressed"],
    "rows": rows,
}
Path(sys.argv[2]).write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({k: summary[k] for k in ("baseline_totals", "candidate_totals", "verdicts", "regressed")}, indent=2))
