"""
Fee Patch Pipeline (Issue #140).

This pipeline reconciles estimated fees with actual CFEE data from Alpaca.
Runs at the start of main.py to finalize fees for trades older than 24 hours.

Pattern: "Query-Fetch-Update"
1. Query: Get BigQuery rows where fee_finalized = FALSE and age > 24h
2. Fetch: Call Alpaca Activities API for CFEE records
3. Update: Patch BigQuery with actual fees and set fee_finalized = TRUE
"""

from datetime import timedelta
from typing import Any, Dict, List

from google.cloud import bigquery
from loguru import logger

from crypto_signals.config import get_settings, get_trading_client
from crypto_signals.engine.execution import ExecutionEngine


class FeePatchPipeline:
    """
    Pipeline to reconcile estimated fees with actual CFEE data.

    Runs daily before signal generation to finalize fees for closed trades.
    """

    # Configuration Constants
    CFEE_SETTLEMENT_HOURS = 24  # Alpaca T+1 settlement window
    MAX_TRADES_PER_RUN = 100  # Batch size for performance and rate limiting

    def __init__(self, execution_engine: Any | None = None):
        """Initialize the pipeline."""
        settings = get_settings()
        self.bq_client = bigquery.Client(project=settings.GOOGLE_CLOUD_PROJECT)

        # Environment-aware table routing
        env_suffix = "" if settings.ENVIRONMENT == "PROD" else "_test"
        self.fact_table_id = (
            f"{settings.GOOGLE_CLOUD_PROJECT}.crypto_analytics.fact_trades{env_suffix}"
        )

        if execution_engine:
            self.execution_engine = execution_engine
        else:
            self.execution_engine = ExecutionEngine(trading_client=get_trading_client())

    def run(self) -> int:
        """
        Run the fee patch pipeline.

        Returns:
            Number of trades patched
        """
        logger.info("[fee_patch] Starting fee reconciliation...")

        # Step 1: Query unfinalized trades older than 24 hours
        unfinalized_trades = self._query_unfinalized_trades()

        if not unfinalized_trades:
            logger.info("[fee_patch] No trades to reconcile")
            return 0

        logger.info(f"[fee_patch] Found {len(unfinalized_trades)} trades to reconcile")

        # Step 2: Fetch CFEE and update BigQuery
        patched_count = 0
        for trade in unfinalized_trades:
            if self._patch_trade_fees(trade):
                patched_count += 1

        logger.info(
            f"[fee_patch] Reconciled {patched_count}/{len(unfinalized_trades)} trades"
        )
        return patched_count

    def _query_unfinalized_trades(self) -> List[Dict[str, Any]]:
        """
        Query BigQuery for trades with unfinalized fees older than 24 hours.

        Returns:
            List of trade dictionaries
        """
        # Reconcile fees for all asset classes.
        # Crypto: patches estimated fees with actual CFEE data.
        # Equity: marks fee_finalized=TRUE (fees are $0, no CFEE events).
        query = f"""
        SELECT
            trade_id,
            symbol,
            asset_class,
            entry_time,
            exit_time,
            entry_order_id,
            exit_order_id,
            fees_usd as estimated_fee_usd,
            ds
        FROM `{self.fact_table_id}`
        WHERE fee_finalized = FALSE
          AND exit_time < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {self.CFEE_SETTLEMENT_HOURS} HOUR)
        ORDER BY exit_time ASC
        LIMIT {self.MAX_TRADES_PER_RUN}
        """

        query_job = self.bq_client.query(query)
        results = query_job.result()

        return [dict(row) for row in results]

    def _patch_trade_fees(self, trade: Dict[str, Any]) -> bool:
        """
        Fetch actual CFEE and update BigQuery for a single trade.

        Args:
            trade: Trade dictionary from BigQuery

        Returns:
            True if patched successfully
        """
        try:
            # Collect all order IDs for this trade
            order_ids = []
            if trade.get("entry_order_id"):
                order_ids.append(trade["entry_order_id"])
            if trade.get("exit_order_id"):
                order_ids.append(trade["exit_order_id"])

            if not order_ids:
                logger.warning(
                    f"[fee_patch] No order IDs for trade {trade['trade_id']}, skipping"
                )
                return False

            # Fetch CFEE from Alpaca
            # Use entry_time - 1 day to exit_time + 2 days for settlement window
            start_date = (trade["entry_time"] - timedelta(days=1)).date()
            end_date = (trade["exit_time"] + timedelta(days=2)).date()

            cfee_result = self.execution_engine.get_crypto_fees_by_orders(
                order_ids=order_ids,
                symbol=trade["symbol"],
                start_date=start_date,
                end_date=end_date,
            )

            actual_fee_usd = cfee_result["total_fee_usd"]
            fee_tier = cfee_result["fee_tier"]

            # Determine fee calculation type
            if actual_fee_usd > 0:
                fee_calculation_type = "ACTUAL_CFEE"
            else:
                # No CFEE found, keep estimate
                fee_calculation_type = "ESTIMATED"
                actual_fee_usd = trade["estimated_fee_usd"]

            # Update BigQuery
            update_query = f"""
            UPDATE `{self.fact_table_id}`
            SET
                fee_finalized = TRUE,
                actual_fee_usd = @actual_fee_usd,
                fee_calculation_type = @fee_calculation_type,
                fee_tier = @fee_tier,
                fee_reconciled_at = CURRENT_TIMESTAMP(),
                fees_usd = @actual_fee_usd,
                pnl_usd = pnl_usd + (fees_usd - @actual_fee_usd)
            WHERE trade_id = @trade_id
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter(
                        "actual_fee_usd", "FLOAT64", actual_fee_usd
                    ),
                    bigquery.ScalarQueryParameter(
                        "fee_calculation_type", "STRING", fee_calculation_type
                    ),
                    bigquery.ScalarQueryParameter("fee_tier", "STRING", fee_tier),
                    bigquery.ScalarQueryParameter(
                        "trade_id", "STRING", trade["trade_id"]
                    ),
                ]
            )

            update_job = self.bq_client.query(update_query, job_config=job_config)
            update_job.result()

            logger.info(
                f"[fee_patch] Patched {trade['trade_id']}: "
                f"${trade['estimated_fee_usd']:.2f} → ${actual_fee_usd:.2f} ({fee_calculation_type})"
            )

            return True

        except Exception as e:
            logger.error(
                f"[fee_patch] Failed to patch {trade['trade_id']}.",
                extra={"trade_id": trade["trade_id"], "error": str(e)},
            )
            return False
