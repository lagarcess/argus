"""Any grounded math, step 9: the model maps a money question to a declared
calculation and Argus computes it in process.

The interpreter's typed ``calculation`` read is the only routing signal; no
phrase, regex or language gate runs before it. A missing input is the model's
own clarification, asked once and merged on the reply. A broad question gets
the model's own follow-ups as question steps, never a catalogue. Every guard
that compensates for the read records a reason code on the turn.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from argus.agent_runtime import calculation_turn as turn
from argus.agent_runtime.calculation_rows import (
    MARKET_COUNTERFACTUAL_KIND,
    market_counterfactual_rows,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.calculation_request import (
    CALCULATION_GUIDANCE,
    CalculationRequest,
    calculation_kinds,
    calculation_kinds_clause,
)
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret import interpret_stage_async
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState
from argus.api.chat.runtime_user import runtime_user_for
from argus.api.schemas import User
from argus.domain.calculations import get_calculation_declarations
from argus.domain.tool_declaration import ToolCatalog


@pytest.fixture(autouse=True)
def _no_focused_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests pin the turn after a primary read; the backstop has its own."""
    from argus.agent_runtime.interpreter import calculation_focused_read

    async def declined(**_kwargs):
        return None

    monkeypatch.setattr(
        calculation_focused_read, "invoke_openrouter_json_schema", declined
    )


SAVING_PLAN = {
    "direction": "save",
    "present_value": 10_000,
    "payment": 0,
    "annual_rate_pct": 5,
    "periods": 120,
}


def _read(
    calculation: dict[str, Any] | None,
    *,
    assistant_response: str | None = "Here is what that plan grows to.",
    requires_clarification: bool = False,
    missing_required_fields: list[str] | None = None,
    research_query: dict[str, Any] | None = None,
) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="compute a plan",
        semantic_turn_act="educational_question",
        requires_clarification=requires_clarification,
        missing_required_fields=list(missing_required_fields or []),
        assistant_response=assistant_response,
        candidate_strategy_draft=StrategySummary(),
        calculation=(
            CalculationRequest.model_validate(calculation)
            if calculation is not None
            else None
        ),
        research_query=(
            ResearchQueryExtraction.model_validate(research_query)
            if research_query is not None
            else None
        ),
    )


def _run(
    interpretation: StructuredInterpretation,
    *,
    user: UserState | None = None,
    metadata: dict[str, Any] | None = None,
    message: str = "If I put 10,000 away at 5% for ten years, what do I end up with?",
) -> StageResult | None:
    return asyncio.run(
        turn.calculation_turn_stage_result(
            interpretation=interpretation,
            state=RunState.new(current_user_message=message, recent_thread_history=[]),
            user=user
            or UserState(user_id="u1", language_preference="en", currency="USD"),
            selected_thread_metadata=dict(metadata or {}),
        )
    )


def _card(result: StageResult) -> dict[str, Any]:
    cards = result.patch["final_response_payload"]["tool_result_cards"]
    assert len(cards) == 1
    return cards[0]


def test_a_stated_plan_computes_in_process_and_states_no_figure_in_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.domain.research import perplexity_agent

    def no_provider(*_args, **_kwargs):
        raise AssertionError("a calculation never calls a provider")

    monkeypatch.setattr(
        perplexity_agent.PerplexityAgentClient, "run_research", no_provider
    )
    result = _run(
        _read({"kind": "time_value", "inputs": SAVING_PLAN, "solve_for": "future_value"})
    )
    assert result is not None
    assert result.outcome == "ready_to_respond"
    card = _card(result)
    assert card["tool_name"] == "time_value"
    assert card["outcome"]["status"] == "succeeded"
    assert card["arguments"]["future_value"] is None
    assert card["arguments"]["currency"] == "USD"
    patch = result.patch
    assert patch["assistant_response"] == "Here is what that plan grows to."
    assert not any(character.isdigit() for character in patch["assistant_response"])
    assert patch["tool_calls"] == []
    assert "research" not in patch
    assert "follow_up" not in json.dumps(patch, default=str)
    assert result.decision is not None
    assert turn.CALCULATION_ANSWER_REASON_CODE in result.decision.reason_codes


