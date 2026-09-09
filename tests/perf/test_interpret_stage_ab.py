"""The in-process A/B summarizer counts fires per turn and the guardrail share."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.benchmarks.interpret_stage_ab import load_records, render, summarize


def _turn(category: str, elapsed_ms: float, receipts: list[dict]) -> dict:
    return {
        "label": "x",
        "iteration": 1,
        "category": category,
        "case_id": f"{category}-case",
        "language": "en",
        "elapsed_ms": elapsed_ms,
        "outcome": "ready_to_respond",
        "error_kind": None,
        "assistant_characters": 10,
        "calls_reserved": len(receipts),
        "blocked_tasks": [],
        "receipts": receipts,
    }


def _receipt(name: str, ms: int, task: str = "interpretation", **extra) -> dict:
    return {
        "task": task,
        "schema_name": name,
        "latency_ms": ms,
        "outcome": "succeeded",
        **extra,
    }


def test_summary_counts_fires_per_turn_and_the_guardrail_share() -> None:
    rows = [
        _turn(
            "ordinary_chat",
            20000,
            [
                _receipt("LLMInterpretationResponse", 9000),
                _receipt("FocusedStrategyExtraction", 2000, task="interpretation_repair"),
                _receipt(
                    "FocusedStrategyExtraction",
                    3000,
                    task="interpretation_repair",
                    fallback_used=True,
                ),
                {
                    "task": "chat_composer",
                    "schema_name": None,
                    "latency_ms": 0,
                    "outcome": "skipped",
                },
            ],
        ),
        _turn("ordinary_chat", 10000, [_receipt("LLMInterpretationResponse", 8000)]),
    ]

    summary = summarize(rows)["ordinary_chat"]

    assert summary["turns"] == 2
    assert summary["calls"]["FocusedStrategyExtraction"] == {
        "fires": 2,
        "turns": 1,
        "p50_s": 2.0,
    }
    assert summary["calls"]["ContextQuestionAudit"]["fires"] == 0
    assert summary["guardrail_share"] == round(5000 / 22000, 3)
    assert summary["other_calls_mean_s"] == 8.5
    assert summary["composer_skipped"] == 1
    assert summary["elapsed_p50_s"] == 10.0


def test_records_round_trip_and_render(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    lines = [
        json.dumps({"provenance": {"label": "base"}}),
        json.dumps(
            _turn("confirmation", 12000, [_receipt("LLMInterpretationResponse", 11000)])
        ),
        json.dumps({"finished_at": "later"}),
    ]
    path.write_text("\n".join(lines) + "\n")

    provenance, records = load_records(path)
    table = render([(provenance["label"], summarize(records))])

    assert provenance["label"] == "base"
    assert len(records) == 1
    assert "| confirmation | base | 1 | 12.00s |" in table
