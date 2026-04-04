"""
Validate Alpaca API credentials and connection.

Usage:
    poetry run python -m argus.market.validate

Returns exit code 0 on success, 1 on failure.
"""

from loguru import logger


def validate_credentials() -> bool:
    """Check that Alpaca credentials are valid."""
    try:
        from argus.config import get_settings

        settings = get_settings()

        if not settings.ALPACA_API_KEY:
            logger.error("ALPACA_API_KEY is not set")
            return False
        if not settings.ALPACA_SECRET_KEY:
            logger.error("ALPACA_SECRET_KEY is not set")
            return False

        logger.info(
            "Credentials loaded",
            key_prefix=settings.ALPACA_API_KEY[:8] + "...",
        )

        # Attempt a lightweight API call
        from argus.config import get_stock_data_client

        client = get_stock_data_client()

        # Fetch 1 bar for SPY as a connectivity test
        from datetime import datetime, timedelta

        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        request = StockBarsRequest(
            symbol_or_symbols=["SPY"],
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=5),
            limit=1,
        )
        bars = client.get_stock_bars(request)

        if bars and bars.data:
            logger.info(
                "API connection valid",
                test_symbol="SPY",
                bars_returned=len(bars.data.get("SPY", [])),
            )
            return True
        else:
            logger.warning("API returned empty data")
            return False

    except Exception as e:
        logger.error(f"Credential validation failed: {e}")
        return False


if __name__ == "__main__":
    import sys

    success = validate_credentials()
    if success:
        print("✅ Alpaca credentials valid.")
    else:
        print("❌ Alpaca credential check failed.")
        sys.exit(1)