def test_the_market_counterfactual_is_offered_with_the_users_amounts_never_run() -> None:
    result = _run(
        _read({"kind": "time_value", "inputs": SAVING_PLAN, "solve_for": "future_value"})
    )
    assert result is not None
    rows = result.patch["next_experiments"]["rows"]
    assert [row["kind"] for row in rows] == [MARKET_COUNTERFACTUAL_KIND]
    assert rows[0]["send_text"] == (
        "Test buying and holding SPY with 10000 USD over the last 10 years"
    )
    assert "10,000 USD" in rows[0]["label"]
    assert result.patch["next_steps"]["items"] == [
        {"type": "test", "kind": MARKET_COUNTERFACTUAL_KIND}
    ]
    # Offered, not run: the turn dispatched exactly the calculation.
    assert [record["tool_name"] for record in result.patch["tool_call_records"]] == [
        "time_value"
    ]


def test_a_monthly_plan_offers_the_same_monthly_buys_in_the_market() -> None:
    rows = market_counterfactual_rows(
        {"currency": "DOP", "payment": 5000, "periods": 240, "periods_per_year": 12},
        language="es-419",
    )
    assert rows is not None
    assert rows["rows"][0]["send_text"] == (
        "Prueba comprar 5000 DOP de SPY cada mes durante los últimos 20 años"
    )
    assert (
        market_counterfactual_rows({"currency": "USD", "periods": 7}, language="en")
        is None
    )
    assert (
        market_counterfactual_rows(
            {"currency": "USD", "present_value": 100, "periods": 400}, language="en"
        )
        is None
    )


def test_a_missing_input_is_the_models_own_clarification_asked_once() -> None:
    result = _run(
        _read(
            {
                "kind": "time_value",
                "inputs": {"direction": "save", "payment": 500, "annual_rate_pct": 5},
                "solve_for": "future_value",
            },
            assistant_response="For how many months would you keep that up?",
            requires_clarification=True,
            missing_required_fields=["periods"],
        )
    )
    assert result is not None
    assert result.outcome == "await_user_reply"
    patch = result.patch
    assert patch["assistant_prompt"] == "For how many months would you keep that up?"
    assert patch["requested_field"] == "periods"
    clarification = patch["clarification"]
    assert clarification["kind"] == "clarification"
    assert clarification["reason_code"] == turn.INPUT_MISSING_REASON_CODE
    assert clarification["prompt_source"] == "llm_generated"
    pending = clarification["payload"]["calculation"]
    assert pending["kind"] == "time_value"
    assert pending["inputs"] == {
        "direction": "save",
        "payment": 500,
        "annual_rate_pct": 5,
        "currency": "USD",
    }
    assert "final_response_payload" not in patch


def test_the_reply_merges_the_pending_calculation_and_computes() -> None:
    first = _run(
        _read(
            {
                "kind": "time_value",
                "inputs": {
                    "direction": "save",
                    "present_value": 0,
                    "payment": 500,
                    "annual_rate_pct": 5,
                },
                "solve_for": "future_value",
            },
            requires_clarification=True,
            missing_required_fields=["periods"],
        )
    )
    assert first is not None
    metadata = {
        "last_stage_outcome": "await_user_reply",
        "clarification": first.patch["clarification"],
    }
    reply = _read(
        {"kind": "time_value", "inputs": {"periods": 240}},
        assistant_response="Here is the plan over those months.",
    )
    result = _run(reply, metadata=metadata, message="20 years")
    assert result is not None
    assert result.outcome == "ready_to_respond"
    card = _card(result)
    assert card["arguments"]["periods"] == 240
    assert card["arguments"]["payment"] == 500
    assert card["arguments"]["future_value"] is None
    assert card["outcome"]["status"] == "succeeded"
    assert turn.PENDING_MERGED_REASON_CODE in result.decision.reason_codes


