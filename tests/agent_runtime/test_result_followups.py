from __future__ import annotations

import json
from typing import Any

import pytest
from argus.agent_runtime.result_followups import (
    PrivateAlphaSaveDraft,
    ResultFollowupDraft,
    coerce_result_followup_draft,
    compose_private_alpha_save_response,
    compose_result_followup_response,
    render_private_alpha_save_draft,
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
                "AAPL beat SPY by 14.5 percentage points in this run: the strategy returned "
                "+40.8% while SPY returned +26.4%, so the useful read is the "
                "spread, not a generic underperformance story."
            ),
            fact_ids=[
                "symbols",
                "relative_performance",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_comparison",
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
    assert "AAPL beat SPY by 14.5 percentage points" in response
    assert "For this run" not in response
    assert "Strategy return:" not in response
    assert "Asset:" not in response
    assert "AAPL" in response
    assert "beat SPY by 14.5 percentage points" in response
    assert "+40.8%" in response
    assert "SPY" in response
    assert "+26.4%" in response
    assert "14.5 percentage points" in response
    assert "stored run facts" not in response
    assert "causal proof" not in response
    assert calls[0]["task"] == "result_summary"
    assert calls[0]["schema_model"] is ResultFollowupDraft


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
            "metrics": {
                "aggregate": {"performance": {"total_return_pct": 12.4}}
            },
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


@pytest.mark.asyncio
async def test_result_followup_prefers_structured_answer_blocks() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="beat_benchmark",
            answer=(
                "This dense compatibility answer should not be the rendered response."
            ),
            answer_blocks=[
                "AAPL beat SPY by 12.4 percentage points in this run.",
                (
                    "That is useful historical evidence, but it does not prove the "
                    "same edge would persist."
                ),
            ],
            fact_ids=[
                "symbols",
                "relative_performance",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_comparison",
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
            "config_snapshot": {"template": "buy_and_hold"},
        },
        focus="why_underperformed",
        user_message="why did this happen?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is not None
    assert "compatibility answer" not in response
    assert "AAPL beat SPY by 12.4 percentage points in this run.\n\nThat is useful" in response


def test_result_followup_rejects_dense_unstructured_answer() -> None:
    rendered = render_result_followup_draft(
        draft=ResultFollowupDraft(
            relative_performance_claim="beat_benchmark",
            answer=(
                "AAPL beat SPY in this run and the setup was a buy and hold strategy "
                "over the stored window with a strong return, a benchmark comparison, "
                "a drawdown observation, a macro backdrop note, a caveat about historical "
                "simulation, and a next step all packed into one long paragraph that "
                "reads like a compact report instead of a useful chat response."
            ),
            fact_ids=[
                "symbols",
                "relative_performance",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_delta",
                "max_drawdown",
                "caveat",
            ],
        ),
        fact_bank={
            "symbols": "AAPL",
            "relative_performance": "AAPL beat SPY by +12.4% in this run",
            "total_return": "+39.7%",
            "benchmark_symbol": "SPY",
            "benchmark_return": "+27.3%",
            "benchmark_delta": "+12.4%",
            "max_drawdown": "16.8%",
            "caveat": "Historical simulation evidence, not a prediction.",
        },
        required_fact_ids={"symbols", "relative_performance", "caveat"},
        focus="why_underperformed",
    )

    assert rendered is None


def test_result_followup_ignores_unknown_optional_fact_ids_after_required_facts() -> None:
    rendered = render_result_followup_draft(
        draft=ResultFollowupDraft(
            relative_performance_claim="beat_benchmark",
            answer=(
                "AAPL returned +39.7% in this historical run. Historical simulation "
                "only, not a prediction."
            ),
            fact_ids=[
                "symbols",
                "total_return",
                "caveat",
                "optional_style_note",
            ],
        ),
        fact_bank={
            "symbols": "AAPL",
            "total_return": "+39.7%",
            "caveat": "Historical simulation only, not a prediction.",
        },
        required_fact_ids={"symbols", "total_return", "caveat"},
        focus="general",
    )

    assert rendered is not None
    assert "AAPL returned +39.7%" in rendered


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


def test_result_followup_prompt_uses_requested_response_language() -> None:
    messages = result_followup_llm_messages(
        fact_bank={
            "symbols": "ETH",
            "total_return": "+18.1%",
            "caveat": "Historical simulation evidence, not a prediction.",
        },
        focus="general",
        user_message="explícame esto",
        required_fact_ids={"symbols", "total_return", "caveat"},
        language="es-419",
    )

    system_prompt = messages[0]["content"]
    assert "Answer in Spanish" in system_prompt
    assert "plain-English" not in system_prompt


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
    assert "benchmark_delta" not in fact_bank

    messages = result_followup_llm_messages(
        fact_bank=fact_bank,
        focus="why_underperformed",
        user_message="why did this lag?",
        required_fact_ids={"symbols", "relative_performance", "caveat"},
    )
    payload = json.loads(messages[1]["content"])
    assert payload["relative_performance_truth"] == "lagged_benchmark"
    assert payload["fact_bank"]["benchmark_comparison"] == (
        "Lagged by 5.3 percentage points"
    )
    assert "benchmark_comparison_claim" not in payload["fact_bank"]
    assert "benchmark_delta" not in payload["fact_bank"]


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
                "benchmark_comparison",
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
async def test_result_followup_rejects_when_structured_claim_contradicts_positive_delta() -> (
    None
):
    openrouter.clear_openrouter_route_receipts()

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
                "benchmark_comparison",
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

    assert response is None
    receipts = openrouter.get_openrouter_route_receipts()
    assert receipts[-1].failure_mode == "relative_performance_claim_contradiction"


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
                "its benchmark: AAPL beat SPY by 12.4 percentage points in this run, with "
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
                "benchmark_comparison",
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
    assert "AAPL beat SPY by 12.4 percentage points in this run" in response
    assert "+39.7%" in response


@pytest.mark.asyncio
async def test_result_followup_general_focus_appends_required_symbol_fact() -> None:
    async def fake_schema_client(**kwargs: Any) -> object:
        schema = kwargs["schema_model"]
        return schema(
            relative_performance_claim="unknown",
            answer="The latest run peaked at $14,500.25 on 2021-11-09.",
            answer_blocks=["The latest run peaked at $14,500.25 on 2021-11-09."],
            fact_ids=["peak_date", "peak_value", "caveat"],
        )

    response = await compose_result_followup_response(
        metadata={
            "symbols": ["COST", "TGT"],
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 28.4,
                        "portfolio_value_range": {
                            "peak_value": 14500.25,
                            "currency": "USD",
                            "source": "strategy_portfolio_equity_close",
                        },
                    }
                }
            },
            "chart": {
                "kind": "portfolio_equity",
                "currency": "USD",
                "series": [
                    {"time": "2020-02-03", "value": 10000.0},
                    {"time": "2021-11-09", "value": 14500.25},
                    {"time": "2026-07-02", "value": 13900.0},
                ],
            },
            "config_snapshot": {
                "template": "dca_accumulation",
                "date_range": {"start": "2020-02-01", "end": "2026-07-02"},
            },
        },
        focus="general",
        user_message="what date did this peak?",
        invoke_json_schema_func=fake_schema_client,
    )

    assert response is not None
    assert "2021-11-09" in response
    assert "COST, TGT" in response


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
                "+130.0% while SPY returned +24.8%, a 105.2 percentage point gap. The attached "
                "fed funds rate observation is only backdrop."
            ),
            fact_ids=[
                "symbols",
                "total_return",
                "benchmark_symbol",
                "benchmark_return",
                "benchmark_comparison",
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
    assert "TSLA beat SPY by 105.2 percentage points in this run" in response
    assert "simulated trades" in response
    assert "caus" in response.lower()
    assert calls[0]["context_packet_ids"] == ["packet-1"]


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

    assert response is None
