"""
Unified Configuration Module for Argus.

This module provides a single source of truth for all configuration settings using
pydantic-settings for validation and environment variable loading.
"""

from functools import lru_cache
from typing import Any

from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from pydantic import Field, field_validator
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

    # Alpaca API Credentials (Required for market data)
    ALPACA_API_KEY: str | None = Field(default=None)
    ALPACA_SECRET_KEY: str | None = Field(default=None)

    # Use paper trading for safety (affects data endpoints)
    ALPACA_PAPER_TRADING: bool = Field(
        default=True,
        description="Use Alpaca paper trading environment",
    )

    # Portfolio Configuration
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

    # Market Data Caching
    ENABLE_MARKET_DATA_CACHE: bool = Field(
        default=False,
        description="Enable disk caching for market data. Useful for backtesting/dev.",
    )

    # Supabase Configuration
    SUPABASE_URL: str | None = Field(default=None)
    SUPABASE_SERVICE_ROLE_KEY: str | None = Field(default=None)
    SUPABASE_JWT_SECRET: str | None = Field(default=None)

    # Rate Limiting Configuration
    RATE_LIMIT_DELAY: float = Field(
        default=0.5,
        description=(
            "Delay in seconds between processing symbols "
            "(Alpaca limit: 200 req/min = 0.3s/req minimum)"
        ),
        ge=0.0,
        le=10.0,
    )

    @field_validator("CRYPTO_SYMBOLS", "EQUITY_SYMBOLS", mode="before")
    @classmethod
    def parse_list_from_str(cls, v: Any) -> Any:
        """Parse comma-separated string into list."""
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings.
    Uses lru_cache to ensure singleton behavior (settings are loaded once).

    Returns:
        Settings: Validated application settings

    Raises:
        pydantic.ValidationError: If required environment variables are missing
    """
    return Settings()


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
