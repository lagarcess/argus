"""Issue #159 options semantic-admission repair.

Invariant under test: a structured interpretation that still carries
``intent=unsupported_or_out_of_scope`` must never become an executable
confirmation. Promotion to a supported intent is LLM-owned (capability-conflict
audit); every other outcome fails closed into typed unsupported recovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
    interpret_stage_async,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UnsupportedConstraint,
    UserState,
)

FULL_YEAR_2024 = {"start": "2024-01-01", "end": "2024-12-31"}
EN_OPTIONS_MESSAGE = (
    "can you run an options straddle on TSLA from 2024-01-01 through 2024-12-31?"
)
ES_OPTIONS_MESSAGE = (
    "por favor intenta probar opciones semanales de AAPL desde 2024-01-01 "
    "hasta 2024-12-31"
)


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class RecordingInterpreter:
    def __init__(self, response: StructuredInterpretation | None) -> None:
        self.response = response
        self.requests = []
        self.last_status = "unused"

    def __call__(self, request):
        self.requests.append(request)
        self.last_status = "used"
        return self.response


def _stub_equity_asset_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str, **_: Any) -> ResolvedAssetStub:
        return ResolvedAssetStub(symbol.upper(), "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)


def _run_interpret(
    *,
    message: str,
    response: StructuredInterpretation,
    user: UserState | None = None,
    snapshot: TaskSnapshot | None = None,
):
    interpreter = RecordingInterpreter(response)
    result = interpret_stage(
        state=RunState.new(current_user_message=message, recent_thread_history=[]),
        user=user or UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={},
        structured_interpreter=interpreter,
    )
    return result, interpreter


def _contradictory_interpretation(
    *,
    symbol: str,
    semantic_turn_act: str,
    requires_clarification: bool = False,
    assistant_response: str | None = None,
    detected_user_language: str | None = None,
) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=requires_clarification,
        user_goal_summary=f"User asked to backtest an options idea on {symbol}.",
        detected_user_language=detected_user_language,
        assistant_response=assistant_response,
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            asset_universe=[symbol],
            asset_class="equity",
            date_range=dict(FULL_YEAR_2024),
        ),
        semantic_turn_act=semantic_turn_act,
    )


def _assert_blocked_unsupported_admission(
    result,
    *,
    symbol: str,
    expected_intent: str = "unsupported_or_out_of_scope",
) -> None:
    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    decision = result.decision
    assert decision.intent == expected_intent
    assert decision.requires_clarification is True
    assert "unsupported_intent_confirmation_blocked" in decision.reason_codes
    constraints = decision.unsupported_constraints
    assert [item.category for item in constraints] == ["unsupported_strategy_logic"]
    constraint = constraints[0]
    assert constraint.raw_value
    assert constraint.raw_value != "buy_and_hold"
    replacement_strategy_types = {
        option.replacement_values.get("strategy_type")
        for option in constraint.simplification_options
    }
    assert "buy_and_hold" in replacement_strategy_types
    strategy = decision.candidate_strategy_draft
    assert strategy.asset_universe == [symbol]
    assert strategy.date_range == FULL_YEAR_2024
    patch = result.patch
    assert patch.get("confirmation_payload") is None
    assert (
        patch["optional_parameter_status"]["unsupported_constraints"][0]["category"]
        == "unsupported_strategy_logic"
    )


def test_unsupported_intent_new_idea_options_contradiction_blocks_en(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_equity_asset_resolution(monkeypatch)
    result, _ = _run_interpret(
        message=EN_OPTIONS_MESSAGE,
        response=_contradictory_interpretation(
            symbol="TSLA", semantic_turn_act="new_idea"
        ),
    )
    _assert_blocked_unsupported_admission(result, symbol="TSLA")


def test_unsupported_intent_options_contradiction_blocks_es(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_equity_asset_resolution(monkeypatch)
    result, _ = _run_interpret(
        message=ES_OPTIONS_MESSAGE,
        response=_contradictory_interpretation(
            symbol="AAPL",
            semantic_turn_act="new_idea",
            detected_user_language="es-419",
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
    )
    _assert_blocked_unsupported_admission(result, symbol="AAPL")


def test_unsupported_request_turn_act_contradiction_blocks_and_keeps_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_equity_asset_resolution(monkeypatch)
    refusal = "Options strategies are not executable yet."
    result, _ = _run_interpret(
        message=EN_OPTIONS_MESSAGE,
        response=_contradictory_interpretation(
            symbol="TSLA",
            semantic_turn_act="unsupported_request",
            requires_clarification=True,
            assistant_response=refusal,
        ),
    )
    _assert_blocked_unsupported_admission(result, symbol="TSLA")
    assert result.patch.get("assistant_response") == refusal


def test_supported_intent_with_unsupported_request_act_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The unsupported verdict can arrive on either typed field; both fail closed."""

    _stub_equity_asset_resolution(monkeypatch)
    mixed = _contradictory_interpretation(
        symbol="TSLA", semantic_turn_act="unsupported_request"
    ).model_copy(update={"intent": "backtest_execution"})
    result, _ = _run_interpret(message=EN_OPTIONS_MESSAGE, response=mixed)
    _assert_blocked_unsupported_admission(
        result, symbol="TSLA", expected_intent="backtest_execution"
    )
    assert result.decision.semantic_turn_act == "unsupported_request"


