"""Unit tests for the StateReconciler logic (migrated from ExecutionEngine)."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from alpaca.trading.models import Order
from crypto_signals.domain.schemas import (
    ExitReason,
    Position,
    SignalStatus,
    TradeStatus,
)
from crypto_signals.engine.reconciler import StateReconciler
from crypto_signals.engine.reconciler_notifications import ReconcilerNotificationService

from tests.factories import PositionFactory


@pytest.fixture(autouse=True)
def block_real_signal_repo(monkeypatch):
    """Prevent any unmocked StateReconciler from hitting real Firestore."""
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = None
    monkeypatch.setattr(
        "crypto_signals.engine.reconciler.SignalRepository",
        lambda *args, **kwargs: mock_repo,
    )


@pytest.fixture
def mock_alpaca():
    return MagicMock()


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_discord():
    return MagicMock()


@pytest.fixture
def mock_notification_service(mock_discord):
    return ReconcilerNotificationService(mock_discord)


@pytest.fixture
def mock_signal_repo():
    return MagicMock()


@pytest.fixture
def reconciler(mock_alpaca, mock_repo, mock_notification_service, mock_signal_repo):
    return StateReconciler(
        alpaca_client=mock_alpaca,
        position_repo=mock_repo,
        notification_service=mock_notification_service,
        signal_repo=mock_signal_repo,
    )


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


class TestHandleManualExitVerification:
    """Tests for the handle_manual_exit_verification method in StateReconciler."""

    def test_verify_manual_exit_success(
        self, reconciler, mock_alpaca, sample_position, mock_discord
    ):
        """Verify that a filled sell order marks the position as CLOSED/MANUAL_EXIT."""
        # Arrange get_orders to return a FILLED SELL order
        mock_sell_order = MagicMock(spec=Order)
        mock_sell_order.id = "manual-sell-order-123"
        mock_sell_order.status = "filled"
        mock_sell_order.side = "sell"
        mock_sell_order.filled_avg_price = "55000.0"
        mock_sell_order.filled_at = datetime(2025, 1, 16, 12, 0, 0, tzinfo=timezone.utc)

        mock_alpaca.get_orders.return_value = [mock_sell_order]

        # Act
        result = reconciler.handle_manual_exit_verification(sample_position)

        # Assert
        assert isinstance(
            result, Position
        ), f"Expected result to be instance of Position, got {type(result).__name__}"
        assert (
            sample_position.status == TradeStatus.CLOSED
        ), f"Expected sample_position.status == TradeStatus.CLOSED, got {sample_position.status}"
        assert (
            sample_position.exit_reason == ExitReason.MANUAL_EXIT
        ), f"Expected sample_position.exit_reason == ExitReason.MANUAL_EXIT, got {sample_position.exit_reason}"
        assert (
            sample_position.exit_fill_price == 55000.0
        ), f"Expected sample_position.exit_fill_price == 55000.0, got {sample_position.exit_fill_price}"
        assert (
            sample_position.exit_order_id == "manual-sell-order-123"
        ), 'Expected sample_position.exit_order_id == "manual-sell-order-123"'

        # Assert Discord notification sent
        mock_discord.send_message.assert_called_once()
        assert (
            "MANUAL EXIT DETECTED" in mock_discord.send_message.call_args[0][0]
        ), 'Assertion condition not met: "MANUAL EXIT DETECTED" in mock_discord.send_message.call_args[0][0]'

    def test_verify_manual_exit_failed_no_orders(
        self, reconciler, mock_alpaca, sample_position
    ):
        """Verify that if no orders are found, it returns False and keeps position OPEN."""
        # Arrange get_orders to return empty list
        mock_alpaca.get_orders.return_value = []

        # Act
        result = reconciler.handle_manual_exit_verification(sample_position)

        # Assert
        assert result is None, f"result should be None, got {result}"
        assert (
            sample_position.status == TradeStatus.OPEN
        ), f"Expected sample_position.status == TradeStatus.OPEN, got {sample_position.status}"

    def test_verify_manual_exit_ignores_tp_sl_legs(
        self, reconciler, mock_alpaca, sample_position
    ):
        """Verify that known TP/SL legs are ignored in the manual exit search."""
        # 1. Return the TP order as the only "recent filled order"
        mock_tp_order = MagicMock(spec=Order)
        mock_tp_order.id = sample_position.tp_order_id  # Matches known TP
        mock_tp_order.status = "filled"

        mock_alpaca.get_orders.return_value = [mock_tp_order]

        # Act
        result = reconciler.handle_manual_exit_verification(sample_position)

        # Assert
        assert result is None, f"result should be None, got {result}"
        assert (
            sample_position.status == TradeStatus.OPEN
        ), f"Expected sample_position.status == TradeStatus.OPEN, got {sample_position.status}"


class TestSignalStatusHealing:
    """Tests for the _heal_signal_statuses method in StateReconciler."""

    def test_heal_signal_status_success(self, reconciler, mock_signal_repo):
        """
        Verify that StateReconciler heals WAITING signals to ACTIVE if an OPEN position exists.
        """
        from tests.factories import SignalFactory

        # 1. Setup an OPEN position with a WAITING signal
        signal_id = "waiting_signal_id"
        open_position = PositionFactory.build(
            signal_id=signal_id, symbol="BTC/USD", status=TradeStatus.OPEN
        )

        waiting_signal = SignalFactory.build(
            signal_id=signal_id, symbol="BTC/USD", status=SignalStatus.WAITING
        )

        # 2. Configure mock signal repo
        mock_signal_repo.get_by_id.return_value = waiting_signal
        mock_signal_repo.update_signal_atomic.return_value = True

        # 3. Execute Healing (directly or via reconcile)
        healed_count, errors = reconciler._heal_signal_statuses([open_position])

        # 4. Verification
        assert healed_count == 1
        assert len(errors) == 0
        mock_signal_repo.update_signal_atomic.assert_called_with(
            signal_id, {"status": SignalStatus.ACTIVE.value}
        )
