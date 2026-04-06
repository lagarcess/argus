"""
Argus FastAPI entrypoint.

Serves the backtest engine and manages history/auth via Supabase.
"""

from contextlib import asynccontextmanager
from datetime import datetime, time, timezone
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from argus.api.auth import auth_required
from argus.api.schemas import (
    BacktestRequest,
    HistoryResponse,
    SimulationLogEntry,
)
from argus.config import get_crypto_data_client, get_stock_data_client
from argus.domain.persistence import PersistenceService
from argus.domain.schemas import AssetClass, User
from argus.engine import ArgusEngine, BacktestResult, StrategyConfig
from argus.market.data_provider import MarketDataProvider

persistence_service = PersistenceService()


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


@app.get("/api/v1/auth/session", response_model=User)
def get_session(user: User = Depends(auth_required)):  # noqa: B008
    """Return the current authenticated user session."""
    return user


@app.post("/api/v1/backtest")
def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(auth_required),  # noqa: B008
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
        )

        ac = AssetClass.CRYPTO if request.asset_class == "crypto" else AssetClass.EQUITY

        # 3. Execute Simulation
        # Convert date to datetime for engine
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
        # We save the strategy first to get an ID, then the simulation
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
