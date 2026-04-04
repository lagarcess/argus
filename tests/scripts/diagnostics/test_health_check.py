from unittest.mock import MagicMock, patch

from crypto_signals.scripts.diagnostics.health_check import (
    verify_alpaca_market_data,
    verify_alpaca_trading,
    verify_firestore,
)


def test_verify_alpaca_trading_success():
    """Test verify_alpaca_trading success path."""
    mock_settings = MagicMock()
    mock_settings.ALPACA_API_KEY = "key"
    mock_settings.ALPACA_SECRET_KEY = "secret"
    mock_settings.is_paper_trading = True

    with patch(
        "crypto_signals.scripts.diagnostics.health_check.TradingClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value
        result = verify_alpaca_trading(mock_settings)
        assert result is True, "verify_alpaca_trading failed to return True"
        mock_client.get_account.assert_called_once()
        assert (
            mock_client.get_account.call_count == 1
        ), "Expected get_account to be called exactly once"


def test_verify_alpaca_market_data_success():
    """Test verify_alpaca_market_data success path."""
    mock_settings = MagicMock()
    mock_settings.ALPACA_API_KEY = "key"
    mock_settings.ALPACA_SECRET_KEY = "secret"

    with patch(
        "crypto_signals.scripts.diagnostics.health_check.CryptoHistoricalDataClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.get_crypto_bars.return_value.data = {
            "BTC/USD": [MagicMock(close=50000.0)]
        }
        result = verify_alpaca_market_data(mock_settings)
        assert result is True, "verify_alpaca_market_data failed to return True"


def test_verify_firestore_success():
    """Test verify_firestore success path."""
    mock_settings = MagicMock()
    mock_settings.GOOGLE_CLOUD_PROJECT = "project"

    with patch(
        "crypto_signals.scripts.diagnostics.health_check.firestore.Client"
    ) as mock_cls:
        mock_client = mock_cls.return_value
        # Mocking collection().document().set()
        result = verify_firestore(mock_settings)
        assert result is True, "verify_firestore failed to return True"
        assert mock_client.collection.called, "Firestore collection was not accessed"
