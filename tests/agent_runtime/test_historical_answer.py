"""Historical evidence uses one provider fetch and ends the answer."""

import pytest
from argus.agent_runtime import answer_calculation as ac
from argus.agent_runtime import research_grounded as grounded
from argus.domain.calculations.answer_request import AnswerCalculation
from argus.domain.capability_registry import get_tool_catalog
from argus.domain.computation_marker import computation_from_tool_card
from argus.domain.research.contracts import ResearchPacket, ResearchSource

from tests.domain.calculations.test_historical_drawdown import END, START
from tests.domain.calculations.test_historical_drawdown import (
    provider as historical_provider,
)
from tests.research.test_calculation_retrieval import USER, _interpretation

provider = historical_provider


def request():
    return AnswerCalculation(
        kind="historical_drawdown",
        inputs=[
            {"name": "symbol", "value": "BTC", "source": "user"},
            {"name": "start_date", "value": START.isoformat(), "source": "user"},
            {"name": "end_date", "value": END.isoformat(), "source": "user"},
        ],
    )


PROSE = "Drawdown {{max_drawdown_pct}}, from {{observed_start_date}} to {{observed_end_date}}."


def test_answer_fetches_history_once_and_publishes_its_marker(provider):
    result = ac.publish_calculations(
        [request()],
        template=PROSE,
        language="en",
        catalog=get_tool_catalog(),
        retrieved=[],
        currency="DOP",
        subject_symbol=None,
        market_close=lambda _: pytest.fail("no current price"),
        notes=[],
    )
    assert result is not None
    card = ac.card_in(result.patch)
    assert card.outcome.status == "succeeded"
    assert "currency" not in card.arguments
    assert "-50%" in result.answer_text
    provider[1].assert_called_once()
    marker = computation_from_tool_card(card)
    assert marker is not None and marker.kinds == ["historical_drawdown"]
    assert ac.calculation_ends_answer(result.patch)


def test_research_composition_shows_drawdown_and_offers_no_next_test(
    monkeypatch, provider
):
    packet = ResearchPacket(
        answer_markdown=PROSE,
        calculations=(request().model_dump(mode="json"),),
        sources=(ResearchSource(url="https://example.com/risk"),),
        follow_up_questions=("What should I buy next?",),
    )
    result = grounded._packet_stage_result(
        packet=packet,
        subjects=[],
        shape="balanced",
        capability_class="balanced_lookup",
        language="en",
        interpretation=_interpretation(),
        user=USER,
        cache_status="miss",
        question_kind="current_external",
        message="Show Bitcoin drawdown.",
    )
    assert result is not None
    assert "-50%" in result.patch["assistant_response"]
    assert not (result.patch.get("next_experiments") or {}).get("rows")
    assert not (result.patch.get("next_steps") or {}).get("items")
    provider[1].assert_called_once()
