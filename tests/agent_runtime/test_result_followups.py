from __future__ import annotations

import json
from typing import Any

import pytest
from argus.agent_runtime.result_followups import (
    ResultFollowupDraft,
    coerce_result_followup_draft,
    compose_result_followup_response,
    fallback_result_followup_response,
    render_result_followup_draft,
    result_followup_fact_bank,
    result_followup_llm_messages,
)
from argus.llm import openrouter


@pytest.mark.asyncio
async def test_result_followup_composes_with_llm_fact_references() -> None:
    calls: list[dict[str, Any]] = []

    async def fake_schema_client(**kwargs: Any) -> object:
        calls.append(kwargs)
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="beat_benchmark",
            answer=(
                "AAPL beat SPY by +14.5% in this run: the strategy returned "
                "+40.8% while SPY returned +26.4%, so the useful read is the "
                "spread, not a generic underperformance story."
            ),
            fact_ids=[
                "symbols",
                "relative_performance",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_delta",
                "caveat",
            ],
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
    assert "AAPL beat SPY by +14.5%" in response
    assert "For this run" not in response
    assert "Strategy return:" not in response
    assert "Asset:" not in response
    assert "AAPL" in response
    assert "beat SPY by +14.5%" in response
    assert "+40.8%" in response
    assert "SPY" in response
    assert "+26.4%" in response
    assert "+14.5%" in response
    assert "stored run facts" not in response
    assert "causal proof" not in response
    assert calls[0]["task"] == "result_summary"
    assert calls[0]["schema_model"] is ResultFollowupDraft


def test_result_followup_schema_uses_flat_answer_and_fact_id_contract() -> None:
    draft = coerce_result_followup_draft(
        {
            "relative_performance_claim": "beat_benchmark",
            "parts": [
                {"kind": "text", "text": "The value belongs in a fact reference."},
                {"kind": "fact", "text": "TSLA"},
            ],
        }
    )

    assert draft is None


def test_result_followup_prompt_keeps_runtime_words_out_of_market_facts() -> None:
    messages = result_followup_llm_messages(
        fact_bank={
            "symbols": "TSLA",
            "total_return": "+130.0%",
            "benchmark_symbol": "SPY",
            "benchmark_return": "+24.8%",
            "benchmark_delta": "+105.2%",
            "caveat": "Historical simulation evidence, not a prediction.",
        },
        focus="why_underperformed",
        user_message="explain this after the routing fix",
        required_fact_ids={"symbols", "total_return", "caveat"},
    )

    system_prompt = messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    assert "routing fixes" in system_prompt
    assert "unless fact_bank explicitly includes" in system_prompt
    assert "unsupported causes" in system_prompt
    assert "Do not expose fact_bank keys" in system_prompt
    assert "benchmark_delta" in system_prompt
    assert "translate them into plain language" in system_prompt
    assert "user_message also asks what to try" in system_prompt
    assert "separate bullets or numbered lines" in system_prompt
    assert payload["question"] == (
        "Explain the result versus the benchmark, correcting the premise if the "
        "strategy did not underperform."
    )
    assert payload["user_message"] == "explain this after the routing fix"
    assert "routing fix" not in payload["question"]
    assert "routing fix" not in json.dumps(payload["fact_bank"])


def test_result_followup_rejects_user_visible_internal_fact_names() -> None:
    rendered = render_result_followup_draft(
        draft=ResultFollowupDraft(
            relative_performance_claim="beat_benchmark",
            answer=(
                "The benchmark_delta was +41.3 percentage points, so the strategy "
                "beat SPY."
            ),
            fact_ids=[
                "symbols",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_delta",
                "caveat",
            ],
        ),
        fact_bank={
            "symbols": "TSLA",
            "total_return": "+64.0%",
            "benchmark_symbol": "SPY",
            "benchmark_return": "+22.7%",
            "benchmark_delta": "+41.3%",
            "caveat": "Historical simulation evidence, not a prediction.",
        },
        required_fact_ids={"symbols", "total_return", "caveat"},
        focus="why_underperformed",
    )

    assert rendered is None


