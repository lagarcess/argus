from dataclasses import dataclass
from datetime import date

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_interpreter import (
    LLMInterpretationResponse,
    LLMRiskRule,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
    _pending_signal_rule_planning_response,
    _recover_supported_signal_rule_from_draft_if_needed,
    _response_from_signal_grounding_audit,
    _response_from_signal_rule_plan,
    _signal_rule_checked_response,
)
from argus.agent_runtime.signal_rule_repair import (
    SignalRuleGroundingAudit,
    SignalRulePlan,
)
from argus.agent_runtime.stages.interpret import InterpretationRequest, interpret_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.agent_runtime.strategy_contract import resolve_date_range
from argus.domain.backtesting.rules import explicit_signal_rule_intent_from_text


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


def test_llm_interpreter_validates_asset_class_with_alpaca_resolver(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    calls: list[str] = []

    def resolve_stub(symbol: str) -> ResolvedAssetStub:
        calls.append(symbol)
        return ResolvedAssetStub(
            canonical_symbol=symbol.upper(),
            asset_class="crypto" if symbol.upper() == "BTC" else "equity",
        )

    monkeypatch.setattr(interpreter_module, "resolve_asset", resolve_stub)

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Backtest Tesla and Bitcoin together.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Backtest Tesla and Bitcoin together.",
            strategy_type="buy_and_hold",
            strategy_thesis="Hold Tesla and Bitcoin together.",
            asset_universe=["tsla", "btc"],
            date_range="last 2 years",
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Backtest Tesla and Bitcoin together.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert calls == ["tsla", "btc"]
    assert result.candidate_strategy_draft.asset_universe == ["TSLA", "BTC"]
    assert result.candidate_strategy_draft.asset_class == "mixed"
    assert result.unsupported_constraints[0].category == "unsupported_asset_mix"
    assert "currency pairs" in result.unsupported_constraints[0].explanation


def test_llm_interpreter_prompt_names_currency_pair_runtime_truth() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt()

    assert "currency pairs" in prompt
    assert "currency pair benchmark is the tested pair itself" in prompt
    assert "Kraken" in prompt


def test_llm_interpreter_prompt_routes_why_result_questions_to_performance_focus() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "why did this result happen" in prompt
    assert "why/how the result happened" in prompt
    assert "why_underperformed" in prompt


def test_llm_interpreter_prompt_separates_benchmarks_from_asset_universe() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "against spy" in prompt
    assert "comparison_baseline" in prompt
    assert "do not add benchmark symbols to asset_universe" in prompt
    assert "exact start/end dates" in prompt
    assert "never replace them with past year" in prompt


@pytest.mark.asyncio
async def test_llm_interpreter_plans_active_artifact_assumption_edit_after_model_failure(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            raise ValueError("general interpreter returned unusable JSON")
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible draft starting capital.",
            initial_capital=5000,
            confidence=0.91,
        )

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

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="Use $5,000 starting capital",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Nvidia.",
                    asset_universe=["NVDA"],
                    asset_class="equity",
                    date_range={"start": "2024-07-03", "end": "2024-08-13"},
                )
            ),
            selected_thread_metadata={
                "requested_field": "assumption",
                "last_stage_outcome": "await_user_reply",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.semantic_turn_act == "answer_pending_need"
    assert result.candidate_strategy_draft.capital_amount == 5000
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "capital_amount": "starting_capital"
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_plans_underfilled_active_artifact_assumption_edit(
    monkeypatch,
) -> None:
    from argus.agent_runtime import artifact_edit_planner
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if schema_model.__name__ == "LLMInterpretationResponse":
            return LLMInterpretationResponse(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User continued the visible draft.",
                candidate_strategy_draft=LLMStrategyDraft(
                    raw_user_phrasing="Use $5,000 starting capital",
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Nvidia.",
                    asset_universe=["NVDA"],
                    date_range={"start": "2024-07-03", "end": "2024-08-13"},
                ),
                semantic_turn_act="answer_pending_need",
            )
        return schema_model(
            outcome="ready_to_confirm",
            user_goal_summary="User changed the visible draft starting capital.",
            initial_capital=5000,
            confidence=0.91,
        )

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

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="Use $5,000 starting capital",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold Nvidia.",
                    asset_universe=["NVDA"],
                    asset_class="equity",
                    date_range={"start": "2024-07-03", "end": "2024-08-13"},
                )
            ),
            selected_thread_metadata={
                "requested_field": "assumption",
                "last_stage_outcome": "await_user_reply",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse", "ArtifactAssumptionEditPlan"]
    assert result is not None
    assert result.intent == "backtest_execution"
    assert result.candidate_strategy_draft.capital_amount == 5000
    assert result.candidate_strategy_draft.extra_parameters["field_provenance"] == {
        "capital_amount": "starting_capital"
    }
    assert "artifact_assumption_edit_planned" in result.reason_codes


def test_signal_rule_plan_promotes_macd_crossover_to_ready_rule_spec() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="Test Bitcoin with a MACD crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="ok run the macd crossover only",
            strategy_type="signal_strategy",
            strategy_thesis="Test Bitcoin when MACD turns bullish.",
            asset_universe=["BTC"],
            date_range="last 6 months",
            entry_logic="MACD crosses above its signal line",
        ),
        assistant_response="I need a more specific rule.",
    )
    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "macd",
                        "parameters": {"fast": 12, "slow": 26, "signal": 9},
                    },
                    "operator": "cross_above",
                    "right": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "signal",
                        "parameters": {"fast": 12, "slow": 26, "signal": 9},
                    },
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "macd",
                        "parameters": {"fast": 12, "slow": 26, "signal": 9},
                    },
                    "operator": "cross_below",
                    "right": {
                        "kind": "indicator",
                        "key": "macd",
                        "output": "signal",
                        "parameters": {"fast": 12, "slow": 26, "signal": 9},
                    },
                }
            ]
        },
    }

    repaired = _response_from_signal_rule_plan(
        response=response,
        plan=SignalRulePlan(
            outcome="ready_to_confirm",
            user_goal_summary="Test Bitcoin with a MACD crossover.",
            entry_logic="MACD(12,26,9) crosses above signal",
            exit_logic="MACD(12,26,9) crosses below signal",
            rule_spec=rule_spec,
        ),
    )

    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert repaired.assistant_response is None
    assert repaired.candidate_strategy_draft.rule_spec == rule_spec
    assert repaired.candidate_strategy_draft.entry_logic == (
        "MACD(12,26,9) crosses above signal"
    )
    assert "signal_rule_plan_repair" in repaired.reason_codes