def test_supported_intent_same_draft_still_admits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_equity_asset_resolution(monkeypatch)
    response = _contradictory_interpretation(symbol="TSLA", semantic_turn_act="new_idea")
    supported = response.model_copy(
        update={"intent": "backtest_execution", "user_goal_summary": "Hold TSLA."}
    )
    result, _ = _run_interpret(
        message="hold TSLA for 2024 please",
        response=supported,
    )
    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    assert result.decision.unsupported_constraints == []


# --- normalization-layer (D2 inverse audit arm) coverage -----------------------------


def _inverse_llm_response(
    *,
    symbol: str = "TSLA",
    semantic_turn_act: str = "new_idea",
    date_range: dict[str, str] | None = None,
) -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary=f"User asked to backtest an options idea on {symbol}.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=[symbol],
            asset_class="equity",
            date_range=dict(date_range) if date_range is not None else None,
        ),
        semantic_turn_act=semantic_turn_act,
    )


def _request(
    message: str = EN_OPTIONS_MESSAGE,
    *,
    snapshot: TaskSnapshot | None = None,
    selected_thread_metadata: dict[str, Any] | None = None,
) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata or {},
        user=UserState(user_id="u1"),
    )


class _SchemaRecorder:
    def __init__(self, conflict_audit: Any) -> None:
        self.conflict_audit = conflict_audit
        self.schema_names: list[str] = []
        self.conflict_messages: list[list[dict[str, str]]] = []

    async def __call__(self, **kwargs):
        from argus.agent_runtime import llm_interpreter as interpreter_module

        schema_name = kwargs["schema_name"]
        self.schema_names.append(schema_name)
        if schema_name == "SupportedStrategyCapabilityConflictAudit":
            self.conflict_messages.append(kwargs["messages"])
            if isinstance(self.conflict_audit, Exception):
                raise self.conflict_audit
            return self.conflict_audit
        if schema_name == "DcaContractAudit":
            return interpreter_module.DcaContractAudit(
                is_recurring_buy_request=False,
                confidence=0.9,
            )
        raise AssertionError(f"unexpected audit call: {schema_name}")


