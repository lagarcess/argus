from __future__ import annotations

from dataclasses import dataclass

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_interpreter import (
    LatestResultRoutingAudit,
    LLMInterpretationResponse,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
)
from argus.agent_runtime.stages.interpret import interpret_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


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
        lambda: ["test-model"],
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
        lambda: ["test-model"],
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
        lambda: ["test-model"],
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
        lambda: ["test-model"],
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
    assert "visible card" in result.patch["assistant_response"].lower()


def test_spanish_result_followup_anchors_to_latest_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages import interpret_actions as interpret_actions_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
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
