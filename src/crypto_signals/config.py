"""
Unified Configuration Module for Crypto Sentinel.

This module provides a single source of truth for all configuration settings using
pydantic-settings for validation and environment variable loading.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.trading.client import TradingClient
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All required credentials are strictly validated on initialization. Missing or empty
    values will raise a ValidationError.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Alpaca API Credentials (Required)
    ALPACA_API_KEY: str | None = Field(default=None)
    ALPACA_SECRET_KEY: str | None = Field(default=None)

    # Google Cloud Configuration (Required)
    GOOGLE_CLOUD_PROJECT: str | None = Field(default=None)

    # Google Cloud Credentials Path (Optional - for service account auth)
    GOOGLE_APPLICATION_CREDENTIALS: str | None = Field(
        default=None,
        description="Path to Google Cloud service account JSON file",
    )

    # Discord Webhooks (Multi-destination routing)
    TEST_DISCORD_WEBHOOK: SecretStr | None = Field(default=None)
    LIVE_CRYPTO_DISCORD_WEBHOOK_URL: SecretStr | None = Field(
        default=None,
        description="Discord Webhook URL for live CRYPTO signals (required when TEST_MODE=False)",
    )
    LIVE_STOCK_DISCORD_WEBHOOK_URL: SecretStr | None = Field(
        default=None,
        description="Discord Webhook URL for live EQUITY signals (required when TEST_MODE=False)",
    )

    # Discord Bot Configuration (for Thread Recovery / Reading)
    DISCORD_BOT_TOKEN: SecretStr | None = Field(
        default=None,
        description="Discord Bot Token for reading threads (optional, enabling recovery)",
    )
    DISCORD_CHANNEL_ID_CRYPTO: str | None = Field(
        default=None,
        description="Channel ID for Crypto signals (required for recovery)",
    )
    DISCORD_CHANNEL_ID_STOCK: str | None = Field(
        default=None,
        description="Channel ID for Stock signals (required for recovery)",
    )
    DISCORD_SHADOW_WEBHOOK_URL: SecretStr | None = Field(
        default=None,
        description="Discord Webhook URL for shadow (rejected) signals",
    )
    DISCORD_DEPLOYS: SecretStr | None = Field(
        default=None,
        description="Discord Webhook URL for CI/CD deployment notifications (used in GitHub Actions)",
    )

    DISCORD_USE_FORUMS: bool = Field(
        default=False,
        description="If True, enables Forum Channel specific logic (e.g. thread_name)",
    )

    DISCORD_SHADOW_USE_FORUMS: bool = Field(
        default=False,
        description="If True, enables Forum Channel specific logic for shadow (rejected) signals.",
    )

    # Environment Mode (defaults to True for safety - all traffic goes to test webhook)
    TEST_MODE: bool = Field(
        default=True,
        description="If True, all traffic routes to TEST_DISCORD_WEBHOOK",
    )

    ALPACA_PAPER_TRADING: bool = Field(
        default=True,
        description="Use Alpaca paper trading environment",
    )

    # Google Cloud Logging (for production environments)
    # Defaults to True in PROD, False in DEV (handled by validator)
    ENABLE_GCP_LOGGING: bool | None = Field(
        default=None,
        description="Enable Google Cloud Logging. Defaults to True if ENVIRONMENT=PROD.",
    )

    # Environment Mode (PROD or DEV)
    ENVIRONMENT: str = Field(
        default="DEV",
        description="Execution Environment (PROD or DEV). Controls DB routing and TTL.",
        pattern="^(PROD|DEV)$",
    )

    # Application Mode
    APP_MODE: str = Field(
        default="NORMAL",
        description="Application mode (NORMAL or SMOKE_TEST). Controls credential validation.",
        pattern="^(NORMAL|SMOKE_TEST)$",
    )

    # TTL Configuration (Days)
    TTL_DAYS_PROD: int = Field(
        default=30, description="TTL for Production signals (days)."
    )
    TTL_DAYS_DEV: int = Field(default=7, description="TTL for Dev signals (days).")
    TTL_DAYS_POSITION: int = Field(default=90, description="TTL for Positions (days).")

    # Portfolio Configuration (Optional - defaults to hardcoded lists)
    CRYPTO_SYMBOLS: Any = Field(
        default=[
            "BTC/USD",
            "ETH/USD",
            "XRP/USD",
        ],
        description="List of crypto pairs to analyze",
    )
    EQUITY_SYMBOLS: Any = Field(
        default=[],
        description="List of equity symbols to analyze",
    )

    # Rate Limiting Configuration (Optional)
    RATE_LIMIT_DELAY: float = Field(
        default=0.5,
        description=(
            "Delay in seconds between processing symbols "
            "(Alpaca limit: 200 req/min = 0.3s/req minimum)"
        ),
        ge=0.0,
        le=10.0,
    )

    MAX_WORKERS: int = Field(
        default=3,
        description="Maximum number of parallel worker threads for asset processing.",
        ge=1,
        le=20,
    )

    # Execution Engine
    ENABLE_EXECUTION: bool = Field(
        default=False,
        description="Enable order execution (requires ALPACA_PAPER_TRADING=True)",
    )
    RISK_PER_TRADE: float = Field(
        default=100.0,
        description=(
            "Fixed dollar amount to risk per trade. Position size is calculated as "
            "RISK_PER_TRADE / (entry_price - stop_loss), ensuring you lose exactly "
            "this amount if the stop is hit."
        ),
        ge=10.0,
        le=10000.0,
    )
    MIN_ORDER_NOTIONAL_USD: float = Field(
        default=15.0,
        description="Minimum order value in USD to meet broker requirements.",
        ge=1.0,
    )

    # === Risk Management (Issue #114) ===
    MAX_CRYPTO_POSITIONS: int = Field(
        default=5,
        description="Maximum concurrent open positions for Crypto asset class.",
    )
    MAX_EQUITY_POSITIONS: int = Field(
        default=5,
        description="Maximum concurrent open positions for Equity asset class.",
    )
    MAX_CRYPTO_POSITION_QTY: float = Field(
        default=1_000_000.0,
        description="Maximum share quantity for a single crypto order (micro-cap safeguard).",
        ge=1.0,
    )
    MAX_EQUITY_POSITION_QTY: float = Field(
        default=10_000.0,
        description="Maximum share quantity for a single equity order (micro-cap safeguard).",
        ge=1.0,
    )
    MAX_DAILY_DRAWDOWN_PCT: float = Field(
        default=0.02,
        description="Maximum daily drawdown (2% default). Halts execution if reached.",
    )
    MIN_ASSET_BP_USD: float = Field(
        default=100.0,
        description="Minimum buying power required to perform a trade.",
    )

    ENABLE_EQUITIES: bool = Field(
        default=False,
        description=(
            "Enable equity (stock) trading. Requires Alpaca paid plan with SIP data "
            "access. Set to True only if you have SIP data subscription."
        ),
    )

    # Market Data Caching
    ENABLE_MARKET_DATA_CACHE: bool = Field(
        default=False,
        description="Enable disk caching for market data. Useful for backtesting/dev.",
    )

    CLEANUP_ON_FAILURE: bool = Field(
        default=True,
        description="Auto-delete documents from Firestore if they fail Pydantic validation",
    )

    # === Schema Guardian Configuration ===
    SCHEMA_GUARDIAN_STRICT_MODE: bool = Field(
        default=True,
        description="If True, raise error on schema mismatch. If False, log warning only.",
    )
    SCHEMA_MIGRATION_AUTO: bool = Field(
        default=True,
        description="Automatically add missing columns to BigQuery tables.",
    )

    USE_LEGACY_ARCHIVAL: bool = Field(
        default=True,
        description="Enable older archival pipelines alongside unified backtest archival.",
    )

    # === Saturation Filtering (Issue #290) ===
    SIGNAL_SATURATION_THRESHOLD_PCT: float = Field(
        default=0.5,
        description="Percentage of portfolio triggering same pattern to flag saturation.",
        ge=0.1,
        le=1.0,
    )

    # === Performance Metrics Configuration ===
    PERFORMANCE_BASELINE_CAPITAL: float = Field(
        default=100000.0,
        description="Baseline capital for strategy performance percentage calculations.",
        ge=1000.0,
    )

    # === Cooldown Configuration (Issue #117 Strategic Feedback) ===
    COOLDOWN_SCOPE: str = Field(
        default="SYMBOL",
        description=(
            "Cooldown scope: 'SYMBOL' blocks all patterns after exit (conservative), "
            "'PATTERN' blocks only the same pattern (flexible). "
            "Set to 'PATTERN' to allow different high-probability patterns to trade "
            "even if recent exit on same symbol but different pattern."
        ),
        pattern="^(SYMBOL|PATTERN)$",
    )

    @field_validator("CRYPTO_SYMBOLS", "EQUITY_SYMBOLS", mode="before")
    @classmethod
    def parse_list_from_str(cls, v: Any) -> Any:
        """Parse comma-separated string into list."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator(
        "GOOGLE_CLOUD_PROJECT",
        mode="before",
    )
    @classmethod
    def validate_gcp_project_not_empty(cls, v: str, info) -> str:
        """Ensure GOOGLE_CLOUD_PROJECT is not an empty string."""
        if v is None or (isinstance(v, str) and v.strip() == ""):
            raise ValueError(f"{info.field_name} cannot be empty")
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def validate_conditional_requirements(self) -> "Settings":
        """Validate fields that are required only under certain conditions."""

        # Default Enable GCP Logging to True in PROD if not specified
        if self.ENABLE_GCP_LOGGING is None:
            self.ENABLE_GCP_LOGGING = self.ENVIRONMENT == "PROD"

        if not self.TEST_MODE:
            if not self.LIVE_CRYPTO_DISCORD_WEBHOOK_URL:
                raise ValueError(
                    "LIVE_CRYPTO_DISCORD_WEBHOOK_URL is required when TEST_MODE=False"
                )
            if not self.LIVE_STOCK_DISCORD_WEBHOOK_URL:
                raise ValueError(
                    "LIVE_STOCK_DISCORD_WEBHOOK_URL is required when TEST_MODE=False"
                )
        if self.ENABLE_EXECUTION:
            if not self.ALPACA_API_KEY:
                raise ValueError("ALPACA_API_KEY is required when ENABLE_EXECUTION=True")
            if not self.ALPACA_SECRET_KEY:
                raise ValueError(
                    "ALPACA_SECRET_KEY is required when ENABLE_EXECUTION=True"
                )
        return self

    @property
    def project_root(self) -> Path:
        """Return the project root directory."""
        return Path(__file__).parent.parent.parent

    @property
    def is_paper_trading(self) -> bool:
        """Check if running in paper trading mode."""
        return self.ALPACA_PAPER_TRADING


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings.
    Uses lru_cache to ensure singleton behavior (settings are loaded once).
    Also bridges Pydantic settings to os.environ for Google Cloud SDKs.

    Returns:
        Settings: Validated application settings

    Raises:
        pydantic.ValidationError: If required environment variables are missing
    """
    settings = Settings()

    # BRIDGE: Force the Pydantic setting into the OS Environment for Google SDKs
    # Google Cloud libraries rely on os.environ, not Pydantic settings
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
            settings.GOOGLE_APPLICATION_CREDENTIALS
        )

    # Equities disabled by configuration (Basic Alpaca Plans can't access SIP data)
    # Users with paid plans can set ENABLE_EQUITIES=true to enable stock trading
    if not settings.ENABLE_EQUITIES:
        settings.EQUITY_SYMBOLS = []

    return settings


# Convenience singleton for quick access


def get_trading_client() -> TradingClient:
    """
    Get an authenticated Alpaca TradingClient.

    Returns:
        TradingClient: Authenticated client
    """
    settings = get_settings()
    return TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.is_paper_trading,
    )


def get_stock_data_client() -> StockHistoricalDataClient:
    """
    Get an authenticated Alpaca StockHistoricalDataClient.

    Returns:
        StockHistoricalDataClient: Authenticated client
    """
    settings = get_settings()
    return StockHistoricalDataClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
    )


def get_crypto_data_client() -> CryptoHistoricalDataClient:
    """
    Get an authenticated Alpaca CryptoHistoricalDataClient.

    Returns:
        CryptoHistoricalDataClient: Authenticated client
    """
    settings = get_settings()
    return CryptoHistoricalDataClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
    )


if __name__ == "__main__":
    # Debug output when run directly
    cfg = get_settings()
    print(f"GCP Project: {cfg.GOOGLE_CLOUD_PROJECT}")


def load_config_from_firestore() -> dict[str, list[str]]:
    """
    Load active strategy configuration from Firestore.

    Queries the 'dim_strategies' collection for strategies marked active=True.
    Extracts assets and asset classes to build dynamic portfolio lists.

    Returns:
        dict: Configuration dict containing 'CRYPTO_SYMBOLS' and 'EQUITY_SYMBOLS' lists.
              Empty dict if no active strategies found or error occurs.
    """
    from google.cloud import firestore
    from google.cloud.firestore import FieldFilter
    from loguru import logger

    try:
        settings = get_settings()
        # Ensure we have a project ID
        if not settings.GOOGLE_CLOUD_PROJECT:
            logger.warning("No Google Cloud Project ID set. Skipping Firestore config.")
            return {}

        db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        collection_ref = db.collection("dim_strategies")

        # Query for active strategies
        query = collection_ref.where(filter=FieldFilter("active", "==", True))

        crypto_symbols = set()
        equity_symbols = set()

        logger.info("Querying Firestore for active strategies...")

        docs = list(query.stream())
        if not docs:
            logger.info("No active strategies found in Firestore.")
            return {}

        for doc in docs:
            data = doc.to_dict()
            assets = data.get("assets", [])
            asset_class = data.get("asset_class")

            if not assets:
                continue

            # Standardize asset class string check
            if asset_class == "CRYPTO":
                crypto_symbols.update(assets)
            elif asset_class == "EQUITY":
                equity_symbols.update(assets)
            else:
                logger.warning(
                    f"Unknown asset class '{asset_class}' in strategy {doc.id}"
                )

        result = {
            "CRYPTO_SYMBOLS": list(crypto_symbols),
            "EQUITY_SYMBOLS": list(equity_symbols),
        }

        logger.info(
            f"Loaded config from Firestore: "
            f"{len(crypto_symbols)} Crypto, {len(equity_symbols)} Equity"
        )
        return result

    except Exception as e:
        logger.error(
            "Failed to load configuration from Firestore.",
            extra={"error": str(e)},
        )
        # Return empty to trigger fallback or empty state
        return {}
