"""
Tests for Fee Patch Pipeline (Issue #140).

Verifies that the pipeline reconciles fees for both CRYPTO and EQUITY trades.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.pipelines.fee_patch import FeePatchPipeline


class TestFeePatchPipeline:
    """Test Fee Patch Pipeline logic."""

    @pytest.fixture
    def mock_pipeline_components(self):
        """Provides a patched FeePatchPipeline instance and its mocks."""
        with (
            patch("crypto_signals.pipelines.fee_patch.bigquery.Client") as mock_bq_class,
            patch("crypto_signals.config.get_settings") as mock_settings,
            patch(
                "crypto_signals.pipelines.fee_patch.ExecutionEngine"
            ) as mock_engine_class,
        ):
            mock_settings.return_value.GOOGLE_CLOUD_PROJECT = "test-project"
            mock_settings.return_value.ENVIRONMENT = "PROD"
            pipeline = FeePatchPipeline()
            yield pipeline, mock_bq_class.return_value, mock_engine_class.return_value

    @pytest.mark.parametrize(
        "asset_class",
        [
            pytest.param("EQUITY", id="equity_included"),
            pytest.param("CRYPTO", id="crypto_included"),
        ],
    )
    def test_query_unfinalized_trades_includes_all_assets(
        self, mock_pipeline_components, asset_class
    ):
        """Test that the query includes both CRYPTO and EQUITY trades."""
        pipeline, mock_bq_client, _ = mock_pipeline_components

        # Mock query results
        mock_row = {
            "trade_id": f"trade-{asset_class}",
            "symbol": "BTC/USD" if asset_class == "CRYPTO" else "AAPL",
            "asset_class": asset_class,
            "entry_time": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "exit_time": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "entry_order_id": "order-1",
            "exit_order_id": "order-2",
            "fees_usd": 0.0,  # This will be mapped to estimated_fee_usd in results
            "ds": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc).date(),
        }

        mock_query_job = MagicMock()
        # BigQuery results are row objects that can be converted to dict
        mock_query_job.result.return_value = [mock_row]
        mock_bq_client.query.return_value = mock_query_job

        # Act
        results = pipeline._query_unfinalized_trades()

        # Assert
        found = any(t["asset_class"] == asset_class for t in results)
        assert found, f"Expected {asset_class} trade in unfinalized query results"

        # Verify the SQL query does NOT contain the filter
        query_call = mock_bq_client.query.call_args[0][0]
        assert (
            "AND asset_class = 'CRYPTO'" not in query_call
        ), "Query should not filter by CRYPTO only"

    def test_patch_trade_fees_equity(self, mock_pipeline_components):
        """Test patching an EQUITY trade (should result in $0 fees, ESTIMATED)."""
        pipeline, mock_bq_client, mock_engine = mock_pipeline_components

        # Alpaca returns $0 for equity
        mock_engine.get_crypto_fees_by_orders.return_value = {
            "total_fee_usd": 0.0,
            "fee_tier": None,
        }

        trade = {
            "trade_id": "equity-trade",
            "symbol": "AAPL",
            "asset_class": "EQUITY",
            "entry_time": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "exit_time": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "entry_order_id": "order-1",
            "exit_order_id": "order-2",
            "estimated_fee_usd": 0.0,
        }

        # Act
        success = pipeline._patch_trade_fees(trade)

        # Assert
        assert success is True
        mock_engine.get_crypto_fees_by_orders.assert_called_once()

        # Verify BQ update
        update_call = mock_bq_client.query.call_args
        job_config = update_call[1]["job_config"]
        params = {p.name: p.value for p in job_config.query_parameters}
        assert params["actual_fee_usd"] == 0.0
        assert params["fee_calculation_type"] == "ESTIMATED"
        assert params["fee_tier"] is None

    def test_patch_trade_fees_crypto(self, mock_pipeline_components):
        """Test patching a CRYPTO trade (should use ACTUAL_CFEE if fees > 0)."""
        pipeline, mock_bq_client, mock_engine = mock_pipeline_components

        mock_engine.get_crypto_fees_by_orders.return_value = {
            "total_fee_usd": 1.25,
            "fee_tier": "Tier 0: 0.25%",
        }

        trade = {
            "trade_id": "crypto-trade",
            "symbol": "BTC/USD",
            "asset_class": "CRYPTO",
            "entry_time": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "exit_time": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "entry_order_id": "order-1",
            "exit_order_id": "order-2",
            "estimated_fee_usd": 1.0,
        }

        # Act
        success = pipeline._patch_trade_fees(trade)

        # Assert
        assert success is True

        # Verify BQ update
        update_call = mock_bq_client.query.call_args
        job_config = update_call[1]["job_config"]
        params = {p.name: p.value for p in job_config.query_parameters}
        assert params["actual_fee_usd"] == 1.25
        assert params["fee_calculation_type"] == "ACTUAL_CFEE"
        assert params["fee_tier"] == "Tier 0: 0.25%"
