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


class LLMAssetMentionCandidate(BaseModel):
    raw_text: str = Field(
        default="",
        description=(
            "Exact short user-message span that names a possible traded asset, "
            "company, ticker, crypto asset, currency pair, benchmark, or "
            "comparison asset."
        ),
    )
    role: Literal["traded_asset", "benchmark", "unknown"] = Field(
        default="unknown",
        description=(
            "Use traded_asset when the user wants to buy, hold, test, or include "
            "the asset in the strategy. Use benchmark when it is only a comparison "
            "or reference baseline."
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class LLMAssetMentionExtraction(BaseModel):
    asset_mentions: list[LLMAssetMentionCandidate] = Field(
        default_factory=list,
        description=(
            "Provider-resolution candidates identified by the LLM from the current "
            "message. Keep at most five distinct asset-like mentions."
        ),
    )


class LLMDateRangeIntent(BaseModel):
    kind: (
        Literal[
            "explicit_range",
            "rolling_window",
            "year_to_date",
            "calendar_year",
            "since",
            "endpoint_patch",
            "same_as_latest_result",
        ]
        | None
    ) = Field(
        default=None,
        description=(
            "Canonical, language-neutral temporal intent. Use this for relative "
            "or semantic windows such as last 12 months or year to date instead "
            "of asking deterministic code to parse localized prose. Use "
            "same_as_latest_result when the user references the latest completed "
            "test's window; the runtime binds the dates from the canonical run."
        ),
    )
    start: str | None = Field(
        default=None,
        description="ISO date, YYYY-MM-DD, or canonical sentinel 'today'.",
    )
    end: str | None = Field(
        default=None,
        description="ISO date, YYYY-MM-DD, or canonical sentinel 'today'.",
    )
    day_offset: int | None = Field(
        default=None,
        description=(
            "Optional day offset from anchor for endpoint patches, e.g. -1 for "
            "the previous day. This is canonical machine data, not localized text."
        ),
    )
    count: int | None = Field(default=None, ge=1)
    unit: Literal["day", "week", "month", "quarter", "year"] | None = None
    anchor: Literal["today", "current_date"] | None = "today"
    year: int | None = Field(default=None, ge=1900, le=2100)
    endpoint: Literal["start", "end"] | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    evidence: str | None = Field(
        default=None,
        description="Short user-message span supporting this intent.",
    )


class LLMStrategyDraft(BaseModel):
    raw_user_phrasing: str | None = None
    language: str | None = Field(
        default=None,
        description=(
            "Detected user-message language as a BCP-47-style code such as en, "
            "es, or es-419. This guides user-facing prose and bounded parsers; "
            "executable fields still use canonical Argus values."
        ),
    )
    strategy_type: str | None = None
    strategy_thesis: str | None = None
    asset_universe: list[str] = Field(default_factory=list)
    asset_universe_operation: Literal["append", "add", "replace"] | None = Field(
        default=None,
        description=(
            "Patch operation for asset_universe when editing an anchored artifact. "
            "Use append/add when the user adds traded assets to the current setup, "
            "and replace when the user swaps the traded assets."
        ),
    )
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
    date_range_raw_text: str | None = Field(
        default=None,
        description=(
            "Exact short user text span that expresses the requested date or time "
            "window, for example 'last 8 months' or 'enero 2024 a marzo 2024'."
        ),
    )
    date_range_intent: LLMDateRangeIntent | None = None
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
    evidence_spans: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Short user-message spans that justify extracted canonical fields, keyed "
            "by field name such as strategy_type, asset_universe, date_range, "
            "capital_amount, cadence, or comparison_baseline."
        ),
    )
    extra_parameters: dict[str, Any] = Field(default_factory=dict)


class LLMSimplificationOption(BaseModel):
    label: str
    replacement_values: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Canonical action payload for this simplification option. Labels are "
            "display text only; executable recovery must use this structured "
            "payload, for example {'strategy_type': 'buy_and_hold'}."
        ),
    )


