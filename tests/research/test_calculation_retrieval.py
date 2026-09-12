"""Any grounded math, the answer step: a research answer returns its calculation
with each input's source, Argus computes it and fills the prose's figures from
the card, and a money input counted in another currency never feeds the math."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from argus.agent_runtime import answer_calculation as ac
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.research.perplexity_agent import PerplexityAgentClient

from tests.research.conftest import (
    RecordingTransport,
    agent_response,
    set_research_query,
    typed_answer_text,
)

USER = UserState(
    user_id="research-user", language_preference="es-419", country="DO", currency="DOP"
)
PRICE_PAGE = "https://www.example.com.do/ipad"
QUESTION = "¿Cuánto debo ahorrar mensual si gano 38,000 pesos y quiero una iPad?"
PROSE = (
    "Asumiendo {{annual_rate_pct}} de rendimiento durante {{periods}} meses, "
    "necesitas **{{payment}}** al mes para una iPad de {{future_value}}."
)


def _goal(price_currency: str) -> dict[str, Any]:
    price = 45000 if price_currency == "DOP" else 349
    return {
        "kind": "time_value",
        "solve_for": "payment",
        "inputs": [
            {"name": "direction", "value": "save", "source": "user"},
            {"name": "present_value", "value": 0, "source": "user", "currency": "DOP"},
            {"name": "annual_rate_pct", "value": 0, "source": "assumption"},
            {"name": "periods", "value": 12, "source": "assumption"},
            {
                "name": "future_value",
                "value": price,
                "source": "page",
                "source_url": PRICE_PAGE,
                "as_of": "2026-09-10",
                "currency": price_currency,
            },
        ],
    }


def _interpretation() -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="savings goal",
        semantic_turn_act="educational_question",
        candidate_strategy_draft=StrategySummary(),
    )


def _turn(
    monkeypatch: pytest.MonkeyPatch, calculation: dict[str, Any], prose: str = PROSE
):
    set_research_query(
        monkeypatch, globals(), question_kind="current_external", symbols=[]
    )
    transport = RecordingTransport(
        [
            agent_response(
                text=typed_answer_text(prose, [], calculation),
                sources=[PRICE_PAGE],
                tickers=[],
            )
        ]
    )
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    interpretation = _interpretation()
    result = asyncio.run(
        ra.research_answer_stage_result(
            interpretation=interpretation,
            state=RunState.new(current_user_message=QUESTION, recent_thread_history=[]),
            user=USER,
        )
    )
    return result, transport, interpretation


def test_a_savings_goal_computes_from_the_price_its_answer_cited(monkeypatch) -> None:
    result, transport, _ = _turn(monkeypatch, _goal("DOP"))
    assert result is not None
    sent = json.loads(transport.requests[0].content.decode())
    schema = sent["response_format"]["json_schema"]["schema"]
    assert "calculation" in schema["required"]
    card = result.stage_patch["final_response_payload"]["tool_result_cards"][0]
    assert card["tool_name"] == "time_value"
    assert card["outcome"]["status"] == "succeeded"
    assert card["arguments"]["currency"] == "DOP"
    assert card["arguments"]["sources"]["future_value"]["url"] == PRICE_PAGE
    assert card["arguments"]["sources"]["future_value"]["date"] == "2026-09-10"
    assert card["arguments"]["sources"]["periods"] == {"kind": "assumption"}
    assert card["presentation"]["answer"]["value"] == pytest.approx(3750.0)
    answer = result.stage_patch["assistant_response"]
    assert "**DOP 3,750**" in answer and "DOP 45,000" in answer
    assert "{{" not in answer
    template = result.stage_patch[ac.ANSWER_TEMPLATE_KEY]
    assert template["artifact_id"] == card["artifact_id"]
    assert "{{payment}}" in template["text"]
    assert "degraded" not in result.stage_patch["research"]


def test_a_price_in_another_currency_is_not_computed_and_no_blank_card_renders(
    monkeypatch,
) -> None:
    result, _, interpretation = _turn(monkeypatch, _goal("USD"))
    assert result is not None
    assert "final_response_payload" not in result.stage_patch
    assert result.stage_patch["research"]["degraded"] == {
        "code": "calculation_inputs_not_found"
    }
    assert ac.CURRENCY_MISMATCH_REASON_CODE in interpretation.reason_codes
    answer = result.stage_patch["assistant_response"]
    assert "{{" not in answer and "DOP" not in answer


def test_an_answer_that_needs_a_figure_only_the_user_knows_offers_the_calculation(
    monkeypatch,
) -> None:
    from argus.agent_runtime.calculated_answer import (
        CALCULATION_OFFER_KEY,
        CALCULATION_OFFERED_REASON_CODE,
    )

    goal = _goal("DOP")
    goal["inputs"][1] = {"name": "present_value", "value": None, "source": "user"}
    prose = "Una iPad cuesta {{future_value}}; ahorrarla depende de lo que ya tienes."
    result, _, _ = _turn(monkeypatch, goal, prose=prose)
    assert result is not None and result.outcome == "ready_to_respond"
    answer = result.stage_patch["assistant_response"]
    assert "DOP 45,000" in answer and "{{" not in answer
    offer = result.stage_patch[CALCULATION_OFFER_KEY]
    assert offer["requested_field"] == "present_value"
    assert offer["calculation"]["kind"] == "time_value"
    assert offer["retrieved"][0]["url"] == PRICE_PAGE
    assert result.stage_patch["next_steps"]["items"][0] == {
        "type": "test",
        "kind": "calculation_offer",
    }
    assert "final_response_payload" not in result.stage_patch
    assert "degraded" not in result.stage_patch["research"]
    assert CALCULATION_OFFERED_REASON_CODE in result.decision.reason_codes


def test_an_offer_whose_prose_leans_on_a_result_it_cannot_show_is_not_published(
    monkeypatch,
) -> None:
    goal = _goal("DOP")
    goal["inputs"][1] = {"name": "present_value", "value": None, "source": "user"}
    result, _, _ = _turn(monkeypatch, goal)
    assert result is not None
    assert result.stage_patch["research"]["degraded"] == {
        "code": "calculation_inputs_not_found"
    }
    assert "{{" not in str(result.stage_patch.get("assistant_response"))


def test_a_money_unit_with_a_qualifier_keeps_its_code() -> None:
    from argus.domain.research.contracts import RetrievedRow

    row = {
        "subject": "NVIDIA",
        "symbol": "NVDA",
        "label": "fiscal-year diluted earnings per share",
        "value": 4.9,
        "kind": "currency",
        "unit": "USD per share",
        "as_of": "2026-01-25",
        "source_url": "https://example.com/nvda/eps",
    }
    assert RetrievedRow.model_validate(row).unit == "USD"
    assert RetrievedRow.model_validate({**row, "unit": "USD/share"}).unit == "USD"
    with pytest.raises(ValueError):
        RetrievedRow.model_validate({**row, "unit": "dollars"})
