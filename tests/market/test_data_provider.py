"""Tests for the MarketDataProvider module."""

from unittest.mock import Mock

import pandas as pd
import pytest
from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.timeframe import TimeFrame
from crypto_signals.domain.schemas import AssetClass
from crypto_signals.market.data_provider import MarketDataProvider, memory
from crypto_signals.market.exceptions import MarketDataError


@pytest.fixture(autouse=True)
def clear_cache():
    memory.clear(warn=False)
    yield
    memory.clear(warn=False)


@pytest.fixture
def mock_stock_client():
    """Mock stock historical data client."""
    return Mock(spec=StockHistoricalDataClient)


@pytest.fixture
def mock_crypto_client():
    """Mock crypto historical data client."""
    return Mock(spec=CryptoHistoricalDataClient)


@pytest.fixture
def provider(mock_stock_client, mock_crypto_client):
    """Fixture for MarketDataProvider with mocked clients."""
    return MarketDataProvider(mock_stock_client, mock_crypto_client)


def test_init(mock_stock_client, mock_crypto_client):
    """Test initialization of MarketDataProvider."""
    provider = MarketDataProvider(mock_stock_client, mock_crypto_client)
    assert provider.stock_client == mock_stock_client
    assert provider.crypto_client == mock_crypto_client


def test_get_daily_bars_equity_success(provider, mock_stock_client):
    """Test fetching equity bars proxies to stock client correctly."""
    # Setup
    mock_bars = Mock()
    # Mock dataframe response
    df_data = {"close": [150.0, 155.0]}
    df = pd.DataFrame(df_data)
    mock_bars.df = df
    mock_stock_client.get_stock_bars.return_value = mock_bars

    # Exec
    result = provider.get_daily_bars("AAPL", AssetClass.EQUITY, lookback_days=10)

    # Verify
    assert result.equals(df)
    mock_stock_client.get_stock_bars.assert_called_once()
    call_args = mock_stock_client.get_stock_bars.call_args[0][0]
    assert call_args.symbol_or_symbols == "AAPL"
    # Compare TimeFrame properties as object equality might fail
    assert call_args.timeframe.amount == TimeFrame.Day.amount
    assert call_args.timeframe.unit == TimeFrame.Day.unit
    assert call_args.adjustment == "split"


def test_get_daily_bars_crypto_success(provider, mock_crypto_client):
    """Test fetching crypto bars proxies to crypto client correctly."""
    # Setup
    mock_bars = Mock()
    df_data = {"close": [50000.0, 51000.0]}
    df = pd.DataFrame(df_data)
    mock_bars.df = df
    mock_crypto_client.get_crypto_bars.return_value = mock_bars

    # Exec
    result = provider.get_daily_bars("BTC/USD", AssetClass.CRYPTO)

    # Verify
    assert result.equals(df)
    mock_crypto_client.get_crypto_bars.assert_called_once()
    call_args = mock_crypto_client.get_crypto_bars.call_args[0][0]
    assert call_args.symbol_or_symbols == "BTC/USD"
    assert call_args.timeframe.amount == TimeFrame.Day.amount
    assert call_args.timeframe.unit == TimeFrame.Day.unit


def test_get_daily_bars_empty_error(provider, mock_stock_client):
    """Test that empty dataframe raises MarketDataError."""
    mock_bars = Mock()
    mock_bars.df = pd.DataFrame()  # Empty
    mock_stock_client.get_stock_bars.return_value = mock_bars

    with pytest.raises(MarketDataError, match="get_daily_bars failed after"):
        provider.get_daily_bars("AAPL", AssetClass.EQUITY)


def test_get_daily_bars_api_error(provider, mock_stock_client):
    """Test API failure raises MarketDataError."""
    mock_stock_client.get_stock_bars.side_effect = Exception("API Down")

    with pytest.raises(MarketDataError, match="get_daily_bars failed after"):
        provider.get_daily_bars("AAPL", AssetClass.EQUITY)


def test_get_latest_price_equity(provider, mock_stock_client):
    """Test fetching latest equity price."""
    # Setup
    mock_trade_response = {"AAPL": Mock(price=150.50)}
    mock_stock_client.get_stock_latest_trade.return_value = mock_trade_response

    # Exec
    price = provider.get_latest_price("AAPL", AssetClass.EQUITY)

    # Verify
    assert price == 150.50
    mock_stock_client.get_stock_latest_trade.assert_called_once()
    call_args = mock_stock_client.get_stock_latest_trade.call_args[0][0]
    assert call_args.symbol_or_symbols == "AAPL"


