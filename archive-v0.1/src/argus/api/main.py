import asyncio
import math
import time
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from argus.api.agent import router as agent_router
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
    TelemetryAcceptedResponse,
    TelemetryEventPayload,
    TradeSnippet,
)
from argus.api.strategies import router as strategies_router
from argus.config import (
    get_crypto_data_client,
    get_settings,
    get_stock_data_client,
)
from argus.core.alpaca_fetcher import AlpacaDataFetcher
from argus.domain.persistence import PersistenceError, PersistenceService
from argus.domain.schemas import AssetClass, UserResponse
from argus.engine import ArgusEngine, StrategyInput
from argus.market.data_provider import MarketDataProvider
from argus.supabase import supabase_client

persistence_service = PersistenceService()


@lru_cache()
def get_alpaca_fetcher() -> AlpacaDataFetcher:
    """Lazy initialize the AlpacaDataFetcher."""
    return AlpacaDataFetcher()


def emit_posthog_event(event: str, properties: dict[str, Any]) -> None:
    """Placeholder for PostHog event emission."""
    logger.info(f"PostHog Event: {event} | Properties: {properties}")


def sanitize_metric(v: Any) -> Any:
    """Ensure floating point values are JSON compliant (no inf/nan)."""
    if isinstance(v, float):
        if math.isinf(v) or math.isnan(v):
            return 0.0
    elif isinstance(v, list):
        return [sanitize_metric(x) for x in v]
    return v


def normalize_ratio(value: Any, *, default: float) -> float:
    """Normalize metrics that can be encoded as percent (0..100) or ratio (0..1)."""
    try:
        parsed = float(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    normalized = parsed / 100.0 if parsed > 1.0 else parsed
    return max(0.0, min(1.0, normalized))


@lru_cache(maxsize=32)
def _normalize_allowed_sso_redirects(allowed_urls: tuple[str, ...]) -> frozenset[str]:
    """Cache canonical callback allowlist by concrete allowlist values."""
    normalized = {
        f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
        for raw in allowed_urls
        if (parsed := urlparse(raw)).scheme and parsed.netloc
    }
    return frozenset(normalized)


def is_allowed_sso_redirect(redirect_to: str, allowed_urls: list[str]) -> bool:
    """Strictly validate redirect targets against an explicit callback allowlist."""
    try:
        candidate = urlparse(redirect_to)
    except Exception:
        return False

    if not candidate.scheme or not candidate.netloc:
        return False
    if candidate.query:
        return False
    if candidate.fragment:
        return False
    if candidate.username or candidate.password:
        return False

    normalized_candidate = f"{candidate.scheme.lower()}://{candidate.netloc.lower()}{candidate.path.rstrip('/')}"
    if not candidate.path.startswith("/auth/callback"):
        return False

    normalized_allowed = _normalize_allowed_sso_redirects(tuple(allowed_urls))
    return normalized_candidate in normalized_allowed


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events."""
    logger.info("Initializing Argus API...")
    settings = get_settings()

    async def prime_asset_registry() -> None:
        try:
            # Best-effort warm path for asset discovery without blocking startup.
            fetcher = get_alpaca_fetcher()
            assets = await asyncio.to_thread(fetcher.get_active_assets)
            asset_cache.set(assets)
            logger.info("Asset registry primed.")
        except Exception as e:
            logger.warning(f"Could not prime asset registry: {e}")

    if settings.APP_ENV == "production":
        app.state.asset_prime_task = asyncio.create_task(prime_asset_registry())
    else:
        logger.debug("Skipping asset registry priming outside production.")
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
app.include_router(agent_router)


@app.get("/health")
def health_check():
    """Service health check."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/api/v1/auth/session", response_model=UserResponse)
def get_session(user: UserResponse = Depends(auth_required)):  # noqa: B008
    """Return the current authenticated user session."""
    return user


@app.get("/api/v1/usage", response_model=Dict[str, Any])
def get_usage(user: UserResponse = Depends(check_rate_limit)):  # noqa: B008
    """
    Get current user usage and quota (used by TopNav).
    """
    return {
        "count": user.backtest_quota - user.remaining_quota,
        "limit": user.backtest_quota,
        "tier": user.subscription_tier,
    }


