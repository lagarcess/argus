import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import uuid4

from alpaca.trading.enums import AssetClass as TradingAssetClass
from alpaca.trading.enums import AssetStatus
from alpaca.trading.requests import GetAssetsRequest
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from argus.api.auth import (
    _user_cache,
    auth_required,
    check_asset_search_rate_limit,
    check_rate_limit,
)
from argus.api.schemas import (
    BacktestRequest,
    BacktestResponse,
    BacktestResults,
    PaginatedHistory,
    ProfileUpdate,
    RealityGapMetrics,
    SimulationLogEntry,
    SSORequest,
    SSOResponse,
    TradeSnippet,
)
from argus.api.strategies import router as strategies_router
from argus.config import (
    get_crypto_data_client,
    get_stock_data_client,
    get_trading_client,
)
from argus.domain.persistence import PersistenceService
from argus.domain.schemas import AssetClass, UserResponse
from argus.engine import ArgusEngine, BacktestResult, StrategyConfig
from argus.market.data_provider import MarketDataProvider
from argus.supabase import supabase_client

persistence_service = PersistenceService()


def emit_posthog_event(event: str, properties: dict[str, Any]) -> None:
    """Placeholder for PostHog event emission."""
    logger.info(f"PostHog Event: {event} | Properties: {properties}")


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
        if time.time() - self._timestamp > self._ttl:
            return []
        return self._assets

    def set(self, assets: List[Any]) -> None:
        self._assets = assets
        self._timestamp = time.time()


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
app.include_router(strategies_router)


@app.get("/health")
def health_check():
    """Service health check."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/api/v1/auth/session", response_model=UserResponse)
def get_session(user: UserResponse = Depends(auth_required)):  # noqa: B008
    """Return the current authenticated user session."""
    return user


@app.post("/api/v1/auth/sso", response_model=SSOResponse)
def sso_login(request: SSORequest):
    """Initiate an SSO login flow."""
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase client not configured.",
        )

    try:
        # Currently supabase-py v2+ auth.sign_in_with_oauth takes provider and options
        res = supabase_client.auth.sign_in_with_oauth(
            {
                "provider": request.provider,  # type: ignore
                "options": {"redirect_to": request.redirect_to},
            }
        )
        return SSOResponse(auth_url=res.url)
    except Exception as e:
        logger.error(f"SSO login failed: {e}")
        # Note: If there's an identity linking issue, supabase usually handles it,
        # but if we get an exception we return it.
        if "conflict" in str(e).lower() or "already linked" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate SSO: {str(e)}",
        ) from e


@app.patch("/api/v1/auth/profile", response_model=UserResponse)
def update_profile(
    updates: ProfileUpdate,
    user: UserResponse = Depends(auth_required),  # noqa: B008
):
    """Update current user's profile preferences."""
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase client not configured.",
        )

    update_dict = {}
    if updates.theme is not None:
        update_dict["theme"] = updates.theme
    if updates.lang is not None:
        update_dict["lang"] = updates.lang

    if not update_dict:
        return user  # No changes

    try:
        res = (
            supabase_client.table("profiles")
            .update(update_dict)
            .eq("id", user.id)
            .execute()
        )

        if res.data and len(res.data) > 0:
            updated_data = res.data[0]
            user.theme = str(updated_data.get("theme", user.theme))
            user.lang = str(updated_data.get("lang", user.lang))

            # Invalidate cache so subsequent requests load new theme/lang
            _user_cache.invalidate(user.id)

            return user

        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Update failed: {e}",
        ) from e


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, request: Request):
    """Clear auth cookies and revoke session."""

    # Check if there is an active session cookie to revoke
    token = request.cookies.get("sb-access-token")
    if token:
        try:
            # Create a request-local Supabase client to avoid global state race conditions
            from argus.config import get_settings
            from supabase import create_client

            settings = get_settings()
            if settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
                local_client = create_client(
                    settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY
                )
                # Set the session on the local client
                local_client.auth.set_session(access_token=token, refresh_token="")
                local_client.auth.sign_out()
        except Exception as e:
            logger.warning(f"Failed to sign out from Supabase: {e}")

    # Clear the cookies on the INJECTED response object
    response.delete_cookie(
        key="sb-access-token", path="/", secure=True, httponly=True, samesite="strict"
    )
    # Also delete the refresh token if it exists
    response.delete_cookie(
        key="sb-refresh-token", path="/", secure=True, httponly=True, samesite="strict"
    )

    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.post("/api/v1/backtests", response_model=BacktestResponse)
