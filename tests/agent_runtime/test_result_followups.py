from __future__ import annotations

import json
from typing import Any

import pytest
from argus.agent_runtime.result_followups import (
    ResultFollowupDraft,
    compose_result_followup_response,
    fallback_result_followup_response,
    result_followup_fact_bank,
)
from argus.llm import openrouter


@pytest.mark.asyncio
async def test_result_followup_composes_with_llm_fact_references() -> None:
    calls: list[dict[str, Any]] = []

    async def fake_schema_client(**kwargs: Any) -> object:
        calls.append(kwargs)
        schema = kwargs["schema_model"]
        return schema(
            parts=[
                {
                    "kind": "text",
                    "text": "This run beat the benchmark; the useful read is the spread, not a generic underperformance story.",
                },
                {"kind": "fact", "fact_id": "symbols"},
                {"kind": "fact", "fact_id": "total_return"},
                {"kind": "fact", "fact_id": "benchmark_symbol"},
                {"kind": "fact", "fact_id": "benchmark_return"},
                {"kind": "fact", "fact_id": "benchmark_delta"},
                {"kind": "fact", "fact_id": "caveat"},
            ]
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 40.8,
                        "benchmark_return_pct": 26.4,
                        "delta_vs_benchmark_pct": 14.5,
                    }
                }
            },
        },
        focus="why_underperformed",
        user_message="Why did it underperform?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is not None
    assert "This run beat the benchmark" in response
    assert "For this run" not in response
    assert "Strategy return:" not in response
    assert "Asset:" not in response
    assert "AAPL" in response
    assert "+40.8%" in response
    assert "SPY" in response
    assert "+26.4%" in response
    assert "+14.5%" in response
    assert "stored run facts" not in response
    assert "causal proof" not in response
    assert calls[0]["task"] == "result_summary"
    assert calls[0]["schema_model"] is ResultFollowupDraft


@pytest.mark.asyncio
async def test_result_followup_replaces_llm_answer_that_contradicts_positive_delta() -> (
    None
):
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            parts=[
                {
                    "kind": "text",
                    "text": "It underperformed the benchmark, so the important read is the gap.",
                },
                {"kind": "fact", "fact_id": "symbols"},
                {"kind": "fact", "fact_id": "total_return"},
                {"kind": "fact", "fact_id": "benchmark_symbol"},
                {"kind": "fact", "fact_id": "benchmark_return"},
                {"kind": "fact", "fact_id": "benchmark_delta"},
                {"kind": "fact", "fact_id": "caveat"},
            ]
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 40.8,
                        "benchmark_return_pct": 26.4,
                        "delta_vs_benchmark_pct": 14.5,
                    }
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "date_range": {"start": "2025-05-14", "end": "2026-05-14"},
            },
        },
        focus="why_underperformed",
        user_message="Why did it underperform?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is not None
    assert response.startswith("AAPL beat SPY in this run.")
    assert "underperformed" not in response.lower()
    assert "+14.5%" in response


@pytest.mark.asyncio
async def test_result_followup_rejects_fact_only_template_output() -> None:
    openrouter.clear_openrouter_route_receipts()

    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            parts=[
                {"kind": "fact", "fact_id": "symbols"},
                {"kind": "fact", "fact_id": "total_return"},
                {"kind": "fact", "fact_id": "benchmark_symbol"},
                {"kind": "fact", "fact_id": "benchmark_return"},
                {"kind": "fact", "fact_id": "benchmark_delta"},
                {"kind": "fact", "fact_id": "caveat"},
            ]
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["MSFT"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": -10.6,
                        "benchmark_return_pct": 26.4,
                        "delta_vs_benchmark_pct": -36.9,
                    }
                }
            },
            "config_snapshot": {"template": "buy_and_hold", "date_range": "past year"},
        },
        focus="why_underperformed",
        user_message="Why did it underperform?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is None
    receipts = openrouter.get_openrouter_route_receipts()
    assert receipts[-1].failure_mode == "result_followup_draft_rejected"


