"""
Unit tests for the ExpiredSignalArchivalPipeline.
"""

import unittest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
from crypto_signals.domain.schemas import AssetClass, ExpiredSignal, OrderSide
from crypto_signals.pipelines.expired_signal_archival import ExpiredSignalArchivalPipeline


class TestExpiredSignalArchivalPipeline(unittest.TestCase):
    """
    Test suite for the ExpiredSignalArchivalPipeline.
    """

    def setUp(self):
        """
        Set up the test environment.
        """
        self.settings_patcher = patch("crypto_signals.pipelines.base.get_settings")
        self.firestore_patcher = patch(
            "crypto_signals.pipelines.expired_signal_archival.firestore.Client"
        )
        self.market_provider_patcher = patch(
            "crypto_signals.pipelines.expired_signal_archival.MarketDataProvider"
        )
        self.bq_patcher = patch("crypto_signals.pipelines.base.bigquery.Client")

        self.mock_get_settings = self.settings_patcher.start()
        self.mock_firestore_client_class = self.firestore_patcher.start()
        self.mock_market_provider_class = self.market_provider_patcher.start()
        self.mock_bq_client_class = self.bq_patcher.start()

        self.addCleanup(self.settings_patcher.stop)
        self.addCleanup(self.firestore_patcher.stop)
        self.addCleanup(self.market_provider_patcher.stop)
        self.addCleanup(self.bq_patcher.stop)

        self.mock_get_settings.return_value.ENVIRONMENT = "TEST"
        self.pipeline = ExpiredSignalArchivalPipeline()
        self.pipeline.firestore_client = self.mock_firestore_client_class.return_value
        self.pipeline.market_provider = self.mock_market_provider_class.return_value

    def test_extract(self):
        """
        Test the extract method.
        """
        mock_collection = MagicMock()
        self.pipeline.firestore_client.collection.return_value = mock_collection
        mock_collection.where.return_value.where.return_value.stream.return_value = [
            MagicMock(id="doc_1", to_dict=lambda: {"signal_id": "1"}),
            MagicMock(id="doc_2", to_dict=lambda: {"signal_id": "2"}),
        ]

        data = self.pipeline.extract()

        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["signal_id"], "1")
        self.assertEqual(data[0]["doc_id"], "doc_1")

    def test_transform(self):
        """
        Test the transform method.
        """
        raw_data = [
            {
                "ds": date(2023, 1, 1),
                "signal_id": "1",
                "strategy_id": "test_strategy",
                "symbol": "BTC/USD",
                "asset_class": AssetClass.CRYPTO,
                "side": OrderSide.BUY,
                "entry_price": 50000.0,
                "suggested_stop": 49000.0,
                "created_at": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "valid_until": datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            }
        ]

        bars_df = pd.DataFrame(
            {"high": [51000.0], "low": [49000.0]},
            index=[pd.to_datetime("2023-01-01 12:00:00+00:00")],
        )
        self.pipeline.market_provider.get_daily_bars.return_value = bars_df

        transformed_data = self.pipeline.transform(raw_data)

        self.assertEqual(len(transformed_data), 1)
        self.assertEqual(transformed_data[0]["signal_id"], "1")
        self.assertEqual(transformed_data[0]["max_mfe_during_validity"], 1000.0)
        self.assertAlmostEqual(transformed_data[0]["distance_to_trigger_pct"], -2.0)

    def test_transform_sell_signal(self):
        """
        Test the transform method for a SELL signal.
        """
        raw_data = [
            {
                "ds": date(2023, 1, 1),
                "signal_id": "1",
                "strategy_id": "test_strategy",
                "symbol": "BTC/USD",
                "asset_class": AssetClass.CRYPTO,
                "side": OrderSide.SELL,
                "entry_price": 50000.0,
                "suggested_stop": 51000.0,
                "created_at": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "valid_until": datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            }
        ]

        bars_df = pd.DataFrame(
            {"high": [51000.0], "low": [49000.0]},
            index=[pd.to_datetime("2023-01-01 12:00:00+00:00")],
        )
        self.pipeline.market_provider.get_daily_bars.return_value = bars_df

        transformed_data = self.pipeline.transform(raw_data)

        self.assertEqual(len(transformed_data), 1)
        self.assertEqual(transformed_data[0]["signal_id"], "1")
        self.assertEqual(transformed_data[0]["max_mfe_during_validity"], 1000.0)
        self.assertAlmostEqual(transformed_data[0]["distance_to_trigger_pct"], -2.0)

    def test_transform_no_market_data(self):
        """
        Test the transform method when no market data is available.
        """
        raw_data = [
            {
                "ds": date(2023, 1, 1),
                "signal_id": "1",
                "strategy_id": "test_strategy",
                "symbol": "BTC/USD",
                "asset_class": AssetClass.CRYPTO,
                "side": OrderSide.BUY,
                "entry_price": 50000.0,
                "suggested_stop": 49000.0,
                "created_at": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "valid_until": datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            }
        ]

        self.pipeline.market_provider.get_daily_bars.return_value = pd.DataFrame()

        transformed_data = self.pipeline.transform(raw_data)

        self.assertEqual(len(transformed_data), 0)

    def test_transform_no_market_data_in_window(self):
        """
        Test the transform method when no market data is available in the validity window.
        """
        raw_data = [
            {
                "ds": date(2023, 1, 1),
                "signal_id": "1",
                "strategy_id": "test_strategy",
                "symbol": "BTC/USD",
                "asset_class": AssetClass.CRYPTO,
                "side": OrderSide.BUY,
                "entry_price": 50000.0,
                "suggested_stop": 49000.0,
                "created_at": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "valid_until": datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            }
        ]

        bars_df = pd.DataFrame(
            {"high": [51000.0], "low": [49000.0]},
            index=[pd.to_datetime("2023-01-03 12:00:00+00:00")],
        )
        self.pipeline.market_provider.get_daily_bars.return_value = bars_df

        transformed_data = self.pipeline.transform(raw_data)

        self.assertEqual(len(transformed_data), 0)

    def test_transform_caching(self):
        """
        Test the transform method's caching logic.
        """
        raw_data = [
            {
                "ds": date(2023, 1, 1),
                "signal_id": "1",
                "strategy_id": "test_strategy",
                "symbol": "BTC/USD",
                "asset_class": AssetClass.CRYPTO,
                "side": OrderSide.BUY,
                "entry_price": 50000.0,
                "suggested_stop": 49000.0,
                "created_at": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "valid_until": datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            },
            {
                "ds": date(2023, 1, 1),
                "signal_id": "2",
                "strategy_id": "test_strategy",
                "symbol": "BTC/USD",
                "asset_class": AssetClass.CRYPTO,
                "side": OrderSide.BUY,
                "entry_price": 50000.0,
                "suggested_stop": 49000.0,
                "created_at": datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "valid_until": datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            },
        ]

        bars_df = pd.DataFrame(
            {"high": [51000.0], "low": [49000.0]},
            index=[pd.to_datetime("2023-01-01 12:00:00+00:00")],
        )
        self.pipeline.market_provider.get_daily_bars.return_value = bars_df

        self.pipeline.transform(raw_data)

        self.pipeline.market_provider.get_daily_bars.assert_called_once()

    def test_cleanup(self):
        """
        Test the cleanup method.
        """
        data = [
            {
                "doc_id": "doc_1",
                "ds": date(2023, 1, 1),
                "signal_id": "1",
                "strategy_id": "test_strategy",
                "symbol": "BTC/USD",
                "asset_class": AssetClass.CRYPTO,
                "side": OrderSide.BUY,
                "entry_price": 50000.0,
                "suggested_stop": 49000.0,
                "valid_until": datetime(2023, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            }
        ]

        # The base class's `run` method re-validates the transformed data, so we
        # need to pass instances of the schema model to `cleanup`.
        cleanup_data = [ExpiredSignal.model_validate(d) for d in data]

        mock_batch = MagicMock()
        self.pipeline.firestore_client.batch.return_value = mock_batch

        self.pipeline.cleanup(cleanup_data)

        mock_batch.delete.assert_called_once()
        mock_batch.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