def test_a_pending_calculation_yields_to_a_different_kind_the_user_moved_to() -> None:
    first = _run(
        _read(
            {
                "kind": "time_value",
                "inputs": {"direction": "save"},
                "solve_for": "payment",
            },
            requires_clarification=True,
        )
    )
    assert first is not None and first.outcome == "await_user_reply"
    metadata = {
        "last_stage_outcome": "await_user_reply",
        "clarification": first.patch["clarification"],
    }
    result = _run(
        _read(
            {
                "kind": "debt_to_income",
                "inputs": {"monthly_debt_payments": 1500, "monthly_income": 5000},
                "solve_for": "ratio_pct",
            }
        ),
        metadata=metadata,
    )
    assert result is not None
    assert _card(result)["tool_name"] == "debt_to_income"
    assert turn.PENDING_MERGED_REASON_CODE not in result.decision.reason_codes


def test_a_broad_question_gets_the_models_follow_ups_as_question_steps() -> None:
    result = _run(
        _read(
            {
                "kind": None,
                "follow_up_questions": [
                    "How much can you put aside each month?",
                    "For how many years?",
                    "Is this money you might need before then?",
                ],
            },
            assistant_response="A few details would let me compute this for you.",
        ),
        message="How should I save for a house?",
    )
    assert result is not None
    assert result.outcome == "ready_to_respond"
    patch = result.patch
    assert (
        patch["assistant_response"] == "A few details would let me compute this for you."
    )
    assert patch["next_steps"]["items"] == [
        {"type": "question", "text": "How much can you put aside each month?"},
        {"type": "question", "text": "For how many years?"},
        {"type": "question", "text": "Is this money you might need before then?"},
    ]
    assert "next_experiments" not in patch
    assert "final_response_payload" not in patch
    assert turn.CALCULATION_FOLLOW_UPS_REASON_CODE in result.decision.reason_codes


def test_follow_ups_without_a_lead_never_claim_a_calculation_exists() -> None:
    for language, expected in (
        (
            "en",
            "A couple more details would let me compute this. Pick a question to continue.",
        ),
        (
            "es-419",
            "Con un par de datos más puedo calcularlo. Elige una pregunta para seguir.",
        ),
    ):
        result = _run(
            _read(
                {"kind": None, "follow_up_questions": ["When do you want to buy it?"]},
                assistant_response=None,
            ),
            user=UserState(user_id="u1", language_preference=language),
        )
        assert result is not None
        assert result.patch["assistant_response"] == expected
        assert "calculation from your numbers" not in result.patch["assistant_response"]
        assert "final_response_payload" not in result.patch


def test_a_read_with_neither_a_kind_nor_follow_ups_leaves_the_turn_alone() -> None:
    assert _run(_read({"kind": None})) is None
    assert _run(_read(None)) is None


def test_published_inputs_route_to_research_which_computes_this_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import research_answer

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    dispatched: list[Any] = []

    async def dispatch(query, **kwargs):
        dispatched.append((query, kwargs["interpretation"].calculation))
        return StageResult(
            outcome="ready_to_respond", stage_patch={"assistant_response": "computed"}
        )

    monkeypatch.setattr(research_answer, "_dispatch", dispatch)
    interpretation = _read(
        {
            "kind": "time_value",
            "inputs": {
                "direction": "save",
                "present_value": 0,
                "annual_rate_pct": 0,
                "periods": 12,
            },
            "solve_for": "payment",
            "retrieve": ["future_value"],
        }
    )
    result = _run(interpretation, message="¿Cuánto debo ahorrar al mes para una iPad?")
    assert result is not None and result.patch["assistant_response"] == "computed"
    ((query, calculation),) = dispatched
    assert query.question_kind == "current_external" and query.symbols == []
    assert calculation.retrieve == ["future_value"]
    assert turn.RESEARCH_QUERY_SYNTHESIZED_REASON_CODE in interpretation.reason_codes
    assert turn.RETRIEVAL_OWNS_REASON_CODE in interpretation.reason_codes

    named = _read(
        {
            "kind": "valuation_scenarios",
            "inputs": {"symbol": "NVDA", "horizon_years": 10},
            "retrieve": ["price", "per_share", "growth_base_pct"],
        },
        research_query={
            "question_kind": "company_lookup",
            "symbols": ["NVDA"],
            "scenario_question": True,
        },
    )
    dispatched.clear()
    assert _run(named) is not None
    assert dispatched[0][0].symbols == ["NVDA"]
    assert turn.RESEARCH_QUERY_SYNTHESIZED_REASON_CODE not in named.reason_codes


