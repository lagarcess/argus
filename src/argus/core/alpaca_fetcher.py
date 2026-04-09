from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

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


class AlpacaDataFetcher:
    """
    Client for fetching market data via the Supabase Edge Function proxy.
    This utilizes the Supabase Global CDN and local lazy-loading for caching.
    """

    def __init__(self):
        settings = get_settings()
        self.enabled = True

        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            logger.warning(
                "Supabase credentials missing. AlpacaDataFetcher will be disabled."
            )
            self.enabled = False
            self.edge_function_url = ""
            self.headers = {}
        else:
            # Construct the Edge Function URL based on SUPABASE_URL
            base_url = settings.SUPABASE_URL.rstrip("/")
            self.edge_function_url = f"{base_url}/functions/v1/alpaca-data-service"

            self.headers = {
                "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
                "Content-Type": "application/json",
            }

        # Shared client for connection pooling
        self.client = httpx.Client(timeout=30.0)
        self._assets_map: dict[str, str] | None = None

    def __enter__(self) -> "AlpacaDataFetcher":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Explicitly close the HTTP client to prevent connection leaks."""
        self.client.close()

    @retry_with_backoff(max_retries=3)
    def _load_assets(self) -> None:
        """
        Lazy-loads the active asset list from Alpaca.
        This is a heavy operation (~1MB fetch) cached locally once per instance.
        """
        if not self.enabled:
            raise ValueError("AlpacaDataFetcher is disabled (missing credentials).")
        if self._assets_map is not None:
            return

        logger.info("Initializing regional Alpaca asset cache...")
        response = self.client.get(
            self.edge_function_url, params={"action": "assets"}, headers=self.headers
        )
        response.raise_for_status()

        assets = response.json()
        # Map symbol -> asset_class for O(1) lookup
        self._assets_map = {
            asset["symbol"].upper(): asset["class"]
            for asset in assets
            if "symbol" in asset and "class" in asset
        }
        logger.debug(f"Cached {len(self._assets_map)} active assets.")

    @lru_cache(maxsize=128)  # noqa: B019
    def validate_asset(self, symbol: str) -> tuple[bool, str | None]:
        """
        Validates if an asset is active using the local cache.

        Args:
            symbol: The asset symbol (e.g., 'AAPL', 'BTC/USD')

        Returns:
            Tuple containing:
            - bool: True if the asset is valid and active
            - str | None: The asset class ('us_equity' or 'crypto'), or None if invalid
        """
        self._load_assets()
        assert self._assets_map is not None

        symbol_upper = symbol.upper()
        asset_class = self._assets_map.get(symbol_upper)

        if asset_class:
            return True, asset_class

        # Fallback for crypto common formats (e.g., BTC/USD -> BTCUSD)
        if "/" in symbol_upper:
            stripped = symbol_upper.replace("/", "")
            asset_class = self._assets_map.get(stripped)
            if asset_class:
                return True, asset_class

        return False, None

    def get_active_assets(self) -> list[str]:
        """Returns a list of all active asset symbols from the local cache."""
        self._load_assets()
        assert self._assets_map is not None
        return list(self._assets_map.keys())

    @retry_with_backoff(max_retries=3)
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
            start: The start datetime (UTC)
            end: The end datetime (optional, UTC)

        Returns:
            Pandas DataFrame with UTC DateTimeIndex and standard OHLCV columns
        """
        if not self.enabled:
            raise ValueError("AlpacaDataFetcher is disabled (missing credentials).")
        if timeframe not in ALLOWED_TIMEFRAMES:
            raise ValueError(
                f"Timeframe '{timeframe}' is not supported. Allowed: {ALLOWED_TIMEFRAMES}"
            )

        mapped_timeframe = TIME_MAP[timeframe]
        is_valid, asset_class = self.validate_asset(symbol)

        if not is_valid or not asset_class:
            raise ValueError(f"Asset '{symbol}' is not valid or active.")

        # Ensure UTC safety for start/end
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        start_utc = start.astimezone(timezone.utc)
        start_str = start_utc.isoformat().replace("+00:00", "Z")

        params = {
            "action": "bars",
            "symbol": symbol,
            "timeframe": mapped_timeframe,
            "start": start_str,
            "asset_class": asset_class,
        }

        if end:
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            end_utc = end.astimezone(timezone.utc)
            params["end"] = end_utc.isoformat().replace("+00:00", "Z")

        logger.info(
            f"Fetching {mapped_timeframe} bars for {symbol} ({asset_class}) from {start_str}"
        )

        response = self.client.get(
            self.edge_function_url, params=params, headers=self.headers
        )
        response.raise_for_status()
        data = response.json()

        bars = data.get("bars", {})
        symbol_bars = bars.get(symbol, [])

        # Fallback for Alpaca's occasional non-symbol-keyed crypto response
        if not symbol_bars and "crypto" in asset_class:
            if bars and isinstance(bars, dict):
                values = list(bars.values())
                if values:
                    symbol_bars = values[0]

        if not symbol_bars:
            logger.warning(f"No bars returned for {symbol}")
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume", "vwap"]
            )

        df = pd.DataFrame(symbol_bars)

        # Consistent OHLCV mapping
        column_mapping = {
            "t": "timestamp",
            "o": "open",
            "h": "high",
            "l": "low",
            "c": "close",
            "v": "volume",
            "vw": "vwap",
        }
        df = df.rename(
            columns={k: v for k, v in column_mapping.items() if k in df.columns}
        )

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()

        required = ["open", "high", "low", "close", "volume", "vwap"]
        df = df[[c for c in required if c in df.columns]]
        return df.astype(float)
