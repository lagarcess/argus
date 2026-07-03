from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from argus.agent_runtime.artifact_action_recovery import artifact_action_recovery_message
from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    EditOperation,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.confirmation_artifacts import confirmation_artifact_reference
from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
    missing_required_fields_for_strategy,
)
from argus.agent_runtime.state.models import (
    AmbiguousField,
    ArtifactReference,
    ResolutionProvenance,
    ResponseIntent,
    ResponseProfileOverrides,
    RunState,
    StrategySummary,
    StructuredActionContext,
    TaskSnapshot,
    UnsupportedConstraint,
    UserState,
)
from argus.context.providers import build_alpaca_market_movers_packet
from argus.domain.indicators import EXECUTABLE_INDICATORS
from argus.nlp.natural_time import parse_date_text, shift_months


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


class RaisingInterpreter:
    last_status = "unused"

    def __call__(self, request):
        del request
        raise RuntimeError("unexpected interpreter failure")


def run_interpret_with_llm(
    *,
    message: str,
    response: StructuredInterpretation,
    user: UserState | None = None,
    snapshot: TaskSnapshot | None = None,
    history: list[dict[str, str]] | None = None,
    selected_thread_metadata: dict[str, Any] | None = None,
    confirmation_payload: dict[str, Any] | None = None,
):
    interpreter = RecordingInterpreter(response)
    state = RunState.new(
        current_user_message=message,
        recent_thread_history=history or [],
    )
    if confirmation_payload is not None:
        state.confirmation_payload = confirmation_payload
    result = interpret_stage(
        state=state,
        user=user or UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata or {},
        structured_interpreter=interpreter,
    )
    return result, interpreter


def test_interpret_stage_does_not_hide_unexpected_interpreter_exceptions() -> None:
    with pytest.raises(RuntimeError, match="unexpected interpreter failure"):
        interpret_stage(
            state=RunState.new(
                current_user_message="test apple against qqq in 2024",
                recent_thread_history=[],
            ),
            user=UserState(user_id="u1"),
            latest_task_snapshot=None,
            structured_interpreter=RaisingInterpreter(),
        )


def test_interpreter_unavailable_recovery_uses_user_language_and_retry_metadata() -> None:
    message = "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 con 100000"

    result = interpret_stage(
        state=RunState.new(current_user_message=message, recent_thread_history=[]),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        structured_interpreter=None,
    )

    assert result.outcome == "ready_to_respond"
    response = result.stage_patch["assistant_response"]
    assert "Guardé tu mensaje" in response
    assert "I saved your message" not in response
    assert result.stage_patch["retry_last_turn"] == {"message": message}
    assert result.stage_patch["recovery"] == {
        "code": "interpreter_unavailable",
        "retryable": True,
        "language": "es-419",
    }


def test_interpreter_unavailable_spanish_atr_routes_to_unsupported_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_test_asset(symbol: str) -> ResolvedAssetStub:
        resolved = str(symbol).upper()
        if resolved not in {"TSLA", "SPY"}:
            raise LookupError(symbol)
        name = "Tesla Inc." if resolved == "TSLA" else "SPDR S&P 500 ETF Trust"
        return ResolvedAssetStub(resolved, "equity", name=name)

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        resolve_test_asset,
    )
    message = "Prueba TSLA con una regla ATR 14"

    result = interpret_stage(
        state=RunState.new(current_user_message=message, recent_thread_history=[]),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.asset_class == "equity"
    assert strategy.raw_user_phrasing == message
    assert result.decision.missing_required_fields == []
    assert result.decision.unsupported_constraints
    constraint = result.decision.unsupported_constraints[0]
    assert constraint.category == "unsupported_strategy_logic"
    assert "ATR 14" in constraint.raw_value
    assert result.stage_patch.get("recovery") is None
    assert "llm_interpreter_unavailable_draft_only_indicator_recovered" in (
        result.decision.reason_codes
    )

    clarify_state = RunState.new(
        current_user_message=message,
        recent_thread_history=[],
    )
    clarify_state.candidate_strategy_draft = strategy
    clarify_state.missing_required_fields = result.decision.missing_required_fields
    clarify_state.optional_parameter_status = result.decision.to_patch()[
        "optional_parameter_status"
    ]
    clarification = clarify_stage(
        state=clarify_state,
        contract=build_default_capability_contract(),
        language="es-419",
    )

    assert clarification.outcome == "await_user_reply"
    assert clarification.patch["response_intent"]["kind"] == "unsupported_recovery"
    assert "ATR 14" in clarification.patch["assistant_prompt"]
    assert "TSLA" in clarification.patch["assistant_prompt"]


def validated_confirmation_payload(strategy: StrategySummary) -> dict[str, Any]:
    symbol = strategy.asset_universe[0] if strategy.asset_universe else "SPY"
    return {
        "strategy": strategy.model_dump(mode="python"),
        "optional_parameters": {},
        "launch_payload": {
            "strategy_type": strategy.strategy_type or "buy_and_hold",
            "symbol": symbol,
            "symbols": list(strategy.asset_universe),
            "timeframe": "1D",
            "date_range": (
                strategy.date_range
                if isinstance(strategy.date_range, dict)
                else {"start": "2025-05-14", "end": "2026-05-14"}
            ),
            "entry_rule": None,
            "exit_rule": None,
            "sizing_mode": "capital_amount",
            "capital_amount": 1000,
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
            "language": "en",
        },
        "validation": {"status": "ready_to_run", "executable": True},
    }


def task_snapshot_with_confirmation(strategy: StrategySummary) -> TaskSnapshot:
    payload = validated_confirmation_payload(strategy)
    reference = confirmation_artifact_reference(
        confirmation_id="confirmation-test",
        confirmation_payload=payload,
    )
    return TaskSnapshot(
        pending_strategy_summary=strategy,
        active_confirmation_reference=reference,
        artifact_references=[reference],
    )


def test_interpret_passes_raw_message_to_llm_without_regex_normalization() -> None:
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User is checking the product.",
        assistant_response="I can help turn an investing idea into a supported backtest.",
        semantic_turn_act="educational_question",
    )

    result, interpreter = run_interpret_with_llm(
        message="  Actually make that weekly instead.  ",
        response=response,
    )

    assert len(interpreter.requests) == 1
    assert (
        interpreter.requests[0].current_user_message
        == "  Actually make that weekly instead.  "
    )
    assert result.outcome == "ready_to_respond"


def test_lump_sum_investment_shape_defaults_to_buy_and_hold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    message = (
        "let's see what an investment of 500 in NU could've made this year so "
        "far if invested at the begining of this year"
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to test a lump-sum investment in NU.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=message,
            strategy_thesis="Test a simple lump-sum investment in NU.",
            asset_universe=["NU"],
            asset_class="equity",
            date_range={"start": "2026-01-01", "end": "2026-06-03"},
            capital_amount=500,
        ),
        missing_required_fields=[],
        semantic_turn_act="new_idea",
    )

    result, _interpreter = run_interpret_with_llm(
        message=message,
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["NU"]
    assert strategy.capital_amount == 500
    assert result.decision.unsupported_constraints == []
    assert "complete_no_rule_shape_defaulted_to_buy_and_hold" in (
        result.decision.reason_codes
    )


def test_dca_starter_turn_suppresses_grounded_amount_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    message = (
        "Can you set a strategy where I buy AAPL GOOG at $200 every month for "
        "Jan 2021-Jan 2024?"
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants monthly recurring buys in AAPL and GOOG.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=message,
            strategy_type="dca_accumulation",
            strategy_thesis="Buy AAPL and GOOG every month.",
            asset_universe=["AAPL", "GOOG"],
            asset_class="equity",
            date_range={"start": "2021-01-01", "end": "2024-01-31"},
            cadence="monthly",
            capital_amount=200,
            sizing_mode="capital_amount",
            extra_parameters={
                "recurring_contribution": 200,
                "recurring_cadence": "monthly",
                "field_provenance": {
                    "capital_amount": "recurring_contribution",
                    "recurring_contribution": "recurring_contribution",
                    "cadence": "explicit_user",
                },
            },
        ),
        ambiguous_fields=[
            AmbiguousField(
                field_name="capital_amount",
                raw_value="$200",
                candidate_normalized_value=200,
                reason_code="missing_recurring_contribution_amount",
            )
        ],
        assistant_response=(
            "Is the $200 the total you want to invest each month across both "
            "stocks, or is that the amount per stock per month?"
        ),
        semantic_turn_act="new_idea",
    )

    result, _interpreter = run_interpret_with_llm(
        message=message,
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    assert result.decision.ambiguous_fields == []
    assert result.decision.candidate_strategy_draft.capital_amount == 200
    assert result.decision.candidate_strategy_draft.asset_universe == ["AAPL", "GOOG"]
    assert "resolved_strategy_ambiguity_suppressed" in result.decision.reason_codes


def test_result_followup_response_does_not_leave_underfilled_strategy_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        del kwargs
        return "TSLA underperformed SPY because the rule went to cash."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": -8.4,
                            "benchmark_return_pct": 76.8,
                            "max_drawdown_pct": -56.0,
                        }
                    }
                },
                "config_snapshot": {"template": "signal_strategy"},
            },
        )
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks why the latest result happened.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="why did that happen?",
            asset_universe=["TSLA"],
            date_range={"start": "2023-05-21", "end": "2026-05-21"},
        ),
        missing_required_fields=["entry_logic"],
        assistant_response=(
            "The rule went to cash during rallies, so it missed much of TSLA's upside."
        ),
        semantic_turn_act="result_followup",
    )

    result, _interpreter = run_interpret_with_llm(
        message="why did that happen?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    assert "TSLA" in answer
    assert "SPY" in answer
    assert result.decision is not None
    assert result.decision.semantic_turn_act == "result_followup"
    assert result.decision.candidate_strategy_draft == StrategySummary()
    assert result.decision.missing_required_fields == []


def test_result_artifact_date_patch_overrides_stale_unsupported_logic() -> None:
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "asset_class": "equity",
                "symbols": ["AAPL", "GOOG"],
                "benchmark_symbol": "SPY",
                "config_snapshot": {
                    "template": "dca_accumulation",
                    "symbols": ["AAPL", "GOOG"],
                    "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
                    "benchmark_symbol": "SPY",
                    "resolved_strategy": {
                        "strategy_type": "dca_accumulation",
                        "asset_universe": ["AAPL", "GOOG"],
                        "entry_rule": {
                            "type": "periodic_accumulation",
                            "cadence": "monthly",
                        },
                        "exit_rule": {"type": "end_of_period"},
                    },
                    "resolved_parameters": {
                        "timeframe": "1D",
                        "date_range": {
                            "start": "2021-01-01",
                            "end": "2024-01-31",
                        },
                        "capital_amount": 200,
                        "recurring_contribution": 200,
                        "cadence": "monthly",
                        "benchmark_symbol": "SPY",
                    },
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User wants to change the latest result date range.",
        candidate_strategy_draft=StrategySummary(
            date_range={"start": "2019-10-01", "end": "2025-10-31"},
        ),
        unsupported_constraints=[
            UnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="do the date range October 2019 to October 2025",
                explanation=(
                    "That idea needs a rule or data source the current backtest "
                    "engine cannot execute directly yet."
                ),
            )
        ],
        semantic_turn_act="result_followup",
        artifact_target="latest_result",
    )

    result, _interpreter = run_interpret_with_llm(
        message="do the date range October 2019 to October 2025",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "end_run"},
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.asset_universe == ["AAPL", "GOOG"]
    assert strategy.date_range == {"start": "2019-10-01", "end": "2025-10-31"}
    assert strategy.capital_amount == 200
    assert strategy.cadence == "monthly"
    assert result.decision.unsupported_constraints == []
    assert result.decision.missing_required_fields == []


def test_spanish_atr_underfilled_draft_routes_to_unsupported_recovery() -> None:
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="El usuario quiere probar TSLA con ATR 14.",
        assistant_response=(
            "Entiendo que quieres probar TSLA con un ATR 14. ¿En qué período "
            "de fechas quieres probar TSLA con ATR 14, y cómo debería usarse "
            "el ATR 14: como señal de entrada o de salida?"
        ),
        candidate_strategy_draft=StrategySummary(
            asset_universe=["TSLA"],
            asset_class="equity",
        ),
        missing_required_fields=["strategy_type", "entry_logic", "exit_logic"],
        semantic_turn_act="new_idea",
    )

    result, _interpreter = run_interpret_with_llm(
        message="Prueba TSLA con una regla ATR 14",
        response=response,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    assert result.decision.unsupported_constraints
    constraint = result.decision.unsupported_constraints[0]
    assert constraint.category == "unsupported_strategy_logic"
    assert "ATR 14" in constraint.raw_value
    assert result.decision.missing_required_fields == []
    assert "assistant_response" not in result.patch

    clarify_state = RunState.new(
        current_user_message="Prueba TSLA con una regla ATR 14",
        recent_thread_history=[],
    )
    clarify_state.candidate_strategy_draft = result.decision.candidate_strategy_draft
    clarify_state.missing_required_fields = result.decision.missing_required_fields
    clarify_state.optional_parameter_status = result.decision.to_patch()[
        "optional_parameter_status"
    ]
    clarification = clarify_stage(
        state=clarify_state,
        contract=build_default_capability_contract(),
        language="es-419",
    )

    assert clarification.outcome == "await_user_reply"
    assert clarification.patch["response_intent"]["kind"] == "unsupported_recovery"
    assert clarification.patch["response_intent"]["semantic_needs"] == [
        "simplification_choice"
    ]
    assert "ATR 14" in clarification.patch["assistant_prompt"]
    assert "Use a supported" not in clarification.patch["assistant_prompt"]
    assert "Comparar con comprar y mantener" in clarification.patch["assistant_prompt"]


def test_spanish_atr_llm_indicator_metadata_routes_to_unsupported_recovery() -> None:
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="El usuario quiere probar TSLA con ATR 14.",
        assistant_response=(
            "Entendido, ATR 14 es un indicador de volatilidad, no una regla "
            "de entrada o salida por sí mismo. Para ejecutar una prueba, "
            "necesito dos cosas: ¿en qué período de fechas quieres probarlo? "
            "Y ¿cómo debería usar el ATR 14 para decidir comprar o vender?"
        ),
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="Prueba TSLA con una regla ATR 14",
            strategy_thesis="Prueba TSLA con una regla ATR 14",
            asset_universe=["TSLA"],
            asset_class="equity",
            comparison_baseline="SPY",
            extra_parameters={
                "indicator": "atr",
                "indicator_parameters": {
                    "indicator": "atr",
                    "indicator_period": 14,
                },
            },
        ),
        missing_required_fields=["entry_logic", "exit_logic", "date_range"],
        semantic_turn_act="new_idea",
    )

    result, _interpreter = run_interpret_with_llm(
        message="Prueba TSLA con una regla ATR 14",
        response=response,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    assert result.decision.unsupported_constraints
    constraint = result.decision.unsupported_constraints[0]
    assert constraint.category == "unsupported_strategy_logic"
    assert "ATR 14" in constraint.raw_value
    assert result.decision.missing_required_fields == []
    assert "assistant_response" not in result.patch
    assert "draft_only_indicator_text_preserved" in result.decision.reason_codes

    clarify_state = RunState.new(
        current_user_message="Prueba TSLA con una regla ATR 14",
        recent_thread_history=[],
    )
    clarify_state.candidate_strategy_draft = result.decision.candidate_strategy_draft
    clarify_state.missing_required_fields = result.decision.missing_required_fields
    clarify_state.optional_parameter_status = result.decision.to_patch()[
        "optional_parameter_status"
    ]
    clarification = clarify_stage(
        state=clarify_state,
        contract=build_default_capability_contract(),
        language="es-419",
    )

    assert clarification.outcome == "await_user_reply"
    assert clarification.patch["response_intent"]["kind"] == "unsupported_recovery"
    assert "Use a supported" not in clarification.patch["assistant_prompt"]
    assert "Comparar con comprar y mantener" in clarification.patch["assistant_prompt"]


def test_supported_strategy_label_with_explicit_unsupported_indicator_needs_recovery() -> None:
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="El usuario quiere probar TSLA con ATR 14 durante 2024.",
        assistant_response=(
            "Listo para probar comprar y mantener TSLA del 1 de enero de 2024 "
            "al 31 de diciembre de 2024."
        ),
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="Prueba TSLA con ATR 14 durante 2024 con $1,000",
            strategy_type="buy_and_hold",
            strategy_thesis="Prueba TSLA con ATR 14 durante 2024 con $1,000",
            asset_universe=["TSLA"],
            asset_class="equity",
            comparison_baseline="SPY",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            capital_amount=1000,
            extra_parameters={
                "language": "es-419",
                "evidence_spans": {
                    "indicator": "ATR 14",
                    "date_range": "durante 2024",
                    "asset_universe": "TSLA",
                    "capital_amount": "$1,000",
                },
                "field_provenance": {
                    "indicator": "explicit_user",
                    "date_range": "explicit_user",
                    "asset_universe": "explicit_user",
                    "capital_amount": "explicit_user",
                    "indicator_period": "explicit_user",
                },
                "raw_strategy_type": "signal_strategy",
                "date_range_raw_text": "durante 2024",
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _interpreter = run_interpret_with_llm(
        message="Prueba TSLA con ATR 14 durante 2024 con $1,000",
        response=response,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    assert result.decision.unsupported_constraints
    constraint = result.decision.unsupported_constraints[0]
    assert constraint.category == "unsupported_strategy_logic"
    assert "ATR 14" in constraint.raw_value
    assert result.decision.missing_required_fields == []
    assert "assistant_response" not in result.patch
    assert "explicit_unsupported_indicator_overrode_strategy_label" in (
        result.decision.reason_codes
    )


def test_executable_artifact_patch_does_not_require_strategy_thesis() -> None:
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User changed an executable artifact date range.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis=None,
            asset_universe=["AAPL", "GOOG"],
            asset_class="equity",
            timeframe="1D",
            cadence="monthly",
            date_range={"start": "2019-10-01", "end": "2025-10-31"},
            capital_amount=200,
            comparison_baseline="SPY",
            entry_rule={"type": "periodic_accumulation", "cadence": "monthly"},
            exit_rule={"type": "end_of_period"},
            extra_parameters={
                "artifact_patch": {
                    "source": "llm_patch",
                    "changed_fields": ["date_range"],
                }
            },
        ),
        missing_required_fields=["strategy_thesis"],
        semantic_turn_act="refine_current_idea",
    )

    result, _interpreter = run_interpret_with_llm(
        message="do the date range October 2019 to October 2025",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    assert result.decision.missing_required_fields == []
    assert result.decision.candidate_strategy_draft.strategy_thesis is None


def test_result_artifact_date_patch_survives_llm_losing_artifact_fields() -> None:
    snapshot = _latest_dca_result_snapshot()
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User wants to change the latest result date range.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="signal_strategy",
            extra_parameters={
                "date_range_intent": {
                    "kind": "explicit_range",
                    "start": "2019-10-01",
                    "end": "2025-10-31",
                    "confidence": 0.92,
                    "evidence": "October 2019 to October 2025",
                }
            },
        ),
        missing_required_fields=["entry_logic", "asset_universe", "exit_logic"],
        semantic_turn_act="refine_current_idea",
    )

    result, _interpreter = run_interpret_with_llm(
        message="do the date range October 2019 to October 2025",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "end_run"},
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.asset_universe == ["AAPL", "GOOG"]
    assert strategy.date_range == {"start": "2019-10-01", "end": "2025-10-31"}
    assert strategy.capital_amount == 200
    assert strategy.cadence == "monthly"
    assert result.decision.missing_required_fields == []


def test_result_artifact_date_patch_overrides_llm_asset_clarification() -> None:
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User wants to adjust the latest result date range.",
        assistant_response=(
            "Which assets would you like to buy each month for this window?"
        ),
        candidate_strategy_draft=StrategySummary(
            strategy_type="dca_accumulation",
            date_range={"start": "2019-10-01", "end": "2025-10-31"},
        ),
        missing_required_fields=["asset_universe"],
        semantic_turn_act="result_followup",
    )

    result, _interpreter = run_interpret_with_llm(
        message="do the date range October 2019 to October 2025",
        response=response,
        snapshot=_latest_dca_result_snapshot(),
        selected_thread_metadata={"last_stage_outcome": "end_run"},
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.asset_universe == ["AAPL", "GOOG"]
    assert strategy.date_range == {"start": "2019-10-01", "end": "2025-10-31"}
    assert strategy.capital_amount == 200
    assert result.decision.missing_required_fields == []


def test_result_artifact_date_patch_overrides_date_only_unsupported_misroute() -> None:
    response = StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User supplied a date window.",
        assistant_response="I need a supported rule to run this.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="do the date range October 2019 to October 2025",
            strategy_thesis="Backtest over the date range October 2019 to October 2025.",
            date_range={"start": "2019-10-01", "end": "2025-10-31"},
        ),
        missing_required_fields=["entry_logic", "asset_universe", "exit_logic"],
        unsupported_constraints=[
            UnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="Backtest over the date range October 2019 to October 2025.",
                explanation="This idea depends on strategy logic that is not executable yet.",
            )
        ],
    )

    result, _interpreter = run_interpret_with_llm(
        message="do the date range October 2019 to October 2025",
        response=response,
        snapshot=_latest_dca_result_snapshot(),
        selected_thread_metadata={"last_stage_outcome": "end_run"},
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "GOOG"]
    assert strategy.date_range == {"start": "2019-10-01", "end": "2025-10-31"}
    assert result.decision.missing_required_fields == []
    assert result.decision.unsupported_constraints == []


def _latest_dca_result_snapshot() -> TaskSnapshot:
    return TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "asset_class": "equity",
                "symbols": ["AAPL", "GOOG"],
                "benchmark_symbol": "SPY",
                "config_snapshot": {
                    "template": "dca_accumulation",
                    "symbols": ["AAPL", "GOOG"],
                    "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
                    "benchmark_symbol": "SPY",
                    "resolved_strategy": {
                        "strategy_type": "dca_accumulation",
                        "asset_universe": ["AAPL", "GOOG"],
                        "entry_rule": {
                            "type": "periodic_accumulation",
                            "cadence": "monthly",
                        },
                        "exit_rule": {"type": "end_of_period"},
                    },
                    "resolved_parameters": {
                        "timeframe": "1D",
                        "date_range": {
                            "start": "2021-01-01",
                            "end": "2024-01-31",
                        },
                        "capital_amount": 200,
                        "recurring_contribution": 200,
                        "cadence": "monthly",
                        "benchmark_symbol": "SPY",
                    },
                },
            },
        )
    )


