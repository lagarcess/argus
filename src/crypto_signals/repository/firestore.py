"""Firestore Repository for persisting signals and positions.

Dev Note: Enable GCP native TTL policy with:
  gcloud firestore fields ttls update delete_at --collection-group=live_signals --enable-ttl
  gcloud firestore fields ttls update delete_at --collection-group=rejected_signals --enable-ttl
  gcloud firestore fields ttls update delete_at --collection-group=live_positions --enable-ttl
  gcloud firestore fields ttls update delete_at --collection-group=test_signals --enable-ttl
  gcloud firestore fields ttls update delete_at --collection-group=test_rejected_signals --enable-ttl
  gcloud firestore fields ttls update delete_at --collection-group=test_positions --enable-ttl
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, cast

from crypto_signals.config import get_settings
from crypto_signals.domain.schemas import (
    AssetClass,
    Position,
    Signal,
    SignalStatus,
    StrategyConfig,
    TradeStatus,
)
from crypto_signals.observability import log_validation_error
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from loguru import logger
from pydantic import ValidationError


class JobLockRepository:
    """Repository for managing distributed job locks."""

    def __init__(self):
        """Initialize Firestore client."""
        settings = get_settings()
        self.db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        self.collection_name = "job_locks"

    def acquire_lock(self, job_id: str, ttl_minutes: int = 10) -> bool:
        """
        Attempt to acquire a distributed lock.

        Args:
            job_id: Unique identifier for the job (e.g., 'signal_generation_cron').
            ttl_minutes: Time-to-live for the lock in minutes.

        Returns:
            bool: True if lock acquired, False if already held by another valid instance.
        """
        doc_ref = self.db.collection(self.collection_name).document(job_id)

        @firestore.transactional
        def _acquire_in_transaction(transaction):
            snapshot = doc_ref.get(transaction=transaction)
            now = datetime.now(timezone.utc)

            if snapshot.exists:
                data = snapshot.to_dict()
                expire_at = data.get("expire_at")
                # Ensure we handle timezone-aware datetimes correctly
                if expire_at:
                    if expire_at > now:
                        return False  # Lock still valid
            new_expiry = now + timedelta(minutes=ttl_minutes)
            transaction.set(
                doc_ref,
                {"locked_at": now, "expire_at": new_expiry, "job_id": job_id},
            )
            return True

        try:
            return cast(bool, _acquire_in_transaction(self.db.transaction()))
        except Exception as e:
            logger.error(
                "Failed to acquire lock for {job_id}.",
                extra={"job_id": job_id, "error": str(e)},
            )
            return False

    def release_lock(self, job_id: str) -> None:
        """Release the job lock."""
        try:
            self.db.collection(self.collection_name).document(job_id).delete()
            logger.info(f"Released lock for {job_id}")
        except Exception as e:
            logger.error(
                "Failed to release lock for {job_id}.",
                extra={"job_id": job_id, "error": str(e)},
            )


class SignalRepository:
    """Repository for storing signals in Firestore."""

    def __init__(self):
        """Initialize Firestore client."""
        self.settings = get_settings()
        self.db = firestore.Client(project=self.settings.GOOGLE_CLOUD_PROJECT)

        # Environment Isolation: Route non-prod traffic to test_signals
        if self.settings.ENVIRONMENT == "PROD":
            self.collection_name = "live_signals"
        else:
            self.collection_name = "test_signals"

    def save(self, signal: Signal) -> None:
        """Save a signal to Firestore.

        Note: delete_at is populated by SignalGenerator (driven by config.py).
        """
        data = signal.model_dump(mode="python")
        if "ds" in data and isinstance(data["ds"], date):
            data["ds"] = data["ds"].isoformat()
        doc_ref = self.db.collection(self.collection_name).document(signal.signal_id)
        doc_ref.set(data)

    def get_active_signals(self, symbol: str) -> list[Signal]:
        """
        Get all ACTIVE signals for a given symbol.

        Active statuses: WAITING, ACTIVE, TP1_HIT, TP2_HIT.
        """
        # Firestore 'in' query allows up to 10 values
        active_statuses = [
            SignalStatus.WAITING.value,
            SignalStatus.ACTIVE.value,
            SignalStatus.TP1_HIT.value,
            SignalStatus.TP2_HIT.value,
        ]

        query = (
            self.db.collection(self.collection_name)
            .where(filter=FieldFilter("symbol", "==", symbol))
            .where(filter=FieldFilter("status", "in", active_statuses))
        )

        results = []
        for doc in query.stream():
            try:
                results.append(Signal(**doc.to_dict()))
            except ValidationError as e:
                # Display Rich error panel for database drift
                log_validation_error(doc.id, e)

                # Auto-delete invalid legacy document if enabled
                if self.settings.CLEANUP_ON_FAILURE:
                    doc.reference.delete()
                    logger.info(f"Auto-deleted invalid legacy signal: {doc.id}")
                else:
                    logger.warning(
                        f"Skipping invalid signal: {doc.id} (cleanup disabled)"
                    )

        return results

    def update_signal(self, signal: Signal) -> None:
        """Update an existing signal in Firestore (merged update)."""
        doc_ref = self.db.collection(self.collection_name).document(signal.signal_id)
        data = signal.model_dump(mode="python")
        if "ds" in data and isinstance(data["ds"], date):
            data["ds"] = data["ds"].isoformat()
        doc_ref.set(data, merge=True)

    def get_by_id(self, signal_id: str) -> Signal | None:
        """
        Get a signal by its ID.

        Args:
            signal_id: The unique signal identifier.

        Returns:
            Signal object if found, None otherwise.
        """
        doc = self.db.collection(self.collection_name).document(signal_id).get()
        if doc.exists:
            try:
                return Signal(**doc.to_dict())
            except ValidationError as e:
                log_validation_error(doc.id, e)

                # Auto-delete invalid legacy document if enabled
                if self.settings.CLEANUP_ON_FAILURE:
                    doc.reference.delete()
                    logger.info(f"Auto-deleted invalid legacy signal: {doc.id}")

                return None
        return None

    def update_signal_atomic(self, signal_id: str, updates: Dict[str, Any]) -> bool:
        """
        Atomically update signal fields using Firestore transaction.

        Use for status changes where race conditions are possible
        (e.g., concurrent signal processing runs).

        Args:
            signal_id: The signal ID to update.
            updates: Dictionary of field updates.

        Returns:
            bool: True if update succeeded, False otherwise.
        """
        doc_ref = self.db.collection(self.collection_name).document(signal_id)

        @firestore.transactional
        def update_in_transaction(transaction):
            snapshot = doc_ref.get(transaction=transaction)
            if not snapshot.exists:
                return False
            transaction.update(doc_ref, updates)
            return True

        try:
            return cast(bool, update_in_transaction(self.db.transaction()))
        except Exception as e:
            logger.error(
                f"Atomic update failed for {signal_id}.",
                extra={"signal_id": signal_id, "error": str(e)},
            )
            return False

    def cleanup_expired(self) -> int:
        """Delete signals that have reached their physical expiration (delete_at).

        Returns:
            The number of deleted signals.
        """
        now = datetime.now(timezone.utc)

        logger.info(
            f"Cleaning up signals in '{self.collection_name}' that expired before {now}"
        )

        query = self.db.collection(self.collection_name).where(
            filter=FieldFilter("delete_at", "<", now)
        )

        # Batch delete for efficiency
        batch = self.db.batch()
        count = 0

        for doc in query.stream():
            batch.delete(doc.reference)
            count += 1

            # Firestore batch limit is 500 operations
            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()
                logger.info(f"Deleted {count} expired signals (batch)")

        # Commit remaining deletes if any
        if count > 0 and count % 400 != 0:
            batch.commit()

        logger.info(f"Cleanup complete: Deleted {count} expired signals")
        return count

    def flush_all(self) -> int:
        """Delete ALL signals in the collection. Use with caution!

        Returns:
            int: Number of documents deleted.
        """
        logger.warning(
            f"FLUSH ALL: Deleting all documents from {self.collection_name} collection"
        )

        # Batch delete for efficiency
        batch = self.db.batch()
        count = 0

        for doc in self.db.collection(self.collection_name).stream():
            batch.delete(doc.reference)
            count += 1

            # Firestore batch limit is 500 operations
            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()
                logger.info(f"Flushed {count} signals (batch)")

        # Commit remaining deletes if any
        if count > 0 and count % 400 != 0:
            batch.commit()

        logger.warning(f"FLUSH ALL complete: Deleted {count} total signals")
        return count

    def get_most_recent_exit(
        self, symbol: str, hours: int = 48, pattern_name: str | None = None
    ) -> Signal | None:
        """Get most recent exit signal for a symbol within specified hours.

        Used by cooldown logic (Issue #117) to prevent double-signal noise.
        Includes both profit exits (TP1/2/3_HIT) and stop-loss exits (INVALIDATED)
        to prevent "revenge trading" after losses.

        Args:
            symbol: Trading pair symbol (e.g., "BTC/USD")
            hours: Lookback window in hours (default 48)
            pattern_name: Optional pattern name filter (only return exits from same pattern)

        Returns:
            Signal | None: Most recent exit signal, or None if no exits found

        Note:
            This method requires a Firestore composite index on:
            - symbol (ASC)
            - status (ASC)
            - timestamp (DESC)

        Strategic Feedback Applied:
            - Includes INVALIDATED status (revenge trading prevention)
            - Exit level mapping: TP1_HIT -> take_profit_1, TP2_HIT -> take_profit_2,
              TP3_HIT -> take_profit_3, INVALIDATED -> suggested_stop
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Use SignalStatus enum for exit statuses (Fix #3)
        # Strategic Feedback: Include INVALIDATED to prevent revenge trading (stop-loss hits)
        exit_statuses = [
            SignalStatus.TP1_HIT,
            SignalStatus.TP2_HIT,
            SignalStatus.TP3_HIT,
            SignalStatus.INVALIDATED,
        ]

        query = (
            self.db.collection(self.collection_name)
            .where(filter=FieldFilter("symbol", "==", symbol))
            .where(filter=FieldFilter("status", "in", [s.value for s in exit_statuses]))
            .where(filter=FieldFilter("exit_time", ">=", cutoff_time))
            .order_by("exit_time", direction=firestore.Query.DESCENDING)
            .limit(1)
        )

        # Optional pattern filter (Fix #2 - prevents different patterns from being blocked)
        if pattern_name:
            query = query.where(filter=FieldFilter("pattern_name", "==", pattern_name))

        docs = query.stream()
        for doc in docs:
            # Cast to Signal to satisfy MyPy's strict type checking
            return cast(Signal, Signal.model_validate(doc.to_dict()))

        return None


class RejectedSignalRepository:
    """Repository for storing rejected (shadow) signals in Firestore.

    Shadow signals are patterns that were detected but failed quality gates
    (e.g., Volume < 1.5x, R:R < 1.5). They are persisted for:
    - Backtesting analysis (Phase 8)
    - Filter optimization
    - Market regime analysis
    """

    def __init__(self):
        """Initialize Firestore client."""
        settings = get_settings()
        self.db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)

        # Environment Isolation
        if settings.ENVIRONMENT == "PROD":
            self.collection_name = "rejected_signals"
        else:
            self.collection_name = "test_rejected_signals"

    def save(self, signal: Signal) -> None:
        """Save a rejected signal to Firestore.

        Args:
            signal: Signal with status=REJECTED_BY_FILTER and rejection_reason populated
        """
        if signal.status != SignalStatus.REJECTED_BY_FILTER:
            logger.warning(
                f"RejectedSignalRepository.save() called with non-rejected signal: "
                f"{signal.signal_id} (status={signal.status})"
            )
            return

        data = signal.model_dump(mode="python")
        if "ds" in data and isinstance(data["ds"], date):
            data["ds"] = data["ds"].isoformat()
        # rejected_at is set here (repository-level metadata)
        # delete_at is already set by SignalGenerator (7-day TTL for rejected signals)
        data["rejected_at"] = datetime.now(timezone.utc)

        doc_ref = self.db.collection(self.collection_name).document(signal.signal_id)
        doc_ref.set(data)

        logger.debug(
            f"[SHADOW] Saved rejected signal: {signal.symbol} {signal.pattern_name} - "
            f"{signal.rejection_reason}"
        )

    def get_rejections_by_symbol(self, symbol: str, days: int = 7) -> list[Signal]:
        """Get recent rejected signals for a symbol.

        Useful for analyzing which patterns are being filtered most often.

        Args:
            symbol: Trading symbol (e.g., "BTC/USD")
            days: Look back period in days (default: 7)

        Returns:
            List of rejected Signal objects
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = (
            self.db.collection(self.collection_name)
            .where(filter=FieldFilter("symbol", "==", symbol))
            .where(filter=FieldFilter("rejected_at", ">=", cutoff))
        )

        results = []
        for doc in query.stream():
            try:
                results.append(Signal(**doc.to_dict()))
            except ValidationError as e:
                log_validation_error(doc.id, e)
                # Auto-delete invalid legacy document
                doc.reference.delete()

        return results

    def get_rejection_stats(self, days: int = 7) -> dict[str, int]:
        """Get aggregated rejection counts by reason.

        Returns:
            Dict mapping rejection_reason to count
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = self.db.collection(self.collection_name).where(
            filter=FieldFilter("rejected_at", ">=", cutoff)
        )

        stats: dict[str, int] = {}
        for doc in query.stream():
            data = doc.to_dict()
            reason = data.get("rejection_reason", "Unknown")
            stats[reason] = stats.get(reason, 0) + 1

        return stats

    def cleanup_expired(self) -> int:
        """Delete expired rejected signals based on delete_at. Returns count deleted."""
        now = datetime.now(timezone.utc)
        query = self.db.collection(self.collection_name).where(
            filter=FieldFilter("delete_at", "<", now)
        )

        batch = self.db.batch()
        count = 0

        for doc in query.stream():
            batch.delete(doc.reference)
            count += 1

            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()

        if count > 0 and count % 400 != 0:
            batch.commit()

        if count > 0:
            logger.info(f"Cleaned up {count} expired rejected signals")

        return count

    def flush_all(self) -> int:
        """Delete ALL rejected signals in the collection. Use with caution!

        Returns:
            int: Number of documents deleted.
        """
        logger.warning(
            f"FLUSH ALL: Deleting all documents from {self.collection_name} collection"
        )

        batch = self.db.batch()
        count = 0

        for doc in self.db.collection(self.collection_name).stream():
            batch.delete(doc.reference)
            count += 1

            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()

        if count > 0 and count % 400 != 0:
            batch.commit()

        logger.warning(f"FLUSH ALL complete: Deleted {count} total rejected signals")
        return count


class PositionRepository:
    """Repository for storing positions in Firestore."""

    def __init__(self):
        """Initialize Firestore client."""
        settings = get_settings()
        self.db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)

        # Environment Isolation
        if settings.ENVIRONMENT == "PROD":
            self.collection_name = "live_positions"
        else:
            self.collection_name = "test_positions"

    def save(self, position: Position) -> None:
        """
        Save a position to Firestore.

        Uses position_id as document ID for idempotency with Alpaca order IDs.
        Only sets created_at on new documents to preserve original timestamp.
        """
        doc_ref = self.db.collection(self.collection_name).document(position.position_id)

        # Check if document exists to preserve created_at
        doc = doc_ref.get()
        position_data = position.model_dump(mode="python")
        if "ds" in position_data and isinstance(position_data["ds"], date):
            position_data["ds"] = position_data["ds"].isoformat()

        # Remove created_at from payload to allow logic below to handle it
        # This prevents overwriting existing created_at with None if the model has it as None
        if "created_at" in position_data:
            del position_data["created_at"]

        if doc.exists:
            # Update existing document, preserve created_at
            position_data["updated_at"] = datetime.now(timezone.utc)
        else:
            # New document, set created_at
            position_data["created_at"] = datetime.now(timezone.utc)

        doc_ref.set(position_data, merge=True)
        logger.info(
            f"Position {position.position_id} saved to Firestore",
            extra={
                "position_id": position.position_id,
                "signal_id": position.signal_id,
                "status": position.status.value,
            },
        )

    def count_open_positions_by_class(self, asset_class: AssetClass) -> int:
        """
        Count number of OPEN positions for a specific asset class.
        Used by RiskEngine for sector capping.

        Requires Composite Index: status (ASC) + asset_class (ASC)
        """
        try:
            # Optimize: Use Count Query (Aggregation) which is cheaper/faster than fetching docs
            query = (
                self.db.collection(self.collection_name)
                .where(filter=FieldFilter("status", "==", TradeStatus.OPEN.value))
                .where(filter=FieldFilter("asset_class", "==", asset_class))
                .count()
            )

            # Execute aggregation
            results = query.get()
            return int(results[0][0].value)

        except Exception as e:
            logger.error(
                f"Error counting open positions for {asset_class}.",
                extra={"asset_class": asset_class, "error": str(e)},
            )
            # Safety first -> block trading on DB error.
            return 9999

    def get_open_positions(self) -> list[Position]:
        """Get all OPEN positions."""
        query = self.db.collection(self.collection_name).where(
            filter=FieldFilter("status", "==", TradeStatus.OPEN.value)
        )

        results = []
        for doc in query.stream():
            try:
                results.append(Position(**doc.to_dict()))
            except ValidationError as e:
                log_validation_error(doc.id, e)
                logger.warning(f"Skipped invalid position document: {doc.id}")

        return results

    def get_position_by_signal(self, signal_id: str) -> Position | None:
        """Get position by its originating signal ID."""
        query = (
            self.db.collection(self.collection_name)
            .where(filter=FieldFilter("signal_id", "==", signal_id))
            .limit(1)
        )

        for doc in query.stream():
            try:
                return Position(**doc.to_dict())
            except ValidationError as e:
                log_validation_error(doc.id, e)
                return None

        return None

    def get_open_position_by_symbol(self, symbol: str) -> Position | None:
        """
        Get the current OPEN position for a symbol.
        Used to prevent pyramiding (double buying).
        """
        query = (
            self.db.collection(self.collection_name)
            .where(filter=FieldFilter("symbol", "==", symbol))
            .where(filter=FieldFilter("status", "==", TradeStatus.OPEN.value))
            .limit(1)
        )

        for doc in query.stream():
            try:
                return Position(**doc.to_dict())
            except ValidationError as e:
                log_validation_error(doc.id, e)
                return None
        return None

    def update_position(self, position: Position) -> None:
        """Update an existing position in Firestore."""
        doc_ref = self.db.collection(self.collection_name).document(position.position_id)
        data = position.model_dump(mode="python")
        if "ds" in data and isinstance(data["ds"], date):
            data["ds"] = data["ds"].isoformat()
        data["updated_at"] = datetime.now(timezone.utc)
        doc_ref.set(data, merge=True)

    def get_closed_positions(self, limit: int = 50) -> list[Position]:
        """Get recently closed positions for orphan detection (Issue #139).

        Used by StateReconciler to detect positions marked CLOSED in Firestore
        but still OPEN in Alpaca (reverse orphans).

        Args:
            limit: Maximum number of positions to return (default: 50)

        Returns:
            List of recently closed Position objects
        """
        query = (
            self.db.collection(self.collection_name)
            .where(filter=FieldFilter("status", "==", TradeStatus.CLOSED.value))
            .order_by("exit_time", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        results = []
        for doc in query.stream():
            try:
                results.append(Position(**doc.to_dict()))
            except ValidationError as e:
                log_validation_error(doc.id, e)
                logger.warning(f"Skipped invalid closed position: {doc.id}")

        return results

    def get_positions_by_status_and_time(
        self, status: TradeStatus, hours_lookback: int = 24
    ) -> list[Position]:
        """
        Get positions with a specific status updated within the last N hours.

        Args:
            status: The status to filter by (e.g., TradeStatus.CLOSED).
            hours_lookback: Number of hours to look back.

        Returns:
            List of matching Position objects.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_lookback)

        query = (
            self.db.collection(self.collection_name)
            .where(filter=FieldFilter("status", "==", status.value))
            .where(filter=FieldFilter("updated_at", ">=", cutoff_time))
            .order_by("updated_at", direction=firestore.Query.DESCENDING)
        )

        results = []
        for doc in query.stream():
            try:
                # Use Position model validation
                results.append(Position(**doc.to_dict()))
            except ValidationError as e:
                log_validation_error(doc.id, e)
                logger.warning(f"Skipped invalid position: {doc.id}")

        return results

    def cleanup_expired(self) -> int:
        """Delete positions past their TTL (delete_at). Returns count deleted."""
        now = datetime.now(timezone.utc)
        logger.info(f"Cleaning up positions that expired before {now}")

        query = self.db.collection(self.collection_name).where(
            filter=FieldFilter("delete_at", "<", now)
        )

        batch = self.db.batch()
        count = 0

        for doc in query.stream():
            batch.delete(doc.reference)
            count += 1

            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()

        if count > 0 and count % 400 != 0:
            batch.commit()

        if count > 0:
            logger.info(f"Cleaned up {count} expired positions")

        return count

    def flush_all(self) -> int:
        """Delete ALL positions in the collection. Use with caution!

        Returns:
            int: Number of documents deleted.
        """
        logger.warning(
            f"FLUSH ALL: Deleting all documents from {self.collection_name} collection"
        )

        batch = self.db.batch()
        count = 0

        for doc in self.db.collection(self.collection_name).stream():
            batch.delete(doc.reference)
            count += 1

            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()

        if count > 0 and count % 400 != 0:
            batch.commit()

        logger.warning(f"FLUSH ALL complete: Deleted {count} total positions")
        return count


class JobMetadataRepository:
    """Repository for storing job metadata, like last run timestamps."""

    def __init__(self):
        """Initialize Firestore client."""
        settings = get_settings()
        self.db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        self.collection_name = "job_metadata"

    def get_last_run_date(self, job_id: str) -> Optional[date]:
        """
        Get the last run date for a specific job.

        Args:
            job_id: The unique identifier for the job.

        Returns:
            The last run date, or None if the job has never run.
        """
        doc_ref = self.db.collection(self.collection_name).document(job_id)
        snapshot = doc_ref.get()
        if snapshot.exists:
            data = snapshot.to_dict()
            last_run_str = data.get("last_run_date")
            if last_run_str:
                return date.fromisoformat(last_run_str)
        return None

    def update_last_run_date(self, job_id: str, run_date: date) -> None:
        """
        Update the last run date for a specific job.

        Args:
            job_id: The unique identifier for the job.
            run_date: The date the job was run.
        """
        self.save_job_metadata(job_id, {"last_run_date": run_date})

    def save_job_metadata(self, job_id: str, metadata: Dict[str, Any]) -> None:
        """
        Save job metadata to Firestore (merge update).

        Args:
            job_id: The unique identifier for the job.
            metadata: Dictionary of metadata to save. Dates are auto-serialized.
        """
        doc_ref = self.db.collection(self.collection_name).document(job_id)
        data = self._serialize_metadata(metadata)
        doc_ref.set(data, merge=True)

    def _serialize_metadata(self, data: Any) -> Any:
        """Recursively serialize date objects to ISO strings."""
        if isinstance(data, dict):
            return {k: self._serialize_metadata(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_metadata(v) for v in data]
        elif isinstance(data, (datetime, date)):
            return data.isoformat()
        return data


class StrategyRepository:
    """Repository for managing Strategy configurations (dim_strategies)."""

    def __init__(self):
        """Initialize Firestore client."""
        settings = get_settings()
        self.db = firestore.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        self.collection_name = "dim_strategies"

    def get_all_strategies(self) -> list[StrategyConfig]:
        """
        Get all strategies from Firestore.

        Returns:
            List of StrategyConfig objects.
        """
        logger.info(f"Fetching all strategies from {self.collection_name}")
        collection_ref = self.db.collection(self.collection_name)
        docs = list(collection_ref.stream())

        strategies = []
        for doc in docs:
            data = doc.to_dict()
            # Ensure strategy_id exists (use doc.id if missing)
            if "strategy_id" not in data:
                data["strategy_id"] = doc.id

            try:
                strategies.append(StrategyConfig(**data))
            except ValidationError as e:
                log_validation_error(doc.id, e)
                logger.warning(f"Skipping invalid strategy config: {doc.id}")

        return strategies

    def save(self, strategy: StrategyConfig) -> None:
        """Save a strategy configuration."""
        doc_ref = self.db.collection(self.collection_name).document(strategy.strategy_id)
        doc_ref.set(strategy.model_dump(mode="json"))
        logger.info(f"Saved strategy config: {strategy.strategy_id}")

    def get_active_strategy_configs(self) -> list[StrategyConfig]:
        """Returns only active=True strategies from Firestore."""
        logger.info(f"Fetching active strategies from {self.collection_name}")
        query = self.db.collection(self.collection_name).where(
            filter=FieldFilter("active", "==", True)
        )
        strategies = []
        for doc in query.stream():
            data = doc.to_dict()
            if "strategy_id" not in data:
                data["strategy_id"] = doc.id
            try:
                strategies.append(StrategyConfig(**data))
            except ValidationError as e:
                log_validation_error(doc.id, e)
                logger.warning(f"Skipping invalid strategy config: {doc.id}")
        return strategies
