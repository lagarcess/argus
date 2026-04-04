"""Unit tests for the main application entrypoint."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import ANY, MagicMock, Mock, call, patch

import pytest
from crypto_signals.domain.schemas import (
    AssetClass,
    OrderSide,
    SignalStatus,
    TradeStatus,
    TradeType,
)
from crypto_signals.main import main
from loguru import logger

from tests.factories import PositionFactory, SignalFactory


@pytest.fixture
def caplog(caplog):
    """Override caplog fixture to capture loguru logs."""
    handler_id = logger.add(
        caplog.handler,
        format="{message}",
        level=0,
        filter=lambda record: record["level"].no >= 0,
        catch=False,
    )
    yield caplog
    logger.remove(handler_id)


@pytest.fixture
def main_test_setup(mock_main_dependencies):
    """Shared setup fixture for main execution tests."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_repo_instance = mock_main_dependencies["repo"].return_value
    mock_discord_instance = mock_main_dependencies["discord"].return_value

    mock_signal = MagicMock()
    mock_signal.symbol = "BTC/USD"
    mock_signal.signal_id = "test_signal_btc_main"
    mock_signal.pattern_name = "bullish_engulfing"
    mock_signal.suggested_stop = 90000.0
    mock_signal.discord_thread_id = None

    mock_discord_instance.find_thread_by_signal_id.return_value = None

    def side_effect(symbol, asset_class, **kwargs):
        if symbol == "BTC/USD":
            return mock_signal
        return None

    mock_gen_instance.generate_signals.side_effect = side_effect
    mock_discord_instance.send_signal.return_value = "thread_123456"

    # Detach return value to prevent attribute access logs (critical_issues, etc.)
    mock_report = MagicMock()
    mock_report.critical_issues = []
    mock_report.zombies = []
    mock_report.orphans = []
    mock_report.reconciled_count = 0
    mock_main_dependencies["reconciler"].return_value.reconcile.return_value = mock_report

    # Configure pipeline return values to prevent logging interaction
    mock_main_dependencies["trade_archival"].return_value.run.return_value = 5
    mock_main_dependencies["fee_patch"].return_value.run.return_value = 2
    mock_main_dependencies["price_patch"].return_value.run.return_value = 1
    mock_main_dependencies["rejected_archival"].return_value.run.return_value = 3
    mock_main_dependencies["expired_archival"].return_value.run.return_value = 4
    mock_main_dependencies["backtest_archival"].return_value.run.return_value = 0

    # Setup tracking for Reconcile -> Archive -> Archival Pipelines -> Fee Patch Sequence
    pipeline_manager = Mock()
    pipeline_manager.attach_mock(
        mock_main_dependencies["reconciler"].return_value.reconcile, "reconcile"
    )
    pipeline_manager.attach_mock(
        mock_main_dependencies["trade_archival"].return_value.run, "archive"
    )
    pipeline_manager.attach_mock(
        mock_main_dependencies["rejected_archival"].return_value.run, "rejected_archive"
    )
    pipeline_manager.attach_mock(
        mock_main_dependencies["expired_archival"].return_value.run, "expired_archive"
    )
    pipeline_manager.attach_mock(
        mock_main_dependencies["backtest_archival"].return_value.run, "backtest_archive"
    )
    pipeline_manager.attach_mock(
        mock_main_dependencies["fee_patch"].return_value.run, "fee_patch"
    )
    pipeline_manager.attach_mock(
        mock_main_dependencies["price_patch"].return_value.run, "price_patch"
    )

    return {
        "generator": mock_gen_instance,
        "repo": mock_repo_instance,
        "discord": mock_discord_instance,
        "signal": mock_signal,
        "pipeline_manager": pipeline_manager,
    }


