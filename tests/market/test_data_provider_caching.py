from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from crypto_signals.config import Settings
from crypto_signals.domain.schemas import AssetClass
from crypto_signals.market.data_provider import MarketDataProvider, memory


@pytest.fixture
def mock_clients():
    stock_client = Mock()
    crypto_client = Mock()
    return stock_client, crypto_client


def test_memory_location_is_none_by_default():
    """
    Regression Test: Ensure joblib memory location is None by default.
    critical for production safety.
    """
    assert memory.location is None


def test_routing_disabled_by_default(mock_clients):
    """Test that requests route to _fetch_bars_core when caching is disabled (default)."""
    stock_client, crypto_client = mock_clients
    provider = MarketDataProvider(stock_client, crypto_client)

    with (
        patch("crypto_signals.market.data_provider._fetch_bars_core") as mock_core,
        patch("crypto_signals.market.data_provider._fetch_bars_cached") as mock_cached,
    ):
        provider.get_daily_bars("AAPL", AssetClass.EQUITY, lookback_days=10)

        mock_core.assert_called_once()
        mock_cached.assert_not_called()

        # Verify call args
        args, kwargs = mock_core.call_args
        assert kwargs["symbol"] == "AAPL"
        assert kwargs["cache_key"] == "no-cache"


def test_routing_enabled_and_cache_key(mock_clients):
    """Test that requests route to _fetch_bars_cached with correct key when enabled."""
    stock_client, crypto_client = mock_clients

    # Enable caching setting
    with patch("crypto_signals.market.data_provider.get_settings") as mock_settings:
        mock_settings.return_value = Settings(ENABLE_MARKET_DATA_CACHE=True)
        provider = MarketDataProvider(stock_client, crypto_client)

        with (
            patch("crypto_signals.market.data_provider._fetch_bars_core") as mock_core,
            patch(
                "crypto_signals.market.data_provider._fetch_bars_cached"
            ) as mock_cached,
            patch("crypto_signals.market.data_provider.datetime") as mock_datetime,
        ):
            # Mock time for stable cache key
            fixed_now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = fixed_now

            provider.get_daily_bars("BTC/USD", AssetClass.CRYPTO, lookback_days=5)

            mock_cached.assert_called_once()
            mock_core.assert_not_called()

            # Verify cache key format (YYYY-MM-DD from mock time)
            args, kwargs = mock_cached.call_args
            assert kwargs["symbol"] == "BTC/USD"
            assert kwargs["cache_key"] == "2023-01-01"
