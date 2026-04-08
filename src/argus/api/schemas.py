"""
API-layer Pydantic schemas.

Separate from engine.py schemas to keep API contracts clean
and allow versioning independently of core engine models.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


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


class BacktestRequest(BaseModel):
    """API backtest request payload from the Strategy Builder UI."""

    strategy_name: str = Field(default="Unnamed Strategy", max_length=120)
    symbols: List[str] = Field(
        ..., min_length=1, max_length=3, description="1–3 symbols to backtest"
    )
    asset_class: Literal["crypto", "equity"] = Field(default="crypto")
    timeframe: str = Field(default="1Day", description="e.g. 1Day, 1Hour, 15Min")
    start_date: Optional[date] = Field(default=None)
    end_date: Optional[date] = Field(default=None)
    entry_patterns: List[str] = Field(default_factory=list)
    exit_patterns: List[str] = Field(default_factory=list)
    confluence_mode: Literal["OR", "AND"] = Field(default="OR")
    slippage: float = Field(default=0.001, ge=0.0, le=0.05)
    fees: float = Field(default=0.001, ge=0.0, le=0.05)
    rsi_period: Optional[int] = Field(default=None, ge=2, le=200)
    rsi_oversold: float = Field(default=30.0, ge=0.0, le=100.0)
    rsi_overbought: float = Field(default=70.0, ge=0.0, le=100.0)
    ema_period: Optional[int] = Field(default=None, ge=2, le=500)
    benchmark_symbol: Optional[str] = Field(
        default="SPY", description="e.g. SPY, BTC-USD"
    )

    @field_validator("symbols")
    @classmethod
    def validate_symbols_count(cls, v: List[str]) -> List[str]:
        if len(v) > 3:
            raise ValueError("Maximum 3 symbols allowed per batch (PRD §7.1)")
        return [s.upper().strip() for s in v]

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        allowed = {"1Day", "1Hour", "4Hour", "15Min", "1Min"}
        if v not in allowed:
            raise ValueError(f"timeframe must be one of {allowed}")
        return v


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


class HistoryResponse(BaseModel):
    simulations: List[SimulationLogEntry]
    total: int


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
