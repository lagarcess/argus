"""Tests for micro-cap safeguards and edge cases (Issue #136)."""

from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.domain.schemas import AssetClass, OrderSide
from crypto_signals.engine.execution import ExecutionEngine

from tests.factories import SignalFactory


@pytest.fixture
def mock_settings():
    """Fixture for mocking settings."""
    mock = MagicMock()
    mock.is_paper_trading = True
    mock.ENABLE_EXECUTION = True
    mock.RISK_PER_TRADE = 100.0
    mock.ENVIRONMENT = "PROD"
    mock.TTL_DAYS_POSITION = 90
    mock.MAX_CRYPTO_POSITION_QTY = 1_000_000.0
    mock.MAX_EQUITY_POSITION_QTY = 10_000.0
    return mock


@pytest.fixture
def mock_trading_client():
    """Fixture for mocking TradingClient."""
    return MagicMock()


@pytest.fixture
def execution_engine(mock_settings, mock_trading_client):
    """Create an ExecutionEngine with mocked dependencies."""
    with (
        patch("crypto_signals.engine.execution.get_settings", return_value=mock_settings),
        patch("crypto_signals.engine.execution.RiskEngine") as MockRiskEngine,
    ):
        mock_risk_instance = MockRiskEngine.return_value
        from crypto_signals.engine.risk import RiskCheckResult

        mock_risk_instance.validate_signal.return_value = RiskCheckResult(passed=True)

        mock_repo = MagicMock()
        engine = ExecutionEngine(trading_client=mock_trading_client, repository=mock_repo)
        yield engine


class TestMicroCapEdgeCases:
    """Test negative stop-loss scenarios for low-priced assets."""

    def test_quantity_calculation_with_tiny_stop_loss(
        self, execution_engine, mock_trading_client
    ):
        """Ensure qty doesn't explode when stop is at SAFE_STOP_VAL."""
        # Arrange: Signal with micro-cap params (very tight stop)
        signal = SignalFactory.build(
            signal_id="micro-cap-test",
            strategy_id="TEST",
            symbol="PEPE/USD",
            asset_class=AssetClass.CRYPTO,
            entry_price=0.00001000,
            pattern_name="ELLIOTT_WAVE_135",
            # suggested_stop very close to entry
            suggested_stop=0.00000999,
            take_profit_1=0.00001200,
            take_profit_2=0.00001500,
            side=OrderSide.BUY,
        )

        # Risk per share = 10.00001000 - 0.00000999 = 0.00000001
        # Risk per trade = 100
        # Qty = 100 / 0.00000001 = 10,000,000,000
        # This should trigger the MAX_POSITION_SIZE guard (1,000,000)

        # Act
        qty = execution_engine._calculate_qty(signal)

        # Assert
        assert qty == 1_000_000, f"Expected capped qty 1,000,000 but got {qty}"
