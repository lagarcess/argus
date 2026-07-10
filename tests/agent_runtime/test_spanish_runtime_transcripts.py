from __future__ import annotations

from dataclasses import dataclass

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.llm_interpreter import (
    LatestResultRoutingAudit,
    LLMInterpretationResponse,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
)
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.stages.interpret import interpret_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from langgraph.checkpoint.memory import MemorySaver


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


def _test_model_candidates(**_: object) -> list[str]:
    return ["test-model"]


def _ethereum_asset_stub(symbol: str) -> ResolvedAssetStub:
    normalized = str(symbol).strip().casefold()
    if normalized not in {"eth", "ethereum"}:
        raise ValueError(symbol)
    return ResolvedAssetStub("ETH", "crypto", name="Ethereum", raw_symbol=symbol)


class RecordingSpanishClarifier:
    def __init__(self, question: str) -> None:
        self.question = question
        self.requests = []

    async def ainvoke(self, request):
        self.requests.append(request)
        return self.question


def _spanish_confirmation_snapshot(strategy: StrategySummary) -> TaskSnapshot:
    payload = {
        "strategy": strategy.model_dump(mode="python"),
        "optional_parameters": {},
        "launch_payload": {
            "strategy_type": strategy.strategy_type,
            "symbol": strategy.asset_universe[0],
            "symbols": list(strategy.asset_universe),
            "timeframe": "1D",
            "date_range": strategy.date_range,
            "sizing_mode": "capital_amount",
            "capital_amount": strategy.capital_amount or 100000,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "BTC",
            "language": "es-419",
        },
        "validation": {"status": "ready_to_run", "executable": True},
    }
    reference = ArtifactReference(
        artifact_kind="confirmation",
        artifact_id="confirmation-es",
        artifact_status="active",
        metadata={"confirmation_payload": payload},
    )
    return TaskSnapshot(
        pending_strategy_summary=strategy,
        active_confirmation_reference=reference,
        artifact_references=[reference],
    )


def test_spanish_dca_runtime_canonicalizes_localized_llm_cadence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary=(
                "El usuario quiere probar compras recurrentes de ETH."
            ),
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "Compra 250 dólares de ETH semanalmente durante 2024"
                ),
                language="es-419",
                strategy_type="dca_accumulation",
                strategy_thesis="Comprar ETH de forma recurrente.",
                asset_universe=["ETH"],
                date_range={"start": "2024-01-01", "end": "2024-12-31"},
                capital_amount=250,
                recurring_contribution=250,
                cadence="weekly",
                field_provenance={
                    "capital_amount": "recurring_contribution",
                    "recurring_contribution": "recurring_contribution",
                    "cadence": "explicit_user",
                },
                evidence_spans={
                    "asset_universe": "ETH",
                    "capital_amount": "250 dólares",
                    "cadence": "semanalmente",
                    "date_range": "durante 2024",
                },
            ),
            semantic_turn_act="new_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Compra 250 dólares de ETH semanalmente durante 2024"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.asset_universe == ["ETH"]
    assert strategy.asset_class == "crypto"
    assert strategy.capital_amount == 250
    assert strategy.cadence == "weekly"
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert strategy.extra_parameters["language"] == "es-419"
    assert strategy.extra_parameters["evidence_spans"]["cadence"] == "semanalmente"


