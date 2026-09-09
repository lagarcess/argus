"""Closed, prose-free subset of the result card's canonical fact bank."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from argus.api.schemas import AssetClass
from argus.domain.benchmark_comparison import BenchmarkComparisonClaim


class ClosedFacts(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", allow_inf_nan=False, strict=True
    )


class ReceiptRuleParameters(ClosedFacts):
    fast: float | None = None
    slow: float | None = None
    signal: float | None = None
    length: float | None = None
    std: float | None = None


class ReceiptRuleSeries(ClosedFacts):
    kind: Literal["price", "volume", "indicator"]
    key: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,31}$")
    field: Literal["open", "high", "low", "close"] | None = None
    period: float | None = None
    output: str | None = Field(default=None, pattern=r"^[a-z_]{1,24}$")
    parameters: ReceiptRuleParameters | None = None

    @model_validator(mode="after")
    def require_series_identity(self) -> "ReceiptRuleSeries":
        if self.kind == "price" and self.field is None:
            raise ValueError("price series requires its field")
        if self.kind == "indicator" and self.key is None:
            raise ValueError("indicator series requires its key")
        return self


class ReceiptRuleCondition(ClosedFacts):
    left: float | ReceiptRuleSeries
    right: float | ReceiptRuleSeries
    operator: Literal["lt", "lte", "gt", "gte", "cross_above", "cross_below"]


class ReceiptRuleGroup(ClosedFacts):
    combinator: Literal["all", "any"] = "all"
    conditions: list[ReceiptRuleCondition] = Field(min_length=1, max_length=20)


class ReceiptRuleSpec(ClosedFacts):
    entry: ReceiptRuleGroup | None = None
    exit: ReceiptRuleGroup | None = None


class ReceiptLegacyRule(ClosedFacts):
    type: str | None = None
    indicator: str | None = None
    period: float | None = None
    threshold: float | None = None
    direction: str | None = None
    fast_indicator: str | None = None
    fast_period: float | None = None
    slow_indicator: str | None = None
    slow_period: float | None = None
    signal_period: float | None = None


class ReceiptStrategy(ClosedFacts):
    strategy_type: str | None = None
    initial_capital: float | None = None
    capital_amount: float | None = None
    recurring_contribution: float | None = None
    contribution_period: str | None = None
    cadence: str | None = None
    entry_rule: ReceiptLegacyRule | None = None
    exit_rule: ReceiptLegacyRule | None = None
    rule_spec: ReceiptRuleSpec | None = None


class ReceiptParameters(ClosedFacts):
    strategy_type: str | None = None
    starting_capital: float | None = None
    recurring_contribution: float | None = None
    cadence: str | None = None
    timeframe: str | None = None
    benchmark_symbol: str | None = None
    indicator: str | None = None
    indicator_period: float | None = None
    entry_threshold: float | None = None
    exit_threshold: float | None = None
    rule_spec: ReceiptRuleSpec | None = None


class ReceiptDates(ClosedFacts):
    start: str
    end: str


class ReceiptConfig(ClosedFacts):
    template: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    date_range: ReceiptDates | None = None
    starting_capital: float | None = None
    timeframe: str | None = None
    benchmark_symbol: str | None = None
    resolved_strategy: ReceiptStrategy | None = None
    resolved_parameters: ReceiptParameters | None = None
    parameters: ReceiptParameters | None = None


class ReceiptFigures(ClosedFacts):
    total_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    delta_vs_benchmark_pct: float | None = None
    benchmark_comparison_claim: BenchmarkComparisonClaim | None = None
    max_drawdown_pct: float | None = None
    gross_total_return_pct: float | None = None
    net_total_return_pct: float | None = None


class ReceiptCosts(ClosedFacts):
    fee_bps: float | None = None
    slippage_bps: float | None = None
    benchmark_treatment: Literal["same_modeled_costs"] | None = None


class ReceiptCardFacts(ClosedFacts):
    execution_costs: ReceiptCosts | None = None


class PublicExcerptFactBank(ClosedFacts):
    symbols: list[str] = Field(min_length=1, max_length=5)
    asset_class: AssetClass | None = None
    benchmark_symbol: str | None = None
    config_snapshot: ReceiptConfig
    figures: ReceiptFigures
    result_card: ReceiptCardFacts
