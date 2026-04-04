"""
Backtest Archival Pipeline (Issue #361).

Unified pipeline to archive ALL terminal-state signals from Firestore to
BigQuery's fact_theoretical_signals table. Replaces both
rejected_signal_archival.py and expired_signal_archival.py (which remain
running in parallel during the 30-day validation window per Issue #368).

Covers four signal outcomes:
1. REJECTED_BY_FILTER — from rejected_signals collection
2. EXPIRED           — from live_signals (status=EXPIRED)
3. INVALIDATED       — from live_signals (status=INVALIDATED)
4. EXECUTED (parent)  — from live_signals (status=TP1/TP2/TP3_HIT)

Pattern: Extract → Transform → Load → Cleanup
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

import pandas as pd
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from loguru import logger
from pydantic import BaseModel

from crypto_signals.config import (
    get_crypto_data_client,
    get_stock_data_client,
)
from crypto_signals.domain.schemas import (
    AssetClassFee,
    FactTheoreticalSignal,
    OrderSide,
    SignalStatus,
)
from crypto_signals.market.data_provider import MarketDataProvider
from crypto_signals.pipelines.base import BigQueryPipelineBase

# Validity window — only archive rejected signals older than 7 days
VALIDITY_WINDOW_DAYS = 7

# Maximum number of documents to extract per collection/status per run
EXTRACTION_BATCH_LIMIT = 100

# Terminal statuses to extract from live_signals
_TERMINAL_LIVE_STATUSES = [
    SignalStatus.EXPIRED.value,
    SignalStatus.INVALIDATED.value,
    SignalStatus.TP1_HIT.value,
    SignalStatus.TP2_HIT.value,
    SignalStatus.TP3_HIT.value,
]

# Statuses where the parent signal was executed — do NOT delete from
# Firestore during cleanup (trade_archival.py still references them).
_EXECUTED_STATUSES = frozenset(
    {
        SignalStatus.TP1_HIT.value,
        SignalStatus.TP2_HIT.value,
        SignalStatus.TP3_HIT.value,
    }
)


class BacktestArchivalPipeline(BigQueryPipelineBase):
    """
    Archives all terminal-state signals to fact_theoretical_signals.

    Covers: REJECTED_BY_FILTER, EXPIRED, INVALIDATED, and parent
    live_signals of EXECUTED trades (for ML indicator preservation).
    """

    def __init__(self) -> None:
        """Initialize the pipeline with specific configuration."""
        super().__init__(
            job_name="backtest_archival",
            staging_table_id=None,
            fact_table_id="",  # Set below after settings are available
            id_column="signal_id",
            partition_column="ds",
            schema_model=FactTheoreticalSignal,
            clustering_fields=["status", "strategy_id", "symbol"],
        )

        env_suffix = "" if self.settings.ENVIRONMENT == "PROD" else "_test"
        self.fact_table_id = (
            f"{self.settings.GOOGLE_CLOUD_PROJECT}"
            f".crypto_analytics.fact_theoretical_signals{env_suffix}"
        )

        # Source clients
        self.firestore_client = firestore.Client(
            project=self.settings.GOOGLE_CLOUD_PROJECT
        )
        self.rejected_collection = (
            "rejected_signals"
            if self.settings.ENVIRONMENT == "PROD"
            else "test_rejected_signals"
        )
        self.live_collection = (
            "live_signals" if self.settings.ENVIRONMENT == "PROD" else "test_signals"
        )

        # Market data for theoretical P&L
        stock_client = get_stock_data_client()
        crypto_client = get_crypto_data_client()
        self.market_provider = MarketDataProvider(stock_client, crypto_client)

    # ------------------------------------------------------------------
    # Extract
    # ------------------------------------------------------------------

    def extract(self) -> List[Any]:
        """
        Extract terminal-state signals from two Firestore collections.

        1. rejected_signals — all docs older than 7 days
        2. live_signals — filtered to terminal statuses

        Each record is tagged with ``_source_collection`` for cleanup routing
        and ``_doc_id`` for explicit document ID mapping (KB [2026-01-27]).
        """
        logger.info(
            "Extracting terminal signals from Firestore",
            extra={"job": self.job_name},
        )

        raw_data: List[Dict[str, Any]] = []

        # --- 1. Rejected signals ---
        cutoff = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=VALIDITY_WINDOW_DAYS)

        rejected_docs = (
            self.firestore_client.collection(self.rejected_collection)
            .where(filter=FieldFilter("created_at", "<", cutoff))
            .limit(EXTRACTION_BATCH_LIMIT)
            .stream()
        )

        for doc in rejected_docs:
            data = doc.to_dict()
            if data:
                data["_doc_id"] = doc.id
                data["source_collection"] = self.rejected_collection
                raw_data.append(data)

        rejected_count = len(raw_data)

        # --- 2. Live signals (terminal statuses) ---
        for status in _TERMINAL_LIVE_STATUSES:
            live_docs = (
                self.firestore_client.collection(self.live_collection)
                .where(filter=FieldFilter("status", "==", status))
                .limit(EXTRACTION_BATCH_LIMIT)
                .stream()
            )
            for doc in live_docs:
                data = doc.to_dict()
                if data:
                    data["_doc_id"] = doc.id
                    data["source_collection"] = self.live_collection
                    raw_data.append(data)

        live_count = len(raw_data) - rejected_count

        logger.info(
            "Extraction complete",
            extra={
                "job": self.job_name,
                "rejected_count": rejected_count,
                "live_count": live_count,
                "total": len(raw_data),
            },
        )
        return raw_data

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    def transform(
        self, raw_data: List[Any], now: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Map each Firestore doc to a FactTheoreticalSignal record.

        Use 'now' to ensure all records share a consistent timestamp for ds/created_at
        if original timestamps are missing (determinism for testing).

        ETL Zombie Prevention (KB [2026-03-02]): NEVER use ``continue`` to
        silently drop a record.  If market data is missing or validation
        fails, assign a deterministic placeholder and pass the record along
        so ``cleanup()`` can still delete it from Firestore.
        """
        logger.info(
            "Transforming signals",
            extra={"job": self.job_name, "count": len(raw_data)},
        )

        if now is None:
            now = datetime.now(timezone.utc)

        transformed: List[Dict[str, Any]] = []

        for signal in raw_data:
            try:
                record = self._map_to_theoretical(signal, now=now)
                model = FactTheoreticalSignal.model_validate(record)
                transformed.append(model.model_dump(mode="json"))
            except Exception as e:
                logger.warning(
                    "Failed to transform signal, using placeholder",
                    extra={
                        "signal_id": signal.get("signal_id"),
                        "error": str(e),
                    },
                )
                try:
                    placeholder = self._make_placeholder(signal, error=str(e), now=now)
                    model = FactTheoreticalSignal.model_validate(placeholder)
                    transformed.append(model.model_dump(mode="json"))
                except Exception as e2:
                    # Last resort — log and continue (record is truly broken)
                    logger.error(
                        "Placeholder construction also failed",
                        extra={
                            "signal_id": signal.get("signal_id"),
                            "error": str(e2),
                        },
                    )

        logger.info(
            "Transformation complete",
            extra={"job": self.job_name, "transformed": len(transformed)},
        )
        return transformed

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self, data: list[BaseModel]) -> None:
        """
        Delete archived signals from Firestore after successful BQ load.

        Routes deletes to the correct source collection.
        Deletes all terminal signals, including parent live_signals of
        EXECUTED trades (now safe since it runs after trade_archival).
        """
        if not data:
            return

        logger.info(
            "Starting cleanup",
            extra={"job": self.job_name, "records": len(data)},
        )

        # Group by source collection for efficient batching
        collections: Dict[str, List[str]] = {}

        for item in data:
            doc_id = getattr(item, "doc_id", None) or getattr(item, "signal_id", None)
            collection = getattr(item, "source_collection", None)

            if not doc_id or not collection:
                logger.warning(
                    "Skipping cleanup for item missing doc_id or source_collection",
                    extra={"job": self.job_name, "doc_id": doc_id},
                )
                continue

            collections.setdefault(collection, []).append(str(doc_id))

        # Batch delete per collection (max 400 per batch per Firestore skill)
        for collection_name, doc_ids in collections.items():
            batch = self.firestore_client.batch()
            count = 0

            for doc_id in doc_ids:
                ref = self.firestore_client.collection(collection_name).document(doc_id)
                batch.delete(ref)
                count += 1

                if count >= 400:
                    batch.commit()
                    batch = self.firestore_client.batch()
                    count = 0

            if count > 0:
                batch.commit()

        logger.info(
            "Cleanup complete",
            extra={"job": self.job_name},
        )

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _map_to_theoretical(
        self, signal: Dict[str, Any], *, now: datetime
    ) -> Dict[str, Any]:
        """Map a Firestore signal doc to FactTheoreticalSignal fields."""
        status = signal.get("status", SignalStatus.REJECTED_BY_FILTER.value)
        created_at = signal.get("created_at")
        if created_at is None:
            created_at = now
        symbol = signal.get("symbol")
        asset_class = signal.get("asset_class", "CRYPTO")
        entry_price = float(signal.get("entry_price") or 0)
        stop_loss = float(signal.get("suggested_stop") or 0)
        take_profit_1 = float(signal.get("take_profit_1") or 0)
        side = signal.get("side", OrderSide.BUY.value)

        # Classify trade type based on status
        trade_type = self._classify_trade_type(status, signal)

        # Calculate theoretical P&L (for non-executed signals)
        pnl = self._calculate_theoretical_pnl(
            symbol=symbol,
            asset_class=asset_class,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            side=side,
            created_at=created_at,
            status=status,
            rejection_reason=signal.get("rejection_reason", ""),
        )

        # Near-miss analysis for EXPIRED signals
        distance_to_trigger = None
        if status == SignalStatus.EXPIRED.value and pnl["bars_df"] is not None:
            distance_to_trigger = self._calculate_distance_to_trigger(
                pnl["bars_df"], entry_price, side
            )

        # FK to fact_trades for EXECUTED signals
        linked_trade_id = None
        if status in _EXECUTED_STATUSES:
            linked_trade_id = signal.get("signal_id")

        return {
            "doc_id": signal.get("_doc_id"),
            "ds": (created_at.date() if hasattr(created_at, "date") else created_at),
            "signal_id": signal.get("signal_id"),
            "strategy_id": signal.get("strategy_id", "UNKNOWN"),
            "symbol": symbol,
            "asset_class": asset_class,
            "side": side,
            "status": status,
            "trade_type": trade_type,
            "exit_reason": signal.get("exit_reason"),
            "rejection_reason": signal.get("rejection_reason"),
            "entry_price": entry_price,
            "pattern_name": signal.get("pattern_name", "UNKNOWN"),
            "suggested_stop": stop_loss,
            "take_profit_1": take_profit_1,
            "take_profit_2": float(signal.get("take_profit_2") or 0) or None,
            "take_profit_3": float(signal.get("take_profit_3") or 0) or None,
            "valid_until": signal.get("valid_until", created_at),
            "created_at": created_at,
            # Structural metadata (ML preservation)
            "pattern_classification": signal.get("pattern_classification"),
            "pattern_duration_days": signal.get("pattern_duration_days"),
            "pattern_span_days": signal.get("pattern_span_days"),
            "conviction_tier": signal.get("conviction_tier"),
            "structural_context": signal.get("structural_context"),
            # Nested JSON fields
            "confluence_factors": signal.get("confluence_factors", []),
            "confluence_snapshot": signal.get("confluence_snapshot"),
            "harmonic_metadata": signal.get("harmonic_metadata"),
            "rejection_metadata": signal.get("rejection_metadata"),
            "structural_anchors": signal.get("structural_anchors"),
            # Theoretical P&L
            "theoretical_exit_price": pnl["exit_price"],
            "theoretical_exit_reason": pnl["exit_reason"],
            "theoretical_exit_time": (
                pnl["exit_time"].isoformat()
                if hasattr(pnl["exit_time"], "isoformat")
                else str(pnl["exit_time"])
            )
            if pnl["exit_time"] is not None
            else None,
            "theoretical_pnl_usd": round(pnl["pnl_net"], 4),
            "theoretical_pnl_pct": round(pnl["pnl_pct"], 4),
            "theoretical_fees_usd": round(pnl["total_fees"], 6),
            # Near-miss
            "distance_to_trigger_pct": distance_to_trigger,
            # FK
            "linked_trade_id": linked_trade_id,
        }

    def _classify_trade_type(self, status: str, signal: Dict[str, Any]) -> str:
        """Determine trade_type classification from signal status."""
        if status in _EXECUTED_STATUSES:
            return "EXECUTED"
        if status == SignalStatus.REJECTED_BY_FILTER.value:
            rejection_reason = signal.get("rejection_reason", "")
            if rejection_reason and "VALIDATION_FAILED" in rejection_reason:
                return "VALIDATION_FAILED"
            return "FILTERED"
        if status == SignalStatus.INVALIDATED.value:
            return "THEORETICAL"
        if status == SignalStatus.EXPIRED.value:
            return "THEORETICAL"
        return "UNKNOWN"

    def _calculate_theoretical_pnl(
        self,
        *,
        symbol: Optional[str],
        asset_class: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        side: str,
        created_at: Any,
        status: str,
        rejection_reason: str,
    ) -> Dict[str, Any]:
        """
        Calculate theoretical P&L for a signal that was never executed.

        For EXECUTED (TP*_HIT) signals, P&L is already captured in
        fact_trades — we skip theoretical simulation and return zeros.

        Returns a dict with keys:
            exit_price, exit_reason, exit_time, pnl_net, pnl_pct,
            total_fees, bars_df
        """
        result: Dict[str, Any] = {
            "exit_price": None,
            "exit_reason": None,
            "exit_time": None,
            "pnl_net": 0.0,
            "pnl_pct": 0.0,
            "total_fees": 0.0,
            "bars_df": None,
        }

        # EXECUTED signals — real P&L lives in fact_trades
        if status in _EXECUTED_STATUSES:
            result["exit_reason"] = "EXECUTED_SEE_FACT_TRADES"
            return result

        # Validation failures — skip market data entirely
        is_validation_failure = (
            rejection_reason and "VALIDATION_FAILED" in rejection_reason
        )
        if is_validation_failure:
            result["exit_reason"] = "VALIDATION_FAILED_NO_EXECUTION"
            result["exit_time"] = created_at
            return result

        # Missing required fields — cannot simulate
        if not all([symbol, entry_price, stop_loss, take_profit_1]):
            result["exit_reason"] = "MISSING_SIGNAL_PARAMS"
            return result

        # Fetch market data
        bars_df = self.market_provider.get_daily_bars(
            symbol=symbol,
            asset_class=asset_class,
            lookback_days=30,
        )

        if bars_df.empty:
            result["exit_reason"] = "NO_MARKET_DATA"
            return result

        # Filter bars after signal creation
        if created_at:
            bars_df = bars_df[bars_df.index >= pd.Timestamp(created_at).floor("D")]
            if bars_df.empty:
                result["exit_reason"] = "NO_MARKET_DATA"
                return result

        result["bars_df"] = bars_df

        # Vectorized TP/SL simulation
        if side == OrderSide.BUY.value:
            tp_mask = bars_df["high"] >= take_profit_1
            sl_mask = bars_df["low"] <= stop_loss
        else:
            tp_mask = bars_df["low"] <= take_profit_1
            sl_mask = bars_df["high"] >= stop_loss

        hit_mask = tp_mask | sl_mask
        exit_price = None
        exit_reason = None
        exit_time = None

        if hit_mask.any():
            exit_time = hit_mask.idxmax()
            if tp_mask.loc[exit_time]:
                exit_price = take_profit_1
                exit_reason = "THEORETICAL_TP1"
            else:
                exit_price = stop_loss
                exit_reason = "THEORETICAL_SL"

        # Fallback — use latest close
        if exit_price is None:
            exit_price = float(bars_df.iloc[-1]["close"])
            exit_reason = "THEORETICAL_OPEN"
            exit_time = bars_df.index[-1]

        # Calculate P&L
        qty = 1.0  # Normalized unit
        if side == OrderSide.BUY.value:
            pnl_gross = (exit_price - entry_price) * qty
        else:
            pnl_gross = (entry_price - exit_price) * qty

        # Fee calculation (asset-class-aware)
        fee_enum = getattr(AssetClassFee, asset_class, None)
        fee_pct = fee_enum.value if fee_enum is not None else 0.0

        entry_fee = entry_price * qty * fee_pct
        exit_fee = exit_price * qty * fee_pct
        total_fees = entry_fee + exit_fee

        pnl_net = pnl_gross - total_fees
        pnl_pct = (pnl_net / (entry_price * qty)) * 100 if entry_price else 0

        result["exit_price"] = exit_price
        result["exit_reason"] = exit_reason
        result["exit_time"] = exit_time
        result["pnl_net"] = pnl_net
        result["pnl_pct"] = pnl_pct
        result["total_fees"] = total_fees
        return result

    def _calculate_distance_to_trigger(
        self,
        bars_df: pd.DataFrame,
        entry_price: float,
        side: str,
    ) -> Optional[float]:
        """Calculate how close an expired signal came to triggering."""
        if bars_df.empty or entry_price <= 0:
            return None

        if side == OrderSide.BUY.value:
            highest_high = bars_df["high"].max()
            if pd.notna(highest_high):
                return cast(float, (entry_price - highest_high) / entry_price * 100)
        else:
            lowest_low = bars_df["low"].min()
            if pd.notna(lowest_low):
                return cast(float, (lowest_low - entry_price) / entry_price * 100)

        return None

    def _make_placeholder(
        self, signal: Dict[str, Any], *, error: str, now: datetime
    ) -> Dict[str, Any]:
        """
        Build a minimal FactTheoreticalSignal record for a broken signal.

        Ensures the record passes through to cleanup() so the source doc
        is still deleted from Firestore (ETL Zombie Prevention).
        """
        created_at = signal.get("created_at", now)
        status = signal.get("status", SignalStatus.REJECTED_BY_FILTER.value)
        return {
            "doc_id": signal.get("_doc_id"),
            "ds": (created_at.date() if hasattr(created_at, "date") else created_at),
            "signal_id": signal.get("signal_id", "UNKNOWN"),
            "strategy_id": signal.get("strategy_id", "UNKNOWN"),
            "symbol": signal.get("symbol", "UNKNOWN"),
            "asset_class": signal.get("asset_class", "CRYPTO"),
            "side": signal.get("side", OrderSide.BUY.value),
            "status": status,
            "trade_type": "ERROR",
            "entry_price": float(signal.get("entry_price") or 0),
            "pattern_name": signal.get("pattern_name", "UNKNOWN"),
            "suggested_stop": float(signal.get("suggested_stop") or 0),
            "valid_until": signal.get("valid_until", created_at),
            "created_at": created_at,
            "theoretical_exit_reason": f"TRANSFORM_ERROR: {error}",
            "theoretical_pnl_usd": 0.0,
            "theoretical_pnl_pct": 0.0,
            "theoretical_fees_usd": 0.0,
        }
