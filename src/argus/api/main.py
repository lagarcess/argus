"""
Argus FastAPI entrypoint.

Serves the backtest engine and manages history/auth via Supabase.
"""

from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from argus.api.auth import get_current_user
from argus.api.schemas import BacktestRequest, PaginatedHistoryResponse
from argus.config import get_crypto_data_client, get_settings, get_stock_data_client
from argus.domain.persistence import PersistenceService
from argus.domain.schemas import AssetClass
from argus.engine import ArgusEngine, StrategyConfig
from argus.market.data_provider import MarketDataProvider
from supabase import Client, create_client

# Supabase Client Initialization
# We use the Service Role key for backend operations (inserting logs safely)
_settings = get_settings()
SUPABASE_URL = _settings.SUPABASE_URL
SUPABASE_SERVICE_KEY = _settings.SUPABASE_SERVICE_ROLE_KEY

supabase_client: Client | None = None
persistence_service = PersistenceService()
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
else:
    logger.warning("Supabase credentials missing. History logging disabled.")


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
# Allow localhost (Nextjs dev) and eventual prod domains
origins = [
    "http://localhost:3000",
    "https://argus.vercel.app",  # Example Vercel domain
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


@app.post("/api/v1/backtest")
def run_backtest(
    request: BacktestRequest,
    user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """
    Execute a backtest simulation on multiple assets.
    """
    symbols = request.symbols
    user_id = user.get("sub", "unknown")

    logger.info(
        f"User {user_id} initiated backtest '{request.strategy_name}' on {symbols}"
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
        )

        # 3. Save Strategy to Persistence Service
        strategy_id = persistence_service.save_strategy(
            user_id, request.strategy_name, config
        )

        ac = AssetClass.CRYPTO if request.asset_class == "crypto" else AssetClass.EQUITY

        # 4. Execute Simulation
        from datetime import datetime, time, timezone

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

        result = engine.run(
            symbols=symbols,
            asset_class=ac,
            timeframe=request.timeframe,
            start_date=start_dt,
            end_date=end_dt,
            config=config,
        )

        # 5. Save Simulation Result
        sim_id = None
        if strategy_id:
            joined_symbols = ",".join(symbols)
            sim_id = persistence_service.save_simulation(
                user_id=user_id,
                strategy_id=strategy_id,
                symbol=joined_symbols,
                timeframe=request.timeframe,
                result=result,
            )

        return {"simulation_id": sim_id, "strategy_id": strategy_id, "result": result}

    except Exception as e:
        logger.exception("Backtest execution failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {e}",
        ) from e


@app.get("/api/v1/history", response_model=PaginatedHistoryResponse)
def get_user_history(
    limit: int = 10,
    offset: int = 0,
    user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get the summarized simulation history for the current user."""
    try:
        user_id = user["sub"]
        summaries, total = persistence_service.get_user_simulations(
            user_id, limit, offset
        )
        from argus.api.schemas import SimulationSummary

        summary_models = [SimulationSummary(**s) for s in summaries]
        return PaginatedHistoryResponse(
            simulations=summary_models, total=total, limit=limit, offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch simulation history.",
        ) from e