@pytest.mark.asyncio
async def test_result_followup_rejects_text_that_repeats_fact_values() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            parts=[
                {
                    "kind": "text",
                    "text": (
                        "This historical simulation used AAPL from "
                        "2025-05-14 to 2026-05-14 and returned +39.7%."
                    ),
                },
                {"kind": "fact", "fact_id": "symbols"},
                {"kind": "fact", "fact_id": "total_return"},
                {"kind": "fact", "fact_id": "benchmark_symbol"},
                {"kind": "fact", "fact_id": "benchmark_return"},
                {"kind": "fact", "fact_id": "benchmark_delta"},
                {"kind": "fact", "fact_id": "caveat"},
            ]
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 39.7,
                        "benchmark_return_pct": 27.3,
                        "delta_vs_benchmark_pct": 12.4,
                    }
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "date_range": {"start": "2025-05-14", "end": "2026-05-14"},
            },
        },
        focus="why_underperformed",
        user_message="Why did this result happen?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is None


@pytest.mark.asyncio
async def test_result_followup_rejects_unknown_fact_ids() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            parts=[
                {"kind": "text", "text": "Here is an invented fact."},
                {"kind": "fact", "fact_id": "made_up_return"},
            ]
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["MSFT"],
            "metrics": {"aggregate": {"risk": {"max_drawdown_pct": -34.2}}},
        },
        focus="max_drawdown",
        user_message="What was the max drawdown?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is None


def test_result_followup_fact_bank_preserves_no_trade_reason() -> None:
    fact_bank = result_followup_fact_bank(
        {
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 0.0,
                        "benchmark_return_pct": 8.9,
                    },
                    "efficiency": {"total_trades": 0},
                }
            },
            "trades": [],
            "config_snapshot": {"template": "rsi_mean_reversion"},
        }
    )

    assert fact_bank["execution_note"].startswith("No entry trades were executed")
    assert fact_bank["total_return"] == "0.0%"
    assert fact_bank["benchmark_return"] == "+8.9%"


def test_result_followup_next_tests_respect_strategy_family() -> None:
    buy_hold_facts = result_followup_fact_bank(
        {
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "metrics": {"aggregate": {"performance": {"total_return_pct": 12.0}}},
            "config_snapshot": {"template": "buy_and_hold"},
        }
    )
    signal_facts = result_followup_fact_bank(
        {
            "symbols": ["NVDA"],
            "benchmark_symbol": "SPY",
            "metrics": {"aggregate": {"performance": {"total_return_pct": 7.0}}},
            "config_snapshot": {"template": "signal_strategy"},
        }
    )

    assert "compare with buy-and-hold" not in buy_hold_facts["runnable_next_tests"]
    assert "RSI threshold on AAPL" in buy_hold_facts["runnable_next_tests"]
    assert "compare NVDA with buy-and-hold" in signal_facts["runnable_next_tests"]
    options = json.loads(signal_facts["next_experiment_options"])
    assert options[0]["contract"] == "supported_backtest_experiment"
    assert {option["kind"] for option in options} >= {
        "adjust_signal_periods",
        "compare_buy_and_hold",
    }


def test_result_followup_fact_bank_includes_context_packet_limitations() -> None:
    fact_bank = result_followup_fact_bank(
        {
            "symbols": ["NVDA"],
            "benchmark_symbol": "SPY",
            "metrics": {"aggregate": {"performance": {"total_return_pct": 7.0}}},
            "config_snapshot": {"template": "buy_and_hold"},
            "context_packets": [
                {
                    "id": "packet-1",
                    "provider": "fred",
                    "packet_type": "macro",
                    "facts": [
                        {
                            "kind": "macro_observation",
                            "label": "FEDFUNDS latest observation",
                            "value": 5.25,
                        }
                    ],
                    "limitations": [
                        "FRED macro observations are contextual backdrop only."
                    ],
                }
            ],
        }
    )

    assert fact_bank["context_packet_ids"] == "packet-1"
    assert "FEDFUNDS latest observation" in fact_bank["context_packet_facts"]
    assert "contextual backdrop only" in fact_bank["context_packet_limitations"]


