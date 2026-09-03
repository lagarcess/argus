"""Replay one recorded candidate prose verdict without rerunning the product."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tests.evals.measurement_eval_harness import (
    PROSE_JUDGE_RUBRIC_VERSION,
    judge_prose_quality,
    load_eval_cases,
)


def _recorded_text(record: dict[str, Any], *, label: str) -> str:
    if record.get("truncated") is not False:
        raise ValueError(f"{label} is truncated and cannot be replayed exactly")
    if record.get("redactions") not in ({}, []):
        raise ValueError(f"{label} is redacted and cannot be replayed exactly")
    text = str(record.get("text") or "")
    if not text:
        raise ValueError(f"{label} is empty")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if digest != record.get("sha256"):
        raise ValueError(f"{label} digest does not match the scorecard")
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scorecard", type=Path)
    parser.add_argument("case_id")
    parser.add_argument("output", type=Path)
    parser.add_argument("--runs", type=int, default=20)
    args = parser.parse_args()

    if args.runs < 1:
        raise ValueError("runs must be positive")

    scorecard = json.loads(args.scorecard.read_text(encoding="utf-8"))
    scorecard_results = {
        str(result["id"]): result for result in scorecard.get("results", [])
    }
    recorded_result = scorecard_results[args.case_id]
    prose_judge = recorded_result["prose_judge"]
    assistant_text = _recorded_text(
        prose_judge["judged_assistant_text"],
        label="judged assistant text",
    )
    rendered_text = _recorded_text(
        prose_judge["judged_rendered_context"],
        label="judged rendered context",
    )
    rendered_context = json.loads(rendered_text)
    cases = {case.id: case for case in load_eval_cases()}
    case = cases[args.case_id]

    verdicts: list[dict[str, Any]] = []
    for index in range(args.runs):
        verdict = judge_prose_quality(
            case=case,
            assistant_text=assistant_text,
            rendered_beside_reply=rendered_context,
        )
        verdicts.append(
            {
                "attempt": index + 1,
                "pass": bool(verdict["pass"]),
                "failed_criteria": list(verdict["failed_criteria"]),
                "notes": str(verdict.get("notes") or ""),
            }
        )
        state = "PASS" if verdict["pass"] else "FAIL"
        print(f"replay={index + 1}/{args.runs} verdict={state}", flush=True)

    output = {
        "case_id": args.case_id,
        "question": "Does the recorded candidate prose fail consistently when the product output and rendered context are held fixed?",
        "method": "Judge-only replay of the scorecard's exact retained assistant text and rendered context. The product is not rerun.",
        "rubric_version": PROSE_JUDGE_RUBRIC_VERSION,
        "scorecard": str(args.scorecard),
        "candidate_sha": scorecard["provenance"]["candidate_sha"],
        "recorded_status": recorded_result["status"],
        "recorded_failed_checks": list(recorded_result["failed_checks"]),
        "assistant_text_sha256": prose_judge["judged_assistant_text"]["sha256"],
        "rendered_context_sha256": prose_judge["judged_rendered_context"]["sha256"],
        "runs": args.runs,
        "passes": sum(1 for verdict in verdicts if verdict["pass"]),
        "failures": sum(1 for verdict in verdicts if not verdict["pass"]),
        "verdicts": verdicts,
    }
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
