"""Unit tests for the ExecutionEngine position sync logic (Issue #139)."""

from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.domain.schemas import (
    ExitReason,
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
def mock_reconciler():
    """Fixture for mocking StateReconciler."""
    return MagicMock()


@pytest.fixture
def execution_engine(mock_settings, mock_trading_client, mock_reconciler):
    """Create an ExecutionEngine with mocked dependencies."""
    with (
        patch("crypto_signals.engine.execution.get_settings", return_value=mock_settings),
        patch("crypto_signals.engine.execution.RiskEngine"),
    ):
        mock_repo = MagicMock()
        engine = ExecutionEngine(
            trading_client=mock_trading_client,
            repository=mock_repo,
            reconciler=mock_reconciler,
        )
        yield engine


@pytest.fixture
def sample_position():
    """Create a sample OPEN position."""
    return PositionFactory.build(
        position_id="test-pos-sync-1",
        signal_id="test-signal-sync-1",
        alpaca_order_id="entry-order-1",
        tp_order_id="tp-order-1",
        sl_order_id="sl-order-1",
        qty=0.05,
    )


class TestSyncPositionStatusIssue139:
    """Tests for the specific fix in Issue #139 regarding Exit Gaps."""

    def test_sync_delegates_to_reconciler_if_missing_from_alpaca(
        self, execution_engine, sample_position, mock_trading_client, mock_reconciler
    ):
        """
        Verify that if get_open_position fails (404), ExecutionEngine delegats to
        the reconciler for verification.
        """
        # Arrange
        mock_trading_client.get_open_position.side_effect = Exception(
            "position not found (404)"
        )

        # Act
        execution_engine.sync_position_status(sample_position)

        # Assert
        mock_reconciler.handle_manual_exit_verification.assert_called_once_with(
            sample_position
        )

    def test_sync_keeps_open_if_no_reconciler_provided(
        self, execution_engine, sample_position, mock_trading_client
    ):
        """
        Verify safety fallback: if no reconciler is provided, position stays OPEN.
        """
        # Arrange
        mock_trading_client.get_open_position.side_effect = Exception("404")

        from crypto_signals.engine.execution import ExecutionEngine

        standalone_engine = ExecutionEngine(
            trading_client=mock_trading_client,
            repository=MagicMock(),  # Fix: Inject mock repo to avoid real Firestore init
        )

        # Act
        updated_pos = standalone_engine.sync_position_status(sample_position)

        # Assert
        assert (
            updated_pos.status == TradeStatus.OPEN
        ), f"Expected updated_pos.status == TradeStatus.OPEN, got {updated_pos.status}"

    def test_sync_captures_exit_order_id_on_sl(
        self, execution_engine, sample_position, mock_trading_client
    ):
        """
        Verify that sync_position_status captures exit_order_id when SL is hit.
        """
        # Arrange
        # 1. Mock parent order details
        parent_order = MagicMock()
        parent_order.id = sample_position.alpaca_order_id
        parent_order.status = "filled"
        parent_order.legs = [
            MagicMock(id="tp-order-1", order_type="limit"),
            MagicMock(id="sl-order-1", order_type="stop"),
        ]

        # 2. Mock SL order details as filled
        sl_order = MagicMock()
        sl_order.id = "sl-order-1"
        sl_order.status = "filled"
        sl_order.filled_avg_price = 45000.0
        sl_order.filled_at = "2024-01-01T12:00:00Z"

        # Configure mock_trading_client to return these orders
        def get_order_side_effect(order_id):
            if order_id == sample_position.alpaca_order_id:
                return parent_order
            if order_id == sample_position.sl_order_id:
                return sl_order
            return None

        mock_trading_client.get_order_by_id.side_effect = get_order_side_effect

        # Act
        updated_pos = execution_engine.sync_position_status(sample_position)

        # Assert
        assert updated_pos.status == TradeStatus.CLOSED
        assert updated_pos.exit_reason == ExitReason.STOP_LOSS
        assert updated_pos.exit_order_id == "sl-order-1"