def test_capability_question_answer_uses_indicator_registry_not_llm_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_chat_completion(**kwargs: Any) -> str:
        captured.update(kwargs)
        return (
            "Yes. Bollinger Bands are supported as a runnable indicator rule when "
            "the setup can be turned into a clear entry and exit condition."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked which indicators Argus can execute.",
        assistant_response="I only support RSI right now.",
        semantic_turn_act="educational_question",
        capability_question_focus="supported_indicators",
    )

    result, interpreter = run_interpret_with_llm(
        message="do you only support two indicators?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_to_respond"
    assert "I only support RSI" not in answer
    for spec in EXECUTABLE_INDICATORS.values():
        assert spec.label in captured["messages"][1]["content"]
    assert captured["task"] == "chat_composer"
    assert (
        result.patch["normalized_signals"]["capability_question_focus"]
        == "supported_indicators"
    )


def test_supported_indicator_capability_composer_failure_uses_locale_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_chat_completion(**_: Any) -> str:
        raise RuntimeError("chat tier unavailable")

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _failing_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked which indicators Argus can execute.",
        assistant_response="I only support RSI right now.",
        semantic_turn_act="educational_question",
        capability_question_focus="supported_indicators",
    )

    result, _interpreter = run_interpret_with_llm(
        message="¿puedo usar bandas bollinger?",
        response=response,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "I only support RSI" not in answer
    assert "No pude formular" in answer
    assert "intenta de nuevo" in answer
    assert "Executable indicators" not in answer
    for spec in EXECUTABLE_INDICATORS.values():
        assert spec.label not in answer


def test_supported_indicator_capability_contradiction_uses_locale_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _contradictory_chat_completion(**_: Any) -> str:
        return "Bollinger Bands are not supported yet, but RSI is available."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _contradictory_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks whether Bollinger Bands are supported.",
        semantic_turn_act="educational_question",
        capability_question_focus="supported_indicators",
    )

    result, _interpreter = run_interpret_with_llm(
        message="¿puedo usar bandas bollinger?",
        response=response,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "No pude formular" in answer
    assert "intenta de nuevo" in answer
    assert "Executable indicators" not in answer
    assert "not supported" not in answer.lower()
    for spec in EXECUTABLE_INDICATORS.values():
        assert spec.label not in answer


def test_strategy_family_education_keeps_llm_language_over_registry_copy() -> None:
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks for beginner education about dollar cost averaging.",
        assistant_response=(
            "Dollar cost averaging means investing the same amount on a regular "
            "schedule, so the test is about the cadence and contribution size."
        ),
        semantic_turn_act="educational_question",
        capability_question_focus="supported_strategies",
    )

    result, _interpreter = run_interpret_with_llm(
        message="Can you explain dollar cost averaging like I'm completely new?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "Dollar cost averaging" in answer
    assert "Executable strategy families" not in answer


def test_supported_strategy_capability_uses_chat_tier_for_natural_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_chat_completion(**kwargs: Any) -> str:
        captured.update(kwargs)
        return (
            "Dollar cost averaging is the recurring-buy version: pick an asset, "
            "a cadence, and a contribution amount, then compare the historical path."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks for beginner education about dollar cost averaging.",
        semantic_turn_act="educational_question",
        capability_question_focus="supported_strategies",
    )

    result, _interpreter = run_interpret_with_llm(
        message="Can you explain dollar cost averaging like I'm completely new?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "Dollar cost averaging" in answer
    assert "Executable strategy families" not in answer
    assert captured["task"] == "chat_composer"
    assert "recurring buys/DCA" in captured["messages"][1]["content"]


def test_general_capability_education_uses_chat_tier_for_natural_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_chat_completion(**kwargs: Any) -> str:
        captured.update(kwargs)
        return (
            "Dollar cost averaging means buying a fixed amount on a schedule. "
            "In Argus, the closest test is a recurring-buy Bitcoin simulation "
            "over a period you choose."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks for beginner education about dollar cost averaging.",
        semantic_turn_act="educational_question",
        capability_question_focus="general",
    )

    result, _interpreter = run_interpret_with_llm(
        message="Can you explain dollar cost averaging with Bitcoin in plain English?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "Dollar cost averaging" in answer
    assert "Executable strategy families" not in answer
    assert captured["task"] == "chat_composer"
    assert "Execution limits" in captured["messages"][1]["content"]


def test_limits_capability_uses_chat_tier_for_natural_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_chat_completion(**kwargs: Any) -> str:
        captured.update(kwargs)
        return (
            "Argus keeps historical tests simple: long-only, one asset class per "
            "run, and no real trades. If you have an idea, give me the asset and "
            "period and I will shape the closest runnable test."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what Argus can and cannot do.",
        semantic_turn_act="educational_question",
        capability_question_focus="limits",
    )

    result, _interpreter = run_interpret_with_llm(
        message="what can you actually run?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "Execution limits:" not in answer
    assert "one asset class" in answer
    assert captured["task"] == "chat_composer"
    assert "Execution limits" in captured["messages"][1]["content"]


def test_standalone_context_curiosity_uses_chat_tier_without_capability_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_chat_completion(**kwargs: Any) -> str:
        captured.update(kwargs)
        return (
            "Inflation can matter because it changes rate expectations and risk "
            "appetite. A useful next test is comparing the same strategy across "
            "higher-rate and lower-rate periods."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks for inflation context.",
        semantic_turn_act="educational_question",
        context_question_focus="macro_context",
        artifact_target="none",
    )

    result, _interpreter = run_interpret_with_llm(
        message="what's happening to inflation right now?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "Execution limits" not in answer
    assert "Inflation" in answer
    assert "test" in answer.lower()
    assert result.decision.context_question_focus == "macro_context"
    assert captured["task"] == "chat_composer"
    assert "Do not open with what Argus cannot do" in captured["messages"][0]["content"]
    fact_packet = captured["messages"][1]["content"]
    assert "macro context" in fact_packet.lower()
    assert "FRED" not in fact_packet


@pytest.mark.parametrize(
    ("focus", "message", "expected_fact"),
    [
        (
            "corporate_events",
            "what can you tell me about corporate events?",
            "corporate actions",
        ),
        (
            "market_movers",
            "what are the top market movers?",
            "movers and most-actives",
        ),
    ],
)
def test_standalone_event_context_uses_context_fact_bank_not_limits(
    monkeypatch: pytest.MonkeyPatch,
    focus: Any,
    message: str,
    expected_fact: str,
) -> None:
    captured: dict[str, Any] = {}
    completion_calls = 0
    if focus == "market_movers":
        monkeypatch.setattr(
            "argus.agent_runtime.stages.interpret.fetch_alpaca_market_movers_packet",
            lambda **_: build_alpaca_market_movers_packet(
                market_type="stocks",
                movers={
                    "gainers": [{"symbol": "TSLA", "percent_change": 5.1}],
                    "losers": [{"symbol": "AAPL", "percent_change": -2.1}],
                },
            ),
        )

    async def _fake_chat_completion(**kwargs: Any) -> str:
        nonlocal completion_calls
        completion_calls += 1
        captured.update(kwargs)
        if focus == "market_movers" and completion_calls > 1:
            return (
                "A short-lived movers snapshot can help pick test seeds like TSLA "
                "or AAPL. Treat them as symbols to validate, not recommendations, "
                "then choose one for a historical experiment."
            )
        return (
            "That can be useful context, but I would treat it as a starting point "
            "for a historical test. Pick a symbol and I can shape the closest "
            "runnable experiment."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User asks a standalone market context question.",
        semantic_turn_act="educational_question",
        context_question_focus=focus,
        artifact_target="none",
    )

    result, _interpreter = run_interpret_with_llm(
        message=message,
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "Execution limits" not in answer
    assert result.decision.context_question_focus == focus
    assert captured["task"] == "chat_composer"
    assert "Do not open with what Argus cannot do" in captured["messages"][0]["content"]
    assert "Do not reject standalone context questions" in captured["messages"][0][
        "content"
    ]
    assert "Do not suggest live" in captured["messages"][0]["content"]
    assert "Do not propose a concrete executable rule unless" in captured["messages"][
        0
    ]["content"]
    assert "price-jump" in captured["messages"][0]["content"]
    assert "opening sentence must give useful investing context" in captured[
        "messages"
    ][0]["content"]
    fact_packet = captured["messages"][1]["content"]
    assert expected_fact in fact_packet.lower()
    live_packet = captured["messages"][2]["content"]
    supported_packet = captured["messages"][3]["content"]
    assert "buy and hold" in supported_packet
    assert "Bollinger Band" in supported_packet
    assert "unregistered triggers" in supported_packet
    if focus == "market_movers":
        assert "symbol seed" in fact_packet
        assert "ranking feed" in fact_packet
        assert "volume-surge test" in fact_packet
        assert "TSLA" in live_packet
        assert "AAPL" in live_packet
        assert "not recommendations" in live_packet
        assert "asset validation" in live_packet
        assert "TSLA" in answer
        assert completion_calls == 2
    if focus == "corporate_events":
        assert "Do not propose earnings plays" in fact_packet
        assert "No live context packet" in live_packet
        assert "historical test" in answer
        assert completion_calls == 1
    assert "Alpaca" not in fact_packet
    assert "provider" not in captured["messages"][0]["content"].lower()


def test_market_movers_without_packet_does_not_return_hallucinated_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completion_calls = 0

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.fetch_alpaca_market_movers_packet",
        lambda **_: None,
    )

    async def _fake_chat_completion(**_: Any) -> str:
        nonlocal completion_calls
        completion_calls += 1
        return "Current top movers include TSLA, NVDA, and AAPL right now."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User asks for current top market movers.",
        semantic_turn_act="educational_question",
        context_question_focus="market_movers",
        artifact_target="none",
    )

    result, _interpreter = run_interpret_with_llm(
        message="what are the top market movers?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert completion_calls == 0
    assert "TSLA" not in answer
    assert "NVDA" not in answer
    assert "AAPL" not in answer
    assert "historical test" in answer


def test_market_movers_without_packet_uses_user_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completion_calls = 0

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.fetch_alpaca_market_movers_packet",
        lambda **_: None,
    )

    async def _fake_chat_completion(**_: Any) -> str:
        nonlocal completion_calls
        completion_calls += 1
        return "Current top movers include TSLA, NVDA, and AAPL right now."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User asks for current top market movers.",
        semantic_turn_act="educational_question",
        context_question_focus="market_movers",
        artifact_target="none",
    )

    result, _interpreter = run_interpret_with_llm(
        message="cuales son los movimientos fuertes del mercado hoy?",
        response=response,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert completion_calls == 0
    assert "prueba histórica compatible" in answer
    assert "historical test" not in answer
    assert "TSLA" not in answer
    assert "NVDA" not in answer
    assert "AAPL" not in answer


def test_empty_educational_turn_uses_chat_tier_recovery_not_blank_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_chat_completion(**kwargs: Any) -> str:
        captured.update(kwargs)
        return (
            "Market movers can be a starting point for a historical test. Pick a "
            "symbol or theme and I can help check whether similar jumps tended to "
            "continue or reverse."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User asks broad market curiosity.",
        semantic_turn_act="educational_question",
        artifact_target="none",
    )

    result, _interpreter = run_interpret_with_llm(
        message="what are the top market movers?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert answer
    assert "historical test" in answer
    assert captured["task"] == "chat_composer"


def test_unhandled_broad_turn_recovers_with_chat_tier_instead_of_blank_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_chat_completion(**kwargs: Any) -> str:
        captured.update(kwargs)
        return (
            "That is a useful starting point for an experiment. Pick a symbol or "
            "time period and I can turn it into a grounded historical test."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User asks a broad investing question.",
        semantic_turn_act="unsupported_request",
        artifact_target="none",
    )

    result, _interpreter = run_interpret_with_llm(
        message="what are the top market movers?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert answer
    assert "historical test" in answer
    assert captured["task"] == "chat_composer"
    assert "no user-facing answer" in captured["messages"][0]["content"]
    assert "Do not suggest live screens" in captured["messages"][0]["content"]
    assert "Supported experiment paths" in captured["messages"][2]["content"]


def test_supported_strategy_capability_composer_failure_stays_human(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_chat_completion(**_: Any) -> str:
        raise RuntimeError("chat tier unavailable")

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _failing_chat_completion,
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks for beginner education about dollar cost averaging.",
        semantic_turn_act="educational_question",
        capability_question_focus="supported_strategies",
    )

    result, _interpreter = run_interpret_with_llm(
        message="Can you explain dollar cost averaging like I'm completely new?",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "Executable strategy families" not in answer
    assert "could not phrase that capability answer" in answer
    assert "supported rule" in answer


def test_interpret_social_opener_uses_llm_response() -> None:
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User greeted Argus.",
        assistant_response="Hi. Tell me the investing idea you want to test.",
        confidence=0.94,
        semantic_turn_act="educational_question",
    )

    result, interpreter = run_interpret_with_llm(message="hello", response=response)

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"] == response.assistant_response
    assert result.decision.reason_codes[0] == "llm_interpreter_used"
    assert "beginner_language_detected" not in result.decision.reason_codes


def test_unanchored_strategy_route_uses_chat_tier_without_pending_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_chat_completion(**kwargs: Any) -> str:
        captured.update(kwargs)
        return (
            "For a long-term experiment, start with buy and hold or recurring buys. "
            "Pick an asset and a date range, and I can shape the closest runnable test."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _fake_chat_completion,
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User sent a vague conversational message.",
        assistant_response="I'm here. Tell me the investing idea you want to test.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="hello from browser smoke",
            strategy_thesis="hello from browser smoke",
        ),
        missing_required_fields=["asset_universe", "entry_logic", "date_range"],
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="hello from browser smoke",
        response=response,
    )

    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"] != response.assistant_response
    assert "buy and hold" in result.patch["assistant_response"]
    assert captured["task"] == "chat_composer"
    assert "Supported-strategy facts" in captured["messages"][1]["content"]
    assert result.decision.intent == "conversation_followup"
    assert result.decision.missing_required_fields == []
    assert result.decision.candidate_strategy_draft.asset_universe == []
    assert "unanchored_strategy_route_suppressed" in result.decision.reason_codes


def test_unanchored_strategy_route_composer_failure_is_degraded_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _failing_chat_completion(**_: Any) -> str:
        raise RuntimeError("chat tier unavailable")

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.invoke_openrouter_chat_completion",
        _failing_chat_completion,
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User sent a vague strategy start.",
        assistant_response="I'm here. Tell me the investing idea you want to test.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="I want a new strategy",
            strategy_thesis="I want a new strategy",
        ),
        missing_required_fields=["asset_universe", "entry_logic", "date_range"],
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="I want a new strategy",
        response=response,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "saved your message" in answer.lower()
    assert "reliable test setup" in answer.lower()
    assert "buy and hold" not in answer.lower()
    assert "recurring buys" not in answer.lower()
    assert "unanchored_strategy_route_suppressed" in result.decision.reason_codes


def test_interpret_uses_llm_extracted_strategy_fields(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User supplied an RSI strategy.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=(
                "Backtest Tesla and sell when RSI is above 70 over the last 2 years"
            ),
            strategy_type="indicator_threshold",
            strategy_thesis="Backtest Tesla RSI exit rule.",
            asset_universe=["TSLA"],
            entry_logic="RSI drops below 30",
            exit_logic="RSI rises above 70",
            date_range="last 2 years",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Backtest Tesla and sell when RSI is above 70 over the last 2 years",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.exit_logic == "RSI rises above 70"
    assert strategy.date_range == "last 2 years"


def test_interpret_preserves_llm_extracted_timeframe_as_user_assumption(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User supplied an hourly TSLA buy-and-hold test.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="Test TSLA on 1 hour candles over the past month.",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold TSLA on hourly bars.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="past month",
            timeframe="1h",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Test TSLA on 1 hour candles over the past month.",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.candidate_strategy_draft.timeframe == "1h"
    assert result.patch["optional_parameter_status"]["timeframe"] == "1h"
    assert "semantic_timeframe_constraint_preserved" in result.decision.reason_codes


def test_pending_rule_answer_preserves_active_artifact_context(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        raw_user_phrasing="Test buying SPY when it starts rising.",
        strategy_type="signal_strategy",
        strategy_thesis="Test buying SPY when it starts rising.",
        asset_universe=["SPY"],
        asset_class="equity",
        entry_logic="buy SPY when it starts rising",
        exit_logic="sell SPY when it starts falling",
        date_range="past month",
    )
    snapshot = task_snapshot_with_confirmation(pending)
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User defined the pending rising rule as an SMA crossover.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=(
                "use a 20-day SMA crossing above the 50-day SMA over the last month"
            ),
            strategy_type="signal_strategy",
            strategy_thesis="Use a 20-day/50-day SMA crossover.",
            entry_logic="20-day SMA crosses above 50-day SMA",
            exit_logic="20-day SMA crosses below 50-day SMA",
            date_range="last 1 month",
            entry_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 20,
                "slow_indicator": "sma",
                "slow_period": 50,
                "direction": "bullish",
            },
            exit_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 20,
                "slow_indicator": "sma",
                "slow_period": 50,
                "direction": "bearish",
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="use a 20-day SMA crossing above the 50-day SMA over the last month",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "entry_logic",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["SPY"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == "last 1 month"
    assert strategy.entry_rule["fast_period"] == 20
    assert strategy.exit_rule["direction"] == "bearish"
    assert result.decision.missing_required_fields == []


def test_malformed_signal_rule_spec_is_not_executable() -> None:
    strategy = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Buy when price crosses above an undefined moving average.",
        asset_universe=["SPY"],
        asset_class="equity",
        date_range="past month",
        rule_spec={
            "entry": {
                "conditions": [
                    {
                        "left": "price",
                        "operator": "crosses_above",
                        "right": "sma",
                    }
                ]
            },
            "exit": {
                "conditions": [
                    {
                        "left": "price",
                        "operator": "crosses_below",
                        "right": "sma",
                    }
                ]
            },
        },
    )

    assert "entry_logic" in missing_required_fields_for_strategy(
        strategy,
        contract=build_default_capability_contract(),
    )


def test_pending_signal_subset_with_macd_shorthand_reaches_confirmation(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    pending = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Test Bitcoin when MACD turns bullish and volume jumps.",
        asset_universe=["BTC"],
        asset_class="crypto",
        date_range="last 6 months",
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User chose the runnable MACD subset.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="signal_strategy",
            entry_logic="MACD line crosses above the signal line",
            exit_logic="MACD line crosses below the signal line",
            rule_spec={
                "type": "macd_crossover",
                "direction": "bullish",
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            },
        ),
        missing_required_fields=["entry_logic"],
        assistant_response="The old volume clarification should not block this subset.",
        semantic_turn_act="new_idea",
    )

    result, _interpreter = run_interpret_with_llm(
        message="ok run the macd crossover only",
        response=response,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "entry_logic",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["BTC"]
    assert strategy.date_range == "last 6 months"
    assert strategy.entry_logic == "MACD line crosses above the signal line"
    assert result.decision.missing_required_fields == []


def test_structured_signal_rule_from_llm_reaches_confirmation_without_text_scanner(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to buy SPY on a concrete moving-average crossover.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="Test buying SPY when the 5-day SMA crosses above the 20-day SMA.",
            strategy_type="signal_strategy",
            strategy_thesis="Test buying SPY when the 5-day SMA crosses above the 20-day SMA.",
            asset_universe=["SPY"],
            asset_class="equity",
            entry_logic="5-day SMA crosses above 20-day SMA",
            exit_logic="5-day SMA crosses below 20-day SMA",
            date_range="past month",
            entry_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 5,
                "slow_indicator": "sma",
                "slow_period": 20,
                "direction": "bullish",
            },
            exit_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 5,
                "slow_indicator": "sma",
                "slow_period": 20,
                "direction": "bearish",
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Test buying SPY when the 5-day SMA crosses above the 20-day SMA.",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["SPY"]
    assert strategy.entry_rule["fast_period"] == 5
    assert strategy.exit_rule["direction"] == "bearish"
    assert result.decision.missing_required_fields == []
    assert "semantic_unsubstantiated_signal_rule_removed" not in result.decision.reason_codes


def test_interpret_approval_uses_semantic_turn_act() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        date_range="past year",
    )
    snapshot = task_snapshot_with_confirmation(pending)
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User approved the pending backtest.",
        candidate_strategy_draft=pending,
        assistant_response="I will run the backtest now.",
        semantic_turn_act="approval",
    )

    result, _ = run_interpret_with_llm(
        message="Run backtest",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        confirmation_payload=validated_confirmation_payload(pending),
        history=[
            {"role": "user", "content": "Buy and hold Tesla over the past year."},
            {"role": "assistant", "content": "Please confirm this backtest."},
        ],
    )

    assert result.outcome == "ready_to_respond"
    response_text = result.patch["assistant_response"].lower()
    assert "visible confirmation" in response_text
    assert "simulation" in response_text
    assert "confirmation_payload" not in result.patch
    assert result.decision.semantic_turn_act == "approval"


def test_interpret_approval_preserves_visible_artifact_without_re_resolving(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub("SLAY", "crypto", raw_symbol=symbol),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="past year",
    )
    snapshot = task_snapshot_with_confirmation(pending)
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User approved the pending backtest.",
        candidate_strategy_draft=StrategySummary(),
        assistant_response="I will run the backtest now.",
        semantic_turn_act="approval",
    )

    result, _ = run_interpret_with_llm(
        message="Run backtest",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        confirmation_payload=validated_confirmation_payload(pending),
    )

    assert result.outcome == "ready_to_respond"
    response_text = result.patch["assistant_response"].lower()
    assert "visible confirmation" in response_text
    assert "simulation" in response_text
    assert "confirmation_payload" not in result.patch
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["TSLA"]


def test_interpret_approval_without_validated_payload_refreshes_confirmation() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User approved the pending backtest.",
        candidate_strategy_draft=pending,
        assistant_response="I will run the backtest now.",
        semantic_turn_act="approval",
    )

    result, _ = run_interpret_with_llm(
        message="Run backtest",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        confirmation_payload={
            "strategy": pending.model_dump(mode="python"),
            "optional_parameters": {},
        },
    )

    assert result.outcome == "ready_for_confirmation"
    assert "confirmation_payload" not in result.patch


def test_interpret_approval_does_not_run_when_turn_contains_date_refinement(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Nvidia.",
        asset_universe=["NVDA"],
        asset_class="equity",
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User wants to shorten the existing Nvidia draft.",
        candidate_strategy_draft=StrategySummary(date_range="last 6 months"),
        semantic_turn_act="approval",
    )

    result, _ = run_interpret_with_llm(
        message="Use the last 6 months instead.",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        confirmation_payload=validated_confirmation_payload(pending),
    )

    assert result.outcome == "ready_for_confirmation"
    assert "confirmation_payload" not in result.patch
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.date_range == "last 6 months"
    assert result.decision.task_relation == "refine"


def test_active_confirmation_date_refinement_is_material_even_when_labeled_approval(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2025-06-16", "end": "2026-06-15"},
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User changed the active confirmation date range.",
        candidate_strategy_draft=StrategySummary(
            date_range={"start": "2025-01-01", "end": "2025-04-01"},
        ),
        semantic_turn_act="approval",
    )

    result, _ = run_interpret_with_llm(
        message="Use Jan 1 2025 to Apr 1 2025",
        response=response,
        snapshot=task_snapshot_with_confirmation(pending),
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        confirmation_payload=validated_confirmation_payload(pending),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.candidate_strategy_draft.date_range == {
        "start": "2025-01-01",
        "end": "2025-04-01",
    }
    assert result.decision.candidate_strategy_draft.asset_universe == ["AAPL"]


def test_interpret_approval_does_not_run_when_turn_contains_asset_refinement(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User wants to change the asset in the visible draft.",
        candidate_strategy_draft=StrategySummary(asset_universe=["NVDA"]),
        semantic_turn_act="approval",
    )

    result, _ = run_interpret_with_llm(
        message="Actually make it Nvidia.",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        confirmation_payload=validated_confirmation_payload(pending),
    )

    assert result.outcome == "ready_for_confirmation"
    assert "confirmation_payload" not in result.patch
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.date_range == "past year"
    assert result.decision.task_relation == "refine"


def test_structured_confirmation_action_preserves_visible_artifact_without_re_resolving(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub("SLAY", "crypto", raw_symbol=symbol),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.structured_action = StructuredActionContext(
        type="run_backtest",
        label="Run backtest",
        presentation="confirmation",
    )
    state.confirmation_payload = validated_confirmation_payload(pending)

    result = interpret_stage(
        state=state,
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=None,
    )

    assert result.outcome == "approved_for_execution"
    strategy = result.patch["confirmation_payload"]["strategy"]
    assert strategy["asset_universe"] == ["TSLA"]
    assert strategy["asset_class"] == "equity"
    assert result.patch["confirmation_payload"]["launch_payload"]["symbol"] == "TSLA"


def test_structured_confirmation_action_uses_snapshot_payload_when_turn_payload_missing(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub("SLAY", "crypto", raw_symbol=symbol),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="past year",
    )
    payload = validated_confirmation_payload(pending)
    snapshot = TaskSnapshot(
        pending_strategy_summary=pending,
        active_confirmation_reference=confirmation_artifact_reference(
            confirmation_id="confirm-visible",
            confirmation_payload=payload,
        ),
    )
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.structured_action = StructuredActionContext(
        type="run_backtest",
        label="Run backtest",
        presentation="confirmation",
        payload={
            "confirmation_id": "confirm-visible",
        },
    )

    result = interpret_stage(
        state=state,
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=None,
    )

    assert result.outcome == "approved_for_execution"
    assert result.patch["confirmation_payload"]["launch_payload"]["symbol"] == "TSLA"


def test_selected_asset_mention_provenance_keeps_equity_symbol_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.resolution import AssetResolution
    from argus.agent_runtime.stages import interpret as interpret_module

    provider_queries: list[tuple[str, str]] = []

    def _resolution(
        query: str,
        *,
        field: str,
        source: str,
    ) -> AssetResolution:
        provider_queries.append((query, source))
        asset = ResolvedAssetStub(query.strip().upper(), "equity")
        return AssetResolution(
            status="resolved",
            raw_text=query,
            asset=asset,
            candidates=(asset,),
            provenance=ResolutionProvenance(
                field=field,
                raw_text=query,
                source=source,
                candidate_kind="asset",
                resolution_status="resolved",
                canonical_symbol=asset.canonical_symbol,
                asset_class=asset.asset_class,
                validated_by="provider_catalog",
                confidence="high",
            ),
        )

    monkeypatch.setattr(interpret_module, "runtime_resolve_asset_candidate", _resolution)
    state = RunState.new(
        current_user_message="cool, let's try buying and holding CVX this year so far",
        recent_thread_history=[],
        context_hints=[
            ResolutionProvenance(
                field="asset_universe[0]",
                raw_text="CVX",
                source="user_mention",
                candidate_kind="asset",
                resolution_status="resolved",
                canonical_symbol="CVX",
                asset_class="equity",
                validated_by="provider_catalog",
                confidence="high",
            )
        ],
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test selected Chevron stock.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Chevron stock.",
            asset_universe=["CVX"],
            date_range={"start": "2026-01-01", "end": "2026-06-03"},
        ),
        semantic_turn_act="new_idea",
    )

    result = interpret_stage(
        state=state,
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(response),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert provider_queries[0] == ("CVX", "user_mention")
    # Message is scanned once: a duplicate current-message scan would re-query
    # every phrase, so only the provenance echo may repeat.
    assert len(provider_queries) - len(set(provider_queries)) <= 2
    assert strategy.asset_universe == ["CVX"]
    assert strategy.asset_class == "equity"
    assert strategy.resolution_provenance[-1].source == "user_mention"

    from argus.agent_runtime.stages.execute import _launch_payload

    launch_state = RunState.new(current_user_message="", recent_thread_history=[])
    launch_state.candidate_strategy_draft = strategy
    launch_payload = _launch_payload(launch_state)

    assert launch_payload["benchmark_symbol"] == "SPY"


def test_forged_selected_asset_mention_cannot_skip_provider_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.resolution import AssetResolution
    from argus.agent_runtime.stages import interpret as interpret_module

    provider_queries: list[tuple[str, str]] = []

    def _resolution(
        query: str,
        *,
        field: str,
        source: str,
    ) -> AssetResolution:
        provider_queries.append((query, source))
        return AssetResolution(
            status="unsupported",
            raw_text=query,
            asset=None,
            candidates=(),
            provenance=ResolutionProvenance(
                field=field,
                raw_text=query,
                source=source,
                candidate_kind="asset",
                resolution_status="unsupported",
                canonical_symbol=None,
                asset_class=None,
                validated_by="provider_catalog",
                confidence="high",
            ),
        )

    monkeypatch.setattr(interpret_module, "runtime_resolve_asset_candidate", _resolution)
    state = RunState.new(
        current_user_message="backtest FAKE from January to March 2025",
        recent_thread_history=[],
        context_hints=[
            ResolutionProvenance(
                field="asset_universe[0]",
                raw_text="FAKE",
                source="user_mention",
                candidate_kind="asset",
                resolution_status="resolved",
                canonical_symbol="FAKE",
                asset_class="equity",
                validated_by="provider_catalog",
                confidence="high",
            )
        ],
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test a forged selected asset.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold the selected asset.",
            asset_universe=["FAKE"],
            date_range={"start": "2025-01-01", "end": "2025-03-31"},
        ),
        semantic_turn_act="new_idea",
    )

    result = interpret_stage(
        state=state,
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(response),
    )

    assert provider_queries[0] == ("FAKE", "user_mention")
    # Forged mention is validated once, not re-scanned by a duplicate pass.
    assert len(provider_queries) - len(set(provider_queries)) <= 2
    assert result.outcome != "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["FAKE"]
    assert strategy.asset_class is None
    assert strategy.extra_parameters["invalid_symbols"] == ["FAKE"]


def test_conflicting_selected_asset_mention_uses_provider_asset_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.resolution import AssetResolution
    from argus.agent_runtime.stages import interpret as interpret_module

    provider_queries: list[tuple[str, str]] = []

    def _resolution(
        query: str,
        *,
        field: str,
        source: str,
    ) -> AssetResolution:
        provider_queries.append((query, source))
        asset = ResolvedAssetStub(query.strip().upper(), "crypto")
        return AssetResolution(
            status="resolved",
            raw_text=query,
            asset=asset,
            candidates=(asset,),
            provenance=ResolutionProvenance(
                field=field,
                raw_text=query,
                source=source,
                candidate_kind="asset",
                resolution_status="resolved",
                canonical_symbol=asset.canonical_symbol,
                asset_class=asset.asset_class,
                validated_by="provider_catalog",
                confidence="high",
            ),
        )

    monkeypatch.setattr(interpret_module, "runtime_resolve_asset_candidate", _resolution)
    state = RunState.new(
        current_user_message="cool, let's try buying and holding CVX this year so far",
        recent_thread_history=[],
        context_hints=[
            ResolutionProvenance(
                field="asset_universe[0]",
                raw_text="CVX",
                source="user_mention",
                candidate_kind="asset",
                resolution_status="resolved",
                canonical_symbol="CVX",
                asset_class="equity",
                validated_by="provider_catalog",
                confidence="high",
            )
        ],
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test selected asset with conflicting metadata.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold the selected asset.",
            asset_universe=["CVX"],
            date_range={"start": "2026-01-01", "end": "2026-06-03"},
        ),
        semantic_turn_act="new_idea",
    )

    result = interpret_stage(
        state=state,
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(response),
    )

    assert result.outcome == "ready_for_confirmation"
    assert provider_queries[0] == ("CVX", "user_mention")
    # No phrase is re-queried by a duplicate current-message scan.
    assert len(provider_queries) - len(set(provider_queries)) <= 2
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["CVX"]
    assert strategy.asset_class == "crypto"


def test_launch_payload_carries_strategy_asset_class() -> None:
    from argus.agent_runtime.stages.execute import _launch_payload

    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Chevron stock.",
        asset_universe=["CVX"],
        asset_class="equity",
        date_range={"start": "2026-01-01", "end": "2026-06-03"},
        comparison_baseline="SPY",
    )

    launch_payload = _launch_payload(state)

    assert launch_payload["asset_class"] == "equity"
    assert launch_payload["symbols"] == ["CVX"]
    assert launch_payload["benchmark_symbol"] == "SPY"


