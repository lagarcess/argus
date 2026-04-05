"""
Market Data Provider.

This module abstracts the Alpaca API to provide clean, validated market data
(Candles/Bars) and real-time prices for both Stocks and Crypto.
"""

import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Dict, Optional

import joblib
import pandas as pd
from alpaca.common.enums import Sort
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import (
    CryptoBarsRequest,
    CryptoLatestTradeRequest,
    StockBarsRequest,
    StockLatestTradeRequest,
)
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from argus.config import get_settings
from argus.domain.schemas import AssetClass
from argus.market.exceptions import MarketDataError

# Configure joblib memory cache
# Only set location if caching is enabled to avoid creating directories in production
settings = get_settings()
location = ".gemini/cache" if settings.ENABLE_MARKET_DATA_CACHE else None
memory = joblib.Memory(location=location, verbose=0)


def retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    """
    Decorator to retry functions with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds between retries
        backoff_factor: Multiplier for delay after each retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        # Log retry attempt
                        from loguru import logger

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed for "
                            f"{func.__name__}: {e}. Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        # Last attempt failed - log error
                        from loguru import logger

                        logger.error(
                            f"{func.__name__} failed after {max_retries} "
                            f"attempts: {last_exception}"
                        )
                        raise MarketDataError(
                            f"{func.__name__} failed after {max_retries} attempts"
                        ) from last_exception

            # Should not reach here, but if it does, raise the last exception
            raise MarketDataError(
                f"{func.__name__} failed after {max_retries} attempts"
            ) from last_exception

        return wrapper

    return decorator


class MarketDataProvider:
    """
    Provider for market data (Stocks and Crypto).

    Wraps Alpaca's historical data clients.
    """

    def __init__(
        self,
        stock_client: StockHistoricalDataClient,
        crypto_client: CryptoHistoricalDataClient,
    ):
        """
        Initialize with data clients.

        Args:
            stock_client: Alpaca Stock client
            crypto_client: Alpaca Crypto client
        """
        self.stock_client = stock_client
        self.crypto_client = crypto_client

    def _parse_timeframe(self, timeframe_str: str) -> TimeFrame:
        import re

        match = re.match(
            r"^(\d+)?(Min|Hour|Day|Week|Month)$", timeframe_str, re.IGNORECASE
        )
        if not match:
            raise MarketDataError(f"Invalid timeframe format: {timeframe_str}")

        amount_str, unit_str = match.groups()
        amount = int(amount_str) if amount_str else 1
        unit_str = unit_str.capitalize()

        unit_map = {
            "Min": TimeFrameUnit.Minute,
            "Hour": TimeFrameUnit.Hour,
            "Day": TimeFrameUnit.Day,
            "Week": TimeFrameUnit.Week,
            "Month": TimeFrameUnit.Month,
        }
        unit = unit_map.get(unit_str)
        if unit is None:
            raise MarketDataError(f"Unsupported timeframe unit: {unit_str}")

        return TimeFrame(amount, unit)

    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_historical_bars(
        self,
        symbol: str | list[str],
        asset_class: AssetClass,
        timeframe_str: str,
        start_dt: datetime,
        end_dt: datetime,
        limit: Optional[int] = None,
        adjustment: Optional[str] = None,
        asof: Optional[str] = None,
        feed: Optional[str] = None,
        currency: Optional[str] = None,
        page_token: Optional[str] = None,
        sort: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch historical bars with customizable timeframe and full Alpaca API parameter support.

        Args:
            symbol: Ticker symbol (e.g. "BTC/USD") or list of symbols
            asset_class: Asset class (CRYPTO or EQUITY)
            timeframe_str: Timeframe string e.g., '1Min', '15Min', '1Day'
            start_dt: Start datetime
            end_dt: End datetime
            limit: Limit number of bars returned
            adjustment: Corporate action adjustment for stocks
            asof: Asof date for stock feeds
            feed: Data feed
            currency: Currency for crypto
            page_token: Pagination token
            sort: Sorting order

        Returns:
            pd.DataFrame: DataFrame containing historical bars
        """
        try:
            tf = self._parse_timeframe(timeframe_str)

            if asset_class == AssetClass.CRYPTO:
                # Add optional crypto parameters
                crypto_kwargs: Dict[str, Any] = {
                    "symbol_or_symbols": symbol,
                    "timeframe": tf,
                    "start": start_dt,
                    "end": end_dt,
                }
                if limit is not None:
                    crypto_kwargs["limit"] = limit
                if page_token is not None:
                    crypto_kwargs["page_token"] = page_token
                if sort is not None:
                    crypto_kwargs["sort"] = sort if isinstance(sort, Sort) else Sort(sort)

                crypto_req = CryptoBarsRequest(**crypto_kwargs)
                bars = self.crypto_client.get_crypto_bars(crypto_req)

            elif asset_class == AssetClass.EQUITY:
                adj = Adjustment.SPLIT
                if adjustment is not None:
                    adj = (
                        adjustment
                        if isinstance(adjustment, Adjustment)
                        else Adjustment(adjustment)
                    )

                stock_kwargs: Dict[str, Any] = {
                    "symbol_or_symbols": symbol,
                    "timeframe": tf,
                    "start": start_dt,
                    "end": end_dt,
                    "adjustment": adj,
                }
                if limit is not None:
                    stock_kwargs["limit"] = limit
                if page_token is not None:
                    stock_kwargs["page_token"] = page_token
                if feed is not None:
                    stock_kwargs["feed"] = (
                        feed if isinstance(feed, DataFeed) else DataFeed(feed)
                    )
                if asof is not None:
                    stock_kwargs["asof"] = asof

                stock_req = StockBarsRequest(**stock_kwargs)
                bars = self.stock_client.get_stock_bars(stock_req)
            else:
                raise MarketDataError(f"Unsupported asset class: {asset_class}")

            df = bars.df  # type: ignore

            if df.empty:
                raise MarketDataError(f"No bars found for {symbol}")

            if isinstance(symbol, str) and isinstance(df.index, pd.MultiIndex):
                df = df.reset_index(level=0, drop=True)

            if not isinstance(df.index, pd.MultiIndex):
                df.index = pd.to_datetime(df.index)

            return df

        except MarketDataError:
            raise
        except Exception as e:
            raise MarketDataError(
                f"Failed to fetch historical bars for {symbol}: {e}"
            ) from e

    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_daily_bars(
        self,
        symbol: str | list[str],
        asset_class: AssetClass,
        lookback_days: int = 365,
    ) -> pd.DataFrame:
        """
        Fetch daily bars for a symbol or list of symbols.

        Args:
            symbol: Ticker symbol (e.g. "BTC/USD") or list of symbols
            asset_class: Asset class (CRYPTO or EQUITY)
            lookback_days: Number of days of history to fetch

        Returns:
            pd.DataFrame:
                - If single symbol: DataFrame indexed by date (UTC)
                - If list of symbols: MultiIndex DataFrame (symbol, date)

        Raises:
            MarketDataError: If data is empty or fetch fails
        """
        settings = get_settings()

        # Defensive coding: Upstream callers might pass None (Issue #252)
        lookback_days = lookback_days or 365

        # If caching is enabled, use the cached wrapper.
        # Otherwise, call the core function directly.
        try:
            if settings.ENABLE_MARKET_DATA_CACHE:
                # Calculate cache key based on current DATE (midnight UTC) to ensure freshness
                # This acts as a TTL for the joblib cache
                cache_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                return _fetch_bars_cached(
                    symbol=symbol,
                    asset_class=asset_class,
                    lookback_days=lookback_days,
                    stock_client=self.stock_client,
                    crypto_client=self.crypto_client,
                    cache_key=cache_key,
                )
            else:
                return _fetch_bars_core(
                    symbol=symbol,
                    asset_class=asset_class,
                    lookback_days=lookback_days,
                    stock_client=self.stock_client,
                    crypto_client=self.crypto_client,
                    cache_key="no-cache",
                )
        except MarketDataError:
            raise
        except Exception as e:
            raise MarketDataError(f"Failed to fetch daily bars for {symbol}: {e}") from e

    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_latest_price(self, symbol: str, asset_class: AssetClass) -> float:
        """
        Fetch the absolute latest trade price (real-time).

        Args:
            symbol: Ticker symbol
            asset_class: Asset class

        Returns:
            float: Latest trade price

        Raises:
            MarketDataError: If data fetching fails or the asset class is unsupported.
        """
        price: Optional[float] = None
        try:
            if asset_class == AssetClass.CRYPTO:
                crypto_req = CryptoLatestTradeRequest(symbol_or_symbols=symbol)
                trade = self.crypto_client.get_crypto_latest_trade(crypto_req)
                if trade and symbol in trade:
                    price = trade[symbol].price

            elif asset_class == AssetClass.EQUITY:
                stock_req = StockLatestTradeRequest(symbol_or_symbols=symbol)
                trade = self.stock_client.get_stock_latest_trade(stock_req)
                if trade and symbol in trade:
                    price = trade[symbol].price
            else:
                raise MarketDataError(f"Unsupported asset class: {asset_class}")

            if price is None:
                raise MarketDataError(f"Latest trade price for {symbol} is null.")

            return float(price)

        except MarketDataError:
            raise
        except Exception as e:
            raise MarketDataError(
                f"Failed to fetch latest price for {symbol}: {e}"
            ) from e