def run_backtest(
    request: BacktestRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    user: UserResponse = Depends(check_rate_limit),  # noqa: B008
):
    """
    Execute a backtest simulation with XOR logic (Strategy ID or Inline config).
    """
    # Rate limit headers mock for the UI
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = "99"
    response.headers["X-RateLimit-Reset"] = str(int(datetime.now().timestamp() + 3600))

    user_id_str = str(user.id)
    simulation_id = str(uuid4())

    try:
        # 1. Resolve Strategy Configuration
        if request.strategy_id:
            logger.info(f"Fetching strategy {request.strategy_id} for backtest")
            strat_record = persistence_service.get_strategy(request.strategy_id, user_id_str)
            if not strat_record:
                raise HTTPException(status_code=404, detail="Strategy not found")

            # Map DB record to Engine Config
            config = StrategyConfig(
                name=strat_record["name"],
                entry_criteria=strat_record.get("entry_criteria", []),
                exit_criteria=strat_record.get("exit_criteria", {}),
                indicators_config=strat_record.get("indicators_config", {}),
                patterns=strat_record.get("patterns", []),
            )
            symbols = [strat_record["symbol"]]
            timeframe = strat_record["timeframe"]
            start_dt = strat_record.get("start_date")
            end_dt = strat_record.get("end_date")
            strategy_id = request.strategy_id
        else:
            # Inline configuration
            config = StrategyConfig(
                name=request.name or "Inline Strategy",
                entry_criteria=request.entry_criteria or [],
                exit_criteria=request.exit_criteria or {},
                indicators_config=request.indicators_config or {},
                patterns=request.patterns or [],
            )
            symbols = [request.symbol] if request.symbol else []
            timeframe = request.timeframe
            start_dt = request.start_date
            end_dt = request.end_date

            # Save inline strategies as "drafts" for persistence
            strategy_data = {
                "name": config.name,
                "symbol": symbols[0] if symbols else "",
                "timeframe": timeframe or "",
                "start_date": start_dt.isoformat() if start_dt else None,
                "end_date": end_dt.isoformat() if end_dt else None,
                "entry_criteria": config.entry_criteria,
                "exit_criteria": config.exit_criteria,
                "indicators_config": config.indicators_config,
                "patterns": config.patterns,
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
            strat_record = persistence_service.save_strategy(user_id_str, strategy_data)
            strategy_id = strat_record["id"]

        # 2. Run Engine
        logger.info(f"Running engine for simulation {simulation_id}")
        engine = ArgusEngine(
            data_provider=MarketDataProvider(
                get_stock_data_client(), get_crypto_data_client()
            )
        )

        # Determine asset class from symbols
        ac = AssetClass.CRYPTO if any(s in (symbols[0] or "") for s in ["BTC", "ETH", "SOL"]) else AssetClass.EQUITY

        result = engine.run(
            symbols=symbols,
            asset_class=ac,
            timeframe=timeframe or "1Hour",
            start_date=start_dt,
            end_date=end_dt,
            config=config,
        )

        # 3. Post-Execution Hooks (Atomic Quota + PostHog)
        if not user.is_admin:
            emit_posthog_event("backtest_run", {
                "user_id": user_id_str,
                "tier": user.subscription_tier,
                "symbol": symbols[0] if symbols else "unknown"
            })
            if supabase_client:
                try:
                    supabase_client.rpc("decrement_user_quota", {"user_uuid": user_id_str}).execute()
                except Exception as e:
                    logger.error(f"Failed to decrement quota: {e}")

        # 4. Background Persistence
        background_tasks.add_task(
            persistence_service.save_simulation,
            user_id=user_id_str,
            strategy_id=strategy_id,
            symbol=symbols[0] if symbols else "",
            timeframe=timeframe,
            result=result,
            config_snapshot={
                "name": config.name,
                "symbol": symbols[0] if symbols else "",
                "timeframe": timeframe or "",
            },
            simulation_id=simulation_id,
        )

        _user_cache.invalidate(user_id_str)

        # Map to BacktestResponse (Mapping Engine -> API schema)
        return BacktestResponse(
            id=simulation_id,
            config_snapshot={
                "name": config.name,
                "symbol": symbols[0] if symbols else "",
                "timeframe": timeframe or "",
            },
            results=BacktestResults(
                total_return_pct=result.metrics.total_return_pct,
                win_rate=result.metrics.win_rate_pct / 100.0,
                sharpe_ratio=result.metrics.sharpe_ratio,
                sortino_ratio=result.metrics.sortino_ratio,
                calmar_ratio=result.metrics.calmar_ratio,
                profit_factor=result.metrics.profit_factor,
                expectancy=result.metrics.expectancy,
                max_drawdown_pct=result.metrics.max_drawdown_pct,
                equity_curve=[p.value for p in result.equity_curve],
                trades=[
                    TradeSnippet(
                        entry_time=t.entry_time,
                        entry_price=t.entry_price,
                        exit_price=t.exit_price,
                        pnl_pct=t.pnl_pct
                    ) for t in result.trades[:50] # Top 50 recent
                ],
                reality_gap_metrics=RealityGapMetrics(
                    slippage_impact_pct=result.reality_gap_metrics.get("slippage_impact_pct", 0.0),
                    fee_impact_pct=result.reality_gap_metrics.get("fee_impact_pct", 0.0)
                ) if hasattr(result, "reality_gap_metrics") and isinstance(result.reality_gap_metrics, dict) else RealityGapMetrics(slippage_impact_pct=0, fee_impact_pct=0),
                pattern_breakdown=getattr(result, "pattern_breakdown", {})
            )
        )

    except ValueError as e:
        logger.warning(f"Engine validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Backtest execution failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Backtest failed: {e}") from e


@app.get("/api/v1/backtests/{id}", response_model=BacktestResponse)
def get_backtest_detail(
    id: str,
    response: Response,
    user: UserResponse = Depends(auth_required),  # noqa: B008
):
    """Get the full details of a specific simulation."""
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = "99"
    response.headers["X-RateLimit-Reset"] = "1712534400"

    # Fetch real data from persistence
    sim_data = persistence_service.get_simulation(id, user.id)
    if not sim_data:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Map database structure back to BacktestResponse
    summary = sim_data.get("summary", {})
    full_result = sim_data.get("full_result", {})
    config_snapshot = sim_data.get("config_snapshot", {})

    return BacktestResponse(
        id=id,
        config_snapshot=config_snapshot,
        results=BacktestResults(
            total_return_pct=summary.get("total_return_pct", 0.0),
            win_rate=summary.get("win_rate_pct", 0.0) / 100.0,
            sharpe_ratio=summary.get("sharpe_ratio", 0.0),
            sortino_ratio=summary.get("sortino_ratio", 0.0),
            calmar_ratio=summary.get("calmar_ratio", 0.0),
            profit_factor=summary.get("profit_factor", 0.0),
            expectancy=summary.get("expectancy", 0.0),
            max_drawdown_pct=summary.get("max_drawdown_pct", 0.0),
            equity_curve=[p.get("value") for p in full_result.get("equity_curve", [])],
            trades=[
                TradeSnippet(
                    entry_time=t.get("entry_time"),
                    entry_price=t.get("entry_price"),
                    exit_price=t.get("exit_price"),
                    pnl_pct=t.get("pnl_pct")
                ) for t in full_result.get("trades", [])[:50]
            ],
            reality_gap_metrics=RealityGapMetrics(
                slippage_impact_pct=sim_data.get("reality_gap_metrics", {}).get("slippage_impact_pct", 0.0),
                fee_impact_pct=sim_data.get("reality_gap_metrics", {}).get("fee_impact_pct", 0.0)
            ),
            pattern_breakdown=full_result.get("pattern_breakdown", {})
        )
    )


@app.get("/api/v1/history", response_model=PaginatedHistory)
def get_user_history(
    response: Response,
    cursor: Optional[str] = None,
    limit: int = 10,
    user: UserResponse = Depends(auth_required),  # noqa: B008
):
    """Get the summarized simulation history for the current user with pagination."""
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = "99"
    response.headers["X-RateLimit-Reset"] = str(int(datetime.now().timestamp() + 3600))

    try:
        user_id_str = str(user.id)
        # Fetch from persistence with cursor support
        summaries, total = persistence_service.get_user_simulations(
            user_id_str, limit=limit, cursor=cursor
        )

        return PaginatedHistory(
            simulations=[SimulationLogEntry(**s) for s in summaries],
            total=total,
            next_cursor=summaries[-1].get("id") if (summaries and len(summaries) >= limit) else None
        )

    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch simulation history.",
        ) from e


@app.get("/api/v1/simulations/{sim_id}")
def get_simulation_detail(sim_id: str, user: UserResponse = Depends(auth_required)):  # noqa: B008
    """Get the full details of a specific simulation."""
    try:
        user_id_str = str(user.id)
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
