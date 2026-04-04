from unittest.mock import MagicMock, patch

from crypto_signals.pipelines.trade_archival import TradeArchivalPipeline


def test_trade_archival_orchestration_flow():
    """
    Prod-Safe Verification of the Trade Archival Pipeline.
    Verifies:
    1. Extraction from Firestore (mocked).
    2. Transformation with weighted average logic (mocked Alpaca).
    3. Loading to BigQuery (mocked).
    4. Cleanup of Firestore (mocked).
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
        patch("crypto_signals.pipelines.base.bigquery.Client") as mock_bq_cls,
        patch("crypto_signals.engine.execution.ExecutionEngine") as mock_exec_engine,
        patch("crypto_signals.pipelines.base.SchemaGuardian"),
    ):
        # 1. Setup Environment
        mock_settings.return_value.GOOGLE_CLOUD_PROJECT = "test-project"
        mock_settings.return_value.ENVIRONMENT = "PROD"  # Simulate PROD

        # 2. Setup Firestore Data (Mock Closed Position with Scale Outs)
        mock_firestore = mock_firestore_cls.return_value
        mock_doc = MagicMock()
        mock_doc.to_dict.return_value = {
            "position_id": "pos_123",
            "status": "CLOSED",
            "symbol": "BTC/USD",
            "asset_class": "CRYPTO",
            "entry_time": "2025-01-01T10:00:00",
            "exit_time": "2025-01-01T12:00:00",
            "entry_fill_price": 50000.0,
            "exit_fill_price": 52000.0,  # Final exit price
            "side": "buy",
            "qty": 1.0,
            "original_qty": 1.0,
            "account_id": "acc_123",
            "strategy_id": "strat_A",
            "target_entry_price": 50000.0,
            "scaled_out_prices": [
                {"qty": 0.5, "price": 51000.0, "timestamp": "2025-01-01T11:00:00"}
            ],
        }
        # Simulate doc ID (though cleanup uses trade_id from model)
        mock_doc.id = "pos_123"

        mock_firestore.collection.return_value.where.return_value.stream.return_value = [
            mock_doc
        ]

        # 3. Setup Alpaca Mock (Order Found)
        mock_order = MagicMock()
        mock_order.id = "alpaca_order_123"
        mock_order.filled_avg_price = 50000.0
        mock_order.filled_qty = 1.0
        mock_order.side = "buy"
        mock_alpaca.return_value.get_order_by_client_id.return_value = mock_order

        # Mock Account Activities for Actual Fees

        # Activity 1: CFEE for Buy Order (Fee in Asset)
        # 0.0001 BTC fee * 50000 USD/BTC = 5 USD
        mock_activity = {
            "order_id": "alpaca_order_123",
            "qty": "0.0001",
            "price": "50000.0",
            "symbol": "BTC/USD",
        }

        mock_alpaca.return_value.get.return_value = [mock_activity]

        # 4. Setup Execution Engine (Fees)
        mock_exec_engine.return_value.get_current_fee_tier.return_value = {
            "tier_name": "Tier 0",
            "taker_fee_pct": 0.1,
        }

        # 5. Setup BigQuery Mock
        mock_bq = mock_bq_cls.return_value
        # Ensure tables exist (mock get_table success)
        mock_bq.get_table.return_value = True
        # Ensure insert_rows_json returns empty list (no errors)
        mock_bq.insert_rows_json.return_value = []

        # === EXECUTE ===
        pipeline = TradeArchivalPipeline()
        # Mock cache to avoid MFE fetch
        pipeline.market_provider.get_daily_bars.return_value = MagicMock(empty=True)

        processed_count = pipeline.run()

        # === VERIFY ===
        assert processed_count == 1

        # A. Check Transformation (Weighted Average)
        # 0.5 * 51000 + 0.5 * 52000 = 25500 + 26000 = 51500
        # Total qty = 1.0
        # Avg Exit Price = 51500
        # PnL Gross = (51500 - 50000) * 1.0 = 1500

        # We can inspect the calls to query to check the data in _merge_via_temp_table
        # It should have been called once for the temp table creation and merge
        assert mock_bq.query.called
        call_args_list = mock_bq.query.call_args_list
        # The last call should contain our JSON data in the parameters
        last_call = call_args_list[-1]
        job_config = last_call[1]["job_config"]
        json_data = job_config.query_parameters[0].value
        import json

        rows = json.loads(json_data)
        row = rows[0]

        assert row["trade_id"] == "pos_123"
        assert row["exit_price"] == 51500.0

        # PnL USD = Gross - Fees
        # Gross PnL = (51500 - 50000) * 1.0 = 1500
        # Actual Fees = 0.0001 * 50000 = 5.0 USD (Derived from mocked activity)
        # PnL USD = 1500 - 5.0 = 1495.0

        assert row["fees_usd"] == 5.0
        assert row["pnl_usd"] == 1495.0
        assert row["fee_calculation_type"] == "ACTUAL_CFEE"

        # B. Check Cleanup
        # Should call batch.delete with document reference
        mock_firestore.collection.return_value.document.assert_called_with("pos_123")
        pipeline.firestore_client.batch.return_value.delete.assert_called()
        pipeline.firestore_client.batch.return_value.commit.assert_called()


if __name__ == "__main__":
    test_trade_archival_orchestration_flow()