def test_structured_confirmation_action_rejects_stale_artifact_identity() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="past year",
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=pending,
        active_confirmation_reference=ArtifactReference(
            artifact_kind="confirmation",
            artifact_id="confirm-new",
            artifact_status="active",
            metadata={
                "confirmation_id": "confirm-new",
                "launch_payload_hash": "new-hash",
            },
        ),
    )
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.structured_action = StructuredActionContext(
        type="run_backtest",
        label="Run backtest",
        presentation="confirmation",
        payload={
            "confirmation_id": "confirm-old",
            "launch_payload_hash": "old-hash",
        },
    )
    state.confirmation_payload = validated_confirmation_payload(pending)

    result = interpret_stage(
        state=state,
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=None,
    )

    assert result.outcome == "await_user_reply"
    assert "confirmation was updated" in result.patch["assistant_prompt"]
    assert "confirmation_payload" not in result.patch


def test_structured_confirmation_action_without_validated_payload_refreshes_card() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.structured_action = StructuredActionContext(
        type="run_backtest",
        label="Run backtest",
        presentation="confirmation",
    )
    state.confirmation_payload = {
        "strategy": pending.model_dump(mode="python"),
        "optional_parameters": {},
    }

    result = interpret_stage(
        state=state,
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=None,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.patch["candidate_strategy_draft"]["asset_universe"] == ["TSLA"]
    assert "confirmation_payload" not in result.patch


def test_confirmation_edit_action_publishes_intent_without_backend_prompt() -> None:
    pending = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Buy Apple weekly.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-03-01", "end": "2024-10-31"},
        cadence="weekly",
        capital_amount=250,
        extra_parameters={
            "field_provenance": {
                "capital_amount": "recurring_contribution",
                "cadence": "explicit_user",
            },
            "recurring_contribution": 250,
            "recurring_cadence": "weekly",
        },
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.structured_action = StructuredActionContext(
        type="adjust_assumptions",
        label="Adjust assumptions",
        presentation="confirmation",
    )

    result = interpret_stage(
        state=state,
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=None,
    )

    assert result.outcome == "needs_clarification"
    assert result.patch["assistant_prompt"] is None
    assert result.patch["requested_field"] == "assumption"
    assert result.patch["missing_required_fields"] == ["assumption"]
    assert result.patch["response_intent"]["kind"] == "clarification"
    assert result.patch["response_intent"]["semantic_needs"] == ["assumption"]
    assert result.patch["response_intent"]["requested_fields"] == ["assumption"]
    assert result.patch["response_intent"]["facts"]["strategy"]["asset_universe"] == [
        "AAPL"
    ]


def test_failed_action_retry_recovery_uses_explicit_recovery_message() -> None:
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.response_intent = ResponseIntent(
        kind="artifact_action_recovery",
        facts={
            "action_type": "retry_failed_action",
            "status": "stale",
            "requested_failed_action_id": "failed-old",
            "latest_failed_action_id": "failed-new",
        },
    )

    prompt = artifact_action_recovery_message(state.response_intent)

    assert prompt is not None
    assert "older failed run" in prompt
    assert "latest retry action" in prompt


def test_failed_action_retry_rebuilt_confirmation_uses_explicit_recovery_message() -> None:
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.response_intent = ResponseIntent(
        kind="artifact_action_recovery",
        facts={
            "action_type": "retry_failed_action",
            "status": "rebuilt_confirmation",
            "latest_failed_action_id": "failed-action-1",
        },
    )

    prompt = artifact_action_recovery_message(state.response_intent)

    assert prompt is not None
    assert "rebuilt the draft" in prompt
    assert "review the card" in prompt


def test_failed_action_retry_recovery_degrades_invalid_facts() -> None:
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state.response_intent = ResponseIntent(
        kind="artifact_action_recovery",
        facts={
            "action_type": "retry_failed_action",
            "status": "retry_this_somehow",
            "latest_failed_action_id": "failed-action-1",
        },
    )

    prompt = artifact_action_recovery_message(state.response_intent)

    assert prompt is not None
    assert "current conversation state" in prompt
    assert "latest visible action" in prompt


def test_interpret_answers_pending_draft_assumption_followup_without_approval() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked a follow-up.",
        candidate_strategy_draft=pending,
        assistant_response="I can explain the assumptions first.",
        semantic_turn_act="result_followup",
    )

    result, _ = run_interpret_with_llm(
        message="Can you explain the assumptions?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    assert "For the current idea" in result.patch["assistant_response"]
    assert "Long-only" in result.patch["assistant_response"]
    assert result.decision.semantic_turn_act == "result_followup"


def test_result_followup_uses_latest_result_fact_bank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        assert kwargs["focus"] == "max_drawdown"
        assert kwargs["metadata"]["symbols"] == ["MSFT"]
        assert kwargs["language"] == "en"
        return "MSFT's max drawdown was 34.2% in the latest run."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={
                "symbols": ["MSFT"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": -9.7,
                            "benchmark_return_pct": 26.4,
                            "delta_vs_benchmark_pct": -36.1,
                        },
                        "risk": {"max_drawdown_pct": -34.2},
                    }
                },
                "config_snapshot": {
                    "template": "buy_and_hold",
                    "symbols": ["MSFT"],
                    "date_range": {"start": "2025-05-13", "end": "2026-05-13"},
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks for max drawdown.",
        semantic_turn_act="result_followup",
        result_followup_focus="max_drawdown",
    )

    result, _ = run_interpret_with_llm(
        message="What was the max drawdown?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    response_text = result.patch["assistant_response"]
    assert "34.2%" in response_text
    assert "drawdown" in response_text.lower()
    assert "MSFT" in response_text


def test_result_followup_uses_latest_result_when_interpreter_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "Grounded answer from the latest result facts."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-interpreter-down",
            artifact_status="completed",
            metadata={
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 41.1,
                            "benchmark_return_pct": 26.7,
                            "delta_vs_benchmark_pct": 14.4,
                        }
                    }
                },
                "config_snapshot": {
                    "template": "buy_and_hold",
                    "symbols": ["AAPL"],
                    "date_range": {"start": "2025-05-15", "end": "2026-05-15"},
                },
            },
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="Why did this happen?",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=snapshot,
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"].startswith("**What happened**")
    assert "Grounded answer from the latest result facts." in result.patch[
        "assistant_response"
    ]
    assert result.decision is not None
    assert result.decision.semantic_turn_act == "result_followup"
    assert result.decision.result_followup_focus == "general"
    assert "latest_result_fact_bank_recovery" in result.decision.reason_codes
    assert captured["metadata"]["symbols"] == ["AAPL"]
    assert captured["user_message"] == "Why did this happen?"


def test_result_followup_heading_uses_user_language_when_interpreter_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        del kwargs
        return "Respuesta fundamentada en el resultado más reciente."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-interpreter-down-es",
            artifact_status="completed",
            metadata={
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 41.1,
                            "benchmark_return_pct": 26.7,
                            "delta_vs_benchmark_pct": 14.4,
                        }
                    }
                },
                "config_snapshot": {
                    "template": "buy_and_hold",
                    "symbols": ["AAPL"],
                    "date_range": {"start": "2025-05-15", "end": "2026-05-15"},
                },
            },
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="¿por qué pasó esto?",
            recent_thread_history=[],
        ),
        user=UserState(
            user_id="u1",
            expertise_level="advanced",
            language_preference="es-419",
        ),
        latest_task_snapshot=snapshot,
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"].startswith("**Qué pasó**")
    assert "Respuesta fundamentada" in result.patch["assistant_response"]


def test_result_followup_uses_llm_composer_before_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        captured.update(kwargs)
        return "LLM-composed answer grounded in the result fact bank."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-llm-followup",
            artifact_status="completed",
            metadata={
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 40.8,
                            "benchmark_return_pct": 26.4,
                            "delta_vs_benchmark_pct": 14.5,
                        }
                    }
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks why the result happened.",
        semantic_turn_act="result_followup",
        result_followup_focus="why_underperformed",
    )

    result, _ = run_interpret_with_llm(
        message="Why did this happen?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"].startswith("**What happened**")
    assert (
        "LLM-composed answer grounded in the result fact bank."
        in result.patch["assistant_response"]
    )
    assert captured["metadata"]["symbols"] == ["AAPL"]
    assert captured["focus"] == "why_underperformed"
    assert captured["user_message"] == "Why did this happen?"