def test_an_input_only_the_user_knows_is_asked_before_any_page_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import research_answer

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    dispatched: list[Any] = []

    async def dispatch(query, **kwargs):
        dispatched.append(query)
        return StageResult(
            outcome="ready_to_respond", stage_patch={"assistant_response": "computed"}
        )

    monkeypatch.setattr(research_answer, "_dispatch", dispatch)
    first = _run(
        _read(
            {
                "kind": "time_value",
                "inputs": {"direction": "save", "present_value": 0, "annual_rate_pct": 0},
                "solve_for": "payment",
                "retrieve": ["future_value"],
            },
            assistant_response="Over how many months do you want to save?",
            requires_clarification=True,
            missing_required_fields=["periods"],
        )
    )
    assert first is not None and first.outcome == "await_user_reply"
    assert first.patch["requested_field"] == "periods"
    assert dispatched == [], "no page is read while the user's own input is missing"
    reply = _run(
        _read({"kind": "time_value", "inputs": {"periods": 10}}),
        metadata={
            "last_stage_outcome": "await_user_reply",
            "clarification": first.patch["clarification"],
        },
    )
    assert reply is not None and reply.patch["assistant_response"] == "computed"
    assert len(dispatched) == 1


def test_without_research_a_published_input_is_asked_of_the_user() -> None:
    result = _run(
        _read(
            {
                "kind": "valuation_scenarios",
                "inputs": {"symbol": "NVDA", "horizon_years": 10, "amount": 10000},
                "retrieve": ["price", "per_share", "growth_base_pct"],
            },
            assistant_response=None,
        )
    )
    assert result is not None
    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "price"
    assert (
        result.patch["clarification"]["payload"]["calculation"]["kind"]
        == "valuation_scenarios"
    )


def test_argument_names_are_advertised_and_stray_names_are_dropped_with_a_record() -> (
    None
):
    from argus.agent_runtime.interpreter.calculation_request import (
        calculation_argument_names,
    )

    names = set(calculation_argument_names())
    assert {
        "future_value",
        "present_value",
        "annual_rate_pct",
        "price",
        "per_share",
    } <= names
    assert "currency" not in names and "sources" not in names
    schema = CalculationRequest.model_json_schema()["properties"]
    assert set(schema["retrieve"]["items"]["enum"]) == names
    assert schema["solve_for"]["anyOf"][0]["enum"] == sorted(names)
    assert CalculationRequest.model_json_schema()["required"] == [
        "inputs",
        "solve_for",
        "retrieve",
        "follow_up_questions",
        "kind",
    ]
    assert CalculationRequest.model_validate({"kind": "time_value"}).inputs == {}
    pairs = schema["inputs"]
    assert pairs["type"] == "array"
    assert pairs["items"]["additionalProperties"] is False
    assert set(pairs["items"]["properties"]["name"]["enum"]) == names | {"currency"}
    parsed = CalculationRequest.model_validate(
        {
            "kind": "time_value",
            "inputs": [
                {"name": "present_value", "value": 25000},
                {"name": "currency", "value": "USD"},
            ],
        }
    )
    assert parsed.inputs == {"present_value": 25000, "currency": "USD"}
    assert CalculationRequest.model_validate({"inputs": {"payment": 5}}).inputs == {
        "payment": 5
    }
    interpretation = _read(
        {
            "kind": "time_value",
            "inputs": SAVING_PLAN,
            "solve_for": "the ending balance",
            "retrieve": ["iPad price"],
        }
    )
    result = _run(interpretation)
    assert result is not None
    assert result.outcome == "await_user_reply" or result.patch["final_response_payload"]
    assert turn.UNKNOWN_NAMES_REASON_CODE in interpretation.reason_codes


