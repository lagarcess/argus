from unittest.mock import MagicMock, patch

from alpaca.trading.client import TradingClient
from crypto_signals.pipelines.trade_archival import TradeArchivalPipeline


@patch("crypto_signals.pipelines.base.get_settings")
@patch("crypto_signals.pipelines.trade_archival.firestore")
@patch("crypto_signals.pipelines.trade_archival.get_trading_client")
@patch("crypto_signals.pipelines.trade_archival.get_stock_data_client")
@patch("crypto_signals.pipelines.trade_archival.get_crypto_data_client")
@patch("crypto_signals.engine.execution.ExecutionEngine")  # Correct patch path
@patch("crypto_signals.pipelines.base.bigquery.Client")
def test_get_actual_fees_uses_public_api(
    mock_bq_client,
    mock_execution_engine_cls,
    mock_get_crypto,
    mock_get_stock,
    mock_get_trading,
    mock_firestore,
    mock_settings,
):
    """Verify fee archival uses the public Alpaca Activity API."""
    # Setup
    mock_settings.return_value.ENVIRONMENT = "PROD"
    mock_settings.return_value.GOOGLE_CLOUD_PROJECT = "test-project"

    # Mock Alpaca Client
    mock_alpaca = MagicMock(spec=TradingClient)
    # Ensure _get is NOT present (simulating the issue if we rely on it,
    # verify=True ensures we only can call existing methods of TradingClient)

    mock_get_trading.return_value = mock_alpaca

    # Initialize functionality
    pipeline = TradeArchivalPipeline()

    # Execute
    # Execute
    # We want to trigger _get_actual_fees which constructs a list of activities.

    # Mocking the return of get (list of activities)
    mock_activity_dict = {
        "order_id": "test-order-id",
        "qty": "0.005",
        "price": "100.0",
        "symbol": "BTC/USD",
    }

    # Mock public .get()
    mock_alpaca.get.return_value = [mock_activity_dict]

    # Trigger method - should pass now
    pipeline._get_actual_fees("test-order-id", "BTC/USD", "buy")

    # Assertions
    mock_alpaca.get.assert_called_once()
    args, kwargs = mock_alpaca.get.call_args
    # Verify positional args (path) and dict params
    assert args[0] == "/account/activities"
    assert args[1] == {"activity_types": "CSD,CFEE"}

    # Ensure legacy private method is NOT called
    mock_alpaca._request.assert_not_called()
