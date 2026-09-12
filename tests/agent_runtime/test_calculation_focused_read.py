"""The focused calculation read runs only on a typed contradiction in the
primary read, recovers a declared kind, and records that it fired."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.agent_runtime import calculation_turn as turn
from argus.agent_runtime.interpreter import calculation_focused_read as focused
from argus.agent_runtime.interpreter.calculation_request import (
    CalculationRequest,
    calculation_kinds_clause,
)
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, StrategySummary, UserState


def _read(**updates: Any) -> StructuredInterpretation:
    base = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="money question",
        semantic_turn_act="educational_question",
        candidate_strategy_draft=StrategySummary(),
    )
    return base.model_copy(update=updates)


def test_the_read_runs_only_on_a_typed_contradiction() -> None:
    assert (
        focused.focused_calculation_trigger(
            _read(
                calculation=CalculationRequest(
                    kind=None, inputs={"present_value": 180000}
                )
            )
        )
        == focused.KIND_MISSING_TRIGGER
    )
    assert (
        focused.focused_calculation_trigger(
            _read(calculation=CalculationRequest(kind="time_value"))
        )
        is None
    )
    concept = ResearchQueryExtraction(question_kind="concept")
    assert (
        focused.focused_calculation_trigger(_read(research_query=concept))
        == focused.UNROUTED_CONCEPT_TRIGGER
    )
    assert (
        focused.focused_calculation_trigger(_read()) is None
    ), "no research read, such as a greeting"
    assert (
        focused.focused_calculation_trigger(
            _read(
                research_query=ResearchQueryExtraction(
                    question_kind="company_lookup", symbols=["AAPL"]
                )
            )
        )
        is None
    )
    assert (
        focused.focused_calculation_trigger(
            _read(
                research_query=concept,
                intent="strategy_drafting",
                semantic_turn_act="new_idea",
            )
        )
        is None
    )
    discovery = AssetDiscoveryRequest(
        relationship="category", category_description="banks"
    )
    assert (
        focused.focused_calculation_trigger(
            _read(research_query=concept, asset_discovery=discovery)
        )
        is None
    )
    draft = StrategySummary(
        strategy_type="buy_and_hold", asset_universe=["AAPL"], capital_amount=1000
    )
    assert (
        focused.focused_calculation_trigger(
            _read(research_query=concept, candidate_strategy_draft=draft)
        )
        is None
    )


def test_the_read_carries_the_declared_catalogue_and_the_message() -> None:
    messages = focused._read_messages(
        "I owe 25,000 at 9 percent", [{"role": "user", "content": "hi"}]
    )
    assert messages[0]["content"].startswith(focused.FOCUSED_CALCULATION_READ_GUIDANCE)
    assert calculation_kinds_clause() in messages[0]["content"]
    assert "Recent conversation" in messages[1]["content"]
    assert messages[-1] == {"role": "user", "content": "I owe 25,000 at 9 percent"}


def _run(
    interpretation: StructuredInterpretation, monkeypatch: pytest.MonkeyPatch, read: Any
):
    async def invoke(**kwargs):
        assert kwargs["schema_model"] is focused.FocusedCalculationRead
        if isinstance(read, Exception):
            raise read
        return read

    monkeypatch.setattr(focused, "invoke_openrouter_json_schema", invoke)
    return asyncio.run(
        turn.calculation_turn_stage_result(
            interpretation=interpretation,
            state=RunState.new(
                current_user_message="I owe 180,000 at 14 percent on the car",
                recent_thread_history=[],
            ),
            user=UserState(user_id="u1", language_preference="en", currency="USD"),
            selected_thread_metadata={},
        )
    )


def test_a_missing_kind_is_recovered_and_the_models_question_asks_for_the_input(
    monkeypatch,
) -> None:
    interpretation = _read(
        calculation=CalculationRequest(
            kind=None,
            inputs={
                "present_value": 180000,
                "annual_rate_pct": 14,
                "direction": "borrow",
            },
            follow_up_questions=["What is your current monthly payment?"],
        ),
        requires_clarification=True,
    )
    read = focused.FocusedCalculationRead(
        wants_a_computed_figure=True,
        calculation=CalculationRequest(
            kind="time_value",
            inputs={"future_value": 0},
            solve_for="periods",
            follow_up_questions=["What is your current monthly payment?"],
        ),
    )
    result = _run(interpretation, monkeypatch, read)
    assert result is not None
    assert result.outcome == "await_user_reply"
    assert result.patch["assistant_prompt"] == "What is your current monthly payment?"
    assert result.patch["requested_field"] == "payment"
    pending = result.patch["clarification"]["payload"]["calculation"]
    assert pending["kind"] == "time_value"
    assert (
        pending["inputs"]["present_value"] == 180000
    ), "the primary's stated inputs are kept"
    assert focused.FOCUSED_READ_REASON_CODE in interpretation.reason_codes


def test_a_declined_or_failed_read_leaves_the_primary_follow_ups(monkeypatch) -> None:
    for read in (
        focused.FocusedCalculationRead(wants_a_computed_figure=False),
        RuntimeError("provider down"),
        None,
    ):
        interpretation = _read(
            calculation=CalculationRequest(
                kind=None, follow_up_questions=["What is the price you have in mind?"]
            ),
            assistant_response="A few details would help.",
        )
        result = _run(interpretation, monkeypatch, read)
        assert result is not None
        assert result.patch["next_steps"]["items"] == [
            {"type": "question", "text": "What is the price you have in mind?"}
        ]
        assert focused.FOCUSED_READ_REASON_CODE not in interpretation.reason_codes


def test_an_unrouted_concept_question_that_wants_a_figure_becomes_a_calculation(
    monkeypatch,
) -> None:
    interpretation = _read(
        research_query=ResearchQueryExtraction(question_kind="concept"),
        intent="beginner_guidance",
    )
    read = focused.FocusedCalculationRead(
        wants_a_computed_figure=True,
        calculation=CalculationRequest(
            kind="time_value",
            inputs={
                "direction": "save",
                "present_value": 10000,
                "payment": 0,
                "annual_rate_pct": 5,
                "periods": 120,
            },
            solve_for="future_value",
        ),
    )
    result = _run(interpretation, monkeypatch, read)
    assert result is not None
    card = result.patch["final_response_payload"]["tool_result_cards"][0]
    assert card["tool_name"] == "time_value" and card["outcome"]["status"] == "succeeded"
