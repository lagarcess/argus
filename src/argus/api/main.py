"""
Argus FastAPI entrypoint.

Serves the backtest engine and manages history/auth via Supabase.
"""

import time as time_module
from contextlib import asynccontextmanager
from datetime import datetime, time, timezone
from typing import Any, List
from uuid import uuid4

from alpaca.trading.enums import AssetClass as TradingAssetClass
from alpaca.trading.enums import AssetStatus
from alpaca.trading.requests import GetAssetsRequest
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from argus.api.auth import (
    FREE_TIER_MONTHLY_LIMIT,
    auth_required,
    check_asset_search_rate_limit,
    check_rate_limit,
)
from argus.api.schemas import (
    BacktestRequest,
    HistoryResponse,
    SimulationLogEntry,
)
from argus.config import get_crypto_data_client, get_stock_data_client, get_trading_client
from argus.domain.persistence import PersistenceService
from argus.domain.schemas import AssetClass, User
from argus.engine import ArgusEngine, BacktestResult, StrategyConfig
from argus.market.data_provider import MarketDataProvider
from argus.supabase import supabase_client

persistence_service = PersistenceService()


class AssetCache:
    """
    In-memory TTL cache for the global Alpaca asset list.
    Avoids fetching thousands of assets on every search request.
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._assets: List[Any] = []
        self._timestamp: float = 0
        self._ttl = ttl_seconds

    def get(self) -> List[Any]:
        if time_module.time() - self._timestamp > self._ttl:
            return []
        return self._assets

    def set(self, assets: List[Any]) -> None:
        self._assets = assets
        self._timestamp = time_module.time()


# Global singleton cache for the asset endpoint
asset_cache = AssetCache(ttl_seconds=3600)  # 1 hour


def _background_save_simulation(
    user_id: str,
    strategy_id: str,
    symbol: str,
    result: BacktestResult,
    simulation_id: str,
    timeframe: str | None = None,
):
    """Robust wrapper for background persistence with separate try/except."""
    try:
        persistence_service.save_simulation(
            user_id=user_id,
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe or "",
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


@app.get("/api/v1/usage")
def get_usage(user: User = Depends(auth_required)):  # noqa: B008
    """
    Get the current user's simulation usage for the current calendar month.
    """
    user_id_str = str(user.user_id)

    # Pro tier has unlimited limits
    if user.subscription_tier == "pro":
        return {
            "count": 0,  # Could still show count for stats
            "limit": None,
            "tier": "pro",
        }

    # Free tier limit check using current calendar month
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    try:
        if not supabase_client:
            return {
                "count": 0,
                "limit": FREE_TIER_MONTHLY_LIMIT,
                "tier": user.subscription_tier,
            }

        count_res = (
            supabase_client.table("simulation_logs")
            .select("id", count="exact")  # type: ignore[arg-type]
            .eq("user_id", user_id_str)
            .gte("created_at", start_of_month.isoformat())
            .execute()
        )
        count = count_res.count if count_res.count else 0

        return {
            "count": count,
            "limit": FREE_TIER_MONTHLY_LIMIT,
            "tier": user.subscription_tier,
        }
    except Exception as e:
        logger.error(f"Failed to fetch usage for {user_id_str}: {e}")
        return {
            "count": 0,
            "limit": FREE_TIER_MONTHLY_LIMIT,
            "tier": user.subscription_tier,
        }


@app.post("/api/v1/backtest")
def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(check_rate_limit),  # noqa: B008
):
    """
    Execute a backtest simulation on multiple assets.
    """
    symbols = request.symbols
    user_id_str = str(user.user_id)

    logger.info(
        f"User {user_id_str} initiated backtest '{request.strategy_name}' on {symbols}"
    )

    try:
        # 1. Build Engine & Provider
        stock_client = get_stock_data_client()
        crypto_client = get_crypto_data_client()
        provider = MarketDataProvider(stock_client, crypto_client)
        engine = ArgusEngine(provider)

        # 2. Configure Strategy
        config = StrategyConfig(
            entry_patterns=request.entry_patterns,
            exit_patterns=request.exit_patterns,
            confluence_mode=request.confluence_mode,
            slippage=request.slippage,
            fees=request.fees,
            rsi_period=request.rsi_period,
            rsi_oversold=request.rsi_oversold,
            rsi_overbought=request.rsi_overbought,
            ema_period=request.ema_period,
            symbols=symbols,
            benchmark_symbol=request.benchmark_symbol,
        )

        ac = AssetClass.CRYPTO if request.asset_class == "crypto" else AssetClass.EQUITY

        # 3. Execute Simulation
        start_dt = (
            datetime.combine(request.start_date, time.min, tzinfo=timezone.utc)
            if request.start_date
            else None
        )
        end_dt = (
            datetime.combine(request.end_date, time.max, tzinfo=timezone.utc)
            if request.end_date
            else None
        )

        # Pre-generate simulation ID for frontend tracking
        simulation_id = str(uuid4())

        result = engine.run(
            symbols=symbols,
            asset_class=ac,
            timeframe=request.timeframe,
            start_date=start_dt,
            end_date=end_dt,
            config=config,
        )

        # 4. Persistence (Background Task)
        strategy_id = persistence_service.save_strategy(
            user_id_str, request.strategy_name, config
        )

        if strategy_id:
            background_tasks.add_task(
                _background_save_simulation,
                user_id=user_id_str,
                strategy_id=strategy_id,
                symbol=",".join(symbols),
                timeframe=request.timeframe,
                result=result,
                simulation_id=simulation_id,
            )

        return {
            "status": "success",
            "strategy_id": strategy_id,
            "simulation_id": simulation_id,
            "result": result,
        }

    except ValueError as e:
        logger.warning(f"Engine validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Backtest execution failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {e}",
        ) from e


@app.get("/api/v1/history", response_model=HistoryResponse)
def get_user_history(
    limit: int = 10,
    offset: int = 0,
    user: User = Depends(auth_required),  # noqa: B008
):
    """Get the summarized simulation history for the current user."""
    try:
        user_id_str = str(user.user_id)
        summaries, total = persistence_service.get_user_simulations(
            user_id_str, limit, offset
        )

        return HistoryResponse(
            simulations=[SimulationLogEntry(**s) for s in summaries],
            total=total,
        )

    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch simulation history.",
        ) from e


@app.get("/api/v1/simulations/{sim_id}")
def get_simulation_detail(sim_id: str, user: User = Depends(auth_required)):  # noqa: B008
    """Get the full details of a specific simulation."""
    try:
        user_id_str = str(user.user_id)
        simulation = persistence_service.get_simulation(sim_id, user_id_str)

        if not simulation:
            # Fallback for "latest"
            if sim_id == "latest":
                summaries, _ = persistence_service.get_user_simulations(
                    user_id_str, limit=1
                )
                if summaries:
                    simulation = persistence_service.get_simulation(
                        str(summaries[0]["id"]), user_id_str
                    )

        if not simulation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Simulation not found.",
            )

        return simulation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch simulation {sim_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch simulation details.",
        ) from e


@app.get("/api/v1/assets", response_model=List[str])
def get_assets(
    search: str,
    response: Response,
    rate_limit_headers: dict[str, Any] = Depends(check_asset_search_rate_limit),  # noqa: B008
    timeframe: str | None = None,
):
    """
    Search for active assets (US Equity and Crypto).
    Applies an in-memory case-insensitive search to symbol or name.
    Uses a 1-hour TTL cache to avoid frequent Alpaca API calls.
    """
    # Validate timeframe if provided (must be >= 15m)
    allowed_timeframes = {"15Min", "1Hour", "4Hour", "1Day", "15m", "1h", "4h", "1d"}
    if timeframe and timeframe not in allowed_timeframes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"timeframe must be one of {allowed_timeframes} (min 15m)",
        )

    # Attach rate limit headers
    for key, value in rate_limit_headers.items():
        response.headers[key] = value

    try:
        # Check cache first
        assets = asset_cache.get()

        # Fetch from Alpaca if cache miss
        if not assets:
            logger.info("AssetCache miss: fetching from Alpaca")
            trading_client = get_trading_client()
            req_equity = GetAssetsRequest(
                status=AssetStatus.ACTIVE, asset_class=TradingAssetClass.US_EQUITY
            )
            req_crypto = GetAssetsRequest(
                status=AssetStatus.ACTIVE, asset_class=TradingAssetClass.CRYPTO
            )

            equity_assets = trading_client.get_all_assets(req_equity)
            crypto_assets = trading_client.get_all_assets(req_crypto)

            if isinstance(equity_assets, list):
                assets.extend(equity_assets)
            if isinstance(crypto_assets, list):
                assets.extend(crypto_assets)

            # Update cache
            asset_cache.set(assets)

        # O(N) case-insensitive search with set for uniqueness
        search_lower = search.lower()
        matched_symbols = set()

        for a in assets:
            sym = getattr(a, "symbol", None)
            if not sym or sym in matched_symbols:
                continue

            name = getattr(a, "name", "")
            if search_lower in sym.lower() or (name and search_lower in name.lower()):
                matched_symbols.add(sym)

        # Return alphabetically sorted matches
        return sorted(list(matched_symbols))

    except Exception as e:
        logger.error(f"Failed to fetch assets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch assets.",
        ) from e
