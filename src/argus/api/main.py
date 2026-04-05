"""
Argus FastAPI entrypoint.

Serves the backtest engine and manages history/auth via Supabase.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from supabase import Client, create_client

from argus.api.auth import get_current_user
from argus.api.schemas import BacktestRequest, HistoryResponse
from argus.config import get_crypto_data_client, get_settings, get_stock_data_client
from argus.domain.schemas import AssetClass
from argus.engine import ArgusEngine, StrategyConfig
from argus.market.data_provider import MarketDataProvider

# Supabase Client Initialization
# We use the Service Role key for backend operations (inserting logs safely)
_settings = get_settings()
SUPABASE_URL = _settings.SUPABASE_URL
SUPABASE_SERVICE_KEY = _settings.SUPABASE_SERVICE_ROLE_KEY

supabase_client: Client | None = None
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

    logger.info(
        f"User {user.get('sub')} initiated backtest '{request.strategy_name}' on {symbols}"
    )

    # 1. Start a simulation log entry in Supabase (if configured)
    sim_id = None
    if supabase_client:
        try:
            res = (
                supabase_client.table("simulation_logs")
                .insert(
                    {
                        "user_id": user["sub"],
                        "strategy_name": request.strategy_name,
                        "symbols": symbols,
                        "timeframe": request.timeframe,
                        "start_date": request.start_date.isoformat()
                        if request.start_date
                        else None,
                        "end_date": request.end_date.isoformat()
                        if request.end_date
                        else None,
                        "confluence_mode": request.confluence_mode,
                        "entry_patterns": request.entry_patterns,
                        "exit_patterns": request.exit_patterns,
                        "rsi_period": request.rsi_period,
                        "rsi_oversold": request.rsi_oversold,
                        "rsi_overbought": request.rsi_overbought,
                        "ema_period": request.ema_period,
                        "slippage": request.slippage,
                        "fees": request.fees,
                        "status": "processing",
                    }
                )
                .execute()
            )
            if res.data:
                sim_id = res.data[0]["id"]
        except Exception as e:
            logger.error(f"Failed to create simulation log: {e}")

    try:
        # 2. Build Engine & Provider
        # Settings already load from .env
        stock_client = get_stock_data_client()
        crypto_client = get_crypto_data_client()
        provider = MarketDataProvider(stock_client, crypto_client)
        engine = ArgusEngine(provider)

        # 3. Configure Strategy
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

        # 4. Execute
        result = engine.run(
            symbol=symbols,
            asset_class=ac,
            timeframe_str=request.timeframe,
            start_dt=request.start_date,
            end_dt=request.end_date,
            strategy_config=config,
        )

        # 5. Update Supabase with success
        if supabase_client and sim_id:
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                supabase_client.table("simulation_logs").update(
                    {
                        "status": "completed",
                        "total_return_pct": float(result.metrics.total_return_pct),
                        "sharpe_ratio": float(result.metrics.sharpe_ratio),
                        "sortino_ratio": float(result.metrics.sortino_ratio),
                        "max_drawdown_pct": float(result.metrics.max_drawdown_pct),
                        "win_rate_pct": float(result.metrics.win_rate_pct),
                        "total_trades": int(result.metrics.total_trades),
                        "result_json": result.model_dump(mode="json"),
                        "completed_at": now_iso,
                    }
                ).eq("id", sim_id).execute()
            except Exception as e:
                logger.error(f"Failed to update simulation log on success: {e}")

        return {"simulation_id": sim_id, "result": result}

    except Exception as e:
        logger.exception("Backtest execution failed")
        # Update Supabase with failure
        if supabase_client and sim_id:
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                supabase_client.table("simulation_logs").update(
                    {
                        "status": "failed",
                        "error_message": str(e),
                        "completed_at": now_iso,
                    }
                ).eq("id", sim_id).execute()
            except Exception as update_err:
                logger.error(f"Failed to update simulation log on error: {update_err}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {e}",
        ) from e


@app.get("/api/v1/history", response_model=HistoryResponse)
def get_user_history(
    limit: int = 50,
    offset: int = 0,
    user: Dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Get the simulation history for the current user."""
    if not supabase_client:
        return HistoryResponse(simulations=[], total=0)

    try:
        user_id = user["sub"]

        # Fetch count
        count_res = (
            supabase_client.table("simulation_logs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        total = count_res.count if count_res.count else 0

        # Fetch page
        res = (
            supabase_client.table("simulation_logs")
            .select(
                "id, strategy_name, symbols, timeframe, status, total_return_pct, "
                "sharpe_ratio, max_drawdown_pct, win_rate_pct, total_trades, "
                "created_at, completed_at",
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return HistoryResponse(simulations=res.data, total=total)

    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch simulation history.",
        ) from e
