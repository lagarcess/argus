from __future__ import annotations

from dataclasses import dataclass

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_interpreter import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
)
from argus.agent_runtime.stages.interpret import interpret_stage
from argus.agent_runtime.state.models import RunState, UserState


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


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
                cadence="semanal",
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