@pytest.mark.asyncio
@pytest.mark.parametrize("semantic_turn_act", ["new_idea", "unsupported_request"])
async def test_inverse_contradiction_triggers_capability_conflict_audit(
    monkeypatch: pytest.MonkeyPatch,
    semantic_turn_act: str,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    recorder = _SchemaRecorder(
        interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type=None,
            drop_unsupported_strategy_logic=False,
            keep_unsupported_strategy_logic=True,
            confidence=0.9,
        )
    )
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)

    ready = await interpreter_module._response_ready_for_runtime(
        response=_inverse_llm_response(
            semantic_turn_act=semantic_turn_act, date_range=FULL_YEAR_2024
        ),
        preferred_model="test-model",
        request=_request(),
    )

    assert "SupportedStrategyCapabilityConflictAudit" in recorder.schema_names
    system_prompt = recorder.conflict_messages[0][0]["content"]
    assert "unsupported" in system_prompt
    assert ready.intent == "unsupported_or_out_of_scope"
    assert "supported_strategy_capability_conflict_audit" not in ready.reason_codes


@pytest.mark.asyncio
async def test_inverse_contradiction_confident_audit_promotion_is_single_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    recorder = _SchemaRecorder(
        interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type="buy_and_hold",
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.9,
        )
    )
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)

    ready = await interpreter_module._response_ready_for_runtime(
        response=_inverse_llm_response(date_range=FULL_YEAR_2024),
        preferred_model="test-model",
        request=_request("hold TSLA for all of 2024"),
    )

    assert ready.intent == "backtest_execution"
    assert ready.requires_clarification is False
    assert ready.unsupported_constraints == []
    assert "supported_strategy_capability_conflict_audit" in ready.reason_codes
    assert "supported_strategy_capability_conflict_inverse" in ready.reason_codes


@pytest.mark.asyncio
async def test_mixed_shape_promotion_normalizes_intent_and_turn_act(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    recorder = _SchemaRecorder(
        interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type="buy_and_hold",
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.9,
        )
    )
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)
    mixed = _inverse_llm_response(date_range=FULL_YEAR_2024).model_copy(
        update={
            "intent": "backtest_execution",
            "semantic_turn_act": "unsupported_request",
        }
    )

    ready = await interpreter_module._response_ready_for_runtime(
        response=mixed,
        preferred_model="test-model",
        request=_request("hold TSLA for all of 2024"),
    )

    assert ready.intent == "backtest_execution"
    assert ready.semantic_turn_act == "new_idea"
    assert "supported_strategy_capability_conflict_inverse" in ready.reason_codes


@pytest.mark.asyncio
async def test_inverse_promotion_without_dates_asks_for_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    recorder = _SchemaRecorder(
        interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type="buy_and_hold",
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.9,
        )
    )
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)

    ready = await interpreter_module._response_ready_for_runtime(
        response=_inverse_llm_response(date_range=None),
        preferred_model="test-model",
        request=_request("run TSLA options for me"),
    )

    assert ready.intent == "strategy_drafting"
    assert ready.requires_clarification is True
    assert "date_range" in ready.missing_required_fields


class _WrongSchema:
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_shape",
    [pytest.param("unsupported_intent"), pytest.param("mixed_unsupported_act")],
)
@pytest.mark.parametrize(
    "conflict_audit",
    [
        pytest.param(
            RuntimeError("capability_conflict audit unavailable"), id="exception"
        ),
        pytest.param(_WrongSchema(), id="invalid_payload"),
        pytest.param("keep", id="keep_unsupported"),
        pytest.param("low_confidence", id="low_confidence"),
    ],
)
async def test_inverse_contradiction_fails_closed_without_promotion(
    monkeypatch: pytest.MonkeyPatch,
    conflict_audit: Any,
    response_shape: str,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    if conflict_audit == "keep":
        conflict_audit = interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type=None,
            drop_unsupported_strategy_logic=False,
            keep_unsupported_strategy_logic=True,
            confidence=0.95,
        )
    elif conflict_audit == "low_confidence":
        conflict_audit = interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type="buy_and_hold",
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.4,
        )
    recorder = _SchemaRecorder(conflict_audit)
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)
    response = _inverse_llm_response(date_range=FULL_YEAR_2024)
    expected_intent = "unsupported_or_out_of_scope"
    if response_shape == "mixed_unsupported_act":
        response = response.model_copy(
            update={
                "intent": "backtest_execution",
                "semantic_turn_act": "unsupported_request",
            }
        )
        expected_intent = "backtest_execution"

    ready = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=_request(),
    )

    assert ready.intent == expected_intent
    if response_shape == "mixed_unsupported_act":
        assert ready.semantic_turn_act == "unsupported_request"
    assert "supported_strategy_capability_conflict_audit" not in ready.reason_codes
    assert "supported_strategy_capability_conflict_inverse" not in ready.reason_codes