@app.post("/api/v1/auth/sso", response_model=SSOResponse)
def sso_login(request: SSORequest):
    """Initiate an SSO login flow."""
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase client not configured.",
        )

    settings = get_settings()
    if not is_allowed_sso_redirect(request.redirect_to, settings.ALLOWED_REDIRECT_URLS):
        raise HTTPException(status_code=400, detail="Invalid redirect URL")

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


@app.post(
    "/api/v1/telemetry/events",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TelemetryAcceptedResponse,
)
def ingest_telemetry_event(
    payload: TelemetryEventPayload,
    background_tasks: BackgroundTasks,
    user: UserResponse = Depends(auth_required),  # noqa: B008
):
    """Persist client-side funnel telemetry for private-beta observability."""
    try:
        persisted = persistence_service.save_telemetry_event(
            user_id=str(user.id),
            event=payload.event,
            event_ts=payload.timestamp,
            properties=payload.properties,
            strict=True,
        )
    except PersistenceError as e:
        logger.error(f"Telemetry persistence error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist telemetry event.",
        ) from e
    if not persisted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist telemetry event.",
        )

    settings = get_settings()
    if settings.ENABLE_POSTHOG_FORWARDING:
        background_tasks.add_task(
            emit_posthog_event,
            payload.event,
            {
                "user_id": str(user.id),
                "event_ts": payload.timestamp.isoformat(),
                **payload.properties,
            },
        )
    return TelemetryAcceptedResponse(status="accepted")


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
    if updates.onboarding_completed is not None:
        update_dict["onboarding_completed"] = updates.onboarding_completed
    if updates.onboarding_step is not None:
        update_dict["onboarding_step"] = updates.onboarding_step
    if updates.onboarding_intent is not None:
        update_dict["onboarding_intent"] = updates.onboarding_intent

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
            user.onboarding_completed = bool(
                updated_data.get("onboarding_completed", user.onboarding_completed)
            )
            user.onboarding_step = str(
                updated_data.get("onboarding_step", user.onboarding_step)
            )
            user.onboarding_intent = updated_data.get(
                "onboarding_intent", user.onboarding_intent
            )

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
    strategy_id: Optional[str] = Query(None),  # noqa: B008
    user: UserResponse = Depends(check_rate_limit),  # noqa: B008
    fetcher: AlpacaDataFetcher = Depends(get_alpaca_fetcher),  # noqa: B008
    stock_client: StockHistoricalDataClient = Depends(get_stock_data_client),  # noqa: B008
    crypto_client: CryptoHistoricalDataClient = Depends(get_crypto_data_client),  # noqa: B008
):
    """
    Execute a backtest simulation with XOR logic (Strategy ID or Inline config).
    """
    # 0. System Guard (Memory Safety)
    import psutil

    mem = psutil.virtual_memory()
    # Ensure available memory is at least 15% to protect host
    if mem.available / mem.total < 0.15:
        logger.error(
            f"OOM Risk: Available memory is at {mem.available / mem.total * 100:.1f}%. Rejecting backtest."
        )
        raise HTTPException(
            status_code=503,
            detail="System memory is critically low. Please try again later.",
        )

    # 1. Sync strategy_id from Query or Body for XOR check
    sid = strategy_id or request.strategy_id
    # Rate limit headers mock for the UI
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = "99"
    response.headers["X-RateLimit-Reset"] = str(int(datetime.now().timestamp() + 3600))

    user_id_str = str(user.id)
    simulation_id = str(uuid4())
    start_time = time.time()

    try:
        # 1. Resolve Strategy Configuration
        if sid:
            logger.info(f"Fetching strategy {sid} for backtest")
            strat_record = persistence_service.get_strategy(sid, user_id_str)
            if not strat_record:
                raise HTTPException(status_code=404, detail="Strategy not found")

            # Map DB record to Engine Config
            symbols = strat_record.get("symbols") or []
            config = StrategyInput(
                name=strat_record["name"],
                symbols=symbols,
                timeframe=strat_record["timeframe"],
                start_date=strat_record.get("start_date"),
                end_date=strat_record.get("end_date"),
                entry_criteria=strat_record.get("entry_criteria", []),
                exit_criteria=strat_record.get("exit_criteria", []),
                indicators_config=strat_record.get("indicators_config", {}),
                patterns=strat_record.get("patterns", []),
                slippage=request.slippage,
                fees=request.fees,
                participation_rate=request.participation_rate,
                execution_priority=request.execution_priority,
                va_sensitivity=request.va_sensitivity,
                slippage_model=request.slippage_model,
            )
            timeframe = strat_record["timeframe"]
            start_dt = strat_record.get("start_date")
            end_dt = strat_record.get("end_date")
            strategy_id = sid
        else:
            # Inline configuration
            symbols = request.symbols or []
            config = StrategyInput(
                name=request.name or "Inline Strategy",
                symbols=symbols,
                timeframe=request.timeframe or "",
                start_date=request.start_date,
                end_date=request.end_date,
                entry_criteria=request.entry_criteria
                if request.entry_criteria is not None
                else [],
                exit_criteria=request.exit_criteria
                if request.exit_criteria is not None
                else [],
                indicators_config=request.indicators_config
                if request.indicators_config is not None
                else {},
                patterns=request.patterns if request.patterns is not None else [],
                slippage=request.slippage,
                fees=request.fees,
                participation_rate=request.participation_rate,
                execution_priority=request.execution_priority,
                va_sensitivity=request.va_sensitivity,
                slippage_model=request.slippage_model,
            )
            timeframe = request.timeframe
            start_dt = request.start_date
            end_dt = request.end_date
        # --- Multi-Dimensional Tier Gating Validation ---
        if not user.is_admin:
            from datetime import timezone

            from argus.domain.quotas import TIER_CONFIG

            tier = user.subscription_tier or "free"
            limits = TIER_CONFIG.get(tier, TIER_CONFIG["free"])

            # 1. Symbol Count
            if len(symbols) > limits["max_symbols"]:
                raise HTTPException(
                    status_code=403,
                    detail=f"Tier '{tier}' is limited to {limits['max_symbols']} symbols per backtest.",
                )

            # 2. Lookback Horizon
            if start_dt:
                s_dt = start_dt
                e_dt = end_dt if end_dt else datetime.now(timezone.utc)
                delta_days = (e_dt - s_dt).days

                is_intraday = timeframe and any(x in timeframe for x in ["Min", "Hour"])
                if is_intraday and delta_days > limits["intraday_lookback_days"]:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Tier '{tier}' is limited to {limits['intraday_lookback_days']} days for intraday data.",
                    )
                elif not is_intraday and delta_days > limits["daily_lookback_days"]:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Tier '{tier}' is limited to {limits['daily_lookback_days']} days for daily data.",
                    )

            # 3. Execution Forge (Tier Sanitization)
            if tier == "free":
                config.participation_rate = 1.0  # Infinite liquidity
                config.execution_priority = 1.0  # Full spread cross
                config.slippage_model = "fixed"
            # ------------------------------------------------

            # Save inline strategies as "drafts" for persistence
            strategy_data = {
                "name": config.name,
                "symbols": symbols,
                "timeframe": timeframe or "",
                "start_date": start_dt,
                "end_date": end_dt,
                "entry_criteria": config.entry_criteria,
                "exit_criteria": config.exit_criteria,
                "indicators_config": config.indicators_config,
                "patterns": config.patterns,
                "executed_at": datetime.now(timezone.utc).isoformat(),
            }
            strat_record = persistence_service.save_strategy(
                user_id_str,
                strategy_data,
                strict=True,
            )
            if not strat_record:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to persist strategy draft before backtest.",
                )
            strategy_id = strat_record["id"]

        # 2. Run Engine
        logger.info(f"Running engine for simulation {simulation_id}")
        engine = ArgusEngine(
            data_provider=MarketDataProvider(
                stock_client,
                crypto_client,
                fetcher=fetcher,
            )
        )

        # 3. Determine Asset Class (Strict Registry Validation for all symbols)
        if not symbols:
            raise HTTPException(
                status_code=400, detail="No symbols provided for backtest."
            )

        first_alpaca_class = None
        for sym in symbols:
            is_valid, alpaca_class = fetcher.validate_asset(sym)
            if not is_valid or not alpaca_class:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Asset '{sym}' is not supported by the Alpaca registry."
                        " Check symbol for typos (e.g. 'BTC/USD' or 'AAPL')."
                    ),
                )
            if first_alpaca_class is None:
                first_alpaca_class = alpaca_class
            elif alpaca_class != first_alpaca_class:
                raise HTTPException(
                    status_code=400,
                    detail="Mixed asset classes (e.g., Crypto and Stocks) are not supported in a single backtest.",
                )

        ac = AssetClass.from_alpaca(first_alpaca_class)

        result = engine.run(config=config, asset_class=ac)

        # 3. Post-Execution Hooks (Atomic Quota + PostHog)
        if not user.is_admin:
            emit_posthog_event(
                "backtest_run",
                {
                    "user_id": user_id_str,
                    "tier": user.subscription_tier,
                    "symbols": symbols,
                },
            )
            if supabase_client:
                try:
                    supabase_client.rpc(
                        "decrement_user_quota", {"user_uuid": user_id_str}
                    ).execute()
                except Exception as e:
                    err_str = str(e)
                    if "P0001" in err_str or "quota_exhausted" in err_str:
                        raise HTTPException(
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail="Quota exhausted. Upgrade your plan to continue.",
                        ) from e
                    logger.error(f"Failed to decrement quota: {e}")

        # 4. Background Persistence
        background_tasks.add_task(
            persistence_service.save_simulation,
            user_id=user_id_str,
            strategy_id=strategy_id,
            symbols=symbols,
            timeframe=timeframe,
            result=result,
            config_snapshot=config.model_dump(),
            simulation_id=simulation_id,
        )

        _user_cache.invalidate(user_id_str)

        execution_time = time.time() - start_time
        logger.info(f"Backtest {simulation_id} completed in {execution_time:.2f}s")

        # Map to BacktestResponse (Mapping Engine -> API schema)
        return BacktestResponse(
            id=simulation_id,
            config_snapshot=config.model_dump(),
            results=BacktestResults(
                total_return_pct=sanitize_metric(result.total_return_pct),
                win_rate=sanitize_metric(result.win_rate),
                sharpe_ratio=sanitize_metric(result.sharpe_ratio),
                sortino_ratio=sanitize_metric(result.sortino_ratio),
                calmar_ratio=sanitize_metric(result.calmar_ratio),
                profit_factor=sanitize_metric(result.profit_factor),
                expectancy=sanitize_metric(result.expectancy),
                max_drawdown_pct=sanitize_metric(result.max_drawdown_pct),
                equity_curve=[float(x) for x in result.equity_curve]
                if result.equity_curve
                else [],
                ideal_equity_curve=[float(x) for x in result.ideal_equity_curve]
                if result.ideal_equity_curve
                else [],
                trades=[
                    TradeSnippet(
                        entry_time=str(t["entry_time"]),
                        entry_price=sanitize_metric(t["entry_price"]),
                        exit_price=sanitize_metric(t["exit_price"]),
                        pnl_pct=sanitize_metric(t["pnl_pct"]),
                    )
                    for t in result.trades[:50]
                ],
                reality_gap_metrics=RealityGapMetrics(
                    slippage_impact_pct=sanitize_metric(
                        result.reality_gap_metrics.get("slippage_impact_pct", 0.0)
                    ),
                    fee_impact_pct=sanitize_metric(
                        result.reality_gap_metrics.get("fee_impact_pct", 0.0)
                    ),
                    vol_hazard_pct=sanitize_metric(
                        result.reality_gap_metrics.get("vol_hazard_pct", 0.0)
                    ),
                    fidelity_score=sanitize_metric(
                        result.reality_gap_metrics.get("fidelity_score", 1.0)
                    ),
                ),
                pattern_breakdown=result.pattern_breakdown,
            ),
        )

    except ValueError as e:
        logger.warning(f"Engine validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Backtest execution failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {e}",
        ) from e


