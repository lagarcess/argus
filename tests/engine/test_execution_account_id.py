from unittest.mock import MagicMock, patch

from crypto_signals.domain.schemas import OrderSide
from crypto_signals.engine.execution import ExecutionEngine

from tests.factories import SignalFactory


class TestExecutionAccountID:
    def test_account_id_is_used_instead_of_hardcoded_string(self):
        """
        Verify that ExecutionEngine uses the real Alpaca Account UUID
        instead of hardcoded 'paper' or 'live' strings.
        """
        # Mock Settings to enable execution
        mock_settings = MagicMock()
        mock_settings.is_paper_trading = True
        mock_settings.ENABLE_EXECUTION = True
        mock_settings.ENVIRONMENT = "PROD"
        mock_settings.RISK_PER_TRADE = 100.0
        mock_settings.TTL_DAYS_POSITION = 90
        mock_settings.MIN_ORDER_NOTIONAL_USD = 10.0
        mock_settings.MAX_CRYPTO_POSITION_QTY = 1_000_000.0
        mock_settings.MAX_EQUITY_POSITION_QTY = 10_000.0

        # Mock Trading Client
        mock_trading_client = MagicMock()

        # Mock Account with a specific UUID
        expected_account_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        mock_account = MagicMock()
        mock_account.id = expected_account_id
        mock_trading_client.get_account.return_value = mock_account

        # Mock Order submission response
        mock_order = MagicMock()
        mock_order.id = "test-order-id"
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Sample Signal
        signal = SignalFactory.build(
            signal_id="test-signal-uuid",
            strategy_id="TEST",
            pattern_name="TEST",
            side=OrderSide.BUY,
        )

        with (
            patch(
                "crypto_signals.engine.execution.get_settings", return_value=mock_settings
            ),
            patch("crypto_signals.engine.execution.RiskEngine") as MockRiskEngine,
        ):
            # Configure RiskEngine to PASS
            mock_risk_instance = MockRiskEngine.return_value
            from crypto_signals.engine.risk import RiskCheckResult

            mock_risk_instance.validate_signal.return_value = RiskCheckResult(passed=True)

            # Initialize Engine
            engine = ExecutionEngine(
                trading_client=mock_trading_client, repository=MagicMock()
            )

            # Act
            position = engine.execute_signal(signal)

            # Assert
            assert position is not None, "position should not be None"
            # THIS ASSERTION SHOULD FAIL until the fix is implemented
            # Currently it returns "paper"
            assert (
                position.account_id == expected_account_id
            ), f"Expected account_id {expected_account_id}, but got {position.account_id}"

    def test_account_id_defaults_to_unknown_on_error(self):
        """
        Verify that ExecutionEngine defaults account_id to 'unknown'
        when the Alpaca API fails.
        """
        mock_trading_client = MagicMock()
        from alpaca.common.exceptions import APIError

        # Simulate API Error
        mock_trading_client.get_account.side_effect = APIError("API Connection Failed")

        with patch("crypto_signals.engine.execution.get_settings") as mock_settings_ref:
            mock_settings = mock_settings_ref.return_value
            mock_settings.ENVIRONMENT = "PROD"

            # Allow initialization despite error (via try-except block)
            engine = ExecutionEngine(
                trading_client=mock_trading_client, repository=MagicMock()
            )

            assert (
                engine.account_id == "unknown"
            ), 'Expected engine.account_id == "unknown"'
