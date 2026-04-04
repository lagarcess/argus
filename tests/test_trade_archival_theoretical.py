from unittest.mock import MagicMock, patch

from alpaca.common.exceptions import APIError
from crypto_signals.pipelines.trade_archival import TradeArchivalPipeline


def test_archival_fallback_for_theoretical_trades():
    """
    Verify that TradeArchivalPipeline archives positions even if the Alpaca Order is not found
    (Fallback to Firestore data for Theoretical/Paper trades).
    """
    with (
        patch("crypto_signals.pipelines.base.get_settings") as mock_settings,
        patch(
            "crypto_signals.pipelines.trade_archival.get_trading_client"
        ) as mock_alpaca,
        patch("crypto_signals.pipelines.trade_archival.get_stock_data_client"),
        patch("crypto_signals.pipelines.trade_archival.get_crypto_data_client"),
        patch("crypto_signals.pipelines.trade_archival.MarketDataProvider"),
        patch("google.cloud.firestore.Client") as mock_firestore_cls,
        patch("crypto_signals.pipelines.base.bigquery.Client"),
        patch("crypto_signals.engine.execution.ExecutionEngine") as mock_exec_engine,
    ):  # Patch ExecutionEngine
        # Setup Environment
        mock_settings.return_value.GOOGLE_CLOUD_PROJECT = "test-project"
        mock_settings.return_value.ENVIRONMENT = "DEV"

        # Setup ExecutionEngine fee tier for crypto handling
        # It's called in transform loop
        mock_exec_engine.return_value.get_current_fee_tier.return_value = {
            "tier_name": "Tier 0",
            "taker_fee_pct": 0.1,
        }

        # Setup Firestore Mock to return one CLOSED position
        mock_firestore = mock_firestore_cls.return_value
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "position_id": "theoretical_pos_1",
            "status": "CLOSED",
            "symbol": "BTC/USD",
            "asset_class": "CRYPTO",
            "entry_time": "2025-01-01T12:00:00",
            "exit_time": "2025-01-01T14:00:00",
            "entry_fill_price": 50000.0,
            "exit_fill_price": 51000.0,
            "side": "buy",
            "qty": 0.1,
            "account_id": "theoretical",
            "strategy_id": "test_strat_1",
            "target_entry_price": 50000.0,
        }
        mock_firestore.collection.return_value.where.return_value.stream.return_value = [
            mock_doc
        ]

        # Setup Alpaca Mock to raise 404 (Not Found)
        error = APIError("Order not found")
        mock_http = MagicMock()
        mock_http.status_code = 404
        error.http_error = mock_http

        mock_alpaca.return_value.get_order_by_client_id.side_effect = error

        # Run Pipeline
        pipeline = TradeArchivalPipeline()

        # Mock Cache (Market Data) via the class mock instance attached to pipeline
        # pipeline.market_provider is the return_value of mock_mdp_cls call
        # Mock class returns instance.
        pipeline.market_provider.get_daily_bars.return_value = MagicMock(empty=True)

        raw_data = pipeline.extract()
        transformed_data = pipeline.transform(raw_data)

        # Expectation: SUCCESS (Length 1)
        assert (
            len(transformed_data) == 1
        ), "Pipeline should have archived the theoretical trade"

        # Verification of Fallback Data
        trade = transformed_data[0]
        assert trade["entry_price"] == 50000.0
        assert trade["qty"] == 0.1
        assert trade["alpaca_order_id"] is None
        assert trade["trade_duration"] == 7200  # 2 hours in seconds


if __name__ == "__main__":
    test_archival_fallback_for_theoretical_trades()
