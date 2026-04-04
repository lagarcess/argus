from unittest.mock import MagicMock

import pytest
from crypto_signals.domain.schemas import (
    TradeType,
)
from crypto_signals.engine.reconciler import StateReconciler
from crypto_signals.engine.reconciler_notifications import ReconcilerNotificationService
from crypto_signals.repository.firestore import PositionRepository

from tests.factories import PositionFactory


@pytest.fixture
def mock_notification_service(mock_discord_client):
    return ReconcilerNotificationService(mock_discord_client)


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
def mock_trading_client():
    return MagicMock()


@pytest.fixture
def mock_position_repo():
    return MagicMock(spec=PositionRepository)


@pytest.fixture
def mock_discord_client():
    return MagicMock()


@pytest.fixture
def mock_settings():
    mock = MagicMock()
    mock.ENVIRONMENT = "PROD"
    return mock


@pytest.fixture
def theoretical_position():
    return PositionFactory.build(
        position_id="theo-123",
        account_id="theoretical",
        signal_id="sig-123",
        alpaca_order_id="theo-order-1",
        qty=0.01,
        trade_type=TradeType.THEORETICAL.value,  # Key field
    )


def test_reconcile_ignores_theoretical_positions(
    mock_trading_client,
    mock_position_repo,
    mock_notification_service,
    mock_settings,
    theoretical_position,
):
    """Verify that OPEN theoretical positions are NOT flagged as zombies when missing from Alpaca."""
    # Alpaca has NO positions (empty)
    mock_trading_client.get_all_positions.return_value = []

    # Firestore has one OPEN theoretical position
    mock_position_repo.get_open_positions.return_value = [theoretical_position]

    reconciler = StateReconciler(
        alpaca_client=mock_trading_client,
        position_repo=mock_position_repo,
        notification_service=mock_notification_service,
        settings=mock_settings,
    )

    report = reconciler.reconcile()

    # Should be NO zombies because theoretical trades are filtered out
    assert (
        len(report.zombies) == 0
    ), f"Expected len(report.zombies) == 0, got {len(report.zombies)}"
    assert (
        "BTC/USD" not in report.zombies
    ), 'Assertion condition not met: "BTC/USD" not in report.zombies'

    # Should be NO orphans
    assert (
        len(report.orphans) == 0
    ), f"Expected len(report.orphans) == 0, got {len(report.orphans)}"


def test_reconcile_detects_normal_zombies(
    mock_trading_client,
    mock_position_repo,
    mock_notification_service,
    mock_settings,
    theoretical_position,
):
    """Verify that normal OPEN positions ARE flagged as zombies, even if mixed with theoreticals."""
    # Create a normal executed position
    normal_position = PositionFactory.build(
        position_id="real-123",
        symbol="ETH/USD",
        signal_id="sig-456",
        alpaca_order_id="alpaca-order-1",
        entry_fill_price=2000.0,
        current_stop_loss=1900.0,
        qty=1.0,
        trade_type=TradeType.EXECUTED.value,  # Normal trade
    )

    # Alpaca has NO positions
    mock_trading_client.get_all_positions.return_value = []

    # Firestore has one THEORETICAL and one NORMAL position
    mock_position_repo.get_open_positions.return_value = [
        theoretical_position,
        normal_position,
    ]

    reconciler = StateReconciler(
        alpaca_client=mock_trading_client,
        position_repo=mock_position_repo,
        notification_service=mock_notification_service,
        settings=mock_settings,
    )

    report = reconciler.reconcile()

    # The normal position should be a zombie
    assert (
        len(report.zombies) == 1
    ), f"Expected len(report.zombies) == 1, got {len(report.zombies)}"
    assert (
        "ETH/USD" in report.zombies
    ), 'Assertion condition not met: "ETH/USD" in report.zombies'

    # The theoretical position (BTC/USD) should be ignored
    assert (
        "BTC/USD" not in report.zombies
    ), 'Assertion condition not met: "BTC/USD" not in report.zombies'
