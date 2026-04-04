from unittest.mock import MagicMock

import pytest

# Local imports
from alpaca.trading.enums import AssetClass as AlpacaAssetClass
from alpaca.trading.enums import OrderSide
from alpaca.trading.models import Order, TradeAccount
from crypto_signals.config import Settings
from crypto_signals.domain.schemas import AssetClass
from crypto_signals.engine.risk import RiskEngine
from crypto_signals.market.data_provider import MarketDataProvider
from crypto_signals.repository.firestore import PositionRepository

# Ensure AssetClass is available in module scope for test methods
CRYPTO = AssetClass.CRYPTO
EQUITY = AssetClass.EQUITY


class TestRiskEngine:
    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock(spec=Settings)
        # Default Safe Settings
        settings.MAX_CRYPTO_POSITIONS = 5
        settings.MAX_EQUITY_POSITIONS = 5
        settings.MAX_DAILY_DRAWDOWN_PCT = 0.05  # 5%
        settings.MIN_ASSET_BP_USD = 100.0
        return settings

    @pytest.fixture
    def mock_repo(self):
        return MagicMock(spec=PositionRepository)

    @pytest.fixture
    def mock_market_provider(self):
        return MagicMock(spec=MarketDataProvider)

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        # default healthy account
        account = MagicMock(spec=TradeAccount)
        account.buying_power = "20000.00"  # Equity Reg-T
        account.regt_buying_power = "20000.00"  # Explicit Reg-T
        account.non_marginable_buying_power = "5000.00"  # Crypto Cash
        account.equity = "10000.00"
        account.last_equity = "10000.00"  # No drawdown
        client.get_account.return_value = account
        return client

    @pytest.fixture
    def risk_engine(self, mock_client, mock_repo, mock_settings, mock_market_provider):
        # Patch the engine's settings property or injected dependency
        # Patch get_settings() dependency for RiskEngine
        with pytest.MonkeyPatch.context() as m:
            # Patch at module level where it's imported
            m.setattr("crypto_signals.engine.risk.get_settings", lambda: mock_settings)
            engine = RiskEngine(
                trading_client=mock_client,
                repository=mock_repo,
                market_provider=mock_market_provider,
            )
            yield engine

    @pytest.mark.parametrize(
        "asset_class,required_bp,expected_passed,expected_reason_snippet",
        [
            pytest.param(CRYPTO, 1000.0, True, None, id="crypto_pass"),
            pytest.param(
                CRYPTO, 6000.0, False, "Insufficient Buying Power", id="crypto_fail"
            ),
            pytest.param(EQUITY, 10000.0, True, None, id="equity_pass"),
        ],
    )
    def test_check_buying_power(
        self,
        risk_engine,
        asset_class,
        required_bp,
        expected_passed,
        expected_reason_snippet,
    ):
        """Verify buying power checks for different asset classes."""
        # Arrange

        # Act
        result = risk_engine.check_buying_power(asset_class, required_bp)

        # Assert
        assert (
            result.passed == expected_passed
        ), f"Expected passed == {expected_passed} for {asset_class}, got {result.passed}"
        if expected_reason_snippet:
            assert (
                expected_reason_snippet in result.reason
            ), f'Expected "{expected_reason_snippet}" in reason, got "{result.reason}"'

    @pytest.mark.parametrize(
        "num_positions,num_orders,expected_passed",
        [
            pytest.param(4, 1, False, id="sector_cap_fail"),
            pytest.param(4, 0, True, id="sector_cap_pass"),
        ],
    )
    def test_check_sector_cap_crypto(
        self, risk_engine, mock_client, num_positions, num_orders, expected_passed
    ):
        """Verify sector cap limits including open orders."""
        # Arrange
        mock_pos = MagicMock()
        mock_pos.asset_class = AlpacaAssetClass.CRYPTO
        mock_client.get_all_positions.return_value = [mock_pos] * num_positions

        mock_order = MagicMock(spec=Order)
        mock_order.asset_class = AlpacaAssetClass.CRYPTO
        mock_order.side = OrderSide.BUY
        mock_client.get_orders.return_value = [mock_order] * num_orders

        # Act
        result = risk_engine.check_sector_limit(CRYPTO)

        # Assert
        assert (
            result.passed == expected_passed
        ), f"Expected passed == {expected_passed} with {num_positions} positions and {num_orders} orders, got {result.passed}"
        if not expected_passed:
            assert (
                "Max CRYPTO positions reached" in result.reason
            ), f'Expected "Max CRYPTO positions reached" in reason, got "{result.reason}"'

    def test_daily_drawdown_fail(self, risk_engine, mock_client):
        """Verify daily drawdown limit hit."""
        # Arrange
        # Equity 9000, Last 10000 -> 10% Drop. Max is 5%
        mock_client.get_account.return_value.equity = "9000.00"
        mock_client.get_account.return_value.last_equity = "10000.00"

        # Act
        result = risk_engine.check_daily_drawdown()

        # Assert
        assert (
            result.passed is False
        ), f"Expected result.passed to be False, got {result.passed}"
        assert (
            "Daily Drawdown Limit Hit" in result.reason
        ), 'Assertion condition not met: "Daily Drawdown Limit Hit" in result.reason'

    def test_check_duplicate_symbol_fail(self, risk_engine, mock_repo):
        """Verify duplicate symbol check fails when position already exists."""
        # Arrange
        # Position exists for BTC/USD
        from crypto_signals.domain.schemas import Position, Signal

        pos = MagicMock(spec=Position)
        pos.symbol = "BTC/USD"
        pos.position_id = "pos_1"
        mock_repo.get_open_positions.return_value = [pos]

        # Signal for SAME symbol
        signal = MagicMock(spec=Signal)
        signal.symbol = "BTC/USD"

        # Act
        result = risk_engine.check_duplicate_symbol(signal)

        # Assert
        assert (
            result.passed is False
        ), f"Expected result.passed to be False, got {result.passed}"
        assert (
            "Duplicate Position" in result.reason
        ), 'Assertion condition not met: "Duplicate Position" in result.reason'