def test_main_execution_flow(mock_main_dependencies, main_test_setup):
    """Test the normal execution flow of the main function."""
    setup = main_test_setup
    mock_gen_instance = setup["generator"]
    mock_repo_instance = setup["repo"]
    mock_discord_instance = setup["discord"]
    mock_signal = setup["signal"]
    pipeline_manager = setup["pipeline_manager"]

    # Create a manager to track call order across the initial generation loop mocks
    manager = Mock()
    manager.attach_mock(mock_repo_instance.save, "save")
    manager.attach_mock(mock_discord_instance.send_signal, "send_signal")
    manager.attach_mock(mock_repo_instance.update_signal, "update_signal")

    # Execute
    main(smoke_test=False)

    # Verify Initialization
    mock_main_dependencies["stock_client"].assert_called_once()
    mock_main_dependencies["crypto_client"].assert_called_once()
    mock_main_dependencies["market_provider"].assert_called_once()
    mock_main_dependencies["generator"].assert_called_once()
    mock_main_dependencies["repo"].assert_called_once()
    mock_main_dependencies["discord"].assert_called_once()

    # Verify Thread Recovery Attempted
    # find_thread_by_signal_id should be called before send_signal
    mock_discord_instance.find_thread_by_signal_id.assert_called()

    # Verify Portfolio Iteration & Asset Class Detection
    expected_calls = [
        call("BTC/USD", AssetClass.CRYPTO, dataframe=ANY),
        call("ETH/USD", AssetClass.CRYPTO, dataframe=ANY),
        call("XRP/USD", AssetClass.CRYPTO, dataframe=ANY),
    ]
    mock_gen_instance.generate_signals.assert_has_calls(expected_calls, any_order=True)

    # Verify Signal Handling (Save FIRST with CREATED, then Discord, then Update to WAITING)
    mock_repo_instance.save.assert_called_once_with(mock_signal)
    mock_discord_instance.send_signal.assert_called_once()
    actual_payload = mock_discord_instance.send_signal.call_args[0][0]
    assert actual_payload.signal is mock_signal
    assert actual_payload.is_saturated is False
    mock_repo_instance.update_signal_atomic.assert_called()

    # Verify thread_id was attached to signal after Discord notification
    assert mock_signal.discord_thread_id == "thread_123456"

    # Verify explicit call order: Save -> Discord -> Update (two-phase commit)
    expected_updates = {
        "discord_thread_id": "thread_123456",
        "status": SignalStatus.WAITING.value,
    }
    mock_repo_instance.update_signal_atomic.assert_called_with(
        mock_signal.signal_id, expected_updates
    )

    # Legacy update should NOT be called
    mock_repo_instance.update_signal.assert_not_called()

    # Verify precise call order for Pipelines
    actual_calls = [c[0] for c in pipeline_manager.mock_calls]
    assert actual_calls == [
        "rejected_archive",
        "expired_archive",
        "reconcile",
        "archive",
        "backtest_archive",
        "fee_patch",
        "price_patch",
    ], f"Actual calls mismatch: {actual_calls}"


def test_main_legacy_archival_disabled(mock_main_dependencies, main_test_setup):
    """Test that legacy archival pipelines are skipped when disabled."""
    # Define Settings flag False
    mock_main_dependencies["settings"].return_value.USE_LEGACY_ARCHIVAL = False

    # Execute
    main(smoke_test=False)

    # Verify explicit call order skips legacy
    pipeline_manager = main_test_setup["pipeline_manager"]
    actual_calls = [c[0] for c in pipeline_manager.mock_calls]
    assert actual_calls == [
        "reconcile",
        "archive",
        "backtest_archive",
        "fee_patch",
        "price_patch",
    ], f"Actual calls mismatch: {actual_calls}"


def test_send_signal_captures_thread_id(mock_main_dependencies):
    """Test that thread_id from send_signal is captured and persisted."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_repo_instance = mock_main_dependencies["repo"].return_value
    mock_discord_instance = mock_main_dependencies["discord"].return_value

    # Setup signal with required attributes for structured logging
    mock_signal = MagicMock()
    mock_signal.symbol = "BTC/USD"
    mock_signal.signal_id = "test_signal_btc"
    mock_signal.pattern_name = "test_pattern"
    mock_signal.suggested_stop = 90000.0
    mock_signal.asset_class = AssetClass.CRYPTO

    def side_effect(symbol, asset_class, **kwargs):
        if symbol == "BTC/USD":
            return mock_signal
        return None

    mock_gen_instance.generate_signals.side_effect = side_effect

    # Mock send_signal to return a thread_id
    mock_discord_instance.send_signal.return_value = "mock_thread_98765"

    # Mock recovery to return None (not found) implies send_signal will be called
    mock_discord_instance.find_thread_by_signal_id.return_value = None

    # Execute
    main(smoke_test=False)

    # Verify thread_id was attached to signal
    assert mock_signal.discord_thread_id == "mock_thread_98765"

    # Verify explicit interactions
    mock_repo_instance.save.assert_called()
    mock_discord_instance.send_signal.assert_called()
    mock_repo_instance.update_signal_atomic.assert_called()
    mock_repo_instance.update_signal.assert_not_called()


def test_main_symbol_error_handling(mock_main_dependencies):
    """Test that main continues processing remaining symbols if one fails."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value

    # Make ETH/USD raise an exception
    def side_effect(symbol, asset_class, **kwargs):
        if symbol == "ETH/USD":
            raise ValueError("Simulated Analysis Error")
        return None

    mock_gen_instance.generate_signals.side_effect = side_effect

    # Execute (should not raise exception)
    main(smoke_test=False)

    # Verify that subsequent symbols (e.g., XRP/USD) were still processed
    calls = mock_gen_instance.generate_signals.call_args_list
    symbols_processed = [args[0] for args, _ in calls]

    assert "BTC/USD" in symbols_processed
    assert "ETH/USD" in symbols_processed
    assert "XRP/USD" in symbols_processed


