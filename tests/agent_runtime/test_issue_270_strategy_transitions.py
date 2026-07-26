"""Regression coverage for issue #270 strategy-family transitions."""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.confirmation_artifacts import (
    confirmation_artifact_reference,
)
from argus.agent_runtime.llm_interpreter import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
)
from argus.agent_runtime.llm_interpreter_types import LLMUnsupportedConstraint
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.interpret import interpret_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.api.chat.confirmation import runtime_confirmation_card
from argus.domain.backtesting.rules import (
    rule_spec_from_moving_average_crossover_rules,
)

from tests.agent_runtime._llm_interpreter_common import ResolvedAssetStub

ENTRY_RULE = {
    "type": "moving_average_crossover",
    "fast_indicator": "sma",
    "fast_period": 50,
    "slow_indicator": "sma",
    "slow_period": 200,
    "direction": "bullish",
}
EXIT_RULE = {
    **ENTRY_RULE,
    "direction": "bearish",
}
RULE_SPEC = rule_spec_from_moving_average_crossover_rules(
    entry_rule=ENTRY_RULE,
    exit_rule=EXIT_RULE,
)
assert RULE_SPEC is not None


def _buy_and_hold_strategy() -> StrategySummary:
    return StrategySummary(
        requested_strategy_template="buy_and_hold",
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and NVDA.",
        asset_universe=["AAPL", "MSFT", "NVDA"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2023-01-03", "end": "2024-12-31"},
        capital_amount=12000,
        comparison_baseline="SPY",
        entry_rule={"type": "start_of_period"},
        exit_rule={"type": "end_of_period"},
        extra_parameters={
            "fee_rate": 0.001,
            "slippage": 0.0005,
        },
    )


def _buy_and_hold_confirmation(strategy: StrategySummary) -> dict[str, Any]:
    return {
        "confirmation_id": "confirmation-270-buy-and-hold",
        "artifact_id": "confirmation-270-buy-and-hold",
        "strategy": strategy.model_dump(mode="python"),
        "optional_parameters": {},
        "launch_payload": {
            "strategy_type": "buy_and_hold",
            "symbol": "AAPL",
            "symbols": ["AAPL", "MSFT", "NVDA"],
            "asset_class": "equity",
            "timeframe": "1D",
            "date_range": {"start": "2023-01-03", "end": "2024-12-31"},
            "entry_rule": None,
            "exit_rule": None,
            "rule_spec": None,
            "sizing_mode": "capital_amount",
            "capital_amount": 12000,
            "position_size": None,
            "cadence": None,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
            "language": "en",
        },
        "validation": {
            "status": "ready_to_run",
            "executable": True,
            "date_adjusted": False,
        },
    }


def _strategy_edit_snapshot() -> TaskSnapshot:
    strategy = _buy_and_hold_strategy()
    confirmation = _buy_and_hold_confirmation(strategy)
    reference = confirmation_artifact_reference(
        confirmation_id="confirmation-270-buy-and-hold",
        confirmation_payload=confirmation,
    )
    completed_result = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-270-historical",
        artifact_status="completed",
        metadata={
            "run_id": "run-270-historical",
            "strategy_type": "buy_and_hold",
            "symbols": ["AAPL", "MSFT", "NVDA"],
        },
    )
    return TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=strategy,
        active_confirmation_reference=reference,
        latest_backtest_result_reference=completed_result,
        artifact_references=[completed_result, reference],
    )


