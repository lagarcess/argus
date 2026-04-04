"""Unit tests for the ExecutionEngine module."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from alpaca.trading.enums import OrderClass
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from crypto_signals.domain.schemas import (
    AssetClass,
    ExitReason,
    OrderSide,
    TradeStatus,
    TradeType,
)
from crypto_signals.engine.execution import ExecutionEngine

from tests.factories import PositionFactory, SignalFactory


@pytest.fixture
def mock_settings():
    """Fixture for mocking settings."""
    mock = MagicMock()
    mock.is_paper_trading = True
    mock.ENABLE_EXECUTION = True
    mock.RISK_PER_TRADE = 100.0
    mock.ENVIRONMENT = "PROD"
    mock.TTL_DAYS_POSITION = 90
    mock.MIN_ORDER_NOTIONAL_USD = 15.0
    mock.MAX_CRYPTO_POSITION_QTY = 1_000_000.0
    mock.MAX_EQUITY_POSITION_QTY = 10_000.0
    return mock


@pytest.fixture
def mock_trading_client():
    """Fixture for mocking TradingClient."""
    return MagicMock()


@pytest.fixture
def sample_signal():
    """Create a sample BUY signal for testing."""
    return SignalFactory.build()


@pytest.fixture
def sample_sell_signal():
    """Create a sample SELL signal for testing short positions."""
    return SignalFactory.build(
        signal_id="test-signal-sell-456",
        strategy_id="BEARISH_ENGULFING",
        pattern_name="BEARISH_ENGULFING",
        suggested_stop=52000.0,  # Stop ABOVE entry for short
        take_profit_1=45000.0,  # TP BELOW entry for short
        take_profit_2=40000.0,
        side=OrderSide.SELL,
    )


@pytest.fixture
def sample_equity_signal():
    """Create a sample equity BUY signal for testing bracket orders.

    Bracket orders (OTOCO) are only supported for equities, not crypto.
    """
    return SignalFactory.build(
        signal_id="test-signal-equity-789",
        symbol="AAPL",
        asset_class=AssetClass.EQUITY,
        entry_price=150.0,
        suggested_stop=145.0,
        take_profit_1=160.0,
        take_profit_2=170.0,
    )


@pytest.fixture
def execution_engine(mock_settings, mock_trading_client):
    """Create an ExecutionEngine with mocked dependencies."""
    with (
        patch("crypto_signals.engine.execution.get_settings", return_value=mock_settings),
        patch("crypto_signals.engine.execution.RiskEngine") as MockRiskEngine,
    ):
        # Configure default RiskEngine behavior to Pass
        mock_risk_instance = MockRiskEngine.return_value
        from crypto_signals.engine.risk import RiskCheckResult

        mock_risk_instance.validate_signal.return_value = RiskCheckResult(passed=True)

        # Mock Repository to avoid Firestore Auth
        mock_repo = MagicMock()
        engine = ExecutionEngine(trading_client=mock_trading_client, repository=mock_repo)
        yield engine


class TestExecuteSignal:
    """Tests for the execute_signal method."""

    def test_bracket_order_construction(
        self, execution_engine, sample_equity_signal, mock_trading_client
    ):
        """Verify MarketOrderRequest is constructed with OrderClass.BRACKET for equity.

        Note: Bracket orders (OTOCO) are only supported for equities, not crypto.
        """
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-123"
        mock_order.client_order_id = sample_equity_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        position = execution_engine.execute_signal(sample_equity_signal)

        # Assert
        assert position is not None, "Execution failed to return a position object"
        mock_trading_client.submit_order.assert_called_once()

        # Get the order request that was passed
        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]  # First positional argument

        assert (
            order_request.order_class == OrderClass.BRACKET
        ), f"Expected BRACKET order class, got {order_request.order_class}"

    def test_take_profit_matches_signal(
        self, execution_engine, sample_equity_signal, mock_trading_client
    ):
        """Verify take_profit param matches signal's take_profit_1 for equity bracket orders."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-123"
        mock_order.client_order_id = sample_equity_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        execution_engine.execute_signal(sample_equity_signal)

        # Assert
        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]

        assert order_request.take_profit.limit_price == round(
            sample_equity_signal.take_profit_1, 2
        ), "Take profit price mismatch in order request"

    def test_stop_loss_matches_signal(
        self, execution_engine, sample_equity_signal, mock_trading_client
    ):
        """Verify stop_loss param matches signal's suggested_stop for equity bracket orders."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-123"
        mock_order.client_order_id = sample_equity_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        execution_engine.execute_signal(sample_equity_signal)

        # Assert
        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]

        assert order_request.stop_loss.stop_price == round(
            sample_equity_signal.suggested_stop, 2
        ), "Stop loss price mismatch in order request"

    def test_client_order_id_matches_signal_id(
        self, execution_engine, sample_signal, mock_trading_client
    ):
        """Verify client_order_id equals signal.signal_id for traceability."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-123"
        mock_order.client_order_id = sample_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        execution_engine.execute_signal(sample_signal)

        # Assert
        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]

        assert (
            order_request.client_order_id == sample_signal.signal_id
        ), "client_order_id does not match signal_id"

    def test_qty_calculation(self, execution_engine, sample_signal, mock_trading_client):
        """Verify qty calculation: RISK_PER_TRADE / (entry_price - stop_loss)."""
        # Arrange
        # RISK_PER_TRADE = 100, entry = 50000, stop = 48000
        # Risk per share = 50000 - 48000 = 2000
        # Expected qty = 100 / 2000 = 0.05
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-123"
        mock_order.client_order_id = sample_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        execution_engine.execute_signal(sample_signal)

        # Assert
        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]

        expected_qty = round(100.0 / 2000.0, 6)
        assert (
            order_request.qty == expected_qty
        ), f"Quantity mismatch. Expected {expected_qty}, got {order_request.qty}"

    def test_execution_blocked_when_not_paper_trading(
        self, sample_signal, mock_trading_client
    ):
        """Verify execution is blocked when ALPACA_PAPER_TRADING=False."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.is_paper_trading = False
        mock_settings.ENABLE_EXECUTION = True
        mock_settings.TTL_DAYS_POSITION = 90
        mock_settings.MAX_CRYPTO_POSITION_QTY = 1_000_000.0
        mock_settings.MAX_EQUITY_POSITION_QTY = 10_000.0
        # Determine environment to test fallback
        mock_settings.ENVIRONMENT = "PROD"
        mock_settings.RISK_PER_TRADE = 100.0

        with (
            patch(
                "crypto_signals.engine.execution.get_settings", return_value=mock_settings
            ),
            patch("crypto_signals.engine.execution.RiskEngine") as MockRiskEngine,
        ):
            # Configure RiskEngine to PASS
            MockRiskEngine.return_value.validate_signal.return_value.passed = True

            # Mock Repo to avoid Firestore Auth
            mock_repo = MagicMock()
            engine = ExecutionEngine(
                trading_client=mock_trading_client, repository=mock_repo
            )

            # Act
            position = engine.execute_signal(sample_signal)

            # Assert
            mock_trading_client.submit_order.assert_not_called()

            assert position is not None, "Execution failed to return a position object"
            assert (
                position.trade_type == "THEORETICAL"
            ), f"Expected THEORETICAL trade type, got {position.trade_type}"

    def test_execution_blocked_when_disabled(self, sample_signal, mock_trading_client):
        """Verify execution is blocked when ENABLE_EXECUTION=False."""
        # Arrange
        mock_settings = MagicMock()
        mock_settings.is_paper_trading = True
        mock_settings.ENABLE_EXECUTION = False
        mock_settings.ENVIRONMENT = "PROD"
        mock_settings.RISK_PER_TRADE = 100.0
        mock_settings.TTL_DAYS_POSITION = 90
        mock_settings.MAX_CRYPTO_POSITION_QTY = 1_000_000.0
        mock_settings.MAX_EQUITY_POSITION_QTY = 10_000.0

        with (
            patch(
                "crypto_signals.engine.execution.get_settings", return_value=mock_settings
            ),
            patch("crypto_signals.engine.execution.RiskEngine") as MockRiskEngine,
        ):
            # Configure RiskEngine to PASS
            # Configure RiskEngine to PASS
            MockRiskEngine.return_value.validate_signal.return_value.passed = True

            # Mock Repo to avoid Firestore Auth
            mock_repo = MagicMock()
            engine = ExecutionEngine(
                trading_client=mock_trading_client, repository=mock_repo
            )

            # Act
            position = engine.execute_signal(sample_signal)

            # Assert
            mock_trading_client.submit_order.assert_not_called()

            assert position is not None, "position should not be None"
            assert (
                position.trade_type == "THEORETICAL"
            ), 'Expected position.trade_type == "THEORETICAL"'

    def test_position_created_on_success(
        self, execution_engine, sample_signal, mock_trading_client
    ):
        """Verify Position object is created with correct fields on success."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-123"
        mock_order.client_order_id = sample_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        position = execution_engine.execute_signal(sample_signal)

        # Assert
        assert position is not None, "Execution failed to return a position object"
        assert (
            position.position_id == sample_signal.signal_id
        ), "position_id does not match signal_id"
        assert position.delete_at is not None, "delete_at timestamp missing in position"
        assert (
            position.signal_id == sample_signal.signal_id
        ), "signal_id mismatch in position"
        assert (
            position.current_stop_loss == sample_signal.suggested_stop
        ), "current_stop_loss mismatch in position"
        assert (
            position.entry_fill_price == sample_signal.entry_price
        ), "entry_fill_price mismatch in position"
        assert position.side == sample_signal.side, "side mismatch in position"

    def test_sell_order_side(
        self, execution_engine, sample_sell_signal, mock_trading_client
    ):
        """Verify SELL signals submit orders with OrderSide.SELL."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-sell-789"
        mock_order.client_order_id = sample_sell_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        position = execution_engine.execute_signal(sample_sell_signal)

        # Assert
        assert position is not None, "Execution failed to return a position object"
        mock_trading_client.submit_order.assert_called_once()

        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]

        assert (
            order_request.side == AlpacaOrderSide.SELL
        ), "Order request side is not SELL"
        assert position.side == OrderSide.SELL, "Position side is not SELL"


class TestCryptoOrderFlow:
    """Tests for crypto-specific order flow (simple market orders, no bracket).

    Alpaca doesn't support OTOCO/bracket orders for crypto. Instead, we use
    simple market orders for entry and track SL/TP manually for exits.
    """

    def test_crypto_uses_simple_market_order(
        self, execution_engine, sample_signal, mock_trading_client
    ):
        """Verify crypto orders do NOT include order_class (no bracket)."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-crypto-123"
        mock_order.client_order_id = sample_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        position = execution_engine.execute_signal(sample_signal)

        # Assert
        assert position is not None, "position should not be None"
        mock_trading_client.submit_order.assert_called_once()

        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]

        assert (
            order_request.order_class is None
        ), "Crypto order should not have an order_class (should be None)"

    def test_crypto_uses_gtc_time_in_force(
        self, execution_engine, sample_signal, mock_trading_client
    ):
        """Verify crypto orders use GTC time_in_force (required by Alpaca)."""
        from alpaca.trading.enums import TimeInForce

        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-crypto-gtc"
        mock_order.client_order_id = sample_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        execution_engine.execute_signal(sample_signal)

        # Assert
        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]

        assert (
            order_request.time_in_force == TimeInForce.GTC
        ), "Crypto order must use GTC time_in_force"

    def test_crypto_position_has_manual_sl_tp_fields(
        self, execution_engine, sample_signal, mock_trading_client
    ):
        """Verify Position stores SL/TP for manual exit tracking."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-crypto-sltp"
        mock_order.client_order_id = sample_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        position = execution_engine.execute_signal(sample_signal)

        # Assert
        assert position is not None, "Execution failed to return a position object"
        assert (
            position.current_stop_loss == sample_signal.suggested_stop
        ), "Position stopped loss not initialized correctly"
        assert (
            position.tp_order_id is None
        ), "Crypto position should not have tp_order_id initially"
        assert (
            position.sl_order_id is None
        ), "Crypto position should not have sl_order_id initially"

    def test_crypto_no_take_profit_in_order(
        self, execution_engine, sample_signal, mock_trading_client
    ):
        """Verify crypto orders do NOT include take_profit parameter."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-crypto-notp"
        mock_order.client_order_id = sample_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        execution_engine.execute_signal(sample_signal)

        # Assert
        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]

        assert (
            not hasattr(order_request, "take_profit") or order_request.take_profit is None
        ), "Crypto order request should not have take_profit set"

    def test_crypto_no_stop_loss_in_order(
        self, execution_engine, sample_signal, mock_trading_client
    ):
        """Verify crypto orders do NOT include stop_loss parameter."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-crypto-nosl"
        mock_order.client_order_id = sample_signal.signal_id
        mock_order.status = "accepted"
        mock_trading_client.submit_order.return_value = mock_order

        # Act
        execution_engine.execute_signal(sample_signal)

        # Assert
        call_args = mock_trading_client.submit_order.call_args
        order_request = call_args[0][0]

        assert (
            not hasattr(order_request, "stop_loss") or order_request.stop_loss is None
        ), "Crypto order request should not have stop_loss set"


class TestValidateSignal:
    """Tests for signal validation."""

    def test_missing_take_profit_fails(self, execution_engine):
        """Verify validation fails when take_profit_1 is missing."""
        # Arrange
        signal = SignalFactory.build(
            signal_id="test-signal",
            strategy_id="TEST",
            pattern_name="TEST",
            take_profit_1=None,  # Missing!
        )

        # Act
        result = execution_engine._validate_signal(signal)

        # Assert
        assert result is False, "Validation should fail when take_profit_1 is missing"

    def test_missing_stop_fails(self, execution_engine):
        """Verify validation fails when suggested_stop is missing."""
        # Arrange
        signal = SignalFactory.build(
            signal_id="test-signal",
            strategy_id="TEST",
            pattern_name="TEST",
            suggested_stop=0,  # Invalid!
        )

        # Act
        result = execution_engine._validate_signal(signal)

        # Assert
        assert result is False, "Validation should fail when suggested_stop is 0"

    def test_negative_stop_fails(self, execution_engine):
        """Verify validation fails when suggested_stop is negative."""
        # Arrange
        signal = SignalFactory.build(
            signal_id="test-signal",
            strategy_id="TEST",
            pattern_name="TEST",
            suggested_stop=-100.0,  # Negative is invalid
        )

        # Act
        result = execution_engine._validate_signal(signal)

        # Assert
        assert result is False, "Validation should fail when suggested_stop is negative"


class TestCalculateQty:
    """Tests for position size calculation."""

    def test_crypto_fractional_shares(self, execution_engine, sample_signal):
        """Verify crypto allows fractional shares with 6 decimals."""
        # Arrange
        # sample_signal: entry=50000, stop=48000, risk_distance=2000

        # Act
        qty = execution_engine._calculate_qty(sample_signal)

        # Assert
        # Crypto should be rounded to 6 decimals: 100 / 2000 = 0.05
        assert qty == round(100.0 / 2000.0, 6), "Qty calculation incorrect for crypto"

    def test_equity_fractional_shares(self, execution_engine):
        """Verify equity uses 4 decimal precision."""
        # Arrange
        signal = SignalFactory.build(
            signal_id="test-signal",
            strategy_id="TEST",
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            entry_price=150.0,
            pattern_name="TEST",
            suggested_stop=145.0,
            take_profit_1=160.0,
        )

        # Act
        qty = execution_engine._calculate_qty(signal)

        # Assert
        # Equity should be rounded to 4 decimals: 100 / (150 - 145) = 20
        assert qty == round(100.0 / 5.0, 4), "Qty calculation incorrect for equity"


class TestErrorHandling:
    """Tests for error handling and Rich error panels."""

    def test_api_failure_returns_none(
        self, execution_engine, sample_signal, mock_trading_client
    ):
        """Verify API failure returns None and doesn't raise."""
        # Arrange - simulate Alpaca API failure
        mock_trading_client.submit_order.side_effect = Exception(
            "Insufficient buying power"
        )

        # Act
        position = execution_engine.execute_signal(sample_signal)

        # Assert
        assert position is None, "Position should be None on API failure"


