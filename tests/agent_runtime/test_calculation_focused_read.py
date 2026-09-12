"""The calculation read is the one model read that maps a money question to a
declared calculation. It runs after the primary interpretation only on the
primary's computed-figure mark, a pending calculation reply or a refusal the
primary chose, so an ordinary turn spends no read; it owns its leads and questions and records when it
reaches the turn."""

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
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    UnsupportedConstraint,
    UserState,
)

CAR_LOAN = {
    "present_value": 180000,
    "annual_rate_pct": 14,
    "direction": "borrow",
    "future_value": 0,
}
PENDING = {
    "last_stage_outcome": "await_user_reply",
    "clarification": {
        "payload": {
            "calculation": {"kind": "time_value", "inputs": CAR_LOAN, "solve_for": "periods"}
        }
    },
}


def _read(**updates: Any) -> StructuredInterpretation:
    base = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="money question",
        semantic_turn_act="educational_question",
        candidate_strategy_draft=StrategySummary(),
        computed_figure_decides=True,
    )
    return base.model_copy(update=updates)


def test_the_read_runs_only_on_the_mark_or_a_pending_reply() -> None:
    trigger = focused.focused_calculation_trigger
    assert trigger(_read()) == focused.MONEY_QUESTION_TRIGGER
    assert trigger(_read(computed_figure_decides=False)) is None, "an ordinary turn"
    assert (
        trigger(_read(intent="unsupported_or_out_of_scope", computed_figure_decides=False))
        == focused.BEFORE_REFUSAL_TRIGGER
    ), "an unmarked refusal is read before it names a capability"
    assert (
        trigger(
            _read(
                intent="unsupported_or_out_of_scope",
                computed_figure_decides=False,
                capability_question_focus="limits",
            )
        )
        is None
    ), "a question about Argus keeps its capability answer"
    assert (
        trigger(_read(intent="unsupported_or_out_of_scope", semantic_turn_act="unsupported_request"))
        == focused.MONEY_QUESTION_TRIGGER
    ), "a marked refusal is read for a calculation before it names a capability"
    assert (
        trigger(_read(intent="strategy_drafting", semantic_turn_act="new_idea"))
        == focused.MONEY_QUESTION_TRIGGER
    ), "a marked draft with nothing to run"
    runnable = StrategySummary(
        strategy_type="buy_and_hold", asset_universe=["AAPL"], capital_amount=10000
    )
    assert (
        trigger(_read(intent="strategy_drafting", semantic_turn_act="new_idea", candidate_strategy_draft=runnable))
        is None
    ), "a runnable test keeps its route"
    unrunnable = UnsupportedConstraint(
        category="unsupported_symbol", raw_value="a local bond", explanation="not listed"
    )
    assert (
        trigger(
            _read(
                intent="strategy_drafting",
                semantic_turn_act="new_idea",
                candidate_strategy_draft=runnable,
                unsupported_constraints=[unrunnable],
            )
        )
        == focused.MONEY_QUESTION_TRIGGER
    ), "a draft that names something the runtime cannot run"
    assert (
        trigger(
            _read(
                intent="strategy_drafting",
                semantic_turn_act="new_idea",
                candidate_strategy_draft=runnable,
                unsupported_constraints=[unrunnable],
                computed_figure_decides=False,
            )
        )
        == focused.BEFORE_REFUSAL_TRIGGER
    ), "an unmarked unrunnable draft is read before its refusal"
    assert trigger(_read(intent="backtest_execution")) is None
    assert trigger(_read(intent="results_explanation", semantic_turn_act="result_followup")) is None
    assert trigger(_read(semantic_turn_act="approval")) is None
    discovery = AssetDiscoveryRequest(relationship="category", category_description="banks")
    assert trigger(_read(asset_discovery=discovery)) is None
    pending = CalculationRequest(kind="time_value", inputs=CAR_LOAN)
    assert (
        trigger(
            _read(intent="strategy_drafting", semantic_turn_act="answer_pending_need", computed_figure_decides=False),
            pending=pending,
        )
        == focused.PENDING_REPLY_TRIGGER
    )


def test_the_read_carries_the_catalogue_the_conversation_and_a_pending_calculation() -> None:
    pending = CalculationRequest(kind="time_value", inputs=CAR_LOAN)
    messages = focused._read_messages(
        "48 months", [{"role": "assistant", "content": "How many months are left?"}], pending
    )
    assert messages[0]["content"].startswith(focused.FOCUSED_CALCULATION_READ_GUIDANCE)
    assert calculation_kinds_clause() in messages[0]["content"]
    assert "Recent conversation" in messages[1]["content"]
    assert "waiting for the user's reply to a time_value calculation" in messages[2]["content"]
    assert '"present_value": 180000' in messages[2]["content"]
    assert messages[-1] == {"role": "user", "content": "48 months"}
    assert len(focused._read_messages("hello", [])) == 2


