from __future__ import annotations

from argus.agent_runtime.response_style import (
    ARGUS_RESPONSE_STYLE_CONTRACT,
    argus_response_style_contract,
)
from argus.agent_runtime.result_followups import result_followup_llm_messages
from argus.api.chat.breakdown import _result_breakdown_llm_messages


def test_argus_response_style_contract_names_human_readability_requirements() -> None:
    contract = argus_response_style_contract()
    normalized = contract.lower()

    for idea in (
        "warm",
        "plain-english",
        "concise",
        "curiosity-forward",
        "financial pdf",
        "unsupported causal",
    ):
        assert idea in normalized


def test_result_followup_prompt_includes_argus_response_style_contract() -> None:
    messages = result_followup_llm_messages(
        fact_bank={
            "symbols": "TSLA",
            "total_return": "+130.0%",
            "benchmark_symbol": "SPY",
            "benchmark_delta": "+105.2%",
            "caveat": "Historical simulation evidence, not advice.",
        },
        focus="general",
        user_message="why did that happen?",
        required_fact_ids={"symbols", "total_return", "caveat"},
    )

    assert ARGUS_RESPONSE_STYLE_CONTRACT in messages[0]["content"]
    assert "plain takeaway" in messages[0]["content"]
    assert "not a metric recap" in messages[0]["content"]
    assert "two short paragraphs" in messages[0]["content"]


def test_result_breakdown_prompt_includes_argus_response_style_contract() -> None:
    messages = _result_breakdown_llm_messages(
        fact_bank={
            "symbols": "TSLA",
            "total_return": "+130.0%",
            "benchmark_symbol": "SPY",
            "benchmark_delta": "+105.2%",
            "caveat": "Historical simulation evidence, not advice.",
        },
        required_fact_ids={"symbols", "total_return", "caveat"},
    )

    assert ARGUS_RESPONSE_STYLE_CONTRACT in messages[0]["content"]
    assert "not as a financial report" in messages[0]["content"]
    assert "one warm takeaway" in messages[0]["content"]