@pytest.mark.asyncio
async def test_general_followup_uses_context_packet_facts_when_attached() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        assert kwargs["task"] == "result_breakdown"
        schema = kwargs["schema_model"]
        payload = json.loads(kwargs["messages"][1]["content"])
        assert payload["focus"] == "general"
        assert "context_packet_facts" in payload["required_fact_ids"]
        return schema(
            parts=[
                {
                    "kind": "text",
                    "text": "The run result is performance evidence first; the attached macro packet is only backdrop.",
                },
                {"kind": "fact", "fact_id": "symbols"},
                {"kind": "fact", "fact_id": "total_return"},
                {"kind": "fact", "fact_id": "benchmark_symbol"},
                {"kind": "fact", "fact_id": "benchmark_return"},
                {"kind": "fact", "fact_id": "benchmark_delta"},
                {"kind": "fact", "fact_id": "context_packet_facts"},
                {"kind": "fact", "fact_id": "context_packet_limitations"},
                {"kind": "fact", "fact_id": "caveat"},
            ]
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 130.0,
                        "benchmark_return_pct": 24.8,
                        "delta_vs_benchmark_pct": 105.2,
                    }
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "date_range": {"start": "2023-01-01", "end": "2023-12-31"},
            },
            "context_packets": [
                {
                    "id": "packet-1",
                    "provider": "fred",
                    "packet_type": "macro",
                    "facts": [
                        {
                            "kind": "macro_observation",
                            "label": "FEDFUNDS latest observation",
                            "value": 5.33,
                        }
                    ],
                    "limitations": [
                        "FRED macro observations are contextual backdrop only."
                    ],
                }
            ],
        },
        focus="general",
        user_message="why did that happen?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is not None
    assert "TSLA" in response
    assert "+130.0%" in response
    assert "SPY" in response
    assert "FEDFUNDS latest observation" in response
    assert "contextual backdrop only" in response


@pytest.mark.asyncio
async def test_next_experiment_followup_requires_runnable_next_tests_fact() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            parts=[
                {"kind": "text", "text": "Here is generic performance context."},
                {"kind": "fact", "fact_id": "symbols"},
                {"kind": "fact", "fact_id": "total_return"},
                {"kind": "fact", "fact_id": "caveat"},
            ]
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 0.0,
                        "benchmark_return_pct": 9.6,
                        "delta_vs_benchmark_pct": -9.6,
                    }
                }
            },
            "config_snapshot": {"template": "rsi_mean_reversion"},
        },
        focus="next_experiment",
        user_message="What should I try next?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is None


def test_result_followup_fallback_uses_neutral_result_language() -> None:
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 39.7,
                        "benchmark_return_pct": 27.3,
                        "delta_vs_benchmark_pct": 12.4,
                    }
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "date_range": {"start": "2025-05-14", "end": "2026-05-14"},
            },
        },
        focus="why_underperformed",
    )

    assert response is not None
    assert response.startswith("AAPL beat SPY in this run.")
    assert "It did not underperform" not in response


def test_what_tested_fallback_includes_performance_context_when_focus_drifts() -> None:
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["NVDA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 23.6,
                        "benchmark_return_pct": 11.4,
                        "delta_vs_benchmark_pct": 12.2,
                    }
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "symbols": ["NVDA"],
                "date_range": {
                    "start": "2025-11-14",
                    "end": "2026-05-14",
                },
            },
        },
        focus="what_tested",
    )

    assert response is not None
    assert "I tested NVDA" in response
    assert "The strategy returned +23.6%" in response
    assert "SPY returned +11.4%" in response
    assert "The gap versus the benchmark was +12.2%" in response


def test_general_result_followup_fallback_is_fact_complete_when_focus_is_uncertain() -> (
    None
):
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["NVDA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 21.9,
                        "benchmark_return_pct": 11.4,
                        "delta_vs_benchmark_pct": 10.4,
                    },
                    "risk": {"max_drawdown_pct": -15.7},
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "date_range": {
                    "start": "2025-11-15",
                    "end": "2026-05-15",
                },
            },
        },
        focus="general",
    )

    assert response is not None
    assert "NVDA" in response
    assert "buy and hold" in response
    assert "2025-11-15 to 2026-05-15" in response
    assert "+21.9%" in response
    assert "SPY returned +11.4%" in response
    assert "gap versus the benchmark was +10.4%" in response
    assert "max drawdown was -15.7%" in response.lower()
    assert "try" in response.lower()


def test_performance_fallback_keeps_core_risk_fact_when_focus_drifts() -> None:
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["NVDA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 21.9,
                        "benchmark_return_pct": 11.4,
                        "delta_vs_benchmark_pct": 10.4,
                    },
                    "risk": {"max_drawdown_pct": -15.7},
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "date_range": {
                    "start": "2025-11-15",
                    "end": "2026-05-15",
                },
            },
        },
        focus="why_underperformed",
    )

    assert response is not None
    assert "max drawdown was -15.7%" in response.lower()