def test_signal_rule_plan_ready_drops_unplanned_risk_rules() -> None:
    rule_spec = {
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
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Nvidia with a 50/200 SMA crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="signal_strategy",
            strategy_thesis="Test Nvidia with a 50/200 SMA crossover.",
            asset_universe=["NVDA"],
            date_range="last 1 year",
            risk_rules=[LLMRiskRule(type="max_drawdown", value_pct=0.2)],
        ),
    )

    repaired = _response_from_signal_rule_plan(
        response=response,
        plan=SignalRulePlan(
            outcome="ready_to_confirm",
            entry_logic="50-day SMA crosses above 200-day SMA",
            exit_logic="50-day SMA crosses below 200-day SMA",
            rule_spec=rule_spec,
        ),
    )

    assert repaired.intent == "backtest_execution"
    assert repaired.candidate_strategy_draft.rule_spec == rule_spec
    assert repaired.candidate_strategy_draft.risk_rules == []


def test_signal_rule_plan_draft_only_routes_to_unsupported_recovery() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Apple when news sentiment turns positive.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Test Apple when news sentiment turns positive.",
            strategy_type="signal_strategy",
            strategy_thesis="Use news sentiment as the Apple entry trigger.",
            asset_universe=["AAPL"],
            date_range="last 1 year",
            entry_logic="news sentiment turns positive",
        ),
    )

    repaired = _response_from_signal_rule_plan(
        response=response,
        plan=SignalRulePlan(
            outcome="draft_only",
            assistant_response="Sentiment/news signals are not executable yet.",
        ),
    )

    assert repaired.intent == "unsupported_or_out_of_scope"
    assert repaired.semantic_turn_act == "unsupported_request"
    assert repaired.missing_required_fields == []
    assert repaired.candidate_strategy_draft.strategy_type is None
    assert repaired.unsupported_constraints[0].category == "unsupported_strategy_logic"
    assert "Sentiment/news" in repaired.unsupported_constraints[0].explanation
    assert "signal_rule_plan_draft_only" in repaired.reason_codes


