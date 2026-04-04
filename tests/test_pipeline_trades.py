from crypto_signals.domain.schemas import SignalStatus
from crypto_signals.main import main

from tests.factories import SignalFactory


def test_active_trade_validation_loop(mock_main_dependencies):
    """
    Test that the main loop checks for invalidation of active signals.
    """
    mock_repo = mock_main_dependencies["repo"].return_value
    mock_generator = mock_main_dependencies["generator"].return_value

    mock_settings = mock_main_dependencies["settings"].return_value
    mock_settings.CRYPTO_SYMBOLS = ["BTC/USD"]

    active_sig = SignalFactory.build(
        status=SignalStatus.INVALIDATED,
        exit_reason=None,
    )
    active_sig._trail_updated = False
    mock_repo.get_active_signals.return_value = [active_sig]
    mock_generator.check_exits.return_value = [active_sig]
    mock_generator.generate_signals.return_value = None

    main(smoke_test=False)

    mock_repo.get_active_signals.assert_called_with("BTC/USD")
    mock_generator.check_exits.assert_called()
    mock_repo.update_signal_atomic.assert_called_with(
        active_sig.signal_id, {"status": active_sig.status.value}
    )
