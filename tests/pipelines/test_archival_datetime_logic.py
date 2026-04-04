import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from crypto_signals.pipelines.trade_archival import TradeArchivalPipeline


class TestArchivalDatetimeLogic(unittest.TestCase):
    """
    Verification suite for Datetime Fallback Logic.
    Ensures that missing Firestore timestamps default to Alpaca Order timestamps
    instead of datetime.now().
    """

    @patch("crypto_signals.pipelines.base.get_settings")
    @patch("crypto_signals.pipelines.trade_archival.get_trading_client")
    @patch("crypto_signals.pipelines.trade_archival.get_stock_data_client")
    @patch("crypto_signals.pipelines.trade_archival.get_crypto_data_client")
    @patch("google.cloud.firestore.Client")
    @patch("crypto_signals.pipelines.base.bigquery.Client")
    @patch("crypto_signals.pipelines.base.SchemaGuardian")
    @patch("crypto_signals.engine.execution.ExecutionEngine")
    def test_datetime_fallback_to_alpaca(
        self,
        mock_execution_engine_cls,  # Bottom-most
        mock_schema_guardian,
        mock_bq_cls,
        mock_firestore_cls,
        mock_get_crypto,
        mock_get_stock,
        mock_get_trading,  # The one we need
        mock_get_settings,  # Top-most
    ):
        """
        Verify that if Firestore entry_time is None, we use Alpaca order.filled_at.
        """
        # Setup Pipeline
        mock_trading_client = mock_get_trading.return_value

        pipeline = TradeArchivalPipeline()

        # 1. Setup Data with MISSING timestamps
        raw_pos = {
            "position_id": "test_pos_1",
            "account_id": "acc_test_123",
            "strategy_id": "strat_test_A",
            "entry_time": None,  # MISSING
            "exit_time": None,  # MISSING
            "symbol": "BTC/USD",
            "asset_class": "CRYPTO",
            "side": "buy",
            "qty": 1.0,
            "entry_fill_price": 50000.0,
            "exit_fill_price": 51000.0,
            "status": "CLOSED",
        }

        # 2. Setup Alpaca Order with VALID timestamp
        expected_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        mock_order = MagicMock()
        mock_order.id = "alpaca_123"
        mock_order.filled_avg_price = 50000.0
        mock_order.filled_qty = 1.0
        mock_order.side = "buy"
        mock_order.filled_at = expected_time  # Expected Timestamp
        mock_order.submitted_at = expected_time
        mock_order.updated_at = expected_time

        mock_trading_client.get_order_by_client_id.return_value = mock_order

        # Mock Market Provider to avoid errors
        pipeline.market_provider = MagicMock()
        pipeline.market_provider.get_daily_bars.return_value.empty = True

        # Mock Execution Engine Fee Tier (Required for pipeline transform)
        mock_engine_instance = mock_execution_engine_cls.return_value
        mock_engine_instance.get_current_fee_tier.return_value = {
            "tier_name": "Tier 0",
            "taker_fee_pct": 0.1,
            "maker_fee_pct": 0.1,
        }

        # 3. Execute Transform
        results = pipeline.transform([raw_pos])

        # 4. Verification
        self.assertEqual(len(results), 1)
        trade = results[0]

        # The Critical Assertion:
        # entry_time should be the ALAPACA time.
        # Compare as datetimes to avoid 'Z' vs '+00:00' string mismatch
        actual_entry = datetime.fromisoformat(trade["entry_time"].replace("Z", "+00:00"))
        actual_exit = datetime.fromisoformat(trade["exit_time"].replace("Z", "+00:00"))

        self.assertEqual(actual_entry, expected_time)
        self.assertEqual(actual_exit, expected_time)

        print("\nTEST PASSED: Used Alpaca Timestamp instead of NOW().")


if __name__ == "__main__":
    unittest.main()
