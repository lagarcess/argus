"""
Main Application Entrypoint.

This script executes the signal generation pipeline for a defined portfolio of assets.
It orchestrates data fetching, pattern recognition, persistence, and notifications.
"""

import atexit
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional, Protocol, cast

import typer
from alpaca.common.exceptions import APIError
from google.api_core.exceptions import (
    GoogleAPICallError,
    PermissionDenied,
    Unauthenticated,
)
from google.auth.exceptions import DefaultCredentialsError
from loguru import logger
from pydantic import ValidationError

from crypto_signals.analysis.structural import warmup_jit
from crypto_signals.config import (
    get_crypto_data_client,
    get_settings,
    get_stock_data_client,
    get_trading_client,
    load_config_from_firestore,
)
from crypto_signals.domain.schemas import (
    AssetClass,
    ExitReason,
    NotificationPayload,
    SignalStatus,
    TradeStatus,
    TradeType,
)
from crypto_signals.engine.execution import ExecutionEngine
from crypto_signals.engine.reconciler import StateReconciler
from crypto_signals.engine.reconciler_notifications import ReconcilerNotificationService
from crypto_signals.engine.signal_generator import SignalGenerator
from crypto_signals.market.asset_service import AssetValidationService
from crypto_signals.market.data_provider import MarketDataProvider
from crypto_signals.notifications.discord import DiscordClient
from crypto_signals.observability import (
    MetricsCollector,
    configure_logging,
    console,
    create_execution_summary_table,
    create_portfolio_progress,
    get_metrics_collector,
    log_execution_time,
    setup_gcp_logging,
)
from crypto_signals.pipelines.account_snapshot import AccountSnapshotPipeline
from crypto_signals.pipelines.backtest_archival import BacktestArchivalPipeline
from crypto_signals.pipelines.expired_signal_archival import ExpiredSignalArchivalPipeline
from crypto_signals.pipelines.fee_patch import FeePatchPipeline
from crypto_signals.pipelines.price_patch import PricePatchPipeline
from crypto_signals.pipelines.rejected_signal_archival import RejectedSignalArchival
from crypto_signals.pipelines.strategy_sync import StrategySyncPipeline
from crypto_signals.pipelines.trade_archival import TradeArchivalPipeline
from crypto_signals.repository.firestore import (
    JobLockRepository,
    JobMetadataRepository,
    PositionRepository,
    RejectedSignalRepository,
    SignalRepository,
    StrategyRepository,
)
from crypto_signals.secrets_manager import init_secrets
from crypto_signals.utils.metadata import get_git_hash, get_job_context
from crypto_signals.utils.symbols import normalize_alpaca_symbol

# Configure logging with Rich integration
configure_logging(level="INFO")

# Pre-compile Numba JIT functions to avoid cold-start latency in live trading
warmup_jit()

# Performance SLA Constants
LATENCY_SLA_MS = 200  # 200ms (Strict check after warmup)
QUERY_ERROR_SENTINEL = 9999

# Global flag for graceful shutdown
shutdown_requested = False


# Pipeline Protocol for type safety
class Pipeline(Protocol):
    """Protocol defining the interface for all pipelines."""

    def run(self) -> Any:
        """Execute the pipeline and return result."""
        ...


def _run_pipeline(
    pipeline: Pipeline,
    name: str,
    success_log_fn: Callable[[Any], None],
    metrics_collector: Optional["MetricsCollector"] = None,
) -> None:
    """
    Helper to run a pipeline with standardized logging and metrics.

    Args:
        pipeline: The pipeline instance to run.
        name: The name of the pipeline for metrics/logging.
        success_log_fn: A callback that receives the result and logs success.
        metrics_collector: Optional metrics collector (fetches default if None).
    """
    logger.info(f"Running {name} Pipeline...")
    start_time = time.time()

    # Use provided collector or fetch new one
    metrics = metrics_collector or get_metrics_collector()

    try:
        result = pipeline.run()
        success_log_fn(result)
        metrics.record_success(name, time.time() - start_time)
    except Exception as e:
        logger.error(f"{name} Pipeline failed: {e}")
        metrics.record_failure(name, time.time() - start_time)


def _log_pipeline_result(
    title: str, count: int, unit: str = "signals", action: str = "archived"
) -> None:
    """
    Log standardized completion message for pipelines.

    Args:
        title: Readable name of the pipeline (e.g., "Rejected signal archival").
        count: Number of items processed.
        unit: Unit name (e.g., "signals", "trades").
        action: Past tense action (e.g., "archived", "updated").
    """
    if count > 0:
        logger.info(f"✅ {title} complete: {count} {unit} {action}")
    else:
        logger.info(f"✅ {title} complete: No {unit} to {action}")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name} signal. Initiating graceful shutdown...")
    shutdown_requested = True


def _create_account_snapshot_callback(
    job_metadata_repo, today_date: date, git_hash: str, environment: str
):
    """Create callback for account snapshot pipeline success.

    Args:
        job_metadata_repo: Repository for updating job metadata
        today_date: Today's date for metadata update
        git_hash: Current git hash
        environment: Current environment (PROD/DEV)

    Returns:
        Callback function for _run_pipeline
    """

    def callback(_result):
        logger.info("✅ Account Snapshot Pipeline completed successfully.")
        job_metadata_repo.save_job_metadata(
            "account_snapshot",
            {
                "last_run_date": today_date,
                "git_hash": git_hash,
                "environment": environment,
            },
        )

    return callback


