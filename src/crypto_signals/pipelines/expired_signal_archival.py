"""
Expired Signal Archival Pipeline.

This pipeline moves EXPIRED signals from Firestore to BigQuery for "noise"
analysis. This helps answer the question: "Is our signal generation too
sensitive?" by analyzing signals that never triggered.

Pattern: "Extract-Transform-Load"
1. Extract: Get EXPIRED signals from Firestore.
2. Transform:
    - Fetch market data for the signal's validity period.
    - Calculate max_mfe_during_validity (Max Favorable Excursion).
    - Calculate distance_to_trigger_pct (how close it came to entry).
3. Load: Push to BigQuery fact_signals_expired table.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pandas as pd
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from loguru import logger
from pydantic import BaseModel

from crypto_signals.config import (
    get_crypto_data_client,
    get_stock_data_client,
)
from crypto_signals.domain.schemas import ExpiredSignal, OrderSide
from crypto_signals.market.data_provider import MarketDataProvider
from crypto_signals.pipelines.base import BigQueryPipelineBase


class ExpiredSignalArchivalPipeline(BigQueryPipelineBase):
    """
    Archives expired signals to BigQuery for sensitivity analysis.
    """

    def __init__(self):
        """Initialize the pipeline with specific configuration."""
        # settings is available via self.settings after super().__init__
        super().__init__(
            job_name="expired_signal_archival",
            staging_table_id=None,
            fact_table_id="",  # Placeholder
            id_column="signal_id",
            partition_column="ds",
            schema_model=ExpiredSignal,
        )

        env_suffix = "" if self.settings.ENVIRONMENT == "PROD" else "_test"
        self.fact_table_id = f"{self.settings.GOOGLE_CLOUD_PROJECT}.crypto_analytics.fact_signals_expired{env_suffix}"

        self.firestore_client = firestore.Client(
            project=self.settings.GOOGLE_CLOUD_PROJECT
        )
        self.source_collection = (
            "live_signals" if self.settings.ENVIRONMENT == "PROD" else "test_signals"
        )
        stock_client = get_stock_data_client()
        crypto_client = get_crypto_data_client()
        self.market_provider = MarketDataProvider(stock_client, crypto_client)

    def extract(self) -> List[Any]:
        """Extract EXPIRED signals from Firestore older than 24 hours."""
        logger.info(f"[{self.job_name}] extracting EXPIRED signals from Firestore...")

        # Only process signals that expired at least 24 hours ago
        # This prevents race conditions with the main signal processing loop
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)

        docs = (
            self.firestore_client.collection(self.source_collection)
            .where(filter=FieldFilter("status", "==", "EXPIRED"))
            .where(filter=FieldFilter("valid_until", "<", cutoff))
            .stream()
        )

        raw_data = []
        for doc in docs:
            data = doc.to_dict()
            if data:
                data["doc_id"] = doc.id  # Capture the actual document ID
                raw_data.append(data)

        logger.info(f"[{self.job_name}] extracted {len(raw_data)} expired signals.")
        return raw_data

    def transform(self, raw_data: List[Any]) -> List[Dict[str, Any]]:
        """
        Enrich expired signals with market data analysis.
        """
        logger.info(
            f"[{self.job_name}] Enriching {len(raw_data)} expired signals with market data..."
        )

        transformed = []
        symbol_bars_cache: Dict[str, pd.DataFrame] = {}

        for sig in raw_data:
            try:
                symbol = sig.get("symbol")
                asset_class = sig.get("asset_class", "CRYPTO")
                cache_key = f"{symbol}_{asset_class}"

                if cache_key in symbol_bars_cache:
                    bars_df = symbol_bars_cache[cache_key]
                else:
                    time.sleep(0.1)  # Rate limit safety
                    bars_df = self.market_provider.get_daily_bars(
                        symbol=symbol,
                        asset_class=asset_class,
                        lookback_days=3650,  # Fetch up to 10 years of data
                    )
                    symbol_bars_cache[cache_key] = bars_df

                if bars_df.empty:
                    logger.warning(
                        f"[{self.job_name}] No market data found for {symbol}. Skipping signal {sig.get('signal_id')}."
                    )
                    continue

                created_at = sig.get("created_at")
                valid_until = sig.get("valid_until")

                if not created_at or not valid_until:
                    logger.warning(
                        f"Invalid or missing timestamps for signal {sig.get('signal_id')}. Skipping."
                    )
                    continue

                validity_window_df = bars_df[
                    (bars_df.index >= pd.to_datetime(created_at, utc=True))
                    & (bars_df.index <= pd.to_datetime(valid_until, utc=True))
                ]

                if validity_window_df.empty:
                    logger.warning(
                        f"[{self.job_name}] No market data in validity window for signal {sig.get('signal_id')}. Skipping."
                    )
                    continue

                entry_price = float(sig.get("entry_price", 0.0))
                side = sig.get("side", "buy").lower()

                max_mfe = None
                distance_to_trigger = None

                if side == OrderSide.BUY.value:
                    highest_high = validity_window_df["high"].max()
                    if pd.notna(highest_high):
                        max_mfe = highest_high - entry_price
                        if entry_price > 0:
                            distance_to_trigger = (
                                (entry_price - highest_high) / entry_price * 100
                            )
                else:  # SELL
                    lowest_low = validity_window_df["low"].min()
                    if pd.notna(lowest_low):
                        max_mfe = entry_price - lowest_low
                        if entry_price > 0:
                            distance_to_trigger = (
                                (lowest_low - entry_price) / entry_price * 100
                            )

                expired_signal = ExpiredSignal(
                    doc_id=sig.get("doc_id"),
                    ds=sig.get("ds"),
                    signal_id=sig.get("signal_id"),
                    strategy_id=sig.get("strategy_id"),
                    symbol=symbol,
                    asset_class=asset_class,
                    side=side,
                    entry_price=entry_price,
                    suggested_stop=sig.get("suggested_stop"),
                    valid_until=valid_until,
                    max_mfe_during_validity=max_mfe,
                    distance_to_trigger_pct=distance_to_trigger,
                )
                transformed.append(expired_signal.model_dump(mode="json"))

            except Exception as e:
                logger.error(
                    f"[{self.job_name}] Failed to transform signal "
                    f"{sig.get('signal_id')}: {e}"
                )
                continue

        return transformed

    def cleanup(self, data: List[BaseModel]) -> None:
        """
        Delete processed expired signals from Firestore.
        """
        if not data:
            return

        logger.info(
            f"[{self.job_name}] Cleaning up {len(data)} records from Firestore..."
        )

        batch = self.firestore_client.batch()
        count = 0

        for item in data:
            # The base class's `run` method ensures all items are instances
            # of the pipeline's `schema_model` (ExpiredSignal).
            doc_id = item.doc_id  # type: ignore[attr-defined]
            ref = self.firestore_client.collection(self.source_collection).document(
                doc_id
            )
            batch.delete(ref)
            count += 1

            if count >= 400:  # Firestore batch limit is 500
                batch.commit()
                batch = self.firestore_client.batch()
                count = 0

        if count > 0:
            batch.commit()

        logger.info(f"[{self.job_name}] Cleanup complete.")