def test_main_fatal_error():
    """Test that critical initialization errors cause a system exit."""
    with patch("crypto_signals.main.get_stock_data_client") as mock_init:
        mock_init.side_effect = ImportError("Critical Dependency Missing")

        with pytest.raises(SystemExit) as excinfo:
            main(smoke_test=False)

        assert excinfo.value.code == 1


def test_main_notification_failure(mock_main_dependencies, caplog):
    """Test that main logs a warning if notification fails."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_discord_instance = mock_main_dependencies["discord"].return_value

    # Setup signal for BTC/USD only
    mock_signal = MagicMock()
    mock_signal.symbol = "BTC/USD"
    mock_signal.signal_id = "test_signal_notification"
    mock_signal.pattern_name = "test_pattern"
    mock_signal.suggested_stop = 90000.0
    mock_signal.asset_class = AssetClass.CRYPTO

    def side_effect(symbol, asset_class, **kwargs):
        if symbol == "BTC/USD":
            return mock_signal
        return None

    mock_gen_instance.generate_signals.side_effect = side_effect

    # Mock notification failure
    mock_discord_instance.send_signal.return_value = False

    # Execute with caplog capturing (handled by fixture)

    with caplog.at_level("WARNING"):
        main(smoke_test=False)

    # Verify warning (now uses compensation logic - signal marked invalid)
    assert "Discord notification failed" in caplog.text
    assert "marking signal as invalidated" in caplog.text


def test_main_repo_failure(mock_main_dependencies, caplog):
    """Test that main logs an error and continues if repository save fails."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_repo_instance = mock_main_dependencies["repo"].return_value

    # Setup signals with proper signal_id
    def gen_side_effect(symbol, asset_class, **kwargs):
        if symbol in ["BTC/USD", "ETH/USD"]:
            sig = MagicMock()
            sig.symbol = symbol
            sig.signal_id = f"test_id_{symbol.replace('/', '_')}"
            sig.pattern_name = "test_pattern"
            sig.suggested_stop = 100.0
            sig.asset_class = AssetClass.CRYPTO
            return sig
        return None

    mock_gen_instance.generate_signals.side_effect = gen_side_effect

    # Mock repository failure ONLY for BTC/USD
    def save_side_effect(signal):
        if signal.symbol == "BTC/USD":
            raise RuntimeError("Firestore Unavailable")
        return None

    mock_repo_instance.save.side_effect = save_side_effect

    # Execute with caplog capturing (handled by fixture)

    with caplog.at_level("ERROR"):
        main(smoke_test=False)

    # Verify error log for persistence failure (new behavior: skips notification)
    assert "Failed to persist signal" in caplog.text
    assert "skipping notification to prevent zombie signal" in caplog.text

    # Verify that ETH/USD was still processed (Loop continued)
    calls = mock_gen_instance.generate_signals.call_args_list
    symbols_processed = [args[0] for args, _ in calls]
    assert "ETH/USD" in symbols_processed


def test_main_uses_firestore_config(mock_main_dependencies):
    """Test that Firestore configuration overrides .env settings."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_firestore_config = mock_main_dependencies["firestore_config"]
    mock_settings = mock_main_dependencies["settings"].return_value

    # Setup Firestore returns
    mock_firestore_config.return_value = {
        "CRYPTO_SYMBOLS": ["SOL/USD"],
        # NOTE: Equities intentionally omitted in this test to verify simple crypto override
    }

    # Mock signal generation to avoid side effects
    mock_gen_instance.generate_signals.return_value = None

    # Execute
    main(smoke_test=False)

    # Verify Logic
    # 1. Check if settings were updated
    assert mock_settings.CRYPTO_SYMBOLS == ["SOL/USD"]

    # 2. Verify iteration happened on NEW symbols
    expected_calls = [
        call("SOL/USD", AssetClass.CRYPTO, dataframe=ANY),
    ]
    mock_gen_instance.generate_signals.assert_has_calls(expected_calls, any_order=True)

    # 3. Ensure OLD symbols were NOT processed
    assert mock_gen_instance.generate_signals.call_count == 1


def test_main_fallback_to_env_on_empty(mock_main_dependencies):
    """Test fallback to .env when Firestore returns empty config."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_firestore_config = mock_main_dependencies["firestore_config"]
    mock_settings = mock_main_dependencies["settings"].return_value

    # Setup Firestore returns empty
    mock_firestore_config.return_value = {}

    # Mock signal generation
    mock_gen_instance.generate_signals.return_value = None

    # Execute
    main(smoke_test=False)

    # Verify Logic
    # Settings should remain as default (from fixture)
    assert mock_settings.CRYPTO_SYMBOLS == ["BTC/USD", "ETH/USD", "XRP/USD"]

    # Should process default symbols
    mock_gen_instance.generate_signals.assert_any_call(
        "BTC/USD", AssetClass.CRYPTO, dataframe=ANY
    )


