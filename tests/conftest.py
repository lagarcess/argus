"""Global pytest fixtures and environment overrides.

This file establishes the baseline test environment, ensuring that NO real
network calls or authentications are performed during the test suite, while
avoiding non-thread-safe global MagicMocks that conflict with concurrent executors.
"""

import os
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

# CRUCIAL: Set env vars at the module level so they are loaded BEFORE any
# test modules or Google Cloud libraries are imported. This prevents
# DefaultCredentialsError during test discovery and initialization.
os.environ["ALPACA_API_KEY"] = "test_alpaca_key"
os.environ["ALPACA_API_SECRET"] = "test_alpaca_secret"
os.environ["ALPACA_PAPER_TRADING"] = "True"
os.environ["DISCORD_WEBHOOK"] = "https://discord.com/api/webhooks/test"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project-id"

# Setting the emulator host cleanly bypasses Google Application
# Default Credentials (ADC) without requiring a `MagicMock` globally.
# This prevents `DefaultCredentialsError` in CI environments and avoids
# ThreadPoolExecutor dictionary iteration crashes.
os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"


@pytest.fixture(autouse=True)
def mock_env_vars():
    """
    Keep the fixture to ensure variables remain reset for every test,
    in case a specific test modifies os.environ and doesn't clean up.
    """
    os.environ["ALPACA_API_KEY"] = "test_alpaca_key"
    os.environ["ALPACA_API_SECRET"] = "test_alpaca_secret"
    os.environ["ALPACA_PAPER_TRADING"] = "True"
    os.environ["DISCORD_WEBHOOK"] = "https://discord.com/api/webhooks/test"
    os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project-id"
    os.environ["FIRESTORE_EMULATOR_HOST"] = "127.0.0.1:8080"


@pytest.fixture
def mock_main_dependencies():
    with ExitStack() as stack:
        stock_client = stack.enter_context(
            patch("crypto_signals.main.get_stock_data_client")
        )
        crypto_client = stack.enter_context(
            patch("crypto_signals.main.get_crypto_data_client")
        )
        trading_client = stack.enter_context(
            patch("crypto_signals.main.get_trading_client")
        )
        market_provider = stack.enter_context(
            patch("crypto_signals.main.MarketDataProvider")
        )
        generator = stack.enter_context(patch("crypto_signals.main.SignalGenerator"))
        repo = stack.enter_context(patch("crypto_signals.main.SignalRepository"))
        discord = stack.enter_context(patch("crypto_signals.main.DiscordClient"))
        asset_validator = stack.enter_context(
            patch("crypto_signals.main.AssetValidationService")
        )
        mock_settings = stack.enter_context(patch("crypto_signals.main.get_settings"))
        mock_secrets = stack.enter_context(
            patch("crypto_signals.main.init_secrets", return_value=True)
        )
        mock_firestore_config = stack.enter_context(
            patch("crypto_signals.main.load_config_from_firestore")
        )
        position_repo = stack.enter_context(
            patch("crypto_signals.main.PositionRepository")
        )
        execution_engine = stack.enter_context(
            patch("crypto_signals.main.ExecutionEngine")
        )
        job_lock = stack.enter_context(patch("crypto_signals.main.JobLockRepository"))
        rejected_repo = stack.enter_context(
            patch("crypto_signals.main.RejectedSignalRepository")
        )
        trade_archival = stack.enter_context(
            patch("crypto_signals.main.TradeArchivalPipeline")
        )
        fee_patch = stack.enter_context(patch("crypto_signals.main.FeePatchPipeline"))
        price_patch = stack.enter_context(patch("crypto_signals.main.PricePatchPipeline"))
        reconciler = stack.enter_context(patch("crypto_signals.main.StateReconciler"))
        job_metadata_repo = stack.enter_context(
            patch("crypto_signals.main.JobMetadataRepository")
        )
        strategy_repo = stack.enter_context(
            patch("crypto_signals.main.StrategyRepository")
        )
        rejected_archival = stack.enter_context(
            patch("crypto_signals.main.RejectedSignalArchival")
        )
        expired_archival = stack.enter_context(
            patch("crypto_signals.main.ExpiredSignalArchivalPipeline")
        )
        account_snapshot = stack.enter_context(
            patch("crypto_signals.main.AccountSnapshotPipeline")
        )
        strategy_sync = stack.enter_context(
            patch("crypto_signals.main.StrategySyncPipeline")
        )
        backtest_archival = stack.enter_context(
            patch("crypto_signals.main.BacktestArchivalPipeline")
        )

        job_metadata_repo.return_value.get_last_run_date.return_value = None
        mock_settings.return_value.CRYPTO_SYMBOLS = ["BTC/USD", "ETH/USD", "XRP/USD"]
        mock_settings.return_value.EQUITY_SYMBOLS = []
        mock_settings.return_value.RATE_LIMIT_DELAY = 0.0
        mock_settings.return_value.ENABLE_GCP_LOGGING = False
        mock_settings.return_value.ENABLE_EXECUTION = False
        mock_settings.return_value.SIGNAL_SATURATION_THRESHOLD_PCT = 0.5
        mock_settings.return_value.MAX_WORKERS = 3
        mock_settings.return_value.DISCORD_BOT_TOKEN = "test_token"
        mock_settings.return_value.DISCORD_CHANNEL_ID_CRYPTO = "123"
        mock_settings.return_value.DISCORD_CHANNEL_ID_STOCK = "456"

        mock_firestore_config.return_value = {}

        def get_daily_bars_side_effect(*args, **kwargs):
            m = MagicMock()
            m.empty = False
            return m

        market_provider.return_value.get_daily_bars.side_effect = (
            get_daily_bars_side_effect
        )
        asset_validator.return_value.get_valid_portfolio.side_effect = (
            lambda symbols, asset_class: list(symbols)
        )
        job_lock.return_value.acquire_lock.return_value = True
        discord.return_value.find_thread_by_signal_id.return_value = None

        trade_archival.return_value.run.return_value = 0
        fee_patch.return_value.run.return_value = 0
        price_patch.return_value.run.return_value = 0
        rejected_archival.return_value.run.return_value = 0
        expired_archival.return_value.run.return_value = 0
        account_snapshot.return_value.run.return_value = 0
        strategy_sync.return_value.run.return_value = 0
        backtest_archival.return_value.run.return_value = 0

        yield {
            "stock_client": stock_client,
            "crypto_client": crypto_client,
            "trading_client": trading_client,
            "market_provider": market_provider,
            "generator": generator,
            "repo": repo,
            "discord": discord,
            "asset_validator": asset_validator,
            "settings": mock_settings,
            "secrets": mock_secrets,
            "firestore_config": mock_firestore_config,
            "position_repo": position_repo,
            "execution_engine": execution_engine,
            "job_lock": job_lock,
            "rejected_repo": rejected_repo,
            "trade_archival": trade_archival,
            "fee_patch": fee_patch,
            "price_patch": price_patch,
            "reconciler": reconciler,
            "rejected_archival": rejected_archival,
            "expired_archival": expired_archival,
            "account_snapshot": account_snapshot,
            "strategy_sync": strategy_sync,
            "strategy_repo": strategy_repo,
            "backtest_archival": backtest_archival,
        }