@pytest.mark.asyncio
async def test_spanish_dca_missing_amount_clarifies_through_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        _ethereum_asset_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        _ethereum_asset_stub,
    )
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=True,
            user_goal_summary=(
                "El usuario quiere comprar ETH semanalmente desde 2022."
            ),
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="Compra Ethereum semanalmente desde 2022 hasta hoy",
                language="es-419",
                strategy_type="dca_accumulation",
                strategy_thesis="Comprar ETH de forma recurrente.",
                asset_universe=["Ethereum"],
                asset_class="crypto",
                cadence="weekly",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="since",
                    start="2022-01-01",
                    end="today",
                    evidence="desde 2022 hasta hoy",
                ),
                evidence_spans={
                    "asset_universe": "Ethereum",
                    "cadence": "semanalmente",
                    "date_range_intent": "desde 2022 hasta hoy",
                },
            ),
            missing_required_fields=["capital_amount"],
            semantic_turn_act="new_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    clarifier = RecordingSpanishClarifier(
        "¿Cuánto quieres comprar en cada compra recurrente?"
    )
    workflow = build_workflow(
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
        clarification_generator=clarifier,
        checkpointer=MemorySaver(),
    )

    result = await run_agent_turn(
        workflow=workflow,
        user=UserState(user_id="u1", language_preference="es-419"),
        thread_id="spanish-dca-missing-amount",
        message="Compra Ethereum semanalmente desde 2022 hasta hoy",
    )

    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="since",
            start="2022-01-01",
            end="today",
        )
    )

    assert expected_range is not None
    assert result["stage_outcome"] == "await_user_reply"
    assert result["assistant_prompt"] == (
        "¿Cuánto quieres comprar en cada compra recurrente?"
    )
    assert clarifier.requests
    assert clarifier.requests[0].language == "es-419"
    assert clarifier.requests[0].response_intent["semantic_needs"] == [
        "sizing_amount"
    ]
    pending = result["pending_strategy"]
    assert pending["missing_required_fields"] == ["capital_amount"]
    strategy = pending["strategy"]
    assert strategy["strategy_type"] == "dca_accumulation"
    assert strategy["asset_universe"] == ["ETH"]
    assert strategy["asset_class"] == "crypto"
    assert strategy["cadence"] == "weekly"
    assert strategy["date_range"] == expected_range.payload
    assert "confirmation_payload" not in result


def test_spanish_buy_and_hold_runtime_uses_bounded_date_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="El usuario quiere probar ETH con buy and hold.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 "
                    "con 100000"
                ),
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Comprar y mantener ETH.",
                asset_universe=["ETH"],
                date_range={"start": "2023-01-01", "end": "2023-12-31"},
                date_range_raw_text="enero de 2024 hasta marzo de 2024",
                capital_amount=100000,
                evidence_spans={
                    "strategy_type": "Compra y mantén",
                    "asset_universe": "ETH",
                    "date_range": "enero de 2024 hasta marzo de 2024",
                    "capital_amount": "100000",
                },
            ),
            semantic_turn_act="new_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Compra y mantén ETH de enero de 2024 hasta marzo de 2024 "
                "con 100000"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.asset_universe == ["ETH"]
    assert strategy.asset_class == "crypto"
    assert strategy.capital_amount == 100000
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-03-31"}
    assert (
        "current_message_run_field_contract_repair" in result.decision.reason_codes
        or "stated_run_field_fidelity_audit" in result.decision.reason_codes
    )


def test_spanish_mixed_asset_request_stays_blocked_by_guardrails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.upper()
        if normalized in {"TESLA", "TSLA"}:
            return ResolvedAssetStub("TSLA", "equity", name="Tesla")
        return ResolvedAssetStub(normalized, "crypto")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="El usuario quiere probar BTC y Tesla juntos.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="Prueba BTC y Tesla juntos el año pasado",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Comprar y mantener BTC y Tesla juntos.",
                asset_universe=["BTC", "Tesla"],
                date_range={"start": "2025-01-01", "end": "2025-12-31"},
                evidence_spans={
                    "asset_universe": "BTC y Tesla",
                    "date_range": "el año pasado",
                },
            ),
            semantic_turn_act="new_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="Prueba BTC y Tesla juntos el año pasado",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["BTC", "TSLA"]
    assert strategy.asset_class == "mixed"
    assert any(
        constraint.category == "unsupported_asset_mix"
        for constraint in result.decision.unsupported_constraints
    )