class TestGetOrderDetails:
    """Tests for the get_order_details method."""

    def test_get_order_details_success(self, execution_engine, mock_trading_client):
        """Verify successful order retrieval."""
        # Arrange
        mock_order = MagicMock()
        mock_order.id = "order-123"
        mock_order.status = "filled"
        mock_trading_client.get_order_by_id.return_value = mock_order

        # Act
        order = execution_engine.get_order_details("order-123")

        # Assert
        assert order is not None, "get_order_details returned None for existing order"
        assert order.status == "filled", "Order status mismatch"
        mock_trading_client.get_order_by_id.assert_called_once_with("order-123")

    def test_get_order_details_not_found(self, execution_engine, mock_trading_client):
        """Verify returns None when order not found."""
        # Arrange
        mock_trading_client.get_order_by_id.side_effect = Exception("Order not found")

        # Act
        order = execution_engine.get_order_details("nonexistent-order")

        # Assert
        assert order is None, "get_order_details should return None for nonexistent order"


class TestSyncPositionStatus:
    """Tests for the sync_position_status method."""

    def test_sync_extracts_leg_ids(self, execution_engine, mock_trading_client):
        """Verify TP and SL leg IDs are extracted from filled parent order."""
        # Arrange
        mock_tp_leg = MagicMock()
        mock_tp_leg.id = "tp-leg-uuid-123"
        mock_tp_leg.order_type = "limit"
        mock_tp_leg.status = "new"

        mock_sl_leg = MagicMock()
        mock_sl_leg.id = "sl-leg-uuid-456"
        mock_sl_leg.order_type = "stop"
        mock_sl_leg.status = "new"

        mock_order = MagicMock()
        mock_order.id = "parent-order-123"
        mock_order.status = "filled"
        # Use real datetime objects, not strings, as expected by calculation logic

        mock_order.filled_at = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        mock_order.filled_avg_price = "50100.0"
        mock_order.legs = [mock_tp_leg, mock_sl_leg]

        mock_trading_client.get_order_by_id.return_value = mock_order

        # Create position
        position = PositionFactory.build(
            position_id="test-pos-1",
            signal_id="test-signal-1",
            alpaca_order_id="parent-order-123",
            qty=0.05,
        )

        # Act
        updated = execution_engine.sync_position_status(position)

        # Assert
        assert updated.tp_order_id == "tp-leg-uuid-123", "TP order ID mismatch"
        assert updated.sl_order_id == "sl-leg-uuid-456", "SL order ID mismatch"
        assert updated.entry_fill_price == 50100.0, "Entry fill price mismatch"

    def test_sync_detects_external_close_via_tp(
        self, execution_engine, mock_trading_client
    ):
        """Verify position marked CLOSED when TP order is filled."""

        # Arrange
        mock_parent = MagicMock()
        mock_parent.status = "filled"
        mock_parent.filled_at = None
        mock_parent.filled_avg_price = None
        mock_parent.legs = []

        mock_tp_order = MagicMock()
        mock_tp_order.status = "filled"

        def side_effect(order_id):
            if order_id == "parent-id":
                return mock_parent
            elif order_id == "tp-order-id":
                return mock_tp_order
            return None

        mock_trading_client.get_order_by_id.side_effect = side_effect

        position = PositionFactory.build(
            position_id="test-pos-2",
            signal_id="test-signal-2",
            alpaca_order_id="parent-id",
            tp_order_id="tp-order-id",
            qty=0.05,
        )

        # Act
        updated = execution_engine.sync_position_status(position)

        # Assert
        assert (
            updated.status == TradeStatus.CLOSED
        ), "Position status should be CLOSED after TP fill"

    def test_sync_captures_exit_fill_price_on_tp_fill(
        self, execution_engine, mock_trading_client
    ):
        """Verify exit_fill_price is captured when TP order is filled."""

        # Arrange
        mock_parent = MagicMock()
        mock_parent.status = "filled"
        mock_parent.filled_at = None
        mock_parent.filled_avg_price = None
        mock_parent.legs = []

        mock_tp_order = MagicMock()
        mock_tp_order.status = "filled"
        mock_tp_order.filled_avg_price = "55000.0"
        mock_tp_order.filled_at = datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc)

        def side_effect(order_id):
            if order_id == "parent-id":
                return mock_parent
            elif order_id == "tp-order-id":
                return mock_tp_order
            return None

        mock_trading_client.get_order_by_id.side_effect = side_effect

        position = PositionFactory.build(
            position_id="test-pos-exit",
            signal_id="test-signal-exit",
            alpaca_order_id="parent-id",
            tp_order_id="tp-order-id",
            qty=0.05,
        )

        # Act
        updated = execution_engine.sync_position_status(position)

        # Assert
        assert (
            updated.status == TradeStatus.CLOSED
        ), "Position status should be CLOSED after TP fill"
        assert updated.exit_fill_price == 55000.0, "Exit fill price mismatch"
        assert updated.exit_time == datetime(
            2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc
        ), "Exit time mismatch"

    def test_sync_captures_exit_details_on_sl_fill(
        self, execution_engine, mock_trading_client
    ):
        """Verify exit_fill_price is captured when SL order is filled."""

        # Arrange
        mock_parent = MagicMock()
        mock_parent.status = "filled"
        mock_parent.filled_at = None
        mock_parent.filled_avg_price = None
        mock_parent.legs = []

        mock_tp_order = MagicMock()
        mock_tp_order.status = "new"  # TP not filled

        mock_sl_order = MagicMock()
        mock_sl_order.status = "filled"
        mock_sl_order.filled_avg_price = "48000.0"
        mock_sl_order.filled_at = datetime(2025, 1, 15, 16, 0, 0, tzinfo=timezone.utc)

        def side_effect(order_id):
            if order_id == "parent-id":
                return mock_parent
            elif order_id == "tp-order-id":
                return mock_tp_order
            elif order_id == "sl-order-id":
                return mock_sl_order
            return None

        mock_trading_client.get_order_by_id.side_effect = side_effect

        position = PositionFactory.build(
            position_id="test-pos-sl-exit",
            signal_id="test-signal-sl-exit",
            alpaca_order_id="parent-id",
            tp_order_id="tp-order-id",
            sl_order_id="sl-order-id",
            qty=0.05,
        )

        # Act
        updated = execution_engine.sync_position_status(position)

        # Assert
        assert (
            updated.status == TradeStatus.CLOSED
        ), "Position status should be CLOSED after SL fill"
        assert updated.exit_fill_price == 48000.0, "Exit fill price mismatch"
        assert updated.exit_time == datetime(
            2025, 1, 15, 16, 0, 0, tzinfo=timezone.utc
        ), "Exit time mismatch"

    def test_sync_detects_manual_exit_when_not_found(
        self, execution_engine, mock_trading_client
    ):
        """Verify position marked CLOSED (Manual Exit) when not found on Alpaca."""

        # Arrange
        mock_parent = MagicMock()
        mock_parent.status = "filled"
        mock_parent.legs = []  # No active legs found (or irrelevant)

        mock_trading_client.get_open_position.side_effect = Exception(
            "position not found (404)"
        )

        mock_close_order = MagicMock()
        mock_close_order.id = "manual-close-id"
        mock_close_order.status = "filled"
        mock_close_order.filled_avg_price = "52000.0"
        mock_close_order.filled_at = datetime(2025, 1, 15, 17, 0, 0, tzinfo=timezone.utc)

        mock_trading_client.get_orders.return_value = [mock_close_order]
        mock_trading_client.get_order_by_id.return_value = mock_parent

        position = PositionFactory.build(
            position_id="test-pos-manual",
            signal_id="test-signal-manual",
            alpaca_order_id="parent-id",
            qty=0.05,
        )

        mock_reconciler = MagicMock()

        def mock_handle(p):
            p.status = TradeStatus.CLOSED
            p.exit_reason = ExitReason.MANUAL_EXIT
            p.exit_fill_price = 52000.0
            p.exit_time = datetime(2025, 1, 15, 17, 0, 0, tzinfo=timezone.utc)
            return True

        mock_reconciler.handle_manual_exit_verification.side_effect = mock_handle
        execution_engine.reconciler = mock_reconciler

        # Act
        updated = execution_engine.sync_position_status(position)

        # Assert
        assert (
            updated.status == TradeStatus.CLOSED
        ), "Position status should be CLOSED on manual exit"
        assert (
            updated.exit_reason == ExitReason.MANUAL_EXIT
        ), "Exit reason should be MANUAL_EXIT"
        assert updated.exit_fill_price == 52000.0, "Exit fill price mismatch"
        assert updated.exit_time == datetime(
            2025, 1, 15, 17, 0, 0, tzinfo=timezone.utc
        ), "Exit time mismatch"

        mock_reconciler.handle_manual_exit_verification.assert_called_once_with(position)

    @pytest.mark.parametrize(
        "status",
        [
            pytest.param("accepted", id="queued_accepted"),
            pytest.param("pending_new", id="queued_pending"),
            pytest.param("new", id="queued_new"),
        ],
    )
    def test_sync_handles_queued_statuses(
        self, execution_engine, mock_trading_client, status
    ):
        """Verify that queued order statuses produce an INFO log and stay OPEN."""
        # Arrange
        mock_order = MagicMock()
        mock_order.status = status
        mock_order.id = "queued-order-id"
        mock_trading_client.get_order_by_id.return_value = mock_order

        # Position is initially OPEN with no fill data
        position = PositionFactory.build(
            position_id="queued-pos-123",
            symbol="AAPL",
            alpaca_order_id="queued-order-id",
            status=TradeStatus.OPEN,
            entry_fill_price=100.0,  # Pre-existing value
            filled_at=None,
            created_at=datetime(
                2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc
            ),  # Fixed timestamp to skip manual exit check
        )

        # Mock get_open_position to return 404 (no position yet for queued order)
        mock_trading_client.get_open_position.side_effect = Exception(
            "position not found (404)"
        )

        # Act
        with patch("crypto_signals.engine.execution.logger") as mock_logger:
            updated = execution_engine.sync_position_status(position)

        # Assert
        assert (
            updated.status == TradeStatus.OPEN
        ), f"Expected OPEN for queued order status={status}, got {updated.status}"

        # Ensure no fill data was updated (it should remain as it was)
        assert updated.entry_fill_price == 100.0
        assert updated.filled_at is None

        # Verify informational log
        mock_logger.info.assert_called_with(
            f"Position {position.position_id} order still queued "
            f"(status: {status}). Will sync on next cycle after fill.",
            extra={
                "symbol": position.symbol,
                "order_status": status,
                "position_id": position.position_id,
            },
        )


