import unittest
from unittest.mock import MagicMock, patch

from crypto_signals.domain.schemas import (
    AssetClass,
    OrderSide,
    Position,
    Signal,
    TradeType,
)
from crypto_signals.engine.execution import ExecutionEngine


class TestExecutionGating(unittest.TestCase):
    def setUp(self):
        # Mock settings (no spec to allow custom attributes)
        self.mock_settings = MagicMock()
        # Default to Paper Trading = True (so we only fail on ENVIRONMENT check)
        self.mock_settings.is_paper_trading = True
        self.mock_settings.ENABLE_EXECUTION = True
        self.mock_settings.RISK_PER_TRADE = 100.0
        self.mock_settings.TTL_DAYS_POSITION = 90
        self.mock_settings.MIN_ORDER_NOTIONAL_USD = 15.0
        self.mock_settings.MAX_CRYPTO_POSITION_QTY = 1_000_000.0
        self.mock_settings.MAX_EQUITY_POSITION_QTY = 10_000.0

        # Mock Trading Client
        self.mock_client = MagicMock()

        # Patch get_settings to return our mock
        self.settings_patcher = patch(
            "crypto_signals.engine.execution.get_settings",
            return_value=self.mock_settings,
        )
        self.settings_patcher.start()

        # Patch RiskEngine to pass validation by default
        self.risk_patcher = patch("crypto_signals.engine.execution.RiskEngine")
        self.MockRiskEngine = self.risk_patcher.start()
        # Configure RiskEngine instance to return passed=True
        from crypto_signals.engine.risk import RiskCheckResult

        self.MockRiskEngine.return_value.validate_signal.return_value = RiskCheckResult(
            passed=True
        )

        # Initialize engine with mocked client and repo
        self.mock_repo = MagicMock()
        self.engine = ExecutionEngine(
            trading_client=self.mock_client, repository=self.mock_repo
        )

    def tearDown(self):
        self.settings_patcher.stop()
        self.risk_patcher.stop()

    def test_gate_execute_signal_dev(self):
        """Test that execute_signal is BLOCKED in DEV environment."""
        self.mock_settings.ENVIRONMENT = "DEV"

        signal = MagicMock(spec=Signal)
        signal.symbol = "BTC/USD"
        signal.signal_id = "test_sig"
        signal.take_profit_1 = 50000
        signal.suggested_stop = 40000
        signal.entry_price = 45000
        signal.asset_class = AssetClass.CRYPTO
        signal.side = OrderSide.BUY
        signal.ds = "2023-01-01"
        signal.discord_thread_id = None

        result = self.engine.execute_signal(signal)

        # Should return a THEORETICAL Position (Simulated)
        self.assertIsNotNone(result)
        self.assertEqual(result.trade_type, "THEORETICAL")
        # Should NOT call submit_order (broker)
        self.mock_client.submit_order.assert_not_called()

    def test_gate_execute_signal_prod(self):
        """Test that execute_signal is ALLOWED in PROD environment."""
        self.mock_settings.ENVIRONMENT = "PROD"

        signal = MagicMock(spec=Signal)
        signal.symbol = "BTC/USD"
        signal.signal_id = "test_sig"
        signal.take_profit_1 = 50000
        signal.suggested_stop = 40000
        signal.entry_price = 45000
        signal.asset_class = AssetClass.CRYPTO
        signal.ds = "2023-01-01"
        signal.discord_thread_id = None
        signal.side = None

        # Mock successful order
        mock_order = MagicMock()
        mock_order.id = "order_123"
        mock_order.status = "new"
        self.mock_client.submit_order.return_value = mock_order

        result = self.engine.execute_signal(signal)

        # Should return a Position
        self.assertIsInstance(result, Position)
        # Should call submit_order
        self.mock_client.submit_order.assert_called_once()

    def test_gate_sync_position_dev(self):
        """Test that sync_position skipped in DEV."""
        self.mock_settings.ENVIRONMENT = "DEV"

        pos = MagicMock()
        pos.position_id = "pos_1"
        pos.alpaca_order_id = "ord_1"
        pos.trade_type = TradeType.THEORETICAL
        pos.sl_order_id = None
        pos.tp_order_id = None
        pos.current_stop_loss = 40000.0
        pos.qty = 1.0
        pos.entry_fill_price = 50000.0
        pos.symbol = "BTC/USD"
        pos.side = OrderSide.BUY

        # Call sync
        self.engine.sync_position_status(pos)

        # Should NOT call get_order_by_id
        self.mock_client.get_order_by_id.assert_not_called()

    def test_gate_modify_stop_dev(self):
        """Test that modify_stop_loss is skipped (simulated success) in DEV."""
        self.mock_settings.ENVIRONMENT = "DEV"

        pos = MagicMock()
        pos.position_id = "pos_1"
        pos.trade_type = TradeType.THEORETICAL
        pos.sl_order_id = None
        pos.tp_order_id = None
        pos.current_stop_loss = 40000.0
        pos.qty = 1.0
        pos.entry_fill_price = 50000.0
        pos.symbol = "BTC/USD"
        pos.side = OrderSide.BUY

        result = self.engine.modify_stop_loss(pos, 42000)

        # Should return True (simulated success)
        self.assertTrue(result)
        # Should NOT call replace_order
        self.mock_client.replace_order_by_id.assert_not_called()