def test_spanish_approval_routes_by_llm_semantics_not_text_matching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    pending = StrategySummary(
        raw_user_phrasing="Compra y mantén ETH este año con 100000.",
        strategy_type="buy_and_hold",
        strategy_thesis="Comprar y mantener ETH.",
        asset_universe=["ETH"],
        asset_class="crypto",
        date_range={"start": "2026-01-01", "end": "2026-06-11"},
        capital_amount=100000,
    )
    snapshot = _spanish_confirmation_snapshot(pending)
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="El usuario aprobó la simulación pendiente.",
            semantic_turn_act="approval",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="sí, ejecútalo",
            recent_thread_history=[
                {
                    "role": "user",
                    "content": "Compra y mantén ETH este año con 100000.",
                },
                {
                    "role": "assistant",
                    "content": "Confirma esta simulación en la tarjeta.",
                },
            ],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision is not None
    assert result.decision.semantic_turn_act == "approval"
    assert result.decision.candidate_strategy_draft.asset_universe == ["ETH"]
    assert "confirmation_payload" not in result.patch
    assert result.patch["recovery"]["code"] == "confirmation_action_guidance"
    assert result.patch["recovery"]["retryable"] is False


def test_spanish_result_followup_anchors_to_latest_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages import interpret_actions as interpret_actions_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="results_explanation",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="El usuario quiere entender los supuestos.",
                semantic_turn_act="result_followup",
                result_followup_focus="assumptions",
            )
        if schema_model.__name__ == "LatestResultRoutingAudit":
            return LatestResultRoutingAudit(
                targets_latest_result=True,
                focus="assumptions",
                confidence=0.95,
            )
        return None

    followup_calls: list[dict[str, object]] = []

    async def compose_followup_stub(**kwargs):
        followup_calls.append(kwargs)
        return "El resultado usa capital inicial, datos diarios y sin comisiones."

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        interpret_module,
        "compose_result_followup_response",
        compose_followup_stub,
    )
    monkeypatch.setattr(
        interpret_actions_module,
        "compose_result_followup_response",
        compose_followup_stub,
    )
    result_reference = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-eth-2026",
        artifact_status="completed",
        metadata={
            "symbols": ["ETH"],
            "benchmark_symbol": "BTC",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 13.1,
                        "benchmark_return_pct": 8.0,
                        "delta_vs_benchmark_pct": 5.1,
                    },
                    "risk": {"max_drawdown_pct": -20.8},
                }
            },
            "config_snapshot": {
                "template": "buy_and_hold",
                "symbols": ["ETH"],
                "date_range": {"start": "2026-01-01", "end": "2026-06-11"},
                "starting_capital": 100000,
            },
        },
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="explícame los supuestos del resultado",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=TaskSnapshot(
            latest_backtest_result_reference=result_reference,
            artifact_references=[result_reference],
        ),
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    assert result.outcome == "ready_to_respond"
    assert result.decision is not None
    assert result.decision.semantic_turn_act == "result_followup"
    assert result.decision.result_followup_focus == "assumptions"
    assert result.decision.artifact_target == "latest_result"
    assert followup_calls[0]["focus"] == "assumptions"
    assert followup_calls[0]["user_message"] == "explícame los supuestos del resultado"
    assert "capital inicial" in result.patch["assistant_response"]


def test_spanish_benchmark_comparison_keeps_benchmark_out_of_asset_universe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.upper()
        if normalized in {"APPLE", "AAPL"}:
            return ResolvedAssetStub("AAPL", "equity", name="Apple")
        if normalized == "QQQ":
            return ResolvedAssetStub("QQQ", "equity", name="Invesco QQQ Trust")
        return ResolvedAssetStub(normalized, "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="El usuario quiere probar Apple contra QQQ.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="Haz un backtest de Apple contra QQQ en 2023",
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Comprar y mantener Apple comparado con QQQ.",
                asset_universe=["Apple"],
                asset_class="equity",
                comparison_baseline="QQQ",
                date_range={"start": "2023-01-01", "end": "2023-12-31"},
                field_provenance={"comparison_baseline": "explicit_user"},
                evidence_spans={
                    "asset_universe": "Apple",
                    "comparison_baseline": "QQQ",
                    "date_range": "en 2023",
                },
            ),
            semantic_turn_act="new_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="Haz un backtest de Apple contra QQQ en 2023",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.asset_class == "equity"
    assert strategy.comparison_baseline == "QQQ"
    assert "QQQ" not in strategy.asset_universe


