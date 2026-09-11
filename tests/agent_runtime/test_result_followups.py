"""The latest result's fact bank and the retired-save answer. Answers about a
result are written by the result conversation owner and tested beside it."""

from __future__ import annotations

import json
from typing import Any

import pytest
from argus.agent_runtime.result_followups import (
    PrivateAlphaSaveDraft,
    compose_private_alpha_save_response,
    fallback_private_alpha_save_response,
    render_private_alpha_save_draft,
    result_followup_fact_bank,
)


@pytest.mark.asyncio
async def test_private_alpha_save_response_uses_llm_fact_contract() -> None:
    calls: list[dict[str, Any]] = []

    async def fake_schema_client(**kwargs: Any) -> object:
        calls.append(kwargs)
        schema = kwargs["schema_model"]
        return schema(
            answer="Compatibility answer.",
            answer_blocks=[
                (
                    "I cannot move this into Strategies here, but the completed "
                    "run stays reachable from this chat and Recents."
                )
            ],
            fact_ids=["save_surface_status", "retrieval_path", "symbols"],
            claims_strategy_was_saved=False,
            points_to_hidden_surface=False,
        )

    response = await compose_private_alpha_save_response(
        metadata={
            "symbols": ["AAPL"],
            "benchmark_symbol": "SPY",
            "metrics": {"aggregate": {"performance": {"total_return_pct": 12.4}}},
        },
        user_message="save this",
        language="es-419",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is not None
    assert "Saved" not in response
    assert calls[0]["task"] == "chat_composer"
    assert calls[0]["schema_model"] is PrivateAlphaSaveDraft
    assert "Answer in Spanish" in calls[0]["messages"][0]["content"]
    assert "save_surface_status" in calls[0]["messages"][1]["content"]
    assert "retrieval_path" in calls[0]["messages"][1]["content"]
    assert "retired" in calls[0]["messages"][1]["content"]
    assert "Refine idea" in calls[0]["messages"][1]["content"]


def test_private_alpha_save_fallback_names_retired_surface_and_continuity() -> None:
    response = fallback_private_alpha_save_response(language="en")

    assert response == (
        "The legacy Strategies library and Save action have been retired. "
        "This completed run remains available in this chat and Recents, and you "
        "can use Refine idea to continue testing it."
    )


def test_private_alpha_save_response_rejects_hidden_strategy_claims() -> None:
    rendered = render_private_alpha_save_draft(
        draft=PrivateAlphaSaveDraft(
            answer="Saved it to Strategies.",
            fact_ids=["save_surface_status", "retrieval_path"],
            claims_strategy_was_saved=True,
            points_to_hidden_surface=False,
        ),
        fact_bank={
            "save_surface_status": "Strategies are disabled",
            "retrieval_path": "Runs stay available in conversation history",
        },
        required_fact_ids={"save_surface_status", "retrieval_path"},
    )

    assert rendered is None


def test_result_followup_fact_bank_includes_execution_cost_evidence() -> None:
    fact_bank = result_followup_fact_bank(
        {
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 11.8,
                        "benchmark_return_pct": 8.4,
                        "delta_vs_benchmark_pct": 3.4,
                    }
                }
            },
            "result_card": {
                "execution_costs": {
                    "fee_bps": 10.0,
                    "slippage_bps": 5.0,
                    "gross_total_return_pct": 12.0,
                    "net_total_return_pct": 11.8,
                    "return_drag_pct": 0.2,
                    "benchmark_treatment": "same_modeled_costs",
                }
            },
        }
    )

    assert fact_bank["fee_bps"] == "10 bps"
    assert fact_bank["slippage_bps"] == "5 bps"
    assert fact_bank["gross_total_return"] == "+12.0%"
    assert fact_bank["net_total_return"] == "+11.8%"
    assert fact_bank["return_drag"] == "0.2 percentage points"
    assert (
        fact_bank["benchmark_cost_treatment"] == "Benchmark used the same modeled costs"
    )


def test_result_followup_fact_bank_uses_user_safe_benchmark_comparison() -> None:
    fact_bank = result_followup_fact_bank(
        {
            "symbols": ["AAPL"],
            "benchmark_symbol": "QQQ",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 15.1,
                        "benchmark_return_pct": 20.4,
                        "delta_vs_benchmark_pct": -5.3,
                    }
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "date_range": {"start": "2026-01-01", "end": "2026-05-31"},
            },
        }
    )

    assert fact_bank["benchmark_symbol"] == "QQQ"
    assert fact_bank["benchmark_comparison"] == "Lagged by 5.3 percentage points"
    assert fact_bank["benchmark_delta_magnitude"] == "5.3 percentage points"
    assert fact_bank["relative_performance"] == (
        "AAPL lagged QQQ by 5.3 percentage points in this run"
    )
    assert fact_bank["benchmark_delta"] == "-5.3 percentage points"


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
    assert "Runnable next tests" not in buy_hold_facts["runnable_next_tests"]
    assert "monthly recurring buys on AAPL" in buy_hold_facts["runnable_next_tests"]
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
    assert (
        "Fed funds rate latest observation was 5.25" in fact_bank["context_packet_facts"]
    )
    assert "causal proof" in fact_bank["context_packet_limitations"]
    assert "fred" not in fact_bank["context_packet_facts"].lower()
    assert "FRED" not in fact_bank["context_packet_limitations"]
