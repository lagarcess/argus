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
from loguru import logger

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
        fetcher: Optional[Any] = None,
    ):
        """
        Initialize with data clients and optional hybrid fetcher.

        Args:
            stock_client: Alpaca Stock client
            crypto_client: Alpaca Crypto client
            fetcher: AlpacaDataFetcher instance for hybrid proxy routing
        """
        self.stock_client = stock_client
        self.crypto_client = crypto_client
        self.fetcher = fetcher

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
            settings = get_settings()

            # Hybrid Router: Try Proxy first if enabled and standard request
            if (
                self.fetcher
                and settings.ENABLE_MARKET_DATA_PROXY
                and not adjustment
                and not asof
                and not feed
                and not page_token
                and not sort
                and isinstance(symbol, str)
            ):
                try:
                    df = self.fetcher.fetch_bars(
                        symbol=symbol,
                        timeframe=timeframe_str,
                        start=start_dt,
                        end=end_dt,
                    )
                    if not df.empty:
                        # Ensure column normalization
                        try:
                            df.columns = [str(c).lower() for c in df.columns]
                        except Exception as e:
                            logger.warning(
                                f"Proxy column normalization failed for {symbol}: {e}"
                            )
                        return df
                except Exception as e:
                    logger.warning(
                        f"Proxy fetch failed for {symbol}, falling back to SDK: {e}"
                    )

            tf = self._parse_timeframe(timeframe_str)

            # Convert string parameters to Alpaca Enums if provided
            adj = None
            if adjustment:
                adj = (
                    adjustment
                    if isinstance(adjustment, Adjustment)
                    else Adjustment(adjustment)
                )

            df_out = None
            if settings.ENABLE_MARKET_DATA_CACHE:
                df_out = _fetch_bars_with_ttl(
                    symbol=symbol,
                    asset_class=asset_class,
                    timeframe=tf,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    stock_client=self.stock_client,
                    crypto_client=self.crypto_client,
                    limit=limit,
                    adjustment=adj,
                    asof=asof,
                    feed=feed,
                    page_token=page_token,
                    sort=sort,
                )
            else:
                df_out = _fetch_bars_core(
                    symbol=symbol,
                    asset_class=asset_class,
                    timeframe=tf,
                    start_dt=start_dt,
                    end_dt=end_dt,
                    stock_client=self.stock_client,
                    crypto_client=self.crypto_client,
                    limit=limit,
                    adjustment=adj,
                    asof=asof,
                    feed=feed,
                    page_token=page_token,
                    sort=sort,
                )

            # Post-processing: Normalize all columns to lowercase
            if df_out is not None and not df_out.empty:
                try:
                    df_out.columns = [str(c).lower() for c in df_out.columns]
                except Exception as e:
                    logger.warning(f"SDK column normalization failed for {symbol}: {e}")

            return df_out

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
        """
        settings = get_settings()
        lookback_days = lookback_days or 365

        # Use midnight UTC for daily bars to ensure stable cache keys
        end_dt = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_dt = end_dt - timedelta(days=lookback_days)
        timeframe = TimeFrame.Day

        if settings.ENABLE_MARKET_DATA_CACHE:
            return _fetch_bars_with_ttl(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                start_dt=start_dt,
                end_dt=end_dt,
                stock_client=self.stock_client,
                crypto_client=self.crypto_client,
            )
        else:
            return _fetch_bars_core(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                start_dt=start_dt,
                end_dt=end_dt,
                stock_client=self.stock_client,
                crypto_client=self.crypto_client,
            )

    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_latest_price(self, symbol: str, asset_class: AssetClass) -> float:
        """
        Fetch the absolute latest trade price (real-time).
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
    timeframe: TimeFrame,
    start_dt: datetime,
    end_dt: datetime,
    stock_client: StockHistoricalDataClient,
    crypto_client: CryptoHistoricalDataClient,
    limit: Optional[int] = None,
    adjustment: Optional[Adjustment] = None,
    asof: Optional[str] = None,
    feed: Optional[str] = None,
    page_token: Optional[str] = None,
    sort: Optional[str] = None,
    cache_bin: Optional[int] = None,
) -> pd.DataFrame:
    """
    Core implementation of fetch_bars (uncached by joblib directly, but wrapped).
    Includes full parameter support for Alpaca API.
    """
    try:
        if asset_class == AssetClass.CRYPTO:
            crypto_kwargs: Dict[str, Any] = {
                "symbol_or_symbols": symbol,
                "timeframe": timeframe,
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
            bars = crypto_client.get_crypto_bars(crypto_req)

        elif asset_class == AssetClass.EQUITY:
            adj = adjustment or Adjustment.SPLIT
            stock_kwargs: Dict[str, Any] = {
                "symbol_or_symbols": symbol,
                "timeframe": timeframe,
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
            bars = stock_client.get_stock_bars(stock_req)
        else:
            raise MarketDataError(f"Unsupported asset class: {asset_class}")

        df = bars.df
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
        raise MarketDataError(f"Error in _fetch_bars_core: {e}") from e


# Create a cached version of the core function.
# Clients are ignored because they contain session state.
_fetch_bars_cached = memory.cache(
    _fetch_bars_core,
    ignore=["stock_client", "crypto_client"],
)


def _fetch_bars_with_ttl(
    symbol: str | list[str],
    asset_class: AssetClass,
    timeframe: TimeFrame,
    start_dt: datetime,
    end_dt: datetime,
    stock_client: StockHistoricalDataClient,
    crypto_client: CryptoHistoricalDataClient,
    limit: Optional[int] = None,
    adjustment: Optional[Adjustment] = None,
    asof: Optional[str] = None,
    feed: Optional[str] = None,
    page_token: Optional[str] = None,
    sort: Optional[str] = None,
) -> pd.DataFrame:
    """
    Caching wrapper that uses 'cache binning' for TTL.
    """
    # 1. Timezone Consistency (Force UTC)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    else:
        start_dt = start_dt.astimezone(timezone.utc)

    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    else:
        end_dt = end_dt.astimezone(timezone.utc)

    # 2. 15-Minute Safety Binning
    # Matches the engine's safety buffer to avoid incomplete bars.
    bin_size = 900  # 15 minutes
    cache_bin = int(time.time()) // bin_size

    # 3. Check for Cache Hit (for logging purposes)
    is_in_cache = _fetch_bars_cached.check_call_in_cache(
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        start_dt=start_dt,
        end_dt=end_dt,
        stock_client=stock_client,
        crypto_client=crypto_client,
        limit=limit,
        adjustment=adjustment,
        asof=asof,
        feed=feed,
        page_token=page_token,
        sort=sort,
        cache_bin=cache_bin,
    )

    if is_in_cache:
        logger.debug(f"Cache HIT for {symbol} | Bin: {cache_bin}")
    else:
        logger.info(f"Cache MISS for {symbol} | Fetching from Alpaca | Bin: {cache_bin}")

    # 4. Execute (Joblib handles the actual caching logic)
    return _fetch_bars_cached(
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        start_dt=start_dt,
        end_dt=end_dt,
        stock_client=stock_client,
        crypto_client=crypto_client,
        limit=limit,
        adjustment=adjustment,
        asof=asof,
        feed=feed,
        page_token=page_token,
        sort=sort,
        cache_bin=cache_bin,
    )