def test_guardrail_ignores_firestore_equities(mock_main_dependencies, caplog):
    """
    Risk Verification: Ensure that if Firestore returns equities,
    the system respects the hardcoded restriction and IGNORES them.
    """
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_firestore_config = mock_main_dependencies["firestore_config"]
    mock_settings = mock_main_dependencies["settings"].return_value

    # 1. Simulate Firestore returning Equities
    mock_firestore_config.return_value = {
        "CRYPTO_SYMBOLS": ["BTC/USD"],
        "EQUITY_SYMBOLS": ["AAPL", "TSLA"],
    }

    # 2. Simulate "Basic Plan" Restriction (default is empty)
    mock_settings.EQUITY_SYMBOLS = []

    mock_gen_instance.generate_signals.return_value = None

    mock_gen_instance.generate_signals.return_value = None

    with caplog.at_level("WARNING"):
        main(smoke_test=False)

    # Asset: Equities should still be EMPTY because the guardrail ignored them.
    assert mock_settings.EQUITY_SYMBOLS == []

    # Verify equities were NOT processed
    calls = mock_gen_instance.generate_signals.call_args_list
    symbols = [args[0] for args, _ in calls]
    assert "AAPL" not in symbols
    assert "TSLA" not in symbols
    assert "BTC/USD" in symbols


# =============================================================================
# POSITION SYNC LOOP TESTS
# =============================================================================


def _create_test_position(
    position_id="pos-1",
    status=TradeStatus.OPEN,
    tp_order_id=None,
    sl_order_id=None,
    filled_at=None,
    entry_fill_price=50000.0,
    failed_reason=None,
):
    """Helper to create a Position for testing."""
    return PositionFactory.build(
        position_id=position_id,
        ds=date(2025, 1, 15),
        account_id="paper",
        symbol="BTC/USD",
        signal_id="signal-1",
        alpaca_order_id="alpaca-order-1",
        status=status,
        entry_fill_price=entry_fill_price,
        current_stop_loss=48000.0,
        qty=0.05,
        side=OrderSide.BUY,
        tp_order_id=tp_order_id,
        sl_order_id=sl_order_id,
        filled_at=filled_at,
        failed_reason=failed_reason,
    )


def test_sync_loop_updates_position_on_status_change(mock_main_dependencies, caplog):
    """Test that positions are updated when status changes (TP/SL hit)."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_gen_instance.generate_signals.return_value = None

    mock_settings = mock_main_dependencies["settings"].return_value
    mock_settings.ENABLE_EXECUTION = True

    mock_position_repo = mock_main_dependencies["position_repo"].return_value
    mock_execution_engine = mock_main_dependencies["execution_engine"].return_value

    # Create position that will be "closed" by sync
    original_pos = _create_test_position(status=TradeStatus.OPEN)
    closed_pos = _create_test_position(status=TradeStatus.CLOSED)

    mock_position_repo.get_open_positions.return_value = [original_pos]
    mock_execution_engine.sync_position_status.return_value = closed_pos

    with caplog.at_level("INFO"):
        main(smoke_test=False)

    # Verify update was called with closed status
    mock_position_repo.update_position.assert_called_once_with(closed_pos)

    # Verify logging
    assert "Position pos-1 closed: CLOSED" in caplog.text


def test_sync_loop_updates_position_on_leg_id_change(mock_main_dependencies, caplog):
    """Test that positions are updated when TP/SL leg IDs change."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_gen_instance.generate_signals.return_value = None

    mock_settings = mock_main_dependencies["settings"].return_value
    mock_settings.ENABLE_EXECUTION = True

    mock_position_repo = mock_main_dependencies["position_repo"].return_value
    mock_execution_engine = mock_main_dependencies["execution_engine"].return_value

    # Create position without leg IDs
    original_pos = _create_test_position(tp_order_id=None, sl_order_id=None)
    # Sync returns position with leg IDs populated
    synced_pos = _create_test_position(tp_order_id="tp-leg-123", sl_order_id="sl-leg-456")

    mock_position_repo.get_open_positions.return_value = [original_pos]
    mock_execution_engine.sync_position_status.return_value = synced_pos

    with caplog.at_level("INFO"):
        main(smoke_test=False)

    # Verify update was called
    mock_position_repo.update_position.assert_called_once_with(synced_pos)

    # Verify logging shows what changed
    assert "Position pos-1 synced" in caplog.text
    assert "TP=tp-leg-123" in caplog.text
    assert "SL=sl-leg-456" in caplog.text


