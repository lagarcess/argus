from __future__ import annotations

import pytest
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.response_style import (
    argus_response_style_contract,
    result_followup_heading_key,
    result_followup_response_intent,
)
from argus.agent_runtime.result_conversation import result_conversation_instructions
from argus.agent_runtime.state.models import ResponseIntent
from argus.api.chat.breakdown import _result_breakdown_llm_messages
from argus.domain.result_readout_grounding import (
    READOUT_FIGURE_REFERENCE_INSTRUCTIONS,
    READOUT_RUN_GROUNDING_INSTRUCTIONS,
)
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


@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize("can_search", [True, False])
def test_answers_after_a_result_keep_advice_forecasts_and_floor_years_out(
    language: str, can_search: bool
) -> None:
    instructions = result_conversation_instructions(language=language, can_search=can_search)

    assert response_language_instruction(language) in instructions
    assert "No investment advice" in instructions
    assert "no forecast stated as fact" in instructions
    assert "only from the supplied history starts" in instructions
    assert "2016" not in instructions
    assert READOUT_FIGURE_REFERENCE_INSTRUCTIONS in instructions
    # Only the Agent may search; the answer without it links nothing.
    assert ("link short descriptive text" in instructions) is can_search
    assert ("You cannot search the web" in instructions) is not can_search
    assert ("include no links" in instructions) is not can_search


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
    assert READOUT_FIGURE_REFERENCE_INSTRUCTIONS in messages[0]["content"]
    assert BREAKDOWN_SOURCE_INSTRUCTIONS in messages[0]["content"]
    assert argus_response_style_contract() not in messages[0]["content"]