def test_empty_non_strategy_turn_after_result_uses_followup_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def empty_compose_result_followup_response(**kwargs: Any) -> None:
        del kwargs
        return None

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        empty_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-next-tests",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 40.8,
                            "benchmark_return_pct": 26.4,
                            "delta_vs_benchmark_pct": 14.5,
                        }
                    }
                },
                "config_snapshot": {
                    "template": "indicator_threshold",
                    "symbols": ["TSLA"],
                    "date_range": {"start": "2025-05-20", "end": "2026-05-20"},
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what to try next.",
        semantic_turn_act="educational_question",
        artifact_target="latest_result",
    )

    result, _ = run_interpret_with_llm(
        message="what should I try next?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    answer_lower = answer.lower()
    assert "latest result" in answer_lower
    assert "could not safely answer that follow-up" in answer_lower
    assert result.decision.semantic_turn_act == "result_followup"
    assert result.decision.result_followup_focus == "general"
    assert result.decision.artifact_target == "latest_result"


def test_latest_result_recovery_preserves_next_experiment_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def empty_compose_result_followup_response(**kwargs: Any) -> None:
        captured.update(kwargs)
        return None

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        empty_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-next-focus",
            artifact_status="completed",
            metadata={
                "symbols": ["BTC"],
                "benchmark_symbol": "BTC",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 75.1,
                            "benchmark_return_pct": 75.1,
                            "delta_vs_benchmark_pct": 0.0,
                        }
                    }
                },
                "config_snapshot": {
                    "template": "buy_and_hold",
                    "symbols": ["BTC"],
                    "date_range": {"start": "2024-01-01", "end": "2026-05-20"},
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what to try next from the latest result.",
        semantic_turn_act="educational_question",
        result_followup_focus="next_experiment",
        artifact_target="latest_result",
    )

    result, _ = run_interpret_with_llm(
        message="what should I try next from this result?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    answer_lower = answer.lower()
    assert answer.startswith("**Try next**")
    assert "could not safely answer that follow-up" in answer_lower
    assert result.patch["recovery"] == {
        "code": "latest_result_followup_unavailable",
        "retryable": True,
        "language": "en",
    }
    assert result.decision.semantic_turn_act == "result_followup"
    assert result.decision.result_followup_focus == "next_experiment"
    assert result.decision.artifact_target == "latest_result"


def test_latest_result_save_request_is_history_preserved_when_strategies_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_compose_result_followup_response(**kwargs: Any) -> str:
        del kwargs
        raise AssertionError("save intent should use the private-alpha guard")

    composed_save_response: dict[str, Any] = {}

    async def compose_private_alpha_save_response(**kwargs: Any) -> str:
        composed_save_response.update(kwargs)
        return "I cannot move this into Strategies here, but the run stays reachable from this chat and Recents."

    monkeypatch.setenv("ARGUS_STRATEGIES_ENABLED", "false")
    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.compose_result_followup_response",
        unexpected_compose_result_followup_response,
    )
    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret.compose_private_alpha_save_response",
        compose_private_alpha_save_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-save-request",
            artifact_status="completed",
            metadata={
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "metrics": {"aggregate": {"performance": {"total_return_pct": 12.4}}},
                "config_snapshot": {
                    "template": "buy_and_hold",
                    "symbols": ["AAPL"],
                    "date_range": {"start": "2025-01-01", "end": "2026-01-01"},
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks to save the latest result.",
        semantic_turn_act="result_followup",
        result_followup_focus="general",
        artifact_target="latest_result",
        reason_codes=["latest_result_save_requested"],
    )

    result, _ = run_interpret_with_llm(
        message="save this",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    assert "Saved" not in answer
    assert "Strategy was saved" not in answer
    assert composed_save_response["user_message"] == "save this"
    assert composed_save_response["language"] == "en"
    assert composed_save_response["metadata"]["symbols"] == ["AAPL"]
    assert "latest_result_save_requested" in result.decision.reason_codes


def test_unanchored_clarification_after_result_uses_followup_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def empty_compose_result_followup_response(**kwargs: Any) -> None:
        del kwargs
        return None

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        empty_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-next-tests",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 40.8,
                            "benchmark_return_pct": 26.4,
                            "delta_vs_benchmark_pct": 14.5,
                        }
                    }
                },
                "config_snapshot": {
                    "template": "indicator_threshold",
                    "symbols": ["TSLA"],
                    "date_range": {"start": "2025-05-20", "end": "2026-05-20"},
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User asks what to try next.",
        assistant_response=(
            "I understand the shape of the idea. I need one more detail before "
            "I can turn this into a backtest."
        ),
        candidate_strategy_draft=StrategySummary(),
        semantic_turn_act="new_idea",
        artifact_target="latest_result",
    )

    result, _ = run_interpret_with_llm(
        message="what would be worth trying after that run?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    answer_lower = answer.lower()
    assert "latest result" in answer_lower
    assert "could not safely answer that follow-up" in answer_lower
    assert "one more detail" not in answer
    assert result.decision.semantic_turn_act == "result_followup"
    assert result.decision.requires_clarification is False
    assert result.decision.artifact_target == "latest_result"


def test_result_followup_timeout_uses_localized_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    from argus.agent_runtime.stages import interpret_actions
    from argus.llm import openrouter

    async def slow_compose_result_followup_response(**kwargs: Any) -> str:
        del kwargs
        await asyncio.sleep(1)
        return "late answer"

    monkeypatch.setattr(
        interpret_actions,
        "RESULT_FOLLOWUP_COMPOSER_TIMEOUT_SECONDS",
        0.01,
    )
    monkeypatch.setattr(
        interpret_actions,
        "compose_result_followup_response",
        slow_compose_result_followup_response,
    )
    openrouter.clear_openrouter_route_receipts()
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-followup-timeout",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 27.5,
                            "benchmark_return_pct": 23.8,
                            "delta_vs_benchmark_pct": 3.8,
                        },
                        "risk": {"max_drawdown_pct": -17.7},
                    }
                },
                "config_snapshot": {
                    "template": "indicator_threshold",
                    "symbols": ["TSLA"],
                    "date_range": {"start": "2025-05-20", "end": "2026-05-20"},
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks why the result happened.",
        semantic_turn_act="result_followup",
        result_followup_focus="general",
    )

    result, _ = run_interpret_with_llm(
        message="why did that happen?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    assert answer.startswith("**What happened**")
    assert "could not safely answer that follow-up" in answer
    receipts = openrouter.get_openrouter_route_receipts()
    assert receipts[-1].task == "result_summary"
    assert receipts[-1].failure_mode == "result_followup_timeout"


def test_results_explanation_intent_uses_result_artifact_even_if_turn_act_drifts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        assert kwargs["user_message"] == "What exactly did you test?"
        return (
            "I tested AAPL with a buy and hold strategy over the saved run window "
            "against SPY."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-result-intent",
            artifact_status="completed",
            metadata={
                "symbols": ["AAPL"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 40.4,
                            "benchmark_return_pct": 27.3,
                            "delta_vs_benchmark_pct": 13.1,
                        }
                    }
                },
                "config_snapshot": {
                    "template": "buy_and_hold",
                    "symbols": ["AAPL"],
                    "date_range": {
                        "start": "2025-05-14",
                        "end": "2026-05-14",
                    },
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what was tested.",
        assistant_response=(
            "**What happened**\n\nThe strategy returned 40.4% while the benchmark "
            "returned 27.3%."
        ),
        semantic_turn_act="educational_question",
    )

    result, _ = run_interpret_with_llm(
        message="What exactly did you test?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"].startswith("**What happened**")
    assert "I tested AAPL" in result.patch["assistant_response"]
    assert result.decision.semantic_turn_act == "result_followup"


def test_underperformance_followup_corrects_false_premise_when_run_outperformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        assert kwargs["focus"] == "why_underperformed"
        assert kwargs["metadata"]["symbols"] == ["TSLA"]
        return (
            "TSLA beat SPY in this run: the strategy returned +33.4%, "
            "while SPY returned +26.5%."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-outperform",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 33.4,
                            "benchmark_return_pct": 26.5,
                            "delta_vs_benchmark_pct": 6.8,
                        }
                    }
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks why it underperformed.",
        semantic_turn_act="result_followup",
        result_followup_focus="why_underperformed",
    )

    result, _ = run_interpret_with_llm(
        message="Why did it underperform the benchmark?",
        response=response,
        snapshot=snapshot,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "beat SPY" in answer
    assert "+33.4%" in answer
    assert "+26.5%" in answer
    assert "strategy returned +33.4%" in answer
    assert "SPY returned +26.5%" in answer
    assert "while the gap" not in answer


def test_zero_return_followup_uses_result_reason_without_repeating_readout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        assert kwargs["focus"] == "general"
        assert kwargs["metadata"]["symbols"] == ["TSLA"]
        return (
            "The strategy returned 0.0% while SPY returned +8.9%. "
            "No entry trades were executed."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-flat",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 0.0,
                            "benchmark_return_pct": 8.9,
                        },
                        "efficiency": {"total_trades": 0},
                    }
                },
                "resolved_strategy": {
                    "strategy_type": "indicator_threshold",
                    "asset_universe": ["TSLA"],
                    "entry_rule": {
                        "kind": "indicator_threshold",
                        "indicator": "rsi",
                        "period": 14,
                        "operator": "<=",
                        "threshold": 20,
                    },
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks why the result was flat.",
        semantic_turn_act="result_followup",
        result_followup_focus="general",
    )

    result, _ = run_interpret_with_llm(
        message="Why did it return 0%?",
        response=response,
        snapshot=snapshot,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert answer.startswith("**What happened**")
    assert "strategy returned 0.0%" in answer
    assert "SPY returned +8.9%" in answer
    assert "No entry trades were executed" in answer


def test_result_followup_summarizes_what_was_tested_from_fact_bank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        assert kwargs["focus"] == "what_tested"
        assert kwargs["metadata"]["symbols"] == ["MSFT"]
        return (
            "I tested MSFT with buy and hold over May 13, 2025 to May 13, 2026. "
            "Assumptions: Long-only; Equal weight; No fees/slippage; Benchmark: SPY."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-what-tested",
            artifact_status="completed",
            metadata={
                "symbols": ["MSFT"],
                "benchmark_symbol": "SPY",
                "metrics": {},
                "config_snapshot": {
                    "template": "buy_and_hold",
                    "symbols": ["MSFT"],
                    "date_range": {
                        "start": "2025-05-13",
                        "end": "2026-05-13",
                        "display": "May 13, 2025 to May 13, 2026",
                    },
                    "starting_capital": 10000,
                },
                "result_card": {
                    "assumptions": [
                        "Long-only",
                        "Equal weight",
                        "No fees/slippage",
                        "Benchmark: SPY",
                    ]
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what was tested.",
        semantic_turn_act="result_followup",
        result_followup_focus="what_tested",
    )

    result, _ = run_interpret_with_llm(
        message="What exactly did you test?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    assert "MSFT" in answer
    assert "buy and hold" in answer
    assert "May 13, 2025 to May 13, 2026" in answer
    assert "Benchmark: SPY" in answer
    assert "Long-only; Equal weight; No fees/slippage; Benchmark: SPY." in answer
    assert ".;" not in answer
    assert ".." not in answer


def test_result_followup_uses_composer_question_when_llm_focus_is_wrong(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        assert kwargs["focus"] == "max_drawdown"
        assert kwargs["user_message"] == "What exactly did you test?"
        resolved_strategy = kwargs["metadata"]["config_snapshot"]["resolved_strategy"]
        assert resolved_strategy["entry_rule"]["fast_period"] == 20
        return (
            "I tested SPY with the 20-day SMA crossing above the 50-day SMA, "
            "and exited on the opposite 20/50 SMA cross."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-focus-guardrail",
            artifact_status="completed",
            metadata={
                "symbols": ["SPY"],
                "benchmark_symbol": "SPY",
                "metrics": {"aggregate": {"risk": {"max_drawdown_pct": -0.5}}},
                "config_snapshot": {
                    "template": "signal_strategy",
                    "symbols": ["SPY"],
                    "date_range": "past year",
                    "resolved_strategy": {
                        "strategy_type": "signal_strategy",
                        "entry_rule": {
                            "type": "moving_average_crossover",
                            "fast_indicator": "sma",
                            "fast_period": 20,
                            "slow_indicator": "sma",
                            "slow_period": 50,
                            "direction": "bullish",
                        },
                        "exit_rule": {
                            "type": "moving_average_crossover",
                            "fast_indicator": "sma",
                            "fast_period": 20,
                            "slow_indicator": "sma",
                            "slow_period": 50,
                            "direction": "bearish",
                        },
                    },
                },
            },
        )
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what was tested.",
        semantic_turn_act="result_followup",
        result_followup_focus="max_drawdown",
    )

    result, _ = run_interpret_with_llm(
        message="What exactly did you test?",
        response=response,
        snapshot=snapshot,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "20-day SMA crossing above the 50-day SMA" in answer
    assert "opposite 20/50 SMA cross" in answer
    assert "The max drawdown was -0.5%" not in answer


def test_result_followup_names_indicator_rules_and_no_trade_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_compose_result_followup_response(**kwargs: Any) -> str:
        assert kwargs["focus"] == "what_tested"
        assert kwargs["metadata"]["symbols"] == ["TSLA"]
        return (
            "I tested TSLA with an RSI mean reversion strategy: enter when "
            "RSI(14) falls below 20 and exit when RSI(14) rises above 60. "
            "No entry trades were executed, so the run stayed in cash."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret_actions.compose_result_followup_response",
        fake_compose_result_followup_response,
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-flat-rsi",
            artifact_status="completed",
            metadata={
                "symbols": ["TSLA"],
                "benchmark_symbol": "SPY",
                "metrics": {
                    "aggregate": {
                        "performance": {
                            "total_return_pct": 0.0,
                            "benchmark_return_pct": 8.9,
                            "delta_vs_benchmark_pct": -8.9,
                        },
                        "efficiency": {"total_trades": 0},
                    }
                },
                "config_snapshot": {
                    "template": "rsi_mean_reversion",
                    "symbols": ["TSLA"],
                    "date_range": {
                        "start": "2026-02-13",
                        "end": "2026-05-13",
                    },
                    "benchmark_symbol": "SPY",
                    "resolved_strategy": {
                        "strategy_type": "indicator_threshold",
                        "asset_universe": ["TSLA"],
                        "entry_rule": {
                            "indicator": "rsi",
                            "operator": "below",
                            "period": 14,
                            "threshold": 20.0,
                        },
                        "exit_rule": {
                            "indicator": "rsi",
                            "operator": "above",
                            "period": 14,
                            "threshold": 60.0,
                        },
                    },
                    "resolved_parameters": {
                        "indicator": "rsi",
                        "indicator_period": 14,
                        "entry_threshold": 20.0,
                        "exit_threshold": 60.0,
                    },
                },
                "trades": [],
            },
        )
    )
    response = StructuredInterpretation(
        intent="results_explanation",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks what was tested.",
        semantic_turn_act="result_followup",
        result_followup_focus="what_tested",
    )

    result, _ = run_interpret_with_llm(
        message="What exactly did you test?",
        response=response,
        snapshot=snapshot,
    )

    answer = result.patch["assistant_response"]
    assert result.outcome == "ready_to_respond"
    assert "TSLA" in answer
    assert "an RSI mean reversion strategy" in answer
    assert "RSI(14)" in answer
    assert "20" in answer
    assert "60" in answer
    assert "No entry trades were executed" in answer
    assert "stayed in cash" in answer
    assert answer.count("No entry trades were executed") == 1


def test_pending_confirmation_assumption_question_uses_visible_draft() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Microsoft.",
        asset_universe=["MSFT"],
        asset_class="equity",
        date_range="past year",
        assumptions=["Long-only", "Equal weight", "Benchmark: SPY"],
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=pending,
        active_confirmation_reference=ArtifactReference(
            artifact_kind="confirmation",
            artifact_id="confirmation-1",
            artifact_status="active",
            metadata={
                "confirmation_card": {
                    "assumptions": ["Long-only", "Equal weight", "Benchmark: SPY"]
                }
            },
        ),
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks which assumptions are on the visible draft.",
        semantic_turn_act="result_followup",
        result_followup_focus="assumptions",
    )

    result, _ = run_interpret_with_llm(
        message="What assumptions are you using?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    assert "Long-only" in result.patch["assistant_response"]
    assert "Benchmark: SPY" in result.patch["assistant_response"]
    assert "confirmation_card" not in result.patch


def test_pending_confirmation_assumption_question_uses_structured_focus() -> None:
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Nvidia.",
        asset_universe=["NVDA"],
        asset_class="equity",
        date_range="past 6 months",
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=pending,
        active_confirmation_reference=ArtifactReference(
            artifact_kind="confirmation",
            artifact_id="confirmation-1",
            artifact_status="active",
            metadata={
                "confirmation_card": {
                    "assumptions": [
                        "$1,000 starting capital",
                        "1D bars",
                        "No fees",
                        "No slippage",
                        "Benchmark: SPY",
                    ]
                }
            },
        ),
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks which assumptions are on the visible draft.",
        assistant_response="I am using $10,000 starting capital.",
        semantic_turn_act="result_followup",
        result_followup_focus="assumptions",
    )

    result, _ = run_interpret_with_llm(
        message="What assumptions are you using?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    assert "$1,000 starting capital" in result.patch["assistant_response"]
    assert "$10,000" not in result.patch["assistant_response"]


def test_llm_extracted_company_name_resolves_through_provider_catalog(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        lookup = {
            "apple": ResolvedAssetStub("AAPL", "equity", name="Apple Inc."),
            "AAPL": ResolvedAssetStub("AAPL", "equity", name="Apple Inc."),
        }
        if symbol in lookup:
            return lookup[symbol]
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to test buying and holding Apple.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple.",
            asset_universe=["apple"],
            date_range="past year",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Test buying and holding Apple over the past year.",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    assert (
        result.decision.candidate_strategy_draft.asset_universe
        == ["AAPL"]
    )
    assert "assistant_response" not in result.patch


def _patch_company_basket_asset_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.agent_runtime.resolution import AssetResolution
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_candidate_stub(
        query: str,
        *,
        field: str,
        source: str,
    ) -> AssetResolution:
        lookup = {
            "target": ResolvedAssetStub(
                "TGT",
                "equity",
                name="Target Corporation",
            ),
            "tgt": ResolvedAssetStub(
                "TGT",
                "equity",
                name="Target Corporation",
            ),
            "walmart": ResolvedAssetStub(
                "WMT",
                "equity",
                name="Walmart Inc.",
            ),
            "wmt": ResolvedAssetStub(
                "WMT",
                "equity",
                name="Walmart Inc.",
            ),
            "costco": ResolvedAssetStub(
                "COST",
                "equity",
                name="Costco Wholesale Corporation",
            ),
            "cost": ResolvedAssetStub(
                "COST",
                "equity",
                name="Costco Wholesale Corporation",
            ),
        }
        normalized = str(query or "").strip().casefold()
        if normalized in lookup:
            asset = lookup[normalized]
            return AssetResolution(
                status="resolved",
                raw_text=query,
                asset=asset,
                candidates=(asset,),
                provenance=ResolutionProvenance(
                    field=field,
                    raw_text=query,
                    source=source,
                    candidate_kind="asset",
                    resolution_status="resolved",
                    canonical_symbol=asset.canonical_symbol,
                    asset_class=asset.asset_class,
                    validated_by="provider_catalog",
                    confidence="high",
                ),
            )
        return AssetResolution(
            status="unsupported",
            raw_text=query,
            asset=None,
            candidates=(),
            provenance=ResolutionProvenance(
                field=field,
                raw_text=query,
                source=source,
                candidate_kind="asset",
                resolution_status="unsupported",
                canonical_symbol=None,
                asset_class=None,
                validated_by="provider_catalog",
                confidence="low",
            ),
        )

    monkeypatch.setattr(
        interpret_module,
        "runtime_resolve_asset_candidate",
        resolve_candidate_stub,
    )


def test_messy_company_name_prompt_preserves_same_class_asset_basket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_company_basket_asset_resolver(monkeypatch)
    message = (
        "Id like to buy target Walmart and costco evenly with 500 dollars every "
        "month from February 2020 till today"
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants monthly recurring buys in Target, Walmart, and Costco.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=message,
            strategy_type="dca_accumulation",
            strategy_thesis=(
                "Buy Target, Walmart, and Costco with $500 monthly contributions "
                "from February 2020 through today."
            ),
            asset_universe=["target", "Walmart", "costco"],
            asset_class="equity",
            date_range={"start": "2020-02-01", "end": "2026-07-02"},
            cadence="monthly",
            capital_amount=500,
            sizing_mode="capital_amount",
            extra_parameters={
                "recurring_contribution": 500,
                "recurring_cadence": "monthly",
                "field_provenance": {
                    "asset_universe": "explicit_user",
                    "capital_amount": "recurring_contribution",
                    "recurring_contribution": "recurring_contribution",
                    "cadence": "explicit_user",
                    "date_range": "explicit_user",
                },
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(message=message, response=response)

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.asset_universe == ["TGT", "WMT", "COST"]
    assert strategy.asset_class == "equity"
    assert strategy.capital_amount == 500
    assert strategy.cadence == "monthly"
    assert strategy.date_range == {"start": "2020-02-01", "end": "2026-07-02"}
    assert strategy.extra_parameters["recurring_contribution"] == 500
    assert strategy.extra_parameters["recurring_cadence"] == "monthly"
    assert "invalid_symbols" not in strategy.extra_parameters
    assert not any("invalid_symbol" in code for code in result.decision.reason_codes)
    assert result.decision.ambiguous_fields == []
    assert result.decision.unsupported_constraints == []


def test_company_name_asset_basket_preservation_is_strategy_agnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_company_basket_asset_resolver(monkeypatch)
    message = "Backtest target Walmart and costco with 500 dollars since February 2020"
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to backtest Target, Walmart, and Costco.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=message,
            strategy_type="buy_and_hold",
            strategy_thesis=(
                "Buy and hold Target, Walmart, and Costco with $500 starting "
                "capital since February 2020."
            ),
            asset_universe=["target", "Walmart", "costco"],
            asset_class="equity",
            date_range={"start": "2020-02-01", "end": "2026-07-02"},
            capital_amount=500,
            sizing_mode="capital_amount",
            extra_parameters={
                "field_provenance": {
                    "asset_universe": "explicit_user",
                    "capital_amount": "explicit_user",
                    "date_range": "explicit_user",
                },
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(message=message, response=response)

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["TGT", "WMT", "COST"]
    assert strategy.asset_class == "equity"
    assert strategy.capital_amount == 500
    assert strategy.date_range == {"start": "2020-02-01", "end": "2026-07-02"}
    assert "invalid_symbols" not in strategy.extra_parameters
    assert not any("invalid_symbol" in code for code in result.decision.reason_codes)
    assert result.decision.ambiguous_fields == []
    assert result.decision.unsupported_constraints == []


def test_company_name_asset_basket_canonicalizes_interpreter_identified_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.resolution import AssetResolution
    from argus.agent_runtime.stages import interpret as interpret_module

    apple = ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")
    walmart = ResolvedAssetStub("WMT", "equity", name="Walmart Inc.")

    def resolve_candidate_stub(
        query: str,
        *,
        field: str,
        source: str,
    ) -> AssetResolution:
        normalized = str(query or "").strip().casefold()
        lookup = {"aapl": apple, "apple": apple, "walmart": walmart, "wmt": walmart}
        if normalized in lookup:
            asset = lookup[normalized]
            return AssetResolution(
                status="resolved",
                raw_text=query,
                asset=asset,
                candidates=(asset,),
                provenance=ResolutionProvenance(
                    field=field,
                    raw_text=query,
                    source=source,
                    candidate_kind="asset",
                    resolution_status="resolved",
                    canonical_symbol=asset.canonical_symbol,
                    asset_class=asset.asset_class,
                    validated_by="provider_catalog",
                    confidence="high",
                ),
            )
        return AssetResolution(
            status="unsupported",
            raw_text=query,
            asset=None,
            candidates=(),
            provenance=ResolutionProvenance(
                field=field,
                raw_text=query,
                source=source,
                candidate_kind="asset",
                resolution_status="unsupported",
                canonical_symbol=None,
                asset_class=None,
                validated_by="provider_catalog",
                confidence="low",
            ),
        )

    monkeypatch.setattr(
        interpret_module,
        "runtime_resolve_asset_candidate",
        resolve_candidate_stub,
    )
    message = "Backtest AAPL and walmart with 500 dollars since February 2020"
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to backtest AAPL and Walmart.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=message,
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL and Walmart with $500.",
            asset_universe=["AAPL", "walmart"],
            asset_class="equity",
            date_range={"start": "2020-02-01", "end": "2026-07-02"},
            capital_amount=500,
            sizing_mode="capital_amount",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(message=message, response=response)

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "WMT"]
    assert strategy.asset_class == "equity"
    assert "invalid_symbols" not in strategy.extra_parameters
    assert result.decision.ambiguous_fields == []
    assert result.decision.unsupported_constraints == []


def test_ambiguous_interpreter_identified_company_name_clarifies_instead_of_dropping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.resolution import AssetResolution
    from argus.agent_runtime.stages import interpret as interpret_module

    apple = ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")
    alphabet_a = ResolvedAssetStub("GOOGL", "equity", name="Alphabet Inc. Class A")
    alphabet_c = ResolvedAssetStub("GOOG", "equity", name="Alphabet Inc. Class C")

    def resolve_candidate_stub(
        query: str,
        *,
        field: str,
        source: str,
    ) -> AssetResolution:
        normalized = str(query or "").strip().casefold()
        if normalized in {"apple", "aapl"}:
            return AssetResolution(
                status="resolved",
                raw_text=query,
                asset=apple,
                candidates=(apple,),
                provenance=ResolutionProvenance(
                    field=field,
                    raw_text=query,
                    source=source,
                    candidate_kind="asset",
                    resolution_status="resolved",
                    canonical_symbol="AAPL",
                    asset_class="equity",
                    validated_by="provider_catalog",
                    confidence="high",
                ),
            )
        if normalized == "google":
            return AssetResolution(
                status="ambiguous",
                raw_text=query,
                asset=None,
                candidates=(alphabet_a, alphabet_c),
                provenance=ResolutionProvenance(
                    field=field,
                    raw_text=query,
                    source=source,
                    candidate_kind="asset",
                    resolution_status="ambiguous",
                    canonical_symbol=None,
                    asset_class=None,
                    validated_by="provider_catalog",
                    confidence="medium",
                ),
            )
        return AssetResolution(
            status="unsupported",
            raw_text=query,
            asset=None,
            candidates=(),
            provenance=ResolutionProvenance(
                field=field,
                raw_text=query,
                source=source,
                candidate_kind="asset",
                resolution_status="unsupported",
                canonical_symbol=None,
                asset_class=None,
                validated_by="provider_catalog",
                confidence="low",
            ),
        )

    monkeypatch.setattr(
        interpret_module,
        "runtime_resolve_asset_candidate",
        resolve_candidate_stub,
    )
    message = "Backtest AAPL and google with 500 dollars since February 2020"
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to backtest AAPL and Google.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing=message,
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL and Google with $500.",
            asset_universe=["AAPL", "google"],
            asset_class="equity",
            date_range={"start": "2020-02-01", "end": "2026-07-02"},
            capital_amount=500,
            sizing_mode="capital_amount",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(message=message, response=response)

    assert result.outcome == "needs_clarification"
    assert result.decision.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert result.decision.unsupported_constraints == []
    assert len(result.decision.ambiguous_fields) == 1
    ambiguous = result.decision.ambiguous_fields[0]
    assert ambiguous.field_name == "asset_universe[1]"
    assert ambiguous.raw_value == "google"
    assert ambiguous.candidate_normalized_value is None
    assert ambiguous.reason_code == "asset_resolution_ambiguous"


def test_llm_extracted_company_name_canonicalizes_without_current_message_rescan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.resolution import AssetResolution
    from argus.agent_runtime.stages import interpret as interpret_module

    provider_queries: list[tuple[str, str]] = []

    def _resolution(
        query: str,
        *,
        field: str,
        source: str,
    ) -> AssetResolution:
        provider_queries.append((query, source))
        raw = query.strip()
        if raw == "APPLE" and source == "llm_extraction":
            return AssetResolution(
                status="unsupported",
                raw_text=query,
                asset=None,
                candidates=(),
                provenance=ResolutionProvenance(
                    field=field,
                    raw_text=query,
                    source=source,
                    candidate_kind="asset",
                    resolution_status="unsupported",
                    canonical_symbol=None,
                    asset_class=None,
                    validated_by="provider_catalog",
                    confidence="high",
                ),
            )
        if raw.casefold() == "apple":
            asset = ResolvedAssetStub("AAPL", "equity", name="Apple Inc.")
            return AssetResolution(
                status="resolved",
                raw_text=query,
                asset=asset,
                candidates=(asset,),
                provenance=ResolutionProvenance(
                    field=field,
                    raw_text=query,
                    source=source,
                    candidate_kind="asset",
                    resolution_status="resolved",
                    canonical_symbol="AAPL",
                    asset_class="equity",
                    validated_by="provider_catalog",
                    confidence="medium",
                ),
            )
        return AssetResolution(
            status="unsupported",
            raw_text=query,
            asset=None,
            candidates=(),
            provenance=ResolutionProvenance(
                field=field,
                raw_text=query,
                source=source,
                candidate_kind="asset",
                resolution_status="unsupported",
                canonical_symbol=None,
                asset_class=None,
                validated_by="provider_catalog",
                confidence="low",
            ),
        )

    monkeypatch.setattr(interpret_module, "runtime_resolve_asset_candidate", _resolution)
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="El usuario quiere comprar y mantener Apple.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Comprar y mantener Apple.",
            asset_universe=["Apple"],
            date_range="past year",
            capital_amount=100000,
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Prueba comprar y mantener Apple con 100k durante el ultimo ano",
        response=response,
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    assert ("Apple", "llm_extraction") in provider_queries
    assert ("Apple", "user_mention") not in provider_queries
    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.asset_class == "equity"
    assert "invalid_symbols" not in strategy.extra_parameters
    assert all(
        item.resolution_status != "unsupported"
        for item in strategy.resolution_provenance
        if item.field.startswith("asset_universe")
    )
    assert "assistant_response" not in result.patch


def test_explicit_buy_and_hold_overrides_spurious_rule_clarification(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to backtest Tesla.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Backtest buy and hold Tesla over the past year.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="past year",
        ),
        missing_required_fields=["entry_logic", "exit_logic"],
        assistant_response="Do you mean to buy at the start and sell at the end?",
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Backtest buy and hold Tesla over the past year.",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.date_range == "past year"
    assert strategy.entry_logic is None
    assert strategy.exit_logic is None
    assert "assistant_response" not in result.patch


def test_buy_and_hold_repair_uses_structured_type_not_phrase_regex(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants the simple baseline for Tesla.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Own Tesla for the full selected period.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="past year",
        ),
        missing_required_fields=["entry_logic", "exit_logic"],
        assistant_response="What entry and exit rule should I use?",
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Use the simple baseline for Tesla over the past year.",
        response=response,
    )

    strategy = result.decision.candidate_strategy_draft
    assert result.outcome == "ready_for_confirmation"
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.entry_logic is None
    assert strategy.exit_logic is None
    assert "assistant_response" not in result.patch


def test_signal_strategy_missing_exit_only_asks_for_missing_period(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants a 50/200 moving-average crossover.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
            asset_universe=["NVDA"],
            entry_logic="50-day moving average crosses above the 200-day moving average",
            entry_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
        ),
        missing_required_fields=["exit_logic", "date_range"],
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message=(
            "Test Nvidia when the 50-day moving average crosses above "
            "the 200-day moving average."
        ),
        response=response,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.missing_required_fields == ["date_range"]
    assert (
        result.decision.candidate_strategy_draft.exit_logic
        == "50-day SMA crosses below 200-day SMA"
    )


def test_signal_strategy_without_typed_date_range_asks_for_period(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants a 50/200 moving-average crossover.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
            asset_universe=["NVDA"],
            entry_logic="50-day moving average crosses above the 200-day moving average",
            entry_rule={
                "type": "moving_average_crossover",
                "fast_indicator": "sma",
                "fast_period": 50,
                "slow_indicator": "sma",
                "slow_period": 200,
                "direction": "bullish",
            },
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message=(
            "Test Nvidia when the 50-day moving average crosses above "
            "the 200-day moving average."
        ),
        response=response,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.candidate_strategy_draft.date_range is None
    assert result.decision.missing_required_fields == ["date_range"]


def test_vague_signal_strategy_requires_executable_rule(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to buy SPY when it starts rising.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY when it starts rising.",
            asset_universe=["SPY"],
            asset_class="equity",
            date_range="past month",
            entry_logic="buy SPY when it starts rising",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Test buying SPY when it starts rising.",
        response=response,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.missing_required_fields == ["entry_logic"]


def test_unclassified_rule_like_strategy_requires_executable_rule_before_assets(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to buy and sell when price goes up.",
        candidate_strategy_draft=StrategySummary(
            strategy_thesis="Buy when price starts rising and sell after gains.",
            entry_logic="buy when price goes up",
            exit_logic="sell when price goes up",
        ),
        missing_required_fields=["asset_universe", "date_range"],
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="buy and sell when it goes up",
        response=response,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.missing_required_fields[0] == "entry_logic"
    assert "asset_universe" in result.decision.missing_required_fields
    assert "date_range" in result.decision.missing_required_fields


def test_unanchored_investing_thesis_routes_to_supported_simplification(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to test a non-executable signal source.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="trade based on Reddit sentiment",
            strategy_thesis=(
                "Use social discussion sentiment as the signal for trades."
            ),
        ),
        missing_required_fields=["asset_universe", "entry_logic", "date_range"],
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="trade based on Reddit sentiment",
        response=response,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.unsupported_constraints
    constraint = result.decision.unsupported_constraints[0]
    assert constraint.category == "unsupported_strategy_logic"
    assert constraint.simplification_options
    labels = [option.label for option in constraint.simplification_options]
    assert labels == [
        "Use a supported RSI threshold rule",
        "Compare with buy and hold",
        "Use a supported moving-average crossover",
    ]


def test_non_executable_signal_rule_requires_rule_before_date(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants to buy SPY when it starts rising.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY when it starts rising.",
            asset_universe=["SPY"],
            asset_class="equity",
            entry_logic="buy SPY when it starts rising",
            entry_rule={"type": "price_momentum", "direction": "up"},
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Test buying SPY when it starts rising.",
        response=response,
    )

    assert result.outcome == "needs_clarification"
    assert result.decision.missing_required_fields == ["entry_logic"]


def test_llm_vague_rule_clarifying_response_is_not_discarded() -> None:
    response = StructuredInterpretation(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to test buying SPY when it starts rising.",
        assistant_response=(
            "I understand the idea, but 'starts rising' needs a concrete trigger. "
            "Do you want to define it with a moving-average crossover, an RSI "
            "threshold, or a specific percentage move?"
        ),
        semantic_turn_act="unsupported_request",
    )

    result, _ = run_interpret_with_llm(
        message="Test buying SPY when it starts rising.",
        response=response,
    )

    assert result.outcome == "ready_to_respond"
    assert "starts rising" in result.patch["assistant_response"]


def test_pending_date_answer_uses_structured_interpreter_before_updating_draft(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple.",
            asset_universe=["AAPL"],
            asset_class="equity",
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User answered the pending date question.",
            candidate_strategy_draft=StrategySummary(date_range="past month"),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="last month",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_for_confirmation"
    assert result.decision.candidate_strategy_draft.date_range == "past month"
    assert "typed_pending_date_answer_applied" not in result.decision.reason_codes


def test_pending_date_answer_accepts_sentence_and_preserves_signal_rule(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    entry_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 20,
        "slow_indicator": "sma",
        "slow_period": 50,
        "direction": "bullish",
    }
    exit_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 20,
        "slow_indicator": "sma",
        "slow_period": 50,
        "direction": "bearish",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY on a moving-average crossover.",
            asset_universe=["SPY"],
            asset_class="equity",
            date_range="past month",
            entry_logic="20-day SMA crosses above 50-day SMA",
            exit_logic="20-day SMA crosses below 50-day SMA",
            entry_rule=entry_rule,
            exit_rule=exit_rule,
            extra_parameters={"entry_rule": entry_rule, "exit_rule": exit_rule},
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User changed only the date on the pending draft.",
            candidate_strategy_draft=StrategySummary(date_range="past year"),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="use the past year instead",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == "past year"
    assert strategy.entry_rule == entry_rule
    assert strategy.exit_rule == exit_rule
    assert result.decision.missing_required_fields == []


def test_pending_date_edit_uses_full_current_message_month_span(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Apple every week.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            capital_amount=250,
            cadence="weekly",
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User changed the pending date range.",
            candidate_strategy_draft=StrategySummary(
                date_range={"end": "2024-10-31"},
                extra_parameters={
                    "date_range_intent": {
                        "kind": "explicit_range",
                        "start": "2024-03-01",
                        "end": "2024-10-31",
                        "confidence": 0.9,
                        "evidence": "march through october 2024",
                    }
                },
            ),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="march through october 2024",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == {"start": "2024-03-01", "end": "2024-10-31"}
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.capital_amount == 250
    assert strategy.cadence == "weekly"


def test_pending_spanish_date_answer_repairs_stale_llm_noop_date_range(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    prior_date_range = {"start": "2025-01-01", "end": "2025-04-01"}
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Compra y conserva AAPL.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range=prior_date_range,
            capital_amount=10000,
            comparison_baseline="SPY",
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User answered the pending date question.",
            candidate_strategy_draft=StrategySummary(
                date_range=prior_date_range,
            ),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Usa del 1 de febrero de 2025 al 1 de mayo de 2025"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == {"start": "2025-02-01", "end": "2025-05-01"}
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.capital_amount == 10000
    assert strategy.comparison_baseline == "SPY"
    assert "pending_date_answer_current_message_repaired" in (
        result.decision.reason_codes
    )
    assert "pending_date_edit_noop_rejected" not in result.decision.reason_codes


def test_pending_spanish_date_answer_repairs_missing_llm_date_range(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    prior_date_range = {"start": "2025-01-01", "end": "2025-04-01"}
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Compra y conserva AAPL.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range=prior_date_range,
            capital_amount=10000,
            comparison_baseline="SPY",
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User answered the pending date question.",
            candidate_strategy_draft=StrategySummary(),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Usa del 1 de febrero de 2025 al 1 de mayo de 2025"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == {"start": "2025-02-01", "end": "2025-05-01"}
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.capital_amount == 10000
    assert strategy.comparison_baseline == "SPY"
    assert "pending_date_answer_current_message_repaired" in (
        result.decision.reason_codes
    )
    assert "pending_date_edit_noop_rejected" not in result.decision.reason_codes


def test_pending_spanish_date_answer_repairs_reload_thinned_metadata(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    prior_date_range = {"start": "2025-01-01", "end": "2025-04-01"}
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Compra y conserva AAPL.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range=prior_date_range,
            capital_amount=10000,
            comparison_baseline="SPY",
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=True,
            assistant_response=(
                "¿Quieres comparar este periodo con una estrategia de compra "
                "y mantenimiento simple?"
            ),
            user_goal_summary="User answered with a date range.",
            candidate_strategy_draft=StrategySummary(),
            semantic_turn_act="educational_question",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Usa del 1 de febrero de 2025 al 1 de mayo de 2025"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"requested_field": "date_range"},
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == {"start": "2025-02-01", "end": "2025-05-01"}
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.capital_amount == 10000
    assert strategy.comparison_baseline == "SPY"
    assert "pending_date_answer_route_repaired" in result.decision.reason_codes
    assert "pending_date_edit_noop_rejected" not in result.decision.reason_codes


def test_pending_date_route_repair_prefers_prior_weekday_when_today_matches(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 6, 19)

    monkeypatch.setattr(interpret_module, "date", FrozenDate)
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    prior_date_range = {"start": "2026-01-01", "end": "2026-06-19"}
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range=prior_date_range,
            capital_amount=10000,
            comparison_baseline="SPY",
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=True,
            assistant_response="Which date should we use?",
            user_goal_summary="Misrouted the pending date answer.",
            candidate_strategy_draft=StrategySummary(),
            semantic_turn_act="educational_question",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="last friday",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="en"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == {"start": "2026-01-01", "end": "2026-06-12"}
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.capital_amount == 10000
    assert "pending_date_answer_route_repaired" in result.decision.reason_codes


def test_pending_date_route_repair_runs_when_llm_marks_answer_but_omits_date(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="compare with buy and hold",
            strategy_type="buy_and_hold",
            strategy_thesis="Compare TSLA with buy and hold.",
            asset_universe=["TSLA"],
            asset_class="equity",
            comparison_baseline="SPY",
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User answered the pending date question.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="buy_and_hold",
                asset_universe=["TSLA"],
                asset_class="equity",
                comparison_baseline="SPY",
            ),
            missing_required_fields=[],
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="calendar year 2024",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="en"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.comparison_baseline == "SPY"
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert "pending_date_answer_current_message_repaired" in (
        result.decision.reason_codes
    )


def test_pending_date_edit_preserves_dca_recurring_contribution_role(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Apple every week.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            capital_amount=250,
            cadence="weekly",
            extra_parameters={
                "field_provenance": {
                    "capital_amount": "recurring_contribution",
                    "cadence": "explicit_user",
                },
                "recurring_contribution": 250,
                "recurring_cadence": "weekly",
            },
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User changed the pending date range.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="dca_accumulation",
                strategy_thesis="Buy Apple every week.",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range={"start": "2024-03-01", "end": "2024-10-31"},
                capital_amount=250,
                cadence="weekly",
                extra_parameters={
                    "field_provenance": {
                        "capital_amount": "total_budget",
                        "cadence": "explicit_user",
                    },
                    "total_budget": 250,
                    "recurring_cadence": "weekly",
                },
            ),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="march through october 2024",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == {"start": "2024-03-01", "end": "2024-10-31"}
    assert strategy.capital_amount == 250
    assert strategy.extra_parameters["recurring_contribution"] == 250
    assert "total_budget" not in strategy.extra_parameters
    assert (
        strategy.extra_parameters["field_provenance"]["capital_amount"]
        == "recurring_contribution"
    )
    assert result.decision.unsupported_constraints == []


def test_canonical_dca_interpreter_output_reaches_confirmation_without_phrase_repair(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="User wants weekly Nvidia recurring buys.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="dca_accumulation",
                strategy_thesis=(
                    "DCA accumulation of Nvidia with $250 weekly investments "
                    "from January 1, 2024 to December 31, 2024."
                ),
                asset_universe=["NVDA"],
                asset_class="equity",
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
                capital_amount=250,
                cadence="weekly",
                extra_parameters={
                    "field_provenance": {
                        "cadence": "explicit_user",
                        "capital_amount": "recurring_contribution",
                    },
                    "recurring_contribution": 250,
                    "recurring_cadence": "weekly",
                },
            ),
            missing_required_fields=[],
            semantic_turn_act="new_idea",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Test buying $250 of Nvidia every week, starting January 1, "
                "2024 and ending December 31, 2024."
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=None,
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.cadence == "weekly"
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.capital_amount == 250
    assert result.decision.missing_required_fields == []
    assert result.decision.unsupported_constraints == []
    assert not any(
        "dca_contract_repair" in reason
        for reason in result.decision.reason_codes
    )


def test_pending_dca_assumption_edit_preserves_interpreter_recurring_contribution(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Apple weekly.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2024-03-01", "end": "2024-10-31"},
            capital_amount=250,
            cadence="weekly",
            extra_parameters={
                "field_provenance": {
                    "capital_amount": "recurring_contribution",
                    "cadence": "explicit_user",
                },
                "recurring_contribution": 250,
                "recurring_cadence": "weekly",
            },
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User wants to adjust the DCA contribution.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="dca_accumulation",
                strategy_thesis="Buy Apple weekly.",
                asset_universe=["AAPL"],
                asset_class="equity",
                date_range={"start": "2024-03-01", "end": "2024-10-31"},
                capital_amount=200,
                cadence="weekly",
                extra_parameters={
                    "field_provenance": {
                        "capital_amount": "recurring_contribution",
                    },
                    "recurring_contribution": 200,
                    "recurring_cadence": "weekly",
                },
            ),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="change contribution to 200 dollars every week",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "assumption",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.capital_amount == 200
    assert strategy.cadence == "weekly"
    assert strategy.extra_parameters["recurring_contribution"] == 200
    assert (
        strategy.extra_parameters["field_provenance"]["capital_amount"]
        == "recurring_contribution"
    )
    assert result.decision.unsupported_constraints == []


def test_pending_asset_date_answer_preserves_signal_family_when_llm_defaults_buy_hold(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    entry_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    exit_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bearish",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy when the 50-day moving average crosses above the 200-day.",
            entry_logic="50-day SMA crosses above 200-day SMA",
            exit_logic="50-day SMA crosses below 200-day SMA",
            entry_rule=entry_rule,
            exit_rule=exit_rule,
            extra_parameters={"entry_rule": entry_rule, "exit_rule": exit_rule},
        )
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User answered the pending asset and date question.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold TSLA over the past year.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="past year",
            extra_parameters={"raw_strategy_type": "buy_and_hold"},
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="TSLA over the last year",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "signal_strategy"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.date_range == "past year"
    assert strategy.entry_rule == entry_rule
    assert strategy.exit_rule == exit_rule
    assert strategy.entry_logic == "50-day SMA crosses above 200-day SMA"
    assert strategy.exit_logic == "50-day SMA crosses below 200-day SMA"


def test_ready_pending_signal_ignores_resolved_optional_ambiguity(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    entry_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    exit_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bearish",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy when the 50-day moving average crosses above the 200-day.",
            entry_logic="50-day SMA crosses above 200-day SMA",
            exit_logic="50-day SMA crosses below 200-day SMA",
            entry_rule=entry_rule,
            exit_rule=exit_rule,
            extra_parameters={"entry_rule": entry_rule, "exit_rule": exit_rule},
        )
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User answered the pending asset and date question.",
        candidate_strategy_draft=StrategySummary(
            strategy_thesis="Test TSLA with the 50/200 crossover over the past year.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="past year",
        ),
        ambiguous_fields=[
            AmbiguousField(
                field_name="exit_logic",
                raw_value="optional alternate exit rule",
                candidate_normalized_value="use the opposite moving-average cross",
                reason_code="optional_exit_rule_suggestion",
            )
        ],
        assistant_response=(
            "Would you like to run it as-is, or add a simple exit rule?"
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message="TSLA over the last year",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    assert result.decision.ambiguous_fields == []
    assert result.decision.candidate_strategy_draft.strategy_type == "signal_strategy"
    assert result.decision.candidate_strategy_draft.entry_rule == entry_rule
    assert result.decision.candidate_strategy_draft.exit_rule == exit_rule
    assert "assistant_response" not in result.stage_patch


def test_pending_date_answer_removes_mislabeled_timeframe_constraint(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    entry_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    exit_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bearish",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
            asset_universe=["NVDA"],
            asset_class="equity",
            entry_logic="50-day SMA crosses above 200-day SMA",
            exit_logic="50-day SMA crosses below 200-day SMA",
            entry_rule=entry_rule,
            exit_rule=exit_rule,
            extra_parameters={"entry_rule": entry_rule, "exit_rule": exit_rule},
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User answered the pending date question.",
            candidate_strategy_draft=StrategySummary(
                date_range="past year",
                timeframe="past year",
                extra_parameters={
                    "date_range_intent": {
                        "kind": "rolling_window",
                        "count": 1,
                        "unit": "year",
                        "anchor": "today",
                        "evidence": "past year",
                    }
                },
            ),
            unsupported_constraints=[
                UnsupportedConstraint(
                    category="unsupported_time_granularity",
                    raw_value="past year",
                    explanation="The timeframe is not supported.",
                )
            ],
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="Use the past year.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    today = date.today()
    assert strategy.date_range == {
        "start": today.replace(year=today.year - 1).isoformat(),
        "end": today.isoformat(),
    }
    assert strategy.timeframe is None
    assert strategy.entry_rule == entry_rule
    assert strategy.exit_rule == exit_rule
    assert result.decision.unsupported_constraints == []
    assert (
        "semantic_unsubstantiated_timeframe_constraint_removed"
        in result.decision.reason_codes
    )


def test_pending_rolling_window_endpoint_patch_preserves_duration(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    rolling_intent = {
        "kind": "rolling_window",
        "count": 12,
        "unit": "month",
        "anchor": "today",
        "confidence": 0.94,
        "evidence": "last 12 months",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL over the last 12 months.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2025-06-15", "end": "2026-06-15"},
            capital_amount=100000,
            comparison_baseline="SPY",
            extra_parameters={"date_range_intent": rolling_intent},
        )
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied a new end date for the rolling window.",
        candidate_strategy_draft=StrategySummary(
            date_range={"end": "2026-06-12"},
            extra_parameters={
                "date_range_intent": {
                    "kind": "endpoint_patch",
                    "endpoint": "end",
                    "end": "2026-06-12",
                    "confidence": 0.9,
                    "evidence": "last friday",
                }
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message="last friday",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.comparison_baseline == "SPY"
    assert strategy.capital_amount == 100000
    assert strategy.date_range == {"start": "2025-06-12", "end": "2026-06-12"}
    assert "assistant_response" not in result.stage_patch


def test_pending_rolling_window_patch_infers_missing_endpoint_from_date_delta(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    rolling_intent = {
        "kind": "rolling_window",
        "count": 12,
        "unit": "month",
        "anchor": "today",
        "confidence": 0.94,
        "evidence": "ultimos 12 meses",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Compra y mantén AAPL por los últimos 12 meses.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2025-06-15", "end": "2026-06-15"},
            capital_amount=100000,
            comparison_baseline="SPY",
            extra_parameters={"date_range_intent": rolling_intent},
        )
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied a new end date for the rolling window.",
        candidate_strategy_draft=StrategySummary(
            date_range={"start": "2025-06-15", "end": "2026-06-12"},
            extra_parameters={
                "date_range_intent": {
                    "kind": "endpoint_patch",
                    "confidence": 0.8,
                    "base_intent": rolling_intent,
                }
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message="viernes pasado",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.comparison_baseline == "SPY"
    assert strategy.capital_amount == 100000
    assert strategy.date_range == {"start": "2025-06-12", "end": "2026-06-12"}
    assert "assistant_response" not in result.stage_patch


def test_pending_rolling_window_patch_resolves_bounded_endpoint_evidence(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 6, 15)

    monkeypatch.setattr(interpret_module, "date", FrozenDate)
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    rolling_intent = {
        "kind": "rolling_window",
        "count": 12,
        "unit": "month",
        "anchor": "today",
        "confidence": 0.94,
        "evidence": "ultimos 12 meses",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Compra y mantén AAPL por los últimos 12 meses.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2025-06-15", "end": "2026-06-15"},
            capital_amount=100000,
            comparison_baseline="SPY",
            extra_parameters={"date_range_intent": rolling_intent},
        )
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied a new end date for the rolling window.",
        candidate_strategy_draft=StrategySummary(
            date_range={"start": "2025-06-15", "end": "2026-06-15"},
            extra_parameters={
                "date_range_raw_text": "viernes pasado",
                "date_range_intent": {
                    "kind": "endpoint_patch",
                    "endpoint": "end",
                    "confidence": 0.8,
                    "base_intent": rolling_intent,
                },
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message="viernes pasado",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.comparison_baseline == "SPY"
    assert strategy.capital_amount == 100000
    assert strategy.date_range == {"start": "2025-06-12", "end": "2026-06-12"}
    assert "assistant_response" not in result.stage_patch


def test_pending_date_answer_misroute_uses_pending_field_context(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    rolling_intent = {
        "kind": "rolling_window",
        "count": 12,
        "unit": "month",
        "anchor": "today",
        "confidence": 0.94,
        "evidence": "ultimos 12 meses",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Compra y mantén AAPL por los últimos 12 meses.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2025-06-15", "end": "2026-06-15"},
            capital_amount=100000,
            comparison_baseline="SPY",
            extra_parameters={"date_range_intent": rolling_intent},
        )
    )
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked about last Friday.",
        assistant_response="Podemos hablar de ese viernes como contexto de mercado.",
        semantic_turn_act="educational_question",
    )

    result, _ = run_interpret_with_llm(
        message="viernes pasado",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    expected_end = parse_date_text(
        "viernes pasado",
        today=date.today(),
        languages=("es", "en"),
        prefer_dates_from="past",
    )
    assert expected_end is not None
    expected_start = shift_months(expected_end, -12)

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.comparison_baseline == "SPY"
    assert strategy.capital_amount == 100000
    assert strategy.date_range == {
        "start": expected_start.isoformat(),
        "end": expected_end.isoformat(),
    }
    assert "pending_date_answer_route_repaired" in result.decision.reason_codes
    assert "assistant_response" not in result.stage_patch


def test_pending_concrete_date_endpoint_patch_preserves_existing_start(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL over the last 12 months.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range={"start": "2025-06-15", "end": "2026-06-15"},
            capital_amount=100000,
            comparison_baseline="SPY",
        )
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied a new end date for the existing window.",
        candidate_strategy_draft=StrategySummary(
            date_range={"end": "2026-06-12"},
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message="last friday",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.comparison_baseline == "SPY"
    assert strategy.capital_amount == 100000
    assert strategy.date_range == {"start": "2025-06-15", "end": "2026-06-12"}
    assert "assistant_response" not in result.stage_patch


def test_interpreter_unavailable_date_answer_preserves_active_confirmation(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    async def unavailable_active_confirmation_recovery(**kwargs: Any) -> None:
        del kwargs
        return None

    monkeypatch.setattr(
        interpret_module,
        "compose_active_confirmation_interpreter_recovery",
        unavailable_active_confirmation_recovery,
    )
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    monkeypatch.setattr(
        interpret_module,
        "date",
        type(
            "FrozenDate",
            (date,),
            {"today": classmethod(lambda cls: cls(2026, 6, 15))},
        ),
    )
    strategy = StrategySummary(
        raw_user_phrasing=(
            "Buy and hold AAPL over the last 12 months with SPY as the benchmark."
        ),
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL over the last 12 months.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2025-06-15", "end": "2026-06-15"},
        capital_amount=1000,
        comparison_baseline="SPY",
        extra_parameters={
            "date_range_intent": {
                "kind": "rolling_window",
                "count": 12,
                "unit": "month",
                "anchor": "today",
                "evidence": "last 12 months",
            }
        },
    )

    result = interpret_stage(
        state=RunState.new(current_user_message="last friday", recent_thread_history=[]),
        user=UserState(user_id="u1", language_preference="en"),
        latest_task_snapshot=task_snapshot_with_confirmation(strategy),
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision is not None
    assert result.decision.reason_codes == ["llm_interpreter_unavailable"]
    assert result.decision.candidate_strategy_draft.date_range is None
    assert result.stage_patch["retry_last_turn"] == {"message": "last friday"}
    assert result.stage_patch["recovery"] == {
        "code": "interpreter_unavailable",
        "retryable": True,
        "language": "en",
    }
    assert "visible confirmation" in result.stage_patch["assistant_response"]


def test_contextual_asset_edit_preserves_existing_signal_rule_without_restatement(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    entry_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 20,
        "slow_indicator": "sma",
        "slow_period": 50,
        "direction": "bullish",
    }
    exit_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 20,
        "slow_indicator": "sma",
        "slow_period": 50,
        "direction": "bearish",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY on a moving-average crossover.",
            asset_universe=["SPY"],
            asset_class="equity",
            date_range="past year",
            entry_logic="20-day SMA crosses above 50-day SMA",
            exit_logic="20-day SMA crosses below 50-day SMA",
            entry_rule=entry_rule,
            exit_rule=exit_rule,
            extra_parameters={"entry_rule": entry_rule, "exit_rule": exit_rule},
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="strategy_drafting",
            task_relation="refine",
            requires_clarification=False,
            user_goal_summary="User changed only the asset on the pending draft.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="signal_strategy",
                asset_universe=["NVDA"],
                asset_class="equity",
            ),
            semantic_turn_act="refine_current_idea",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="Actually make it Nvidia.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.date_range == "past year"
    assert strategy.entry_rule == entry_rule
    assert strategy.exit_rule == exit_rule
    assert "semantic_unsubstantiated_signal_rule_removed" not in result.decision.reason_codes


def test_initial_multi_symbol_equity_defaults_to_spy_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User wants a buy-and-hold test for three equities.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
            asset_universe=["AAPL", "MSFT", "TSLA"],
            asset_class="equity",
            date_range={"start": "2023-01-01", "end": "today"},
            capital_amount=100000,
            timeframe="1D",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message=(
            "let's test holding AAPL MSFT and TSLA from 2023 to date with 100k"
        ),
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "MSFT", "TSLA"]
    assert strategy.comparison_baseline == "SPY"
    assert strategy.date_range == {"start": "2023-01-01", "end": "today"}
    assert strategy.capital_amount == 100000
    assert strategy.timeframe == "1D"


def test_contextual_benchmark_edit_preserves_traded_assets_and_setup(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "today"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User changed only the benchmark.",
        candidate_strategy_draft=StrategySummary(
            comparison_baseline="QQQ",
            extra_parameters={
                "field_provenance": {"comparison_baseline": "explicit_user"}
            },
        ),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = run_interpret_with_llm(
        message="compare it to QQQ",
        response=response,
        snapshot=task_snapshot_with_confirmation(pending),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "MSFT", "TSLA"]
    assert strategy.comparison_baseline == "QQQ"
    assert strategy.date_range == {"start": "2023-01-01", "end": "today"}
    assert strategy.capital_amount == 100000
    assert "QQQ" not in strategy.asset_universe


def test_contextual_same_asset_universe_without_operation_is_noop(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "today"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User changed only the benchmark.",
        candidate_strategy_draft=StrategySummary(
            asset_universe=["TSLA", "AAPL", "MSFT"],
            comparison_baseline="QQQ",
            extra_parameters={
                "field_provenance": {"comparison_baseline": "explicit_user"}
            },
        ),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = run_interpret_with_llm(
        message="compare the same setup to QQQ",
        response=response,
        snapshot=task_snapshot_with_confirmation(pending),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "MSFT", "TSLA"]
    assert strategy.comparison_baseline == "QQQ"
    assert strategy.date_range == {"start": "2023-01-01", "end": "today"}
    assert strategy.capital_amount == 100000
    assert "artifact_patch" not in strategy.extra_parameters


def test_active_confirmation_llm_asset_patch_uses_planner_when_new_asset_is_grounded(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_asset_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.strip().upper()
        aliases = {
            "AAPL": "AAPL",
            "APPLE": "AAPL",
            "GOOGL": "GOOGL",
            "GOOGLE": "GOOGL",
            "MICROSOFT": "MSFT",
            "MSFT": "MSFT",
            "TSLA": "TSLA",
            "TESLA": "TSLA",
        }
        canonical = aliases.get(normalized, normalized)
        return ResolvedAssetStub(canonical, "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_asset_stub)
    planner_calls: list[dict[str, Any]] = []

    async def plan_stub(**kwargs: Any) -> ArtifactAssumptionEditPlan:
        planner_calls.append(kwargs)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="add", target="asset", symbols=["GOOGL"]),
                EditOperation(op="remove", target="asset", symbols=["Microsoft"]),
                EditOperation(op="set", target="capital", number=75000),
                EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="explicit_range",
                        start="2026-03-01",
                        end="2026-06-05",
                        confidence=0.95,
                        evidence="3/1/26 thru june 5 2026",
                    ),
                ),
            ],
            confidence=0.94,
        )

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        plan_stub,
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2026-01-01", "end": "2026-06-30"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User changed the visible card.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            asset_universe=["MSFT"],
            asset_class="equity",
            date_range={"start": "2026-03-01", "end": "2026-06-05"},
            capital_amount=75000,
            extra_parameters={"asset_universe_operation": "replace"},
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message=(
            "ok tweak the card: add Google/GOOGL, ditch Microsoft, "
            "make cash seventy five grand, dates 3/1/26 thru june 5 2026"
        ),
        response=response,
        snapshot=task_snapshot_with_confirmation(pending),
    )

    assert planner_calls
    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "TSLA", "GOOGL"]
    assert strategy.capital_amount == 75000
    assert strategy.date_range == {"start": "2026-03-01", "end": "2026-06-05"}
    assert "artifact_assumption_edit_planned" in result.decision.reason_codes


def test_contextual_asset_append_preserves_benchmark_and_setup(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "today"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="QQQ",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User added two equities to the active setup.",
        candidate_strategy_draft=StrategySummary(
            asset_universe=["GOOGL", "NVDA"],
            asset_class="equity",
            extra_parameters={"asset_universe_operation": "append"},
        ),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = run_interpret_with_llm(
        message="add GOOGL and NVDA",
        response=response,
        snapshot=task_snapshot_with_confirmation(pending),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "MSFT", "TSLA", "GOOGL", "NVDA"]
    assert strategy.comparison_baseline == "QQQ"
    assert strategy.date_range == {"start": "2023-01-01", "end": "today"}
    assert strategy.capital_amount == 100000
    assert strategy.extra_parameters["artifact_patch"][
        "asset_universe_operation"
    ] == "append"
    assert "asset_universe_operation" not in strategy.extra_parameters


def test_contextual_asset_replace_preserves_explicit_benchmark_and_setup(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, TSLA, GOOGL, and NVDA.",
        asset_universe=["AAPL", "MSFT", "TSLA", "GOOGL", "NVDA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "today"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="QQQ",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User replaced the active traded universe.",
        candidate_strategy_draft=StrategySummary(
            asset_universe=["AMD", "INTC"],
            asset_class="equity",
            extra_parameters={"asset_universe_operation": "replace"},
        ),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = run_interpret_with_llm(
        message="replace them with AMD and INTC",
        response=response,
        snapshot=task_snapshot_with_confirmation(pending),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AMD", "INTC"]
    assert strategy.comparison_baseline == "QQQ"
    assert strategy.date_range == {"start": "2023-01-01", "end": "today"}
    assert strategy.capital_amount == 100000
    assert strategy.extra_parameters["artifact_patch"][
        "asset_universe_operation"
    ] == "replace"
    assert "asset_universe_operation" not in strategy.extra_parameters


def test_spanish_contextual_asset_edits_use_structured_operation_not_phrase_gates(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Comprar y mantener AAPL y MSFT.",
        asset_universe=["AAPL", "MSFT"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "today"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
    )

    append_result, _ = run_interpret_with_llm(
        message="agrega TSLA",
        response=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="refine",
            requires_clarification=False,
            user_goal_summary="El usuario agregó TSLA.",
            candidate_strategy_draft=StrategySummary(
                asset_universe=["TSLA"],
                asset_class="equity",
                extra_parameters={"asset_universe_operation": "append"},
            ),
            semantic_turn_act="refine_current_idea",
        ),
        snapshot=task_snapshot_with_confirmation(pending),
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    assert append_result.outcome == "ready_for_confirmation"
    appended = append_result.decision.candidate_strategy_draft
    assert appended.asset_universe == ["AAPL", "MSFT", "TSLA"]
    assert appended.comparison_baseline == "SPY"

    replace_result, _ = run_interpret_with_llm(
        message="reemplázalas con AMD e INTC y compáralas contra QQQ",
        response=StructuredInterpretation(
            intent="backtest_execution",
            task_relation="refine",
            requires_clarification=False,
            user_goal_summary="El usuario reemplazó activos y cambió referencia.",
            candidate_strategy_draft=StrategySummary(
                asset_universe=["AMD", "INTC"],
                asset_class="equity",
                comparison_baseline="QQQ",
                extra_parameters={
                    "asset_universe_operation": "replace",
                    "field_provenance": {"comparison_baseline": "explicit_user"},
                },
            ),
            semantic_turn_act="refine_current_idea",
        ),
        snapshot=task_snapshot_with_confirmation(appended),
        user=UserState(user_id="u1", language_preference="es-419"),
    )

    assert replace_result.outcome == "ready_for_confirmation"
    replaced = replace_result.decision.candidate_strategy_draft
    assert replaced.asset_universe == ["AMD", "INTC"]
    assert replaced.comparison_baseline == "QQQ"
    assert replaced.date_range == {"start": "2023-01-01", "end": "today"}
    assert replaced.capital_amount == 100000


def test_crypto_contextual_asset_append_preserves_btc_default_benchmark(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold ETH.",
        asset_universe=["ETH"],
        asset_class="crypto",
        date_range={"start": "2024-01-01", "end": "today"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="BTC",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User added SOL to the crypto setup.",
        candidate_strategy_draft=StrategySummary(
            asset_universe=["SOL"],
            asset_class="crypto",
            extra_parameters={"asset_universe_operation": "append"},
        ),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = run_interpret_with_llm(
        message="add SOL too",
        response=response,
        snapshot=task_snapshot_with_confirmation(pending),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["ETH", "SOL"]
    assert strategy.asset_class == "crypto"
    assert strategy.comparison_baseline == "BTC"


def test_contextual_asset_append_over_five_symbols_requires_correction(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold five equities.",
        asset_universe=["AAPL", "MSFT", "TSLA", "GOOGL", "NVDA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "today"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="QQQ",
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User tried to add a sixth equity.",
        candidate_strategy_draft=StrategySummary(
            asset_universe=["AMD"],
            asset_class="equity",
            extra_parameters={"asset_universe_operation": "append"},
        ),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = run_interpret_with_llm(
        message="add AMD too",
        response=response,
        snapshot=task_snapshot_with_confirmation(pending),
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "MSFT", "TSLA", "GOOGL", "NVDA", "AMD"]
    assert strategy.comparison_baseline == "QQQ"
    assert any(
        "5 symbols" in constraint.explanation
        or "5 symbols" in constraint.raw_value
        for constraint in result.decision.unsupported_constraints
    )


def test_mixed_confirmation_edit_uses_current_explicit_date_intent(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(
            {"microsoft": "MSFT"}.get(str(symbol).casefold(), symbol.upper()),
            "equity",
        ),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, Microsoft, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2026-01-01", "end": "2026-06-30"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
        extra_parameters={
            "date_range_raw_text": "from January 1, 2026 to June 30, 2026",
            "date_range_intent": {
                "kind": "explicit_range",
                "start": "2026-01-01",
                "end": "2026-06-30",
            },
            "evidence_spans": {
                "date_range": "from January 1, 2026 to June 30, 2026",
            },
            "field_provenance": {"date_range": "explicit_user"},
        },
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary=(
            "User added GOOGL, removed Microsoft, changed capital, and set dates."
        ),
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL, TSLA, and GOOGL.",
            asset_universe=["AAPL", "TSLA", "GOOGL"],
            asset_class="equity",
            date_range={"start": "2026-01-01", "end": "2026-06-30"},
            capital_amount=75000,
            timeframe="1D",
            extra_parameters={
                "asset_universe_operation": "replace",
                "date_range_intent": {
                    "kind": "explicit_range",
                    "start": "2026-03-01",
                    "end": "2026-06-05",
                },
                "field_provenance": {
                    "asset_universe": "explicit_user",
                    "capital_amount": "starting_capital",
                    "date_range": "explicit_user",
                },
            },
        ),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = run_interpret_with_llm(
        message=(
            "add GOOGL, remove Microsoft, set capital to $75,000, "
            "date March 1, 2026 to June 5, 2026"
        ),
        response=response,
        snapshot=task_snapshot_with_confirmation(pending),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "TSLA", "GOOGL"]
    assert strategy.capital_amount == 75000
    assert strategy.date_range == {"start": "2026-03-01", "end": "2026-06-05"}


def test_bilingual_confirmation_date_edit_prefers_typed_intent_over_raw_parse(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, GOOG, and TSLA.",
        asset_universe=["AAPL", "GOOG", "TSLA"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
        extra_parameters={
            "date_range_intent": {
                "kind": "explicit_range",
                "start": "2024-01-01",
                "end": "2024-12-31",
                "evidence": "Jan 1 2024 to Dec 31 2024",
            },
            "field_provenance": {"date_range": "explicit_user"},
        },
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User changed the pending date range.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold AAPL, GOOG, and TSLA.",
            asset_universe=["AAPL", "GOOG", "TSLA"],
            asset_class="equity",
            date_range={"start": "2025-04-01", "end": "2026-12-31"},
            capital_amount=100000,
            timeframe="1D",
            comparison_baseline="SPY",
            extra_parameters={
                "date_range_raw_text": (
                    "cambia la fecha a marzo 2 del 2025 a April 14 del 2026"
                ),
                "date_range_intent": {
                    "kind": "explicit_range",
                    "start": "2025-03-02",
                    "end": "2026-04-14",
                    "confidence": 0.9,
                    "evidence": (
                        "cambia la fecha a marzo 2 del 2025 a April 14 del 2026"
                    ),
                },
                "field_provenance": {"date_range": "explicit_user"},
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message="cambia la fecha a marzo 2 del 2025 a April 14 del 2026",
        response=response,
        user=UserState(user_id="u1", language_preference="en"),
        snapshot=task_snapshot_with_confirmation(pending),
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == {"start": "2025-03-02", "end": "2026-04-14"}


def test_interpreter_unavailable_mixed_confirmation_edit_preserves_all_operations(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(
            {"microsoft": "MSFT"}.get(str(symbol).casefold(), symbol.upper()),
            "equity",
        ),
    )
    monkeypatch.setattr(
        interpret_module,
        "provider_ticker_mentions_from_text",
        lambda *args, **kwargs: [
            SimpleNamespace(asset=SimpleNamespace(canonical_symbol="GOOGL"))
        ],
    )

    async def planned_edit(**kwargs: Any) -> ArtifactAssumptionEditPlan:
        del kwargs
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary=(
                "User added GOOGL, removed Microsoft, changed capital, and set dates."
            ),
            operations=[
                EditOperation(op="add", target="asset", symbols=["GOOGL"]),
                EditOperation(op="remove", target="asset", symbols=["Microsoft"]),
                EditOperation(op="set", target="capital", number=75000),
                EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="explicit_range",
                        start="2026-03-01",
                        end="2026-06-05",
                    ),
                ),
            ],
        )

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        planned_edit,
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, Microsoft, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2025-01-01", "end": "2025-12-31"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "add GOOGL, remove Microsoft, set capital to $75,000, "
                "date March 1, 2026 to June 5, 2026"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=task_snapshot_with_confirmation(pending),
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
        structured_interpreter=None,
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "TSLA", "GOOGL"]
    assert strategy.date_range == {"start": "2026-03-01", "end": "2026-06-05"}
    assert strategy.capital_amount == 75000
    assert strategy.timeframe == "1D"
    assert strategy.comparison_baseline == "SPY"


def test_interpreter_unavailable_does_not_parse_pending_date_from_text(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY when it starts rising.",
            asset_universe=["SPY"],
            asset_class="equity",
            entry_logic="buy SPY when it starts rising",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="last month",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision.reason_codes == ["llm_interpreter_unavailable"]
    assert result.decision.candidate_strategy_draft.asset_universe == []
    assert "could not safely apply that change" in result.patch[
        "assistant_response"
    ].lower()
    assert "interpreter" not in result.patch["assistant_response"].lower()


def test_interpreter_unavailable_pending_supported_strategy_applies_calendar_year_text(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Use buy and hold instead",
            strategy_type="buy_and_hold",
            strategy_thesis="Backtest TSLA using an ATR 14 rule",
            asset_universe=["TSLA"],
            asset_class="equity",
            comparison_baseline="SPY",
            refinement_of="prior_atr_draft",
            extra_parameters={
                "raw_strategy_type": "buy_and_hold",
                "field_provenance": {"strategy_type": "explicit_user"},
            },
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="calendar year 2024",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.comparison_baseline == "SPY"
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert "pending_date_answer_interpreter_unavailable_repaired" in (
        result.decision.reason_codes
    )


def test_interpreter_unavailable_spanish_pending_strategy_applies_calendar_year_text(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="ok, mejor compra y mantén TSLA",
            strategy_type="buy_and_hold",
            strategy_thesis="Compra y mantén TSLA",
            asset_universe=["TSLA"],
            asset_class="equity",
            comparison_baseline="SPY",
            refinement_of="prior_atr_draft",
            extra_parameters={
                "raw_strategy_type": "buy_and_hold",
                "language": "es-419",
                "field_provenance": {"strategy_type": "explicit_user"},
            },
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="año calendario 2024",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.comparison_baseline == "SPY"
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert "pending_date_answer_interpreter_unavailable_repaired" in (
        result.decision.reason_codes
    )


def test_interpreter_unavailable_pending_simplification_uses_typed_buy_hold_choice(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Test TSLA with an ATR 14 trading rule",
            strategy_type="signal_strategy",
            strategy_thesis="Backtest TSLA using an ATR 14 rule.",
            asset_universe=["TSLA"],
            asset_class="equity",
            comparison_baseline="SPY",
            entry_logic="ATR 14 trading rule",
            refinement_of="unsupported_atr_rule",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="yeah compare w/ buy and hold pls",
            recent_thread_history=[],
            action_context={
                "type": "select_response_option",
                "label": "Compare with buy and hold",
                "payload": {
                    "replacement_values": {"strategy_type": "buy_and_hold"},
                },
            },
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "response_intent": {
                "kind": "unsupported_recovery",
                "semantic_needs": ["simplification_choice"],
                "options": [
                    {
                        "label": "Use a supported RSI threshold rule",
                        "replacement_values": {
                            "strategy_type": "indicator_threshold",
                        },
                    },
                    {
                        "label": "Compare with buy and hold",
                        "replacement_values": {
                            "strategy_type": "buy_and_hold",
                            "requested_field": "date_range",
                        },
                    },
                    {
                        "label": "Use a supported moving-average crossover",
                        "replacement_values": {
                            "strategy_type": "moving_average_crossover",
                        },
                    },
                ],
            },
        },
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.entry_logic is None
    assert strategy.strategy_thesis is None
    assert result.decision.missing_required_fields == ["date_range"]
    assert "pending_response_option_interpreter_unavailable_repaired" in (
        result.decision.reason_codes
    )


@pytest.mark.parametrize(
    ("message", "typed_selection", "expected_strategy_type", "expected_rule"),
    [
        (
            "sí, usa una regla RSI compatible",
            {"simplify_logic": "rsi_only"},
            "indicator_threshold",
            "rsi_threshold",
        ),
        (
            "usa el cruce de medias móviles",
            {
                "strategy_type": "signal_strategy",
                "rule_family": "moving_average_crossover",
            },
            "signal_strategy",
            "moving_average_crossover",
        ),
    ],
)
def test_interpreter_unavailable_pending_simplification_uses_typed_selection(
    monkeypatch,
    message: str,
    typed_selection: dict[str, object],
    expected_strategy_type: str,
    expected_rule: str,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Prueba TSLA con una regla ATR 14",
            strategy_type="signal_strategy",
            strategy_thesis="Prueba TSLA con una regla ATR 14.",
            asset_universe=["TSLA"],
            asset_class="equity",
            comparison_baseline="SPY",
            entry_logic="regla ATR 14",
            refinement_of="unsupported_atr_rule",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=message,
            recent_thread_history=[],
            action_context={
                "type": "select_response_option",
                "label": message,
                "payload": {
                    "replacement_values": typed_selection,
                },
            },
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "response_intent": {
                "kind": "unsupported_recovery",
                "semantic_needs": ["simplification_choice"],
                "options": [
                    {
                        "label": "Use a supported RSI threshold rule",
                        "replacement_values": {
                            "simplify_logic": "rsi_only",
                        },
                    },
                    {
                        "label": "Compare with buy and hold",
                        "replacement_values": {
                            "strategy_type": "buy_and_hold",
                            "requested_field": "date_range",
                        },
                    },
                    {
                        "label": "Use a supported moving-average crossover",
                        "replacement_values": {
                            "strategy_type": "signal_strategy",
                            "rule_family": "moving_average_crossover",
                        },
                    },
                ],
            },
        },
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "needs_clarification"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == expected_strategy_type
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.strategy_thesis is None
    if expected_rule == "rsi_threshold":
        assert strategy.extra_parameters["indicator_parameters"] == {
            "indicator": "rsi",
            "indicator_period": 14,
            "entry_threshold": 30.0,
            "exit_threshold": 55.0,
        }
    else:
        assert strategy.entry_rule["type"] == expected_rule
    assert result.decision.missing_required_fields == ["date_range"]
    assert "pending_response_option_interpreter_unavailable_repaired" in (
        result.decision.reason_codes
    )


def test_interpreter_unavailable_pending_simplification_uses_nested_intent_and_spanish_text(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    prior_date_range = {"start": "2024-01-01", "end": "2024-12-31"}
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Prueba TSLA con una regla ATR 14 durante 2024",
            strategy_type="signal_strategy",
            strategy_thesis="Prueba TSLA con una regla ATR 14.",
            asset_universe=["TSLA"],
            asset_class="equity",
            comparison_baseline="SPY",
            date_range=prior_date_range,
            capital_amount=1000,
            entry_logic="regla ATR 14",
            refinement_of="unsupported_atr_rule",
        )
    )
    response_intent = {
        "kind": "unsupported_recovery",
        "semantic_needs": ["simplification_choice"],
        "options": [
            {
                "label": "Use a supported RSI threshold rule",
                "replacement_values": {"simplify_logic": "rsi_only"},
            },
            {
                "label": "Compare with buy and hold",
                "replacement_values": {"strategy_type": "buy_and_hold"},
            },
            {
                "label": "Use a supported moving-average crossover",
                "replacement_values": {
                    "strategy_type": "signal_strategy",
                    "rule_family": "moving_average_crossover",
                },
            },
        ],
    }

    result = interpret_stage(
        state=RunState.new(
            current_user_message="usa el cruce de medias moviles compatible",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "pending_strategy": {"response_intent": response_intent},
        },
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "signal_strategy"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.date_range == prior_date_range
    assert strategy.capital_amount == 1000
    assert strategy.entry_rule == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    assert strategy.exit_rule["direction"] == "bearish"
    assert "pending_response_option_interpreter_unavailable_repaired" in (
        result.decision.reason_codes
    )


def test_pending_simplification_typed_choice_overrides_llm_atr_baggage(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    prior_date_range = {"start": "2024-01-01", "end": "2024-12-31"}
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Prueba TSLA con ATR 14 durante 2024 con $1,000",
            strategy_type=None,
            strategy_thesis="Prueba TSLA con ATR 14 durante 2024 con $1,000",
            asset_universe=["TSLA"],
            asset_class="equity",
            comparison_baseline="SPY",
            date_range=prior_date_range,
            capital_amount=1000,
            entry_logic="ATR 14",
            extra_parameters={
                "evidence_spans": {
                    "indicator": "ATR 14",
                    "date_range": "durante 2024",
                    "asset_universe": "TSLA",
                    "capital_amount": "$1,000",
                },
                "date_range_raw_text": "durante 2024",
            },
        )
    )
    response_intent = {
        "kind": "unsupported_recovery",
        "semantic_needs": ["simplification_choice"],
        "options": [
            {
                "label": "Use a supported RSI threshold rule",
                "replacement_values": {"simplify_logic": "rsi_only"},
            },
            {
                "label": "Compare with buy and hold",
                "replacement_values": {"strategy_type": "buy_and_hold"},
            },
            {
                "label": "Use a supported moving-average crossover",
                "replacement_values": {
                    "strategy_type": "signal_strategy",
                    "rule_family": "moving_average_crossover",
                },
            },
        ],
    }
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="strategy_drafting",
            task_relation="continue",
            requires_clarification=True,
            user_goal_summary="User chose buy and hold, but ATR baggage remained.",
            candidate_strategy_draft=StrategySummary(
                raw_user_phrasing="sí mejor comparar con comprar y mantener, porfa",
                strategy_thesis="sí mejor comparar con comprar y mantener, porfa",
                asset_universe=["TSLA"],
                asset_class="equity",
                comparison_baseline="SPY",
                date_range=prior_date_range,
                capital_amount=1000,
                entry_logic="ATR 14",
            ),
            assistant_response=(
                "Perfecto, compararemos TSLA contra comprar y mantener durante "
                "2024 con $1,000. ¿Quieres usar el ATR 14 como regla de entrada?"
            ),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="sí mejor comparar con comprar y mantener, porfa",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "pending_strategy": {"response_intent": response_intent},
        },
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_for_confirmation"
    assert "assistant_response" not in result.stage_patch
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.date_range == prior_date_range
    assert strategy.capital_amount == 1000
    assert strategy.entry_logic is None
    assert "pending_response_option_selected" in result.decision.reason_codes
    assert "pending_response_option_typed_selection_applied" in (
        result.decision.reason_codes
    )


def test_interpreter_unavailable_pending_date_does_not_apply_raw_date_text(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Compra y mantiene ETH.",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2024-01-01"},
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="marzo de 2024",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=None,
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision.reason_codes == ["llm_interpreter_unavailable"]
    assert result.decision.candidate_strategy_draft.date_range is None


def test_pending_date_answer_does_not_bypass_structured_interpreter_response(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY when it starts rising.",
            asset_universe=["SPY"],
            asset_class="equity",
            entry_logic="buy SPY when it starts rising",
        )
    )
    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="conversation_followup",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User answered with a date.",
            assistant_response="Please provide a complete strategy.",
            semantic_turn_act="educational_question",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="last month",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"] == "Please provide a complete strategy."


def test_pending_signal_rule_answer_uses_structured_interpreter(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY when it starts rising.",
            asset_universe=["SPY"],
            asset_class="equity",
            entry_logic="buy SPY when it starts rising",
            date_range="past month",
        )
    )

    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="strategy_drafting",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User defined the pending rising rule as an SMA crossover.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="signal_strategy",
                entry_logic="20-day SMA crosses above 50-day SMA",
                exit_logic="20-day SMA crosses below 50-day SMA",
                date_range="past month",
                entry_rule={
                    "type": "moving_average_crossover",
                    "fast_indicator": "sma",
                    "fast_period": 20,
                    "slow_indicator": "sma",
                    "slow_period": 50,
                    "direction": "bullish",
                },
                exit_rule={
                    "type": "moving_average_crossover",
                    "fast_indicator": "sma",
                    "fast_period": 20,
                    "slow_indicator": "sma",
                    "slow_period": 50,
                    "direction": "bearish",
                },
            ),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "use a 20-day SMA crossing above the 50-day SMA over the last month"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "entry_logic",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["SPY"]
    assert strategy.date_range == "past month"
    assert strategy.entry_rule["fast_period"] == 20
    assert strategy.entry_rule["slow_period"] == 50
    assert strategy.exit_rule["direction"] == "bearish"
    assert "typed_pending_signal_rule_answer_applied" not in result.decision.reason_codes


def test_pending_signal_rule_answer_preserves_context_when_llm_labels_new_idea(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    prior_date_range = {"start": "2024-01-01", "end": "2024-12-31"}
    entry_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    exit_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bearish",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Test TSLA with a moving-average crossover.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range=prior_date_range,
            entry_logic="Use a moving-average crossover.",
        )
    )

    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="User supplied the moving-average periods.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="signal_strategy",
                strategy_thesis="Use a 50/200 moving-average crossover.",
                asset_universe=["USA"],
                asset_class="equity",
                date_range={"start": "2025-12-13", "end": "2026-07-01"},
                entry_logic="50-day SMA crosses above 200-day SMA",
                exit_logic="50-day SMA crosses below 200-day SMA",
                entry_rule=entry_rule,
                exit_rule=exit_rule,
                extra_parameters={
                    "date_range_raw_text": "50 y 200 dias",
                    "field_provenance": {"asset_universe": "explicit_user"},
                    "evidence_spans": {
                        "asset_universe": "usa",
                        "date_range": "50 y 200 dias",
                        "entry_rule": "50 y 200 dias",
                    },
                },
            ),
            semantic_turn_act="new_idea",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="usa 50 y 200 dias",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "entry_rule",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "signal_strategy"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.date_range == prior_date_range
    assert strategy.entry_rule == entry_rule
    assert strategy.exit_rule == exit_rule


def test_complete_spanish_pending_crossover_answer_suppresses_stale_question(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    prior_date_range = {"start": "2024-01-01", "end": "2024-12-31"}
    entry_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    exit_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bearish",
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Test TSLA with a moving-average crossover.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range=prior_date_range,
            capital_amount=1000,
            entry_logic="Use a moving-average crossover.",
        )
    )

    interpreter = RecordingInterpreter(
        StructuredInterpretation(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=True,
            user_goal_summary="User supplied the moving-average periods.",
            candidate_strategy_draft=StrategySummary(
                strategy_type="signal_strategy",
                strategy_thesis="Use a 50/200 moving-average crossover.",
                asset_universe=["USA"],
                asset_class="equity",
                date_range={"start": "2025-12-13", "end": "2026-07-01"},
                capital_amount=1000,
                entry_logic="50-day SMA crosses above 200-day SMA",
                exit_logic="50-day SMA crosses below 200-day SMA",
                entry_rule=entry_rule,
                exit_rule=exit_rule,
                comparison_baseline="SPY",
                extra_parameters={
                    "date_range_raw_text": "50 y 200 dias",
                    "field_provenance": {"asset_universe": "explicit_user"},
                    "evidence_spans": {
                        "asset_universe": "usa",
                        "date_range": "50 y 200 dias",
                        "entry_rule": "50 y 200 dias",
                    },
                },
            ),
            assistant_response=(
                "¿Quieres entrar cuando la media de 50 días cruza ARRIBA "
                "de la media de 200 días, o ABAJO?"
            ),
            semantic_turn_act="answer_pending_need",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="usa 50 y 200 dias",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "entry_rule",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=interpreter,
    )

    assert len(interpreter.requests) == 1
    assert result.outcome == "ready_for_confirmation"
    assert "assistant_response" not in result.stage_patch
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "signal_strategy"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.date_range == prior_date_range
    assert strategy.capital_amount == 1000
    assert strategy.entry_rule == entry_rule
    assert strategy.exit_rule == exit_rule


def test_interpreter_unavailable_does_not_infer_missing_signal_rule_from_text(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY when it starts rising.",
            asset_universe=["SPY"],
            asset_class="equity",
            entry_logic="buy SPY when it starts rising",
            date_range="past month",
        )
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "use a 20-day SMA crossing above the 50-day SMA over the last month"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision.reason_codes == ["llm_interpreter_unavailable"]
    assert result.decision.candidate_strategy_draft.entry_rule is None
    assert "could not safely apply that change" in result.patch[
        "assistant_response"
    ].lower()
    assert "interpreter" not in result.patch["assistant_response"].lower()


def test_explicit_relative_date_reference_clears_llm_date_ambiguity(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="User wants to buy and hold Apple over the last month.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="last month",
        ),
        ambiguous_fields=[
            AmbiguousField(
                field_name="date_range",
                raw_value="last month",
                reason_code="calendar_or_trading_days",
            )
        ],
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Test buying Apple over the last month.",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.candidate_strategy_draft.date_range == "last month"
    assert result.decision.ambiguous_fields == []
    assert "semantic_date_constraint_preserved" in result.decision.reason_codes


def test_refinement_without_date_words_preserves_active_draft_period(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Apple.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="past year",
        )
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User changed the asset to Nvidia.",
        candidate_strategy_draft=StrategySummary(asset_universe=["NVDA"]),
        semantic_turn_act="refine_current_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Actually make it Nvidia.",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.candidate_strategy_draft.asset_universe == ["NVDA"]
    assert result.decision.candidate_strategy_draft.date_range == "past year"
    assert "spurious_date_range_removed" not in result.decision.reason_codes


def test_contextual_merge_clears_prior_signal_rules_when_family_changes_to_buy_hold(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    prior_entry_rule = {
        "type": "moving_average_crossover",
        "direction": "bullish",
        "fast_period": 50,
        "slow_period": 200,
        "fast_indicator": "sma",
        "slow_indicator": "sma",
    }
    prior_exit_rule = {
        "type": "moving_average_crossover",
        "direction": "bearish",
        "fast_period": 50,
        "slow_period": 200,
        "fast_indicator": "sma",
        "slow_indicator": "sma",
    }
    prior_rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "sma", "period": 50},
                    "operator": "cross_above",
                    "right": {"kind": "indicator", "key": "sma", "period": 200},
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "sma", "period": 50},
                    "operator": "cross_below",
                    "right": {"kind": "indicator", "key": "sma", "period": 200},
                }
            ]
        },
    }
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy Nvidia on a moving-average crossover.",
            asset_universe=["NVDA"],
            asset_class="equity",
            date_range="past year",
            entry_logic="50-day SMA crosses above 200-day SMA",
            exit_logic="50-day SMA crosses below 200-day SMA",
            entry_rule=prior_entry_rule,
            exit_rule=prior_exit_rule,
            rule_spec=prior_rule_spec,
            extra_parameters={
                "entry_rule": prior_entry_rule,
                "exit_rule": prior_exit_rule,
                "rule_spec": prior_rule_spec,
            },
        )
    )
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="refine",
        requires_clarification=False,
        user_goal_summary="User wants a fresh Tesla buy-and-hold test.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="Backtest buying and holding Tesla over the past year.",
            strategy_type=None,
            strategy_thesis="Buy and hold Tesla.",
            asset_universe=["TSLA"],
            asset_class="equity",
            date_range="past year",
            extra_parameters={"raw_strategy_type": "buy_and_hold"},
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message="Backtest buying and holding Tesla over the past year.",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={"requested_field": "refinement"},
    )

    strategy = result.decision.candidate_strategy_draft
    assert result.outcome == "ready_for_confirmation"
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.date_range == "past year"
    assert strategy.strategy_thesis == "Buy and hold Tesla."
    assert strategy.entry_logic is None
    assert strategy.exit_logic is None
    assert strategy.entry_rule is None
    assert strategy.exit_rule is None
    assert strategy.rule_spec is None
    assert "entry_rule" not in strategy.extra_parameters
    assert "exit_rule" not in strategy.extra_parameters
    assert "rule_spec" not in strategy.extra_parameters


def test_indicator_simplification_does_not_patch_when_llm_misroutes(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
        asset_universe=["NVDA"],
        asset_class="equity",
        entry_logic="50-day moving average crosses above the 200-day moving average",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User has a question.",
        assistant_response="I have a question...",
        semantic_turn_act="educational_question",
    )

    result, _ = run_interpret_with_llm(
        message="Simplify it to RSI.",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision.candidate_strategy_draft.strategy_type is None
    assert result.patch["assistant_response"] == "I have a question..."


def test_supported_indicator_patch_uses_structured_indicator_not_phrase_regex(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="signal_strategy",
        strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
        asset_universe=["NVDA"],
        asset_class="equity",
        date_range="past year",
        entry_logic="50-day moving average crosses above the 200-day moving average",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User chose a supported threshold indicator for the draft.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="indicator_threshold",
            extra_parameters={
                "indicator": "rsi",
                "indicator_parameters": {"indicator": "rsi"},
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message="Let's go with the simpler runnable option.",
        response=response,
        snapshot=snapshot,
    )

    strategy = result.decision.candidate_strategy_draft
    assert result.outcome == "ready_for_confirmation"
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.date_range == "past year"
    assert strategy.strategy_type == "indicator_threshold"
    assert strategy.extra_parameters["indicator"] == "rsi"
    assert strategy.entry_logic == "Buy when RSI(14) drops to 30 or below"
    assert strategy.exit_logic == "Sell when RSI(14) rises to 55 or above"
    assert "supported_indicator_simplification_applied" in result.decision.reason_codes


def test_supported_indicator_patch_accepts_structured_template_alias(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_thesis="Test Apple when news sentiment turns positive.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User chose a supported RSI simplification.",
        candidate_strategy_draft=StrategySummary(
            raw_user_phrasing="Simplify the active draft to a supported indicator.",
            strategy_type="indicator_threshold",
            extra_parameters={"raw_strategy_type": "rsi_mean_reversion"},
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message="Let's do the runnable version.",
        response=response,
        snapshot=snapshot,
    )

    strategy = result.decision.candidate_strategy_draft
    assert result.outcome == "ready_for_confirmation"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.date_range == "past year"
    assert strategy.strategy_type == "indicator_threshold"
    assert strategy.extra_parameters["indicator"] == "rsi"
    assert strategy.entry_logic == "Buy when RSI(14) drops to 30 or below"
    assert strategy.exit_logic == "Sell when RSI(14) rises to 55 or above"
    assert "supported_indicator_simplification_applied" in result.decision.reason_codes


def test_supported_indicator_simplification_preserves_user_threshold_overrides(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    pending = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Buy Tesla after big drops.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range="past 3 months",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User supplied RSI thresholds.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="indicator_threshold",
            strategy_thesis="Use RSI for the active Tesla draft.",
            extra_parameters={
                "indicator": "rsi",
                "indicator_parameters": {
                    "indicator": "rsi",
                    "entry_threshold": 20,
                    "exit_threshold": 60,
                },
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result, _ = run_interpret_with_llm(
        message=(
            "Use RSI: enter at 20 or lower, exit at 60 or higher, "
            "over the last 3 months."
        ),
        response=response,
        snapshot=snapshot,
    )

    strategy = result.decision.candidate_strategy_draft
    assert result.outcome == "ready_for_confirmation"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.entry_logic == "Buy when RSI(14) drops to 20 or below"
    assert strategy.exit_logic == "Sell when RSI(14) rises to 60 or above"
    assert strategy.extra_parameters["indicator_parameters"]["entry_threshold"] == 20.0
    assert strategy.extra_parameters["indicator_parameters"]["exit_threshold"] == 60.0
    assert "supported_indicator_simplification_applied" in result.decision.reason_codes


def test_active_artifact_rule_answer_repairs_and_preserves_prior_asset(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.llm_interpreter import (
        FocusedStrategyExtraction,
        LLMInterpretationResponse,
        LLMStrategyDraft,
        OpenRouterStructuredInterpreter,
    )
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda **_: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        calls.append(schema_model.__name__)
        if len(calls) == 1:
            return LLMInterpretationResponse(
                intent="strategy_drafting",
                task_relation="new_task",
                requires_clarification=True,
                user_goal_summary="User supplied RSI thresholds.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing=(
                        "technical thing like RSI, buy when it gets to 20 or "
                        "lower, sell when 60 or higher, past 3 months"
                    ),
                    strategy_thesis=(
                        "RSI mean reversion: buy when RSI <= 20, sell when "
                        "RSI >= 60, over the last 3 months."
                    ),
                    date_range="last 3 months",
                ),
                assistant_response=(
                    "Strategy drafted as RSI mean reversion. Asset symbol is missing."
                ),
                semantic_turn_act="new_idea",
            )
        if schema_model.__name__ == "FocusedStrategyExtraction":
            return FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary="User supplied RSI thresholds.",
                raw_user_phrasing=(
                    "technical thing like RSI, buy when it gets to 20 or "
                    "lower, sell when 60 or higher, past 3 months"
                ),
                strategy_type="indicator_threshold",
                strategy_thesis="Use RSI thresholds for the active draft.",
                date_range="last 3 months",
                indicator="rsi",
                entry_threshold=20,
                exit_threshold=60,
            )
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="User supplied RSI thresholds.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "technical thing like RSI, buy when it gets to 20 or "
                    "lower, sell when 60 or higher, past 3 months"
                ),
                strategy_type="indicator_threshold",
                strategy_thesis="Use RSI thresholds for the active draft.",
                date_range="last 3 months",
                indicator="rsi",
                entry_threshold=20,
                exit_threshold=60,
            ),
            semantic_turn_act="new_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    pending = StrategySummary(
        strategy_type=None,
        strategy_thesis="User wants to buy Tesla after big drops.",
        asset_universe=["TSLA"],
        asset_class="equity",
        raw_user_phrasing="What if I bought Tesla after big drops?",
    )
    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "technical thing like RSI, buy when it gets to 20 or lower, "
                "sell when 60 or higher, past 3 months"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract()
        ),
    )

    strategy = result.decision.candidate_strategy_draft
    assert calls[:2] == ["LLMInterpretationResponse", "FocusedStrategyExtraction"]
    assert set(calls[2:]).issubset(
        {
            "LLMInterpretationResponse",
            "StatedRunFieldFidelityAudit",
            "StatedStartingCapitalAudit",
        }
    )
    assert result.outcome == "ready_for_confirmation"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.date_range == "last 3 months"
    assert strategy.strategy_type == "indicator_threshold"
    assert strategy.entry_logic == "Buy when RSI(14) drops to 20 or below"
    assert strategy.exit_logic == "Sell when RSI(14) rises to 60 or above"


def test_active_artifact_indicator_token_asset_candidate_preserves_prior_asset(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="User wants to test Tesla.",
        asset_universe=["TSLA"],
        asset_class="equity",
        raw_user_phrasing="What if I bought Tesla?",
    )
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Add MACD as the rule for the past 3 months.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={},
        structured_interpreter=RecordingInterpreter(
            StructuredInterpretation(
                intent="strategy_drafting",
                task_relation="new_task",
                requires_clarification=False,
                user_goal_summary="User wants to add a MACD rule.",
                candidate_strategy_draft=StrategySummary(
                    raw_user_phrasing="Add MACD as the rule for the past 3 months.",
                    strategy_type="indicator_threshold",
                    strategy_thesis="Use MACD as an indicator rule.",
                    asset_universe=["MACD"],
                    asset_class="equity",
                    date_range="last 3 months",
                    extra_parameters={
                        "indicator": "macd",
                        "indicator_parameters": {"indicator": "macd"},
                    },
                ),
                semantic_turn_act="new_idea",
            )
        ),
    )

    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["TSLA"]


def test_result_refinement_reply_forks_latest_result_into_new_draft(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.llm_interpreter import (
        FocusedStrategyExtraction,
        LLMInterpretationResponse,
        LLMStrategyDraft,
        OpenRouterStructuredInterpreter,
    )
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda **_: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        calls.append(schema_model.__name__)
        if len(calls) == 1:
            return LLMInterpretationResponse(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary=(
                    "User wants to refine the latest result into recurring buys."
                ),
                assistant_response=(
                    "I've updated the strategy to use biweekly recurring buys."
                ),
                semantic_turn_act="educational_question",
            )
        if schema_model.__name__ == "FocusedStrategyExtraction":
            return FocusedStrategyExtraction(
                is_testable_strategy=True,
                requires_clarification=False,
                user_goal_summary=(
                    "Refine the latest AAPL result into recurring $500 buys."
                ),
                raw_user_phrasing=(
                    "i want to do recurrent biweekly buys of 500 bucks instead"
                ),
                strategy_type="dca_accumulation",
                strategy_thesis="Buy AAPL with recurring $500 contributions.",
                cadence="biweekly",
                capital_amount=500,
                recurring_contribution=500,
            )
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="refine",
            requires_clarification=False,
            user_goal_summary=(
                "Refine the latest AAPL result into recurring $500 buys."
            ),
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "i want to do recurrent biweekly buys of 500 bucks instead"
                ),
                strategy_type="dca_accumulation",
                strategy_thesis="Buy AAPL with recurring $500 contributions.",
                cadence="biweekly",
                capital_amount=500,
                field_provenance={
                    "capital_amount": "recurring_contribution",
                    "cadence": "explicit_user",
                },
            ),
            semantic_turn_act="refine_current_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Apple.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range="past year",
        raw_user_phrasing="Backtest buy and hold Apple over the past year.",
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "i want to do recurrent biweekly buys of 500 bucks instead"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", expertise_level="advanced"),
        latest_task_snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "requested_field": "refinement",
            "source_result_run_id": "run_123",
        },
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract()
        ),
    )

    strategy = result.decision.candidate_strategy_draft
    assert calls[:2] == ["LLMInterpretationResponse", "LLMInterpretationResponse"]
    assert set(calls[2:]).issubset(
        {
            "FocusedStrategyExtraction",
            "FocusedDateWindowExtraction",
            "StatedRunFieldFidelityAudit",
            "StatedStartingCapitalAudit",
        }
    )
    assert result.outcome == "ready_for_confirmation"
    assert result.stage_patch.get("assistant_response") is None
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.date_range == "past year"
    assert strategy.cadence == "biweekly"
    assert strategy.capital_amount == 500


def test_indicator_simplification_does_not_regex_parse_when_interpreter_unavailable(
    monkeypatch,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="signal_strategy",
            strategy_thesis="Buy Nvidia on a 50/200 moving-average crossover.",
            asset_universe=["NVDA"],
            asset_class="equity",
            entry_logic="50-day moving average crosses above the 200-day moving average",
        )
    )
    interpreter = RecordingInterpreter(None)
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Simplify it to RSI.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        structured_interpreter=interpreter,
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision.candidate_strategy_draft.asset_universe == []
    assert result.decision.reason_codes == ["llm_interpreter_unavailable"]
    assert "could not safely apply that change" in result.patch[
        "assistant_response"
    ].lower()
    assert "interpreter" not in result.patch["assistant_response"].lower()
    assert "draft" not in result.patch["assistant_response"].lower()


def test_interpreter_unavailable_reads_visible_confirmation_assumptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable_active_confirmation_recovery(**kwargs: Any) -> None:
        del kwargs
        return None

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret."
        "compose_active_confirmation_interpreter_recovery",
        unavailable_active_confirmation_recovery,
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Nvidia.",
            asset_universe=["NVDA"],
            asset_class="equity",
            date_range="past 6 months",
        ),
        active_confirmation_reference=ArtifactReference(
            artifact_kind="confirmation",
            artifact_id="confirmation-1",
            artifact_status="active",
            metadata={
                "confirmation_card": {
                    "assumptions": [
                        "$1,000 starting capital",
                        "1D bars",
                        "No fees",
                        "No slippage",
                        "Benchmark: SPY",
                    ]
                }
            },
        ),
    )
    result = interpret_stage(
        state=RunState.new(
            current_user_message="What assumptions are you using?",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    assert "$1,000 starting capital" in answer
    assert "Benchmark: SPY" in answer
    assert "visible confirmation" in answer
    assert "start the simulation" in answer
    assert "card controls" in answer


def test_interpreter_unavailable_active_confirmation_plans_benchmark_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime.stages import interpret as interpret_module

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "2026-06-19"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
    )

    async def plan_stub(**kwargs: Any):
        assert kwargs["current_user_message"] == (
            "compare it to QQQ, keep the same assets and dates"
        )
        return artifact_edit_planner.ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible benchmark.",
            comparison_baseline="QQQ",
            confidence=0.93,
        )

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        plan_stub,
    )
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "compare it to QQQ, keep the same assets and dates"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=task_snapshot_with_confirmation(pending),
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "MSFT", "TSLA"]
    assert strategy.comparison_baseline == "QQQ"
    assert strategy.date_range == {"start": "2023-01-01", "end": "2026-06-19"}
    assert strategy.capital_amount == 100000


def test_interpreter_unavailable_active_rsi_confirmation_plans_threshold_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime.stages import interpret as interpret_module

    pending = StrategySummary(
        strategy_type="indicator_threshold",
        strategy_thesis="Backtest TSLA with an RSI threshold rule.",
        asset_universe=["TSLA"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=1000,
        timeframe="1D",
        comparison_baseline="SPY",
        entry_logic="Buy when RSI(14) drops to 30 or below",
        exit_logic="Sell when RSI(14) rises to 70 or above",
        extra_parameters={
            "indicator": "rsi",
            "indicator_parameters": {
                "indicator": "rsi",
                "indicator_period": 14,
                "entry_threshold": 30,
                "exit_threshold": 70,
            },
        },
    )

    async def plan_stub(**kwargs: Any):
        assert kwargs["current_user_message"] == (
            "baja la entrada RSI a 20 y la salida a 60, porfa"
        )
        return artifact_edit_planner.ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible RSI thresholds.",
            operations=[
                EditOperation(
                    op="set",
                    target="indicator_entry_threshold",
                    number=20,
                ),
                EditOperation(
                    op="set",
                    target="indicator_exit_threshold",
                    number=60,
                ),
            ],
            confidence=0.93,
        )

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        plan_stub,
    )
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "baja la entrada RSI a 20 y la salida a 60, porfa"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=task_snapshot_with_confirmation(pending),
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "indicator_threshold"
    assert strategy.asset_universe == ["TSLA"]
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert strategy.extra_parameters["indicator_parameters"]["entry_threshold"] == 20
    assert strategy.extra_parameters["indicator_parameters"]["exit_threshold"] == 60
    assert "artifact_assumption_edit_planned" in result.decision.reason_codes


def test_interpreter_unavailable_planner_ignores_same_asset_universe_without_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime.stages import interpret as interpret_module

    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "2026-06-19"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
    )

    async def plan_stub(**kwargs: Any):
        assert kwargs["current_user_message"] == (
            "compare it to QQQ, same assets and capital"
        )
        return artifact_edit_planner.ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible benchmark.",
            asset_universe=["TSLA", "AAPL", "MSFT"],
            comparison_baseline="QQQ",
            confidence=0.93,
        )

    monkeypatch.setattr(
        interpret_module,
        "plan_artifact_assumption_edit",
        plan_stub,
    )
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="compare it to QQQ, same assets and capital",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=task_snapshot_with_confirmation(pending),
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL", "MSFT", "TSLA"]
    assert strategy.comparison_baseline == "QQQ"
    assert strategy.date_range == {"start": "2023-01-01", "end": "2026-06-19"}
    assert strategy.capital_amount == 100000
    assert "artifact_assumption_edit_planned" in result.decision.reason_codes


def test_interpreter_unavailable_active_confirmation_can_answer_side_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_compose_active_confirmation_interpreter_recovery(
        **kwargs: Any,
    ) -> str:
        captured.update(kwargs)
        return (
            "Dollar cost averaging spreads recurring purchases over time while "
            "the current confirmation stays ready."
        )

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret."
        "compose_active_confirmation_interpreter_recovery",
        fake_compose_active_confirmation_interpreter_recovery,
        raising=False,
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="dca_accumulation",
            strategy_thesis="Buy ETH every two weeks.",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2022-01-01", "end": "2023-12-31"},
            capital_amount=125,
            cadence="biweekly",
        ),
        active_confirmation_reference=ArtifactReference(
            artifact_kind="confirmation",
            artifact_id="confirmation-1",
            artifact_status="active",
            metadata={
                "confirmation_card": {
                    "assumptions": [
                        "$125 recurring contribution",
                        "1D bars",
                        "No fees",
                        "No slippage",
                        "Benchmark: BTC",
                    ]
                }
            },
        ),
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="explain what dollar cost averaging means",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    assert "spreads recurring purchases" in answer
    assert "$125 recurring contribution" not in answer
    assert "Benchmark: BTC" not in answer
    assert captured["current_user_message"] == "explain what dollar cost averaging means"
    assert "Benchmark: BTC" in captured["assumptions_response"]


def test_interpreter_unavailable_active_confirmation_passes_user_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_compose_active_confirmation_interpreter_recovery(
        **kwargs: Any,
    ) -> str:
        captured.update(kwargs)
        return "Claro, la confirmación sigue lista."

    monkeypatch.setattr(
        "argus.agent_runtime.stages.interpret."
        "compose_active_confirmation_interpreter_recovery",
        fake_compose_active_confirmation_interpreter_recovery,
        raising=False,
    )
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Comprar y mantener ETH.",
            asset_universe=["ETH"],
            asset_class="crypto",
            date_range={"start": "2025-10-14", "end": "2026-06-14"},
            capital_amount=100000,
        ),
        active_confirmation_reference=ArtifactReference(
            artifact_kind="confirmation",
            artifact_id="confirmation-1",
            artifact_status="active",
        ),
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="que significa esto?",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_to_respond"
    assert captured["language"] == "es-419"


def test_interpreter_unavailable_during_assumption_edit_does_not_answer_stale_assumptions() -> None:
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Nvidia.",
            asset_universe=["NVDA"],
            asset_class="equity",
            date_range="past 6 months",
        ),
        active_confirmation_reference=ArtifactReference(
            artifact_kind="confirmation",
            artifact_id="confirmation-1",
            artifact_status="active",
            metadata={
                "confirmation_card": {
                    "assumptions": [
                        "$1,000 starting capital",
                        "1D bars",
                        "No fees",
                        "No slippage",
                        "Benchmark: SPY",
                    ]
                }
            },
        ),
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="Use $5,000 starting capital",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "assumption",
            "last_stage_outcome": "await_user_reply",
        },
        structured_interpreter=RecordingInterpreter(None),
    )

    assert result.outcome == "ready_to_respond"
    answer = result.patch["assistant_response"]
    assert "could not safely apply that assumption change" in answer
    assert "$1,000 starting capital" not in answer
    assert "left the current idea unchanged" in answer
    assert "interpreter" not in answer.lower()