def test_sync_loop_handles_exceptions_gracefully(mock_main_dependencies, caplog):
    """Test that sync loop continues after individual position sync failures."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_gen_instance.generate_signals.return_value = None

    mock_settings = mock_main_dependencies["settings"].return_value
    mock_settings.ENABLE_EXECUTION = True

    mock_position_repo = mock_main_dependencies["position_repo"].return_value
    mock_execution_engine = mock_main_dependencies["execution_engine"].return_value

    # Create two positions
    pos1 = _create_test_position(position_id="pos-1")
    pos2 = _create_test_position(position_id="pos-2")

    mock_position_repo.get_open_positions.return_value = [pos1, pos2]

    # First position sync fails, second succeeds with changes
    synced_pos2 = _create_test_position(position_id="pos-2", tp_order_id="tp-new")

    def sync_side_effect(pos):
        if pos.position_id == "pos-1":
            raise RuntimeError("Alpaca API Error")
        return synced_pos2

    mock_execution_engine.sync_position_status.side_effect = sync_side_effect

    with caplog.at_level("WARNING"):
        main(smoke_test=False)

    # Verify error was logged for pos-1
    assert "Failed to sync position pos-1" in caplog.text
    assert "Alpaca API Error" in caplog.text

    # Verify pos-2 was still updated (loop continued)
    mock_position_repo.update_position.assert_called_once_with(synced_pos2)


def test_sync_loop_skipped_when_execution_disabled(mock_main_dependencies):
    """Test that sync loop is skipped when ENABLE_EXECUTION is False."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_gen_instance.generate_signals.return_value = None

    mock_settings = mock_main_dependencies["settings"].return_value
    mock_settings.ENABLE_EXECUTION = False

    mock_position_repo = mock_main_dependencies["position_repo"].return_value

    main(smoke_test=False)

    # Verify get_open_positions was never called
    mock_position_repo.get_open_positions.assert_not_called()


