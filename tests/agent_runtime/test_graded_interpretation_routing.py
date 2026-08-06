"""Regression locks for graded interpretation routing.

A resolved asset, date, or injected benchmark names what the user is talking
about; only execution evidence may pull a turn onto the strategy route. This is
the macro fix behind the knowledge-question interrogation and the ValueError
dead ends: partial understanding gets a destination instead of a discard.
"""

from __future__ import annotations

import asyncio
from typing import Any

from argus.agent_runtime.interpreter.draft_shape import strategy_has_execution_evidence
from argus.agent_runtime.interpreter.focused_extraction import (
    strategy_extraction_repair_is_allowed,
)
from argus.agent_runtime.llm_interpreter import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
    _structured_interpretation_has_required_shape,
)
from argus.agent_runtime.stages.interpret import (
    InterpretationRequest,
    interpret_stage_async,
)
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)

USER = UserState(user_id="graded", language_preference="es")


def _bare_request(message: str) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=None,
        selected_thread_metadata={},
        user=USER,
    )


def _response(**overrides: Any) -> LLMInterpretationResponse:
    payload: dict[str, Any] = {
        "intent": "unsupported_or_out_of_scope",
        "user_goal_summary": "graded",
        "task_relation": "new_task",
        "requires_clarification": True,
        "assistant_response": "",
        "semantic_turn_act": "unsupported_request",
        "candidate_strategy_draft": LLMStrategyDraft(),
    }
    payload.update(overrides)
    return LLMInterpretationResponse(**payload)


def test_reference_fields_are_not_execution_evidence() -> None:
    reference_only = StrategySummary(
        asset_universe=["SPY"],
        asset_class="equity",
        date_range="last 1 year",
        timeframe="1d",
        comparison_baseline="SPY",
    )
    assert strategy_has_execution_evidence(reference_only) is False
    assert strategy_has_execution_evidence(
        StrategySummary(entry_logic="SMA 50 crosses above SMA 200")
    )
    assert strategy_has_execution_evidence(StrategySummary(capital_amount=1000.0))
    assert strategy_has_execution_evidence(
        LLMStrategyDraft(strategy_type="buy_and_hold")
    )


class _StubInterpreter:
    def __init__(self, interpretation: Any) -> None:
        self._interpretation = interpretation
        self.last_failure_kind = None
        self.last_status = "used"

    def __call__(self, request: InterpretationRequest) -> Any:
        return self._interpretation

    async def ainvoke(self, request: InterpretationRequest) -> Any:
        return self._interpretation


def _run_stage(interpretation: LLMInterpretationResponse, message: str) -> Any:
    return asyncio.run(
        interpret_stage_async(
            state=RunState.new(current_user_message=message, recent_thread_history=[]),
            user=USER,
            latest_task_snapshot=None,
            structured_interpreter=_StubInterpreter(interpretation),
        )
    )


def test_knowledge_turn_with_resolved_asset_is_not_interrogated() -> None:
    # The production shape: statistics question, model resolves SPY, answers.
    interpretation = StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        user_goal_summary="graded",
        semantic_turn_act="unsupported_request",
        requires_clarification=False,
        assistant_response="Puedo mostrarte estadísticas del S&P 500 mediante SPY.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="Ayúdame con estadísticas sobre el S&P 500",
            strategy_thesis="Ayúdame con estadísticas sobre el S&P 500",
            asset_universe=["SPY"],
            asset_class="equity",
            comparison_baseline="SPY",
        ),
    )
    result = _run_stage(interpretation, "Ayúdame con estadísticas sobre el S&P 500")

    assert result.decision.missing_required_fields == []
    assert "entry_logic" not in result.decision.missing_required_fields
    assert result.stage_patch.get("assistant_response") == (
        "Puedo mostrarte estadísticas del S&P 500 mediante SPY."
    )


def test_strategy_intent_with_one_ticker_still_routes_to_strategy() -> None:
    # Level 2 must survive: a real strategy ask gets a targeted question.
    interpretation = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="graded",
        semantic_turn_act="new_idea",
        requires_clarification=True,
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            asset_universe=["AAPL"],
        ),
    )
    result = _run_stage(interpretation, "Simula comprar y mantener AAPL")

    assert result.decision.missing_required_fields


def _extraction_allowed(response: LLMInterpretationResponse, message: str) -> bool:
    return strategy_extraction_repair_is_allowed(
        response,
        request=_bare_request(message),
        has_failed_action_launch_payload=lambda request: False,
        noncanonical_text_needs_repair=lambda *, response, request: False,
        has_active_strategy_context=lambda request: False,
        current_turn_has_material_execution_evidence=lambda request: False,
    )


def test_extraction_cannot_invent_a_strategy_from_an_echo() -> None:
    message = "Ayúdame con estadísticas sobre el S&P 500"
    echo = _response(
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_thesis=message,
            asset_universe=["SPY"],
        ),
    )
    assert _extraction_allowed(echo, message) is False

    # A model-asserted thesis distinct from the message is an idea to extract.
    asserted = _response(
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="what if I bought Tesla when it looked cheap?",
            strategy_thesis="Buy Tesla on dips and hold.",
        ),
    )
    assert _extraction_allowed(
        asserted, "what if I bought Tesla when it looked cheap?"
    )


def test_reference_only_unsupported_without_text_fails_required_shape() -> None:
    silent = _response(
        candidate_strategy_draft=LLMStrategyDraft(asset_universe=["SPY"]),
    )
    assert (
        _structured_interpretation_has_required_shape(
            silent, request=_bare_request("Ayúdame con estadísticas sobre el S&P 500")
        )
        is False
    )


def test_pending_date_answer_rescue_beats_the_no_progress_menu() -> None:
    # The live 2026-08-06 failure: both tiers rejected the period reply, and
    # the recovery menu asked the user to re-provide the detail they just gave.
    from datetime import date as _date

    from argus.agent_runtime.stages.interpret_internal.pending_date_answer import (
        pending_date_answer_interpretation,
    )

    snapshot = TaskSnapshot(
        latest_task_type="strategy_drafting",
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            asset_universe=["SPY"],
            asset_class="equity",
        ),
        pending_needs=["period"],
    )
    rescued = pending_date_answer_interpretation(
        current_user_message="del ultimo año para aca",
        language="es",
        snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        today=_date(2026, 8, 6),
        reason_code="pending_date_answer_interpreter_unavailable_repaired",
        user_goal_summary="probe",
    )

    assert rescued is not None
    assert rescued.candidate_strategy_draft.date_range == {
        "start": "2025-08-06",
        "end": "2026-08-06",
    }
    assert rescued.semantic_turn_act == "answer_pending_need"
