"""Any grounded math, step 10 widened: retrieval supplies typed inputs to any
declared calculation, not only scenarios, and a money row counted in another
currency never feeds the math."""

from __future__ import annotations

import asyncio

import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.interpreter.calculation_request import CalculationRequest
from argus.agent_runtime.research_inputs import CURRENCY_MISMATCH_REASON_CODE
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.research.perplexity_agent import PerplexityAgentClient

from tests.research.conftest import (
    RecordingTransport,
    agent_response,
    retrieved_row,
    set_research_query,
    typed_answer_text,
)

USER = UserState(
    user_id="research-user", language_preference="es-419", country="DO", currency="DOP"
)
IPAD_GOAL = CalculationRequest(
    kind="time_value",
    inputs={"direction": "save", "present_value": 0, "annual_rate_pct": 0, "periods": 12},
    solve_for="payment",
    retrieve=["future_value"],
)


def _interpretation() -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="savings goal",
        semantic_turn_act="educational_question",
        candidate_strategy_draft=StrategySummary(),
    )


def _turn(monkeypatch: pytest.MonkeyPatch, row: dict):
    set_research_query(
        monkeypatch, globals(), question_kind="current_external", symbols=[]
    )
    transport = RecordingTransport(
        [
            agent_response(
                text=typed_answer_text("Una iPad cuesta alrededor de RD$45,000.", [row]),
                sources=["https://www.example.com.do/ipad"],
                tickers=[],
            )
        ]
    )
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    interpretation = _interpretation().model_copy(update={"calculation": IPAD_GOAL})
    result = asyncio.run(
        ra.research_answer_stage_result(
            interpretation=interpretation,
            state=RunState.new(
                current_user_message="¿Cuánto debo ahorrar mensual si gano 38,000 pesos y quiero una iPad?",
                recent_thread_history=[],
            ),
            user=USER,
        )
    )
    return result, transport, interpretation


def _card(result) -> dict:
    return result.stage_patch["final_response_payload"]["tool_result_cards"][0]


def test_a_savings_goal_computes_from_the_retrieved_price_with_its_page(
    monkeypatch,
) -> None:
    result, transport, _ = _turn(
        monkeypatch,
        retrieved_row(
            subject="iPad",
            symbol=None,
            label="future_value",
            value=45000.0,
            kind="currency",
            unit="DOP",
            as_of="2026-09-10",
            source_url="https://www.example.com.do/ipad",
        ),
    )
    assert result is not None
    sent = __import__("json").loads(transport.requests[0].content.decode())
    assert (
        "- future_value: the current price of the goal the question names"
        in sent["input"]
    )
    card = _card(result)
    assert card["tool_name"] == "time_value"
    assert card["outcome"]["status"] == "succeeded"
    assert card["arguments"]["currency"] == "DOP"
    assert (
        card["arguments"]["sources"]["future_value"]["url"]
        == "https://www.example.com.do/ipad"
    )
    answer = card["presentation"]["answer"]
    assert answer["value"] == pytest.approx(3750.0)
    assert "degraded" not in result.stage_patch["research"]


def test_a_price_in_another_currency_leaves_the_input_typeable(monkeypatch) -> None:
    result, _, interpretation = _turn(
        monkeypatch,
        retrieved_row(
            subject="iPad",
            symbol=None,
            label="future_value",
            value=349.0,
            kind="currency",
            unit="USD",
            as_of="2026-09-10",
            source_url="https://www.example.com/ipad",
        ),
    )
    assert result is not None
    card = _card(result)
    assert card["outcome"]["status"] == "invalid"
    assert card["arguments"].get("future_value") is None
    assert "future_value" not in (card["arguments"].get("sources") or {})
    assert CURRENCY_MISMATCH_REASON_CODE in interpretation.reason_codes