@pytest.mark.asyncio
async def test_constraint_present_direction_keeps_structured_fallback_promotion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    recorder = _SchemaRecorder(RuntimeError("audit offline"))
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)
    response = _inverse_llm_response(date_range=FULL_YEAR_2024).model_copy(
        update={
            "requires_clarification": True,
            "unsupported_constraints": [
                interpreter_module.LLMUnsupportedConstraint(
                    category="unsupported_strategy_logic",
                    raw_value="hold TSLA through 2024",
                    explanation="Model over-refused a plain holding request.",
                )
            ],
        }
    )

    ready = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=_request("hold TSLA for all of 2024"),
    )

    assert ready.intent == "backtest_execution"
    assert ready.unsupported_constraints == []
    assert "supported_strategy_capability_structured_fallback" in ready.reason_codes


@pytest.mark.asyncio
async def test_pending_simplification_acceptance_progresses_without_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    class _AcceptanceRecorder(_SchemaRecorder):
        async def __call__(self, **kwargs):
            schema_name = kwargs["schema_name"]
            if schema_name == "PendingResponseOptionSelectionAudit":
                self.schema_names.append(schema_name)
                return interpreter_module.PendingResponseOptionSelectionAudit(
                    is_selection=True,
                    selected_option_index=0,
                    confidence=0.9,
                )
            return await super().__call__(**kwargs)

    recorder = _AcceptanceRecorder(RuntimeError("conflict audit must not run"))
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type=None,
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range=dict(FULL_YEAR_2024),
        ),
        pending_needs=["simplification_choice"],
    )
    metadata = {
        "last_stage_outcome": "await_user_reply",
        "requested_field": "unsupported_constraints",
        "response_intent": {
            "kind": "unsupported_recovery",
            "semantic_needs": ["simplification_choice"],
            "options": [
                {
                    "label": "Compare with buy and hold",
                    "replacement_values": {"strategy_type": "buy_and_hold"},
                }
            ],
        },
    }
    acceptance = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User accepted the buy and hold simplification.",
        candidate_strategy_draft=LLMStrategyDraft(
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range=dict(FULL_YEAR_2024),
        ),
        semantic_turn_act="answer_pending_need",
    )

    ready = await interpreter_module._response_ready_for_runtime(
        response=acceptance,
        preferred_model="test-model",
        request=_request(
            "ok, compare with buy and hold instead",
            snapshot=snapshot,
            selected_thread_metadata=metadata,
        ),
    )

    assert "PendingResponseOptionSelectionAudit" in recorder.schema_names
    assert "SupportedStrategyCapabilityConflictAudit" not in recorder.schema_names
    assert ready.intent == "backtest_execution"
    assert "pending_response_option_selected" in ready.reason_codes
    assert ready.unsupported_constraints == []


# --- prose-bearing contradiction: readiness + admission cross-layer coverage ---------

REFUSAL_PROSE_EN = "I can't run options strategies yet — I can test holding TSLA instead."

_EXPECTED_VERDICT_BY_SHAPE = {
    "unsupported_intent_only": ("unsupported_or_out_of_scope", "new_idea"),
    "unsupported_act_only": ("backtest_execution", "unsupported_request"),
    "both_unsupported": ("unsupported_or_out_of_scope", "unsupported_request"),
}


