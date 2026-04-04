"""Tests for PR Gap Closure: Invalidation Path & Price Patching."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.domain.schemas import (
    TradeStatus,
)
from crypto_signals.engine.execution import ExecutionEngine

from tests.factories import PositionFactory


@pytest.fixture
def mock_settings():
    """Fixture for mocking settings."""
    mock = MagicMock()
    mock.is_paper_trading = True
    mock.ENABLE_EXECUTION = True
    mock.RISK_PER_TRADE = 100.0
    mock.ENVIRONMENT = "PROD"
    mock.TTL_DAYS_POSITION = 90
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


class TestInvalidationPath:
    def test_sl_exit_captures_exit_order_id(self, execution_engine, mock_trading_client):
        """Verify exit_order_id is set when Position closes via Stop Loss."""
        # Arrange
        mock_parent = MagicMock()
        mock_parent.status = "filled"
        mock_parent.filled_at = None
        mock_parent.filled_avg_price = None
        mock_parent.legs = []  # Assuming legs processed previously or irrelevant for this specific sync check

        mock_tp_order = MagicMock()
        mock_tp_order.status = "new"

        mock_sl_order = MagicMock()
        mock_sl_order.status = "filled"
        mock_sl_order.id = "sl-order-uuid-123"
        mock_sl_order.filled_avg_price = "48000.0"
        mock_sl_order.filled_at = datetime(2025, 1, 15, 16, 0, 0, tzinfo=timezone.utc)

        def side_effect(order_id):
            if order_id == "parent-id":
                return mock_parent
            elif order_id == "tp-order-id":
                return mock_tp_order
            elif order_id == "sl-order-id":
                return mock_sl_order
            return None

        mock_trading_client.get_order_by_id.side_effect = side_effect

        position = PositionFactory.build(
            position_id="test-pos-sl-exit",
            signal_id="test-signal-exit",
            alpaca_order_id="parent-id",
            tp_order_id="tp-order-id",
            sl_order_id="sl-order-id",
            qty=0.05,
        )

        # Act
        updated = execution_engine.sync_position_status(position)

        # Assert
        assert (
            updated.status == TradeStatus.CLOSED
        ), f"Expected updated.status == TradeStatus.CLOSED, got {updated.status}"
        # This is the Critical Gap: exit_order_id MUST be set to the SL order ID
        assert (
            updated.exit_order_id == "sl-order-uuid-123"
        ), 'Expected updated.exit_order_id == "sl-order-uuid-123"'

    def test_tp_exit_captures_exit_order_id(self, execution_engine, mock_trading_client):
        """Verify exit_order_id is set when Position closes via Take Profit."""
        # Arrange
        mock_parent = MagicMock()
        mock_parent.status = "filled"
        mock_parent.legs = []

        mock_tp_order = MagicMock()
        mock_tp_order.status = "filled"
        mock_tp_order.id = "tp-order-uuid-456"
        mock_tp_order.filled_avg_price = "55000.0"
        mock_tp_order.filled_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        def side_effect(order_id):
            if order_id == "parent-id":
                return mock_parent
            elif order_id == "tp-order-id":
                return mock_tp_order
            return None

        mock_trading_client.get_order_by_id.side_effect = side_effect

        position = PositionFactory.build(
            position_id="test-pos-tp-exit",
            signal_id="test-signal-exit-tp",
            alpaca_order_id="parent-id",
            tp_order_id="tp-order-id",
            sl_order_id="sl-order-id",
            qty=0.05,
        )

        # Act
        updated = execution_engine.sync_position_status(position)

        # Assert
        assert (
            updated.status == TradeStatus.CLOSED
        ), f"Expected updated.status == TradeStatus.CLOSED, got {updated.status}"
        # This is the Critical Gap: exit_order_id MUST be set to the TP order ID
        assert (
            updated.exit_order_id == "tp-order-uuid-456"
        ), 'Expected updated.exit_order_id == "tp-order-uuid-456"'