class TestModifyStopLoss:
    """Tests for the modify_stop_loss method."""

    def test_modify_stop_loss_success(self, execution_engine, mock_trading_client):
        """Verify stop loss can be replaced when in replaceable state."""
        # Arrange
        mock_sl_order = MagicMock()
        mock_sl_order.status = "new"

        mock_replaced_order = MagicMock()
        mock_replaced_order.id = "new-sl-order-id"

        mock_trading_client.get_order_by_id.return_value = mock_sl_order
        mock_trading_client.replace_order_by_id.return_value = mock_replaced_order

        position = PositionFactory.build(
            position_id="test-pos-3",
            signal_id="test-signal-3",
            alpaca_order_id="parent-id",
            sl_order_id="old-sl-order-id",
            qty=0.05,
        )

        # Act
        result = execution_engine.modify_stop_loss(position, 49000.0)

        # Assert
        assert result is True, "modify_stop_loss failed to return True"
        assert position.sl_order_id == "new-sl-order-id", "SL order ID was not updated"
        assert position.current_stop_loss == 49000.0, "current_stop_loss was not updated"
        mock_trading_client.replace_order_by_id.assert_called_once()

    def test_modify_stop_loss_pending_fails(self, execution_engine, mock_trading_client):
        """Verify replacement fails when order is in pending state."""
        # Arrange
        mock_sl_order = MagicMock()
        mock_sl_order.status = "pending_replace"
        mock_trading_client.get_order_by_id.return_value = mock_sl_order

        position = PositionFactory.build(
            position_id="test-pos-4",
            signal_id="test-signal-4",
            alpaca_order_id="parent-id",
            sl_order_id="sl-order-id",
            qty=0.05,
        )

        # Act
        result = execution_engine.modify_stop_loss(position, 49000.0)

        # Assert
        assert result is False, "modify_stop_loss should fail for pending order"
        mock_trading_client.replace_order_by_id.assert_not_called()


