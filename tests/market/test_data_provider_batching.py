from unittest.mock import Mock, patch

import pandas as pd
import pytest
from crypto_signals.domain.schemas import AssetClass
from crypto_signals.market.data_provider import MarketDataProvider


class TestDataProviderBatching:
    @pytest.fixture
    def mock_clients(self):
        return Mock(), Mock()

    def test_get_daily_bars_single_symbol(self, mock_clients):
        """Verify fetching daily bars for a single symbol."""
        stock_client, crypto_client = mock_clients
        provider = MarketDataProvider(stock_client, crypto_client)

        # Setup mock return
        dates = pd.date_range("2023-01-01", periods=5)
        df_mock = pd.DataFrame({"close": [1, 2, 3, 4, 5]}, index=dates)

        # Mock core fetch
        with patch(
            "crypto_signals.market.data_provider._fetch_bars_core", return_value=df_mock
        ) as mock_core:
            df = provider.get_daily_bars("AAPL", AssetClass.EQUITY, lookback_days=10)

            assert isinstance(df.index, pd.DatetimeIndex)
            mock_core.assert_called_once()
            args, kwargs = mock_core.call_args
            assert kwargs["symbol"] == "AAPL"

    def test_get_daily_bars_list_symbols(self, mock_clients):
        """Verify batch fetching of daily bars for multiple symbols."""
        stock_client, crypto_client = mock_clients
        provider = MarketDataProvider(stock_client, crypto_client)

        # Setup mock return for MultiIndex
        dates = pd.date_range("2023-01-01", periods=2)
        iterables = [["AAPL", "GOOG"], dates]
        index = pd.MultiIndex.from_product(iterables, names=["symbol", "timestamp"])
        df_mock = pd.DataFrame({"close": [100, 101, 200, 202]}, index=index)

        with patch(
            "crypto_signals.market.data_provider._fetch_bars_core", return_value=df_mock
        ) as mock_core:
            df = provider.get_daily_bars(
                ["AAPL", "GOOG"], AssetClass.EQUITY, lookback_days=10
            )

            assert isinstance(df.index, pd.MultiIndex)
            mock_core.assert_called_once()
            args, kwargs = mock_core.call_args
            assert kwargs["symbol"] == ["AAPL", "GOOG"]
