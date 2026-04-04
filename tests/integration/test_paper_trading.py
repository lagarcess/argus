from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.domain.schemas import (
    AssetClass,
    SignalStatus,
    TradeType,
)
from crypto_signals.engine.execution import ExecutionEngine

from tests.factories import SignalFactory


@pytest.mark.integration
class TestPaperTradingFlow:
    """
    Integration tests for the full order lifecycle using mocked Alpaca responses
    simulating paper trading behavior.
    """

    @pytest.fixture
    def mock_alpaca(self):
        with patch("crypto_signals.engine.execution.TradingClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def execution_engine(self, mock_alpaca):
        # Create a concrete mock settings object to avoid MagicMock comparison issues
        class MockSettings:
            ENVIRONMENT = "PROD"
            ALPACA_PAPER_TRADING = True
            ENABLE_EXECUTION = True
            RISK_PER_TRADE = 100.0
            TTL_DAYS_POSITION = 30

            @property
            def is_paper_trading(self):
                return self.ALPACA_PAPER_TRADING

        settings_instance = MockSettings()

        # Patch get_settings to return our concrete object
        with patch("crypto_signals.engine.execution.get_settings") as mock_get_settings:
            mock_get_settings.return_value = settings_instance

            # Pass mock_alpaca directly to constructor injection
            engine = ExecutionEngine(trading_client=mock_alpaca)
            yield engine

    def test_crypto_order_lifecycle_integration(self, execution_engine, mock_alpaca):
        """
        Verify the full lifecycle of a crypto trade:
        1. Signal Entry -> Simple Market Order
        2. Position Tracking -> Manual SL/TP
        3. TP1 Hit -> Move Stop to Breakeven
        """
        # 1. Setup Crypto Signal
        signal = SignalFactory.build(
            signal_id="test_crypto_sig_001",
            strategy_id="BULL_FLAG",
            pattern_name="BULL_FLAG",
            symbol="BTC/USD",
            ds=datetime.now(timezone.utc).date(),
            asset_class=AssetClass.CRYPTO,
            status=SignalStatus.WAITING,
            entry_price=50000.0,
            take_profit_1=51000.0,
            take_profit_2=52000.0,
            suggested_stop=49000.0,
            trade_type=TradeType.EXECUTED,
            created_at=datetime.now(timezone.utc),
        )

        # Mock Order Response
        mock_order = MagicMock()
        mock_order.id = "alpaca_order_123"
        mock_order.status = "filled"
        mock_order.filled_avg_price = "50050.0"  # Slight slippage
        mock_order.filled_qty = "0.1"
        mock_order.side = "buy"
        mock_alpaca.submit_order.return_value = mock_order

        # 2. Execute Signal
        position = execution_engine.execute_signal(signal)

        # Verification 1: Order Submission
        assert position is not None, "Position should be created"
        mock_alpaca.submit_order.assert_called_once()
        # submit_order is called positionally: submit_order(order_request)
        order_req = mock_alpaca.submit_order.call_args[0][0]

        assert order_req.symbol == "BTC/USD"
        assert order_req.side.value == "buy"
        assert order_req.type.value == "market"
        assert order_req.time_in_force.value == "gtc"
        # Crucial: No take_profit or stop_loss params for crypto
        assert order_req.take_profit is None
        assert order_req.stop_loss is None

        # 3. Verify Position Object
        assert position.position_id == signal.signal_id
        assert position.trade_type == TradeType.EXECUTED
        assert position.current_stop_loss == 49000.0

        # 4. Simulate Move to Breakeven
        # Execute Move to Breakeven on the returned position
        result = execution_engine.move_stop_to_breakeven(position)

        # Verification 2: Breakeven Update
        # For crypto, this should NOT call replace_order
        mock_alpaca.replace_order.assert_not_called()
        assert result is True

        # It SHOULD update the position object locally
        # 50000.0 * 1.001 = 50050.0
        assert position.current_stop_loss == 50050.0
        assert position.breakeven_applied is True

    def test_equity_order_lifecycle_integration(self, execution_engine, mock_alpaca):
        """
        Verify the full lifecycle of an equity trade (Regression Test):
        1. Signal Entry -> Bracket Order
        """
        # 1. Setup Equity Signal
        signal = SignalFactory.build(
            signal_id="test_equity_sig_001",
            strategy_id="BULL_FLAG",
            pattern_name="BULL_FLAG",
            symbol="AAPL",
            ds=datetime.now(timezone.utc).date(),
            asset_class=AssetClass.EQUITY,
            status=SignalStatus.WAITING,
            entry_price=150.0,
            take_profit_1=155.0,
            take_profit_2=160.0,
            suggested_stop=145.0,
            trade_type=TradeType.EXECUTED,
            created_at=datetime.now(timezone.utc),
        )

        # Mock Order Response
        mock_order = MagicMock()
        mock_order.id = "alpaca_order_456"
        mock_order.status = "new"  # Bracket orders start as new
        mock_alpaca.submit_order.return_value = mock_order

        # 2. Execute Signal
        position = execution_engine.execute_signal(signal)

        # Verification: Bracket Order
        assert position is not None, "Equity Position should be created"
        order_req = mock_alpaca.submit_order.call_args[0][0]

        assert order_req.symbol == "AAPL"
        assert order_req.order_class.value == "bracket"  # Bracket
        assert order_req.take_profit is not None
        assert order_req.stop_loss is not None