class TestClosePositionEmergency:
    """Tests for the close_position_emergency method."""

    def test_emergency_close_cancels_all_legs(
        self, execution_engine, mock_trading_client
    ):
        """Verify all legs are canceled and market close order submitted."""

        # Arrange
        mock_close_order = MagicMock()
        mock_close_order.id = "close-order-id"
        mock_trading_client.submit_order.return_value = mock_close_order

        mock_parent_order = MagicMock()
        mock_parent_order.symbol = "BTC/USD"
        mock_trading_client.get_order_by_id.return_value = mock_parent_order

        position = PositionFactory.build(
            position_id="test-pos-5",
            signal_id="test-signal-5",
            alpaca_order_id="parent-id",
            tp_order_id="tp-order-id",
            sl_order_id="sl-order-id",
            qty=0.05,
        )

        # Act
        result = execution_engine.close_position_emergency(position)

        # Assert
        assert result is True, "close_position_emergency failed to return True"
        assert position.status == TradeStatus.CLOSED, "Position status should be CLOSED"

    def test_emergency_close_captures_exit_order_id_and_reason(
        self, execution_engine, mock_trading_client
    ):
        """Verify exit_order_id and exit_reason are captured during emergency close."""

        # Arrange
        mock_close_order = MagicMock()
        mock_close_order.id = "close-order-uuid-999"
        mock_close_order.filled_avg_price = "50000.0"
        mock_trading_client.submit_order.return_value = mock_close_order

        mock_parent_order = MagicMock()
        mock_parent_order.symbol = "BTC/USD"
        mock_trading_client.get_order_by_id.return_value = mock_parent_order

        position = PositionFactory.build(
            position_id="test-pos-exit-id",
            signal_id="test-signal-exit-id",
            alpaca_order_id="parent-id",
            tp_order_id="tp-order-id",
            sl_order_id="sl-order-id",
            qty=0.05,
        )

        # Act
        result = execution_engine.close_position_emergency(
            position, exit_reason=ExitReason.STRUCTURAL_INVALIDATION
        )

        # Assert
        assert result is True
        assert position.status == TradeStatus.CLOSED
        assert position.exit_order_id == "close-order-uuid-999"
        assert position.exit_reason == ExitReason.STRUCTURAL_INVALIDATION

        cancel_calls = mock_trading_client.cancel_order_by_id.call_args_list
        canceled_ids = [call[0][0] for call in cancel_calls]
        assert "tp-order-id" in canceled_ids, "TP order was not canceled"
        assert "sl-order-id" in canceled_ids, "SL order was not canceled"
        mock_trading_client.submit_order.assert_called_once()

    def test_emergency_close_theoretical_trade(self, execution_engine):
        """Verify emergency close for theoretical trades."""

        # Arrange
        position = PositionFactory.build(
            position_id="test-pos-theo",
            signal_id="test-signal-theo",
            trade_type=TradeType.THEORETICAL.value,
            qty=0.05,
        )

        # Act
        result = execution_engine.close_position_emergency(
            position, exit_reason=ExitReason.STRUCTURAL_INVALIDATION
        )

        # Assert
        assert result is True
        assert position.status == TradeStatus.CLOSED
        assert position.exit_reason == ExitReason.STRUCTURAL_INVALIDATION
        assert position.exit_order_id.startswith("theo-exit-")


