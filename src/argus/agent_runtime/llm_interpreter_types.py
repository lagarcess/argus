from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from argus.agent_runtime.stages.interpret_types import (
    ArtifactTarget,
    CapabilityQuestionFocus,
    ContextQuestionFocus,
    ResultFollowupFocus,
)
from argus.agent_runtime.state.models import ResponseProfileOverrides


class LLMRiskRule(BaseModel):
    type: str
    value_pct: float | None = None
    mode: str | None = None


class LLMStrategyDraft(BaseModel):
    raw_user_phrasing: str | None = None
    strategy_type: str | None = None
    strategy_thesis: str | None = None
    asset_universe: list[str] = Field(default_factory=list)
    asset_class: str | None = None
    timeframe: str | None = None
    cadence: str | None = None
    entry_logic: str | None = None
    exit_logic: str | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    indicator: str | None = None
    indicator_period: int | None = None
    entry_threshold: float | None = None
    exit_threshold: float | None = None
    date_range: str | dict[str, str] | None = None
    sizing_mode: str | None = None
    capital_amount: float | None = None
    recurring_contribution: float | None = None
    initial_capital: float | None = None
    total_capital: float | None = None
    position_size: float | None = None
    risk_rules: list[LLMRiskRule] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    comparison_baseline: str | None = None
    refinement_of: str | None = None
    field_provenance: dict[str, str] = Field(default_factory=dict)
    extra_parameters: dict[str, Any] = Field(default_factory=dict)


class LLMUnsupportedConstraint(BaseModel):
    category: str
    raw_value: str
    explanation: str
    simplification_labels: list[str] = Field(default_factory=list)


class LLMAmbiguousField(BaseModel):
    field_name: str
    raw_value: str
    candidate_normalized_value: Any | None = None
    reason_code: str


class LLMInterpretationResponse(BaseModel):
    intent: Literal[
        "beginner_guidance",
        "strategy_drafting",
        "backtest_execution",
        "results_explanation",
        "collection_management",
        "conversation_followup",
        "unsupported_or_out_of_scope",
    ]
    task_relation: Literal["new_task", "continue", "refine", "ambiguous"]
    requires_clarification: bool = False
    user_goal_summary: str
    candidate_strategy_draft: LLMStrategyDraft = Field(default_factory=LLMStrategyDraft)
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
    uses_latest_result_context: bool | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    ambiguous_fields: list[LLMAmbiguousField] = Field(default_factory=list)
    unsupported_constraints: list[LLMUnsupportedConstraint] = Field(default_factory=list)
    response_profile_overrides: ResponseProfileOverrides = Field(
        default_factory=ResponseProfileOverrides
    )
    semantic_turn_act: (
        Literal[
            "new_idea",
            "answer_pending_need",
            "refine_current_idea",
            "educational_question",
            "result_followup",
            "retry_failed_action",
            "approval",
            "unsupported_request",
        ]
        | None
    ) = None
    result_followup_focus: ResultFollowupFocus | None = None
    capability_question_focus: CapabilityQuestionFocus | None = None
    context_question_focus: ContextQuestionFocus | None = None
    artifact_target: ArtifactTarget | None = None


class FocusedStrategyExtraction(BaseModel):
    is_testable_strategy: bool
    requires_clarification: bool = False
    user_goal_summary: str
    strategy_type: str | None = None
    strategy_thesis: str | None = None
    asset_universe: list[str] = Field(default_factory=list)
    asset_class: str | None = None
    timeframe: str | None = Field(
        default=None,
        description=(
            "User-stated candle/bar interval normalized to supported notation, "
            "for example 1h for one-hour/hourly candles, 4h for four-hour bars, "
            "or 1D for daily candles. Leave null only when the user did not state it."
        ),
    )
    date_range: str | dict[str, str] | None = Field(
        default=None,
        description=(
            "User-stated test window. Preserve today/current as 'today' or the runtime "
            "date when it appears as an endpoint."
        ),
    )
    capital_amount: float | None = Field(
        default=None,
        description=(
            "User-stated starting capital or recurring contribution amount. "
            "Examples: $1k -> 1000, $500 -> 500."
        ),
    )
    entry_logic: str | None = None
    exit_logic: str | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    indicator: str | None = None
    indicator_period: int | None = None
    entry_threshold: float | None = None
    exit_threshold: float | None = None
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
