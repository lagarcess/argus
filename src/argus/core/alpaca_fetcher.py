from datetime import datetime, timezone
from typing import Literal

import httpx
import pandas as pd
from argus.config import get_settings
from argus.market.data_provider import retry_with_backoff
from loguru import logger

# Allowed timeframes from system guidelines
ALLOWED_TIMEFRAMES = ["15Min", "1Hour", "4Hour", "1Day"]


class AlpacaDataFetcher:
    """
    Client for fetching market data via the Supabase Edge Function proxy.
    This utilizes the Supabase Global CDN for caching responses.
    """

    def __init__(self):
        settings = get_settings()
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in environment.")

        # Construct the Edge Function URL based on SUPABASE_URL
        # Remove trailing slash if present, then append the function path
        base_url = settings.SUPABASE_URL.rstrip("/")
        self.edge_function_url = f"{base_url}/functions/v1/alpaca-data-service"

        self.headers = {
            "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
        }

        # Use httpx Client for connection pooling and efficient HTTP requests
        self.client = httpx.Client(timeout=30.0)

    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def validate_asset(self, symbol: str) -> tuple[bool, str | None]:
        """
        Validates if an asset is active and returns its asset class.

        Args:
            symbol: The asset symbol (e.g., 'AAPL', 'BTC/USD')

        Returns:
            Tuple containing:
            - bool: True if the asset is valid and active
            - str | None: The asset class ('us_equity' or 'crypto'), or None if invalid
        """
        response = self.client.get(
            self.edge_function_url, params={"action": "assets"}, headers=self.headers
        )
        response.raise_for_status()

        assets = response.json()

        # Look for the specific symbol in the cached list of assets
        # Case insensitive match
        symbol_upper = symbol.upper()

        for asset in assets:
            if asset.get("symbol", "").upper() == symbol_upper:
                return True, asset.get("class")

        # If the symbol is like BTC/USD but we couldn't find it, try matching without the slash for crypto
        # Alpaca crypto sometimes drops the slash or requires 'USD' postfix
        if "/" in symbol_upper:
            # Fallback for crypto formats like BTCUSD
            stripped_symbol = symbol_upper.replace("/", "")
            for asset in assets:
                if asset.get("symbol", "").upper() == stripped_symbol:
                    return True, "crypto"

        return False, None

    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def fetch_bars(
        self,
        symbol: str,
        timeframe: Literal["15Min", "1Hour", "4Hour", "1Day"],
        start: datetime,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Fetches historical OHLCV data for an asset.

        Args:
            symbol: The asset symbol
            timeframe: The timeframe for the bars (e.g., '1Day')
            start: The start datetime (will be converted to ISO format)
            end: The end datetime (optional)

        Returns:
            Pandas DataFrame with UTC DateTimeIndex and columns ['open', 'high', 'low', 'close', 'volume']

        Raises:
            ValueError: If the asset is invalid or timeframe is not supported
        """
        # 1. Validate timeframe
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(
                f"Timeframe '{timeframe}' is not supported. Allowed: {ALLOWED_TIMEFRAMES}"
            )

        # 2. Validate asset and get asset_class
        is_valid, asset_class = self.validate_asset(symbol)
        if not is_valid or not asset_class:
            raise ValueError(f"Asset '{symbol}' is not valid or active.")

        logger.info(
            f"Fetching bars for {symbol} ({asset_class}) on {timeframe} from {start}"
        )

        # 3. Format parameters for Edge Function
        # Edge function expects ISO 8601 strings (e.g., "2023-01-01T00:00:00Z")
        start_str = start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        params = {
            "action": "bars",
            "symbol": symbol,
            "timeframe": timeframe,
            "start": start_str,
            "asset_class": asset_class,
        }

        if end:
            end_str = end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            params["end"] = end_str

        # 4. Fetch data from proxy
        response = self.client.get(
            self.edge_function_url, params=params, headers=self.headers
        )
        response.raise_for_status()

        data = response.json()

        # 5. Extract bars from Alpaca response format
        bars = data.get("bars", {})
        if not bars:
            logger.warning(f"No bars returned for {symbol}")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # Bars might be under the symbol key directly or nested
        symbol_bars = bars.get(symbol, [])
        if not symbol_bars:
            # For crypto it might use a different symbol format in the response
            if "crypto" in asset_class:
                # Try finding the first value in the dict
                values = list(bars.values())
                if values:
                    symbol_bars = values[0]

        if not symbol_bars:
            logger.warning(f"No bars found for specific symbol {symbol} in response")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # 6. Build the DataFrame
        # Alpaca format: 't': timestamp, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume
        df = pd.DataFrame(symbol_bars)

        # Rename columns to standard lower case
        column_mapping = {
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "n": "trade_count",
            "vw": "vwap",
        }
        df = df.rename(
            columns={k: v for k, v in column_mapping.items() if k in df.columns}
        )

        # Ensure we have the required columns
        required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in API response: {missing_cols}")

        # Process timestamp to UTC DatetimeIndex
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")

        # Filter to just the requested columns to keep it clean
        df = df[["open", "high", "low", "close", "volume"]]

        # Convert types to float
        df = df.astype(float)

        return df