def _run(
    interpretation: StructuredInterpretation,
    monkeypatch: pytest.MonkeyPatch,
    read: Any,
    *,
    metadata: dict[str, Any] | None = None,
    message: str = "I owe 180,000 at 14 percent on the car",
):
    seen: list[dict[str, Any]] = []

    async def invoke(**kwargs):
        assert kwargs["schema_model"] is focused.FocusedCalculationRead
        seen.append(kwargs)
        if isinstance(read, Exception):
            raise read
        return read

    monkeypatch.setattr(focused, "invoke_openrouter_json_schema", invoke)
    result = asyncio.run(
        turn.calculation_turn_stage_result(
            interpretation=interpretation,
            state=RunState.new(current_user_message=message, recent_thread_history=[]),
            user=UserState(user_id="u1", language_preference="en", currency="USD"),
            selected_thread_metadata=metadata or {},
        )
    )
    return result, seen


def test_a_mapped_question_asks_the_reads_own_question_for_the_missing_input(
    monkeypatch,
) -> None:
    interpretation = _read(assistant_response="Paying extra is a personal choice.")
    read = focused.FocusedCalculationRead(
        answered_by_a_calculation=True,
        calculation=CalculationRequest(
            kind="time_value",
            inputs=CAR_LOAN,
            solve_for="periods",
            follow_up_questions=["What is your current monthly payment?"],
        ),
    )
    result, _ = _run(interpretation, monkeypatch, read)
    assert result is not None
    assert result.outcome == "await_user_reply"
    assert result.patch["assistant_prompt"] == "What is your current monthly payment?"
    assert result.patch["requested_field"] == "payment"
    pending = result.patch["clarification"]["payload"]["calculation"]
    assert pending["kind"] == "time_value"
    assert pending["inputs"]["present_value"] == 180000
    assert focused.MONEY_QUESTION_TRIGGER in interpretation.reason_codes
    assert focused.READ_MAPPED_REASON_CODE in interpretation.reason_codes


def test_a_declined_failed_or_empty_read_leaves_the_turn_to_the_primary_route(
    monkeypatch,
) -> None:
    for read in (
        focused.FocusedCalculationRead(answered_by_a_calculation=False),
        focused.FocusedCalculationRead(
            answered_by_a_calculation=True, calculation=CalculationRequest(kind=None)
        ),
        RuntimeError("provider down"),
        None,
    ):
        interpretation = _read()
        result, seen = _run(interpretation, monkeypatch, read)
        assert result is None
        assert len(seen) == 1
        assert focused.READ_MAPPED_REASON_CODE not in interpretation.reason_codes
    backtest = _read(intent="backtest_execution")
    result, seen = _run(backtest, monkeypatch, None)
    assert result is None and seen == [], "a marked test keeps its route and spends no read"
    assert focused.ROUTE_KEPT_REASON_CODE in backtest.reason_codes


def test_an_ordinary_turn_spends_no_calculation_read(monkeypatch) -> None:
    for intent in ("conversation_followup", "beginner_guidance"):
        ordinary = _read(intent=intent, computed_figure_decides=False)
        result, seen = _run(ordinary, monkeypatch, None, message="What is compound interest?")
        assert result is None and seen == []
        assert ordinary.reason_codes == []


def test_a_broad_question_gets_the_reads_three_questions_under_argus_own_lead(
    monkeypatch,
) -> None:
    interpretation = _read(
        intent="unsupported_or_out_of_scope",
        semantic_turn_act="unsupported_request",
        assistant_response="I cannot recommend a card.",
    )
    questions = [
        "Do you carry a balance from month to month?",
        "About how much do you spend on the card each month?",
        "Which cards are you choosing between?",
    ]
    read = focused.FocusedCalculationRead(
        answered_by_a_calculation=True,
        calculation=CalculationRequest(kind=None, follow_up_questions=questions),
    )
    result, _ = _run(interpretation, monkeypatch, read, message="Which credit card should I get?")
    assert result is not None
    assert result.outcome == "ready_to_respond"
    assert result.patch["next_steps"]["items"] == [
        {"type": "question", "text": text} for text in questions
    ]
    assert result.patch["assistant_response"] == turn._follow_up_lead(
        UserState(user_id="u1", language_preference="en")
    )


def test_a_reply_to_a_pending_calculation_is_read_with_it_and_computes(monkeypatch) -> None:
    interpretation = _read(intent="strategy_drafting", semantic_turn_act="answer_pending_need")
    read = focused.FocusedCalculationRead(
        answered_by_a_calculation=True,
        calculation=CalculationRequest(kind="time_value", inputs={"payment": 3000}),
    )
    result, seen = _run(interpretation, monkeypatch, read, metadata=PENDING, message="3,000 a month")
    assert result is not None
    assert result.outcome == "ready_to_respond"
    card = result.patch["final_response_payload"]["tool_result_cards"][0]
    assert card["tool_name"] == "time_value" and card["outcome"]["status"] == "succeeded"
    assert "time_value calculation" in seen[0]["messages"][-2]["content"]
    assert focused.PENDING_REPLY_TRIGGER in interpretation.reason_codes
    assert turn.PENDING_MERGED_REASON_CODE in interpretation.reason_codes


def test_a_reply_the_read_does_not_map_leaves_the_pending_calculation_alone(
    monkeypatch,
) -> None:
    interpretation = _read(intent="strategy_drafting", semantic_turn_act="new_idea")
    read = focused.FocusedCalculationRead(answered_by_a_calculation=False)
    result, _ = _run(interpretation, monkeypatch, read, metadata=PENDING, message="backtest AAPL instead")
    assert result is None
    assert turn.PENDING_MERGED_REASON_CODE not in interpretation.reason_codes
