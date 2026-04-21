"""
API-layer Pydantic schemas.

Separate from engine.py schemas to keep API contracts clean
and allow versioning independently of core engine models.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class AuthRequest(BaseModel):
    """Unified auth request supporting email/password and social SSO."""

    mode: Literal["login", "signup"] = Field(
        default="login", description="login or signup"
    )
    provider: Optional[Literal["email", "google", "discord"]] = Field(default="email")
    email: Optional[str] = None
    password: Optional[str] = None
    oauth_token: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------


class BacktestRequest(BaseModel):
    """API backtest request payload (XOR)."""

    strategy_id: Optional[str] = None

    # Inline strategy definition (XOR with strategy_id)
    name: Optional[str] = None
    symbols: Optional[List[str]] = None
    timeframe: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    entry_criteria: Optional[List[Dict[str, Any]]] = None
    exit_criteria: Optional[List[Dict[str, Any]]] = None
    stop_loss_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    take_profit_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    indicators_config: Optional[Dict[str, Any]] = None
    patterns: Optional[List[str]] = None
    slippage: float = Field(default=0.001, ge=0.0, le=0.05)
    fees: float = Field(default=0.001, ge=0.0, le=0.02)

    # Execution Forge (Institutional Physics)
    side: Literal["long", "short"] = Field(default="long", description="Trade direction")
    participation_rate: float = Field(default=0.1, ge=0.001, le=1.0)
    execution_priority: float = Field(default=1.0, ge=0.0, le=1.0)
    va_sensitivity: float = Field(default=1.0, ge=0.0, le=5.0)
    slippage_model: Literal["fixed", "vol_adjusted"] = Field(default="vol_adjusted")

    @model_validator(mode="after")
    def validate_xor(self):
        has_id = bool(self.strategy_id)
        has_inline = bool(self.symbols or self.timeframe)

        if has_id == has_inline:
            raise ValueError(
                "Must provide either strategy_id OR inline strategy fields (not both, not neither)"
            )

        if has_inline:
            missing = []
            if not self.symbols:
                missing.append("symbols")
            if not self.timeframe:
                missing.append("timeframe")
            if not self.start_date:
                missing.append("start_date")
            if not self.end_date:
                missing.append("end_date")
            if missing:
                raise ValueError(
                    f"Missing required inline strategy fields: {', '.join(missing)}"
                )

        return self


class TradeSnippet(BaseModel):
    entry_time: str
    entry_price: float
    exit_price: float
    pnl_pct: float


class RealityGapMetrics(BaseModel):
    slippage_impact_pct: float
    fee_impact_pct: float
    vol_hazard_pct: float = Field(default=0.0)
    fidelity_score: float = Field(default=1.0)
    assets: Optional[Dict[str, float]] = None


class BacktestResults(BaseModel):
    total_return_pct: float
    win_rate: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    profit_factor: float
    expectancy: float
    max_drawdown_pct: float
    equity_curve: List[float]
    ideal_equity_curve: List[float] = Field(default_factory=list)
    benchmark_equity_curve: List[float] = Field(default_factory=list)
    benchmark_symbol: Optional[str] = None
    trades: List[TradeSnippet]
    reality_gap_metrics: RealityGapMetrics
    pattern_breakdown: Dict[str, int]


class BacktestResponse(BaseModel):
    id: str
    config_snapshot: Dict[str, Any]
    results: BacktestResults


# ---------------------------------------------------------------------------
# Simulation history
# ---------------------------------------------------------------------------


class SimulationLogEntry(BaseModel):
    id: str
    strategy_name: str
    symbols: List[str]
    timeframe: str
    status: Literal["pending", "completed", "failed", "processing"]
    total_return_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: Optional[int] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    calmar_ratio: Optional[float] = None
    avg_trade_duration: Optional[str] = None
    fidelity_score: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class PaginatedHistory(BaseModel):
    simulations: List[SimulationLogEntry]
    total: int
    next_cursor: Optional[str] = None


class ProfileUpdate(BaseModel):
    """Schema for updating user profile preferences."""

    theme: Optional[str] = None
    lang: Optional[str] = None
    onboarding_completed: Optional[bool] = None
    onboarding_step: Optional[str] = None
    onboarding_intent: Optional[str] = None


class SSORequest(BaseModel):
    """Schema for SSO sign-in request."""

    provider: Literal["google", "discord"]
    redirect_to: str


class SSOResponse(BaseModel):
    """Schema for SSO sign-in response."""

    auth_url: str


TelemetryEventName = Literal[
    "onboarding_complete",
    "draft_success",
    "draft_fail",
    "draft_saved",
    "backtest_success",
    "backtest_fail",
    "logout",
]


class TelemetryEventPayload(BaseModel):
    """Schema for frontend telemetry event ingestion."""

    event: TelemetryEventName
    timestamp: datetime
    properties: Dict[str, Any] = Field(default_factory=dict)


class TelemetryAcceptedResponse(BaseModel):
    """Response schema for successful telemetry ingestion."""

    status: str


class PaginatedHistoryResponse(BaseModel):
    simulations: List[SimulationLogEntry]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Strategies CRUD
# ---------------------------------------------------------------------------


class StrategyCreate(BaseModel):
    """Payload for creating or updating a strategy draft."""

    name: str = Field(..., max_length=120)
    symbols: List[str] = Field(default_factory=list, min_length=1)
    timeframe: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    entry_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    exit_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    stop_loss_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    take_profit_pct: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    indicators_config: Dict[str, Any] = Field(default_factory=dict)
    patterns: List[str] = Field(default_factory=list)
    slippage: float = Field(
        default=0.001,
        ge=0.0,
        le=0.05,
        description="Slippage percentage (e.g., 0.001 = 0.1%)",
    )
    fees: float = Field(
        default=0.001,
        ge=0.0,
        le=0.02,
        description="Trading fees percentage (e.g., 0.001 = 0.1%)",
    )
    capital: float = Field(default=100000.0, ge=100.0)
    trade_direction: Literal["LONG", "SHORT", "BOTH"] = Field(default="LONG")
    participation_rate: float = Field(default=0.1, ge=0.001, le=1.0)
    execution_priority: float = Field(default=1.0, ge=0.0, le=1.0)
    va_sensitivity: float = Field(default=1.0, ge=0.0, le=5.0)
    slippage_model: Literal["fixed", "vol_adjusted"] = Field(default="vol_adjusted")

    @model_validator(mode="before")
    @classmethod
    def hydrate_execution_fields_from_indicators(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        indicators_config = data.get("indicators_config")
        if not isinstance(indicators_config, dict):
            return data

        for field in (
            "capital",
            "trade_direction",
            "participation_rate",
            "execution_priority",
            "va_sensitivity",
            "slippage_model",
        ):
            if data.get(field) is None and field in indicators_config:
                data[field] = indicators_config[field]
        return data

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe_strategy(cls, v: str) -> str:
        allowed = {"1Day", "1Hour", "4Hour", "15Min", "1Min", "1d", "4h", "1h", "15m"}
        if v not in allowed:
            raise ValueError(f"timeframe must be one of {allowed}")
        return v


class StrategyResponse(StrategyCreate):
    """Response model for a strategy, includes db fields."""

    id: str
    user_id: str
    executed_at: Optional[datetime] = None


class PaginatedStrategiesResponse(BaseModel):
    strategies: List[StrategyResponse]
    next_cursor: Optional[str] = None


class AgentDraftRequest(BaseModel):
    """Request payload for generating a strategy draft via agent."""

    prompt: str = Field(
        ...,
        max_length=1000,
        description="Natural language prompt describing the strategy",
    )


class AgentDraftResponse(BaseModel):
    """Response containing the generated strategy draft and explanation."""

    draft: StrategyCreate
    ai_explanation: str
