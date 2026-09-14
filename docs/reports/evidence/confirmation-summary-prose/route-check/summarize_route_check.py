"""Build the route check report from the committed capture files.

Reads `steps.jsonl` and the server captures in ROUTE_CHECK_OUT and writes
route-check-report.json and route-check-report.md beside them. For each step the
report shows what the step row recorded (request, reply, recovery, card facts,
title), the history loads and naming records in the step's window, and the
status, receipts and non-system messages of each captured model request in that
window. A step's window runs from its request until the next step starts, by
record write time; only history loads are matched to a conversation. Totals
count the server's records over the whole capture. The report covers only what
these files record.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

OUT = Path(os.environ.get("ROUTE_CHECK_OUT") or sys.argv[1]).resolve()
RETIRED_SENTENCE = "Ready to test"
TYPED_CARD_TURN = '{"confirmation_card":'
MESSAGE_CHARACTERS_SHOWN = 600


def _jsonl(name: str) -> list[dict[str, Any]]:
    path = OUT / f"{name}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _in(row: dict[str, Any], start: float, end: float) -> bool:
    return start <= row["ts"] < end


def _content_text(content: Any) -> str:
    if isinstance(content, list):
        return " ".join(str(part.get("text", part)) for part in content if isinstance(part, dict))
    return "" if content is None else str(content)


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
        turns.append({"role": message.get("role"), "content": _content_text(message.get("content"))})
    return {"model": model, "non_system_messages": turns}


def _message_text(body: Any) -> str:
    raw = body.get("messages") if isinstance(body, dict) else None
    if not isinstance(raw, list):
        return ""
    return "\n".join(_content_text(message.get("content")) for message in raw if isinstance(message, dict))


def _mentions(text: str, *needles: str) -> bool:
    lowered = (text or "").lower()
    return any(needle.lower() in lowered for needle in needles)


def main() -> None:
    stream = _jsonl("steps")
    stops = [row for row in stream if row.get("stopped_for_cap")]
    timeline = sorted((row for row in stream if not row.get("stopped_for_cap")), key=lambda row: row["started"])
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
        conversation_id = step.get("conversation_id")
        final = step.get("final") or {}
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
        run = final.get("run")
        report_steps.append(
            {
                "language": step["language"],
                "step": step["step"],
                "retry": step["step"].endswith("_retry"),
                "request": step.get("request") or {"message": None},
                "status": step.get("status"),
                "stages": step.get("stages"),
                "reply": step.get("reply"),
                "recovery": final.get("recovery"),
                "latest_card": step.get("latest_card"),
                "result_run": {key: run.get(key) for key in ("id", "status", "symbols")} if isinstance(run, dict) else None,
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
                "receipts_not_succeeded_or_skipped": [
                    r for r in window_receipts if r.get("outcome") not in {"succeeded", "skipped"}
                ],
                "research_costs": [r for r in research if _in(r, start, end)],
                "retired_sentence_in_captured_model_requests": any(
                    RETIRED_SENTENCE in json.dumps(r.get("body"), ensure_ascii=False) for r in window_requests
                ),
            }
        )
    for step in report_steps:
        if step["retry"]:
            first_attempt = next(
                (
                    other
                    for other in report_steps
                    if other["language"] == step["language"] and other["step"] == step["step"].removesuffix("_retry")
                ),
                None,
            )
            step["first_attempt_recovery"] = (first_attempt or {}).get("recovery")

    checks = _checks(report_steps)
    report = {
        "server": json.loads((OUT / "server.json").read_text()) if (OUT / "server.json").exists() else None,
        "stopped_for_cap": stops,
        "totals": _totals(requests, receipts, research, history, naming_in, naming_out),
        "checks": checks,
        "failed_checks": [c for c in checks if not c["pass"]],
        "steps": report_steps,
    }
    (OUT / "route-check-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    (OUT / "route-check-report.md").write_text(_markdown(report))
    print(
        json.dumps(
            {
                "steps": len(report_steps),
                "checks": [{k: c[k] for k in ("language", "check", "pass")} for c in checks],
                "stopped_for_cap": stops,
                "totals": report["totals"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _totals(
    requests: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    research: list[dict[str, Any]],
    history: list[dict[str, Any]],
    naming_in: list[dict[str, Any]],
    naming_out: list[dict[str, Any]],
) -> dict[str, Any]:
    assistant_items = [
        _content_text(item.get("content")) for load in history for item in load["history"] if item.get("role") == "assistant"
    ]
    priced = [r["receipt"]["usage_cost_usd"] for r in receipts if r["receipt"].get("usage_cost_usd") is not None]
    research_priced = [r["cost_usd"] for r in research if r.get("cost_usd") is not None]
    return {
        "captured_model_requests": len(requests),
        "captured_model_requests_by_host": dict(Counter(str(r.get("host")) for r in requests)),
        "captured_model_requests_by_status": dict(Counter(str(r.get("status", r.get("error"))) for r in requests)),
        "captured_model_requests_containing_a_typed_card_turn": sum(
            1 for r in requests if TYPED_CARD_TURN in _message_text(r.get("body"))
        ),
        "captured_model_requests_containing_the_retired_sentence": sum(
            1 for r in requests if RETIRED_SENTENCE in json.dumps(r.get("body"), ensure_ascii=False)
        ),
        "receipts": len(receipts),
        "receipts_by_task_and_outcome": dict(
            sorted(Counter(f"{r['receipt'].get('task')}: {r['receipt'].get('outcome')}" for r in receipts).items())
        ),
        "priced_receipts_usd": round(sum(priced), 6),
        "unpriced_receipts": len(receipts) - len(priced),
        "research_cost_records": len(research),
        "priced_research_costs_usd": round(sum(research_priced), 6),
        "captured_history_loads_by_reader": dict(Counter(str(load.get("reader")) for load in history)),
        "captured_history_assistant_items": {
            "total": len(assistant_items),
            "typed_card_facts": sum(1 for text in assistant_items if text.startswith(TYPED_CARD_TURN)),
            "empty": sum(1 for text in assistant_items if not text.strip()),
            "containing_the_retired_sentence": sum(1 for text in assistant_items if RETIRED_SENTENCE in text),
        },
        "naming_inputs": len(naming_in),
        "naming_outputs": len(naming_out),
    }


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
        checks.append(
            {
                "language": language,
                "check": "card step: latest card has symbols [AAPL], strategy buy_and_hold and capital 10000",
                "pass": bool(card and card.get("symbols") == ["AAPL"] and card.get("strategy_type") == "buy_and_hold" and card.get("capital") == 10000),
                "observed": card,
            }
        )
        change = named.get("change")
        if change is not None:
            changed = change.get("latest_card")
            kept = bool(card and changed and all(changed.get(key) == card.get(key) for key in ("strategy_type", "symbols", "date_range")))
            checks.append(
                {
                    "language": language,
                    "check": "change step: latest card is a new card turn with the same symbols, strategy and dates and capital 5000",
                    "pass": bool(kept and changed.get("capital") == 5000 and changed.get("message_id") != card.get("message_id")),
                    "observed": changed,
                }
            )
        run = named.get("run")
        if run is not None:
            checks.append({"language": language, "check": "run step: final payload carries a run", "pass": run.get("result_run") is not None, "observed": run.get("result_run")})
        for name in ("result_question", "result_question_retry"):
            question = named.get(name)
            if question is None:
                continue
            checks.append(
                {
                    "language": language,
                    "check": f"{name} step: reply mentions SPY and Apple or AAPL, and the final payload carries no recovery",
                    "pass": _answers_result(question),
                    "observed": {
                        "reply": question.get("reply"),
                        "recovery": question.get("recovery"),
                        "receipts_not_succeeded_or_skipped": question.get("receipts_not_succeeded_or_skipped"),
                    },
                }
            )
    return checks


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Route check report",
        "",
        "Built by `summarize_route_check.py` from the committed capture files; figures cover only what those files record.",
        "",
    ]
    server = report.get("server") or {}
    lines += [f"Server source head `{server.get('source_head')}`; working tree changes under src or web: {server.get('working_tree_changes_under_src_or_web')}.", ""]
    lines += ["## Totals", ""]
    lines += [f"- {key}: {json.dumps(value, ensure_ascii=False)}" for key, value in (report.get("totals") or {}).items()]
    lines += ["", "## Checks", ""]
    for check in report["checks"]:
        lines.append(f"- {'PASS' if check['pass'] else 'FAIL'} ({check['language']}) {check['check']}")
    for step in report["steps"]:
        lines += ["", f"## {step['language']} / {step['step']}", ""]
        if step.get("retry"):
            lines.append(f"First attempt's recovery: {json.dumps(step.get('first_attempt_recovery'), ensure_ascii=False)}")
        request = step.get("request") or {}
        lines.append(f"Request: {request.get('message') or (request.get('action') or {}).get('type')}")
        if step.get("title"):
            lines.append(f"Title after the step: {step['title'].get('title')} ({step['title'].get('title_source')})")
        lines.append(f"Reply: {step.get('reply')}")
        if step.get("recovery"):
            lines.append(f"Recovery: {json.dumps(step['recovery'], ensure_ascii=False)}")
        for receipt in step.get("receipts_not_succeeded_or_skipped") or []:
            lines.append(f"Receipt not succeeded or skipped: {json.dumps(receipt, ensure_ascii=False)}")
        if step.get("latest_card"):
            lines.append(f"Latest card: {json.dumps(step['latest_card'], ensure_ascii=False)}")
        if step.get("result_run"):
            lines.append(f"Run: {json.dumps(step['result_run'], ensure_ascii=False)}")
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
            lines.append(
                f"Captured model request to {call.get('model')} (status {call.get('status')}), "
                f"non-system messages, first {MESSAGE_CHARACTERS_SHOWN} characters each:"
            )
            for message in messages:
                content = str(message.get("content"))
                shown = content[:MESSAGE_CHARACTERS_SHOWN]
                lines.append(f"  - {message.get('role')}: {shown}{'...' if len(content) > MESSAGE_CHARACTERS_SHOWN else ''}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
