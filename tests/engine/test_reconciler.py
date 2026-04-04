"""Unit tests for the StateReconciler module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.domain.enums import ReconciliationErrors
from crypto_signals.domain.schemas import (
    ExitReason,
    TradeStatus,
    TradeType,
)
from crypto_signals.engine.reconciler import StateReconciler
from crypto_signals.engine.reconciler_notifications import ReconcilerNotificationService
from crypto_signals.repository.firestore import PositionRepository

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
def mock_signal_repo():
    """Fixture for mocking SignalRepository."""
    mock = MagicMock()
    # Default to returning None to avoid healing in basic tests
    mock.get_by_id.return_value = None
    return mock


@pytest.fixture
def mock_trading_client():
    """Fixture for mocking TradingClient."""
    return MagicMock()


@pytest.fixture
def mock_position_repo():
    """Fixture for mocking PositionRepository."""
    return MagicMock(spec=PositionRepository)


@pytest.fixture
def mock_notification_service():
    """Fixture for mocking ReconcilerNotificationService."""
    return MagicMock(spec=ReconcilerNotificationService)


@pytest.fixture
def mock_settings():
    """Fixture for mocking settings."""
    mock = MagicMock()
    mock.ENVIRONMENT = "PROD"
    mock.TTL_DAYS_POSITION = 90
    mock.CRYPTO_SYMBOLS = ["BTC/USD", "ETH/USD"]
    return mock


@pytest.fixture
def sample_open_position():
    """Create a sample OPEN position."""
    return PositionFactory.build(
        position_id="signal-123",
        signal_id="signal-123",
        alpaca_order_id="order-123",
        qty=0.01,
    )


@pytest.fixture
def sample_alpaca_position():
    """Create a sample Alpaca position object."""
    mock_pos = MagicMock()
    # Alpaca uses symbols without slashes for crypto (e.g., BTCUSD)
    mock_pos.symbol = "BTCUSD"
    mock_pos.qty = 0.01
    mock_pos.side = "long"
    return mock_pos


@pytest.fixture
def reconciler(
    mock_trading_client,
    mock_position_repo,
    mock_notification_service,
    mock_settings,
    mock_signal_repo,
):
    """Create a StateReconciler with injected mock dependencies."""
    return StateReconciler(
        alpaca_client=mock_trading_client,
        position_repo=mock_position_repo,
        notification_service=mock_notification_service,
        settings=mock_settings,
        signal_repo=mock_signal_repo,
    )


# ============================================================================
# Test Classes organized by functionality
# ============================================================================


class TestStateReconcilerInitialization:
    """Test StateReconciler initialization and dependency injection."""

    def test_init_stores_dependencies(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """StateReconciler stores injected dependencies."""
        # Act
        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Assert
        assert (
            reconciler.alpaca == mock_trading_client
        ), f"Expected reconciler.alpaca == mock_trading_client, got {reconciler.alpaca}"
        assert (
            reconciler.position_repo == mock_position_repo
        ), f"Expected reconciler.position_repo == mock_position_repo, got {reconciler.position_repo}"
        assert (
            reconciler.notifications == mock_notification_service
        ), f"Expected reconciler.notifications == mock_notification_service, got {reconciler.notifications}"
        assert (
            reconciler.settings == mock_settings
        ), f"Expected reconciler.settings == mock_settings, got {reconciler.settings}"


class TestDetectZombies:
    """Test zombie detection: Firestore OPEN, Alpaca closed."""

    def test_detect_zombies(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
        sample_alpaca_position,
    ):
        """Zombies are detected: Firestore OPEN, Alpaca closed."""
        # Arrange
        # Alpaca has NO position
        mock_trading_client.get_all_positions.return_value = []

        # Firestore has OPEN position
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        # Zombie detected
        assert (
            "BTC/USD" in report.zombies
        ), 'Assertion condition not met: "BTC/USD" in report.zombies'
        assert (
            len(report.zombies) == 1
        ), f"Expected len(report.zombies) == 1, got {len(report.zombies)}"

    def test_race_condition_young_zombie_skipped(
        self,
        mock_trading_client,
        mock_position_repo,
        reconciler,
    ):
        """A position created < 5 mins ago is skipped to prevent race conditions (Issue #244)."""
        # Arrange
        now = datetime.now(timezone.utc)
        pos = PositionFactory.build(
            symbol="BTC/USD",
            position_id="pos-123",
            trade_type="EXECUTED",
            created_at=now - timedelta(seconds=10),  # 10 seconds old
        )

        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = [pos]

        # Act
        reconciler.reconcile(min_age_minutes=5)

        # Assert
        # Young position should NOT be closed
        mock_position_repo.update_position.assert_not_called()

    def test_reconcile_handles_multiple_zombies(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """Reconciliation handles multiple zombies."""
        # Arrange
        # Create two open positions in Firestore
        pos1 = PositionFactory.build(
            symbol="BTC/USD",
            position_id="signal-1",
            trade_type="EXECUTED",
        )

        pos2 = PositionFactory.build(
            symbol="ETH/USD",
            position_id="signal-2",
            trade_type="EXECUTED",
        )

        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = [pos1, pos2]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        assert (
            len(report.zombies) == 2
        ), f"Expected len(report.zombies) == 2, got {len(report.zombies)}"
        assert (
            "BTC/USD" in report.zombies
        ), 'Assertion condition not met: "BTC/USD" in report.zombies'
        assert (
            "ETH/USD" in report.zombies
        ), 'Assertion condition not met: "ETH/USD" in report.zombies'


class TestDetectOrphans:
    """Test orphan detection: Alpaca OPEN, Firestore missing."""

    def test_detect_orphans(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_alpaca_position,
    ):
        """Orphans are detected: Alpaca OPEN, Firestore missing."""
        # Arrange
        # Alpaca has open position
        mock_trading_client.get_all_positions.return_value = [sample_alpaca_position]

        # Firestore has NO position
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        # Orphan detected
        assert (
            "BTC/USD" in report.orphans
        ), 'Assertion condition not met: "BTC/USD" in report.orphans'
        assert (
            len(report.orphans) == 1
        ), f"Expected len(report.orphans) == 1, got {len(report.orphans)}"

    def test_reconcile_handles_multiple_orphans(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """Reconciliation handles multiple orphans."""
        # Arrange
        pos1 = MagicMock()
        pos1.symbol = "BTCUSD"

        pos2 = MagicMock()
        pos2.symbol = "ETHUSD"

        mock_trading_client.get_all_positions.return_value = [pos1, pos2]
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        assert (
            len(report.orphans) == 2
        ), f"Expected len(report.orphans) == 2, got {len(report.orphans)}"
        assert (
            "BTC/USD" in report.orphans
        ), 'Assertion condition not met: "BTC/USD" in report.orphans'
        assert (
            "ETH/USD" in report.orphans
        ), 'Assertion condition not met: "ETH/USD" in report.orphans'

    def test_reconcile_reports_critical_issues(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_alpaca_position,
    ):
        """Orphan positions are reported as critical issues."""
        # Arrange
        mock_trading_client.get_all_positions.return_value = [sample_alpaca_position]
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        assert (
            len(report.critical_issues) > 0
        ), f"Expected len(report.critical_issues) > 0, got {len(report.critical_issues)}"
        expected_error = ReconciliationErrors.ORPHAN_POSITION.format(symbol="BTC/USD")
        assert any(
            expected_error in issue for issue in report.critical_issues
        ), "Expected any(expected_error in issue for issue in report.critical_issues)"


class TestHealingAndAlerts:
    """Test zombie healing and orphan alerts."""

    def test_heal_zombie_marks_closed_externally(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
    ):
        """Healing zombie marks position CLOSED_EXTERNALLY."""
        # Arrange
        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        # Mock verification to succeed so that update_position is called
        # We need to simulate the side effect of updating the position object
        def verify_side_effect(pos):
            pos.status = TradeStatus.CLOSED
            pos.exit_reason = ExitReason.MANUAL_EXIT
            return pos

        with patch.object(
            reconciler, "handle_manual_exit_verification", side_effect=verify_side_effect
        ):
            reconciler.reconcile()

        # Assert
        mock_position_repo.update_position.assert_called()

        # Assert the position was marked CLOSED (reason is now MANUAL_EXIT due to verification)
        called_position = mock_position_repo.update_position.call_args[0][0]
        assert (
            called_position.status == TradeStatus.CLOSED
        ), f"Expected called_position.status == TradeStatus.CLOSED, got {called_position.status}"
        assert (
            called_position.exit_reason == ExitReason.MANUAL_EXIT
        ), f"Expected called_position.exit_reason == ExitReason.MANUAL_EXIT, got {called_position.exit_reason}"

    def test_alert_orphan_sends_discord_message(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_alpaca_position,
    ):
        """Orphan detection sends Discord message."""
        # Arrange
        mock_trading_client.get_all_positions.return_value = [sample_alpaca_position]
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        reconciler.reconcile()

        # Assert
        assert mock_notification_service.notify_orphan.called, f"Expected mock_notification_service.notify_orphan.called to be truthy, got {mock_notification_service.notify_orphan.called}"

    def test_manual_verification_failure_does_not_close(
        self,
        mock_trading_client,
        mock_position_repo,
        reconciler,
    ):
        """If manual exit verification fails, position is NOT closed (Issue #244)."""
        # Arrange
        now = datetime.now(timezone.utc)
        pos = PositionFactory.build(
            symbol="ETH/USD",
            position_id="pos-456",
            trade_type="EXECUTED",
            created_at=now - timedelta(minutes=10),
        )

        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = [pos]

        # Act
        with patch.object(
            reconciler, "handle_manual_exit_verification", return_value=None
        ) as mock_verify:
            report = reconciler.reconcile()

            # Assert
            mock_verify.assert_called_once_with(pos)
            mock_position_repo.update_position.assert_not_called()
            assert (
                len(report.critical_issues) > 0
            ), f"Expected len(report.critical_issues) > 0, got {len(report.critical_issues)}"
            assert (
                "CRITICAL SYNC ISSUE" in report.critical_issues[0]
            ), 'Assertion condition not met: "CRITICAL SYNC ISSUE" in report.critical_issues[0]'

    def test_manual_verification_success_updates_position(
        self,
        mock_trading_client,
        mock_position_repo,
        reconciler,
    ):
        """If manual exit verification succeeds, position IS updated (Issue #244)."""
        # Arrange
        now = datetime.now(timezone.utc)
        pos = PositionFactory.build(
            symbol="ETH/USD",
            position_id="pos-789",
            trade_type="EXECUTED",
            created_at=now - timedelta(minutes=10),
        )

        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = [pos]

        # Act
        with patch.object(
            reconciler, "handle_manual_exit_verification", return_value=pos
        ) as mock_verify:
            reconciler.reconcile()

            # Assert
            mock_verify.assert_called_once_with(pos)
            mock_position_repo.update_position.assert_called_once_with(pos)


class TestReconciliationBehavior:
    """Test reconciliation behavior, reports, and idempotency."""

    def test_reconcile_returns_report(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """reconcile() returns a ReconciliationReport."""
        # Arrange
        # Mock empty positions (no zombies, no orphans)
        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        assert report is not None, "report should not be None"
        assert hasattr(
            report, "zombies"
        ), 'Assertion condition not met: hasattr(report, "zombies")'
        assert hasattr(
            report, "orphans"
        ), 'Assertion condition not met: hasattr(report, "orphans")'
        assert hasattr(
            report, "reconciled_count"
        ), 'Assertion condition not met: hasattr(report, "reconciled_count")'
        assert hasattr(
            report, "timestamp"
        ), 'Assertion condition not met: hasattr(report, "timestamp")'
        assert hasattr(
            report, "duration_seconds"
        ), 'Assertion condition not met: hasattr(report, "duration_seconds")'

    def test_reconcile_idempotent(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
    ):
        """Running reconciliation twice produces consistent results."""
        # Arrange
        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report1 = reconciler.reconcile()
        report2 = reconciler.reconcile()

        # Assert
        assert (
            len(report1.zombies) == len(report2.zombies)
        ), f"Expected len(report1.zombies) == len(report2.zombies), got {len(report1.zombies)}"
        assert (
            len(report1.orphans) == len(report2.orphans)
        ), f"Expected len(report1.orphans) == len(report2.orphans), got {len(report1.orphans)}"

    def test_reconcile_reports_duration(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """Reconciliation report includes execution duration."""
        # Arrange
        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        assert (
            report.duration_seconds >= 0.0
        ), f"Expected report.duration_seconds >= 0.0, got {report.duration_seconds}"
        assert isinstance(
            report.duration_seconds, float
        ), f"Expected report.duration_seconds to be instance of float, got {type(report.duration_seconds).__name__}"


class TestEnvironmentGating:
    """Test environment isolation and gating."""

    def test_reconcile_non_prod_environment(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """Reconciliation respects ENVIRONMENT != PROD."""
        # Arrange
        mock_settings.ENVIRONMENT = "DEV"
        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        reconciler.reconcile()

        # Assert
        mock_trading_client.get_all_positions.assert_not_called()


class TestErrorHandling:
    """Test error handling and resilience."""

    def test_reconcile_error_handling_get_all_positions_fails(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """Reconciliation handles Alpaca API errors gracefully."""
        # Arrange
        mock_trading_client.get_all_positions.side_effect = Exception("API Error")
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        # Should not raise, should return error report
        report = reconciler.reconcile()

        # Assert
        assert (
            len(report.critical_issues) > 0
        ), f"Expected len(report.critical_issues) > 0, got {len(report.critical_issues)}"

    def test_reconcile_error_handling_firestore_fails(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """Reconciliation handles Firestore errors gracefully."""
        # Arrange
        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.side_effect = Exception("DB Error")

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        # Should not raise, should return error report
        report = reconciler.reconcile()

        # Assert
        assert (
            len(report.critical_issues) > 0
        ), f"Expected len(report.critical_issues) > 0, got {len(report.critical_issues)}"


class TestReconcilerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_reconcile_with_empty_symbols(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """Reconciliation handles empty symbol sets gracefully."""
        # Arrange
        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        assert (
            len(report.zombies) == 0
        ), f"Expected len(report.zombies) == 0, got {len(report.zombies)}"
        assert (
            len(report.orphans) == 0
        ), f"Expected len(report.orphans) == 0, got {len(report.orphans)}"
        assert (
            report.reconciled_count == 0
        ), f"Expected report.reconciled_count == 0, got {report.reconciled_count}"

    def test_reconcile_zombie_update_failure_not_blocking(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
    ):
        """Zombie healing failure doesn't block orphan alerts."""
        # Arrange
        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        # Fail on update_position, succeed on other calls
        mock_position_repo.update_position.side_effect = Exception("DB Write Error")

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        # Should still return report with critical issues
        report = reconciler.reconcile()

        # Assert
        assert (
            len(report.critical_issues) > 0
        ), f"Expected len(report.critical_issues) > 0, got {len(report.critical_issues)}"
        assert (
            "BTC/USD" in report.zombies
        ), 'Assertion condition not met: "BTC/USD" in report.zombies'

    def test_reconcile_notification_failure_not_blocking(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_settings,
        sample_alpaca_position,
    ):
        """Notification failure (at service level) doesn't block reconciliation."""
        # Arrange
        mock_trading_client.get_all_positions.return_value = [sample_alpaca_position]
        mock_position_repo.get_open_positions.return_value = []

        # Use real service with mocked discord client to test internal error handling
        mock_discord = MagicMock()
        mock_discord.send_message.side_effect = Exception("Discord Error")
        service = ReconcilerNotificationService(mock_discord)

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=service,
            settings=mock_settings,
        )

        # Act
        # Should still return report
        report = reconciler.reconcile()

        # Assert
        assert (
            len(report.orphans) > 0
        ), f"Orphan still detected: expected len(report.orphans) > 0, got {len(report.orphans)}"
        expected_error = ReconciliationErrors.ORPHAN_POSITION.format(symbol="BTC/USD")
        assert any(
            expected_error in issue for issue in report.critical_issues
        ), "Expected any(expected_error in issue for issue in report.critical_issues)"

    def test_reconcile_report_timestamp_is_set(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
    ):
        """Reconciliation report includes current timestamp."""
        # Arrange
        from datetime import datetime

        mock_trading_client.get_all_positions.return_value = []
        mock_position_repo.get_open_positions.return_value = []

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        before = datetime.now(datetime.now().astimezone().tzinfo)
        report = reconciler.reconcile()
        after = datetime.now(datetime.now().astimezone().tzinfo)

        # Assert
        assert (
            before <= report.timestamp <= after
        ), f"Expected before <= report.timestamp <= after, got {before}"

    def test_reconcile_only_processes_open_positions(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
    ):
        """Reconciliation only checks open positions from Firestore."""
        # Arrange
        # Alpaca has nothing
        mock_trading_client.get_all_positions.return_value = []

        # Firestore returns only open positions (as per method contract)
        # Using sample_open_position which has all required attributes
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        # Only BTC/USD should be detected as zombie
        assert (
            "BTC/USD" in report.zombies
        ), 'Assertion condition not met: "BTC/USD" in report.zombies'
        assert (
            len(report.zombies) == 1
        ), f"Expected len(report.zombies) == 1, got {len(report.zombies)}"

    def test_reconcile_with_same_symbols_in_both_states(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
    ):
        """Reconciliation detects no issues when symbols match."""
        # Arrange
        alpaca_pos = MagicMock()
        alpaca_pos.symbol = "BTCUSD"

        # Use sample_open_position which has all required attributes
        sample_open_position.status = TradeStatus.OPEN
        mock_trading_client.get_all_positions.return_value = [alpaca_pos]
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile()

        # Assert
        # No zombies or orphans when in sync
        assert (
            len(report.zombies) == 0
        ), f"Expected len(report.zombies) == 0, got {len(report.zombies)}"
        assert (
            len(report.orphans) == 0
        ), f"Expected len(report.orphans) == 0, got {len(report.orphans)}"
        assert (
            report.reconciled_count == 0
        ), f"Expected report.reconciled_count == 0, got {report.reconciled_count}"


class TestReconcilerSettings:
    """Test reconciler behavior with different settings."""

    def test_reconcile_uses_provided_settings(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
    ):
        """Reconciler uses provided settings instead of global defaults."""
        # Arrange
        custom_settings = MagicMock()
        custom_settings.ENVIRONMENT = "STAGING"

        # Act
        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=custom_settings,
        )

        # Assert
        assert (
            reconciler.settings == custom_settings
        ), f"Expected reconciler.settings == custom_settings, got {reconciler.settings}"
        assert (
            reconciler.settings.ENVIRONMENT == "STAGING"
        ), 'Expected reconciler.settings.ENVIRONMENT == "STAGING"'

    def test_reconcile_defaults_to_get_settings_when_none(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
    ):
        """Reconciler uses get_settings() when settings param is None."""
        # Arrange
        with patch("crypto_signals.engine.reconciler.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.ENVIRONMENT = "PROD"
            mock_get_settings.return_value = mock_settings

            mock_trading_client.get_all_positions.return_value = []
            mock_position_repo.get_open_positions.return_value = []

            # Act
            reconciler = StateReconciler(
                alpaca_client=mock_trading_client,
                position_repo=mock_position_repo,
                notification_service=mock_notification_service,
                settings=None,
            )

            # Assert
            assert (
                reconciler.settings == mock_settings
            ), f"Expected reconciler.settings == mock_settings, got {reconciler.settings}"
            mock_get_settings.assert_called_once()


class TestSafetyMechanisms:
    """Test critical safety mechanisms (Issue #244 fixes)."""

    def test_reconcile_skips_young_zombies(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
    ):
        """Reconciliation ignores zombies created within the grace period (Race Condition protection)."""
        # Arrange
        # Zombie Position (Open in DB, Missing in Alpaca)
        mock_trading_client.get_all_positions.return_value = []

        # Make it "Young" (created 1 minute ago)
        sample_open_position.created_at = datetime.now(timezone.utc) - timedelta(
            minutes=1
        )
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile(min_age_minutes=5)

        # Assert
        # Should NOT be healed/closed
        mock_position_repo.update_position.assert_not_called()

        # Should not be in critical issues (it's skipped intentionaly)
        assert (
            len(report.critical_issues) == 0
        ), f"Expected len(report.critical_issues) == 0, got {len(report.critical_issues)}"
        # Should not be counted as a processed zombie in the final report lists
        # (implementation detail: logic creates zombies list first, then loops.
        # Check if code removes it from list or just skips actions.
        # Based on code: it iterates zombies but `continue`. So it IS in report.zombies list but NO action taken)
        assert (
            "BTC/USD" in report.zombies
        ), 'Assertion condition not met: "BTC/USD" in report.zombies'

    def test_reconcile_refuses_to_close_unverified_zombie(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
    ):
        """Reconciliation REFUSES to close a zombie if manual verification fails."""
        # Arrange
        # Old Zombie (valid age)
        mock_trading_client.get_all_positions.return_value = []
        sample_open_position.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        # Mock Verification to FAIL (return False)
        # using patch object on the specific instance method
        with patch.object(
            reconciler, "handle_manual_exit_verification", return_value=None
        ):
            report = reconciler.reconcile()

        # Assert
        # CRITICAL: Database must NOT be updated (Position must remain OPEN)
        mock_position_repo.update_position.assert_not_called()

        # Should log critical issue
        assert (
            len(report.critical_issues) > 0
        ), f"Expected len(report.critical_issues) > 0, got {len(report.critical_issues)}"
        expected_error = ReconciliationErrors.ZOMBIE_EXIT_GAP.format(symbol="BTC/USD")
        assert any(
            expected_error in i for i in report.critical_issues
        ), "Expected any(expected_error in i for i in report.critical_issues)"

        # Should alert notification service
        assert mock_notification_service.notify_critical_sync_failure.called, f"Expected mock_notification_service.notify_critical_sync_failure.called to be truthy, got {mock_notification_service.notify_critical_sync_failure.called}"


class TestReconcilerRaceConditions:
    """Test race condition fixes (Issue #244)."""

    def test_race_condition_zombie_kill(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
    ):
        """
        Verify that a 'zombie' which is just a few seconds old is NOT killed/closed.
        This simulates the race condition where `main.py` creates a position,
        saves to DB, submits to Alpaca, but Alpaca hasn't indexed it yet
        when Reconciler runs.
        """
        # Arrange
        # Zombie Position (Open in DB, Missing in Alpaca)
        mock_trading_client.get_all_positions.return_value = []

        # Make it "Young" (created 1 minute ago)
        # Using a fixed time for stability
        now = datetime.now(timezone.utc)
        sample_open_position.created_at = now - timedelta(minutes=1)
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        report = reconciler.reconcile(min_age_minutes=5)

        # Assert
        # Should NOT be healed/closed
        mock_position_repo.update_position.assert_not_called()

        # Should NOT be in critical issues (it's skipped intentionally)
        assert (
            len(report.critical_issues) == 0
        ), f"Expected len(report.critical_issues) == 0, got {len(report.critical_issues)}"

        # Should be in zombies list but skipped
        assert (
            "BTC/USD" in report.zombies
        ), 'Assertion condition not met: "BTC/USD" in report.zombies'

    def test_manual_exit_verification_used(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        sample_open_position,
    ):
        """
        Verify that before closing a zombie, the reconciler calls
        handle_manual_exit_verification.
        """
        # Arrange
        # Old Zombie (valid age)
        mock_trading_client.get_all_positions.return_value = []
        sample_open_position.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_position_repo.get_open_positions.return_value = [sample_open_position]

        reconciler = StateReconciler(
            alpaca_client=mock_trading_client,
            position_repo=mock_position_repo,
            notification_service=mock_notification_service,
            settings=mock_settings,
        )

        # Act
        with patch.object(
            reconciler, "handle_manual_exit_verification", return_value=True
        ) as mock_verify:
            reconciler.reconcile()

            # Assert
            mock_verify.assert_called_once()
            # And position was updated (closed)
            mock_position_repo.update_position.assert_called()


class TestTheoreticalPositions:
    """Test handling of theoretical positions."""

    @pytest.fixture
    def theoretical_position(self):
        return PositionFactory.build(
            position_id="theo-123",
            account_id="theoretical",
            signal_id="sig-123",
            alpaca_order_id="theo-order-1",
            qty=0.01,
            trade_type=TradeType.THEORETICAL.value,  # Key field
        )

    def test_reconcile_ignores_theoretical_positions(
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        theoretical_position,
    ):
        """Verify that OPEN theoretical positions are NOT flagged as zombies when missing from Alpaca."""
        # Arrange
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

        # Act
        report = reconciler.reconcile()

        # Assert
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
        self,
        mock_trading_client,
        mock_position_repo,
        mock_notification_service,
        mock_settings,
        theoretical_position,
    ):
        """Verify that normal OPEN positions ARE flagged as zombies, even if mixed with theoreticals."""
        # Arrange
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

        # Act
        report = reconciler.reconcile()

        # Assert
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