def test_retry_failed_action_rebuilds_confirmation_instead_of_auto_running() -> None:
    launch_payload = {
        "strategy_type": "buy_and_hold",
        "symbol": "MSFT",
        "symbols": ["MSFT"],
        "timeframe": "1D",
        "date_range": {"start": "2025-05-13", "end": "2026-05-13"},
        "sizing_mode": "capital_amount",
        "capital_amount": 1000,
        "benchmark_symbol": "SPY",
    }
    snapshot = TaskSnapshot(
        latest_failed_action_reference=ArtifactReference(
            artifact_kind="failed_action",
            artifact_id="failed-action-1",
            artifact_status="failed",
            metadata={
                "action_type": "run_backtest",
                "launch_payload": launch_payload,
                "failure_classification": "upstream_dependency_error",
                "error": "market_data_unavailable",
                "retryable": True,
            },
        )
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asks to retry the failed run.",
        semantic_turn_act="retry_failed_action",
    )

    result, _ = run_interpret_with_llm(
        message="Can you try again?",
        response=response,
        snapshot=snapshot,
    )

    assert result.outcome == "ready_for_confirmation"
    assert "confirmation_payload" not in result.patch
    assert result.patch["candidate_strategy_draft"].asset_universe == ["MSFT"]
    assert result.patch["candidate_strategy_draft"].date_range == {
        "start": "2025-05-13",
        "end": "2026-05-13",
    }
    assert "assistant_response" not in result.patch
    assert result.patch["response_intent"] == {
        "kind": "artifact_action_recovery",
        "facts": {
            "action_type": "retry_failed_action",
            "status": "rebuilt_confirmation",
            "requested_failed_action_id": None,
            "latest_failed_action_id": "failed-action-1",
            "user_safe_message": "market_data_unavailable",
            "language": "en",
        },
    }


