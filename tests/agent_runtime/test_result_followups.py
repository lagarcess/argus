from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.result_followups import (
    ResultFollowupDraft,
    compose_result_followup_response,
    fallback_result_followup_response,
    result_followup_fact_bank,
)


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
async def test_result_followup_rejects_fact_only_template_output() -> None:
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