def test_sync_loop_no_update_when_position_unchanged(mock_main_dependencies):
    """Test that positions are not updated when nothing changed."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_gen_instance.generate_signals.return_value = None

    mock_settings = mock_main_dependencies["settings"].return_value
    mock_settings.ENABLE_EXECUTION = True

    mock_position_repo = mock_main_dependencies["position_repo"].return_value
    mock_execution_engine = mock_main_dependencies["execution_engine"].return_value

    # Create position
    pos = _create_test_position()

    mock_position_repo.get_open_positions.return_value = [pos]
    # Sync returns same position (no changes)
    mock_execution_engine.sync_position_status.return_value = pos

    main(smoke_test=False)

    # Verify update was NOT called
    mock_position_repo.update_position.assert_not_called()


# =============================================================================
# ZOMBIE SIGNAL PREVENTION TESTS
# =============================================================================


def test_zombie_signal_prevention_persistence_first(mock_main_dependencies):
    """
    Test that signals are persisted BEFORE Discord notification (two-phase commit).

    This prevents "Zombie Signals" where users receive Discord notifications
    for signals that were never persisted to the database.
    """
    from crypto_signals.domain.schemas import SignalStatus

    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_repo_instance = mock_main_dependencies["repo"].return_value
    mock_discord_instance = mock_main_dependencies["discord"].return_value

    # Setup signal
    mock_signal = MagicMock()
    mock_signal.symbol = "BTC/USD"
    mock_signal.signal_id = "test_signal_zombie_prevention"
    mock_signal.pattern_name = "bullish_engulfing"
    mock_signal.suggested_stop = 90000.0

    def side_effect(symbol, asset_class, **kwargs):
        if symbol == "BTC/USD":
            return mock_signal
        return None

    mock_gen_instance.generate_signals.side_effect = side_effect
    mock_discord_instance.send_signal.return_value = "thread_123"

    # Track call order
    call_order = []

    def track_save(signal):
        call_order.append(("save", signal.status))

    def track_update(signal):
        call_order.append(("update", signal.status))

    def track_discord(signal):
        call_order.append(("discord", getattr(signal, "status", None)))
        return "thread_123"

    mock_discord_instance.send_signal.side_effect = track_discord
    mock_repo_instance.save.side_effect = track_save

    def track_atomic(signal_id, updates):
        # Interpret status from updates dict
        status = updates.get("status")
        # Convert value back to enum if necessary or just store value
        # Tests check against SignalStatus enum usually, so let's try to map back if int?
        # But wait, updates["status"] is .value (int/str). SignalStatus is Enum.
        # Original test tracked signal.status (Enum).
        # Let's just track ("update", status_value) and adjust assertion.
        call_order.append(("update", status))
        return True

    mock_repo_instance.update_signal_atomic.side_effect = track_atomic

    main(smoke_test=False)

    # Verify CREATED status set first, then saved, then Discord, then WAITING update
    assert len(call_order) == 3
    assert call_order[0] == ("save", SignalStatus.CREATED)
    assert call_order[1][0] == "discord"  # Discord called after save
    # Atomic update passes the VALUE of the status, verify that.
    assert call_order[2] == ("update", SignalStatus.WAITING.value)

    # Verify atomic update called separately
    mock_repo_instance.update_signal_atomic.assert_called()


def test_zombie_signal_compensation_on_discord_failure(mock_main_dependencies, caplog):
    """
    Test that signal is marked INVALIDATED if Discord notification fails.

    When persistence succeeds but Discord fails, we compensate by marking
    the signal as INVALIDATED to prevent untracked active signals.
    """
    from crypto_signals.domain.schemas import ExitReason, SignalStatus

    mock_gen_instance = mock_main_dependencies["generator"].return_value
    _mock_repo_instance = mock_main_dependencies["repo"].return_value  # noqa: F841
    mock_discord_instance = mock_main_dependencies["discord"].return_value

    mock_signal = MagicMock()
    mock_signal.symbol = "BTC/USD"
    mock_signal.signal_id = "test_signal_discord_fail"
    mock_signal.pattern_name = "test_pattern"
    mock_signal.suggested_stop = 90000.0
    mock_signal.asset_class = AssetClass.CRYPTO

    def side_effect(symbol, asset_class, **kwargs):
        if symbol == "BTC/USD":
            return mock_signal
        return None

    mock_gen_instance.generate_signals.side_effect = side_effect

    # Discord fails - returns None/False
    mock_discord_instance.send_signal.return_value = None

    with caplog.at_level("WARNING"):
        main(smoke_test=False)

    # Verify compensation: signal marked as INVALIDATED via atomic update
    if not mock_main_dependencies["repo"].return_value.update_signal_atomic.called:
        pytest.fail(f"Atomic update NOT called. Logs:\n{caplog.text}")

    # We check the atomic update call args because checking mock_signal.status can be unreliable if main uses a copy
    args, _ = mock_main_dependencies["repo"].return_value.update_signal_atomic.call_args
    assert args[0] == "test_signal_discord_fail"
    updates = args[1]
    assert updates["status"] == SignalStatus.INVALIDATED
    assert updates["exit_reason"] == ExitReason.NOTIFICATION_FAILED

    # Verify warning was logged
    assert "Discord notification failed" in caplog.text
    assert "marking signal as invalidated" in caplog.text


def test_signal_skipped_if_initial_persistence_fails(mock_main_dependencies, caplog):
    """
    Test that Discord is NOT called if initial persistence fails.

    This is critical to prevent Zombie Signals - if we can't persist,
    we must NOT notify users about a signal we can't track.
    """
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_repo_instance = mock_main_dependencies["repo"].return_value
    mock_discord_instance = mock_main_dependencies["discord"].return_value

    mock_signal = MagicMock()
    mock_signal.symbol = "BTC/USD"
    mock_signal.signal_id = "test_signal_persist_fail"
    mock_signal.pattern_name = "test_pattern"
    mock_signal.suggested_stop = 90000.0
    mock_signal.asset_class = AssetClass.CRYPTO

    def side_effect(symbol, asset_class, **kwargs):
        if symbol == "BTC/USD":
            return mock_signal
        return None

    mock_gen_instance.generate_signals.side_effect = side_effect

    # Initial save fails
    mock_repo_instance.save.side_effect = RuntimeError("Firestore Unavailable")

    with caplog.at_level("ERROR"):
        main(smoke_test=False)

    # Verify Discord was NEVER called (zombie prevention)
    mock_discord_instance.send_signal.assert_not_called()

    # Verify error logged
    assert "Failed to persist signal" in caplog.text
    assert "skipping notification to prevent zombie signal" in caplog.text


def test_thread_recovery_check(mock_main_dependencies, caplog):
    """Test that existing thread is recovered and send_signal is skipped."""
    mock_gen_instance = mock_main_dependencies["generator"].return_value
    mock_discord_instance = mock_main_dependencies["discord"].return_value
    mock_repo_instance = mock_main_dependencies["repo"].return_value

    # Setup signal
    # Setup signal
    mock_signal = MagicMock()
    mock_signal.symbol = "BTC/USD"
    mock_signal.signal_id = "test_signal_recovery"
    mock_signal.pattern_name = "test_pattern"
    mock_signal.asset_class = AssetClass.CRYPTO
    mock_signal.discord_thread_id = None  # Initially missing

    def side_effect(symbol, asset_class, **kwargs):
        if symbol == "BTC/USD":
            return mock_signal
        return None

    mock_gen_instance.generate_signals.side_effect = side_effect

    # Reinforce environment mocks
    mock_main_dependencies["job_lock"].return_value.acquire_lock.return_value = True
    mock_main_dependencies["secrets"].return_value = True

    # Mock Recovery Success
    mock_discord_instance.find_thread_by_signal_id.return_value = "recovered_thread_123"
    mock_repo_instance.update_signal_atomic.return_value = True

    with caplog.at_level("INFO"):
        main(smoke_test=False)

    # Verify:
    # 1. find_thread called
    mock_discord_instance.find_thread_by_signal_id.assert_called_once()

    # 2. send_signal SKIPPED
    mock_discord_instance.send_signal.assert_not_called()

    # 3. Verify object update explicitly if logical check needed
    assert mock_signal.discord_thread_id == "recovered_thread_123"

    # 3. repo updated with recovered ID
    # atomic update call
    mock_repo_instance.update_signal_atomic.assert_called()
    # Check signal object state updated
    assert mock_signal.discord_thread_id == "recovered_thread_123"


def test_main_expires_before_check_exits(mock_main_dependencies):
    """
    Verify that main.py expires stale signals before calling check_exits (Issue #280).
    """
    repo = mock_main_dependencies["repo"].return_value
    generator = mock_main_dependencies["generator"].return_value

    # 1. Setup a STALE WAITING signal
    now_utc = datetime.now(timezone.utc)
    stale_signal = SignalFactory.build(
        signal_id="stale_id",
        ds=datetime.now(timezone.utc).date() - timedelta(days=2),
        strategy_id="strat",
        symbol="BTC/USD",
        asset_class=AssetClass.CRYPTO,
        entry_price=100.0,
        pattern_name="TEST",
        suggested_stop=90.0,
        status=SignalStatus.WAITING,
        valid_until=now_utc - timedelta(hours=1),
        created_at=now_utc - timedelta(hours=2),
    )

    repo.get_active_signals.return_value = [stale_signal]
    repo.get_by_id.return_value = None  # For idempotency check
    generator.generate_signals.return_value = None  # No new signals

    # Mock check_exits to return the signal as INVALIDATED (the bug)
    # We want to see if main.py prevents this by expiring it first.
    def mock_check_exits(signals, symbol, asset_class, dataframe=None):
        results = []
        for s in signals:
            if s.status == SignalStatus.WAITING:
                # Simulate the bug: check_exits incorrectly invalidates a stale signal
                s.status = SignalStatus.INVALIDATED
                results.append(s)
        return results

    generator.check_exits.side_effect = mock_check_exits

    # Track order of calls
    call_order = []

    def append_to_call_order(method_name, original_mock):
        def wrapper(*args, **kwargs):
            call_order.append(method_name)
            # Handle both function calls and MagicMock return values
            if callable(original_mock):
                return original_mock(*args, **kwargs)
            return original_mock

        return wrapper

    # Assuming these are already patched/mocked in mock_main_dependencies
    mock_reconcile = mock_main_dependencies["reconciler"].return_value.reconcile
    mock_archive = mock_main_dependencies["trade_archival"].return_value.run
    mock_fee_patch = mock_main_dependencies["fee_patch"].return_value.run

    # Attach side effects to track order
    mock_reconcile.side_effect = append_to_call_order(
        "reconcile", mock_reconcile.return_value
    )
    mock_archive.side_effect = append_to_call_order("archive", mock_archive.return_value)
    mock_fee_patch.side_effect = append_to_call_order(
        "fee_patch", mock_fee_patch.return_value
    )

    # Execute
    main(smoke_test=False)

    # Verification
    # Expected behavior:
    # 1. check_exits called with EMPTY list (because stale signal was removed)

    # Verify check_exits call arguments
    # find the call where BTC/USD was being checked
    found_call = False
    for call_args in generator.check_exits.call_args_list:
        signals_passed = call_args[0][0]
        symbol_passed = call_args[0][1]
        if symbol_passed == "BTC/USD":
            found_call = True
            # BUG: If "stale_id" is in the signals list, then it's wrong.
            ids = [s.signal_id for s in signals_passed]
            assert (
                "stale_id" not in ids
            ), f"Stale signal should NOT be passed to check_exits, got {ids}"

    assert found_call, "check_exits was not called for BTC/USD"

    # Verify pipeline execution order (HIGH priority CR fix)
    assert call_order == [
        "reconcile",
        "archive",
        "fee_patch",
    ], f"Pipeline call order mismatch: {call_order}"

    # Also verify it was updated to EXPIRED
    # Note: repo.update_signal_atomic is called in main.py
    # repo.update_signal_atomic.assert_any_call("stale_id", ANY)

    # Find the call for EXPIRED in the update_signal_atomic mock
    expired_calls = [
        c
        for c in repo.update_signal_atomic.call_args_list
        if c[0][1].get("status") == SignalStatus.EXPIRED.value
    ]
    assert len(expired_calls) > 0, "Signal should have been updated to EXPIRED"


# =============================================================================
# REAPER ROBUSTNESS TESTS (Issue: Signals with Open Positions Marked as EXPIRED)
# =============================================================================


def test_reaper_ignores_waiting_signal_with_open_position(mock_main_dependencies):
    """
    TIER 3 REGRESSION: Verify that a WAITING signal past its valid_until time
    is NOT expired if a corresponding OPEN position exists.
    """
    repo = mock_main_dependencies["repo"].return_value
    pos_repo = mock_main_dependencies["position_repo"].return_value
    generator = mock_main_dependencies["generator"].return_value

    # 1. Setup a STALE WAITING signal
    now_utc = datetime.now(timezone.utc)
    signal_id = "live_trade_signal"
    stale_signal = SignalFactory.build(
        signal_id=signal_id,
        symbol="BTC/USD",
        status=SignalStatus.WAITING,
        valid_until=now_utc - timedelta(hours=1),
    )

    # 2. Setup a corresponding OPEN position
    open_position = PositionFactory.build(
        signal_id=signal_id,
        symbol="BTC/USD",
        status=TradeStatus.OPEN,
    )

    # 3. Configure Mocks
    repo.get_active_signals.return_value = [stale_signal]
    repo.get_by_id.return_value = stale_signal
    pos_repo.get_position_by_signal.return_value = open_position
    generator.generate_signals.return_value = None

    # 4. Execute Main
    main(smoke_test=False)

    # 5. Verification
    # Ensure update_signal_atomic was NOT called with EXPIRED for this signal
    for update_call in repo.update_signal_atomic.call_args_list:
        args, kwargs = update_call
        if args[0] == signal_id:
            updates = args[1]
            assert (
                updates.get("status") != SignalStatus.EXPIRED.value
            ), "Signal with OPEN position was incorrectly expired by reaper!"

    # Ensure it remained in valid_active_signals and was passed to check_exits
    # (The first argument to check_exits is the list of valid signals)
    found_in_check_exits = False
    for check_call in generator.check_exits.call_args_list:
        signals_list = check_call[0][0]
        if any(s.signal_id == signal_id for s in signals_list):
            found_in_check_exits = True
            break

    assert (
        found_in_check_exits
    ), "Signal protected by reaper guard was not passed to check_exits!"


def test_intra_run_active_transition(mock_main_dependencies):
    """
    TIER 1 REGRESSION: Verify that a signal transitions to ACTIVE immediately
    after successful execution in the same run.
    """
    repo = mock_main_dependencies["repo"].return_value
    generator = mock_main_dependencies["generator"].return_value
    execution_engine = mock_main_dependencies["execution_engine"].return_value
    settings = mock_main_dependencies["settings"].return_value

    # 0. Enable execution
    settings.ENABLE_EXECUTION = True

    # 1. Setup a new signal
    new_signal = SignalFactory.build(
        signal_id="new_signal_id",
        symbol="BTC/USD",
        status=SignalStatus.WAITING,
    )
    generator.generate_signals.return_value = new_signal

    # Mock repo.get_by_id to return None first (new signal), then the signal
    # This simulates the idempotency check in main.py
    repo.get_by_id.return_value = None

    # 2. Setup successful execution
    executed_position = PositionFactory.build(
        signal_id="new_signal_id",
        symbol="BTC/USD",
        trade_type=TradeType.EXECUTED,
        status=TradeStatus.OPEN,
    )
    execution_engine.execute_signal.return_value = executed_position

    # Mock Alpaca return None (no existing position) for pre-execution check
    execution_engine.alpaca.get_open_position.return_value = None

    # 3. Execute Main
    main(smoke_test=False)

    # 4. Verification
    # Ensure signal was updated to ACTIVE
    repo.update_signal_atomic.assert_any_call(
        "new_signal_id", {"status": SignalStatus.ACTIVE.value}
    )
    assert new_signal.status == SignalStatus.ACTIVE
