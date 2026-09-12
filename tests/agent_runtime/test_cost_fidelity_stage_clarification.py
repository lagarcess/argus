"""A stated cost the fidelity audit cannot ground is asked about, never run at 0 bps (#271)."""

from __future__ import annotations

import pytest
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft
from argus.agent_runtime.stages import interpret as interpret_module
from argus.agent_runtime.stages.interpret import interpret_stage
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, UserState

from tests.agent_runtime._llm_interpreter_common import ResolvedAssetStub

_STAGE_COST_CASES = [
    pytest.param(
        "en",
        "Test MSFT with $12,000 for calendar year 2022 using daily data, "
        "SPY as benchmark, a 10 bps fee and 5 bps slippage.",
        "10 bps fee",
        id="english",
    ),
    pytest.param(
        "es-419",
        "Prueba MSFT con $12,000 durante el año calendario 2022 con datos diarios, "
        "SPY como referencia, una comisión de 10 bps y un deslizamiento de 5 bps.",
        "comisión de 10 bps",
        id="spanish",
    ),
]


def _fee_only_interpretation(
    message: str, fee_span: str, *, unresolved: bool
) -> StructuredInterpretation:
    # What apply_cost_fidelity leaves when the audit grounds the fee but not the
    # stated slippage: the slippage is removed and a question is owed.
    draft = LLMStrategyDraft(
        raw_user_phrasing="Test MSFT with modeled execution costs.",
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold MSFT.",
        asset_universe=["MSFT"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2022-01-01", "end": "2022-12-31"},
        capital_amount=12000,
        comparison_baseline="SPY",
        field_provenance={
            "capital_amount": "starting_capital",
            "comparison_baseline": "explicit_user",
            "timeframe": "explicit_user",
        },
        extra_parameters={"fee_rate": 0.001},
    )
    draft.evidence_spans["fee_rate"] = fee_span
    draft.field_provenance["fee_rate"] = "explicit_user"
    draft._validated_execution_cost_evidence["fee_rate"] = (0.001, fee_span)
    return StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=unresolved,
        user_goal_summary="Test MSFT with modeled execution costs.",
        candidate_strategy_draft=_strategy_from_llm(draft, current_user_message=message),
        missing_required_fields=["assumption"] if unresolved else [],
        reason_codes=[
            "stated_run_field_fidelity_audit",
            *(["execution_cost_evidence_unresolved"] if unresolved else []),
        ],
        semantic_turn_act="new_idea",
        confidence=0.9,
    )


class _ScriptedInterpretation:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response

    def __call__(self, request: InterpretationRequest) -> StructuredInterpretation:
        return self.response

    async def ainvoke(self, request: InterpretationRequest) -> StructuredInterpretation:
        return self.response


def _interpret_scripted(
    monkeypatch: pytest.MonkeyPatch,
    *,
    message: str,
    language: str,
    response: StructuredInterpretation,
) -> StageResult:
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol, **_: ResolvedAssetStub(symbol.strip().upper(), "equity"),
    )
    return interpret_stage(
        state=RunState.new(current_user_message=message, recent_thread_history=[]),
        user=UserState(user_id="u-271", language_preference=language),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=_ScriptedInterpretation(response),
    )


@pytest.mark.parametrize(("language", "message", "fee_span"), _STAGE_COST_CASES)
def test_a_stated_cost_the_audit_cannot_ground_is_asked_not_launched_at_zero(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str, fee_span: str
) -> None:
    result = _interpret_scripted(
        monkeypatch,
        message=message,
        language=language,
        response=_fee_only_interpretation(message, fee_span, unresolved=True),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.requires_clarification is True
    assert "assumption" in result.decision.missing_required_fields


@pytest.mark.parametrize(("language", "message", "fee_span"), _STAGE_COST_CASES)
def test_grounded_costs_still_reach_confirmation(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str, fee_span: str
) -> None:
    result = _interpret_scripted(
        monkeypatch,
        message=message,
        language=language,
        response=_fee_only_interpretation(message, fee_span, unresolved=False),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.requires_clarification is False


@pytest.mark.parametrize(("language", "message", "fee_span"), _STAGE_COST_CASES)
@pytest.mark.asyncio
async def test_an_owed_cost_question_is_asked_through_the_whole_turn(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str, fee_span: str
) -> None:
    # The interpret stage owes the question; the clarify stage must ask it rather
    # than fall through to a confirmation card at the default rate.
    from argus.agent_runtime.graph.workflow import build_workflow
    from argus.agent_runtime.runtime import run_agent_turn
    from langgraph.checkpoint.memory import MemorySaver

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol, **_: ResolvedAssetStub(symbol.strip().upper(), "equity"),
    )
    workflow = build_workflow(
        structured_interpreter=_ScriptedInterpretation(
            _fee_only_interpretation(message, fee_span, unresolved=True)
        ),
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u-271", language_preference=language),
        thread_id=f"thread-owed-cost-{language}",
        message=message,
    )

    assert result["stage_outcome"] == "await_user_reply"
    assert result["response_intent"]["requested_fields"] == ["assumption"]
    assert not result.get("confirmation_payload")


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_the_clarify_stage_asks_for_a_missing_assumption_on_a_new_request(
    language: str,
) -> None:
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages.clarify import clarify_stage
    from argus.agent_runtime.state.models import StrategySummary

    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["MSFT"],
        asset_class="equity",
        date_range={"start": "2022-01-01", "end": "2022-12-31"},
    )
    state.missing_required_fields = ["assumption"]

    result = clarify_stage(
        state=state, contract=build_default_capability_contract(), language=language
    )

    assert result.outcome == "await_user_reply"
    assert result.patch["requested_field"] == "assumption"
