"""
Strategy Synchronization Pipeline (SCD Type 2).

This pipeline syncs strategy configurations from Firestore (dim_strategies)
to BigQuery (dim_strategies), maintaining a full history of changes (SCD Type 2).
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from loguru import logger

from crypto_signals.domain.schemas import StagingStrategy
from crypto_signals.pipelines.base import BigQueryPipelineBase
from crypto_signals.repository.firestore import StrategyRepository


class StrategySyncPipeline(BigQueryPipelineBase):
    """
    SCD Type 2 Pipeline for Strategy Configuration.

    Detects changes in Firestore strategy config and creates versioned
    records in BigQuery.
    """

    # Config fields tracked for change detection
    RELEVANT_CONFIG_KEYS = [
        "active",
        "timeframe",
        "asset_class",
        "assets",
        "risk_params",
        "confluence_config",
        "pattern_overrides",
        "pattern_name",
    ]

    def __init__(self):
        # settings is available via self.settings after super().__init__
        super().__init__(
            job_name="strategy_sync",
            staging_table_id=None,
            fact_table_id="",  # Placeholder
            id_column="strategy_id",  # Not strictly used in custom merge
            partition_column="valid_from",  # Used for partitioning if applicable
            schema_model=StagingStrategy,
        )
        self.fact_table_id = (
            f"{self.settings.GOOGLE_CLOUD_PROJECT}.crypto_analytics.dim_strategies"
        )
        self.repository = StrategyRepository()

    def _calculate_hash(self, config_data: Dict[str, Any]) -> str:
        """Calculate a deterministic hash of the configuration."""
        subset = {k: config_data.get(k) for k in self.RELEVANT_CONFIG_KEYS}

        # Sort keys for deterministic JSON serialization
        serialized = json.dumps(subset, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _get_bq_current_state(self) -> Dict[str, str]:
        """
        Fetch the current active version hash for each strategy from BigQuery.
        Returns: Dict[strategy_id, config_hash]
        """
        if not self._check_table_exists(self.fact_table_id):
            logger.warning(
                f"Target table {self.fact_table_id} does not exist. Assuming empty state."
            )
            return {}

        query = f"""
            SELECT strategy_id, config_hash
            FROM `{self.fact_table_id}`
            WHERE valid_to IS NULL
        """
        try:
            results = self.bq_client.query(query).result()
            return {row.strategy_id: row.config_hash for row in results}
        except Exception as e:
            logger.warning(
                "Failed to fetch BQ state. Assuming empty state.",
                extra={"error": str(e)},
            )
            return {}

    def extract(self) -> List[Dict[str, Any]]:
        """
        Extract strategies from Firestore and determine changes.
        """
        logger.info("Extracting strategies from Firestore...")
        strategies = self.repository.get_all_strategies()

        if not strategies:
            logger.info("No strategies found in Firestore.")
            return []

        # Get current state from BQ
        bq_state = self._get_bq_current_state()

        new_versions = []
        now = datetime.now(timezone.utc)

        for strategy in strategies:
            try:
                # Convert Pydantic model to dict for processing
                data = strategy.model_dump(mode="python")

                # Calculate Hash
                config_hash = self._calculate_hash(data)

                strategy_id = strategy.strategy_id
                current_hash = bq_state.get(strategy_id)

                if current_hash != config_hash:
                    logger.info(
                        f"Change detected for {strategy_id}. New Hash: {config_hash[:8]}"
                    )

                    # Validate required 'active' field explicitly
                    if "active" not in data:
                        logger.error(
                            f"Strategy {strategy_id} missing required 'active' field"
                        )
                        continue

                    # Create Staging Record
                    staging_record = {
                        "strategy_id": strategy_id,
                        "active": data["active"],
                        "timeframe": data.get("timeframe", ""),
                        "asset_class": data.get("asset_class", "CRYPTO"),
                        "assets": data.get("assets", []),
                        "risk_params": json.dumps(
                            data.get("risk_params", {}), sort_keys=True, default=str
                        ),
                        "confluence_config": json.dumps(
                            data.get("confluence_config", {}), sort_keys=True, default=str
                        ),
                        "pattern_overrides": json.dumps(
                            data.get("pattern_overrides", {}), sort_keys=True, default=str
                        ),
                        "pattern_name": data.get("pattern_name"),
                        "config_hash": config_hash,
                        "valid_from": now,
                        "valid_to": None,
                        "is_current": True,
                    }
                    new_versions.append(staging_record)
                else:
                    logger.debug(f"No change for {strategy_id}")

            except Exception as e:
                logger.error(
                    f"Error processing strategy {strategy.strategy_id}.",
                    extra={"strategy_id": strategy.strategy_id, "error": str(e)},
                )
                continue

        logger.info(f"Found {len(new_versions)} strategy updates.")
        return new_versions

    def cleanup(self, data: List[Any]) -> None:
        """No-op for strategy sync (we don't delete source)."""
        pass

    def _get_merge_sql(self, source_table_id: str) -> str:
        """
        Execute SCD Type 2 Merge.
        1. Close old records (Update valid_to)
        2. Insert new records
        """
        # 1. Update existing current records that have a new version in staging
        # We join Staging on strategy_id.
        update_query = f"""
            UPDATE `{self.fact_table_id}` AS T
            SET
                valid_to = S.valid_from,
                is_current = FALSE
            FROM `{source_table_id}` AS S
            WHERE T.strategy_id = S.strategy_id
              AND T.valid_to IS NULL;
        """

        # 2. Insert new records
        insert_query = f"""
            INSERT INTO `{self.fact_table_id}`
            (strategy_id, active, timeframe, asset_class, assets, risk_params, confluence_config, pattern_overrides, pattern_name, config_hash, valid_from, valid_to, is_current)
            SELECT
                strategy_id, active, timeframe, asset_class, assets, risk_params, confluence_config, pattern_overrides, pattern_name, config_hash, valid_from, valid_to, is_current
            FROM `{source_table_id}`;
        """

        return f"""
            BEGIN TRANSACTION;
            {update_query}
            {insert_query}
            COMMIT TRANSACTION;
        """