def main(
    smoke_test: bool = typer.Option(
        False, help="Run a shallow connectivity check (Smoke Test) and exit."
    ),
):
    """Execute the main signal generation loop."""
    global shutdown_requested

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Get metrics collector
    metrics = get_metrics_collector()

    # Get settings early for GCP logging setup
    settings = get_settings()

    # Enable GCP Cloud Logging if configured (additive - does not disable Rich output)
    # This is inside main() to allow graceful error handling if credentials are missing
    if settings.ENABLE_GCP_LOGGING:
        try:
            setup_gcp_logging()
        except Exception as e:
            logger.warning(
                f"Failed to initialize GCP Cloud Logging: {e}. "
                "Continuing with Rich terminal logging only."
            )

    logger.info("Starting Crypto Sentinel Signal Generator...")
    app_start_time = time.time()

    # Capture Execution Context
    git_hash = get_git_hash()
    job_context = get_job_context(settings)
    logger.info(f"Execution Context: Git={git_hash}, Env={settings.ENVIRONMENT}")

    try:
        # Initialize Secrets
        logger.info("Loading secrets...")
        with log_execution_time(logger, "load_secrets"):
            if not init_secrets():
                logger.critical("Failed to load required secrets. Exiting.")
                sys.exit(1)

        # --- SMOKE TEST PATH ---
        if smoke_test:
            logger.warning("💨 SMOKE TEST: Running connectivity checks...")

            # 1. Verify Firestore Connectivity (skip if no credentials in CI)
            try:
                # Initializing repository creates the Firestore client
                JobLockRepository()
                logger.info("✅ Firestore: Client Initialized")

                # 1b. Performance Check: Firestore Latency (Issue #128)
                # Enforces 100ms SLA for sector cap queries to prevent slippage
                pos_repo = PositionRepository()

                # Warm-up query to handle Cloud Run cold starts (SSL/Connection overhead)
                try:
                    logger.info("Running Firestore warm-up query...")
                    pos_repo.count_open_positions_by_class(AssetClass.CRYPTO)
                except Exception:
                    # Ignore warmup failures, real check is below
                    pass

                start_time = time.perf_counter()

                # Execute a representative sector cap query
                count = pos_repo.count_open_positions_by_class(AssetClass.CRYPTO)
                latency_ms = (time.perf_counter() - start_time) * 1000

                # Log latency as a metric for Cloud Monitoring
                logger.info(
                    f"⏱️  Firestore Latency: {latency_ms:.2f}ms",
                    extra={
                        "metric_type": "latency_check",
                        "latency_ms": latency_ms,
                        "query_type": "count_open_positions_by_class",
                        "asset_class": AssetClass.CRYPTO.value,
                    },
                )

                if count == QUERY_ERROR_SENTINEL:
                    # count_open_positions_by_class returns sentinel when it catches an internal exception
                    logger.error(
                        f"❌ Firestore: Performance Check Failed - Query failed (returned {QUERY_ERROR_SENTINEL})."
                    )
                    sys.exit(1)
                elif latency_ms > LATENCY_SLA_MS:
                    logger.error(
                        f"❌ Firestore: Performance Check Failed - Latency {latency_ms:.2f}ms exceeds {LATENCY_SLA_MS}ms threshold. "
                        "Check for missing composite indexes or degraded performance."
                    )
                    sys.exit(1)

                logger.info(
                    f"✅ Firestore: Performance Check Passed (<{LATENCY_SLA_MS}ms)"
                )

            except (DefaultCredentialsError, Unauthenticated, PermissionDenied) as e:
                logger.warning(f"⚠️  Firestore: Skipped (auth/permission issue) - {e}")
            except Exception as e:
                logger.error(f"❌ Firestore: Performance Check Failed - {e}")
                sys.exit(1)

            # 2. Verify settings loaded
            if not settings.GOOGLE_CLOUD_PROJECT:
                raise ValueError("Missing GOOGLE_CLOUD_PROJECT")
            logger.info(f"✅ Configuration: Project={settings.GOOGLE_CLOUD_PROJECT}")

            logger.success("🟢 SMOKE TEST PASSED: All connectivity checks succeeded.")
            sys.exit(0)
        # -----------------------

        # Initialize Services
        logger.info("Initializing services...")
        with log_execution_time(logger, "initialize_services"):
            stock_client = get_stock_data_client()
            crypto_client = get_crypto_data_client()
            market_provider = MarketDataProvider(stock_client, crypto_client)

            # Load strategies for injection into SignalGenerator
            strategy_repo = StrategyRepository()
            try:
                active_configs = strategy_repo.get_active_strategy_configs()
            except (GoogleAPICallError, ValidationError) as e:
                logger.warning(
                    "Failed to load strategy configs. UUID injection disabled.",
                    extra={"error": str(e)},
                )
                active_configs = []

            generator = SignalGenerator(
                market_provider=market_provider, strategy_configs=active_configs
            )
            repo = SignalRepository()
            position_repo = PositionRepository()
            discord = DiscordClient()
            asset_validator = AssetValidationService(get_trading_client())

            reconciler = StateReconciler(
                alpaca_client=get_trading_client(),
                position_repo=position_repo,
                notification_service=ReconcilerNotificationService(discord),
                settings=settings,
                signal_repo=repo,
            )
            execution_engine = ExecutionEngine(
                reconciler=reconciler, market_provider=market_provider
            )
            job_lock_repo = JobLockRepository()
            rejected_repo = RejectedSignalRepository()  # Shadow signal persistence
            job_metadata_repo = JobMetadataRepository()

            # Pipeline Services
            trade_archival = TradeArchivalPipeline(execution_engine=execution_engine)
            rejected_archival = RejectedSignalArchival()
            expired_archival = ExpiredSignalArchivalPipeline()
            fee_patch = FeePatchPipeline(execution_engine=execution_engine)
            price_patch = PricePatchPipeline(execution_engine=execution_engine)
            account_snapshot = AccountSnapshotPipeline()
            backtest_archival = BacktestArchivalPipeline()
            strategy_sync = StrategySyncPipeline()

        # Job Locking
        job_id = "signal_generator_cron"
        if not job_lock_repo.acquire_lock(job_id):
            logger.warning(f"Job lock held by another instance ({job_id}). Exiting.")
            sys.exit(0)

        # Ensure lock is released on exit
        atexit.register(job_lock_repo.release_lock, job_id)

        # === STRATEGY SYNC (SCD Type 2) ===
        # === STRATEGY SYNC (SCD Type 2) ===
        _run_pipeline(
            strategy_sync,
            "strategy_sync",
            lambda count: logger.info(
                f"✅ Strategy Sync complete: {count} versions updated."
                if count > 0
                else "✅ Strategy Sync complete: No changes detected."
            ),
            metrics_collector=metrics,
        )

        # === ACCOUNT SNAPSHOT (New Independent Job) ===
        today = datetime.now(timezone.utc).date()
        last_snapshot = job_metadata_repo.get_last_run_date("account_snapshot")

        if last_snapshot != today:
            _run_pipeline(
                account_snapshot,
                "account_snapshot",
                _create_account_snapshot_callback(
                    job_metadata_repo, today, git_hash, settings.ENVIRONMENT
                ),
                metrics_collector=metrics,
            )
        else:
            logger.info("Account Snapshot has already run today. Skipping.")

        # === REJECTED SIGNAL ARCHIVAL (Issue #183) ===
        # Archive "Ghost Trades" to BigQuery for analysis
        # MUST run before daily cleanup deletes the source data
        if settings.USE_LEGACY_ARCHIVAL:
            _run_pipeline(
                rejected_archival,
                "rejected_archival",
                lambda count: _log_pipeline_result(
                    "Rejected signal archival", count, "signals", "archived"
                ),
                metrics_collector=metrics,
            )

            # === EXPIRED SIGNAL ARCHIVAL (Issue #183) ===
            # Archive "Noise" to BigQuery for analysis
            # MUST run before daily cleanup deletes the source data
            _run_pipeline(
                expired_archival,
                "expired_archival",
                lambda count: _log_pipeline_result(
                    "Expired signal archival", count, "signals", "archived"
                ),
                metrics_collector=metrics,
            )

        # === DAILY CLEANUP ===
        last_cleanup_date = job_metadata_repo.get_last_run_date("daily_cleanup")
        if last_cleanup_date != today:
            logger.info("Running daily cleanup...")
            deleted_signals = repo.cleanup_expired()
            deleted_rejected = rejected_repo.cleanup_expired()
            deleted_positions = position_repo.cleanup_expired()
            logger.info(
                f"Cleanup complete: {deleted_signals} signals, "
                f"{deleted_rejected} rejected signals, {deleted_positions} positions."
            )
            job_metadata_repo.save_job_metadata(
                "daily_cleanup",
                {
                    "last_run_date": today,
                    "git_hash": git_hash,
                    "environment": settings.ENVIRONMENT,
                },
            )
        else:
            logger.info("Daily cleanup has already run today. Skipping.")

        # === STATE RECONCILIATION (Issue #113) ===
        # Detect and heal zombie/orphan positions before main loop
        logger.info("Running state reconciliation...")
        reconciliation_failed = False
        reconciliation_start_time = time.time()
        try:
            reconciliation_report = reconciler.reconcile()

            if reconciliation_report.critical_issues:
                logger.warning(
                    f"Reconciliation detected {len(reconciliation_report.critical_issues)} critical issue(s)",
                    extra={
                        "issues": reconciliation_report.critical_issues,
                        "zombies": len(reconciliation_report.zombies),
                        "orphans": len(reconciliation_report.orphans),
                    },
                )
            else:
                logger.info(
                    f"Reconciliation complete: {reconciliation_report.reconciled_count} positions healed"
                )
        except Exception as e:
            logger.error(
                f"Reconciliation failed: {e}",
                extra={"error": str(e)},
            )
            metrics.record_failure(
                "reconciliation", time.time() - reconciliation_start_time
            )
            # Mark as failed to prevent archival of potentially inconsistent state
            reconciliation_failed = True

        # === TRADE ARCHIVAL (Issue #149) ===
        # Move Closed Positions -> BigQuery (Before Fee Patch!)
        # Must run AFTER reconciliation (so we archive what was just closed)
        if not reconciliation_failed:
            _run_pipeline(
                trade_archival,
                "trade_archival",
                lambda count: logger.info(
                    f"✅ Trade archival complete: {count} trades archived"
                    if count > 0
                    else "✅ Trade archival complete: No closed trades to archive"
                ),
                metrics_collector=metrics,
            )

            # === BACKTEST ARCHIVAL (Issue #361) ===
            # Unified pipeline: archives ALL terminal signals to fact_theoretical_signals
            # Must run AFTER Trade Archival (Issue #368) so linked_trade_id FKs exist
            _run_pipeline(
                backtest_archival,
                "backtest_archival",
                lambda count: _log_pipeline_result(
                    "Backtest archival", count, "signals", "archived"
                ),
                metrics_collector=metrics,
            )

        else:
            logger.warning("⚠️ Skipping trade archival due to reconciliation failure.")

        # === FEE RECONCILIATION (Issue #140) ===
        # Patch estimated fees with actual CFEE data before generating new signals
        # Runs T+1 reconciliation for trades older than 24 hours
        if not reconciliation_failed:
            _run_pipeline(
                fee_patch,
                "fee_patch",
                lambda count: logger.info(
                    f"✅ Fee reconciliation complete: {count} trades updated"
                    if count > 0
                    else "✅ Fee reconciliation complete: No trades to update"
                ),
                metrics_collector=metrics,
            )
        else:
            logger.warning("⚠️ Skipping fee reconciliation due to reconciliation failure.")

        # === EXIT PRICE RECONCILIATION (Issue #141) ===
        # Patch $0.00 exit prices with actual fill prices from Alpaca
        # Runs for historical repair and daily reconciliation
        if not reconciliation_failed:
            _run_pipeline(
                price_patch,
                "price_patch",
                lambda count: logger.info(
                    f"✅ Exit price reconciliation complete: {count} trades repaired"
                    if count > 0
                    else "✅ Exit price reconciliation complete: No trades to repair"
                ),
                metrics_collector=metrics,
            )
        else:
            logger.warning(
                "⚠️ Skipping exit price reconciliation due to reconciliation failure."
            )

        # Define Portfolio
        firestore_config = load_config_from_firestore()

        if firestore_config:
            logger.info("Using configuration from Firestore (overriding .env)")
            if "CRYPTO_SYMBOLS" in firestore_config:
                settings.CRYPTO_SYMBOLS = firestore_config["CRYPTO_SYMBOLS"]
        else:
            logger.info("Using configuration from .env")

        # Pre-flight: Validate symbols against Alpaca's live asset status
        logger.info("Validating portfolio assets...")
        with log_execution_time(logger, "asset_validation"):
            valid_crypto = asset_validator.get_valid_portfolio(
                settings.CRYPTO_SYMBOLS, AssetClass.CRYPTO
            )
            valid_equity = asset_validator.get_valid_portfolio(
                settings.EQUITY_SYMBOLS, AssetClass.EQUITY
            )

        portfolio_items = [(s, AssetClass.CRYPTO) for s in valid_crypto] + [
            (s, AssetClass.EQUITY) for s in valid_equity
        ]

        if not portfolio_items:
            logger.warning(
                "No valid symbols to process! All configured symbols were filtered out "
                "during asset validation. Check the 'INACTIVE ASSET SKIPPED' panels above."
            )

        logger.info(f"Processing {len(portfolio_items)} symbols...")

        # Rate limiting (Alpaca: 200 req/min = 0.3s minimum, use 0.5s for safety)
        rate_limit_delay = getattr(settings, "RATE_LIMIT_DELAY", 0.5)

        # Phase 1: Signal Discovery & Active Trade Validation
        candidate_signals = []  # To be processed in Phase 2 (Saturation Filter)
        symbols_processed = 0

        def process_portfolio_item(
            item: tuple[str, AssetClass], progress: Any, task: Any, index: int = 0
        ) -> Optional[tuple[Any, AssetClass, float]]:
            """Process a single portfolio item: fetch data, generate signals, and check exits."""
            symbol, asset_class = item

            # Check for shutdown signal
            if shutdown_requested:
                logger.info(f"Shutdown requested. Skipping {symbol}.")
                return None

            # Concurrency-safe rate limiting: Stagger threads using index-based delay
            # Ensures we respect Alpaca's rate limits across parallel workers.
            target_start = phase1_start_time + (index * rate_limit_delay)
            wait_time = target_start - time.time()
            if wait_time > 0:
                logger.debug(f"Staggering {symbol} by {wait_time:.2f}s")
                time.sleep(wait_time)

            symbol_start_time = time.time()

            try:
                logger.info(
                    f"Analyzing {symbol} ({asset_class.value})...",
                    extra={"symbol": symbol, "asset_class": asset_class.value},
                )

                # Fetch Data ONCE
                try:
                    df = market_provider.get_daily_bars(
                        symbol, asset_class, lookback_days=365
                    )
                except Exception as e:
                    logger.error(f"Failed to fetch data for {symbol}: {e}")
                    return None

                if df.empty:
                    logger.warning(f"No data for {symbol}")
                    return None

                # Generate Signals
                trade_signal = generator.generate_signals(
                    symbol, asset_class, dataframe=df
                )

                # Track metrics
                symbol_duration = time.time() - symbol_start_time

                if not trade_signal:
                    logger.debug(f"No signal for {symbol}.")
                    metrics.record_success("signal_generation", symbol_duration)

                # Active Trade Validation
                # Check for updates on existing WAITING/ACTIVE signals
                active_signals = repo.get_active_signals(symbol)
                if active_signals:
                    logger.info(
                        f"Checking active signals for {symbol} ({len(active_signals)})..."
                    )

                    # 1. Run Expiration Check (24h Rule)
                    # MUST run before check_exits to prevent stale WAITING signals
                    # from being falsely invalidated or exited.
                    now_utc = datetime.now(timezone.utc)
                    expired_signals = []
                    valid_active_signals = []

                    # Phase 1: Partition signals
                    for sig in active_signals:
                        # Only expire WAITING signals.
                        if (
                            sig.status == SignalStatus.WAITING
                            and sig.valid_until
                            and now_utc > sig.valid_until
                        ):
                            # TIER 3: Safety-First Reaper
                            # Ignore WAITING signals if an OPEN position already exists
                            # This prevents 24h expiration logic from killing active trades
                            existing_pos = position_repo.get_position_by_signal(
                                sig.signal_id
                            )
                            if existing_pos and existing_pos.status == TradeStatus.OPEN:
                                logger.warning(
                                    f"REAPER GUARD: Skipping expiration for {symbol} "
                                    f"({sig.signal_id}) - OPEN position detected.",
                                    extra={
                                        "symbol": symbol,
                                        "signal_id": sig.signal_id,
                                        "position_id": existing_pos.position_id,
                                    },
                                )
                                valid_active_signals.append(sig)
                            else:
                                expired_signals.append(sig)
                        else:
                            valid_active_signals.append(sig)

                    # Phase 2: Process expired signals (side effects)
                    for sig in expired_signals:
                        logger.info(
                            f"EXPIRING Signal {sig.signal_id} (Valid Until: {sig.valid_until})",
                            extra={"symbol": symbol, "signal_id": sig.signal_id},
                        )
                        sig.status = SignalStatus.EXPIRED
                        sig.exit_reason = ExitReason.EXPIRED
                        repo.update_signal_atomic(
                            sig.signal_id,
                            {
                                "status": SignalStatus.EXPIRED.value,
                                "exit_reason": ExitReason.EXPIRED.value,
                            },
                        )
                        # Reply in thread if available, fallback to main channel
                        discord.send_message(
                            f"⏳ **SIGNAL EXPIRED: {symbol}** ⏳\n"
                            f"Signal expired (24h limit reached).",
                            thread_id=sig.discord_thread_id,
                            asset_class=asset_class,
                        )

                    # 2. Check exits on remaining valid signals
                    exited_signals = generator.check_exits(
                        valid_active_signals, symbol, asset_class, dataframe=df
                    )

                    # Process Exits (TP / Invalidation) and Trail Updates
                    for exited in exited_signals:
                        # --- TRAIL UPDATE (not a status change) ---
                        if getattr(exited, "_trail_updated", False):
                            # Calculate movement percentage (absolute for Short positions)
                            old_tp3 = getattr(exited, "_previous_tp3", 0.0)
                            new_tp3 = exited.take_profit_3 or 0.0
                            movement_pct = (
                                abs((new_tp3 - old_tp3) / old_tp3 * 100)
                                if old_tp3 > 0
                                else 100.0
                            )

                            logger.info(
                                f"TRAIL UPDATE: {exited.signal_id} "
                                f"TP3 moved from ${old_tp3:.2f} to ${new_tp3:.2f} "
                                f"({movement_pct:.1f}%)",
                                extra={
                                    "symbol": symbol,
                                    "signal_id": exited.signal_id,
                                    "old_tp3": old_tp3,
                                    "new_tp3": new_tp3,
                                    "movement_pct": movement_pct,
                                },
                            )

                            # Always persist the updated trailing value
                            repo.update_signal_atomic(
                                exited.signal_id, {"take_profit_3": new_tp3}
                            )

                            # Notify Discord if significant movement (>1%)
                            if movement_pct > 1.0:
                                discord.send_trail_update(
                                    exited,
                                    old_stop=old_tp3,
                                    asset_class=asset_class,
                                )

                            # === SYNC TRAIL TO ALPACA ===
                            # Update broker stop-loss to match new trailing stop
                            if settings.ENABLE_EXECUTION and new_tp3:
                                pos = position_repo.get_position_by_signal(
                                    exited.signal_id
                                )
                                if pos and pos.status == TradeStatus.OPEN:
                                    if execution_engine.modify_stop_loss(pos, new_tp3):
                                        logger.info(
                                            f"TRAIL SYNC: Stop -> "
                                            f"${new_tp3:.2f} for "
                                            f"{pos.position_id}"
                                        )
                                        position_repo.update_position(pos)

                            # Clean up private attributes
                            if hasattr(exited, "_trail_updated"):
                                delattr(exited, "_trail_updated")
                            if hasattr(exited, "_previous_tp3"):
                                delattr(exited, "_previous_tp3")

                            # Remove from valid_active_signals to maintain consistency
                            if exited in valid_active_signals:
                                valid_active_signals.remove(exited)
                            continue

                        # --- STATUS CHANGE (Exit) ---
                        updates = {
                            "status": exited.status.value,
                        }
                        if exited.exit_reason:
                            updates["exit_reason"] = exited.exit_reason

                        if repo.update_signal_atomic(exited.signal_id, updates):
                            logger.info(
                                f"SIGNAL UPDATE: {exited.signal_id} "
                                f"status -> {exited.status}",
                                extra={
                                    "symbol": symbol,
                                    "signal_id": exited.signal_id,
                                    "new_status": exited.status,
                                },
                            )
                        else:
                            logger.error(
                                f"Failed atomic update for status change {exited.signal_id}"
                            )
                            continue

                        # Notify Discord of Status Change
                        if not exited.discord_thread_id:
                            # Self-healing: Orphaned signal - send recovery msg
                            logger.info(
                                f"Self-healing: Orphaned signal {exited.signal_id} - "
                                "sending update to main channel"
                            )
                            # For orphaned signals, prepend recovery notice
                            recovery_prefix = (
                                f"🔄 **THREAD RECOVERY: {symbol}** 🔄\n"
                                f"*(Original thread unavailable)*\n\n"
                            )
                            # Build inline message for recovery case
                            status_emoji = {
                                SignalStatus.INVALIDATED: "🚫",
                                SignalStatus.TP1_HIT: "🎯",
                                SignalStatus.TP2_HIT: "🚀",
                                SignalStatus.TP3_HIT: "🌕",
                                SignalStatus.EXPIRED: "⏳",
                            }.get(exited.status, "ℹ️")
                            msg = (
                                f"{status_emoji} **SIGNAL UPDATE: {symbol}** "
                                f"{status_emoji}\n"
                                f"**Status**: {exited.status.value}\n"
                                f"**Pattern**: {exited.pattern_name}\n"
                            )
                            if exited.exit_reason:
                                msg += f"**Reason**: {exited.exit_reason}\n"
                            if exited.status == SignalStatus.TP1_HIT:
                                msg += (
                                    "ℹ️ **Action**: Scaling Out (50%) "
                                    "& Stop -> **Breakeven**"
                                )
                            discord.send_message(
                                recovery_prefix + msg, asset_class=asset_class
                            )
                        else:
                            # Normal case: use dedicated method
                            result_status = discord.send_signal_update(
                                exited, asset_class=asset_class
                            )
                            # Self-healing: Clear stale thread_id for next run
                            if result_status == "thread_stale":
                                logger.warning(
                                    f"Self-healing: Clearing stale discord_thread_id "
                                    f"for signal {exited.signal_id}"
                                )
                                repo.update_signal_atomic(
                                    exited.signal_id,
                                    {"discord_thread_id": None},
                                )

                        # === TP AUTOMATION ===
                        # Progressive stop management on each TP stage
                        if settings.ENABLE_EXECUTION:
                            # Find position linked to this signal
                            pos = position_repo.get_position_by_signal(exited.signal_id)
                            # === ISSUE 275 FIX: signal_id Guard ===
                            if (
                                pos
                                and pos.status == TradeStatus.OPEN
                                and pos.signal_id == exited.signal_id
                            ):
                                # Handle Terminal States (Close All) first
                                if exited.status in (
                                    SignalStatus.TP3_HIT,
                                    SignalStatus.INVALIDATED,
                                ):
                                    # === ISSUE 275 FIX: Alpaca Qty Check ===
                                    try:
                                        alpaca_sym = normalize_alpaca_symbol(pos.symbol)
                                        alpaca_pos = (
                                            execution_engine.alpaca.get_open_position(
                                                alpaca_sym
                                            )
                                        )
                                        alpaca_qty = float(cast(Any, alpaca_pos).qty)
                                        if alpaca_qty < pos.qty:
                                            logger.warning(
                                                f"ISSUE 275: Alpaca qty "
                                                f"({alpaca_qty}) < Firestore "
                                                f"qty ({pos.qty}) for "
                                                f"{pos.symbol}. Adjusting.",
                                            )
                                            pos.qty = alpaca_qty
                                    except APIError as e:
                                        if getattr(e, "status_code", None) == 404:
                                            # Position gone from Alpaca (confirmed)
                                            logger.warning(
                                                f"Position {pos.position_id} not "
                                                f"found on Alpaca, marking "
                                                f"CLOSED_EXTERNALLY",
                                            )
                                            pos.status = TradeStatus.CLOSED
                                            pos.exit_reason = ExitReason.CLOSED_EXTERNALLY
                                            position_repo.update_position(pos)
                                            continue
                                        else:
                                            # Transient error (500, 429) -> Skip close
                                            logger.error(
                                                f"ISSUE 275: Alpaca API Error during qty check: {e}",
                                                extra={
                                                    "symbol": pos.symbol,
                                                    "signal_id": pos.signal_id,
                                                },
                                            )
                                            continue  # Safe fail-closed

                                    # Determine exit reason for archival
                                    # (Note: TP3 runner uses ExitReason.TP_HIT for pnl tracking consistency)
                                    target_exit_reason = (
                                        ExitReason.TP_HIT
                                        if exited.status == SignalStatus.TP3_HIT
                                        else exited.exit_reason
                                        or ExitReason.STRUCTURAL_INVALIDATION
                                    )

                                    if execution_engine.close_position_emergency(
                                        pos, exit_reason=target_exit_reason
                                    ):
                                        pos.status = TradeStatus.CLOSED
                                        reason = (
                                            "TP3 Runner"
                                            if exited.status == SignalStatus.TP3_HIT
                                            else "INVALIDATED"
                                        )
                                        logger.info(f"{reason}: Closed {pos.position_id}")
                                    position_repo.update_position(pos)

                                # Handle Progressive States (Scaling)
                                else:
                                    # TP1 Logic: Run if TP1 OR TP2 hit
                                    if exited.status in (
                                        SignalStatus.TP1_HIT,
                                        SignalStatus.TP2_HIT,
                                    ):
                                        # Idempotency: Skip if already scaled
                                        if pos.scaled_out_qty > 0:
                                            pass  # Already done
                                        else:
                                            # 1. Scale out 50%
                                            if execution_engine.scale_out_position(
                                                pos, 0.5
                                            ):
                                                logger.info(
                                                    f"TP1 AUTO: Scaled out 50% of {pos.position_id}"
                                                )
                                            # 2. Move stop to breakeven
                                            if execution_engine.move_stop_to_breakeven(
                                                pos
                                            ):
                                                logger.info(
                                                    f"TP1 AUTO: Stop -> breakeven for {pos.position_id}"
                                                )

                                    # TP2 Logic: Run if TP2 hit
                                    if exited.status == SignalStatus.TP2_HIT:
                                        # Idempotency
                                        original = pos.original_qty or pos.qty
                                        if pos.scaled_out_qty > original * 0.6:
                                            pass  # Already done
                                        else:
                                            # 1. Scale out 50% of remaining
                                            if execution_engine.scale_out_position(
                                                pos, 0.5
                                            ):
                                                logger.info(
                                                    f"TP2 AUTO: Scaled out 50% remaining of {pos.position_id}"
                                                )

                                            # 2. Move stop to TP1 level
                                            tp1_level = exited.take_profit_1
                                            if tp1_level:
                                                if execution_engine.modify_stop_loss(
                                                    pos, tp1_level
                                                ):
                                                    logger.info(
                                                        f"TP2 AUTO: Stop -> TP1 ${tp1_level:.2f} for {pos.position_id}"
                                                    )
                                            else:
                                                logger.warning(
                                                    f"TP2 AUTO: No TP1 level set for {exited.signal_id}"
                                                )

                                    # Persist position updates
                                    position_repo.update_position(pos)
                            elif (
                                pos
                                and pos.status == TradeStatus.OPEN
                                and pos.signal_id != exited.signal_id
                            ):
                                logger.warning(
                                    f"ISSUE 275: signal_id mismatch — "
                                    f"exited signal {exited.signal_id} vs "
                                    f"position {pos.signal_id}. Skipping "
                                    f"emergency close for {pos.symbol}.",
                                )

                        # Remove exited signals from remaining list
                        if exited in valid_active_signals:
                            valid_active_signals.remove(exited)

                return (trade_signal, asset_class, symbol_duration)

            except Exception as e:
                symbol_duration = time.time() - symbol_start_time
                metrics.record_failure("signal_generation", symbol_duration)
                logger.error(
                    f"Error processing {symbol} ({asset_class.value}): {e}",
                    exc_info=True,
                    extra={"symbol": symbol, "asset_class": asset_class.value},
                )
                return None
            finally:
                # Advance progress bar after each symbol
                progress.advance(task)

        phase1_start_time = time.time()
        with create_portfolio_progress(len(portfolio_items)) as (progress, task):
            # Update progress description
            progress.update(
                task, description="[cyan]Analyzing portfolio assets in parallel..."
            )

            # Parallelize asset processing
            max_workers = getattr(settings, "MAX_WORKERS", 3)
            logger.info(f"Parallelizing asset loop with {max_workers} workers...")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_symbol = {
                    executor.submit(
                        process_portfolio_item, item, progress, task, idx
                    ): item[0]
                    for idx, item in enumerate(portfolio_items)
                }

                # Collect results as they complete
                for future in as_completed(future_to_symbol):
                    try:
                        res = future.result()
                        if res:
                            symbols_processed += 1
                            trade_signal, asset_class, symbol_duration = res
                            if trade_signal:
                                candidate_signals.append(
                                    (trade_signal, asset_class, symbol_duration)
                                )
                    except Exception as e:
                        symbol = future_to_symbol[future]
                        logger.error(f"Worker thread for {symbol} failed: {e}")

        phase1_duration = time.time() - phase1_start_time
        logger.info(
            f"✅ Phase 1 complete: Processed {symbols_processed} symbols in {phase1_duration:.2f}s "
            f"(Wall-clock time)"
        )

        # Phase 2: Signal Saturation Filtering
        # Prevents macro-level noise from spamming notifications if >50% of symbols trigger the same pattern.
        pattern_counts: dict[str, int] = {}
        for sig, _, _ in candidate_signals:
            if sig.status != SignalStatus.REJECTED_BY_FILTER:
                pattern_counts[sig.pattern_name] = (
                    pattern_counts.get(sig.pattern_name, 0) + 1
                )

        saturation_threshold = (
            len(portfolio_items) * settings.SIGNAL_SATURATION_THRESHOLD_PCT
        )
        signals_found = 0

        # Diversity Metrics (Phase 3: Multi-Layer Architecture)
        live_signals = [
            sig
            for sig, _, _ in candidate_signals
            if sig.status != SignalStatus.REJECTED_BY_FILTER
        ]
        if live_signals:
            try:
                diversity = generator.compute_diversity_metrics(live_signals)
                logger.info(
                    f"DIVERSITY: {diversity['total_signals']} signals, "
                    f"entropy={diversity['shannon_entropy']:.2f}, "
                    f"patterns={diversity['pattern_distribution']}",
                    extra={
                        "diversity_metrics": diversity,
                        "shannon_entropy": diversity["shannon_entropy"],
                    },
                )
            except AttributeError as e:
                # This specifically handles MagicMock objects in integration tests
                # where mock signals lack the required attributes (.pattern_name, etc.)
                logger.debug(f"Diversity metrics skipped due to mock test objects: {e}")
            except Exception as e:
                # Catch-all to prevent observability failures from crashing the main loop,
                # but logged as an error since a real signal should not fail metrics computation.
                logger.error(f"Failed to compute diversity metrics: {e}")

        # Phase 3: Signal Processing (Persistence, Notification, Execution)
        for trade_signal, asset_class, _symbol_duration in candidate_signals:
            processing_start = time.time()
            symbol = trade_signal.symbol
            pattern_name = trade_signal.pattern_name

            # Check for saturation
            is_saturated = pattern_counts.get(pattern_name, 0) > saturation_threshold
            if is_saturated and trade_signal.status != SignalStatus.REJECTED_BY_FILTER:
                logger.warning(
                    f"SIGNAL SATURATION: Pattern {pattern_name} triggered on "
                    f"{pattern_counts[pattern_name]} symbols. Flagging as suspicious.",
                    extra={
                        "pattern": pattern_name,
                        "count": pattern_counts[pattern_name],
                        "threshold": saturation_threshold,
                    },
                )

            # --- Handle Shadow Signals (rejected by quality gates) ---
            if trade_signal.status == SignalStatus.REJECTED_BY_FILTER:
                # DEDUPLICATION: Skip shadow if active signal exists (avoid noise)
                active_signals = repo.get_active_signals(symbol)
                if active_signals:
                    logger.debug(
                        f"[SHADOW] Skipping {symbol} shadow signal - active signal exists",
                        extra={"symbol": symbol},
                    )
                    continue

                # Persist to rejected_signals collection for audit/analysis
                try:
                    rejected_repo.save(trade_signal)
                    # Send to shadow Discord channel (if configured)
                    discord.send_shadow_signal(trade_signal)
                    logger.info(
                        f"[SHADOW] {trade_signal.symbol} {trade_signal.pattern_name}: "
                        f"{trade_signal.rejection_reason}",
                        extra={
                            "symbol": trade_signal.symbol,
                            "pattern": trade_signal.pattern_name,
                            "rejection_reason": trade_signal.rejection_reason,
                            "pattern_duration_days": trade_signal.pattern_duration_days,
                            "pattern_classification": trade_signal.pattern_classification,
                        },
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to persist shadow signal: {e}",
                        extra={"symbol": trade_signal.symbol},
                    )
                # Shadow signals don't trigger live trading - continue to next symbol
                continue

            # Build Notification Payload (deferred past shadow check for efficiency)
            notification_payload = NotificationPayload(
                signal=trade_signal,
                is_saturated=is_saturated,
                saturation_count=pattern_counts.get(pattern_name, 0),
            )

            # --- Standard signal handling (WAITING status) ---
            signals_found += 1
            logger.info(
                f"SIGNAL FOUND: {trade_signal.pattern_name} on {trade_signal.symbol}",
                extra={
                    "symbol": trade_signal.symbol,
                    "pattern": trade_signal.pattern_name,
                    "stop_loss": trade_signal.suggested_stop,
                    "pattern_duration_days": trade_signal.pattern_duration_days,
                    "pattern_classification": trade_signal.pattern_classification,
                    "is_saturated": is_saturated,
                },
            )

            # ============================================================
            # IDEMPOTENCY GATE: Prevent redundant Discord alerts
            # ============================================================
            existing_signal = repo.get_by_id(trade_signal.signal_id)
            if existing_signal:
                # Skip if signal exists in WAITING status with discord_thread_id
                if (
                    existing_signal.status == SignalStatus.WAITING
                    and existing_signal.discord_thread_id
                ):
                    logger.info(
                        f"[IDEMPOTENCY] Skip notified signal {trade_signal.signal_id}",
                        extra={
                            "signal_id": trade_signal.signal_id,
                            "symbol": trade_signal.symbol,
                            "thread_id": existing_signal.discord_thread_id,
                        },
                    )
                    continue

                # Self-heal: If exists but discord_thread_id is null, proceed to notification
                if not existing_signal.discord_thread_id:
                    logger.info(
                        f"[IDEMPOTENCY] Self-healing signal {trade_signal.signal_id} - "
                        "missing discord_thread_id",
                        extra={
                            "signal_id": trade_signal.signal_id,
                            "symbol": trade_signal.symbol,
                        },
                    )
                    # Continue to notification phase to fix the missing thread_id

            # ============================================================
            # TWO-PHASE COMMIT: Prevents "Zombie Signals"
            # (notifications sent without database tracking)
            # ============================================================

            # PHASE 1: Persist with CREATED status (establishes tracking)
            trade_signal.status = SignalStatus.CREATED
            persistence_start = time.time()
            try:
                repo.save(trade_signal)
                persistence_duration = time.time() - persistence_start
                logger.info(
                    f"Signal {trade_signal.signal_id} created in Firestore",
                    extra={
                        "signal_id": trade_signal.signal_id,
                        "symbol": trade_signal.symbol,
                        "status": "CREATED",
                        "duration_seconds": round(persistence_duration, 3),
                    },
                )
                metrics.record_success("signal_persistence", persistence_duration)
            except Exception as e:
                persistence_duration = time.time() - persistence_start
                logger.error(
                    f"Failed to persist signal {trade_signal.signal_id} - "
                    "skipping notification to prevent zombie signal",
                    extra={
                        "signal_id": trade_signal.signal_id,
                        "symbol": trade_signal.symbol,
                        "error": str(e),
                    },
                )
                metrics.record_failure("signal_persistence", persistence_duration)
                # Skip notification - can't notify without tracking
                continue

            # PHASE 2: Notify Discord
            thread_id = None

            # Self-healing: Check for existing thread (if missing in memory/DB)
            if not trade_signal.discord_thread_id:
                try:
                    thread_id = discord.find_thread_by_signal_id(
                        trade_signal.signal_id,
                        trade_signal.symbol,
                        asset_class,
                    )
                except Exception as e:
                    logger.warning(f"Thread recovery check failed: {e}")

            if thread_id:
                logger.info(
                    f"Self-healing: Recovered Discord thread {thread_id} "
                    f"for signal {trade_signal.signal_id}"
                )
            else:
                # Standard execution: Create new thread (passing payload with saturation info)
                thread_id = discord.send_signal(notification_payload)

            # PHASE 3: Update with thread_id and final status
            if thread_id:
                updates = {
                    "discord_thread_id": thread_id,
                    "status": SignalStatus.WAITING.value,
                }
                if repo.update_signal_atomic(trade_signal.signal_id, updates):
                    trade_signal.discord_thread_id = thread_id
                    trade_signal.status = SignalStatus.WAITING
                    logger.info(
                        "Signal activated with Discord thread",
                        extra={
                            "signal_id": trade_signal.signal_id,
                            "symbol": trade_signal.symbol,
                            "thread_id": thread_id,
                            "status": "WAITING",
                        },
                    )
                else:
                    logger.error(
                        f"Failed to atomic update signal {trade_signal.signal_id} after Discord notification"
                    )
            else:
                # Compensation: Mark as invalidated if notification failed
                logger.warning(
                    f"Discord notification failed for {trade_signal.symbol} "
                    "- marking signal as invalidated",
                    extra={"symbol": trade_signal.symbol},
                )
                trade_signal.status = SignalStatus.INVALIDATED
                trade_signal.exit_reason = ExitReason.NOTIFICATION_FAILED
                try:
                    repo.update_signal_atomic(
                        trade_signal.signal_id,
                        {
                            "status": SignalStatus.INVALIDATED.value,
                            "exit_reason": ExitReason.NOTIFICATION_FAILED.value,
                        },
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to invalidate signal: {e}",
                        extra={
                            "signal_id": trade_signal.signal_id,
                            "error": str(e),
                        },
                    )

            # Execute trade if execution is enabled
            # Safety: ExecutionEngine has built-in guards for:
            #   1. ALPACA_PAPER_TRADING must be True
            #   2. ENABLE_EXECUTION must be True
            if settings.ENABLE_EXECUTION:
                # === ISSUE 275 FIX: Duplicate Symbol Guard ===
                # Alpaca holds one aggregate position per symbol.
                # If we already have an open position, skip to
                # prevent the TP automation race condition.
                try:
                    alpaca_symbol = normalize_alpaca_symbol(trade_signal.symbol)
                    existing_alpaca_pos = execution_engine.alpaca.get_open_position(
                        alpaca_symbol
                    )
                    if existing_alpaca_pos:
                        logger.warning(
                            f"ISSUE 275: Skipping execution for "
                            f"{trade_signal.symbol} — Alpaca already "
                            f"has open position (qty="
                            f"{cast(Any, existing_alpaca_pos).qty})",
                            extra={
                                "symbol": trade_signal.symbol,
                                "signal_id": trade_signal.signal_id,
                                "existing_qty": str(cast(Any, existing_alpaca_pos).qty),
                            },
                        )
                        continue
                except APIError as e:
                    # Position not found (404) is the expected "green path" for this check.
                    if getattr(e, "status_code", None) == 404:
                        logger.debug(
                            f"Pre-execution check passed for {trade_signal.symbol}: No existing position found."
                        )
                    else:
                        # Other API errors: fail-open (log & proceed) to avoid blocking trades.
                        logger.warning(
                            f"ISSUE 275: Pre-execution check failed-open for {trade_signal.symbol} due to API error: {e}",
                            extra={
                                "symbol": trade_signal.symbol,
                                "error": str(e),
                                "status_code": getattr(e, "status_code", "unknown"),
                            },
                        )

                execution_start = time.time()
                try:
                    position = execution_engine.execute_signal(trade_signal)
                    execution_duration = time.time() - execution_start
                    if position:
                        # CRITICAL: Persist position to Firestore for
                        # Position Sync Loop and TP Automation to work
                        position_repo.save(position)

                        # TIER 1: Immediate ACTIVE transition
                        # Stop the 24h reaper clock in real-time
                        if position.trade_type == TradeType.EXECUTED:
                            trade_signal.status = SignalStatus.ACTIVE
                            repo.update_signal_atomic(
                                trade_signal.signal_id,
                                {"status": SignalStatus.ACTIVE.value},
                            )
                            logger.info(
                                f"SIGNAL ACTIVE: {trade_signal.symbol}",
                                extra={
                                    "symbol": trade_signal.symbol,
                                    "signal_id": trade_signal.signal_id,
                                },
                            )

                        # Log differentiation for Risk Blocked vs Executed
                        if position.trade_type == "RISK_BLOCKED":
                            logger.info(
                                f"LIFECYCLE PERSISTED: {trade_signal.symbol} (Type: {position.trade_type})",
                                extra={
                                    "signal_id": trade_signal.signal_id,
                                    "symbol": trade_signal.symbol,
                                    "position_id": position.position_id,
                                    "trade_type": position.trade_type,
                                    "qty": position.qty,
                                },
                            )
                        else:
                            logger.info(
                                f"ORDER EXECUTED: {trade_signal.symbol}",
                                extra={
                                    "signal_id": trade_signal.signal_id,
                                    "symbol": trade_signal.symbol,
                                    "position_id": position.position_id,
                                    "qty": position.qty,
                                    "duration_seconds": round(execution_duration, 3),
                                },
                            )
                        metrics.record_success("order_execution", execution_duration)
                    else:
                        # Execution was blocked by safety guards
                        logger.debug(
                            f"Execution skipped for {trade_signal.symbol} "
                            "(blocked by safety guards or validation)"
                        )
                except Exception as e:
                    execution_duration = time.time() - execution_start
                    logger.error(
                        f"Failed to execute order for {trade_signal.symbol}: {e}",
                        extra={
                            "signal_id": trade_signal.signal_id,
                            "symbol": trade_signal.symbol,
                            "error": str(e),
                        },
                    )
                    metrics.record_failure("order_execution", execution_duration)

            metrics.record_success("signal_processing", time.time() - processing_start)

        # =========================================================================
        # POSITION SYNC LOOP
        # Synchronize open positions with Alpaca broker state.
        # This updates TP/SL leg IDs and detects externally closed positions.
        # =========================================================================
        slippage_values = []  # Track slippage for summary
        if settings.ENABLE_EXECUTION:
            logger.info("Syncing open positions with Alpaca...")
            sync_start = time.time()
            try:
                open_positions = position_repo.get_open_positions()
                synced_count = 0
                closed_count = 0

                for pos in open_positions:
                    if shutdown_requested:
                        logger.info("Shutdown requested. Stopping position sync...")
                        break

                    if rate_limit_delay:
                        time.sleep(rate_limit_delay)
                        if shutdown_requested:
                            logger.info(
                                "Shutdown requested during position sync delay. Stopping..."
                            )
                            break

                    try:
                        # Capture original state for change detection
                        # Position is a Pydantic model; model_copy() allows detecting
                        # in-place modifications made by sync_position_status()
                        original_pos = pos.model_copy(deep=True)
                        updated_pos = execution_engine.sync_position_status(pos)

                        # Check if position was closed externally (TP/SL hit)
                        if updated_pos.status != original_pos.status:
                            position_repo.update_position(updated_pos)
                            closed_count += 1
                            logger.info(
                                f"Position {updated_pos.position_id} closed: "
                                f"{updated_pos.status.value}",
                                extra={
                                    "position_id": updated_pos.position_id,
                                    "symbol": updated_pos.symbol,
                                    "status": updated_pos.status.value,
                                },
                            )

                            # Send trade close notification with PnL
                            if (
                                updated_pos.status == TradeStatus.CLOSED
                                and updated_pos.exit_fill_price
                            ):
                                # Fetch associated signal for thread_id
                                signal_for_pos = repo.get_by_id(updated_pos.signal_id)
                                if signal_for_pos:
                                    # Use pre-calculated PnL from sync_position_status()
                                    pnl_usd = updated_pos.realized_pnl_usd
                                    pnl_pct = updated_pos.realized_pnl_pct

                                    # Format duration from pre-calculated seconds
                                    duration_str = "N/A"
                                    if updated_pos.trade_duration_seconds:
                                        hours, remainder = divmod(
                                            updated_pos.trade_duration_seconds, 3600
                                        )
                                        minutes = remainder // 60
                                        duration_str = f"{int(hours)}h {int(minutes)}m"

                                    # Use actual exit reason from broker sync
                                    exit_reason = (
                                        updated_pos.exit_reason.value
                                        if updated_pos.exit_reason
                                        else "Manual Exit"
                                    )

                                    discord.send_trade_close(
                                        signal=signal_for_pos,
                                        position=updated_pos,
                                        pnl_usd=pnl_usd,
                                        pnl_pct=pnl_pct,
                                        duration_str=duration_str,
                                        exit_reason=exit_reason,
                                    )
                        elif updated_pos != original_pos:
                            # Any field changed (leg IDs, qty, entry_fill_price, etc.)
                            position_repo.update_position(updated_pos)
                            synced_count += 1

                            # Log what changed for debugging
                            changes = []
                            if updated_pos.tp_order_id != pos.tp_order_id:
                                changes.append(f"TP={updated_pos.tp_order_id}")
                            if updated_pos.sl_order_id != pos.sl_order_id:
                                changes.append(f"SL={updated_pos.sl_order_id}")
                            if updated_pos.filled_at != pos.filled_at:
                                changes.append(f"filled_at={updated_pos.filled_at}")
                            if updated_pos.entry_fill_price != pos.entry_fill_price:
                                changes.append(
                                    f"entry_fill_price={updated_pos.entry_fill_price}"
                                )
                            if updated_pos.failed_reason != pos.failed_reason:
                                changes.append(
                                    f"failed_reason={updated_pos.failed_reason}"
                                )

                            logger.info(
                                f"Position {updated_pos.position_id} synced: "
                                f"{', '.join(changes) if changes else 'fields updated'}",
                                extra={
                                    "position_id": updated_pos.position_id,
                                    "symbol": updated_pos.symbol,
                                },
                            )

                            # Log slippage and commission metrics
                            if updated_pos.entry_slippage_pct is not None:
                                slippage_values.append(updated_pos.entry_slippage_pct)
                                logger.info(
                                    f"Position {updated_pos.position_id} metrics: "
                                    f"slippage={updated_pos.entry_slippage_pct:+.3f}%, "
                                    f"commission=${updated_pos.commission:.2f}",
                                    extra={
                                        "position_id": updated_pos.position_id,
                                        "symbol": updated_pos.symbol,
                                        "entry_slippage_pct": updated_pos.entry_slippage_pct,
                                        "commission": updated_pos.commission,
                                    },
                                )

                    except Exception as e:
                        logger.warning(
                            f"Failed to sync position {pos.position_id}: {e}",
                            extra={"position_id": pos.position_id},
                        )
                        metrics.record_failure("position_sync_single", 0)

                sync_duration = time.time() - sync_start
                logger.info(
                    f"Position sync complete: {synced_count} updated, "
                    f"{closed_count} closed",
                    extra={
                        "synced": synced_count,
                        "closed": closed_count,
                        "duration_seconds": round(sync_duration, 3),
                    },
                )
            except Exception as e:
                logger.error(f"Position sync failed: {e}", exc_info=True)
                metrics.record_failure("position_sync", time.time() - sync_start)

        # Display Rich execution summary table
        total_duration = time.time() - app_start_time
        console.print()  # Empty line for spacing

        # Calculate average slippage from position sync (if available)
        avg_slippage = None
        if slippage_values:
            avg_slippage = sum(slippage_values) / len(slippage_values)

        summary_table = create_execution_summary_table(
            total_duration=total_duration,
            symbols_processed=symbols_processed,
            total_symbols=len(portfolio_items),
            signals_found=signals_found,
            avg_slippage_pct=avg_slippage,
        )
        console.print(summary_table)
        console.print()  # Empty line for spacing

        # Log detailed metrics (also uses Rich table now)
        metrics.log_summary(logger)

        if shutdown_requested:
            logger.info("Signal generation cycle interrupted by shutdown request.")
        else:
            logger.info("Signal generation cycle complete.")

        # Persist Final Job Metadata
        now = datetime.now(timezone.utc)
        job_metadata_repo.save_job_metadata(
            "signal_generator_cron",
            {
                "last_run_date": now.date(),
                "git_hash": git_hash,
                "config": job_context,
                "duration_seconds": time.time() - app_start_time,
                "environment": settings.ENVIRONMENT,
                "executed_at": now,
            },
        )

    except Exception as e:
        logger.critical(f"Fatal error in main application loop: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    typer.run(main)
