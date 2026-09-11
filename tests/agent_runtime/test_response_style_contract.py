from __future__ import annotations

from argus.agent_runtime.response_style import (
    ARGUS_RESPONSE_STYLE_CONTRACT,
    argus_response_style_contract,
    result_followup_heading_key,
    result_followup_response_intent,
)
from argus.agent_runtime.result_followups import result_followup_llm_messages
from argus.agent_runtime.state.models import ResponseIntent
from argus.api.chat.breakdown import _result_breakdown_llm_messages
from argus.domain.result_readout_grounding import READOUT_RUN_GROUNDING_INSTRUCTIONS
from argus.domain.result_readout_sources import BREAKDOWN_SOURCE_INSTRUCTIONS


def test_argus_response_style_contract_names_human_readability_requirements() -> None:
    contract = argus_response_style_contract()
    normalized = contract.lower()

    for idea in (
        "warm",
        "plain language",
        "concise",
        "curiosity-forward",
        "financial pdf",
        "unsupported causal",
    ):
        assert idea in normalized
    assert "plain-english" not in normalized


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


def test_result_followup_headings_are_typed_chrome_keys() -> None:
    assert result_followup_heading_key("general") == "general"
    assert result_followup_heading_key("assumptions") == "assumptions"
    assert result_followup_heading_key("next_experiment") == "next_experiment"
    assert result_followup_heading_key("unknown_focus") == "general"
    assert result_followup_response_intent("what_tested") == {
        "kind": "result_followup_chrome",
        "facts": {"focus": "what_tested", "heading_key": "what_tested"},
    }
    assert ResponseIntent.model_validate(
        result_followup_response_intent("what_tested")
    ).kind == "result_followup_chrome"


def test_result_breakdown_prompt_uses_shared_run_and_search_instructions() -> None:
    messages = _result_breakdown_llm_messages(facts={})

    assert READOUT_RUN_GROUNDING_INSTRUCTIONS in messages[0]["content"]
    assert BREAKDOWN_SOURCE_INSTRUCTIONS in messages[0]["content"]
    assert ARGUS_RESPONSE_STYLE_CONTRACT not in messages[0]["content"]