class TestScaleOutPosition:
    """Tests for the scale_out_position method."""

    def test_scale_out_calculates_correct_qty(
        self, execution_engine, mock_trading_client
    ):
        """Verify 50% scale-out calculates the correct quantity."""
        # Arrange
        mock_close_order = MagicMock()
        mock_close_order.id = "scale-order-123"
        mock_close_order.filled_avg_price = "55000.0"
        mock_trading_client.submit_order.return_value = mock_close_order

        position = PositionFactory.build(
            position_id="test-scale-1",
            signal_id="test-signal-scale",
            alpaca_order_id="parent-id",
            qty=0.10,
        )

        # Act
        result = execution_engine.scale_out_position(position, scale_pct=0.5)

        # Assert
        assert result is True, "scale_out_position failed to return True"
        call_args = mock_trading_client.submit_order.call_args[0][0]
        assert (
            call_args.qty == 0.05
        ), f"Scale out qty mismatch. Expected 0.05, got {call_args.qty}"

    def test_scale_out_updates_remaining_qty(self, execution_engine, mock_trading_client):
        """Verify position.qty is reduced after scale-out."""
        # Arrange
        mock_close_order = MagicMock()
        mock_close_order.id = "scale-order-123"
        mock_close_order.filled_avg_price = "55000.0"
        mock_trading_client.submit_order.return_value = mock_close_order

        position = PositionFactory.build(
            position_id="test-scale-2",
            signal_id="test-signal-scale",
            alpaca_order_id="parent-id",
            qty=0.10,
        )

        # Act
        execution_engine.scale_out_position(position, scale_pct=0.5)

        # Assert
        assert (
            position.qty == 0.05
        ), f"Remaining qty mismatch. Expected 0.05, got {position.qty}"

    def test_scale_out_captures_original_qty_once(
        self, execution_engine, mock_trading_client
    ):
        """Verify original_qty is set only on first scale-out, not overwritten."""
        # Arrange
        mock_close_order = MagicMock()
        mock_close_order.id = "scale-order-123"
        mock_close_order.filled_avg_price = "55000.0"
        mock_trading_client.submit_order.return_value = mock_close_order

        position = PositionFactory.build(
            position_id="test-scale-orig",
            signal_id="test-signal-scale",
            alpaca_order_id="parent-id",
            qty=1.0,  # Start with 1.0
        )

        # Act
        # First scale-out (50%): 1.0 -> 0.5
        execution_engine.scale_out_position(position, scale_pct=0.5)

        # Assert
        assert (
            position.original_qty == 1.0
        ), "original_qty should be captured on first scale out"

        # Act
        # Second scale-out (50% of remaining): 0.5 -> 0.25
        execution_engine.scale_out_position(position, scale_pct=0.5)

        # Assert
        assert (
            position.original_qty == 1.0
        ), "original_qty should not be overwritten on subsequent scale outs"

    def test_scale_out_appends_to_prices_list(
        self, execution_engine, mock_trading_client
    ):
        """Verify scaled_out_prices list accumulates for multi-stage exits."""
        # Arrange
        # First scale-out at $55,000
        mock_order_1 = MagicMock()
        mock_order_1.id = "scale-order-1"
        mock_order_1.filled_avg_price = "55000.0"

        # Second scale-out at $58,000
        mock_order_2 = MagicMock()
        mock_order_2.id = "scale-order-2"
        mock_order_2.filled_avg_price = "58000.0"

        mock_trading_client.submit_order.side_effect = [mock_order_1, mock_order_2]

        position = PositionFactory.build(
            position_id="test-scale-prices",
            signal_id="test-signal-scale",
            alpaca_order_id="parent-id",
            qty=1.0,
        )

        # Act
        # First scale-out
        execution_engine.scale_out_position(position, scale_pct=0.5)
        # Second scale-out
        execution_engine.scale_out_position(position, scale_pct=0.5)

        # Assert
        assert (
            len(position.scaled_out_prices) == 2
        ), "scaled_out_prices list length mismatch"
        assert (
            position.scaled_out_prices[0]["price"] == 55000.0
        ), "First scale out price mismatch"
        assert position.scaled_out_prices[0]["qty"] == 0.5, "First scale out qty mismatch"
        assert (
            position.scaled_out_prices[1]["price"] == 58000.0
        ), "Second scale out price mismatch"
        assert (
            position.scaled_out_prices[1]["qty"] == 0.25
        ), "Second scale out qty mismatch"

    def test_scale_out_fails_with_no_qty(self, execution_engine, mock_trading_client):
        """Verify returns False when position has no quantity."""
        # Arrange
        position = PositionFactory.build(
            position_id="test-scale-zero",
            signal_id="test-signal-scale",
            alpaca_order_id="parent-id",
            qty=0,  # Zero qty!
        )

        # Act
        result = execution_engine.scale_out_position(position, scale_pct=0.5)

        # Assert
        assert result is False, "scale_out_position should fail for zero qty"
        mock_trading_client.submit_order.assert_not_called()

    def test_scale_out_handles_order_failure(self, execution_engine, mock_trading_client):
        """Verify failed_reason is set when order submission fails."""
        # Arrange
        mock_trading_client.submit_order.side_effect = Exception("Insufficient funds")

        position = PositionFactory.build(
            position_id="test-scale-fail",
            signal_id="test-signal-scale",
            alpaca_order_id="parent-id",
            qty=0.10,
        )

        # Act
        result = execution_engine.scale_out_position(position, scale_pct=0.5)

        # Assert
        assert result is False, "scale_out_position should fail on API exception"
        assert (
            "Scale-out failed" in position.failed_reason
        ), "failed_reason not set correctly"


class TestMoveStopToBreakeven:
    """Tests for the move_stop_to_breakeven method."""

    def test_breakeven_moves_stop_to_entry(self, execution_engine, mock_trading_client):
        """Verify stop is moved to entry price (with buffer)."""
        # Arrange
        mock_sl_order = MagicMock()
        mock_sl_order.status = "new"

        mock_replaced_order = MagicMock()
        mock_replaced_order.id = "new-sl-order-id"

        mock_trading_client.get_order_by_id.return_value = mock_sl_order
        mock_trading_client.replace_order_by_id.return_value = mock_replaced_order

        position = PositionFactory.build(
            position_id="test-breakeven-1",
            signal_id="test-signal-be",
            alpaca_order_id="parent-id",
            sl_order_id="old-sl-order-id",
            qty=0.05,
        )

        # Act
        result = execution_engine.move_stop_to_breakeven(position)

        # Assert
        assert result is True, "move_stop_to_breakeven failed to return True"
        # Entry + 0.1% buffer = 50000 * 1.001 = 50050
        assert (
            position.current_stop_loss == 50050.0
        ), "Stop loss not moved to breakeven (plus buffer)"

    def test_breakeven_applies_buffer_for_longs(
        self, execution_engine, mock_trading_client
    ):
        """Verify 0.1% buffer is above entry for long positions."""
        # Arrange
        mock_sl_order = MagicMock()
        mock_sl_order.status = "new"
        mock_replaced = MagicMock()
        mock_replaced.id = "new-id"

        mock_trading_client.get_order_by_id.return_value = mock_sl_order
        mock_trading_client.replace_order_by_id.return_value = mock_replaced

        position = PositionFactory.build(
            position_id="test-be-long",
            signal_id="test-signal-be",
            alpaca_order_id="parent-id",
            sl_order_id="sl-id",
            entry_fill_price=100.0,
            current_stop_loss=95.0,
            qty=1.0,
        )

        # Act
        execution_engine.move_stop_to_breakeven(position)

        # Assert
        # Long: 100 * 1.001 = 100.10, rounded to 100.1
        assert (
            position.current_stop_loss == 100.1
        ), "Stop loss calculation incorrect for long position"

    def test_breakeven_applies_buffer_for_shorts(
        self, execution_engine, mock_trading_client
    ):
        """Verify 0.1% buffer is below entry for short positions."""
        # Arrange
        mock_sl_order = MagicMock()
        mock_sl_order.status = "new"
        mock_replaced = MagicMock()
        mock_replaced.id = "new-id"

        mock_trading_client.get_order_by_id.return_value = mock_sl_order
        mock_trading_client.replace_order_by_id.return_value = mock_replaced

        position = PositionFactory.build(
            position_id="test-be-short",
            signal_id="test-signal-be",
            alpaca_order_id="parent-id",
            sl_order_id="sl-id",
            entry_fill_price=100.0,
            current_stop_loss=105.0,
            qty=1.0,
            side=OrderSide.SELL,  # Short position
        )

        # Act
        execution_engine.move_stop_to_breakeven(position)

        # Assert
        # Short: 100 * 0.999 = 99.90, rounded to 99.9
        assert (
            position.current_stop_loss == 99.9
        ), "Stop loss calculation incorrect for short position"

    def test_breakeven_sets_flag(self, execution_engine, mock_trading_client):
        """Verify breakeven_applied flag is set to True on success."""
        # Arrange
        mock_sl_order = MagicMock()
        mock_sl_order.status = "new"
        mock_replaced = MagicMock()
        mock_replaced.id = "new-id"

        mock_trading_client.get_order_by_id.return_value = mock_sl_order
        mock_trading_client.replace_order_by_id.return_value = mock_replaced

        position = PositionFactory.build(
            position_id="test-be-flag",
            signal_id="test-signal-be",
            alpaca_order_id="parent-id",
            sl_order_id="sl-id",
            qty=0.05,
        )

        # Assert
        assert (
            position.breakeven_applied is False
        ), "breakeven_applied should be False initially"

        # Act
        execution_engine.move_stop_to_breakeven(position)

        # Assert
        assert (
            position.breakeven_applied is True
        ), "breakeven_applied should be True after success"

    def test_breakeven_fails_without_entry_price(
        self, execution_engine, mock_trading_client
    ):
        """Verify returns False when entry_fill_price is missing."""
        # Arrange
        # Create valid position first, then set entry_fill_price to None
        position = PositionFactory.build(
            position_id="test-be-no-entry",
            signal_id="test-signal-be",
            alpaca_order_id="parent-id",
            sl_order_id="sl-id",
            qty=0.05,
        )
        # Simulate edge case where entry_fill_price might be cleared
        position.entry_fill_price = None

        # Act
        result = execution_engine.move_stop_to_breakeven(position)

        # Assert
        assert result is False, "move_stop_to_breakeven should fail without entry price"
        mock_trading_client.replace_order_by_id.assert_not_called()