@pytest.mark.asyncio
async def test_result_followup_falls_back_when_structured_claim_contradicts_positive_delta() -> (
    None
):
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="lagged_benchmark",
            answer="It underperformed the benchmark, so the important read is the gap.",
            fact_ids=[
                "symbols",
                "relative_performance",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_delta",
                "caveat",
            ],
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
    assert response.startswith("AAPL beat SPY")
    assert "underperformed" not in response.lower()
    assert "+14.5%" in response


@pytest.mark.asyncio
async def test_result_followup_rejects_fact_only_template_output() -> None:
    openrouter.clear_openrouter_route_receipts()

    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="lagged_benchmark",
            answer=" ",
            fact_ids=[
                "symbols",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_delta",
                "caveat",
            ],
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
async def test_result_followup_accepts_semantic_language_with_required_fact_contract() -> (
    None
):
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="beat_benchmark",
            answer=(
                "The key read is the relationship between the run and "
                "its benchmark: AAPL beat SPY by +12.4% in this run, with "
                "a +39.7% strategy return versus +27.3% for SPY. The wording "
                "can stay conversational because exact values are grounded by "
                "fact ids."
            ),
            fact_ids=[
                "symbols",
                "relative_performance",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_delta",
                "caveat",
            ],
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

    assert response is not None
    assert "exact values are grounded by fact ids" in response
    assert "AAPL beat SPY by +12.4% in this run" in response
    assert "+39.7%" in response


@pytest.mark.asyncio
async def test_result_followup_rejects_unknown_fact_ids() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="unknown",
            answer="Here is an invented fact.",
            fact_ids=["made_up_return"],
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
    assert "Runnable next tests" not in buy_hold_facts["runnable_next_tests"]
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
    assert "Fed funds rate latest observation was 5.25" in fact_bank[
        "context_packet_facts"
    ]
    assert "causal proof" in fact_bank["context_packet_limitations"]
    assert "fred" not in fact_bank["context_packet_facts"].lower()
    assert "FRED" not in fact_bank["context_packet_limitations"]


@pytest.mark.asyncio
async def test_general_followup_uses_context_packet_facts_when_attached() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        assert kwargs["task"] == "result_breakdown"
        schema = kwargs["schema_model"]
        payload = json.loads(kwargs["messages"][1]["content"])
        assert payload["focus"] == "general"
        assert "context_packet_facts" in payload["required_fact_ids"]
        assert "Fed funds rate latest observation was 5.33" in payload["fact_bank"][
            "context_packet_facts"
        ]
        return schema(
            relative_performance_claim="beat_benchmark",
            answer=(
                "TSLA was stronger than SPY in this run: the strategy returned "
                "+130.0% while SPY returned +24.8%, a +105.2% gap. The attached "
                "fed funds rate observation is only backdrop."
            ),
            fact_ids=[
                "symbols",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_delta",
                "context_packet_facts",
            ],
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
    assert "fed funds rate observation" in response
    assert "simulated trades" in response
    assert "caus" in response.lower()


@pytest.mark.asyncio
async def test_context_backed_why_followup_appends_missing_required_run_facts() -> None:
    calls: list[dict[str, Any]] = []

    async def fake_schema_client(**kwargs: Any) -> object:
        calls.append(kwargs)
        assert kwargs["task"] == "result_breakdown"
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="beat_benchmark",
            answer=(
                "The safest explanation is performance evidence first; "
                "the attached macro packet can only be backdrop."
            ),
            fact_ids=[],
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
                    },
                    "risk": {"max_drawdown_pct": -32.7},
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
        focus="why_underperformed",
        user_message="why did TSLA beat SPY using the attached context?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is not None
    assert "performance evidence first" in response
    assert "Fed funds rate latest observation was 5.33" in response
    assert "TSLA" in response
    assert "AAPL" not in response
    assert "TSLA beat SPY by +105.2% in this run" in response
    assert "simulated trades" in response
    assert "caus" in response.lower()
    assert calls[0]["context_packet_ids"] == ["packet-1"]


