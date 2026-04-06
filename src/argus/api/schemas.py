"""
API-layer Pydantic schemas.

Separate from engine.py schemas to keep API contracts clean
and allow versioning independently of core engine models.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class AuthRequest(BaseModel):
    """Unified auth request supporting email/password and social SSO."""

    mode: Literal["login", "signup"] = Field(
        default="login", description="login or signup"
    )
    provider: Optional[Literal["email", "google", "apple", "facebook"]] = Field(
        default="email"
    )
    email: Optional[str] = None
    password: Optional[str] = None
    # Social SSO flow sends an OAuth code/token instead
    oauth_token: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


# ---------------------------------------------------------------------------
# Backtest request (extends engine StrategyConfig with API-specific fields)
# ---------------------------------------------------------------------------


class BacktestRequest(BaseModel):
    """API backtest request payload from the Strategy Builder UI."""

    # Strategy identity
    strategy_name: str = Field(default="Unnamed Strategy", max_length=120)

    # Assets (batched, max 3 per PRD)
    symbols: List[str] = Field(
        ..., min_length=1, max_length=3, description="1–3 symbols to backtest"
    )
    asset_class: Literal["crypto", "equity"] = Field(default="crypto")
    timeframe: str = Field(default="1Day", description="e.g. 1Day, 1Hour, 15Min")
    start_date: Optional[date] = Field(default=None)
    end_date: Optional[date] = Field(default=None)

    # Strategy config fields (mirrors engine.StrategyConfig)
    entry_patterns: List[str] = Field(default_factory=list)
    exit_patterns: List[str] = Field(default_factory=list)
    confluence_mode: Literal["OR", "AND"] = Field(default="OR")
    slippage: float = Field(default=0.001, ge=0.0, le=0.05)
    fees: float = Field(default=0.001, ge=0.0, le=0.05)

    # Indicator confluence
    rsi_period: Optional[int] = Field(default=None, ge=2, le=200)
    rsi_oversold: float = Field(default=30.0, ge=0.0, le=100.0)
    rsi_overbought: float = Field(default=70.0, ge=0.0, le=100.0)
    ema_period: Optional[int] = Field(default=None, ge=2, le=500)

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


# ---------------------------------------------------------------------------
# Simulation history
# ---------------------------------------------------------------------------


class SimulationSummary(BaseModel):
    id: str
    strategy_name: str
    symbol: str
    date: datetime
    total_return: float
    sharpe_ratio: float


class PaginatedHistoryResponse(BaseModel):
    simulations: List[SimulationSummary]
    total: int
    limit: int
    offset: int


# Keeping old types to avoid breaking main.py immediately until we patch it next
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
    created_at: datetime
    completed_at: Optional[datetime] = None


class HistoryResponse(BaseModel):
    simulations: List[SimulationLogEntry]
    total: int
