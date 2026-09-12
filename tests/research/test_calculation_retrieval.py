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


def _turn(monkeypatch: pytest.MonkeyPatch, calculation: dict[str, Any]):
    set_research_query(
        monkeypatch, globals(), question_kind="current_external", symbols=[]
    )
    transport = RecordingTransport(
        [
            agent_response(
                text=typed_answer_text(PROSE, [], calculation),
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
