"""Summarize a route check capture: per step, what the model read and what came back.

Reads the server and driver captures in ROUTE_CHECK_OUT and writes
route-check-report.json and route-check-report.md beside them. Steps and
retries form one timeline; a step's window runs from its request until the next
entry starts, so asynchronous artifact naming after a turn is attributed to
that turn and a retry never borrows the first attempt's calls.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

OUT = Path(os.environ.get("ROUTE_CHECK_OUT") or sys.argv[1]).resolve()
RETIRED_SENTENCE = "Ready to test"


def _jsonl(name: str) -> list[dict[str, Any]]:
    path = OUT / f"{name}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _in(row: dict[str, Any], start: float, end: float) -> bool:
    return start <= row["ts"] < end


def _history_messages(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"shape": type(body).__name__}
    model = body.get("model")
    raw = body.get("messages")
    if not isinstance(raw, list):
        return {"model": model, "shape": sorted(body.keys())}
    turns = []
    for message in raw:
        if not isinstance(message, dict) or message.get("role") == "system":
            continue
        content = message.get("content")
        if isinstance(content, list):
            content = " ".join(str(part.get("text", part)) for part in content if isinstance(part, dict))
        turns.append({"role": message.get("role"), "content": content})
    return {"model": model, "non_system_messages": turns}


def _mentions(text: str, *needles: str) -> bool:
    lowered = (text or "").lower()
    return any(needle.lower() in lowered for needle in needles)


def _conversation_id(entry: dict[str, Any]) -> str | None:
    return next((m["conversation_id"] for m in entry.get("messages") or [] if m.get("conversation_id")), None)


def main() -> None:
    driver = _jsonl("driver")
    steps = [row for row in driver if not row.get("stopped_for_cap")]
    retries = [row for row in _jsonl("driver-retries") if not row.get("stopped_for_cap")]
    stops = [row for row in [*driver, *_jsonl("driver-retries")] if row.get("stopped_for_cap")]
    timeline = sorted([*steps, *retries], key=lambda row: row["started"])
    history = _jsonl("thread_history")
    naming_in = _jsonl("naming_input")
    naming_out = _jsonl("naming_output")
    requests = _jsonl("model_requests")
    receipts = _jsonl("receipts")
    research = _jsonl("research_costs")

    report_steps = []
    for index, step in enumerate(timeline):
        start = step["started"]
        end = timeline[index + 1]["started"] if index + 1 < len(timeline) else float("inf")
        conversation_id = _conversation_id(step)
        window_requests = [r for r in requests if _in(r, start, end)]
        window_receipts = [
            {
                key: r["receipt"].get(key)
                for key in ("task", "model", "outcome", "failure_mode", "usage_cost_usd")
                if key in r["receipt"]
            }
            for r in receipts
            if _in(r, start, end)
        ]
        report_steps.append(
            {
                "language": step["language"],
                "step": step["step"],
                "retry": step["step"].endswith("_retry"),
                "retry_reason": step.get("reason"),
                "request": step.get("request") or {"message": None},
                "status": step.get("status"),
                "stages": step.get("stages"),
                "reply": step.get("reply"),
                "recovery": (step.get("final") or {}).get("recovery"),
                "latest_card": step.get("latest_card"),
                "result_run": _result_run(step),
                "title": step.get("title"),
                "history_loaded": [
                    {"reader": h["reader"], "history": h["history"]}
                    for h in history
                    if _in(h, start, end) and h.get("conversation_id") == conversation_id
                ],
                "naming_input": [n for n in naming_in if _in(n, start, end)],
                "naming_output": [n for n in naming_out if _in(n, start, end)],
                "model_calls": [
                    {"host": r["host"], "status": r.get("status", r.get("error")), **_history_messages(r.get("body"))}
                    for r in window_requests
                ],
                "receipts": window_receipts,
                "provider_failures": [r for r in window_receipts if r.get("outcome") not in {"succeeded", "skipped"}],
                "research_costs": [r for r in research if _in(r, start, end)],
                "retired_sentence_in_model_input": any(
                    RETIRED_SENTENCE in json.dumps(r.get("body"), ensure_ascii=False) for r in window_requests
                ),
                "spend_after": step.get("spend_after"),
            }
        )

    checks = _checks(report_steps)
    report = {
        "server": json.loads((OUT / "server.json").read_text()) if (OUT / "server.json").exists() else None,
        "stopped_for_cap": stops,
        "checks": checks,
        "failed_checks": [c for c in checks if not c["pass"]],
        "retired_sentence_in_any_model_input": any(s["retired_sentence_in_model_input"] for s in report_steps),
        "final_spend": report_steps[-1]["spend_after"] if report_steps else None,
        "steps": report_steps,
    }
    (OUT / "route-check-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    (OUT / "route-check-report.md").write_text(_markdown(report))
    print(
        json.dumps(
            {
                "checks": [{k: c[k] for k in ("language", "check", "pass")} for c in checks],
                "stopped_for_cap": stops,
                "final_spend": report["final_spend"],
                "retired_sentence_in_any_model_input": report["retired_sentence_in_any_model_input"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _result_run(step: dict[str, Any]) -> dict[str, Any] | None:
    run = (step.get("final") or {}).get("run")
    if isinstance(run, dict):
        return {"id": run.get("id"), "status": run.get("status"), "symbols": run.get("symbols")}
    return None


def _answers_result(step: dict[str, Any] | None) -> bool:
    reply = (step or {}).get("reply") or ""
    return bool(reply) and _mentions(reply, "SPY") and _mentions(reply, "AAPL", "Apple") and not (step or {}).get("recovery")


def _checks(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    by_language: dict[str, dict[str, dict[str, Any]]] = {}
    for step in steps:
        by_language.setdefault(step["language"], {})[step["step"]] = step
    for language, named in by_language.items():
        card = (named.get("card") or {}).get("latest_card")
        checks.append({"language": language, "check": "card created with AAPL buy and hold at $10000", "pass": bool(card and card.get("symbols") == ["AAPL"] and card.get("strategy_type") == "buy_and_hold" and card.get("capital") == 10000), "observed": card})
        change = named.get("change")
        if change is not None:
            changed = change.get("latest_card")
            kept = bool(card and changed and all(changed.get(key) == card.get(key) for key in ("strategy_type", "symbols", "date_range")))
            checks.append({"language": language, "check": "input change keeps asset, strategy and dates and sets $5000", "pass": bool(kept and changed.get("capital") == 5000 and changed.get("message_id") != card.get("message_id")), "observed": changed})
        run = named.get("run")
        if run is not None:
            checks.append({"language": language, "check": "run produced a result", "pass": run.get("result_run") is not None, "observed": run.get("result_run")})
        for name, label in (("result_question", "result question"), ("result_question_retry", "retry of the result question")):
            question = named.get(name)
            if question is None:
                continue
            checks.append(
                {
                    "language": language,
                    "check": f"{label} answered about Apple against SPY",
                    "pass": _answers_result(question),
                    "observed": {"reply": question.get("reply"), "recovery": question.get("recovery"), "provider_failures": question.get("provider_failures")},
                }
            )
    return checks


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# Route check report", ""]
    server = report.get("server") or {}
    lines += [f"Source head `{server.get('source_head')}`, working tree changes under src or web: {server.get('working_tree_changes_under_src_or_web')}.", ""]
    spend = report.get("final_spend") or {}
    lines += [f"Billed ${spend.get('billed_usd')}; unpriced receipts {spend.get('unpriced_receipts')}; unpriced research calls {spend.get('unpriced_research_calls')}; cap ceiling ${spend.get('ceiling_usd')}.", ""]
    lines += [f"Retired sentence in any model input: {report.get('retired_sentence_in_any_model_input')}.", ""]
    lines += ["## Checks", ""]
    for check in report["checks"]:
        lines.append(f"- {'PASS' if check['pass'] else 'FAIL'} ({check['language']}): {check['check']}")
    for step in report["steps"]:
        lines += ["", f"## {step['language']} / {step['step']}", ""]
        if step.get("retry_reason"):
            lines.append(f"Retry reason: {step['retry_reason']}")
        request = step.get("request") or {}
        lines.append(f"Request: {request.get('message') or (request.get('action') or {}).get('type')}")
        if step.get("title"):
            lines.append(f"Title after the step: {step['title'].get('title')} ({step['title'].get('title_source')})")
        lines.append(f"Reply: {step.get('reply')}")
        if step.get("recovery"):
            lines.append(f"Recovery: {json.dumps(step['recovery'], ensure_ascii=False)}")
        for failure in step.get("provider_failures") or []:
            lines.append(f"Provider failure: {json.dumps(failure, ensure_ascii=False)}")
        if step.get("latest_card"):
            lines.append(f"Latest card: {json.dumps(step['latest_card'], ensure_ascii=False)}")
        if step.get("result_run"):
            lines.append(f"Result: {json.dumps(step['result_run'], ensure_ascii=False)}")
        for loaded in step["history_loaded"]:
            lines.append(f"History loaded by {loaded['reader']}:")
            for item in loaded["history"]:
                lines.append(f"  - {item['role']}: {item['content']}")
        for naming in step["naming_input"]:
            lines.append(f"Naming input ({naming.get('source')}):")
            lines += [f"  {line}" for line in str(naming.get("context") or "").splitlines()]
        for naming in step["naming_output"]:
            lines.append(f"Naming output: {naming.get('name')} ({naming.get('language')})")
        for call in step["model_calls"]:
            messages = call.get("non_system_messages")
            if messages is None:
                continue
            lines.append(f"Model call to {call.get('model')} (status {call.get('status')}):")
            for message in messages:
                content = str(message.get("content"))
                lines.append(f"  - {message.get('role')}: {content[:600]}{'...' if len(content) > 600 else ''}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
