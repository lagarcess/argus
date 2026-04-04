"""Tests for the AssetValidationService module."""

import uuid
from unittest.mock import Mock, patch

import pytest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass as AlpacaAssetClass
from alpaca.trading.enums import AssetStatus
from alpaca.trading.models import Asset
from crypto_signals.domain.schemas import AssetClass
from crypto_signals.market.asset_service import AssetValidationService


@pytest.fixture
def mock_trading_client():
    """Mock trading client."""
    return Mock(spec=TradingClient)


@pytest.fixture
def service(mock_trading_client):
    """Fixture for AssetValidationService with mocked client."""
    return AssetValidationService(mock_trading_client)


def _create_mock_asset(symbol: str, status: AssetStatus, tradable: bool):
    """Helper to create mock asset objects."""
    data = {
        "id": uuid.uuid4(),
        "class": AlpacaAssetClass.CRYPTO,
        "exchange": "CRYPTO",
        "symbol": symbol,
        "name": symbol,
        "status": status,
        "tradable": tradable,
        "marginable": True,
        "shortable": True,
        "easy_to_borrow": True,
        "fractionable": True,
    }
    return Asset.model_validate(data)


class TestSymbolNormalization:
    """Tests for symbol normalization."""

    def test_normalize_symbol_removes_slash(self, service):
        """Test that slashes are removed from symbols."""
        assert service._normalize_symbol("BTC/USD") == "BTCUSD"

    def test_normalize_symbol_uppercase(self, service):
        """Test that symbols are uppercased."""
        assert service._normalize_symbol("btc/usd") == "BTCUSD"

    def test_normalize_symbol_no_slash(self, service):
        """Test that symbols without slashes work."""
        assert service._normalize_symbol("AAPL") == "AAPL"


class TestAssetClassMapping:
    """Tests for asset class mapping."""

    def test_map_crypto_to_alpaca(self, service):
        """Test mapping CRYPTO to Alpaca's CRYPTO."""
        result = service._map_asset_class(AssetClass.CRYPTO)
        assert result == AlpacaAssetClass.CRYPTO

    def test_map_equity_to_alpaca(self, service):
        """Test mapping EQUITY to Alpaca's US_EQUITY."""
        result = service._map_asset_class(AssetClass.EQUITY)
        assert result == AlpacaAssetClass.US_EQUITY

    def test_map_invalid_raises(self, service):
        """Test that invalid asset class raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported asset class"):
            service._map_asset_class("COMMODITY")  # type: ignore


class TestGetValidPortfolio:
    """Tests for get_valid_portfolio method."""

    def test_filters_inactive_assets(self, service, mock_trading_client):
        """Test that inactive assets are filtered out."""
        mock_trading_client.get_all_assets.return_value = [
            _create_mock_asset("BTCUSD", AssetStatus.ACTIVE, True),
            _create_mock_asset("ETHUSD", AssetStatus.INACTIVE, True),  # Inactive
        ]

        with patch("crypto_signals.market.asset_service.log_critical_situation"):
            result = service.get_valid_portfolio(
                ["BTC/USD", "ETH/USD"], AssetClass.CRYPTO
            )

        assert result == ["BTCUSD"]

    def test_filters_non_tradable_assets(self, service, mock_trading_client):
        """Test that non-tradable assets are filtered out."""
        mock_trading_client.get_all_assets.return_value = [
            _create_mock_asset("BTCUSD", AssetStatus.ACTIVE, True),
            _create_mock_asset("ADAUSD", AssetStatus.ACTIVE, False),  # Not tradable
        ]

        with patch("crypto_signals.market.asset_service.log_critical_situation"):
            result = service.get_valid_portfolio(
                ["BTC/USD", "ADA/USD"], AssetClass.CRYPTO
            )

        assert result == ["BTCUSD"]

    def test_filters_missing_symbols(self, service, mock_trading_client):
        """Test that symbols not found in Alpaca are filtered out."""
        mock_trading_client.get_all_assets.return_value = [
            _create_mock_asset("BTCUSD", AssetStatus.ACTIVE, True),
        ]

        with patch("crypto_signals.market.asset_service.log_critical_situation"):
            result = service.get_valid_portfolio(
                ["BTC/USD", "FAKE/USD"], AssetClass.CRYPTO
            )

        assert result == ["BTCUSD"]

    def test_symbol_normalization_returns_alpaca_format(
        self, service, mock_trading_client
    ):
        """Test that BTC/USD maps to BTCUSD (Alpaca's format) in the result."""
        mock_trading_client.get_all_assets.return_value = [
            _create_mock_asset("BTCUSD", AssetStatus.ACTIVE, True),
        ]

        result = service.get_valid_portfolio(["BTC/USD"], AssetClass.CRYPTO)

        # Returns Alpaca's preferred format, not the config format
        assert result == ["BTCUSD"]

    def test_empty_input_returns_empty(self, service, mock_trading_client):
        """Test that empty symbol list returns empty list."""
        result = service.get_valid_portfolio([], AssetClass.CRYPTO)

        assert result == []
        mock_trading_client.get_all_assets.assert_not_called()

    def test_logs_skipped_symbols(self, service, mock_trading_client):
        """Test that skipped symbols are logged with log_critical_situation."""
        mock_trading_client.get_all_assets.return_value = [
            _create_mock_asset("BTCUSD", AssetStatus.ACTIVE, True),
            _create_mock_asset("ADAUSD", AssetStatus.ACTIVE, False),  # Not tradable
        ]

        with patch(
            "crypto_signals.market.asset_service.log_critical_situation"
        ) as mock_log:
            service.get_valid_portfolio(["BTC/USD", "ADA/USD"], AssetClass.CRYPTO)

        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert call_args[1]["situation"] == "INACTIVE ASSET SKIPPED"
        assert "ADA/USD" in call_args[1]["details"]
        assert "non-tradable" in call_args[1]["details"]

    def test_returns_alpaca_format_for_matching_symbols(
        self, service, mock_trading_client
    ):
        """Test that result contains Alpaca's symbol format, not config format."""
        mock_trading_client.get_all_assets.return_value = [
            _create_mock_asset(
                "BTC/USD", AssetStatus.ACTIVE, True
            ),  # Alpaca returns slashed
            _create_mock_asset(
                "ETHUSD", AssetStatus.ACTIVE, True
            ),  # Alpaca returns no slash
        ]

        result = service.get_valid_portfolio(["BTCUSD", "ETH/USD"], AssetClass.CRYPTO)

        # Returns Alpaca's exact format
        assert "BTC/USD" in result  # From Alpaca's format
        assert "ETHUSD" in result  # From Alpaca's format

    def test_api_failure_returns_original(self, service, mock_trading_client):
        """Test that API failure returns original symbols (fail-open)."""
        mock_trading_client.get_all_assets.side_effect = Exception("API Error")

        result = service.get_valid_portfolio(["BTC/USD", "ETH/USD"], AssetClass.CRYPTO)

        assert result == ["BTC/USD", "ETH/USD"]

    def test_correct_asset_class_passed_to_api(self, service, mock_trading_client):
        """Test that correct asset class is passed to Alpaca API."""
        mock_trading_client.get_all_assets.return_value = []

        service.get_valid_portfolio(["AAPL"], AssetClass.EQUITY)

        call_args = mock_trading_client.get_all_assets.call_args[0][0]
        assert call_args.asset_class == AlpacaAssetClass.US_EQUITY
