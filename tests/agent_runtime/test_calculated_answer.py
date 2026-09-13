"""The no-search answer owns its math: a money question on the user's own
numbers reaches it, its calculation computes the card under the prose, a figure
only the user knows is one plain question, and the reply completes it."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime import calculated_answer as ca
from argus.agent_runtime.answer_calculation import ANSWER_TEMPLATE_KEY
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.research_routing import (
    primary_read_asks_a_fact_question,
    primary_read_is_arithmetic,
)
from argus.agent_runtime.interpreter.unsupported_admission import (
    future_test_window_capability_clause,
)
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret import interpret_stage_async
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.domain.calculations.answer_request import AnswerCalculation

USER = UserState(user_id="u1", language_preference="en", currency="DOP")
LOAN = [
    {"name": "direction", "value": "borrow", "source": "user"},
    {"name": "present_value", "value": 180000, "source": "user", "currency": "DOP"},
    {"name": "annual_rate_pct", "value": 14, "source": "user"},
    {"name": "future_value", "value": 0, "source": "user"},
]


def _read(**query: Any) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="money question",
        semantic_turn_act="educational_question",
        candidate_strategy_draft=StrategySummary(),
        research_query=ResearchQueryExtraction(**query) if query else None,
    )


def _voice(monkeypatch: pytest.MonkeyPatch, answers: list[ca.CalculatedVoicedAnswer]):
    seen: list[list[dict[str, str]]] = []

    def invoke(**kwargs):
        assert kwargs["schema_model"] is ca.CalculatedVoicedAnswer
        seen.append(kwargs["messages"])
        return answers.pop(0)

    monkeypatch.setattr(ca, "resolve_openrouter_api_key", lambda: "k")
    monkeypatch.setattr(ca, "openrouter_structured_model_candidates", lambda: ["model"])
    monkeypatch.setattr(ca, "invoke_openrouter_json_schema_sync", invoke)
    return seen


def _voiced(lead: str, inputs: list[dict[str, Any]], solve_for: str = "payment"):
    return ca.CalculatedVoicedAnswer(
        lead=lead,
        calculation=AnswerCalculation.model_validate(
            {"kind": "time_value", "solve_for": solve_for, "inputs": inputs}
        ),
    )


def test_the_users_own_numbers_reach_the_no_search_answer_and_a_published_figure_reaches_research() -> (
    None
):
    arithmetic = _read(question_kind="none", scenario_question=True)
    assert primary_read_is_arithmetic(arithmetic)
    assert not primary_read_asks_a_fact_question(arithmetic)
    needs_a_page = _read(question_kind="current_external", scenario_question=True)
    assert not primary_read_is_arithmetic(needs_a_page)
    assert primary_read_asks_a_fact_question(needs_a_page)
    named = _read(question_kind="none", scenario_question=True, symbols=["AAPL"])
    assert not primary_read_is_arithmetic(named)
    assert not primary_read_is_arithmetic(_read(question_kind="concept"))
    assert not primary_read_is_arithmetic(
        _read(question_kind="concept", scenario_question=True)
    )
    assert not primary_read_is_arithmetic(_read())


def test_a_calculated_answer_computes_its_card_under_the_prose(monkeypatch) -> None:
    _voice(
        monkeypatch,
        [
            _voiced(
                "Over {{periods}} months at {{annual_rate_pct}}, the payment is **{{payment}}**.",
                [*LOAN, {"name": "periods", "value": 48, "source": "user"}],
            )
        ],
    )
    interpretation = _read(question_kind="none", scenario_question=True)
    result = asyncio.run(
        ca.calculated_answer_stage_result(
            interpretation=interpretation,
            state=RunState.new(
                current_user_message="I owe 180,000 at 14% over 48 months; what's the payment?",
                recent_thread_history=[],
            ),
            user=USER,
        )
    )
    assert result is not None and result.outcome == "ready_to_respond"
    card = result.patch["final_response_payload"]["tool_result_cards"][0]
    assert card["tool_name"] == "time_value" and card["outcome"]["status"] == "succeeded"
    assert (
        "Over 48 months at 14%, the payment is **DOP "
        in result.patch["assistant_response"]
    )
    assert result.patch[ANSWER_TEMPLATE_KEY]["artifact_id"] == card["artifact_id"]
    assert ca.CALCULATED_ANSWER_REASON_CODE in result.decision.reason_codes


def test_a_figure_only_the_user_knows_is_one_question_and_the_reply_computes(
    monkeypatch,
) -> None:
    seen = _voice(
        monkeypatch,
        [
            _voiced(
                "How many months are left on the loan?",
                [*LOAN, {"name": "periods", "value": None, "source": "user"}],
            ),
            _voiced(
                "With {{periods}} months left, the payment is {{payment}}.",
                [*LOAN, {"name": "periods", "value": 48, "source": "user"}],
            ),
        ],
    )
    asked = asyncio.run(
        ca.calculated_answer_stage_result(
            interpretation=_read(question_kind="none", scenario_question=True),
            state=RunState.new(
                current_user_message="I owe 180,000 on the car at 14 percent. Is paying extra worth it?",
                recent_thread_history=[],
            ),
            user=USER,
        )
    )
    assert asked is not None and asked.outcome == "await_user_reply"
    assert asked.patch["assistant_prompt"] == ca.missing_inputs_lead("en")
    assert asked.patch["clarification"]["missing_inputs"] == [
        {
            "name": "periods",
            "label": {
                "locale_key": "tools.calc.fields.periods",
                "interpolation_args": {},
            },
        }
    ]
    assert asked.patch["requested_field"] == "periods"
    pending = asked.patch["clarification"]["payload"]
    assert pending["calculation"]["kind"] == "time_value"

    class _Interpreter:
        async def ainvoke(self, request):
            return _read()

    reply = asyncio.run(
        interpret_stage_async(
            state=RunState.new(current_user_message="48", recent_thread_history=[]),
            user=USER,
            latest_task_snapshot=None,
            selected_thread_metadata={
                "last_stage_outcome": "await_user_reply",
                "clarification": asked.patch["clarification"],
            },
            structured_interpreter=_Interpreter(),
        )
    )
    assert reply.outcome == "ready_to_respond"
    card = reply.patch["final_response_payload"]["tool_result_cards"][0]
    assert card["arguments"]["periods"] == 48
    assert reply.patch["assistant_response"].startswith(
        "With 48 months left, the payment is DOP "
    )
    assert (
        "Argus asked the user for periods of a time_value calculation"
        in seen[1][0]["content"]
    )
    assert ca.PENDING_REPLY_REASON_CODE in reply.decision.reason_codes


def test_without_voicing_the_turn_stays_with_its_other_owners(monkeypatch) -> None:
    monkeypatch.setattr(ca, "resolve_openrouter_api_key", lambda: None)
    result = asyncio.run(
        ca.calculated_answer_stage_result(
            interpretation=_read(question_kind="none", scenario_question=True),
            state=RunState.new(
                current_user_message="2+2 savings?", recent_thread_history=[]
            ),
            user=USER,
        )
    )
    assert result is None


def test_the_primary_prompt_computes_money_questions_and_keeps_products_off_the_strategy_route() -> (
    None
):
    clause = future_test_window_capability_clause()
    prompt = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )._system_prompt()
    assert clause in prompt
    assert "arithmetic, not a" in clause
    assert "scenario_question=true with no symbols" in clause
    assert "set question_kind=current_external" in clause
    assert "never an asset_universe entry, a strategy or an unsupported symbol" in clause
    assert "answer it in assistant_response with the formula" not in clause


def test_an_answer_after_a_failed_lookup_says_so_when_nothing_is_named(
    monkeypatch,
) -> None:
    from argus.agent_runtime import research_calculation

    seen = _voice(
        monkeypatch,
        [
            _voiced(
                "How many months are left on the loan?",
                [*LOAN, {"name": "periods", "value": None, "source": "user"}],
            )
        ],
    )
    monkeypatch.setattr(research_calculation, "resolve_openrouter_api_key", lambda: "k")
    answered = research_calculation.answer_without_lookup(
        message="Is paying extra on my car loan worth it?",
        language="en",
        user=USER,
        subjects=[],
        not_looked_up=(),
        notes=[],
    )
    assert answered is not None and answered.question_field == "periods"
    assert "The lookup for this answer failed" in seen[0][0]["content"]


def test_the_no_search_answer_writes_its_calculation_before_its_prose() -> None:
    schema = ca.CalculatedVoicedAnswer.model_json_schema()
    assert list(schema["properties"])[0] == "calculation"
    assert schema["required"] == list(schema["properties"])


OFFER = {
    "calculation": {
        "kind": "time_value",
        "solve_for": "payment",
        "inputs": [*LOAN, {"name": "periods", "value": None, "source": "user"}],
    },
    "requested_field": "periods",
    "retrieved": [],
}


def test_taking_the_offer_asks_once_for_the_readers_figures(monkeypatch) -> None:
    seen = _voice(
        monkeypatch,
        [
            _voiced(
                "How many months are left on the loan?",
                [*LOAN, {"name": "periods", "value": None, "source": "user"}],
            )
        ],
    )
    state = RunState.new(
        current_user_message="Work it out with your own figures",
        recent_thread_history=[],
        action_context={
            "type": "calculation_offer",
            "label": "Work it out with your own figures",
        },
    )
    asked = asyncio.run(
        ca.calculation_offer_stage_result(
            state=state, user=USER, selected_thread_metadata={"calculation_offer": OFFER}
        )
    )
    assert asked is not None and asked.outcome == "await_user_reply"
    assert asked.patch["requested_field"] == "periods"
    assert asked.patch["clarification"]["payload"]["calculation"]["kind"] == "time_value"
    assert (
        "The reader chose to work this out with their own figures"
        in seen[0][0]["content"]
    )
    assert ca.CALCULATION_OFFER_TAKEN_REASON_CODE in asked.decision.reason_codes


def test_a_stale_offer_tap_says_so_and_other_turns_are_not_offers(monkeypatch) -> None:
    monkeypatch.setattr(ca, "resolve_openrouter_api_key", lambda: None)
    tapped = RunState.new(
        current_user_message="Work it out with your own figures",
        recent_thread_history=[],
        action_context={"type": "calculation_offer"},
    )
    stale = asyncio.run(
        ca.calculation_offer_stage_result(
            state=tapped, user=USER, selected_thread_metadata={}
        )
    )
    assert stale is not None and stale.outcome == "ready_to_respond"
    without_voicing = asyncio.run(
        ca.calculation_offer_stage_result(
            state=tapped, user=USER, selected_thread_metadata={"calculation_offer": OFFER}
        )
    )
    assert without_voicing is not None and without_voicing.outcome == "await_user_reply"
    assert without_voicing.patch["requested_field"] == "periods"
    plain = RunState.new(current_user_message="hi", recent_thread_history=[])
    assert (
        asyncio.run(
            ca.calculation_offer_stage_result(
                state=plain, user=USER, selected_thread_metadata={}
            )
        )
        is None
    )


def test_a_voiced_answer_that_only_restates_the_question_is_never_published(
    monkeypatch,
) -> None:
    question = "Which credit card should I get?"
    _voice(monkeypatch, [ca.CalculatedVoicedAnswer(lead=question, note="Nothing found.")])
    notes: list[str] = []
    assert (
        ca.calculated_answer(message=question, language="en", user=USER, notes=notes)
        is None
    )
    assert ca.ANSWER_RESTATED_QUESTION_REASON_CODE in notes


def test_a_question_names_only_the_missing_inputs_whatever_the_model_wrote(
    monkeypatch,
) -> None:
    _voice(
        monkeypatch,
        [
            _voiced(
                "What is the monthly payment, number of periods, and total interest for the USD loan?",
                [
                    {"name": "direction", "value": "borrow", "source": "user"},
                    {"name": "present_value", "value": 180000, "source": "user"},
                    {"name": "annual_rate_pct", "value": 14, "source": "user"},
                    {"name": "future_value", "value": 0, "source": "user"},
                    {"name": "periods", "value": None, "source": "user"},
                ],
                solve_for="payment",
            )
        ],
    )
    asked = asyncio.run(
        ca.calculated_answer_stage_result(
            interpretation=_read(question_kind="none", scenario_question=True),
            state=RunState.new(
                current_user_message="I owe money on a boat loan at 9 percent, should I refinance?",
                recent_thread_history=[],
            ),
            user=USER,
        )
    )
    assert asked is not None and asked.outcome == "await_user_reply"
    clarification = asked.patch["clarification"]
    assert asked.patch["assistant_prompt"] == ca.missing_inputs_lead("en")
    assert "interest" not in asked.patch["assistant_prompt"]
    assert "USD" not in asked.patch["assistant_prompt"]
    assert clarification["prompt_source"] == "degraded_fallback"
    assert [item["name"] for item in clarification["missing_inputs"]] == ["periods"]
    assert (
        clarification["missing_inputs"][0]["label"]["locale_key"]
        == "tools.calc.fields.periods"
    )


def test_an_optional_detail_left_blank_is_never_asked_for(monkeypatch) -> None:
    _voice(
        monkeypatch,
        [
            _voiced(
                "What is your payment and when did the loan start?",
                [
                    {"name": "direction", "value": "borrow", "source": "user"},
                    {"name": "present_value", "value": 180000, "source": "user"},
                    {"name": "annual_rate_pct", "value": 14, "source": "user"},
                    {"name": "future_value", "value": 0, "source": "user"},
                    {"name": "payment", "value": None, "source": "user"},
                    {"name": "start_date", "value": None, "source": "user"},
                ],
                solve_for="periods",
            )
        ],
    )
    asked = asyncio.run(
        ca.calculated_answer_stage_result(
            interpretation=_read(question_kind="none", scenario_question=True),
            state=RunState.new(
                current_user_message="I owe money on a boat loan at 9 percent, should I refinance?",
                recent_thread_history=[],
            ),
            user=USER,
        )
    )
    assert asked is not None and asked.outcome == "await_user_reply"
    assert [item["name"] for item in asked.patch["clarification"]["missing_inputs"]] == [
        "payment"
    ]