def _fetch_bars_core(
    symbol: str | list[str],
    asset_class: AssetClass,
    lookback_days: int,
    stock_client: StockHistoricalDataClient,
    crypto_client: CryptoHistoricalDataClient,
    cache_key: str,
) -> pd.DataFrame:
    """
    Core implementation of get_daily_bars (uncached).

    Args:
        symbol: Ticker symbol or list of symbols
        asset_class: Asset Class
        lookback_days: Lookback period
        stock_client: Alpaca Stock Client
        crypto_client: Alpaca Crypto Client
        cache_key: Passed for compatibility with cached version, ignored here.
    """
    try:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=lookback_days)

        if asset_class == AssetClass.CRYPTO:
            # Crypto Request
            crypto_req = CryptoBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_dt,
                end=end_dt,
            )
            bars = crypto_client.get_crypto_bars(crypto_req)
        elif asset_class == AssetClass.EQUITY:
            # Stock Request
            stock_req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start_dt,
                end=end_dt,
                adjustment=Adjustment.SPLIT,  # Adjust for splits
            )
            bars = stock_client.get_stock_bars(stock_req)
        else:
            raise MarketDataError(f"Unsupported asset class: {asset_class}")

        # Convert to DataFrame
        # Mypy sees bars as (BarSet | dict), but we know it returns BarSet here for the request
        df = bars.df  # type: ignore

        if df.empty:
            raise MarketDataError(f"No daily bars found for {symbol}")

        # Reset index if multi-indexed (symbol, date) -> just date
        # Alpaca bars.df usually has MultiIndex [symbol, timestamp]
        # logic: if we passed a single symbol (str), we want to return just date index (convenience)
        # if we passed a list, we KEEP the multiindex [symbol, timestamp] so caller can separate
        if isinstance(symbol, str) and isinstance(df.index, pd.MultiIndex):
            df = df.reset_index(level=0, drop=True)

        # Ensure timestamp level (or index) is datetime
        # If MultiIndex, level 1 is timestamp. If single index, index is timestamp.
        if isinstance(df.index, pd.MultiIndex):
            # Check if second level is not datetime (rare but possible if re-ordered)
            # Usually Alpaca returns [symbol, timestamp]
            pass  # Alpaca SDK handles this well usually
        else:
            df.index = pd.to_datetime(df.index)

        return df

    except MarketDataError:
        raise
    except Exception as e:
        raise MarketDataError(f"Error in _fetch_bars_core: {e}") from e


# Create a cached version of the core function
_fetch_bars_cached = memory.cache(
    _fetch_bars_core,
    ignore=["stock_client", "crypto_client"],
)