class LLMUnsupportedConstraint(BaseModel):
    category: str
    raw_value: str
    explanation: str
    simplification_options: list[LLMSimplificationOption] = Field(
        default_factory=list,
        description=(
            "Language-neutral simplification actions. Populate replacement_values "
            "with the canonical payload; keep label as display text."
        ),
    )
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
    language: str | None = None
    strategy_type: str | None = Field(
        default=None,
        description=(
            "Canonical executable strategy family selected by the current user "
            "message. Use buy_and_hold when the user asks in any language to buy, "
            "hold, keep, compare performance, or test one asset over a period "
            "without a separate entry rule, including counterfactual performance "
            "questions such as what would have happened if the user bought or owned "
            "the asset over a period. Use dca_accumulation for recurring "
            "fixed-amount buys and populate cadence plus recurring_contribution. "
            "Use indicator_threshold for supported indicator threshold rules, and "
            "signal_strategy for supported signal/crossover rules. Leave null only "
            "when no executable family is semantically selected."
        ),
    )
    strategy_thesis: str | None = None
    asset_universe: list[str] = Field(
        default_factory=list,
        description=(
            "Primary traded/tested assets explicitly stated by the user. Include "
            "ticker symbols or asset names in any language, such as AAPL, Apple, "
            "ETH, or Bitcoin. Do not put benchmark/reference/comparison assets "
            "here unless the user explicitly says to buy, hold, or test them as "
            "traded assets."
        ),
    )
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
            "date only when it appears as an endpoint. If the user gives only a start "
            "or only an end, preserve only that endpoint and include date_range in "
            "missing_required_fields."
        ),
    )
    date_range_raw_text: str | None = None
    date_range_intent: LLMDateRangeIntent | None = Field(
        default=None,
        description=(
            "Canonical temporal intent for relative or semantic windows. For "
            "phrases equivalent to last/past/previous N days, weeks, months, "
            "quarters, or years in any language, return kind=rolling_window with "
            "count, unit, anchor=today, confidence, and evidence. For current-year "
            "to current-date windows in any language, return kind=year_to_date "
            "with confidence and evidence."
        ),
    )
    comparison_baseline: str | None = Field(
        default=None,
        description=(
            "User-stated benchmark/comparison asset such as SPY, QQQ, BTC, or IWM. "
            "Leave null only when the user did not state a benchmark."
        ),
    )
    capital_amount: float | None = Field(
        default=None,
        description=(
            "User-stated cash amount normalized as a number. For non-recurring "
            "buy-and-hold or backtest requests, this is the starting capital to "
            "test or invest with, even when the user says it in another language. "
            "For recurring DCA requests, this is the recurring contribution "
            "amount. Examples: $1k -> 1000, 10000 dollars -> 10000."
        ),
    )
    recurring_contribution: float | None = Field(
        default=None,
        description=(
            "User-stated contribution for each recurring DCA buy. Populate this "
            "for recurring fixed-amount purchases; keep capital_amount equal to "
            "the same amount unless the user separately states a total budget."
        ),
    )
    cadence: str | None = Field(
        default=None,
        description=(
            "Canonical recurring-buy cadence for DCA, such as daily, weekly, "
            "biweekly, monthly, or quarterly. Leave null when no recurring cadence "
            "is stated."
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
    evidence_spans: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Bounded snippets from the current user message that support populated "
            "canonical fields. Evidence spans are provenance only and never replace "
            "strategy_type, asset_universe, comparison_baseline, date_range_intent, "
            "capital_amount, recurring_contribution, or cadence. If evidence "
            "identifies a supported strategy, asset, benchmark, time window, "
            "contribution, or cadence, the corresponding canonical field must also "
            "be populated."
        ),
    )


class FocusedDateWindowExtraction(BaseModel):
    has_date_window: bool = Field(
        description=(
            "True when the current user message states a backtest date window, "
            "lookback window, start/end date, or other temporal constraint."
        )
    )
    date_range_raw_text: str | None = Field(
        default=None,
        description=(
            "Shortest exact user-message span that expresses the temporal window. "
            "Keep the user's language; this is provenance, not executable input."
        ),
    )
    date_range_intent: LLMDateRangeIntent | None = Field(
        default=None,
        description=(
            "Canonical language-neutral temporal intent. Required for relative or "
            "semantic windows. A present-anchored lookback duration is complete "
            "without explicit calendar endpoints. Do not calculate endpoint dates "
            "for relative windows."
        ),
    )
    date_range: dict[str, str] | None = Field(
        default=None,
        description=(
            "Use only when the user explicitly states calendar endpoints. Values "
            "must be ISO dates or the canonical sentinel today/current_date. Never "
            "put relative, shorthand, or prose windows in start/end; use "
            "date_range_intent for those."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: str | None = Field(
        default=None,
        description="Short user-message span supporting the temporal extraction.",
    )