class TestCFEEReconciliation:
    """Tests for CFEE (Crypto Fee) reconciliation methods (Issue #140)."""

    def test_get_crypto_fees_by_orders_success(
        self, execution_engine, mock_trading_client
    ):
        """Verify successful CFEE fetching and currency normalization."""
        # Arrange
        mock_activity = {
            "id": "cfee-123",
            "symbol": "BTCUSD",
            "qty": "-0.0001",
            "price": "50000.0",
            "date": "2025-01-16",
            "description": "Tier 0: 0.25%",
        }

        mock_trading_client.get.return_value = [mock_activity]

        # Act
        result = execution_engine.get_crypto_fees_by_orders(
            order_ids=["order-123"],
            symbol="BTC/USD",
            start_date=date(2025, 1, 15),
            end_date=date(2025, 1, 17),
        )

        # Assert
        assert result["total_fee_usd"] == 5.0, "total_fee_usd calculation mismatch"
        assert len(result["fee_details"]) == 1, "fee_details list length mismatch"
        assert result["fee_tier"] == "Tier 0: 0.25%", "fee_tier extraction mismatch"

        mock_trading_client.get.assert_called()

    def test_get_crypto_fees_by_orders_multi_order_aggregation(
        self, execution_engine, mock_trading_client
    ):
        """Verify correct aggregation of CFEE for multiple orders within a trade."""
        # Arrange
        mock_activity1 = {
            "id": "cfee-entry",
            "symbol": "BTCUSD",
            "qty": "-0.0001",
            "price": "50000.0",
            "date": "2025-01-16",
            "description": "Tier 0: 0.25%",
        }
        mock_activity2 = {
            "id": "cfee-exit",
            "symbol": "BTCUSD",
            "qty": "-0.0001",
            "price": "55000.0",
            "date": "2025-01-17",
            "description": "Tier 0: 0.25%",
        }

        mock_trading_client.get.return_value = [mock_activity1, mock_activity2]

        # Act
        result = execution_engine.get_crypto_fees_by_orders(
            order_ids=["order-entry", "order-exit"],
            symbol="BTC/USD",
            start_date=date(2025, 1, 15),
            end_date=date(2025, 1, 18),
        )

        # Assert
        assert result["total_fee_usd"] == 10.5, "total_fee_usd aggregation mismatch"
        assert len(result["fee_details"]) == 2, "fee_details length mismatch"

    def test_get_crypto_fees_by_orders_api_failure(
        self, execution_engine, mock_trading_client
    ):
        """Ensure graceful handling when the Alpaca CFEE API call fails."""
        # Arrange
        mock_trading_client.get.side_effect = Exception("API rate limit exceeded")

        # Act
        result = execution_engine.get_crypto_fees_by_orders(
            order_ids=["order-123"],
            symbol="BTC/USD",
            start_date=date(2025, 1, 15),
            end_date=date(2025, 1, 17),
        )

        # Assert
        assert result["total_fee_usd"] == 0.0, "Expected 0.0 total fees on API failure"
        assert result["fee_details"] == [], "Expected empty fee_details on API failure"
        assert result["fee_tier"] is None, "Expected None fee_tier on API failure"

    def test_get_crypto_fees_by_orders_invalid_qty_price(
        self, execution_engine, mock_trading_client
    ):
        """Verify validation skips CFEE records with qty=0 or price=0."""
        # Arrange
        mock_activity = {
            "id": "cfee-invalid",
            "symbol": "BTCUSD",
            "qty": "0.0",
            "price": "50000.0",
            "date": "2025-01-16",
        }

        mock_trading_client.get.return_value = [mock_activity]

        # Act
        result = execution_engine.get_crypto_fees_by_orders(
            order_ids=["order-123"],
            symbol="BTC/USD",
            start_date=date(2025, 1, 15),
            end_date=date(2025, 1, 17),
        )

        # Assert
        assert (
            result["total_fee_usd"] == 0.0
        ), "Total fees should be 0.0 for invalid activity"
        assert (
            len(result["fee_details"]) == 0
        ), "Fee details should be empty for invalid activity"

    def test_get_crypto_fees_by_orders_retry_logic(
        self, execution_engine, mock_trading_client
    ):
        """Verify retry logic with exponential backoff on transient failures."""
        # Arrange
        mock_trading_client.get.side_effect = Exception("Persistent API error")

        # Act
        with patch("crypto_signals.engine.execution.sleep") as mock_sleep:
            result = execution_engine.get_crypto_fees_by_orders(
                order_ids=["order-123"],
                symbol="BTC/USD",
                start_date=date(2025, 1, 15),
                end_date=date(2025, 1, 17),
            )

        # Assert
        assert mock_trading_client.get.call_count == 3, "Expected 3 retry attempts"
        assert mock_sleep.call_count == 2, "Expected 2 sleep calls for backoff"
        assert (
            result["total_fee_usd"] == 0.0
        ), "Expected 0.0 total fees after retries exhausted"
        assert (
            result["fee_details"] == []
        ), "Expected empty fee_details after retries exhausted"
        assert (
            result["fee_tier"] is None
        ), "Expected None fee_tier after retries exhausted"

    def test_get_current_fee_tier_success(self, execution_engine, mock_trading_client):
        """Verify successful retrieval of the current fee tier from Alpaca."""
        # Arrange
        mock_account = MagicMock()
        mock_account.crypto_tier = 0
        mock_trading_client.get_account.return_value = mock_account

        # Act
        result = execution_engine.get_current_fee_tier()

        # Assert
        assert result["tier_name"] == "Tier 0", "Tier name mismatch"
        assert result["maker_fee_pct"] == 0.15, "Maker fee mismatch"
        assert result["taker_fee_pct"] == 0.25, "Taker fee mismatch"

    def test_get_current_fee_tier_api_failure(
        self, execution_engine, mock_trading_client
    ):
        """Ensure graceful handling when the Alpaca fee tier API call fails."""
        # Arrange
        mock_trading_client.get_account.side_effect = Exception("API error")

        # Act
        result = execution_engine.get_current_fee_tier()

        # Assert
        assert result["tier_name"] == "Tier 0", "Expected Tier 0 fallback"
        assert result["maker_fee_pct"] == 0.15, "Expected Tier 0 maker fee fallback"
        assert result["taker_fee_pct"] == 0.25, "Expected Tier 0 taker fee fallback"


# =============================================================================
# MICRO-CAP EDGE CASE TESTS (Issue #136)
# =============================================================================
# Tests for negative stop-loss scenarios on low-priced assets (PEPE, SHIB)
# where ATR-based stop calculations can produce negative values.
# =============================================================================