def _prose_bearing_inverse_response(shape: str) -> LLMInterpretationResponse:
    response = _inverse_llm_response(date_range=FULL_YEAR_2024).model_copy(
        update={
            "requires_clarification": True,
            "assistant_response": REFUSAL_PROSE_EN,
        }
    )
    if shape == "unsupported_intent_only":
        return response
    if shape == "unsupported_act_only":
        return response.model_copy(
            update={
                "intent": "backtest_execution",
                "semantic_turn_act": "unsupported_request",
            }
        )
    return response.model_copy(update={"semantic_turn_act": "unsupported_request"})


def _stage_interpretation_from_readied(
    readied: LLMInterpretationResponse,
) -> StructuredInterpretation:
    draft = readied.candidate_strategy_draft
    return StructuredInterpretation(
        intent=readied.intent,
        task_relation=readied.task_relation,
        requires_clarification=readied.requires_clarification,
        user_goal_summary=readied.user_goal_summary,
        assistant_response=readied.assistant_response,
        candidate_strategy_draft=StrategySummary(
            strategy_type=draft.strategy_type,
            asset_universe=list(draft.asset_universe or []),
            asset_class=draft.asset_class,
            date_range=dict(draft.date_range)
            if isinstance(draft.date_range, dict)
            else None,
        ),
        semantic_turn_act=readied.semantic_turn_act,
        missing_required_fields=list(readied.missing_required_fields),
        reason_codes=list(readied.reason_codes),
    )


async def _run_interpret_async(
    *,
    message: str,
    response: StructuredInterpretation,
    user: UserState | None = None,
):
    interpreter = RecordingInterpreter(response)
    result = await interpret_stage_async(
        state=RunState.new(current_user_message=message, recent_thread_history=[]),
        user=user or UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=interpreter,
    )
    return result, interpreter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_shape",
    [
        pytest.param("unsupported_intent_only"),
        pytest.param("unsupported_act_only"),
        pytest.param("both_unsupported"),
    ],
)
@pytest.mark.parametrize(
    "conflict_audit",
    [
        pytest.param(
            RuntimeError("capability_conflict audit unavailable"), id="exception"
        ),
        pytest.param(_WrongSchema(), id="invalid_payload"),
        pytest.param("keep", id="keep_unsupported"),
        pytest.param("low_confidence", id="low_confidence"),
    ],
)
async def test_prose_bearing_contradiction_keeps_verdict_through_readiness_and_admission(
    monkeypatch: pytest.MonkeyPatch,
    conflict_audit: Any,
    response_shape: str,
) -> None:
    """The clarification-prose normalizer must never erase a non-promoted verdict."""

    from argus.agent_runtime import llm_interpreter as interpreter_module

    if conflict_audit == "keep":
        conflict_audit = interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type=None,
            drop_unsupported_strategy_logic=False,
            keep_unsupported_strategy_logic=True,
            confidence=0.95,
        )
    elif conflict_audit == "low_confidence":
        conflict_audit = interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type="buy_and_hold",
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.4,
        )
    recorder = _SchemaRecorder(conflict_audit)
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)
    expected_intent, expected_turn_act = _EXPECTED_VERDICT_BY_SHAPE[response_shape]

    readied = await interpreter_module._response_ready_for_runtime(
        response=_prose_bearing_inverse_response(response_shape),
        preferred_model="test-model",
        request=_request(),
    )

    assert readied.intent == expected_intent
    assert readied.semantic_turn_act == expected_turn_act
    assert readied.requires_clarification is True
    assert readied.assistant_response == REFUSAL_PROSE_EN
    assert "executable_fields_overrode_clarification_prose" not in readied.reason_codes
    assert "supported_strategy_capability_conflict_audit" not in readied.reason_codes
    assert "supported_strategy_capability_conflict_inverse" not in readied.reason_codes

    _stub_equity_asset_resolution(monkeypatch)
    result, _ = await _run_interpret_async(
        message=EN_OPTIONS_MESSAGE,
        response=_stage_interpretation_from_readied(readied),
    )
    _assert_blocked_unsupported_admission(
        result, symbol="TSLA", expected_intent=expected_intent
    )
    assert result.decision.semantic_turn_act == expected_turn_act
    assert result.patch.get("assistant_response") == REFUSAL_PROSE_EN


