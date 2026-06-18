from dataclasses import dataclass
from datetime import date

import pytest
from argus.agent_runtime.asset_text_grounding import (
    _candidate_text_supports_resolved_asset,
    provider_ticker_mentions_from_text,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.llm_interpreter import (
    AssetGroundingAudit,
    LLMDateRangeIntent,
    LLMInterpretationResponse,
    LLMRiskRule,
    LLMStrategyDraft,
    OpenRouterStructuredInterpreter,
    _llm_strategy_draft_has_executable_shape,
    _pending_signal_rule_planning_response,
    _recover_supported_signal_rule_from_draft_if_needed,
    _response_from_current_message_run_field_contract,
    _response_from_signal_grounding_audit,
    _response_from_signal_rule_plan,
    _strategy_from_llm,
)
from argus.agent_runtime.llm_interpreter_types import FocusedStrategyExtraction
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.signal_rule_repair import (
    SignalRuleGroundingAudit,
    SignalRulePlan,
    _signal_rule_grounding_messages,
)
from argus.agent_runtime.stages.interpret import InterpretationRequest, interpret_stage
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConversationMessage,
    ResolutionProvenance,
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.agent_runtime.strategy_contract import resolve_date_range
from argus.domain.backtesting.rules import (
    describe_rule_spec,
    rule_spec_from_moving_average_crossover_rules,
)


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


def _sma_50_200_crossover_rule_spec() -> dict:
    rule_spec = rule_spec_from_moving_average_crossover_rules(
        entry_rule={
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 50,
            "slow_indicator": "sma",
            "slow_period": 200,
            "direction": "bullish",
        },
        exit_rule=None,
    )
    assert rule_spec is not None
    return rule_spec


def _sma_50_200_crossover_plan(*, strategy_thesis: str) -> SignalRulePlan:
    rule_spec = _sma_50_200_crossover_rule_spec()
    return SignalRulePlan(
        outcome="ready_to_confirm",
        user_goal_summary=strategy_thesis,
        strategy_thesis=strategy_thesis,
        entry_logic=describe_rule_spec(rule_spec, "entry"),
        exit_logic=describe_rule_spec(rule_spec, "exit"),
        rule_spec=rule_spec,
        confidence=0.86,
    )


def _tsla_50_200_focused_extraction() -> FocusedStrategyExtraction:
    return FocusedStrategyExtraction(
        is_testable_strategy=True,
        requires_clarification=False,
        user_goal_summary="User asked for a 50/200 crossover test on Tesla.",
        language="en",
        strategy_type="signal_strategy",
        strategy_thesis=(
            "Backtest a bullish SMA 50/200 crossover on Tesla from January "
            "2022 to today with $10,000 capital."
        ),
        asset_universe=["Tesla"],
        asset_class="equity",
        date_range={"start": "2022-01-01", "end": "today"},
        capital_amount=10000,
        entry_rule={
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 50,
            "slow_indicator": "sma",
            "slow_period": 200,
            "direction": "bullish",
        },
        evidence_spans={
            "asset_universe": "Tesla",
            "date_range": "from January 2022 to today",
            "capital_amount": "10k",
            "entry_rule": "the 50 crosses the 200",
        },
        confidence=0.91,
    )

__all__ = [
    'date',
    'pytest',
    'AssetGroundingAudit',
    'LLMDateRangeIntent',
    'LLMInterpretationResponse',
    'LLMRiskRule',
    'LLMStrategyDraft',
    'OpenRouterStructuredInterpreter',
    '_candidate_text_supports_resolved_asset',
    'provider_ticker_mentions_from_text',
    'build_default_capability_contract',
    '_llm_strategy_draft_has_executable_shape',
    '_pending_signal_rule_planning_response',
    '_recover_supported_signal_rule_from_draft_if_needed',
    '_response_from_current_message_run_field_contract',
    '_response_from_signal_grounding_audit',
    '_response_from_signal_rule_plan',
    '_strategy_from_llm',
    'FocusedStrategyExtraction',
    'AssetResolution',
    'SignalRuleGroundingAudit',
    'SignalRulePlan',
    '_signal_rule_grounding_messages',
    'InterpretationRequest',
    'interpret_stage',
    'ArtifactReference',
    'ConversationMessage',
    'ResolutionProvenance',
    'RunState',
    'StrategySummary',
    'TaskSnapshot',
    'UserState',
    'resolve_date_range',
    'describe_rule_spec',
    'rule_spec_from_moving_average_crossover_rules',
    'ResolvedAssetStub',
    '_sma_50_200_crossover_rule_spec',
    '_sma_50_200_crossover_plan',
    '_tsla_50_200_focused_extraction',
]