def _crossover_draft(*, language: str = "en") -> LLMStrategyDraft:
    return LLMStrategyDraft(
        raw_user_phrasing=(
            "Use a 50/200 SMA crossover instead and keep every other assumption."
        ),
        language=language,
        requested_strategy_template="moving_average_crossover",
        strategy_type="signal_strategy",
        strategy_thesis="Trade a bullish 50/200 SMA crossover.",
        asset_universe=["AAPL", "MSFT", "NVDA"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2023-01-03", "end": "2024-12-31"},
        capital_amount=12000,
        comparison_baseline="SPY",
        entry_logic="50-day SMA crosses above 200-day SMA",
        exit_logic="50-day SMA crosses below 200-day SMA",
        entry_rule=dict(ENTRY_RULE),
        exit_rule=dict(EXIT_RULE),
        rule_spec=RULE_SPEC,
        field_provenance={
            "requested_strategy_template": "explicit_user",
            "strategy_type": "explicit_user",
            "entry_rule": "explicit_user",
            "exit_rule": "explicit_user",
        },
        extra_parameters={
            "fee_rate": 0.001,
            "slippage": 0.0005,
        },
    )


def test_active_buy_and_hold_confirmation_accepts_typed_crossover_patch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A strategy-family edit must replace rules while carrying other facts."""

    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import confirm as confirm_module
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda *args, **kwargs: ["test-model"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    monkeypatch.setattr(confirm_module, "fetch_alpaca_market_clock", lambda: None)

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        if schema_model.__name__ == "LLMInterpretationResponse":
            prior = _buy_and_hold_strategy()
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="Change the active strategy to a crossover.",
                candidate_strategy_draft=LLMStrategyDraft.model_validate(
                    prior.model_dump(mode="python")
                ).model_copy(
                    update={
                        "raw_user_phrasing": (
                            "Use a 50/200 SMA crossover instead and keep every "
                            "other assumption."
                        )
                    }
                ),
                semantic_turn_act="refine_current_idea",
                artifact_target="active_confirmation",
            )
        if schema_model.__name__ == "ArtifactAssumptionEditPlan":
            return schema_model.model_validate(
                {
                    "outcome": "ready_to_confirm",
                    "user_goal_summary": (
                        "Change the active strategy to a 50/200 SMA crossover."
                    ),
                    "operations": [
                        {
                            "op": "replace",
                            "target": "strategy_family",
                            "strategy_template": "moving_average_crossover",
                            "entry_rule": ENTRY_RULE,
                            "exit_rule": EXIT_RULE,
                        }
                    ],
                    "confidence": 0.96,
                }
            )
        return None

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    state = RunState.new(
        current_user_message=(
            "Use a 50/200 SMA crossover instead and keep every other assumption."
        ),
        recent_thread_history=[],
    )
    snapshot = _strategy_edit_snapshot()
    result = interpret_stage(
        state=state,
        user=UserState(user_id="u-270"),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract(),
        ),
    )

    assert result.outcome == "ready_for_confirmation", (
        result.patch.get("missing_required_fields"),
        result.patch.get("unsupported_constraints"),
        {
            key: result.patch.get("candidate_strategy_draft", {}).get(key)
            for key in (
                "requested_strategy_template",
                "strategy_type",
                "strategy_thesis",
                "entry_logic",
                "exit_logic",
                "entry_rule",
                "exit_rule",
                "rule_spec",
            )
        },
    )
    strategy = result.decision.candidate_strategy_draft
    assert strategy.requested_strategy_template == "moving_average_crossover"
    assert strategy.strategy_type == "signal_strategy"
    assert strategy.rule_spec == RULE_SPEC
    assert strategy.entry_rule == ENTRY_RULE
    assert strategy.exit_rule == EXIT_RULE
    assert strategy.asset_universe == ["AAPL", "MSFT", "NVDA"]
    assert strategy.capital_amount == 12000
    assert strategy.date_range == {"start": "2023-01-03", "end": "2024-12-31"}
    assert strategy.timeframe == "1D"
    assert strategy.comparison_baseline == "SPY"
    assert strategy.extra_parameters["fee_rate"] == 0.001
    assert strategy.extra_parameters["slippage"] == 0.0005
    historical_result = snapshot.latest_backtest_result_reference
    assert historical_result is not None
    assert historical_result.artifact_id == "run-270-historical"
    assert historical_result.artifact_status == "completed"
    assert historical_result.metadata["strategy_type"] == "buy_and_hold"

    confirmation_state = RunState.new(
        current_user_message=state.current_user_message,
        recent_thread_history=[],
    )
    confirmation_state.candidate_strategy_draft = strategy
    confirmation = confirm_stage(
        state=confirmation_state,
        contract=build_default_capability_contract(),
    )
    assert confirmation.outcome == "await_approval"
    payload = confirmation.patch["confirmation_payload"]
    assert payload["confirmation_id"] != "confirmation-270-buy-and-hold"
    assert payload["strategy"]["strategy_type"] == "signal_strategy"
    assert payload["strategy"]["rule_spec"] == RULE_SPEC
    assert payload["launch_payload"]["strategy_type"] == "signal_strategy"
    assert payload["launch_payload"]["rule_spec"] == RULE_SPEC


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "message"),
    [
        (
            "en",
            (
                "Backtest AAPL, MSFT, and NVDA with $12,000 from Jan 3, 2023 "
                "through Dec 31, 2024 using daily data and SPY as benchmark. "
                "Enter when the 50-day SMA crosses above the 200-day SMA and "
                "exit when it crosses below."
            ),
        ),
        (
            "es-419",
            (
                "Prueba AAPL, MSFT y NVDA con $12,000 del 3 de enero de 2023 "
                "al 31 de diciembre de 2024, datos diarios y SPY como referencia. "
                "Entra cuando la SMA de 50 días cruce por encima de la SMA de "
                "200 días y sal cuando cruce por debajo."
            ),
        ),
    ],
)
async def test_complete_crossover_conflict_audit_does_not_invent_comparison(
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    message: str,
) -> None:
    """SPY benchmark is not a second buy-and-hold strategy."""

    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test a complete multi-asset 50/200 SMA crossover.",
        candidate_strategy_draft=_crossover_draft(language=language),
        assistant_response=(
            "I cannot run the crossover alongside a buy-and-hold baseline."
        ),
        unsupported_constraints=[
            LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="moving-average crossover alongside buy-and-hold",
                explanation=(
                    "The engine cannot compare this crossover with buy-and-hold."
                ),
            )
        ],
        semantic_turn_act="unsupported_request",
    )

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        assert schema_model.__name__ == "SupportedStrategyCapabilityConflictAudit"
        return schema_model(
            selected_strategy_type="signal_strategy",
            drop_unsupported_strategy_logic=True,
            keep_unsupported_strategy_logic=False,
            confidence=0.98,
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )
    repaired = await interpreter_module._audit_supported_strategy_capability_conflict(
        response=response,
        preferred_model="test-model",
        request=interpreter_module.InterpretationRequest(
            current_user_message=message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            selected_thread_metadata={},
            user=UserState(user_id="u-270", language_preference=language),
        ),
    )

    assert repaired is not None
    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert repaired.unsupported_constraints == []
    assert repaired.candidate_strategy_draft.strategy_type == "signal_strategy"
    assert repaired.candidate_strategy_draft.comparison_baseline == "SPY"
    assert repaired.candidate_strategy_draft.rule_spec == RULE_SPEC


def test_crossover_confirmation_launch_and_reload_share_one_typed_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Card, launch request, and rehydrated artifact must describe one setup."""

    from argus.agent_runtime.stages import confirm as confirm_module

    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setattr(confirm_module, "fetch_alpaca_market_clock", lambda: None)
    state = RunState.new(
        current_user_message="Use the complete 50/200 SMA crossover.",
        recent_thread_history=[],
    )
    state.candidate_strategy_draft = StrategySummary.model_validate(
        _crossover_draft().model_dump(mode="python")
    )

    confirmation = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
    )

    assert confirmation.outcome == "await_approval"
    payload = confirmation.patch["confirmation_payload"]
    strategy = payload["strategy"]
    launch = payload["launch_payload"]
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": payload,
        }
    )
    assert card is not None
    assert card["title"] == "AAPL, MSFT, NVDA moving average crossover"
    assert strategy["requested_strategy_template"] == "moving_average_crossover"
    assert strategy["strategy_type"] == "signal_strategy"
    assert strategy["rule_spec"] == RULE_SPEC
    assert strategy["entry_rule"] == ENTRY_RULE
    assert strategy["exit_rule"] == EXIT_RULE
    assert launch["strategy_type"] == "signal_strategy"
    assert launch["rule_spec"] == RULE_SPEC
    assert launch["entry_rule"] == ENTRY_RULE
    assert launch["exit_rule"] == EXIT_RULE
    assert launch["benchmark_symbol"] == "SPY"

    reference = confirmation_artifact_reference(
        confirmation_id=payload["confirmation_id"],
        confirmation_payload=payload,
        confirmation_card=card,
    )
    reloaded = TaskSnapshot.model_validate(
        TaskSnapshot(
            pending_strategy_summary=StrategySummary.model_validate(strategy),
            active_confirmation_reference=reference,
            artifact_references=[reference],
        ).model_dump(mode="json")
    )
    active = reloaded.active_confirmation_reference
    assert active is not None
    reloaded_payload = active.metadata["confirmation_payload"]
    assert reloaded_payload["strategy"]["strategy_type"] == "signal_strategy"
    assert reloaded_payload["strategy"]["rule_spec"] == RULE_SPEC
    assert reloaded_payload["launch_payload"]["strategy_type"] == "signal_strategy"
    assert reloaded_payload["launch_payload"]["rule_spec"] == RULE_SPEC


def test_complete_fresh_crossover_recovers_registry_template_from_typed_rules() -> None:
    """Executable typed rules must retain their named capability identity."""

    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.strategy_contract import (
        executable_strategy_template_from_typed_rules,
    )

    draft = _crossover_draft().model_copy(
        update={
            "requested_strategy_template": None,
            "rule_spec": None,
        }
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test a complete 50/200 SMA crossover.",
        candidate_strategy_draft=draft,
        semantic_turn_act="new_idea",
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(),
    )

    interpretation = interpreter._to_runtime_interpretation(
        response,
        request=interpreter_module.InterpretationRequest(
            current_user_message=draft.raw_user_phrasing or "",
            recent_thread_history=[],
            latest_task_snapshot=None,
            selected_thread_metadata={},
            user=UserState(user_id="u-270"),
        ),
    )

    assert (
        interpretation.candidate_strategy_draft.requested_strategy_template
        == "moving_average_crossover"
    )
    assert interpretation.candidate_strategy_draft.rule_spec == RULE_SPEC

    malformed = interpretation.candidate_strategy_draft.model_copy(
        update={"exit_rule": dict(ENTRY_RULE)}
    )
    assert executable_strategy_template_from_typed_rules(malformed) is None
