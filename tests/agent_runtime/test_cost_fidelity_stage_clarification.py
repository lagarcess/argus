"""A stated cost the fidelity audit cannot ground is asked about, never run at 0 bps (#271)."""

from __future__ import annotations

import pytest
from argus.agent_runtime.interpreter.audits import StatedRunFieldFidelityAudit
from argus.agent_runtime.interpreter.execution_cost_fidelity import apply_cost_fidelity
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
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


_NO_COST_MONTHLY_BUYS = [
    pytest.param(
        "en",
        "I'll start by putting in $200 a month into SPY, from January 2024 "
        "through December 2024.",
        id="english",
    ),
    pytest.param(
        "es-419",
        "Voy a empezar poniendo $200 al mes en SPY, de enero de 2024 a "
        "diciembre de 2024.",
        id="spanish",
    ),
]

_STATED_SLIPPAGE_MONTHLY_BUYS = [
    pytest.param(
        "en",
        "Put $200 a month into SPY through 2024, with 10 bps slippage per trade.",
        id="english",
    ),
    pytest.param(
        "es-419",
        "Pon $200 al mes en SPY durante 2024, con deslizamiento de 10 bps por operación.",
        id="spanish",
    ),
]


def _monthly_buy_read(message: str, costs: dict[str, float]) -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=message,
        semantic_turn_act="new_idea",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=message,
            strategy_type="dca_accumulation",
            asset_universe=["SPY"],
            asset_class="equity",
            capital_amount=200,
            cadence="monthly",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            extra_parameters=dict(costs),
        ),
    )


@pytest.mark.parametrize(("language", "message"), _NO_COST_MONTHLY_BUYS)
@pytest.mark.parametrize(
    "costs",
    [{"fee_rate": 0.0, "slippage": 0.0}, {"slippage": 0.0}],
    ids=["both-zero", "slippage-zero"],
)
def test_a_zero_cost_only_the_read_carries_is_dropped_without_a_question(
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    message: str,
    costs: dict[str, float],
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    response = _monthly_buy_read(message, costs)

    apply_cost_fidelity(response, StatedRunFieldFidelityAudit(), message, None)

    assert response.requires_clarification is False
    assert "assumption" not in response.missing_required_fields
    assert "execution_cost_evidence_unresolved" not in response.reason_codes
    assert "execution_cost_default_zero_dropped" in response.reason_codes
    extra = response.candidate_strategy_draft.extra_parameters
    assert "fee_rate" not in extra
    assert "slippage" not in extra


@pytest.mark.parametrize(("language", "message"), _NO_COST_MONTHLY_BUYS)
def test_a_nonzero_cost_the_message_does_not_ground_is_still_asked(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    response = _monthly_buy_read(message, {"slippage": 0.0005})

    apply_cost_fidelity(response, StatedRunFieldFidelityAudit(), message, None)

    assert response.requires_clarification is True
    assert "assumption" in response.missing_required_fields
    assert "execution_cost_default_zero_dropped" not in response.reason_codes


@pytest.mark.parametrize(("language", "message"), _STATED_SLIPPAGE_MONTHLY_BUYS)
def test_a_stated_cost_the_audit_does_not_read_is_still_asked(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    response = _monthly_buy_read(message, {"slippage": 0.001})

    apply_cost_fidelity(response, StatedRunFieldFidelityAudit(), message, None)

    assert response.requires_clarification is True
    assert "assumption" in response.missing_required_fields
    assert "execution_cost_evidence_unresolved" in response.reason_codes


@pytest.mark.parametrize(("language", "message"), _NO_COST_MONTHLY_BUYS)
@pytest.mark.asyncio
async def test_a_request_without_costs_passes_the_field_audit_without_a_question(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str
) -> None:
    # Defaults the read carried never stop a request that states no cost.
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def empty_audit(*, schema_name, schema_model, **_):
        if schema_name == "StatedRunFieldFidelityAudit":
            return schema_model()
        raise RuntimeError(schema_name)

    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", empty_audit)
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol, **_: ResolvedAssetStub(symbol.strip().upper(), "equity"),
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=_monthly_buy_read(message, {"fee_rate": 0.0, "slippage": 0.0}),
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u-271", language_preference=language),
        ),
    )

    assert repaired is not None
    assert repaired.requires_clarification is False
    assert "assumption" not in repaired.missing_required_fields
    assert "execution_cost_default_zero_dropped" in repaired.reason_codes


_SLIPPAGE_AND_FEE_MONTHLY_BUYS = [
    pytest.param(
        "en",
        "Put $200 a month into SPY through 2024, with 10 bps slippage and a 5 bps fee.",
        "10 bps slippage",
        id="english",
    ),
    pytest.param(
        "es-419",
        "Pon $200 al mes en SPY durante 2024, con deslizamiento de 10 bps y una "
        "comisión de 5 bps.",
        "deslizamiento de 10 bps",
        id="spanish",
    ),
]


@pytest.mark.parametrize(
    ("language", "message", "slippage_span"), _SLIPPAGE_AND_FEE_MONTHLY_BUYS
)
def test_a_zero_beside_a_cost_the_audit_read_is_still_asked(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str, slippage_span: str
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    response = _monthly_buy_read(message, {"slippage": 0.001, "fee_rate": 0.0})
    audit = StatedRunFieldFidelityAudit.model_validate(
        {"slippage": {"rate": 0.001, "evidence_span": slippage_span}, "confidence": 0.9}
    )

    apply_cost_fidelity(response, audit, message, None)

    assert response.requires_clarification is True
    assert "assumption" in response.missing_required_fields
    assert "execution_cost_default_zero_dropped" not in response.reason_codes
    assert response.candidate_strategy_draft.extra_parameters["slippage"] == 0.001


@pytest.mark.parametrize(
    ("language", "message", "slippage_span"), _SLIPPAGE_AND_FEE_MONTHLY_BUYS
)
def test_a_zero_the_read_quotes_from_the_message_is_still_asked(
    monkeypatch: pytest.MonkeyPatch, language: str, message: str, slippage_span: str
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    response = _monthly_buy_read(message, {"slippage": 0.0})
    response.candidate_strategy_draft.evidence_spans["slippage"] = slippage_span

    apply_cost_fidelity(response, StatedRunFieldFidelityAudit(), message, None)

    assert response.requires_clarification is True
    assert "assumption" in response.missing_required_fields
    assert "execution_cost_default_zero_dropped" not in response.reason_codes