class TestMicroCapEdgeCases:
    """Test suite for micro-cap token edge cases (Issue #136).

    Micro-cap tokens have extremely low prices (often < $0.0001), which can
    cause ATR-based stop-loss calculations to produce negative values:
        suggested_stop = low_price - (0.5 * atr)
        Example: 0.00000080 - (0.5 * 0.000002) = -0.00000020 ❌

    The fix uses floor-based calculation to prevent negatives:
        suggested_stop = max(SAFE_STOP_VAL, low_price - (0.5 * atr))
    """

    @pytest.fixture
    def pepe_usdt_signal_micro_cap(self):
        """PEPE/USD signal with extremely small prices (micro-cap edge case)."""
        return SignalFactory.build(
            signal_id="pepe-micro-cap-001",
            strategy_id="ELLIOTT_IMPULSE_WAVE",
            symbol="PEPE/USD",
            entry_price=0.00001200,  # ~$0.000012
            pattern_name="ELLIOTT_IMPULSE_WAVE",
            suggested_stop=0.00000080,  # Will be tested against floor
            take_profit_1=0.00001800,
            take_profit_2=0.00002400,
            side=OrderSide.BUY,
        )

    @pytest.fixture
    def shib_usdt_signal_micro_cap(self):
        """SHIB/USD signal with extreme volatility (high ATR)."""
        return SignalFactory.build(
            signal_id="shib-micro-cap-002",
            strategy_id="ELLIOTT_IMPULSE_WAVE",
            symbol="SHIB/USD",
            entry_price=0.00000950,  # ~$0.000010
            pattern_name="ELLIOTT_IMPULSE_WAVE",
            suggested_stop=0.00000001,  # SAFE_STOP_VAL (1e-8)
            take_profit_1=0.00001400,
            take_profit_2=0.00001900,
            side=OrderSide.BUY,
        )

    def test_calculate_qty_with_tiny_stop_loss(self, mock_settings, mock_trading_client):
        """Test quantity calculation when stop-loss is at safe floor (1e-8).

        When stop-loss is very close to entry (micro-cap scenario),
        risk_per_share becomes tiny, and qty calculation could explode.
        This test verifies that qty is capped reasonably.

        Example:
            - Entry: 0.00001200
            - Stop: 0.00000001 (SAFE_STOP_VAL)
            - Risk per share: 0.00001199
            - RISK_PER_TRADE: 100
            - qty = 100 / 0.00001199 ≈ 8,340 (reasonable)
        """
        # Arrange
        with patch(
            "crypto_signals.engine.execution.get_settings", return_value=mock_settings
        ):
            execution_engine = ExecutionEngine(
                trading_client=mock_trading_client,
                repository=MagicMock(),
            )

            signal = SignalFactory.build(
                signal_id="micro-qty-test",
                strategy_id="TEST",
                symbol="PEPE/USD",
                entry_price=0.00001200,
                pattern_name="TEST",
                suggested_stop=0.00000001,  # SAFE_STOP_VAL
                take_profit_1=0.00001800,
                side=OrderSide.BUY,
            )

            # Act
            qty = execution_engine._calculate_qty(signal)

            # Assert
            # Qty should be capped at MAX_POSITION_SIZE
            # The guard in _calculate_qty() prevents qty explosion:
            # risk_per_share = 0.00001199
            # qty = 100 / 0.00001199 ≈ 8,340,283 (would explode!)
            # Guard caps at 1,000,000
            assert qty > 0, "Qty should be positive"
            assert qty == 1_000_000, "Qty should be capped at MAX_POSITION_SIZE"

    def test_calculate_qty_with_very_small_risk_per_share(
        self, mock_settings, mock_trading_client
    ):
        """Test qty calculation guards against extreme values.

        When risk_per_share is extremely small, qty can exceed reasonable
        limits that Alpaca would reject. This test ensures the defensive
        guard caps qty at MAX_POSITION_SIZE.
        """
        # Arrange
        with patch(
            "crypto_signals.engine.execution.get_settings", return_value=mock_settings
        ):
            execution_engine = ExecutionEngine(
                trading_client=mock_trading_client,
                repository=MagicMock(),
            )

            # Extreme case: entry and stop almost equal
            signal = SignalFactory.build(
                signal_id="extreme-qty-test",
                strategy_id="TEST",
                symbol="PEPE/USD",
                entry_price=0.00001200,
                pattern_name="TEST",
                suggested_stop=0.00001199,  # Extremely tight
                take_profit_1=0.00001800,
                side=OrderSide.BUY,
            )

            # Act
            qty = execution_engine._calculate_qty(signal)

            # Assert
            # Qty should still be reasonable (capped)
            # risk_per_share = 0.00000001
            # qty = 100 / 0.00000001 = 10,000,000 (would explode!)
            # Should be capped at MAX_POSITION_SIZE
            assert qty >= 0, "Qty should be non-negative"
            # If capping is implemented, should not exceed reasonable limit
            assert qty == 1_000_000, "Qty should be capped at MAX_POSITION_SIZE"

    def test_validate_signal_with_negative_stop_loss(self):
        """Test that _validate_signal_parameters catches negative stops.

        This tests the validation layer that should prevent negative stops
        from being used in bracket orders.
        """
        # Arrange
        from crypto_signals.engine.signal_generator import SignalGenerator

        signal_gen = SignalGenerator(
            market_provider=MagicMock(),
            indicators=None,
        )

        # Params with negative stop (edge case before fix)
        params = {
            "signal_id": "neg-stop-test",
            "strategy_id": "ELLIOTT",
            "symbol": "PEPE/USD",
            "ds": date(2025, 1, 15),
            "asset_class": AssetClass.CRYPTO,
            "confluence_factors": [],
            "entry_price": 0.00001200,
            "pattern_name": "ELLIOTT_IMPULSE_WAVE",
            "suggested_stop": -0.00000020,  # NEGATIVE (pre-fix scenario)
            "invalidation_price": None,
            "take_profit_1": 0.00001800,
            "take_profit_2": None,
            "take_profit_3": None,
            "valid_until": None,
            "pattern_duration_days": None,
            "pattern_span_days": None,
            "pattern_classification": None,
            "structural_anchors": None,
            "harmonic_metadata": None,
            "created_at": None,
            "confluence_snapshot": None,
            "side": OrderSide.BUY,
        }

        # Act
        rejection_reasons = signal_gen._validate_signal_parameters(params)

        # Assert
        # Should detect negative stop
        assert len(rejection_reasons) > 0, "Expected rejection reasons, got empty list"
        assert any(
            "Invalid Stop" in reason for reason in rejection_reasons
        ), f"Expected 'Invalid Stop' in rejection reasons: {rejection_reasons}"

    def test_validate_signal_with_safe_floor_stop_loss(self):
        """Test that safe floor stops (1e-8) pass validation.

        After the fix, suggested_stop should always be >= SAFE_STOP_VAL,
        so validation should pass.
        """
        # Arrange
        from crypto_signals.engine.signal_generator import SignalGenerator

        signal_gen = SignalGenerator(
            market_provider=MagicMock(),
            indicators=None,
        )

        # Params with safe floor stop
        params = {
            "signal_id": "safe-stop-test",
            "strategy_id": "ELLIOTT",
            "symbol": "PEPE/USD",
            "ds": date(2025, 1, 15),
            "asset_class": AssetClass.CRYPTO,
            "confluence_factors": [],
            "entry_price": 0.00001200,
            "pattern_name": "ELLIOTT_IMPULSE_WAVE",
            "suggested_stop": 0.00000001,  # SAFE_STOP_VAL (1e-8)
            "invalidation_price": None,
            "take_profit_1": 0.00001800,
            "take_profit_2": 0.00002400,
            "take_profit_3": None,
            "valid_until": None,
            "pattern_duration_days": None,
            "pattern_span_days": None,
            "pattern_classification": None,
            "structural_anchors": None,
            "harmonic_metadata": None,
            "created_at": None,
            "confluence_snapshot": None,
            "side": OrderSide.BUY,
        }

        # Act
        rejection_reasons = signal_gen._validate_signal_parameters(params)

        # Assert
        # Should NOT detect negative stop (stop is >= SAFE_STOP_VAL)
        assert not any(
            "Invalid Stop" in reason for reason in rejection_reasons
        ), f"Unexpected 'Invalid Stop' in rejection reasons: {rejection_reasons}"

    def test_pepe_signal_rr_ratio_with_micro_cap_prices(self):
        """Test R:R ratio calculation with micro-cap prices.

        With extremely small prices, R:R should still be calculable.
        """
        # Arrange
        from crypto_signals.engine.signal_generator import SignalGenerator

        signal_gen = SignalGenerator(
            market_provider=MagicMock(),
            indicators=None,
        )

        params = {
            "signal_id": "pepe-rr-test",
            "strategy_id": "ELLIOTT",
            "symbol": "PEPE/USD",
            "ds": date(2025, 1, 15),
            "asset_class": AssetClass.CRYPTO,
            "confluence_factors": [],
            "entry_price": 0.00001200,
            "pattern_name": "ELLIOTT_IMPULSE_WAVE",
            "suggested_stop": 0.00000001,  # SAFE_STOP_VAL
            "invalidation_price": None,
            "take_profit_1": 0.00001800,  # Profit > entry
            "take_profit_2": 0.00002400,
            "take_profit_3": None,
            "valid_until": None,
            "pattern_duration_days": None,
            "pattern_span_days": None,
            "pattern_classification": None,
            "structural_anchors": None,
            "harmonic_metadata": None,
            "created_at": None,
            "confluence_snapshot": {},
            "side": OrderSide.BUY,
        }

        # Act
        rejection_reasons = signal_gen._validate_signal_parameters(
            params, confluence_snapshot=params["confluence_snapshot"]
        )

        # Assert
        # R:R should be calculable (profit / risk)
        # profit = 0.00001800 - 0.00001200 = 0.00000600
        # risk = 0.00001200 - 0.00000001 = 0.00001199
        # R:R = 0.00000600 / 0.00001199 ≈ 0.5 (< 1.5, so should be rejected)
        assert any(
            "R:R" in reason for reason in rejection_reasons
        ), f"Expected 'R:R' in rejection reasons: {rejection_reasons}"