@pytest.mark.asyncio
async def test_supported_signal_rule_recovery_rescues_underfilled_ma_crossover(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    rule_spec = {
        "entry": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 50,
                    },
                    "operator": "cross_above",
                    "right": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 200,
                    },
                }
            ]
        },
        "exit": {
            "conditions": [
                {
                    "left": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 50,
                    },
                    "operator": "cross_below",
                    "right": {
                        "kind": "indicator",
                        "key": "sma",
                        "period": 200,
                    },
                }
            ]
        },
    }

    async def plan_stub(**kwargs):
        candidate = kwargs["candidate_strategy"]
        assert candidate["strategy_type"] == "signal_strategy"
        return SignalRulePlan(
            outcome="ready_to_confirm",
            user_goal_summary="Test NVDA with a 50/200 SMA crossover.",
            entry_logic="50-day SMA crosses above 200-day SMA",
            exit_logic="50-day SMA crosses below 200-day SMA",
            rule_spec=rule_spec,
        )

    monkeypatch.setattr(interpreter_module, "repair_signal_rule_plan", plan_stub)

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Nvidia with a Golden Cross strategy.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Test Nvidia when the 50-day moving average crosses above "
                "the 200-day moving average over the last year."
            ),
            strategy_thesis="Use a Golden Cross strategy on NVDA.",
            asset_universe=["NVDA"],
            date_range="last 1 year",
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value="Golden Cross strategy",
                explanation="This rule is not executable yet.",
            )
        ],
    )

    repaired = await _recover_supported_signal_rule_from_draft_if_needed(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Test Nvidia when the 50-day moving average crosses above "
                "the 200-day moving average over the last year."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired is not None
    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert repaired.unsupported_constraints == []
    assert repaired.candidate_strategy_draft.strategy_type == "signal_strategy"
    assert repaired.candidate_strategy_draft.rule_spec == rule_spec
    assert (
        "supported_signal_rule_contract_recovery" in repaired.reason_codes
    )


@pytest.mark.asyncio
async def test_underfilled_explicit_ma_crossover_is_normalized_without_model(
    monkeypatch,
) -> None:
    from argus.agent_runtime import signal_rule_repair as repair_module

    async def fail_if_model_called(**kwargs):
        raise AssertionError("explicit supported rules should normalize before LLM repair")

    monkeypatch.setattr(
        repair_module,
        "invoke_openrouter_json_schema",
        fail_if_model_called,
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary="Test Nvidia with a moving-average crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Test Nvidia over the past year when the 50-day moving average "
                "crosses above the 200-day moving average."
            ),
            strategy_type="signal_strategy",
            strategy_thesis="Test Nvidia with a 50/200 moving-average crossover.",
            asset_universe=["NVDA"],
            date_range="past year",
        ),
    )

    repaired = await _signal_rule_checked_response(
        response=response,
        preferred_model="test-model",
        request=InterpretationRequest(
            current_user_message=(
                "Test Nvidia over the past year when the 50-day moving average "
                "crosses above the 200-day moving average."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert repaired.intent == "backtest_execution"
    assert repaired.requires_clarification is False
    assert repaired.candidate_strategy_draft.rule_spec is not None
    assert repaired.candidate_strategy_draft.entry_logic == (
        "50-day SMA crosses above 200-day SMA"
    )
    assert repaired.candidate_strategy_draft.exit_logic == (
        "50-day SMA crosses below 200-day SMA"
    )


def test_explicit_signal_rule_normalizer_rejects_vague_momentum() -> None:
    assert explicit_signal_rule_intent_from_text(
        "Test buying SPY when it starts rising."
    ) is None


def test_signal_grounding_audit_blocks_invented_vague_momentum_rule() -> None:
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="User wants to buy SPY when it starts rising.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Test buying SPY when it starts rising.",
            strategy_type="signal_strategy",
            strategy_thesis="Buy SPY when it starts rising.",
            asset_universe=["SPY"],
            asset_class="equity",
            entry_logic="5-day SMA crosses above 20-day SMA",
            exit_logic="5-day SMA crosses below 20-day SMA",
            entry_rule={
                "type": "moving_average_crossover",
                "direction": "bullish",
                "fast_indicator": "sma",
                "fast_period": 5,
                "slow_indicator": "sma",
                "slow_period": 20,
            },
            exit_rule={
                "type": "moving_average_crossover",
                "direction": "bearish",
                "fast_indicator": "sma",
                "fast_period": 5,
                "slow_indicator": "sma",
                "slow_period": 20,
            },
        ),
    )
    audit = SignalRuleGroundingAudit(
        outcome="needs_clarification",
        assistant_response="I can test this, but I need the exact rising trigger first.",
        missing_required_fields=["entry_logic"],
    )

    repaired = _response_from_signal_grounding_audit(response=response, audit=audit)

    draft = repaired.candidate_strategy_draft
    assert repaired.requires_clarification is True
    assert repaired.missing_required_fields == ["entry_logic"]
    assert repaired.assistant_response == audit.assistant_response
    assert "signal_rule_grounding_needs_clarification" in repaired.reason_codes
    assert draft.entry_logic is None
    assert draft.exit_logic is None
    assert draft.entry_rule is None
    assert draft.exit_rule is None
    assert draft.rule_spec is None


def test_pending_signal_rule_planning_response_preserves_prior_artifact() -> None:
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="User confirmed a subset of the pending signal idea.",
        candidate_strategy_draft=LLMStrategyDraft(),
        assistant_response="Do you want to use only MACD?",
    )
    prior_strategy = {
        "strategy_type": "signal_strategy",
        "strategy_thesis": "Test Bitcoin when MACD turns bullish and volume jumps.",
        "asset_universe": ["BTC"],
        "asset_class": "crypto",
        "date_range": "last 6 months",
    }

    repaired = _pending_signal_rule_planning_response(
        response=response,
        prior_strategy=prior_strategy,
        current_user_message="ok run the macd crossover only",
    )

    draft = repaired.candidate_strategy_draft
    assert draft.strategy_type == "signal_strategy"
    assert draft.asset_universe == ["BTC"]
    assert draft.date_range == "last 6 months"
    assert draft.raw_user_phrasing == "ok run the macd crossover only"
    assert draft.strategy_thesis is None
    assert draft.entry_logic is None
    assert draft.rule_spec is None


