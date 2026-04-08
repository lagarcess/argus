"""
API-layer Pydantic schemas.

Separate from engine.py schemas to keep API contracts clean
and allow versioning independently of core engine models.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

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
    oauth_token: Optional[str] = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


class StrategyCreate(BaseModel):
    """Strategy definition according to V1 contract."""

    name: str = Field(default="Unnamed Strategy", max_length=120)
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    entry_criteria: List[Dict[str, Any]] = Field(default_factory=list)
    exit_criteria: Dict[str, Any] = Field(default_factory=dict)
    indicators_config: Dict[str, Any] = Field(default_factory=dict)
    patterns: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------


class BacktestRequest(BaseModel):
    """API backtest request payload (XOR)."""

    strategy_id: Optional[str] = None

    # We allow unpacking inline fields to match what the frontend might send,
    # but the cleanest is if the frontend sends the whole object,
    # or we can accept the fields directly.
    # The contract says: OR full inline StrategyCreate object (NEVER both)
    # Let's map it directly as fields in the request, or as a nested object?
    # Usually "inline" means spreading the fields into the root of the JSON.
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
        # Checking if *any* of the required inline fields exist
        has_inline = bool(self.symbol or self.timeframe)

        if has_id == has_inline:
            raise ValueError(
                "Must provide either strategy_id OR inline strategy fields (not both, not neither)"
            )

        # If inline, ensure required fields are present
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


class SimulationSummary(BaseModel):
    id: str
    strategy_name: str
    symbols: List[str]
    timeframe: str
    status: Literal["pending", "completed", "failed", "processing"]
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    total_trades: int
    created_at: datetime
    completed_at: Optional[datetime] = None


class PaginatedHistory(BaseModel):
    simulations: List[SimulationSummary]
    total: int
    next_cursor: Optional[str] = None
