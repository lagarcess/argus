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
    provider: Optional[Literal["email", "google", "discord"]] = Field(
        default="email"
    )
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
    symbol: Optional[str] = None
    timeframe: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    entry_criteria: Optional[List[Dict[str, Any]]] = None
    exit_criteria: Optional[Dict[str, Any]] = None
    indicators_config: Optional[Dict[str, Any]] = None
    patterns: Optional[List[str]] = None

    @model_validator(mode="after")
    def validate_xor(self):
        has_id = bool(self.strategy_id)
        has_inline = bool(self.symbol or self.timeframe)

        if has_id == has_inline:
            raise ValueError(
                "Must provide either strategy_id OR inline strategy fields (not both, not neither)"
            )

        if has_inline:
            missing = []
            if not self.symbol:
                missing.append("symbol")
            if not self.timeframe:
                missing.append("timeframe")
            if not self.start_date:
                missing.append("start_date")
            if not self.end_date:
                missing.append("end_date")
            if missing:
                raise ValueError(f"Missing required inline strategy fields: {', '.join(missing)}")

        return self


class TradeSnippet(BaseModel):
    entry_time: str
    entry_price: float
    exit_price: float
    pnl_pct: float


class RealityGapMetrics(BaseModel):
    slippage_impact_pct: float
    fee_impact_pct: float


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
    win_rate_pct: Optional[float] = None
    total_trades: Optional[int] = None
    alpha: Optional[float] = None
    beta: Optional[float] = None
    calmar_ratio: Optional[float] = None
    avg_trade_duration: Optional[str] = None
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


class SSORequest(BaseModel):
    """Schema for SSO sign-in request."""

    provider: Literal["google", "discord"]
    redirect_to: str


class SSOResponse(BaseModel):
    """Schema for SSO sign-in response."""

    auth_url: str


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
    symbol: str
    timeframe: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    entry_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    exit_criteria: Dict[str, Any] = Field(default_factory=dict)
    indicators_config: Dict[str, Any] = Field(default_factory=dict)
    patterns: List[str] = Field(default_factory=list)

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe_strategy(cls, v: str) -> str:
        allowed = {"1Day", "1Hour", "4Hour", "15Min", "1Min"}
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