class TestCostBasisValidation:
    """Tests for notional value (cost basis) validation (Issue #192)."""

    def test_order_rejected_if_notional_value_too_low(
        self, execution_engine, sample_signal, mock_trading_client, mock_settings
    ):
        """Verify that a signal is rejected if qty * entry_price is below the minimum."""
        # Arrange
        # To create a scenario that fails the notional value check, we can
        # simulate a very low RISK_PER_TRADE. This results in a small
        # quantity, which in turn leads to a low notional value.
        mock_settings.RISK_PER_TRADE = 1.0
        sample_signal.entry_price = 100.0
        sample_signal.suggested_stop = 50.0

        # With the above settings:
        # risk_per_share = 100.0 - 50.0 = 50.0
        # qty = RISK_PER_TRADE / risk_per_share = 1.0 / 50.0 = 0.02
        # notional_value = qty * entry_price = 0.02 * 100.0 = $2.00
        # This notional value of $2.00 is less than the required minimum of $15.0.

        # Act
        position = execution_engine.execute_signal(sample_signal)

        # Assert
        # Assert that the position was not created and no order was submitted.
        assert position is None, "Position should be None when notional value is too low"
        mock_trading_client.submit_order.assert_not_called()

    def test_order_rejected_for_equity_below_minimum(
        self, execution_engine, mock_trading_client, mock_settings
    ):
        """Verify equity bracket orders are rejected when notional value is too low."""
        from crypto_signals.domain.schemas import AssetClass

        # Arrange
        mock_settings.RISK_PER_TRADE = 1.0

        # Create equity signal
        equity_signal = SignalFactory.build(
            signal_id="equity-notional-test",
            strategy_id="TEST",
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,  # Equity path
            entry_price=150.0,
            pattern_name="TEST",
            suggested_stop=100.0,  # risk = 50
            take_profit_1=200.0,
            side=OrderSide.BUY,
        )

        # Act
        # qty = 1.0 / 50.0 = 0.02, notional = 0.02 * 150 = $3 < $15
        position = execution_engine.execute_signal(equity_signal)

        # Assert
        assert (
            position is None
        ), "Position should be None for equity below minimum notional"
        mock_trading_client.submit_order.assert_not_called()

    def test_is_notional_value_sufficient_returns_true_above_minimum(
        self, execution_engine, mock_settings
    ):
        """Verify helper method returns True for sufficient notional value."""
        # Arrange
        signal = SignalFactory.build(
            signal_id="notional-helper-test",
            strategy_id="TEST",
            entry_price=100.0,
            pattern_name="TEST",
            suggested_stop=90.0,
            take_profit_1=120.0,
            side=OrderSide.BUY,
        )

        # Act
        # notional = 1.0 * 100 = $100 > $15
        result = execution_engine._is_notional_value_sufficient(1.0, signal)

        # Assert
        assert result is True, "Notional value check failed for sufficient value"

    def test_is_notional_value_sufficient_returns_false_below_minimum(
        self, execution_engine, mock_settings
    ):
        """Verify helper method returns False for insufficient notional value."""
        # Arrange
        signal = SignalFactory.build(
            signal_id="notional-helper-test-2",
            strategy_id="TEST",
            entry_price=100.0,
            pattern_name="TEST",
            suggested_stop=90.0,
            take_profit_1=120.0,
            side=OrderSide.BUY,
        )

        # Act
        # notional = 0.1 * 100 = $10 < $15
        result = execution_engine._is_notional_value_sufficient(0.1, signal)

        # Assert
        assert result is False, "Notional value check passed for insufficient value"


class TestAssetAwareCaps:
    """Tests for asset-aware position size caps (Issue: Asset-Aware Position Size Cap)."""

    @pytest.mark.parametrize(
        "asset_class, expected_cap",
        [
            pytest.param(AssetClass.CRYPTO, 1_000_000.0, id="crypto_default_cap"),
            pytest.param(AssetClass.EQUITY, 10_000.0, id="equity_default_cap"),
        ],
    )
    def test_default_caps_by_asset_class(
        self, execution_engine, mock_settings, asset_class, expected_cap
    ):
        """Verify default caps are applied correctly based on asset class."""
        # Arrange: The mock_settings fixture provides the necessary default values.
        # Create a signal that would result in an extremely large qty
        # risk_per_share = 0.00000001
        # qty = 100 / 0.00000001 = 10,000,000,000
        signal = SignalFactory.build(
            asset_class=asset_class,
            entry_price=100.0,
            suggested_stop=99.99999999,
        )

        # Act
        qty = execution_engine._calculate_qty(signal)

        # Assert
        assert (
            qty == expected_cap
        ), f"Expected qty {expected_cap} for {asset_class}, got {qty}"

    def test_cap_override_via_settings(self, execution_engine, mock_settings):
        """Verify that caps can be overridden via settings."""
        # Arrange
        custom_crypto_cap = 500_000.0
        custom_equity_cap = 5_000.0
        mock_settings.MAX_CRYPTO_POSITION_QTY = custom_crypto_cap
        mock_settings.MAX_EQUITY_POSITION_QTY = custom_equity_cap
        mock_settings.RISK_PER_TRADE = 100.0

        # Create signals that exceed custom caps
        crypto_signal = SignalFactory.build(
            asset_class=AssetClass.CRYPTO,
            entry_price=100.0,
            suggested_stop=99.9999999,  # qty = 100 / 0.0000001 = 1,000,000,000
        )
        equity_signal = SignalFactory.build(
            asset_class=AssetClass.EQUITY,
            entry_price=100.0,
            suggested_stop=99.9999999,
        )

        # Act
        crypto_qty = execution_engine._calculate_qty(crypto_signal)
        equity_qty = execution_engine._calculate_qty(equity_signal)

        # Assert
        assert (
            crypto_qty == custom_crypto_cap
        ), f"Expected custom crypto cap {custom_crypto_cap}, got {crypto_qty}"
        assert (
            equity_qty == custom_equity_cap
        ), f"Expected custom equity cap {custom_equity_cap}, got {equity_qty}"