@app.get("/api/v1/backtests/{id}", response_model=BacktestResponse)
def get_backtest_detail(
    id: str,
    response: Response,
    user: UserResponse = Depends(auth_required),  # noqa: B008
):
    """Get the full details of a specific simulation."""
    response.headers["X-RateLimit-Limit"] = "100"
    response.headers["X-RateLimit-Remaining"] = "99"
    response.headers["X-RateLimit-Reset"] = str(int(time.time() + 3600))

    # Fetch real data from persistence
    sim_data = persistence_service.get_simulation(id, user.id)
    if not sim_data:
        raise HTTPException(status_code=404, detail="Simulation not found")

    # Map database structure back to BacktestResponse
    summary = sim_data.get("summary", {})
    full_result = sim_data.get("full_result", {})
    config_snapshot = sim_data.get("config_snapshot", {})
    normalized_win_rate = normalize_ratio(summary.get("win_rate"), default=0.0)
    normalized_fidelity = normalize_ratio(
        sim_data.get("reality_gap_metrics", {}).get("fidelity_score"), default=1.0
    )

    return BacktestResponse(
        id=id,
        config_snapshot=config_snapshot,
        results=BacktestResults(
            total_return_pct=summary.get("total_return_pct", 0.0),
            win_rate=normalized_win_rate,
            sharpe_ratio=summary.get("sharpe_ratio", 0.0),
            sortino_ratio=summary.get("sortino_ratio", 0.0),
            calmar_ratio=summary.get("calmar_ratio", 0.0),
            profit_factor=summary.get("profit_factor", 0.0),
            expectancy=summary.get("expectancy", 0.0),
            max_drawdown_pct=summary.get("max_drawdown_pct", 0.0),
            equity_curve=full_result.get("equity_curve", []),
            ideal_equity_curve=full_result.get("ideal_equity_curve", []),
            trades=[
                TradeSnippet(
                    entry_time=t.get("entry_time"),
                    entry_price=t.get("entry_price"),
                    exit_price=t.get("exit_price"),
                    pnl_pct=t.get("pnl_pct"),
                )
                for t in full_result.get("trades", [])[:50]
            ],
            reality_gap_metrics=RealityGapMetrics(
                slippage_impact_pct=sim_data.get("reality_gap_metrics", {}).get(
                    "slippage_impact_pct", 0.0
                ),
                fee_impact_pct=sim_data.get("reality_gap_metrics", {}).get(
                    "fee_impact_pct", 0.0
                ),
                vol_hazard_pct=sim_data.get("reality_gap_metrics", {}).get(
                    "vol_hazard_pct", 0.0
                ),
                fidelity_score=normalized_fidelity,
            ),
            pattern_breakdown=full_result.get("pattern_breakdown", {}),
        ),
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
    response.headers["X-RateLimit-Reset"] = str(int(time.time() + 3600))

    try:
        user_id_str = str(user.id)
        # Fetch from persistence with cursor support
        result = persistence_service.get_user_simulations(
            user_id_str,
            limit=limit,
            cursor=cursor,
            strict=True,
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch simulation history.",
            )
        summaries, total, next_cursor = result

        # Map to SimulationLogEntry, ensuring win_rate is decimal
        formatted_simulations = []
        for s in summaries:
            s_copy = s.copy()

            s_copy["win_rate"] = normalize_ratio(s_copy.get("win_rate"), default=0.0)

            # Map fidelity_score securely to 0..1
            s_copy["fidelity_score"] = normalize_ratio(
                s_copy.get("fidelity_score"), default=1.0
            )

            formatted_simulations.append(SimulationLogEntry(**s_copy))

        return PaginatedHistory(
            simulations=formatted_simulations,
            total=total,
            next_cursor=next_cursor,
        )

    except PersistenceError as e:
        logger.error(f"Failed to fetch history due to persistence error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch simulation history.",
        ) from e
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
                summaries_result = persistence_service.get_user_simulations(
                    user_id_str, limit=1
                )
                if summaries_result:
                    summaries, _, _ = summaries_result
                else:
                    summaries = []
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

        # Fetch from Alpaca (via Proxy) if cache miss
        if not assets:
            logger.info("AssetCache miss: fetching from Alpaca Proxy")
            assets = get_alpaca_fetcher().get_active_assets()
            # Update cache
            asset_cache.set(assets)

        # O(N) case-insensitive search across symbol and name
        search_lower = search.lower()
        matched_symbols = {
            asset["symbol"]
            for asset in assets
            if search_lower in asset["symbol"].lower()
            or (asset.get("name") and search_lower in asset["name"].lower())
        }

        # Return alphabetically sorted matches
        return sorted(list(matched_symbols))

    except Exception as e:
        logger.error(f"Failed to fetch assets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch assets.",
        ) from e
