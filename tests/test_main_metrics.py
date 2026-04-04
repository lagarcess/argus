from unittest.mock import MagicMock, patch

from crypto_signals.main import main


def test_position_sync_metrics_failure_individual(mock_main_dependencies):
    """Test that individual position sync failure records a metric."""
    mocks = mock_main_dependencies

    # We need to explicitly mock get_metrics_collector for this test natively
    # since mock_main_dependencies does not return metrics.
    with patch("crypto_signals.main.get_metrics_collector") as mock_get_metrics:
        mock_metrics = MagicMock()
        mock_metrics.get_summary.return_value = {}
        mock_get_metrics.return_value = mock_metrics

        # Mock generator to avoid infinite loops from MagicMocks
        mocks["generator"].return_value.generate_signals.return_value = None

        # Setup open positions
        mock_pos = MagicMock()
        mock_pos.position_id = "pos-fail"
        mocks["position_repo"].return_value.get_open_positions.return_value = [mock_pos]

        mocks["settings"].return_value.ENABLE_EXECUTION = True
        mocks["settings"].return_value.CRYPTO_SYMBOLS = ["BTC/USD"]

        # Make sync raise exception
        mocks[
            "execution_engine"
        ].return_value.sync_position_status.side_effect = RuntimeError("Sync Error")

        # Run main
        main(smoke_test=False)

        # Verify record_failure called for individual position
        mock_metrics.record_failure.assert_any_call("position_sync_single", 0)


def test_position_sync_metrics_failure_global(mock_main_dependencies):
    """Test that global position sync loop failure records a metric."""
    mocks = mock_main_dependencies

    with patch("crypto_signals.main.get_metrics_collector") as mock_get_metrics:
        mock_metrics = MagicMock()
        mock_metrics.get_summary.return_value = {}
        mock_get_metrics.return_value = mock_metrics

        # Mock generator to avoid infinite loops from MagicMocks
        mocks["generator"].return_value.generate_signals.return_value = None

        mocks["settings"].return_value.ENABLE_EXECUTION = True
        mocks["settings"].return_value.CRYPTO_SYMBOLS = ["BTC/USD"]

        # Since main.py now uses StateReconciler, mock that instead of pos_repo
        with patch("crypto_signals.main.StateReconciler") as mock_reconciler:
            mock_reconciler_instance = mock_reconciler.return_value
            mock_reconciler_instance.reconcile.side_effect = RuntimeError("Sync Error")

            # Run main
            main(smoke_test=False)

            # Verify record_failure called for global sync
            calls = mock_metrics.record_failure.call_args_list
            assert any(call.args[0] == "reconciliation" for call in calls)
