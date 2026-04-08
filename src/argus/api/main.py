"""
Argus FastAPI entrypoint.

Serves the backtest engine and manages history/auth via Supabase.
"""

from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from argus.api.auth import auth_required, check_rate_limit
from argus.api.schemas import (
    BacktestRequest,
)
from argus.domain.persistence import PersistenceService
from argus.domain.schemas import User
from argus.engine import BacktestResult
from argus.supabase import supabase_client

persistence_service = PersistenceService()


def emit_posthog_event(event: str, properties: dict[str, Any]) -> None:
    """Placeholder for PostHog event emission."""
    logger.info(f"PostHog Event: {event} | Properties: {properties}")


def _background_save_simulation(
    user_id: str,
    strategy_id: str,
    symbol: str,
    timeframe: str,
    result: BacktestResult,
    simulation_id: str,
):
    """Robust wrapper for background persistence with separate try/except."""
    try:
        persistence_service.save_simulation(
            user_id=user_id,
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            result=result,
            simulation_id=simulation_id,
        )
        logger.info(f"Successfully saved simulation {simulation_id} in background.")
    except Exception as e:
        logger.error(f"Failed to save simulation {simulation_id} in background: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events."""
    logger.info("Initializing Argus API...")
    yield
    logger.info("Shutting down Argus API...")


app = FastAPI(
    title="Argus Quant Engine API",
    description="Backend for the Obsidian Observatory",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
origins = [
    "http://localhost:3000",
    "https://argus.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Service health check."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/api/v1/auth/session", response_model=User)
def get_session(user: User = Depends(auth_required)):  # noqa: B008
    """Return the current authenticated user session."""
    return user


@app.post("/api/v1/backtests", response_model=None)
def run_backtest(
    request: BacktestRequest,
    response: Response,
    user: User = Depends(check_rate_limit),  # noqa: B008
):
    """
    Execute a backtest simulation.
    """
    # Rate limit headers mock
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = "99"
    response.headers["X-RateLimit-Reset"] = "1712534400"

    user_id_str = str(user.user_id)

    if not user.is_admin:
        emit_posthog_event(
            "backtest_run",
            {
                "tier": user.subscription_tier,
                "duration_ms": 1500,
                "profitable": True,
                "pattern_count": 2,
            },
        )

        # Decrement quota atomically
        if supabase_client:
            try:
                supabase_client.rpc(
                    "decrement_user_quota", {"user_uuid": user_id_str}
                ).execute()
            except Exception as e:
                logger.error(f"Failed to decrement quota for {user_id_str}: {e}")

    # Return mock data
    mock_response = {
        "id": str(uuid4()),
        "config_snapshot": {
            "name": request.name if request.name else "Strategy from ID",
            "symbol": request.symbol if request.symbol else "BTC/USDT",
            "timeframe": "1h",
        },
        "results": {
            "total_return_pct": 14.5,
            "win_rate": 0.62,
            "sharpe_ratio": 1.8,
            "sortino_ratio": 2.1,
            "calmar_ratio": 1.2,
            "profit_factor": 1.5,
            "expectancy": 0.45,
            "max_drawdown_pct": 0.05,
            "equity_curve": [100.0, 101.5, 100.2, 105.0, 114.5],
            "trades": [
                {
                    "entry_time": "2025-01-02T10:00:00Z",
                    "entry_price": 65000.0,
                    "exit_price": 67000.0,
                    "pnl_pct": 3.1,
                }
            ],
            "reality_gap_metrics": {"slippage_impact_pct": 1.2, "fee_impact_pct": 0.4},
            "pattern_breakdown": {"gartley_hits": 4, "morning_star_hits": 2},
        },
    }

    return mock_response


@app.get("/api/v1/backtests/{id}", response_model=None)
def get_backtest_detail(
    id: str,
    response: Response,
    user: User = Depends(auth_required),  # noqa: B008
):
    """Get the full details of a specific simulation."""
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = "99"
    response.headers["X-RateLimit-Reset"] = "1712534400"

    # Return mock data
    return {
        "id": id,
        "config_snapshot": {
            "name": "Golden Cross DR",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
        },
        "results": {
            "total_return_pct": 14.5,
            "win_rate": 0.62,
            "sharpe_ratio": 1.8,
            "sortino_ratio": 2.1,
            "calmar_ratio": 1.2,
            "profit_factor": 1.5,
            "expectancy": 0.45,
            "max_drawdown_pct": 0.05,
            "equity_curve": [100.0, 101.5, 100.2, 105.0, 114.5],
            "trades": [
                {
                    "entry_time": "2025-01-02T10:00:00Z",
                    "entry_price": 65000.0,
                    "exit_price": 67000.0,
                    "pnl_pct": 3.1,
                }
            ],
            "reality_gap_metrics": {"slippage_impact_pct": 1.2, "fee_impact_pct": 0.4},
            "pattern_breakdown": {"gartley_hits": 4, "morning_star_hits": 2},
        },
    }


@app.get("/api/v1/history", response_model=None)
def get_user_history(
    response: Response,
    cursor: str = "",
    limit: int = 10,
    user: User = Depends(auth_required),  # noqa: B008
):
    """Get the summarized simulation history for the current user."""
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = "99"
    response.headers["X-RateLimit-Reset"] = "1712534400"

    # Return mock data matching PaginatedHistory schema
    return {
        "simulations": [
            {
                "id": str(uuid4()),
                "strategy_name": "Golden Cross DR",
                "symbols": ["BTC/USDT"],
                "timeframe": "1h",
                "status": "completed",
                "total_return_pct": 14.5,
                "sharpe_ratio": 1.8,
                "max_drawdown_pct": 5.2,
                "win_rate_pct": 62.0,
                "total_trades": 42,
                "created_at": "2026-04-07T13:15:00Z",
                "completed_at": "2026-04-07T13:15:45Z",
            }
        ],
        "total": 100,
        "next_cursor": "YmFzZTY0LW9wYXF1ZS1zdHJpbmc=",
    }
