"""Typed backtest inputs shared by extraction and the declared callable.

StrategySummary stays the durable canonical artifact. These input facts retain
meaning needed to prepare that artifact before any confirmation can be shown.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from argus.agent_runtime.state.models import ResolutionProvenance, StrategySummary
from argus.domain.strategy_template_contract import RegisteredStrategyTemplate


class LLMRiskRule(BaseModel):
    type: str
    value_pct: float | None = None
    mode: str | None = None


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
            "future_window",
        ]
        | None
    ) = Field(
        default=None,
        description=(
            "Canonical, language-neutral temporal intent. Use this for relative "
            "or semantic windows such as last 12 months or year to date instead "
            "of asking deterministic code to parse localized prose. Use "
            "same_as_latest_result when the user references the latest completed "
            "test's window; the runtime binds the dates from the canonical run. "
            "Use future_window whenever the user's period points forward from "
            "today — in ten years, over the next 3 years, by 2031, dentro de "
            "diez años — with count/unit or year filled and the exact phrase as "
            "evidence. A future_window is never a historical test window: do "
            "not emit rolling_window or calendar dates for a forward-looking "
            "period."
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
    count: float | None = Field(
        default=None,
        gt=0,
        description=(
            "Quantity of unit for rolling windows; may be fractional. The "
            "last 8.5 months is count=8.5 unit=month, and hace 2,5 meses is "
            "count=2.5 unit=month. Never round or truncate a stated "
            "fractional duration; deterministic date math computes from it."
        ),
    )
    unit: Literal["day", "week", "month", "quarter", "year"] | None = None
    anchor: Literal["today", "current_date"] | None = "today"
    year: int | None = Field(default=None, ge=1900, le=2100)
    endpoint: Literal["start", "end"] | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    evidence: str | None = Field(
        default=None,
        description="Short user-message span supporting this intent.",
    )


class BacktestStrategyInput(BaseModel):
    raw_user_phrasing: str | None = None
    language: str | None = Field(
        default=None,
        description=(
            "Detected user-message language as a BCP-47-style code such as en, "
            "es, or es-419. This guides user-facing prose and bounded parsers; "
            "executable fields still use canonical Argus values."
        ),
    )
    requested_strategy_template: RegisteredStrategyTemplate | None = Field(
        default=None,
        description=(
            "Canonical registered strategy-template identity requested by the user. "
            "Set this for both executable and recognized draft-only templates. Keep "
            "it separate from strategy_type, which is the execution family, so a "
            "recognized non-executable template is never silently converted into a "
            "different runnable strategy."
        ),
    )
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
    asset_inclusions: list[str] = Field(
        default_factory=list,
        description=(
            "Role-separated canonical asset symbols the current user explicitly "
            "includes in an anchored artifact edit. Do not copy carried assets or "
            "symbols the user excludes."
        ),
    )
    asset_exclusions: list[str] = Field(
        default_factory=list,
        description=(
            "Role-separated canonical asset symbols the current user explicitly "
            "excludes from an anchored artifact edit. Do not treat exclusions as "
            "members of asset_universe."
        ),
    )
    asset_universe_operation: Literal["append", "add", "replace"] | None = Field(
        default=None,
        description=(
            "Patch operation for asset_universe when editing an anchored artifact. "
            "Use append/add when the user adds traded assets to the current setup, "
            "and replace when the user swaps the traded assets."
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
    date_range: str | dict[str, str] | None = Field(
        default=None,
        description=(
            "User-stated test window. Preserve today/current as 'today' or the runtime "
            "date only when it appears as an endpoint. If the user gives only a start "
            "or only an end, preserve only that endpoint and include date_range in "
            "missing_required_fields."
        ),
    )
    date_range_raw_text: str | None = Field(
        default=None,
        description=(
            "Exact short user text span that expresses the requested date or time "
            "window, for example 'last 8 months' or 'enero 2024 a marzo 2024'."
        ),
    )
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
    sizing_mode: str | None = None
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
        json_schema_extra={"x-argus-capital-role": "recurring_contribution"},
        description="Amount invested on each recurrence. A total plan budget is not a recurring contribution. Leave this unknown if the user has not supplied a per-purchase amount.",
    )
    initial_capital: float | None = Field(
        default=None,
        json_schema_extra={"x-argus-capital-role": "starting_capital"},
        description="Money invested once at the start. Never put a total investment ceiling or available-cash budget here. Zero is a known starting amount.",
    )
    total_capital: float | None = Field(
        default=None,
        json_schema_extra={"x-argus-capital-role": "total_capital"},
        description="Maximum total invested, available-cash budget, or contribution ceiling for the plan. It never becomes the starting amount or recurring contribution; the current engine must ask for a supported alternative.",
    )
    position_size: float | None = None
    risk_rules: list[LLMRiskRule] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    comparison_baseline: str | None = Field(
        default=None,
        description=(
            "User-stated benchmark/comparison asset such as SPY, QQQ, BTC, or IWM. "
            "Leave null only when the user did not state a benchmark."
        ),
    )
    refinement_of: str | None = None
    field_provenance: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Origin of each populated strategy field. Use explicit_user for fields "
            "stated by the user, inherited for carried context, and default only "
            "for values injected without a user request. In particular, an explicit "
            "buy-and-hold request is never a default strategy_type. Evidence spans "
            "must support user-stated fields; missing provenance is not a default. "
            "Preserve the existing capital-role provenance for capital fields."
        ),
    )
    evidence_spans: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Short user-message spans that justify extracted canonical fields, keyed "
            "by field name such as strategy_type, asset_universe, date_range, "
            "capital_amount, cadence, comparison_baseline, fee_rate, or slippage. "
            "For populated fee_rate or slippage, copy the exact bounded phrase from "
            "the current user message into the corresponding evidence key; canonical "
            "explicit-user provenance is derived from that evidence."
        ),
    )
    extra_parameters: dict[str, Any] = Field(default_factory=dict)

    resolution_provenance: list[ResolutionProvenance] = Field(default_factory=list)
    fee_rate: float | None = Field(
        default=None,
        json_schema_extra={"x-argus-runtime-extension": True},
        description="Modeled fee as a decimal rate; 10 basis points is 0.001. Preserve explicit zero. Include its bounded user quote in evidence_spans.fee_rate.",
    )
    slippage: float | None = Field(
        default=None,
        json_schema_extra={"x-argus-runtime-extension": True},
        description="Modeled slippage as a decimal rate; 5 basis points is 0.0005. Preserve explicit zero. Include its bounded user quote in evidence_spans.slippage.",
    )

    def declared_capital_roles(self) -> dict[str, str]:
        roles = {}
        for name, field in type(self).model_fields.items():
            metadata = field.json_schema_extra
            if not isinstance(metadata, dict) or getattr(self, name) is None:
                continue
            role = metadata.get("x-argus-capital-role")
            if isinstance(role, str):
                roles[name] = role
        return roles

    @model_validator(mode="before")
    @classmethod
    def read_legacy_extension_fields(cls, value: Any) -> Any:
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="python")
        if not isinstance(value, dict):
            return value
        extra = value.get("extra_parameters")
        if not isinstance(extra, dict):
            return value
        payload = dict(value)
        for name in cls.model_fields:
            if name not in extra:
                continue
            current = payload.get(name)
            inherited = extra[name]
            if current is None:
                payload[name] = inherited
            elif inherited is not None:
                adapter: TypeAdapter[Any] = TypeAdapter(cls.model_fields[name].annotation)
                if adapter.validate_python(current) != adapter.validate_python(inherited):
                    raise ValueError(f"Conflicting values for backtest input {name}")
        return payload

    @classmethod
    def from_runtime_strategy(cls, strategy: StrategySummary) -> BacktestStrategyInput:
        """Read the already-confirmed artifact without interpreting it again."""
        return cls.model_validate(strategy.model_dump(mode="python"))

    def to_runtime_strategy(self) -> StrategySummary:
        """Project prepared facts; this does not perform admission or date math."""
        payload = self.model_dump(mode="python")
        extra = dict(payload.get("extra_parameters") or {})
        for name in type(self).model_fields:
            if name in StrategySummary.model_fields:
                continue
            value = payload.pop(name)
            if value is not None and value != {} and value != []:
                extra[name] = value
        payload["extra_parameters"] = extra
        return StrategySummary.model_validate(payload)