def test_get_latest_price_crypto(provider, mock_crypto_client):
    """Test fetching latest crypto price."""
    # Setup
    mock_trade_response = {"BTC/USD": Mock(price=60000.00)}
    mock_crypto_client.get_crypto_latest_trade.return_value = mock_trade_response

    # Exec
    price = provider.get_latest_price("BTC/USD", AssetClass.CRYPTO)

    # Verify
    assert price == 60000.00
    mock_crypto_client.get_crypto_latest_trade.assert_called_once()
    call_args = mock_crypto_client.get_crypto_latest_trade.call_args[0][0]
    assert call_args.symbol_or_symbols == "BTC/USD"


def test_invalid_asset_class(provider):
    """Test checking invalid asset class."""
    # Pass an invalid string to bypass type checking and trigger
    # "Unsupported asset class" error
    with pytest.raises(MarketDataError, match="get_latest_price failed after"):
        provider.get_latest_price("GOLD", "COMMODITY")  # type: ignore


def test_get_daily_bars_invalid_asset_class(provider):
    """Test checking invalid asset class in get_daily_bars."""
    with pytest.raises(MarketDataError, match="get_daily_bars failed after"):
        provider.get_daily_bars("GOLD", "COMMODITY")  # type: ignore


def test_get_latest_price_missing_symbol(provider, mock_stock_client):
    """Test that missing symbol in response raises MarketDataError."""
    # Setup - Return empty dict or dict with different symbol
    mock_stock_client.get_stock_latest_trade.return_value = {}

    with pytest.raises(MarketDataError, match="get_latest_price failed after"):
        provider.get_latest_price("MSFT", AssetClass.EQUITY)


def test_get_daily_bars_multiindex_handling(provider, mock_stock_client):
    """Test that MultiIndex is correctly reset to single index."""
    # Setup - Create MultiIndex DataFrame
    dates = pd.date_range(start="2023-01-01", periods=2, name="timestamp")
    arrays = [["AAPL", "AAPL"], dates]
    tuples = list(zip(*arrays))
    index = pd.MultiIndex.from_tuples(tuples, names=["symbol", "timestamp"])
    df = pd.DataFrame({"close": [150.0, 155.0]}, index=index)

    mock_bars = Mock()
    mock_bars.df = df
    mock_stock_client.get_stock_bars.return_value = mock_bars

    # Exec
    result = provider.get_daily_bars("AAPL", AssetClass.EQUITY)

    # Verify
    assert not isinstance(result.index, pd.MultiIndex)
    pd.testing.assert_index_equal(result.index, dates)
    assert result["close"].iloc[0] == 150.0


def test_get_latest_price_api_error(provider, mock_stock_client):
    """Test that API failures in get_latest_price are wrapped in MarketDataError."""
    # Setup
    mock_stock_client.get_stock_latest_trade.side_effect = Exception(
        "API connection failed"
    )

    # Verify
    with pytest.raises(MarketDataError, match="get_latest_price failed after"):
        provider.get_latest_price("AAPL", AssetClass.EQUITY)


def test_get_daily_bars_none_lookback(provider, mock_crypto_client):
    """
    Test that lookback_days=None defaults to 365.
    Regression test for Issue #252.
    """
    # Setup
    import datetime
    from unittest.mock import patch

    mock_bars = Mock()
    df_data = {"close": [50000.0, 51000.0]}
    df = pd.DataFrame(df_data)
    mock_bars.df = df
    mock_crypto_client.get_crypto_bars.return_value = mock_bars

    fake_now = datetime.datetime(2023, 10, 26, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # Patch 'datetime' in the module where it is imported (market.data_provider)
    with patch("crypto_signals.market.data_provider.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_now

        # Exec
        # Explicitly passing None to simulate the crash condition
        result = provider.get_daily_bars(
            "BTC/USD",
            AssetClass.CRYPTO,
            lookback_days=None,  # type: ignore
        )

    # Verify
    assert result.equals(df)
    mock_crypto_client.get_crypto_bars.assert_called_once()

    # Check that start time corresponds exactly to 365 days ago
    call_args = mock_crypto_client.get_crypto_bars.call_args[0][0]
    assert call_args.start is not None

    expected_start = fake_now - datetime.timedelta(days=365)

    # Handle potential timezone stripping by Alpaca SDK
    # If the actual value is naive but we expected aware, compare naive values
    if call_args.start.tzinfo is None and expected_start.tzinfo is not None:
        assert call_args.start == expected_start.replace(tzinfo=None)
    else:
        assert call_args.start == expected_start

    if call_args.end.tzinfo is None and fake_now.tzinfo is not None:
        assert call_args.end == fake_now.replace(tzinfo=None)
    else:
        assert call_args.end == fake_now
