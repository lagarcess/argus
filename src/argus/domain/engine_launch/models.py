from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

LaunchStrategyType = Literal[
    "buy_and_hold",
    "dca_accumulation",
    "indicator_threshold",
]
SizingMode = Literal["capital_amount", "position_size"]
Cadence = Literal["daily", "weekly", "monthly", "quarterly"]
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


class LaunchBacktestRequest(BaseModel):
    strategy_type: LaunchStrategyType
    symbol: str
    symbols: list[str] = Field(default_factory=list)
    timeframe: str
    date_range: DateRange
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    sizing_mode: SizingMode
    capital_amount: float | None = None
    position_size: float | None = None
    cadence: Cadence | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_rules: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_symbol: str

    @model_validator(mode="after")
    def validate_request_shape(self) -> "LaunchBacktestRequest":
        self.symbol = self.symbol.strip().upper()
        self.symbols = _normalize_symbols(self.symbols, fallback_symbol=self.symbol)

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

        if self.strategy_type == "dca_accumulation":
            if self.cadence is None:
                raise ValueError("cadence_required")
        elif self.cadence is not None:
            raise ValueError("cadence_not_applicable")

        return self


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
