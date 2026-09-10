"""Build the before/after markdown table from the recorded turns.
Usage: python table.py <before_dir> <after_dir>"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def rows(folder: Path) -> dict[str, dict]:
    out = {}
    for path in sorted(folder.glob("*.json")):
        record = json.loads(path.read_text())
        out[record["label"]] = record["summary"]
    return out


def cell(summary: dict | None) -> str:
    if summary is None:
        return "not run"
    if summary.get("answered"):
        verdict = "answered"
    elif summary.get("clarification_reason_code"):
        verdict = f"refused: {summary['clarification_kind']}/{summary['clarification_reason_code']}"
    elif summary.get("recovery_code"):
        verdict = f"recovery: {summary['recovery_code']}"
    else:
        verdict = "no answer"
    fired = ", ".join(summary.get("reason_codes") or []) or "no reason codes"
    shape = summary.get("shape") or "no research"
    degraded = (summary.get("degraded") or {}).get("code")
    usage = summary.get("research_usage") or {}
    cost = usage.get("cost_usd")
    cost_text = f"${cost:.3f}" if isinstance(cost, (int, float)) else "n/a"
    text = (summary.get("assistant_text") or "").replace("\n", " ").strip()
    if len(text) > 220:
        text = text[:217] + "..."
    parts = [verdict, fired, shape + (f" ({degraded})" if degraded else ""), f"{len(summary.get('sources') or [])} sources", cost_text, f"{summary.get('elapsed_seconds')}s", text]
    return " · ".join(str(p) for p in parts)


before, after = rows(Path(sys.argv[1])), rows(Path(sys.argv[2])) if len(sys.argv) > 2 else {}
questions = json.loads((Path(__file__).parent / "questions.json").read_text())
print("| Question | Before (integration d0884c3d) | After (lane head) |")
print("| --- | --- | --- |")
for row in questions:
    print(f"| {row['question']} | {cell(before.get(row['id']))} | {cell(after.get(row['id']))} |")