def test_llm_interpreter_maps_indicator_threshold_fields_to_strategy_parameters(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        user_goal_summary="User supplied RSI thresholds.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Use RSI: enter at 20 and exit at 60.",
            strategy_type="indicator_threshold",
            strategy_thesis="Use RSI thresholds for TSLA.",
            asset_universe=["TSLA"],
            indicator="rsi",
            entry_threshold=20,
            exit_threshold=60,
            date_range="past 3 months",
        ),
        semantic_turn_act="answer_pending_need",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Use RSI: enter at 20 and exit at 60.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    parameters = result.candidate_strategy_draft.extra_parameters[
        "indicator_parameters"
    ]
    assert parameters["indicator"] == "rsi"
    assert parameters["entry_threshold"] == 20
    assert parameters["exit_threshold"] == 60


def test_llm_interpreter_keeps_pending_artifact_assumptions_as_followup() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="results_explanation",
        task_relation="continue",
        user_goal_summary="User asks what assumptions the visible draft uses.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            asset_universe=["NVDA"],
            date_range="past 6 months",
        ),
        assistant_response="The assumptions include a starting capital of $10,000.",
        semantic_turn_act="result_followup",
        result_followup_focus="assumptions",
    )

    normalized = interpreter_module._normalize_response_for_runtime_context(
        response,
        request=InterpretationRequest(
            current_user_message="What assumptions are you using?",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["NVDA"],
                    asset_class="equity",
                    date_range="past 6 months",
                )
            ),
            user=UserState(user_id="u1"),
        ),
    )

    assert normalized.intent == "conversation_followup"
    assert normalized.semantic_turn_act == "result_followup"
    assert normalized.result_followup_focus == "assumptions"
    assert normalized.assistant_response is None
    assert "routed_pending_artifact_assumptions_followup" in normalized.reason_codes


@pytest.mark.asyncio
async def test_llm_interpreter_preserves_result_followup_during_pending_refinement(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda: ["test-model"],
    )

    calls: list[str] = []

    async def invoke_stub(*, schema_model, **kwargs):
        del kwargs
        calls.append(schema_model.__name__)
        if len(calls) == 1:
            return LLMInterpretationResponse(
                intent="results_explanation",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="User asks what the latest completed run tested.",
                semantic_turn_act="result_followup",
                result_followup_focus="what_tested",
            )
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="refine",
            requires_clarification=False,
            user_goal_summary="Incorrectly replays the prior MSFT run as a new draft.",
            candidate_strategy_draft=LLMStrategyDraft(
                strategy_type="buy_and_hold",
                strategy_thesis="Buy and hold MSFT.",
                asset_universe=["MSFT"],
                date_range={"start": "2025-01-01", "end": "2025-12-31"},
                capital_amount=100000,
            ),
            semantic_turn_act="answer_pending_need",
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    result = await interpreter.ainvoke(
        InterpretationRequest(
            current_user_message="Before changing anything, what exactly did you test?",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    strategy_thesis="Buy and hold MSFT.",
                    asset_universe=["MSFT"],
                    asset_class="equity",
                    date_range={"start": "2025-01-01", "end": "2025-12-31"},
                ),
                latest_backtest_result_reference=ArtifactReference(
                    artifact_kind="backtest_result",
                    artifact_id="run-msft-2025",
                    artifact_status="completed",
                    metadata={
                        "symbols": ["MSFT"],
                        "benchmark_symbol": "SPY",
                        "metrics": {
                            "aggregate": {
                                "performance": {
                                    "total_return_pct": 15.6,
                                    "benchmark_return_pct": 16.6,
                                    "delta_vs_benchmark_pct": -1.1,
                                }
                            }
                        },
                        "config_snapshot": {
                            "template": "buy_and_hold",
                            "symbols": ["MSFT"],
                            "date_range": {
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                            },
                            "starting_capital": 1000,
                        },
                    },
                ),
            ),
            selected_thread_metadata={
                "requested_field": "refinement",
                "source_result_run_id": "run-msft-2025",
            },
            user=UserState(user_id="u1"),
        )
    )

    assert calls == ["LLMInterpretationResponse"]
    assert result is not None
    assert result.intent == "results_explanation"
    assert result.semantic_turn_act == "result_followup"
    assert result.result_followup_focus == "what_tested"