def test_performance_fallback_preserves_context_packet_backdrop() -> None:
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 130.0,
                        "benchmark_return_pct": 24.8,
                        "delta_vs_benchmark_pct": 105.2,
                    },
                    "risk": {"max_drawdown_pct": -32.7},
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
        focus="why_underperformed",
    )

    assert response is not None
    assert "TSLA beat SPY" in response
    assert "Context backdrop:" not in response
    assert "Context I can use only as backdrop:" not in response
    assert "One backdrop data point:" not in response
    assert "Careful backdrop:" in response
    assert "Fed funds rate latest observation was 5.33" in response
    assert "Context limits:" not in response
    assert "simulated trades" in response
    assert "caus" in response.lower()


@pytest.mark.asyncio
async def test_next_experiment_followup_requires_runnable_next_tests_fact() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="unknown",
            answer="Here is generic performance context.",
            fact_ids=["symbols", "total_return", "caveat"],
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


@pytest.mark.asyncio
async def test_next_experiment_followup_renders_supported_options_not_invented_text() -> (
    None
):
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="lagged_benchmark",
            causal_attribution_claim="none",
            answer=(
                "Great question. Since the crossover lagged, try adding an RSI "
                "filter or a social sentiment overlay."
            ),
            fact_ids=[
                "symbols",
                "runnable_next_tests",
                "next_experiment_options",
                "caveat",
            ],
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": -32.6,
                        "benchmark_return_pct": 54.9,
                        "delta_vs_benchmark_pct": -87.5,
                    }
                }
            },
            "config_snapshot": {"template": "signal_strategy"},
        },
        focus="next_experiment",
        user_message="What should I try next?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is not None
    assert "RSI filter" not in response
    assert "social sentiment" not in response
    normalized = response.lower()
    assert "adjust the signal periods or crossover direction" in normalized
    assert "compare tsla with buy-and-hold" in normalized


@pytest.mark.asyncio
async def test_result_followup_rejects_self_reported_unsupported_causality() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="beat_benchmark",
            causal_attribution_claim="unsupported",
            answer=(
                "The RSI rule likely helped TSLA avoid the worst drops and caused "
                "the outperformance."
            ),
            fact_ids=[
                "symbols",
                "total_return",
                "benchmark_return",
                "benchmark_delta",
                "relative_performance",
                "caveat",
            ],
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 100.9,
                        "benchmark_return_pct": 98.9,
                        "delta_vs_benchmark_pct": 2.0,
                    }
                }
            },
            "config_snapshot": {"template": "indicator_threshold"},
        },
        focus="why_underperformed",
        user_message="Why did that happen?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is not None
    assert "beat SPY" in response
    assert "causal proof" not in response.lower()
    assert "likely helped" not in response.lower()


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
    assert response.startswith("AAPL beat SPY")
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
    assert "next step" in response.lower()


def test_result_followup_fallback_avoids_internal_next_test_label() -> None:
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": -32.6,
                        "benchmark_return_pct": 53.6,
                        "delta_vs_benchmark_pct": -86.2,
                    }
                }
            },
            "config_snapshot": {"template": "signal_strategy"},
        },
        focus="next_experiment",
    )

    assert response is not None
    assert "A good next move" in response
    assert "- Adjust the signal periods or crossover direction." in response
    assert "- Compare TSLA with buy-and-hold." in response
    assert "Runnable next tests" not in response
    assert "{" not in response


def test_result_followup_fallback_does_not_duplicate_strategy_word() -> None:
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": -32.6,
                        "benchmark_return_pct": 53.6,
                        "delta_vs_benchmark_pct": -86.2,
                    }
                }
            },
            "config_snapshot": {"template": "signal_strategy"},
        },
        focus="why_underperformed",
    )

    assert response is not None
    assert "signal strategy strategy" not in response
    assert "signal strategy on TSLA" in response