def test_pending_date_answer_is_not_treated_as_failed_action_retry(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub("TSLA", "equity", raw_symbol=symbol),
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold Tesla.",
        asset_universe=["TSLA"],
        asset_class="equity",
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User answered the missing date range.",
        semantic_turn_act="retry_failed_action",
        candidate_strategy_draft=StrategySummary(
            date_range={"start": "2025-05-19", "end": "2026-05-19"},
        ),
    )

    result, _ = run_interpret_with_llm(
        message="test the past year",
        response=response,
        snapshot=snapshot,
        selected_thread_metadata={
            "requested_field": "date_range",
            "last_stage_outcome": "await_user_reply",
        },
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.patch["semantic_turn_act"] == "answer_pending_need"
    assert "retry_route_repaired_to_pending_need" in result.patch["reason_codes"]
    draft = result.patch["candidate_strategy_draft"]
    assert draft["asset_universe"] == ["TSLA"]
    assert draft["date_range"] == {"start": "2025-05-19", "end": "2026-05-19"}
    assert "assistant_response" not in result.stage_patch


def test_interpret_canonicalizes_symbols_through_market_data(monkeypatch) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub("TSLA", "equity", raw_symbol=symbol),
    )
    response = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="User supplied a buy-and-hold strategy.",
        candidate_strategy_draft=StrategySummary(
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Tesla.",
            asset_universe=["Tesla"],
            date_range="past year",
        ),
        semantic_turn_act="new_idea",
    )

    result, _ = run_interpret_with_llm(
        message="Buy and hold Tesla over the past year",
        response=response,
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision.candidate_strategy_draft.asset_universe == ["TSLA"]
    assert result.decision.candidate_strategy_draft.asset_class == "equity"


def test_interpret_applies_llm_response_profile_overrides() -> None:
    response = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary="User asked for a concise explanation.",
        assistant_response="Here is the short version.",
        response_profile_overrides=ResponseProfileOverrides(verbosity="low"),
        semantic_turn_act="educational_question",
    )

    result, _ = run_interpret_with_llm(
        message="Explain this briefly.",
        response=response,
        user=UserState(user_id="u1", response_verbosity="high"),
    )

    assert result.decision.effective_response_profile.effective_verbosity == "low"
    assert result.decision.user_preference_overridden_for_turn is True


def test_interpret_stage_has_no_regex_nlu_imports() -> None:
    source = Path("src/argus/agent_runtime/stages/interpret.py").read_text()
    forbidden = [
        "extract_signals(",
        "extract_strategy_fields(",
        "resolve_response_profile_overrides(",
        "resolve_intent(",
        "resolve_task_relation(",
        "resolve_gray_case_arbitration(",
        "_direct_conversational_response(",
        "_is_educational_turn(",
        "_is_approval_message(",
    ]
    for token in forbidden:
        assert token not in source


def test_symbol_alias_dictionaries_are_deleted() -> None:
    paths = [Path("src/argus/agent_runtime/stages/interpret.py")]
    source = "\n".join(path.read_text() for path in paths)
    for token in ["SYMBOL_ALIASES", "COMMON_NAMES", "NON_SYMBOLS"]:
        assert token not in source