@pytest.mark.asyncio
async def test_prose_bearing_contradiction_confident_promotion_still_admits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    recorder = _SchemaRecorder(
        interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type="buy_and_hold",
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.9,
        )
    )
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)

    readied = await interpreter_module._response_ready_for_runtime(
        response=_prose_bearing_inverse_response("unsupported_intent_only"),
        preferred_model="test-model",
        request=_request("hold TSLA for all of 2024"),
    )

    assert readied.intent == "backtest_execution"
    assert readied.semantic_turn_act == "new_idea"
    assert readied.requires_clarification is False
    assert readied.assistant_response is None
    assert "supported_strategy_capability_conflict_inverse" in readied.reason_codes

    _stub_equity_asset_resolution(monkeypatch)
    result, _ = await _run_interpret_async(
        message="hold TSLA for all of 2024",
        response=_stage_interpretation_from_readied(readied),
    )
    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    assert result.decision.unsupported_constraints == []


@pytest.mark.asyncio
async def test_incomplete_non_promoted_contradiction_blocks_before_missing_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing run fields must not launder an unsupported typed verdict."""

    from argus.agent_runtime import llm_interpreter as interpreter_module

    recorder = _SchemaRecorder(
        interpreter_module.SupportedStrategyCapabilityConflictAudit(
            selected_strategy_type=None,
            drop_unsupported_strategy_logic=False,
            keep_unsupported_strategy_logic=True,
            confidence=0.95,
        )
    )
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", recorder)
    response = _prose_bearing_inverse_response("both_unsupported").model_copy(
        update={
            "candidate_strategy_draft": _inverse_llm_response(
                date_range=None
            ).candidate_strategy_draft,
            "missing_required_fields": ["date_range"],
        }
    )

    readied = await interpreter_module._response_ready_for_runtime(
        response=response,
        preferred_model="test-model",
        request=_request("run an options straddle on TSLA"),
    )

    assert readied.intent == "unsupported_or_out_of_scope"
    assert readied.semantic_turn_act == "unsupported_request"
    assert readied.requires_clarification is True
    assert "date_range" in readied.missing_required_fields

    _stub_equity_asset_resolution(monkeypatch)
    result, _ = await _run_interpret_async(
        message="run an options straddle on TSLA",
        response=_stage_interpretation_from_readied(readied),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    assert "unsupported_intent_confirmation_blocked" in result.decision.reason_codes
    assert [
        constraint.category for constraint in result.decision.unsupported_constraints
    ] == ["unsupported_strategy_logic"]
    assert result.patch.get("confirmation_payload") is None


def test_admission_invariant_blocks_even_with_model_constraint_free_edge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model-emitted non-strategy constraint must not weaken the invariant."""

    _stub_equity_asset_resolution(monkeypatch)
    response = _contradictory_interpretation(symbol="TSLA", semantic_turn_act="new_idea")
    with_other_constraint = response.model_copy(
        update={
            "unsupported_constraints": [
                UnsupportedConstraint(
                    category="unsupported_timeframe",
                    raw_value="1m bars",
                    explanation="Sub-hour timeframes are not supported.",
                )
            ]
        }
    )
    result, _ = _run_interpret(
        message=EN_OPTIONS_MESSAGE,
        response=with_other_constraint,
    )
    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    assert result.decision.intent == "unsupported_or_out_of_scope"
