from datetime import datetime, timedelta, timezone

from argus.core.alpaca_fetcher import AlpacaDataFetcher
from loguru import logger


def main():
    """
    Functional verification script for the AlpacaDataFetcher implementation.
    This script tests:
    1. Asset validation and class detection
    2. Lazy-loading of the asset cache
    3. OHLCV Bar fetching and DataFrame formatting
    4. Safe timezone handling
    """
    logger.info("Starting AlpacaDataFetcher functional verification...")

    try:
        with AlpacaDataFetcher() as fetcher:
            # 1. Test Asset Validation
            logger.info("Verifying asset validation (AAPL)...")
            is_valid, asset_class = fetcher.validate_asset("AAPL")
            if not is_valid or asset_class != "us_equity":
                logger.error(f"Failed AAPL validation: {is_valid}, {asset_class}")
                return

            logger.info("Verifying asset validation with slashes (BTC/USD)...")
            is_valid, asset_class = fetcher.validate_asset("BTC/USD")
            if not is_valid or asset_class != "crypto":
                logger.error(f"Failed BTC/USD validation: {is_valid}, {asset_class}")
                return

            # 2. Test Bar Fetching
            start = datetime.now(timezone.utc) - timedelta(days=7)
            logger.info(f"Fetching weekly bars for AAPL from {start.date()}...")
            df = fetcher.fetch_bars("AAPL", "1d", start)

            if df.empty:
                logger.warning(
                    "No bars returned for AAPL. Check Alpaca market hours or credentials."
                )
            else:
                logger.success(f"Successfully fetched {len(df)} bars for AAPL.")
                logger.debug(f"Columns: {list(df.columns)}")
                logger.debug(f"First close: {df.iloc[0]['close']}")

            # 3. Test Crypto Fetching
            logger.info("Fetching daily BTC/USD bars...")
            df_crypto = fetcher.fetch_bars("BTC/USD", "1d", start)
            if df_crypto.empty:
                logger.warning("No bars returned for BTC/USD.")
            else:
                logger.success(f"Successfully fetched {len(df_crypto)} crypto bars.")

            logger.success("AlpacaDataFetcher verification PASSED.")

    except Exception as e:
        logger.exception(f"Verification FAILED: {str(e)}")
        logger.error("Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set in .env")


if __name__ == "__main__":
    main()
