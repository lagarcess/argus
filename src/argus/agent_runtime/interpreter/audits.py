"""Structured LLM audit-response schemas (Pydantic models) used by the interpreter.

Behavior-preserving relocation (issue #131). Pure data schemas with no dependency on
interpreter logic, so this module is an import sink for the audit modules and the facade."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
)

from argus.agent_runtime.stages.interpret_types import (
    CapabilityQuestionFocus,
    ContextQuestionFocus,
    ResultFollowupFocus,
)


class CapabilitySideQuestionAudit(BaseModel):
    is_capability_question: bool = Field(
        description=(
            "True only when the current user message is asking what Argus supports, "
            "what it can run, what a supported concept means, or what limits apply."
        )
    )
    focus: CapabilityQuestionFocus | None = Field(
        default=None,
        description=(
            "Capability focus when is_capability_question is true. Use "
            "supported_indicators, supported_strategies, limits, assets, or general."
        ),
    )
    assistant_response: str | None = Field(
        default=None,
        description=(
            "Optional warm answer. Leave null when runtime should compose from the "
            "capability contract."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ContextQuestionAudit(BaseModel):
    is_context_question: bool = Field(
        description=(
            "True only when the current user message asks for broad market, macro, "
            "corporate-event, or movers context rather than supplying executable "
            "strategy details."
        )
    )
    focus: ContextQuestionFocus | None = Field(
        default=None,
        description=(
            "Context focus when is_context_question is true. Use macro_context, "
            "corporate_events, or market_movers."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AssetGroundingAudit(BaseModel):
    grounded_symbols: list[str] = Field(
        default_factory=list,
        description=(
            "Subset of the extracted symbols that the current user message clearly "
            "intended as assets. Use the symbols exactly as provided in the audit prompt."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AssetAnswerCandidateAudit(BaseModel):
    candidate_symbols: list[str] = Field(
        default_factory=list,
        description=(
            "One to three likely public market symbols for the current asset answer, "
            "normalized as tickers or crypto symbols. A common public-company or "
            "public-asset name is a valid answer even when the user did not type the "
            "ticker. Return likely candidates in preference order when the answer is "
            "recognizable. Leave empty only when there is no credible candidate, the "
            "answer is unsupported, or the answer is not an asset answer."
        ),
    )
    needs_clarification: bool = Field(
        default=False,
        description=(
            "True when multiple plausible assets remain and the user should choose "
            "instead of the runtime guessing. If candidate_symbols is non-empty, "
            "the runtime will still validate those candidates in order before "
            "falling back to clarification."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class StrategyFamilyContinuityAudit(BaseModel):
    should_rebind_strategy_family: bool = Field(
        description=(
            "True only when the user is continuing a specific visible strategy-family "
            "setup from recent conversation and the primary interpretation chose the "
            "wrong executable family."
        )
    )
    strategy_type: str | None = Field(
        default=None,
        description=(
            "Executable strategy family to use when rebinding is needed. Use one of "
            "buy_and_hold, dca_accumulation, indicator_threshold, or signal_strategy."
        ),
    )
    total_budget_not_recurring: bool = Field(
        default=False,
        description=(
            "True when a money amount in the current interpretation is a total budget, "
            "starting principal, or cap rather than a recurring DCA contribution."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DcaContributionRoleAudit(BaseModel):
    recurring_contribution_explicit: bool = Field(
        description=(
            "True only when the current user message clearly states the money amount "
            "as the amount invested on each recurring DCA purchase."
        )
    )
    total_budget_not_recurring: bool = Field(
        description=(
            "True when the money amount is a total budget, starting capital, or "
            "capital available across the whole DCA plan rather than each purchase."
        )
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DcaContractAudit(BaseModel):
    is_recurring_buy_request: bool = Field(
        description=(
            "True only when the current user message is asking for a DCA or "
            "recurring fixed-dollar buy backtest."
        )
    )
    recurring_contribution_amount: float | None = Field(
        default=None,
        description=(
            "The per-purchase contribution explicitly stated by the user. Leave "
            "null when the message only states total budget, starting principal, "
            "or cap."
        ),
    )
    cadence: str | None = Field(
        default=None,
        description=(
            "User-stated recurring cadence normalized to one allowed DCA cadence "
            "such as daily, weekly, biweekly, monthly, or quarterly. Leave null "
            "when absent."
        ),
    )
    total_budget_amount: float | None = Field(
        default=None,
        description=(
            "Optional total budget, starting principal, or contribution cap stated "
            "for the whole DCA plan. Do not use this as the recurring contribution."
        ),
    )
    total_budget_source: str | None = Field(
        default=None,
        description=(
            "Semantic role for total_budget_amount, for example cap, max_budget, "
            "total_budget, starting_capital, or initial_capital."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PendingResponseOptionSelectionAudit(BaseModel):
    is_selection: bool = Field(
        description=(
            "True when the current user message semantically selects one of the "
            "pending response-intent options."
        )
    )
    selected_option_index: int | None = Field(
        default=None,
        description=(
            "Zero-based index of the selected option from the provided option list. "
            "Leave null when no option is selected."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class StatedRunFieldFidelityAudit(BaseModel):
    capital_amount: float | None = Field(
        default=None,
        description=(
            "Starting capital explicitly stated by the current user message, "
            "normalized as a number. Examples: 10k -> 10000, $500 -> 500, "
            "100k -> 100000, 100000 -> 100000 when the message uses that "
            "plain number or shorthand as the amount to test or invest. "
            "Leave null when the user did not state starting capital. Do not "
            "treat dates, indicator windows, percentages, or asset names as "
            "capital. For DCA or recurring buys, do not put the per-purchase "
            "contribution here; use recurring_contribution_amount."
        ),
    )
    recurring_contribution_amount: float | None = Field(
        default=None,
        description=(
            "For DCA or recurring-buy requests only: the amount explicitly stated "
            "as each recurring purchase contribution, normalized as a number. "
            "Leave null when the current user message gives only a total budget, "
            "starting principal, cap, or no per-purchase contribution."
        ),
    )
    cadence: str | None = Field(
        default=None,
        description=(
            "For DCA or recurring-buy requests only: user-stated cadence normalized "
            "to daily, weekly, biweekly, monthly, or quarterly. Leave null when "
            "the current user message did not state cadence."
        ),
    )
    timeframe: str | None = Field(
        default=None,
        description=(
            "User-stated bar interval, normalized to 1h, 4h, or 1D when present. "
            "Leave null when the user did not state a timeframe."
        ),
    )
    date_range: str | dict[str, str] | None = Field(
        default=None,
        description=(
            "User-stated date range. Preserve today/current as today or the runtime "
            "date only when the user stated it. If the user stated only one endpoint, "
            "return only that endpoint. Leave null when the user did not state a date "
            "range."
        ),
    )
    comparison_baseline: str | None = Field(
        default=None,
        description=(
            "Benchmark or comparison asset explicitly stated by the current user "
            "message. This is language-agnostic: if the current message states "
            "an asset as a benchmark, reference, baseline, against/versus target, "
            "or comparison target, return that asset here. Leave null when the "
            "user did not state one."
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class StatedStartingCapitalAudit(BaseModel):
    starting_capital: float | None = Field(
        default=None,
        description=(
            "Starting capital explicitly stated by the current user message, "
            "normalized as a number. Return null when the current message does "
            "not state starting capital. Preserve plain numeric allocation "
            "amounts in any language when they are used as the amount to test, "
            "invest, allocate, put on, or use as capital."
        ),
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the starting_capital extraction. Use high confidence "
            "for an exact current-message amount; leave the default acceptable "
            "confidence when starting_capital is directly present but no separate "
            "confidence value is needed."
        ),
    )


class SupportedStrategyCapabilityConflictAudit(BaseModel):
    selected_strategy_type: str | None = Field(
        default=None,
        description=(
            "Canonical executable strategy family when the current user message "
            "semantically selects a supported Alpha strategy. Use buy_and_hold or "
            "dca_accumulation only when the message itself supports that choice. "
            "Leave null when the request contains unsupported custom logic or "
            "does not clearly select a supported strategy."
        ),
    )
    drop_unsupported_strategy_logic: bool = Field(
        description=(
            "True only when the unsupported_strategy_logic constraint is a model "
            "contradiction because the current user message asks for a supported "
            "buy_and_hold or dca_accumulation run without any extra unsupported "
            "entry, exit, fundamental, sentiment, event, custom scripting, or "
            "brokerage/trading rule."
        ),
    )
    keep_unsupported_strategy_logic: bool = Field(
        description=(
            "True when the current user message includes an extra unsupported "
            "strategy rule or condition beyond the supported canonical strategy."
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class ExecutableStrategyGroundingAudit(BaseModel):
    outcome: str = Field(
        description="grounded when the executable draft faithfully matches the user message; otherwise needs_clarification."
    )
    assistant_response: str | None = Field(
        default=None,
        description="Warm clarification to show the user when the draft was over-simplified.",
    )
    missing_required_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class LatestResultRoutingAudit(BaseModel):
    targets_latest_result: bool = Field(
        description=(
            "True when the current user message should be answered from the "
            "latest completed result artifact instead of general capability copy."
        )
    )
    save_requested: bool = Field(
        default=False,
        description=(
            "True when the user is asking to save, keep, bookmark, or promote "
            "the latest completed result artifact."
        ),
    )
    focus: ResultFollowupFocus | None = Field(
        default=None,
        description=(
            "Closest result follow-up focus when targets_latest_result is true."
        ),
    )
    fact_key: str | None = Field(
        default=None,
        description=(
            "Optional canonical result fact key the user asked about, such as "
            "peak_date, peak_value, max_drawdown, drawdown_date, total_return, "
            "benchmark_delta, date_range, symbols, benchmark_symbol, or an "
            "unsupported metric key like sortino_ratio."
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class LatestResultSaveAudit(BaseModel):
    save_requested: bool = Field(
        description=(
            "True only when the user is asking to save, keep, bookmark, or "
            "promote the latest completed result artifact."
        )
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
