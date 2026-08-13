from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from argus.domain.backtesting.date_window import validate_backtest_date_window
from argus.domain.backtesting.types import CoverageAdjustmentReason

LaunchStrategyType = Literal[
    "buy_and_hold",
    "dca_accumulation",
    "indicator_threshold",
    "signal_strategy",
]
AssetClass = Literal["equity", "crypto", "currency_pair"]
SizingMode = Literal["capital_amount", "position_size"]
Cadence = Literal["daily", "weekly", "biweekly", "monthly", "quarterly"]
ExecutionStatus = Literal[
    "succeeded",
    "blocked_unsupported",
    "blocked_invalid_input",
    "failed_upstream",
    "failed_internal",
]


class DateRange(BaseModel):
    start: str
    end: str


class CoveragePreflight(BaseModel):
    schema_version: str = "market_data_coverage_v1"
    outcome: Literal["full_coverage", "adjusted_coverage"]
    requested_date_range: DateRange
    effective_date_range: DateRange
    adjustment_reason: CoverageAdjustmentReason | None = Field(
        default=None,
        exclude=True,
    )
    preflight_id: str
    observations_by_symbol: dict[str, int] = Field(default_factory=dict)


class LaunchBacktestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    strategy_type: LaunchStrategyType
    symbol: str
    symbols: list[str] = Field(default_factory=list)
    asset_class: AssetClass | None = None
    timeframe: str
    date_range: DateRange
    requested_date_range: DateRange | None = None
    coverage_preflight: CoveragePreflight | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    sizing_mode: SizingMode
    capital_amount: float | None = None
    position_size: float | None = None
    # The recurring plan's two money roles. ``capital_amount`` carries the
    # contribution for DCA because every stored card already does; the seed has
    # its own field so neither role can be read off the other.
    starting_capital: float | None = None
    recurring_contribution: float | None = None
    cadence: Cadence | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_rules: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_symbol: str
    execution_realism: dict[str, Any] | None = Field(
        default=None,
        alias="_execution_realism",
    )
    language: str = "en"

    @model_validator(mode="after")
    def validate_request_shape(self) -> "LaunchBacktestRequest":
        self.symbol = self.symbol.strip().upper()
        self.symbols = _normalize_symbols(self.symbols, fallback_symbol=self.symbol)
        self.language = self.language.strip() or "en"

        if self.strategy_type == "dca_accumulation":
            if self.cadence is None:
                raise ValueError("cadence_required")
            self._reconcile_dca_capital_roles()
        else:
            if self.cadence is not None:
                raise ValueError("cadence_not_applicable")
            if self.starting_capital is not None:
                raise ValueError("starting_capital_not_applicable")
            if self.recurring_contribution is not None:
                raise ValueError("recurring_contribution_not_applicable")

        if self.sizing_mode == "capital_amount":
            if self.capital_amount is None:
                raise ValueError("capital_amount_required")
            if self.position_size is not None:
                raise ValueError("position_size_not_applicable")
        if self.sizing_mode == "position_size":
            if self.position_size is None:
                raise ValueError("position_size_required")
            if self.capital_amount is not None:
                raise ValueError("capital_amount_not_applicable")

        try:
            start = date.fromisoformat(self.date_range.start)
            end = date.fromisoformat(self.date_range.end)
        except ValueError as exc:
            raise ValueError("invalid_date_range") from exc
        validate_backtest_date_window(start=start, end=end)

        requested_start, requested_end = start, end
        if self.requested_date_range is not None:
            try:
                requested_start = date.fromisoformat(self.requested_date_range.start)
                requested_end = date.fromisoformat(self.requested_date_range.end)
            except ValueError as exc:
                raise ValueError("invalid_date_range") from exc
            validate_backtest_date_window(
                start=requested_start,
                end=requested_end,
            )

        if self.cadence is not None:
            from argus.domain.dca_capital import (
                contribution_period_window,
                validate_contribution_period_fits_window,
            )

            # The card advertises which periods it will accept from the same
            # owner, so the two cannot offer and refuse the same period.
            window_start, window_end = contribution_period_window(
                requested=(requested_start, requested_end),
                effective=(start, end),
                adjustment_reason=(
                    self.coverage_preflight.adjustment_reason
                    if self.coverage_preflight is not None
                    else None
                ),
            )
            validate_contribution_period_fits_window(
                self.cadence,
                start=window_start,
                end=window_end,
            )

        return self

    def _reconcile_dca_capital_roles(self) -> None:
        """Pin the contribution to one value both spellings agree on.

        ``capital_amount`` is the older spelling of the contribution and stored
        cards still carry it. Where both are present they must state the same
        number, so neither spelling can quietly override the other, and the
        seed is never consulted to fill either one.
        """
        if self.sizing_mode == "position_size":
            if self.recurring_contribution is not None:
                raise ValueError("recurring_contribution_not_applicable")
            return
        if (
            self.recurring_contribution is not None
            and self.capital_amount is not None
            and float(self.recurring_contribution) != float(self.capital_amount)
        ):
            raise ValueError("dca_capital_role_conflict")
        if self.recurring_contribution is None:
            self.recurring_contribution = self.capital_amount
        elif self.capital_amount is None:
            self.capital_amount = self.recurring_contribution


def _normalize_symbols(symbols: list[str], *, fallback_symbol: str) -> list[str]:
    normalized: list[str] = []
    for value in symbols:
        symbol = str(value).strip().upper()
        if symbol and symbol not in normalized:
            normalized.append(symbol)
    if not normalized and fallback_symbol:
        normalized.append(fallback_symbol.strip().upper())
    return normalized


class LaunchExecutionEnvelope(BaseModel):
    execution_status: ExecutionStatus
    resolved_strategy: dict[str, Any]
    resolved_parameters: dict[str, Any]
    metrics: dict[str, Any]
    benchmark_metrics: dict[str, Any]
    assumptions: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    artifact_references: list[dict[str, Any]] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    failure_category: str | None = None
    failure_reason: str | None = None
