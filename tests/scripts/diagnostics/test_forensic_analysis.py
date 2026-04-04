from unittest.mock import MagicMock, patch

from alpaca.trading.enums import OrderSide
from alpaca.trading.models import Order
from crypto_signals.scripts.diagnostics.forensic_analysis import analyze_exit_gap


def test_analyze_exit_gap_no_gaps():
    """Test analyze_exit_gap detection logic."""
    mock_console = MagicMock()
    mock_settings = MagicMock()
    mock_settings.GOOGLE_CLOUD_PROJECT = "test-project"
    mock_settings.ENVIRONMENT = "PROD"
    mock_settings.ALPACA_API_KEY = "key"
    mock_settings.ALPACA_SECRET_KEY = "secret"
    mock_settings.is_paper_trading = True

    # Mock Firestore Positions
    mock_pos = MagicMock()
    mock_pos.to_dict.return_value = {
        "position_id": "pos1",
        "symbol": "BTC/USD",
        "status": "CLOSED",
        "exit_reason": "TP1",
        "trade_type": "LIVE",
    }
    mock_pos.id = "pos1"

    # Mock Alpaca Orders
    mock_order = MagicMock(spec=Order)
    mock_order.symbol = "BTC/USD"

    mock_order.side = OrderSide.SELL
    mock_order.status = "filled"
    mock_order.id = "order1"
    mock_order.order_type = "market"
    mock_order.qty = 1.0
    mock_order.filled_qty = 1.0
    mock_order.client_order_id = "client1"

    with (
        patch(
            "crypto_signals.scripts.diagnostics.forensic_analysis.firestore.Client"
        ) as mock_db_cls,
        patch(
            "crypto_signals.scripts.diagnostics.forensic_analysis.TradingClient"
        ) as mock_alpaca_cls,
    ):
        mock_db = mock_db_cls.return_value
        # get_all_positions mock
        mock_db.collection.return_value.limit.return_value.stream.return_value = [
            mock_pos
        ]
        # get_closed_signals mock (empty list for brevity)
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []

        mock_alpaca = mock_alpaca_cls.return_value
        mock_alpaca.get_orders.return_value = [mock_order]

        results = analyze_exit_gap(mock_console, mock_settings)

        assert results["closed_positions"] == 1, "Expected 1 closed position in results"
        assert results["sell_orders"] == 1, "Expected 1 sell order in results"
        assert results["gaps"] == 0, f"Expected 0 gaps, found {results['gaps']}"


def test_analyze_exit_gap_with_gap():
    """Test analyze_exit_gap identifies a gap when sell order is missing."""
    mock_console = MagicMock()
    mock_settings = MagicMock()
    mock_settings.GOOGLE_CLOUD_PROJECT = "test-project"
    mock_settings.ENVIRONMENT = "PROD"
    mock_settings.ALPACA_API_KEY = "key"
    mock_settings.ALPACA_SECRET_KEY = "secret"
    mock_settings.is_paper_trading = True

    # Mock Firestore Position (CLOSED)
    mock_pos = MagicMock()
    mock_pos.to_dict.return_value = {
        "position_id": "pos_gap",
        "symbol": "ETH/USD",
        "status": "CLOSED",
        "exit_reason": "TP1",
        "trade_type": "LIVE",
    }

    with (
        patch(
            "crypto_signals.scripts.diagnostics.forensic_analysis.firestore.Client"
        ) as mock_db_cls,
        patch(
            "crypto_signals.scripts.diagnostics.forensic_analysis.TradingClient"
        ) as mock_alpaca_cls,
    ):
        mock_db = mock_db_cls.return_value
        mock_db.collection.return_value.limit.return_value.stream.return_value = [
            mock_pos
        ]
        mock_db.collection.return_value.where.return_value.limit.return_value.stream.return_value = []

        mock_alpaca = mock_alpaca_cls.return_value
        mock_alpaca.get_orders.return_value = []  # No orders -> Gap!

        results = analyze_exit_gap(mock_console, mock_settings)

        assert results["gaps"] == 1, "Expected 1 gap detection when order is missing"
        assert (
            results["gap_details"][0]["symbol"] == "ETH/USD"
        ), "Gap details should match the missing symbol 'ETH/USD'"