def test_a_kind_the_catalog_lacks_is_recorded_and_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.domain import capability_registry

    without_time_value = ToolCatalog(
        tuple(
            declaration
            for declaration in get_calculation_declarations()
            if declaration.name != "time_value"
        )
    )
    monkeypatch.setattr(
        capability_registry, "get_tool_catalog", lambda **_: without_time_value
    )
    interpretation = _read(
        {"kind": "time_value", "inputs": SAVING_PLAN, "solve_for": "future_value"}
    )
    assert _run(interpretation) is None
    assert turn.KIND_UNKNOWN_REASON_CODE in interpretation.reason_codes


def test_undeclared_inputs_and_a_valued_unknown_are_dropped_and_recorded() -> None:
    interpretation = _read(
        {
            "kind": "time_value",
            "inputs": {**SAVING_PLAN, "future_value": 16_288.95, "tax_rate": 20},
            "solve_for": "future_value",
        }
    )
    result = _run(interpretation)
    assert result is not None
    card = _card(result)
    assert "tax_rate" not in card["arguments"]
    assert card["arguments"]["future_value"] is None
    assert card["outcome"]["status"] == "succeeded"
    codes = result.decision.reason_codes
    assert turn.INPUTS_DROPPED_REASON_CODE in codes
    assert turn.SOLVE_FOR_CLEARED_REASON_CODE in codes


def test_the_profile_currency_counts_the_answer_and_a_default_is_recorded() -> None:
    read = {"kind": "time_value", "inputs": SAVING_PLAN, "solve_for": "future_value"}
    with_currency = _run(
        _read(read),
        user=UserState(user_id="u1", language_preference="es-419", currency="DOP"),
    )
    assert with_currency is not None
    assert _card(with_currency)["arguments"]["currency"] == "DOP"
    assert turn.CURRENCY_DEFAULTED_REASON_CODE not in with_currency.decision.reason_codes

    without = _run(_read(read), user=UserState(user_id="u2", language_preference="en"))
    assert without is not None
    assert _card(without)["arguments"]["currency"] == turn.DEFAULT_CURRENCY
    assert turn.CURRENCY_DEFAULTED_REASON_CODE in without.decision.reason_codes

    stated = _run(
        _read({**read, "inputs": {**SAVING_PLAN, "currency": "mxn"}}),
        user=UserState(user_id="u3", language_preference="en"),
    )
    assert stated is not None
    assert _card(stated)["arguments"]["currency"] == "MXN"


def test_a_lead_that_states_a_figure_is_replaced_and_recorded() -> None:
    result = _run(
        _read(
            {"kind": "time_value", "inputs": SAVING_PLAN, "solve_for": "future_value"},
            assistant_response="You would end up with about $16,470.",
        )
    )
    assert result is not None
    assert result.patch["assistant_response"] == (
        "Here is the calculation from your numbers. Change any input to recompute it."
    )
    assert turn.LEAD_REPLACED_REASON_CODE in result.decision.reason_codes


def test_a_plan_that_does_not_solve_keeps_its_card_and_offers_no_test() -> None:
    result = _run(
        _read(
            {
                "kind": "time_value",
                "inputs": {
                    "direction": "borrow",
                    "present_value": 180_000,
                    "payment": 2_000,
                    "future_value": 0,
                    "annual_rate_pct": 14,
                },
                "solve_for": "periods",
            },
            assistant_response="Here is how long that loan would take to repay.",
        ),
        user=UserState(user_id="u1", language_preference="es-419", currency="DOP"),
    )
    assert result is not None
    card = _card(result)
    assert card["outcome"]["status"] == "invalid"
    assert card["outcome"]["failure"]["code"] == "payment_below_interest"
    assert card["outcome"]["failure"]["repair"]["changes"]["payment"] > 2_000
    assert result.patch["assistant_response"].startswith("Los números tal como están")
    assert "next_experiments" not in result.patch