def test_result_followup_fallback_does_not_expose_context_packet_plumbing() -> None:
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 27.5,
                        "benchmark_return_pct": 23.8,
                        "delta_vs_benchmark_pct": 3.8,
                    },
                    "risk": {"max_drawdown_pct": -17.7},
                }
            },
            "config_snapshot": {
                "template": "indicator_threshold",
                "date_range": {"start": "2025-05-20", "end": "2026-05-20"},
            },
            "context_packets": [
                {
                    "id": "packet-1",
                    "provider": "fred",
                    "packet_type": "macro",
                    "facts": [
                        {
                            "kind": "macro_observation",
                            "label": "DGS10 latest observation",
                            "value": 4.61,
                        },
                        {
                            "kind": "macro_observation_change",
                            "label": "DGS10 change from previous observation",
                            "value": 0.02,
                        },
                    ],
                    "limitations": [
                        "FRED macro observations are contextual backdrop only."
                    ],
                }
            ],
        },
        focus="general",
    )

    assert response is not None
    assert "10-year Treasury yield latest observation was 4.61" in response
    assert "caus" in response.lower()
    assert "fred" not in response.lower()
    assert "context_packet" not in response


def test_performance_fallback_keeps_context_backdrop_short() -> None:
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": -32.6,
                        "benchmark_return_pct": 54.9,
                        "delta_vs_benchmark_pct": -87.5,
                    },
                    "risk": {"max_drawdown_pct": -56.0},
                }
            },
            "config_snapshot": {"template": "signal_strategy"},
            "context_packets": [
                {
                    "id": "packet-1",
                    "provider": "alpaca",
                    "packet_type": "news",
                    "facts": [
                        {
                            "kind": "news_headline",
                            "label": "First headline",
                        },
                        {
                            "kind": "news_headline",
                            "label": "Second headline",
                        },
                        {
                            "kind": "news_headline",
                            "label": "Third headline",
                        },
                    ],
                    "limitations": [
                        "Context is backdrop only; it cannot change the simulated trades, metrics, or benchmark, and it should not be treated as causal proof."
                    ],
                }
            ],
        },
        focus="why_underperformed",
    )

    assert response is not None
    assert "TSLA lagged SPY" in response
    assert "Context I can use only as backdrop:" not in response
    assert "One backdrop data point:" not in response
    assert "Careful backdrop:" in response
    assert "First headline" in response
    assert "Second headline" not in response
    assert "simulated trades" in response


def test_performance_fallback_for_same_asset_buy_hold_reads_like_argus() -> None:
    response = fallback_result_followup_response(
        metadata={
            "symbols": ["BTC"],
            "benchmark_symbol": "BTC",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 75.5,
                        "benchmark_return_pct": 75.5,
                        "delta_vs_benchmark_pct": 0.0,
                    },
                    "risk": {"max_drawdown_pct": -49.7},
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "date_range": {"start": "2024-01-01", "end": "2026-05-20"},
            },
            "context_packets": [
                {
                    "id": "packet-1",
                    "provider": "fred",
                    "packet_type": "macro",
                    "facts": [
                        {
                            "kind": "macro_observation",
                            "label": "UNRATE latest observation",
                            "value": 4.3,
                        }
                    ],
                    "limitations": [
                        "FRED macro observations are contextual backdrop only."
                    ],
                }
            ],
        },
        focus="why_underperformed",
    )

    assert response is not None
    assert "Here is the performance context" not in response
    assert "One backdrop data point" not in response
    assert "BTC matched BTC in this run" in response
    assert "benchmark was also BTC" in response
    assert "not a separate strategy edge" in response
    assert "Careful backdrop:" in response
    assert "unemployment rate latest observation was 4.3" in response
    assert "prove causality" in response


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