def test_spanish_rsi_threshold_relative_window_reaches_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity", name=symbol),
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity", name=symbol),
    )
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="El usuario quiere probar GOOG con RSI.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "Prueba GOOG con RSI: compra debajo de 30 y vende arriba "
                    "de 60 en los ultimos 6 meses"
                ),
                language="es-419",
                strategy_type="indicator_threshold",
                strategy_thesis="Comprar GOOG cuando RSI baja y salir cuando sube.",
                asset_universe=["GOOG"],
                asset_class="equity",
                indicator="rsi",
                indicator_period=14,
                entry_threshold=30,
                exit_threshold=60,
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=6,
                    unit="month",
                    anchor="today",
                    evidence="ultimos 6 meses",
                ),
                evidence_spans={
                    "asset_universe": "GOOG",
                    "indicator": "RSI",
                    "entry_threshold": "debajo de 30",
                    "exit_threshold": "arriba de 60",
                    "date_range_intent": "ultimos 6 meses",
                },
            ),
            semantic_turn_act="new_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Prueba GOOG con RSI: compra debajo de 30 y vende arriba de 60 "
                "en los ultimos 6 meses"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=6,
            unit="month",
            anchor="today",
        )
    )

    assert expected_range is not None
    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "indicator_threshold"
    assert strategy.asset_universe == ["GOOG"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == expected_range.payload
    assert strategy.extra_parameters["indicator"] == "rsi"
    assert strategy.extra_parameters["indicator_parameters"] == {
        "indicator": "rsi",
        "indicator_period": 14,
        "entry_threshold": 30,
        "exit_threshold": 60,
    }
    assert strategy.extra_parameters["evidence_spans"]["indicator"] == "RSI"


def test_spanish_moving_average_crossover_reaches_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity", name=symbol),
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity", name=symbol),
    )
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary=(
                "El usuario quiere probar NVDA con cruce de medias moviles."
            ),
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "Compra NVDA cuando la media movil de 50 dias cruza arriba "
                    "de la de 200 dias, ultimo ano"
                ),
                language="es-419",
                strategy_type="signal_strategy",
                strategy_thesis="Comprar NVDA con cruce alcista de medias.",
                asset_universe=["NVDA"],
                asset_class="equity",
                entry_logic="media movil de 50 dias cruza arriba de la de 200 dias",
                entry_rule={
                    "type": "moving_average_crossover",
                    "fast_indicator": "sma",
                    "fast_period": 50,
                    "slow_indicator": "sma",
                    "slow_period": 200,
                    "direction": "bullish",
                },
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=1,
                    unit="year",
                    anchor="today",
                    evidence="ultimo ano",
                ),
                evidence_spans={
                    "asset_universe": "NVDA",
                    "entry_rule": (
                        "media movil de 50 dias cruza arriba de la de 200 dias"
                    ),
                    "date_range_intent": "ultimo ano",
                },
            ),
            semantic_turn_act="new_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Compra NVDA cuando la media movil de 50 dias cruza arriba de "
                "la de 200 dias, ultimo ano"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=1,
            unit="year",
            anchor="today",
        )
    )

    assert expected_range is not None
    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.strategy_type == "signal_strategy"
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.asset_class == "equity"
    assert strategy.date_range == expected_range.payload
    assert strategy.entry_logic == "50-day SMA crosses above 200-day SMA"
    assert strategy.entry_rule == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    assert strategy.exit_logic == "50-day SMA crosses below 200-day SMA"
    assert strategy.exit_rule == {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bearish",
    }