def test_a_missing_required_argument_is_asked_for_with_a_language_fallback() -> None:
    result = _run(
        _read(
            {"kind": "bond_value", "inputs": {"face_value": 1000, "years": 3}},
            assistant_response=None,
        ),
        user=UserState(user_id="u1", language_preference="es-419", currency="DOP"),
    )
    assert result is not None
    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "coupon_rate_pct"
    assert result.patch["assistant_prompt"] == (
        "Para calcularlo me falta un dato: coupon rate (%). ¿Qué valor uso?"
    )
    assert result.patch["clarification"]["prompt_source"] == "degraded_fallback"


class _Interpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response

    async def ainvoke(self, request):
        return self.response


def test_the_calculation_owns_the_turn_through_the_whole_interpret_stage() -> None:
    result = asyncio.run(
        interpret_stage_async(
            state=RunState.new(
                current_user_message="What is 4 a year on 100 as a yield?",
                recent_thread_history=[],
            ),
            user=UserState(user_id="u1", language_preference="en", currency="USD"),
            latest_task_snapshot=None,
            selected_thread_metadata={},
            structured_interpreter=_Interpreter(
                _read(
                    {
                        "kind": "income_yield",
                        "inputs": {"annual_income": 4, "price": 100},
                        "solve_for": "yield_pct",
                    },
                    assistant_response="Here is that yield.",
                )
            ),
        )
    )
    assert result.outcome == "ready_to_respond"
    card = _card(result)
    assert card["tool_name"] == "income_yield"
    assert card["outcome"]["result"]["yield_pct"] == 4
    assert result.patch["assistant_response"] == "Here is that yield."
    assert result.patch.get("confirmation_payload") is None


def test_the_prompt_reads_the_guidance_and_the_catalogue_of_declared_kinds() -> None:
    prompt = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )._system_prompt()
    assert CALCULATION_GUIDANCE in prompt
    clause = calculation_kinds_clause()
    assert clause in prompt
    for declaration in get_calculation_declarations():
        assert f"- {declaration.name}: {declaration.description}" in clause
        for rule in declaration.rules:
            assert f"Exactly one blank among {', '.join(rule.fields)}." in clause
    assert "direction (save or borrow)" in clause
    assert "items (list of {label, symbol, value})" in clause
    assert "start_date (ISO date)" in clause
    assert "sources" not in clause
    follow_ups = CalculationRequest.model_fields["follow_up_questions"]
    assert "Never a list of what Argus can calculate" in str(follow_ups.description)
    assert (
        "Leave kind null and fill follow_up_questions only when no kind"
        in CALCULATION_GUIDANCE
    )
    assert "fill calculation with the kind and the stated inputs" in prompt
    assert "answer it in assistant_response with the formula" not in prompt


def test_the_response_schema_types_the_calculation_and_copies_it_through() -> None:
    assert set(calculation_kinds()) == {
        declaration.name for declaration in get_calculation_declarations()
    }
    field = LLMInterpretationResponse.model_fields["calculation"]
    assert field.default is None
    assert "computes" in str(field.description)
    schema = CalculationRequest.model_json_schema()
    assert set(schema["properties"]) == {
        "kind",
        "inputs",
        "solve_for",
        "retrieve",
        "follow_up_questions",
    }
    with pytest.raises(ValueError):
        CalculationRequest(kind="loan_wizard")
    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="compute",
        semantic_turn_act="educational_question",
        calculation={"kind": "time_value", "inputs": SAVING_PLAN, "solve_for": "periods"},
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    runtime = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="how long to reach it",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )
    assert runtime.calculation == response.calculation


def test_the_runtime_user_carries_the_profile_currency() -> None:
    profile = User.model_validate(
        {
            "id": "user-1",
            "email": "one@example.com",
            "country": "DO",
            "created_at": "2026-09-12T00:00:00Z",
            "updated_at": "2026-09-12T00:00:00Z",
        }
    )
    user = runtime_user_for(user_id="user-1", profile=profile, turn_language=None)
    assert user.currency == "DOP"
    assert user.country == "DO"