def test_focused_strategy_extraction_uses_indicator_threshold_registry() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    extraction = interpreter_module.FocusedStrategyExtraction(
        is_testable_strategy=True,
        user_goal_summary="Buy when SMA is below a chosen level.",
        indicator="sma",
        entry_threshold=450,
        exit_threshold=500,
    )

    response = interpreter_module._response_from_focused_strategy_extraction(
        extraction=extraction,
        request=InterpretationRequest(
            current_user_message="Buy SPY when SMA is under 450.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert response.candidate_strategy_draft.strategy_type == "indicator_threshold"
    assert response.candidate_strategy_draft.indicator == "sma"


def test_focused_strategy_extraction_does_not_force_unknown_strategy_contracts() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    extraction = interpreter_module.FocusedStrategyExtraction(
        is_testable_strategy=True,
        user_goal_summary="Buy Apple when news sentiment turns positive.",
        strategy_type="sentiment_strategy",
        strategy_thesis="Use sentiment as the entry signal for Apple.",
        asset_universe=["AAPL"],
        date_range="past year",
        entry_logic="news sentiment turns positive",
    )

    response = interpreter_module._response_from_focused_strategy_extraction(
        extraction=extraction,
        request=InterpretationRequest(
            current_user_message="Test Apple when news sentiment turns positive.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert response.intent == "unsupported_or_out_of_scope"
    assert response.semantic_turn_act == "unsupported_request"
    assert response.requires_clarification is True
    assert response.candidate_strategy_draft.strategy_type is None
    assert response.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert response.unsupported_constraints[0].category == "unsupported_strategy_logic"
    assert (
        "focused_strategy_extraction_unrecognized_contract" in response.reason_codes
    )


def test_focused_strategy_extraction_prompt_preserves_draft_only_strategy_fields() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    messages = interpreter_module._focused_strategy_extraction_messages(
        InterpretationRequest(
            current_user_message="Test Apple when news sentiment turns positive.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        )
    )
    prompt = messages[0].content

    assert "it does not mean Argus can execute every part" in prompt
    assert "preserve the asset, period, unsupported rule" in prompt


def test_focused_strategy_extraction_preserves_non_executable_idea_as_recovery() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    extraction = interpreter_module.FocusedStrategyExtraction(
        is_testable_strategy=False,
        user_goal_summary="Test Apple when news sentiment turns positive.",
        strategy_thesis="Use sentiment as the entry signal for Apple.",
        asset_universe=["AAPL"],
        date_range="past year",
        entry_logic="news sentiment turns positive",
        assistant_response="Sentiment/news signals are not executable yet.",
    )

    response = interpreter_module._response_from_focused_strategy_extraction(
        extraction=extraction,
        request=InterpretationRequest(
            current_user_message="Test Apple when news sentiment turns positive.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert response.intent == "unsupported_or_out_of_scope"
    assert response.semantic_turn_act == "unsupported_request"
    assert response.requires_clarification is True
    assert response.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert response.candidate_strategy_draft.date_range == "past year"
    assert "Sentiment/news signals" in response.unsupported_constraints[0].explanation


def test_unsupported_free_text_strategy_response_needs_context_repair() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="unsupported_or_out_of_scope",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test Apple when news sentiment turns positive.",
        assistant_response=(
            "This strategy requires sentiment analysis, which is not supported."
        ),
    )

    assert interpreter_module._response_needs_artifact_context_repair(response) is True


def test_conversation_followup_with_unstructured_strategy_text_needs_repair() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = LLMInterpretationResponse(
        intent="conversation_followup",
        task_relation="new_task",
        user_goal_summary="Test Apple when news sentiment turns positive.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Test Apple when news sentiment turns positive.",
            strategy_thesis="Test Apple when news sentiment turns positive.",
        ),
        assistant_response=(
            "This strategy requires sentiment analysis, which is not supported."
        ),
        semantic_turn_act="educational_question",
    )

    assert interpreter_module._response_needs_artifact_context_repair(response) is True


def test_llm_interpreter_promotes_typed_indicator_values_from_extra_parameters(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        user_goal_summary="User supplied RSI thresholds.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Use RSI entry 20 exit 60.",
            strategy_type="indicator_threshold",
            strategy_thesis="Use RSI thresholds for TSLA.",
            asset_universe=["TSLA"],
            date_range="past 3 months",
            indicator="rsi",
            extra_parameters={
                "entry_threshold": 20,
                "exit_threshold": 60,
                "field_provenance": {
                    "entry_threshold": "user",
                    "exit_threshold": "user",
                },
                "indicator_parameters": {
                    "indicator": "rsi",
                    "entry_threshold": 30,
                    "exit_threshold": 55,
                },
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Use RSI entry 20 exit 60.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    parameters = strategy.extra_parameters["indicator_parameters"]
    assert parameters["entry_threshold"] == 20.0
    assert parameters["exit_threshold"] == 60.0
    assert strategy.entry_logic == "Buy when RSI(14) drops to 20 or below"
    assert strategy.exit_logic == "Sell when RSI(14) rises to 60 or above"


def test_llm_signal_rule_defaults_describe_indicator_parameters(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="continue",
        user_goal_summary="User supplied RSI signal thresholds.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Use RSI: enter at 20 and exit at 60.",
            strategy_type="signal_strategy",
            strategy_thesis="Use RSI thresholds for TSLA.",
            asset_universe=["TSLA"],
            date_range="past 3 months",
            entry_logic="RSI is 20 or lower",
            exit_logic="RSI is 60 or higher",
            rule_spec={
                "entry": {
                    "conditions": [
                        {
                            "left": {"kind": "indicator", "key": "rsi"},
                            "operator": "lte",
                            "right": 20,
                        }
                    ]
                },
                "exit": {
                    "conditions": [
                        {
                            "left": {"kind": "indicator", "key": "rsi"},
                            "operator": "gte",
                            "right": 60,
                        }
                    ]
                },
            },
        ),
        semantic_turn_act="answer_pending_need",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Use RSI: enter at 20 and exit at 60.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.entry_logic == "RSI(14) is 20 or lower"
    assert strategy.exit_logic == "RSI(14) is 60 or higher"


def test_llm_interpreter_merges_refinement_with_pending_strategy(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )
    monkeypatch.setattr(
        interpret_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    snapshot = TaskSnapshot(
        latest_task_type="backtest_execution",
        completed=False,
        pending_strategy_summary=StrategySummary(
            raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
            strategy_type="dca_accumulation",
            strategy_thesis="Invest $500 in Bitcoin every month since 2021.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="since 2021",
            cadence="monthly",
            capital_amount=500,
            sizing_mode="capital_amount",
        ),
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="refine",
        user_goal_summary="Make the pending DCA strategy weekly.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Actually make that weekly instead.",
            strategy_type="dca_accumulation",
            cadence="weekly",
        ),
    )

    interpretation = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Actually make that weekly instead.",
            recent_thread_history=[],
            latest_task_snapshot=snapshot,
            user=UserState(user_id="u1"),
        ),
    )
    result = interpret_stage(
        state=RunState.new(
            current_user_message="Actually make that weekly instead.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="u1"),
        latest_task_snapshot=snapshot,
        structured_interpreter=lambda request: interpretation,
    )

    strategy = result.decision.candidate_strategy_draft
    assert strategy.asset_universe == ["BTC"]
    assert strategy.capital_amount == 500
    assert strategy.date_range == "since 2021"
    assert strategy.cadence == "weekly"


def test_llm_interpreter_preserves_semantic_turn_act_from_response() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        user_goal_summary="User approved the pending strategy.",
        semantic_turn_act="approval",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="yes run it",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.semantic_turn_act == "approval"


def test_llm_system_prompt_forbids_scaffolding_and_internal_field_names() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "asset_universe" in prompt
    assert "capital_amount" in prompt
    assert "requested_field" in prompt
    assert "not specified" in prompt
    assert "do not expose" in prompt or "never expose" in prompt


def test_llm_system_prompt_owns_phase_one_routing_and_quality_rules() -> None:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )

    prompt = interpreter._system_prompt().lower()

    assert "semantic_turn_act" in prompt
    assert "approval" in prompt
    assert "refine_current_idea" in prompt
    assert "conversation_followup" in prompt
    assert "educational" in prompt
    assert "asset_universe" in prompt
    assert "capital_amount" in prompt
    assert "missing_required_fields" in prompt
    assert "not specified" in prompt
    assert "what to try next" in prompt
    assert "next_experiment" in prompt


def test_llm_system_prompt_owns_phase_three_extraction_rules() -> None:
    prompt = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )._system_prompt()

    assert "Extract symbols, company names, crypto assets, and currency pairs" in prompt
    assert "Do not rely on backend text-pattern extraction" in prompt
    assert "date_range" in prompt
    assert "cadence" in prompt
    assert "semantic_turn_act is the routing source of truth" in prompt
    assert "response_profile_overrides" in prompt
    assert "social" in prompt.lower()
    assert "educational" in prompt.lower()
    assert "what if I bought/held/owned" in prompt
    assert "not a capability or education question" in prompt


def test_llm_interpreter_treats_moving_average_crossover_as_executable_signal(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy Nvidia on a 50/200 moving-average crossover.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "Buy Nvidia when its 50-day moving average crosses above the 200-day"
            ),
            strategy_type="indicator_threshold",
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
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "Buy Nvidia when its 50-day moving average crosses above the 200-day"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.candidate_strategy_draft.entry_logic == (
        "50-day SMA crosses above 200-day SMA"
    )
    assert result.candidate_strategy_draft.strategy_type == "signal_strategy"
    assert result.candidate_strategy_draft.exit_logic == (
        "50-day SMA crosses below 200-day SMA"
    )
    assert result.unsupported_constraints == []


def test_llm_interpreter_humanizes_unsupported_simplification_labels(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy Nvidia when MACD crosses above its signal line.",
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Nvidia when MACD crosses above its signal line.",
            asset_universe=["NVDA"],
            entry_logic="MACD crosses above its signal line",
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_indicator_rule",
                raw_value="MACD signal-line crossover",
                explanation="MACD signal-line crossovers are not directly executable.",
                simplification_labels=["rsi_preset", "buy_and_hold", "dca_accumulation"],
            )
        ],
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "Buy Nvidia when MACD crosses above its signal line."
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    labels = [
        option.label
        for option in result.unsupported_constraints[0].simplification_options
    ]
    assert labels == [
        "Use the supported RSI rule",
        "Compare with buy and hold",
        "Try recurring buys",
    ]
    assert result.unsupported_constraints[0].explanation.startswith("I understand")


def test_llm_interpreter_drops_stale_unsupported_copy_for_executable_rsi_threshold(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="refine",
        user_goal_summary="Use RSI 40 for the Apple dip rule.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="buy every time rsi drops below 40",
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Apple when RSI drops below 40.",
            asset_universe=["AAPL"],
            date_range="last two years",
            entry_logic="RSI drops below 40",
            indicator="rsi",
            entry_threshold=40,
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_indicator_rule",
                raw_value="RSI below 40",
                explanation="The only executable RSI preset is buy below 30.",
                simplification_labels=["rsi_preset"],
            )
        ],
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="buy every time rsi drops below 40",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="strategy_drafting",
                completed=False,
                pending_strategy_summary=StrategySummary(
                    strategy_type="indicator_threshold",
                    strategy_thesis="Buy Apple after big drops.",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    date_range="last two years",
                ),
            ),
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert result.unsupported_constraints == []
    assert strategy.entry_logic == "Buy when RSI(14) drops to 40 or below"
    assert strategy.exit_logic == "Sell when RSI(14) rises to 55 or above"


def test_llm_interpreter_does_not_merge_prior_dca_into_fresh_strategy(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="User wants to define Apple dip buying.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="What if I bought Apple after big drops?",
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Apple after big drops.",
            asset_universe=["AAPL"],
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="What if I bought Apple after big drops?",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                latest_task_type="strategy_drafting",
                completed=False,
                pending_strategy_summary=StrategySummary(
                    strategy_type="dca_accumulation",
                    strategy_thesis="Buy a fixed amount every month.",
                    cadence="monthly",
                    capital_amount=500,
                ),
            ),
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.strategy_type == "indicator_threshold"
    assert strategy.asset_universe == ["AAPL"]
    assert strategy.cadence is None
    assert strategy.capital_amount is None


def test_llm_interpreter_removes_stale_indicator_limit_when_user_only_said_drops(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="User wants to test Apple after big drops.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="What if I bought Apple after big drops?",
            strategy_type="indicator_threshold",
            strategy_thesis="Buy Apple after big drops.",
            asset_universe=["AAPL"],
        ),
        unsupported_constraints=[
            interpreter_module.LLMUnsupportedConstraint(
                category="unsupported_indicator_rule",
                raw_value="moving-average crossover",
                explanation=(
                    "Argus cannot execute that exact moving-average or "
                    "compound indicator logic yet."
                ),
                simplification_labels=["Compare NVDA with buy and hold"],
            )
        ],
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="What if I bought Apple after big drops?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.candidate_strategy_draft.strategy_type == "indicator_threshold"
    assert result.candidate_strategy_draft.cadence is None
    assert result.candidate_strategy_draft.capital_amount is None
    assert result.unsupported_constraints == []


def test_llm_interpreter_accepts_structured_date_ranges(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy and hold Bitcoin from last year to date.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Bitcoin from January 1 last year to date.",
            asset_universe=["BTC"],
            date_range={"start": "2025-01-01", "end": "today"},
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.date_range == {"start": "2025-01-01", "end": "today"}
    assert resolve_date_range(strategy.date_range, today=date(2026, 5, 3)).payload == {
        "start": "2025-01-01",
        "end": "2026-05-03",
    }


def test_llm_interpreter_preserves_user_since_year_when_model_defaults_period(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Invest $500 in Bitcoin every month since 2021.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
            strategy_type="dca_accumulation",
            strategy_thesis="Invest $500 in Bitcoin every month since 2021.",
            asset_universe=["BTC"],
            asset_class="crypto",
            date_range="since 2021",
            cadence="monthly",
            capital_amount=500,
            field_provenance={"capital_amount": "recurring_contribution"},
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Invest $500 in Bitcoin every month since 2021.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.date_range == "since 2021"
    assert strategy.capital_amount == 500
    assert strategy.cadence == "monthly"


def test_llm_interpreter_rejects_invented_dca_contribution_amount(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy Tesla every month.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="What if I bought Tesla every month?",
            strategy_type="dca_accumulation",
            strategy_thesis="Buy Tesla every month.",
            asset_universe=["TSLA"],
            asset_class="equity",
            cadence="monthly",
            capital_amount=10000,
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="What if I bought Tesla every month?",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.strategy_type == "dca_accumulation"
    assert strategy.capital_amount is None


def test_llm_interpreter_rejects_invented_initial_capital(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Test Apple with RSI.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Simplify it to RSI.",
            strategy_type="indicator_threshold",
            strategy_thesis="Test Apple with RSI.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="last year",
            indicator="rsi",
            initial_capital=100000,
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Simplify it to RSI.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert "initial_capital" not in result.candidate_strategy_draft.extra_parameters


def test_llm_interpreter_drops_unstated_buy_hold_execution_defaults(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="continue",
        user_goal_summary="Test TSLA over the past year.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="test the past year",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Tesla.",
            asset_universe=["TSLA"],
            date_range="past 1 year",
            sizing_mode="fixed",
            capital_amount=10000,
            position_size=1.0,
            risk_rules=[LLMRiskRule(type="max_position_size", value_pct=100.0)],
            field_provenance={"capital_amount": "default_assumption"},
        ),
        semantic_turn_act="answer_pending_need",
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="test the past year",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.capital_amount is None
    assert strategy.position_size is None
    assert strategy.sizing_mode is None
    assert strategy.risk_rules == []
    assert "field_provenance" not in strategy.extra_parameters


def test_llm_interpreter_preserves_grounded_initial_capital(monkeypatch) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "equity"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Test Apple with RSI using $10,000.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Test Apple with RSI using $10,000.",
            strategy_type="indicator_threshold",
            strategy_thesis="Test Apple with RSI.",
            asset_universe=["AAPL"],
            asset_class="equity",
            date_range="last year",
            indicator="rsi",
            initial_capital=10000,
            field_provenance={"initial_capital": "explicit_user"},
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message="Test Apple with RSI using $10,000.",
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    assert result.candidate_strategy_draft.extra_parameters["initial_capital"] == 10000


def test_llm_interpreter_honors_explicit_buy_and_hold_over_entry_like_phrase(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="backtest_execution",
        task_relation="new_task",
        user_goal_summary="Buy and hold Bitcoin from January 1 last year.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold Bitcoin from January 1 last year.",
            asset_universe=["BTC"],
            date_range={"start": "2024-01-01", "end": "today"},
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=(
                "let's try a basic buy and hold on BTC from jan first last year to date"
            ),
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.strategy_type == "buy_and_hold"
    assert strategy.entry_logic is None
    assert strategy.exit_logic is None
    assert result.requires_clarification is False


def test_llm_interpreter_preserves_actual_user_phrasing_when_model_rewrites_it(
    monkeypatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol: ResolvedAssetStub(symbol.upper(), "crypto"),
    )

    user_message = (
        "let's try a basic buy and hold on BTC from jan first last year to date"
    )
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    response = LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        user_goal_summary="Buy and hold BTC.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="buy and hold on BTC from jan first last 1 year to date",
            strategy_type="buy_and_hold",
            asset_universe=["BTC"],
            date_range={"start": "2025-01-01", "end": "today"},
            capital_amount=10000,
            comparison_baseline="BTC",
        ),
    )

    result = interpreter._to_runtime_interpretation(
        response,
        request=InterpretationRequest(
            current_user_message=user_message,
            recent_thread_history=[],
            latest_task_snapshot=None,
            user=UserState(user_id="u1"),
        ),
    )

    strategy = result.candidate_strategy_draft
    assert strategy.raw_user_phrasing == user_message
    assert strategy.strategy_thesis == user_message
    assert strategy.date_range == {"start": "2025-01-01", "end": "today"}
