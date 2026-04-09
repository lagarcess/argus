from datetime import datetime, timezone
from functools import lru_cache

import httpx
import pandas as pd
from argus.config import get_settings
from argus.market.data_provider import retry_with_backoff
from loguru import logger

# Timeframe mapping dictionary
TIME_MAP = {
    "15m": "15Min",
    "15Min": "15Min",
    "1h": "1Hour",
    "1Hour": "1Hour",
    "4h": "4Hour",
    "4Hour": "4Hour",
    "1d": "1Day",
    "1Day": "1Day",
}
ALLOWED_TIMEFRAMES = list(TIME_MAP.keys())


@lru_cache(maxsize=128)
@retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
def _validate_asset_cached(
    client: httpx.Client,
    edge_function_url: str,
    headers: tuple[tuple[str, str], ...],
    symbol: str,
) -> tuple[bool, str | None]:
    """Cached internal method for validation."""
    response = client.get(
        edge_function_url, params={"action": "assets"}, headers=dict(headers)
    )
    response.raise_for_status()

    assets = response.json()
    symbol_upper = symbol.upper()

    for asset in assets:
        if asset.get("symbol", "").upper() == symbol_upper:
            return True, asset.get("class")

    return False, None


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
        base_url = settings.SUPABASE_URL.rstrip("/")
        self.edge_function_url = f"{base_url}/functions/v1/alpaca-data-service"

        self.headers = {
            "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
        }

        # Use httpx Client for connection pooling and efficient HTTP requests
        self.client = httpx.Client(timeout=30.0)

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
        headers_tuple = tuple(self.headers.items())
        return _validate_asset_cached(
            self.client, self.edge_function_url, headers_tuple, symbol
        )

    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        """
        Fetches historical OHLCV data for an asset.

        Args:
            symbol: The asset symbol
            timeframe: The timeframe for the bars (e.g., '1Day' or '1d')
            start: The start datetime (will be converted to ISO format)
            end: The end datetime (optional)

        Returns:
            Pandas DataFrame with UTC DateTimeIndex and columns ['open', 'high', 'low', 'close', 'volume', 'vwap']

        Raises:
            ValueError: If the asset is invalid or timeframe is not supported
        """
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(
                f"Timeframe '{timeframe}' is not supported. Allowed: {ALLOWED_TIMEFRAMES}"
            )

        mapped_timeframe = TIME_MAP[timeframe]

        is_valid, asset_class = self.validate_asset(symbol)
        if not is_valid or not asset_class:
            raise ValueError(f"Asset '{symbol}' is not valid or active.")

        logger.info(
            f"Fetching bars for {symbol} ({asset_class}) on {mapped_timeframe} from {start}"
        )

        start_str = start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        params = {
            "action": "bars",
            "symbol": symbol,
            "timeframe": mapped_timeframe,
            "start": start_str,
            "asset_class": asset_class,
        }

        if end:
            end_str = end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            params["end"] = end_str

        response = self.client.get(
            self.edge_function_url, params=params, headers=self.headers
        )
        response.raise_for_status()

        data = response.json()

        bars = data.get("bars", {})
        if not bars:
            logger.warning(f"No bars returned for {symbol}")
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume", "vwap"]
            )

        symbol_bars = bars.get(symbol, [])
        if not symbol_bars:
            if "crypto" in asset_class:
                values = list(bars.values())
                if values:
                    symbol_bars = values[0]

        if not symbol_bars:
            logger.warning(f"No bars found for specific symbol {symbol} in response")
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume", "vwap"]
            )

        df = pd.DataFrame(symbol_bars)

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

        required_cols = ["timestamp", "open", "high", "low", "close", "volume", "vwap"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in API response: {missing_cols}")

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")

        df = df[["open", "high", "low", "close", "volume", "vwap"]]
        df = df.astype(float)

        return df
