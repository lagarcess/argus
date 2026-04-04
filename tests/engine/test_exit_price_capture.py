"""
Unit tests for exit price capture functionality (Issue #141).

Tests cover:
- Emergency close with retry budget
- Scale-out with weighted average calculation
- Deferred backfill via sync_position_status
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from alpaca.trading.models import Order, OrderStatus
from crypto_signals.domain.schemas import (
    TradeType,
)
from crypto_signals.engine.execution import ExecutionEngine

from tests.factories import PositionFactory


class TestEmergencyCloseRetryBudget:
    """Test emergency close with retry budget for volatile markets."""

    def test_immediate_fill_capture(self, mock_trading_client):
        """Test emergency close with immediate fill price."""
        # Arrange
        engine = ExecutionEngine(
            trading_client=mock_trading_client, repository=MagicMock()
        )
        position = PositionFactory.build(
            position_id="test-pos-1",
            symbol="BTC/USD",
            signal_id="test-signal-1",
            qty=0.1,
            trade_type=TradeType.EXECUTED.value,
        )

        # Mock order with immediate fill
        mock_order = MagicMock(spec=Order)
        mock_order.id = "order-123"
        mock_order.filled_avg_price = 51000.0
        mock_order.filled_at = datetime.now(timezone.utc)
        mock_order.status = OrderStatus.FILLED

        mock_trading_client.submit_order.return_value = mock_order

        # Act
        with patch("crypto_signals.engine.execution.get_settings") as mock_settings:
            mock_settings.return_value.ENVIRONMENT = "PROD"
            result = engine.close_position_emergency(position)

        # Assert
        assert result is True, f"Expected result to be True, got {result}"
        assert (
            position.exit_order_id == "order-123"
        ), 'Expected position.exit_order_id == "order-123"'
        assert (
            position.exit_fill_price == 51000.0
        ), f"Expected position.exit_fill_price == 51000.0, got {position.exit_fill_price}"
        assert (
            position.exit_time == mock_order.filled_at
        ), f"Expected position.exit_time == mock_order.filled_at, got {position.exit_time}"
        assert (
            position.awaiting_backfill is False
        ), f"Expected position.awaiting_backfill to be False, got {position.awaiting_backfill}"

    def test_retry_budget_success(self, mock_trading_client):
        """Test emergency close with retry budget (fills on retry 2)."""
        # Arrange
        engine = ExecutionEngine(
            trading_client=mock_trading_client, repository=MagicMock()
        )
        position = PositionFactory.build(
            position_id="test-pos-2",
            symbol="ETH/USD",
            signal_id="test-signal-2",
            entry_fill_price=3000.0,
            current_stop_loss=2900.0,
            qty=1.0,
            trade_type=TradeType.EXECUTED.value,
        )

        # Mock order with no immediate fill
        mock_order = MagicMock(spec=Order)
        mock_order.id = "order-456"
        mock_order.filled_avg_price = None  # Not filled immediately
        mock_order.filled_at = None
        mock_order.status = OrderStatus.ACCEPTED

        mock_trading_client.submit_order.return_value = mock_order

        # Mock get_order_details for retries
        # Retry 1: Still not filled
        mock_order_retry1 = MagicMock(spec=Order)
        mock_order_retry1.filled_avg_price = None
        mock_order_retry1.status = OrderStatus.ACCEPTED

        # Retry 2: Filled!
        mock_order_retry2 = MagicMock(spec=Order)
        mock_order_retry2.filled_avg_price = 3100.0
        mock_order_retry2.filled_at = datetime.now(timezone.utc)
        mock_order_retry2.status = OrderStatus.FILLED

        engine.get_order_details = MagicMock(
            side_effect=[mock_order_retry1, mock_order_retry2]
        )

        # Act
        # Act
        with patch("crypto_signals.engine.execution.get_settings") as mock_settings:
            mock_settings.return_value.ENVIRONMENT = "PROD"
            with patch("time.sleep"):  # Skip actual sleep
                result = engine.close_position_emergency(position)

        # Assert
        assert result is True, f"Expected result to be True, got {result}"
        assert (
            position.exit_order_id == "order-456"
        ), 'Expected position.exit_order_id == "order-456"'
        assert (
            position.exit_fill_price == 3100.0
        ), f"Expected position.exit_fill_price == 3100.0, got {position.exit_fill_price}"
        assert (
            position.exit_time == mock_order_retry2.filled_at
        ), f"Expected position.exit_time == mock_order_retry2.filled_at, got {position.exit_time}"
        assert (
            position.awaiting_backfill is False
        ), f"Expected position.awaiting_backfill to be False, got {position.awaiting_backfill}"
        assert (
            engine.get_order_details.call_count == 2
        ), f"Stopped after retry 2: expected 2, got {engine.get_order_details.call_count}"

    def test_retry_budget_exhausted(self, mock_trading_client):
        """Test emergency close with retry budget exhausted (awaiting backfill)."""
        # Arrange
        engine = ExecutionEngine(
            trading_client=mock_trading_client, repository=MagicMock()
        )
        position = PositionFactory.build(
            position_id="test-pos-3",
            symbol="SOL/USD",
            signal_id="test-signal-3",
            entry_fill_price=100.0,
            current_stop_loss=95.0,
            qty=10.0,
            trade_type=TradeType.EXECUTED.value,
        )

        # Mock order with no immediate fill
        mock_order = MagicMock(spec=Order)
        mock_order.id = "order-789"
        mock_order.filled_avg_price = None
        mock_order.filled_at = None
        mock_order.status = OrderStatus.ACCEPTED

        mock_trading_client.submit_order.return_value = mock_order

        # Mock get_order_details - never fills
        mock_order_retry = MagicMock(spec=Order)
        mock_order_retry.filled_avg_price = None
        mock_order_retry.status = OrderStatus.ACCEPTED

        engine.get_order_details = MagicMock(return_value=mock_order_retry)

        # Act
        # Act
        with patch("crypto_signals.engine.execution.get_settings") as mock_settings:
            mock_settings.return_value.ENVIRONMENT = "PROD"
            with patch("time.sleep"):  # Skip actual sleep
                result = engine.close_position_emergency(position)

        # Assert
        assert (
            result is True
        ), f"Order submitted successfully: expected True, got {result}"
        assert (
            position.exit_order_id == "order-789"
        ), 'Expected position.exit_order_id == "order-789"'
        assert (
            position.exit_fill_price is None
        ), f"Not filled yet: expected None, got {position.exit_fill_price}"
        assert (
            position.awaiting_backfill is True
        ), f"Marked for backfill: expected True, got {position.awaiting_backfill}"
        assert (
            engine.get_order_details.call_count == 3
        ), f"All 3 retries exhausted: expected 3, got {engine.get_order_details.call_count}"


class TestRetryFillPriceHelper:
    """Test the _retry_fill_price_capture helper method."""

    def test_retry_helper_immediate_success(self, mock_trading_client):
        """Test helper returns fill price on first retry."""
        # Arrange
        engine = ExecutionEngine(
            trading_client=mock_trading_client, repository=MagicMock()
        )

        mock_order = MagicMock(spec=Order)
        mock_order.filled_avg_price = 50000.0
        mock_order.filled_at = datetime.now(timezone.utc)

        engine.get_order_details = MagicMock(return_value=mock_order)

        # Act
        with patch("time.sleep"):
            result = engine._retry_fill_price_capture("order-123", "test-pos-1")

        # Assert
        assert result is not None, "result should not be None"
        fill_price, filled_at = result
        assert fill_price == 50000.0, f"Expected fill_price == 50000.0, got {fill_price}"
        assert (
            filled_at == mock_order.filled_at
        ), f"Expected filled_at == mock_order.filled_at, got {filled_at}"
        assert (
            engine.get_order_details.call_count == 1
        ), f"Expected engine.get_order_details.call_count == 1, got {engine.get_order_details.call_count}"

    def test_retry_helper_exhausted(self, mock_trading_client):
        """Test helper returns None when retries exhausted."""
        # Arrange
        engine = ExecutionEngine(
            trading_client=mock_trading_client, repository=MagicMock()
        )

        mock_order = MagicMock(spec=Order)
        mock_order.filled_avg_price = None

        engine.get_order_details = MagicMock(return_value=mock_order)

        # Act
        with patch("time.sleep"):
            result = engine._retry_fill_price_capture(
                "order-456", "test-pos-2", max_retries=2
            )

        # Assert
        assert result is None, f"result should be None, got {result}"
        assert (
            engine.get_order_details.call_count == 2
        ), f"Expected engine.get_order_details.call_count == 2, got {engine.get_order_details.call_count}"


class TestScaleOutWeightedAverage:
    """Test scale-out with weighted average calculation."""

    def test_single_scale_out(self, mock_trading_client):
        """Test single scale-out (no weighted average needed)."""
        # Arrange
        engine = ExecutionEngine(
            trading_client=mock_trading_client, repository=MagicMock()
        )
        position = PositionFactory.build(
            position_id="test-pos-5",
            symbol="BTC/USD",
            signal_id="test-signal-5",
            qty=1.0,
            trade_type=TradeType.EXECUTED.value,
        )

        # Mock order with immediate fill
        mock_order = MagicMock(spec=Order)
        mock_order.id = "scale-order-1"
        mock_order.filled_avg_price = 52000.0
        mock_order.status = OrderStatus.FILLED

        mock_trading_client.submit_order.return_value = mock_order

        # Act
        # Act
        with patch("crypto_signals.engine.execution.get_settings") as mock_settings:
            mock_settings.return_value.ENVIRONMENT = "PROD"
            result = engine.scale_out_position(position, scale_pct=0.5)

        # Assert
        assert result is True, f"Expected result to be True, got {result}"
        assert (
            position.scaled_out_qty == 0.5
        ), f"Expected position.scaled_out_qty == 0.5, got {position.scaled_out_qty}"
        assert (
            position.scaled_out_price == 52000.0
        ), f"No averaging needed: expected 52000.0, got {position.scaled_out_price}"
        assert (
            position.exit_fill_price == 52000.0
        ), f"Set for archival: expected 52000.0, got {position.exit_fill_price}"
        assert position.qty == 0.5, f"Remaining: expected 0.5, got {position.qty}"
        assert (
            len(position.scaled_out_prices) == 1
        ), f"Expected len(position.scaled_out_prices) == 1, got {len(position.scaled_out_prices)}"
        assert (
            position.scaled_out_prices[0]["price"] == 52000.0
        ), 'Expected position.scaled_out_prices[0]["price"] == 52000.0'
        assert (
            position.scaled_out_prices[0]["order_id"] == "scale-order-1"
        ), 'Expected position.scaled_out_prices[0]["order_id"] == "scale-order-1"'

    def test_multi_stage_weighted_average(self, mock_trading_client):
        """Test multi-stage scale-out with weighted average (TP1 + TP2)."""
        # Arrange
        engine = ExecutionEngine(
            trading_client=mock_trading_client, repository=MagicMock()
        )
        position = PositionFactory.build(
            position_id="test-pos-6",
            symbol="ETH/USD",
            signal_id="test-signal-6",
            entry_fill_price=3000.0,
            current_stop_loss=2900.0,
            qty=1.0,
            trade_type=TradeType.EXECUTED.value,
        )

        # Mock TP1 scale-out @ $3200
        mock_order_tp1 = MagicMock(spec=Order)
        mock_order_tp1.id = "tp1-order"
        mock_order_tp1.filled_avg_price = 3200.0
        mock_order_tp1.status = OrderStatus.FILLED

        mock_trading_client.submit_order.return_value = mock_order_tp1

        # Act: TP1 (50% @ $3200)
        # Act: TP1 (50% @ $3200)
        with patch("crypto_signals.engine.execution.get_settings") as mock_settings:
            mock_settings.return_value.ENVIRONMENT = "PROD"
            result_tp1 = engine.scale_out_position(position, scale_pct=0.5)

        # Assert TP1
        assert result_tp1 is True, f"Expected result_tp1 to be True, got {result_tp1}"
        assert (
            position.scaled_out_qty == 0.5
        ), f"Expected position.scaled_out_qty == 0.5, got {position.scaled_out_qty}"
        assert (
            position.scaled_out_price == 3200.0
        ), f"Expected position.scaled_out_price == 3200.0, got {position.scaled_out_price}"
        assert (
            position.exit_fill_price == 3200.0
        ), f"Expected position.exit_fill_price == 3200.0, got {position.exit_fill_price}"
        assert position.qty == 0.5, f"Expected position.qty == 0.5, got {position.qty}"

        # Arrange TP2
        # Mock TP2 scale-out @ $3400
        mock_order_tp2 = MagicMock(spec=Order)
        mock_order_tp2.id = "tp2-order"
        mock_order_tp2.filled_avg_price = 3400.0
        mock_order_tp2.status = OrderStatus.FILLED

        mock_trading_client.submit_order.return_value = mock_order_tp2

        # Act: TP2 (50% of remaining = 0.25 total @ $3400)
        # Act: TP2 (50% of remaining = 0.25 total @ $3400)
        with patch("crypto_signals.engine.execution.get_settings") as mock_settings:
            mock_settings.return_value.ENVIRONMENT = "PROD"
            result_tp2 = engine.scale_out_position(position, scale_pct=0.5)

        # Assert TP2 - Weighted Average
        assert result_tp2 is True, f"Expected result_tp2 to be True, got {result_tp2}"
        assert (
            position.scaled_out_qty == 0.75
        ), f"0.5 + 0.25: expected 0.75, got {position.scaled_out_qty}"
        # Weighted avg: (0.5 * 3200 + 0.25 * 3400) / 0.75 = (1600 + 850) / 0.75 = 3266.67
        assert (
            position.scaled_out_price == pytest.approx(3266.67, rel=0.01)
        ), f"Expected position.scaled_out_price == pytest.approx(3266.67, rel=0.01), got {position.scaled_out_price}"
        assert (
            position.exit_fill_price == pytest.approx(3266.67, rel=0.01)
        ), f"Expected position.exit_fill_price == pytest.approx(3266.67, rel=0.01), got {position.exit_fill_price}"
        assert position.qty == 0.25, f"Remaining: expected 0.25, got {position.qty}"
        assert (
            len(position.scaled_out_prices) == 2
        ), f"Expected len(position.scaled_out_prices) == 2, got {len(position.scaled_out_prices)}"

    def test_scale_out_retry_budget(self, mock_trading_client):
        """Test scale-out with retry budget."""
        # Arrange
        engine = ExecutionEngine(
            trading_client=mock_trading_client, repository=MagicMock()
        )
        position = PositionFactory.build(
            position_id="test-pos-7",
            symbol="SOL/USD",
            signal_id="test-signal-7",
            entry_fill_price=100.0,
            current_stop_loss=95.0,
            qty=10.0,
            trade_type=TradeType.EXECUTED.value,
        )

        # Mock order with no immediate fill
        mock_order = MagicMock(spec=Order)
        mock_order.id = "scale-retry-order"
        mock_order.filled_avg_price = None
        mock_order.status = OrderStatus.ACCEPTED

        mock_trading_client.submit_order.return_value = mock_order

        # Mock get_order_details - fills on retry 1
        mock_order_retry = MagicMock(spec=Order)
        mock_order_retry.filled_avg_price = 105.0
        mock_order_retry.status = OrderStatus.FILLED
        mock_order_retry.filled_at = datetime.now(timezone.utc)

        engine.get_order_details = MagicMock(return_value=mock_order_retry)

        # Act
        # Act
        with patch("crypto_signals.engine.execution.get_settings") as mock_settings:
            mock_settings.return_value.ENVIRONMENT = "PROD"
            with patch("time.sleep"):  # Skip actual sleep
                result = engine.scale_out_position(position, scale_pct=0.5)

        # Assert
        assert result is True, f"Expected result to be True, got {result}"
        assert (
            position.scaled_out_price == 105.0
        ), f"Expected position.scaled_out_price == 105.0, got {position.scaled_out_price}"
        assert (
            position.exit_fill_price == 105.0
        ), f"Expected position.exit_fill_price == 105.0, got {position.exit_fill_price}"
        assert (
            position.awaiting_backfill is False
        ), f"Expected position.awaiting_backfill to be False, got {position.awaiting_backfill}"
        assert (
            engine.get_order_details.call_count == 1
        ), f"Stopped after retry 1: expected 1, got {engine.get_order_details.call_count}"


@pytest.fixture
def mock_trading_client():
    """Mock Alpaca TradingClient."""
    return MagicMock()