def test_spanish_currency_pair_timeframe_reaches_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.upper().replace("/", "")
        if normalized == "EURUSD":
            return ResolvedAssetStub("EURUSD", "currency_pair", name="EUR/USD")
        return ResolvedAssetStub(normalized, "currency_pair")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="new_task",
            requires_clarification=False,
            user_goal_summary="El usuario quiere probar EUR/USD con velas de 1 hora.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=(
                    "Usa velas de 1 hora para EUR/USD durante los ultimos 30 dias"
                ),
                language="es-419",
                strategy_type="buy_and_hold",
                strategy_thesis="Comprar y mantener EUR/USD.",
                asset_universe=["EUR/USD"],
                asset_class="currency_pair",
                timeframe="1h",
                date_range_intent=interpreter_module.LLMDateRangeIntent(
                    kind="rolling_window",
                    count=30,
                    unit="day",
                    anchor="today",
                    evidence="ultimos 30 dias",
                ),
                evidence_spans={
                    "asset_universe": "EUR/USD",
                    "timeframe": "velas de 1 hora",
                    "date_range_intent": "ultimos 30 dias",
                },
            ),
            semantic_turn_act="new_idea",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message=(
                "Usa velas de 1 hora para EUR/USD durante los ultimos 30 dias"
            ),
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    expected_range = interpreter_module.resolve_date_range_intent(
        interpreter_module.LLMDateRangeIntent(
            kind="rolling_window",
            count=30,
            unit="day",
            anchor="today",
        )
    )

    assert expected_range is not None
    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["EURUSD"]
    assert strategy.asset_class == "currency_pair"
    assert strategy.timeframe == "1h"
    assert strategy.date_range == expected_range.payload
    assert result.patch["optional_parameter_status"]["timeframe"] == "1h"


def test_spanish_pending_setup_asset_edit_preserves_existing_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        normalized = symbol.upper()
        if normalized in {"NVIDIA", "NVDA"}:
            return ResolvedAssetStub("NVDA", "equity", name="Nvidia")
        if normalized in {"TESLA", "TSLA"}:
            return ResolvedAssetStub("TSLA", "equity", name="Tesla")
        return ResolvedAssetStub(normalized, "equity")

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    pending = StrategySummary(
        raw_user_phrasing="Compra 100 dólares de Tesla cada mes durante 2024",
        strategy_type="dca_accumulation",
        strategy_thesis="Comprar Tesla de forma recurrente.",
        asset_universe=["TSLA"],
        asset_class="equity",
        cadence="monthly",
        capital_amount=100,
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
    )
    snapshot = TaskSnapshot(pending_strategy_summary=pending)

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="strategy_drafting",
            task_relation="refine",
            requires_clarification=False,
            user_goal_summary="El usuario quiere cambiar el activo a Nvidia.",
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing="Cambia el activo a Nvidia",
                language="es-419",
                asset_universe=["Nvidia"],
                asset_class="equity",
            ),
            semantic_turn_act="refine_current_idea",
            artifact_target="active_confirmation",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="Cambia el activo a Nvidia",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_user_reply"},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["NVDA"]
    assert strategy.asset_class == "equity"
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.cadence == "monthly"
    assert strategy.capital_amount == 100
    assert strategy.date_range == {"start": "2024-01-01", "end": "2024-12-31"}


def test_spanish_unsupported_valuation_request_stays_non_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        _test_model_candidates,
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ != "LLMInterpretationResponse":
            return None
        return LLMInterpretationResponse(
            intent="unsupported_or_out_of_scope",
            task_relation="new_task",
            requires_clarification=True,
            user_goal_summary="El usuario quiere comprar por valoración P/E.",
            assistant_response=(
                "P/E puede ser buen contexto, pero no es una regla ejecutable "
                "en el motor actual. Puedo probar comprar y mantener, RSI, o un "
                "cruce de medias móviles."
            ),
            unsupported_constraints=[
                interpreter_module.LLMUnsupportedConstraint(
                    category="unsupported_strategy_logic",
                    raw_value="P/E",
                    explanation="Valuation ratios are context, not executable rules.",
                    simplification_labels=[
                        "Probar comprar y mantener",
                        "Usar una regla RSI",
                    ],
                )
            ],
            semantic_turn_act="unsupported_request",
            artifact_target="none",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    result = interpret_stage(
        state=RunState.new(
            current_user_message="Compra cuando se vea barato por P/E",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1", language_preference="es-419"),
        latest_task_snapshot=None,
        selected_thread_metadata={},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    assert result.outcome == "needs_clarification"
    assert result.decision is not None
    assert result.decision.semantic_turn_act == "unsupported_request"
    assert result.decision.unsupported_constraints
    assert "confirmation_payload" not in result.patch
    assert "P/E puede ser buen contexto" in result.patch["assistant_response"]
