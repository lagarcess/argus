"""
Base Pipeline Module.

This module provides the `BigQueryPipelineBase` class, which serves as the
Execution Engine for all data movement from Firestore (Operational) to
BigQuery (Analytical).

It implements the strict "Truncate -> Load (Staging) -> Merge (Fact)" pattern
to ensure idempotency and data consistency.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from loguru import logger
from pydantic import BaseModel

from crypto_signals.config import get_settings
from crypto_signals.engine.schema_guardian import SchemaGuardian, SchemaMismatchError


class BigQueryPipelineBase(ABC):
    """
    Abstract base class for Firestore-to-BigQuery pipelines.

    This class implements the "Heavy" pattern where the base class handles
    the complexity of BigQuery interactions (Truncate, Load, Merge), and
    subclasses focus on configuration and data extraction.

    Attributes:
        job_name: Human-readable name for logging (e.g. "trade_archival")
        staging_table_id: Full BigQuery ID for staging (project.dataset.table)
        fact_table_id: Full BigQuery ID for fact/target (project.dataset.table)
        id_column: Primary key column name for the MERGE join
        partition_column: Partition column name for the MERGE join
        schema_model: Pydantic model class for validation and schema definition
    """

    STAGING_CLEANUP_DAYS = 7

    def __init__(
        self,
        job_name: str,
        staging_table_id: Optional[str],
        fact_table_id: str,
        id_column: str,
        partition_column: str,
        schema_model: Type[BaseModel],
        clustering_fields: Optional[List[str]] = None,
    ):
        """Initialize the pipeline with configuration and BigQuery client."""
        if staging_table_id:
            logger.warning(
                f"[{job_name}] DEPRECATION: staging_table_id is no longer required. "
                "Persistent staging tables are being replaced by BQ Temp Tables."
            )

        self.job_name = job_name
        self.staging_table_id = staging_table_id
        self.fact_table_id = fact_table_id
        self.id_column = id_column
        self.partition_column = partition_column
        self.schema_model = schema_model
        self.clustering_fields = clustering_fields

        # Load settings once to ensure consistency and support patching in tests
        self.settings = get_settings()

        # Initialize BigQuery Client
        # We use the project from settings to ensure we target the right GCP env
        self.bq_client = bigquery.Client(project=self.settings.GOOGLE_CLOUD_PROJECT)

        # Initialize Schema Guardian
        # Note: V1 enforces Strict Mode everywhere.
        self.guardian = SchemaGuardian(
            self.bq_client, strict_mode=self.settings.SCHEMA_GUARDIAN_STRICT_MODE
        )

    @abstractmethod
    def extract(self) -> List[Any]:
        """
        Extract data from the source (e.g., Firestore).

        Returns:
            List of raw data objects (dicts or model instances).
        """

    @abstractmethod
    def cleanup(self, data: List[BaseModel]) -> None:
        """
        Delete processed records from the source system.

        Args:
            data: The list of validated Pydantic models that were successfully merged.
        """

    def transform(self, raw_data: List[Any]) -> List[Dict[str, Any]]:
        """
        Validate and transform raw data using the Pydantic schema.

        Args:
            raw_data: List of raw input data.

        Returns:
            List of dictionaries ready for BigQuery insertion.
        """
        logger.info(f"[{self.job_name}] Transforming {len(raw_data)} records...")
        transformed = []
        for item in raw_data:
            model = self.schema_model.model_validate(item)
            transformed.append(model.model_dump(mode="json"))

        return transformed

    def _check_table_exists(self, table_id: str) -> bool:
        """Check if a BigQuery table exists."""
        try:
            self.bq_client.get_table(table_id)
            return True
        except NotFound:
            return False

    def _get_merge_sql(self, source_table_id: str) -> str:
        """
        Generate the MERGE statement to upsert data from Source to Fact.

        Args:
            source_table_id: The table ID to use as the source (S).

        Returns:
            str: The full MERGE SQL statement.
        """
        # 1. Get all column names from the model
        columns = sorted(list(self.schema_model.model_fields.keys()))

        # 2. Build UPDATE clause (T.col = S.col)
        # We generally update ALL columns on match to ensure consistency
        update_list = []
        for col in columns:
            # Skip updating join keys (usually harmless if they match)
            if col not in [self.id_column, self.partition_column]:
                update_list.append(f"T.{col} = S.{col}")

        update_clause = ", ".join(update_list)

        # 3. Build INSERT clause
        insert_cols = ", ".join(columns)
        insert_vals = ", ".join([f"S.{col}" for col in columns])

        # 4. Construct the full MERGE query
        # Using `T` for Target (Fact) and `S` for Source (Staging)
        return f"""
            MERGE `{self.fact_table_id}` AS T
            USING `{source_table_id}` AS S
            ON T.{self.id_column} = S.{self.id_column}
            AND T.{self.partition_column} = S.{self.partition_column}
            WHEN MATCHED THEN
                UPDATE SET {update_clause}
            WHEN NOT MATCHED THEN
                INSERT ({insert_cols})
                VALUES ({insert_vals})
        """

    def _merge_via_temp_table(self, data: List[Dict[str, Any]]) -> None:
        """
        Execute MERGE using an in-session BQ Temp Table.

        Handles chunking for large datasets (> 10MB).

        Args:
            data: List of dictionaries to merge.
        """
        import json

        if not data:
            logger.info(f"[{self.job_name}] No data to merge.")
            return

        # 10MB Chunking Logic
        # Rough estimate: Each row as JSON string
        MAX_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB
        chunks = []
        current_chunk = []
        current_size = 0

        for row in data:
            row_size = len(json.dumps(row))
            if current_size + row_size > MAX_CHUNK_SIZE and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0
            current_chunk.append(row)
            current_size += row_size

        if current_chunk:
            chunks.append(current_chunk)

        logger.info(
            f"[{self.job_name}] Merging {len(data)} rows in {len(chunks)} chunks via temp tables..."
        )

        for i, chunk in enumerate(chunks):
            temp_table_name = f"_stg_{self.job_name}_{i}"
            # Construct UNNEST query with parameters
            # BigQuery UNNEST(ARRAY<STRUCT<...>>) requires explicit types or we use JSON_QUERY
            # A simpler way is to use a single JSON string parameter and JSON_RELAXED_MODE
            # OR better: use UNNEST of JSON array and then parse it.
            # But wait, UNNEST with ArrayQueryParameter of structs is supported.
            # However, we need to know the schema for StructQueryParameter.

            # Alternative: Use a single JSON parameter for the chunk
            json_data = json.dumps(chunk)

            # Using BigQuery's JSON support:
            # We can use UNNEST(JSON_QUERY_ARRAY(@json_data)) but we need to cast each field.
            # Actually, standard way for high-perf is to use the generated schema.

            # Let's use the schema we already have from SchemaGuardian or just inferred from model
            # Actually, using a list of dicts with ArrayQueryParameter(..., sub_type="RECORD")
            # requires us to specify the fields.

            # Let's use a simpler approach that doesn't require complex param building:
            # CREATE TEMP TABLE AS SELECT * FROM UNNEST(JSON_QUERY_ARRAY(@json_data))
            # Wait, BigQuery has 'EXTERNAL_QUERY' or 'LOAD DATA' but those are for files.

            # If we use `bigquery.Client.load_table_from_json`, it uses a temporary table if we don't provide a destination?
            # No, it needs a destination.

            # The issue suggested:
            # CREATE TEMP TABLE _stg_{self.job_name} AS (
            #     SELECT * FROM UNNEST(...)
            # );
            # I will use ArrayQueryParameter.

            merge_sql = self._get_merge_sql(temp_table_name)

            # We need to build the SELECT clause from UNNEST to match the schema
            # SELECT CAST(json_extract_scalar(x, '$.id') AS STRING) as id, ... FROM UNNEST(JSON_QUERY_ARRAY(@json_data)) x
            # This is too complex.

            # Let's use the documented pattern for UNNEST with structs:
            # query_params = [bigquery.ArrayQueryParameter("rows", "RECORD", [ ... ])]
            # But "RECORD" needs sub_params.

            # Let's try to use `load_table_from_json` to a TEMP table.
            # Can we load to a TEMP table? Yes, if we use a table ID starting with `_` in a special way?
            # Actually, `load_table_from_json` to a persistent table was the old way.

            # Use JSON_VALUE/JSON_QUERY to extract fields from JSON
            # But we need types.

            # Let's reconsider `bigquery.ArrayQueryParameter` with `RECORD`.
            # We can use `SchemaGuardian` to get the BQ types.
            # But the requirement says "Use structural SQL assertion".

            # Let's use a simpler SQL that uses JSON_VALUE for everything and casts.
            # But wait, some fields are not strings.

            # Actually, the most robust way to create a temp table from data in Python is
            # to use `bq_client.load_table_from_json` but how to make it a TEMP table?
            # BigQuery `load_table_from_json` always creates a persistent table unless it's in a session.
            # But we want it to be automatically dropped.

            # If I use `CREATE TEMP TABLE` with `SELECT * FROM UNNEST(...)`
            # I need the `...` to be a valid array of structs.

            # I'll use a single JSON string and `UNNEST(JSON_QUERY_ARRAY(@json_data))`
            # and then I'll use the model schema to cast.

            field_selects = []
            for name, field_info in self.schema_model.model_fields.items():
                if field_info.exclude:
                    continue
                # Determine BQ type
                # Simple mapping for now, can be improved
                from datetime import date, datetime

                py_type = field_info.annotation
                # Handle Optional
                import typing

                if typing.get_origin(py_type) is typing.Union:
                    py_type = typing.get_args(py_type)[0]

                if py_type == int:
                    bq_type = "INT64"
                elif py_type == float:
                    bq_type = "FLOAT64"
                elif py_type == bool:
                    bq_type = "BOOL"
                elif py_type == datetime:
                    bq_type = "TIMESTAMP"
                elif py_type == date:
                    bq_type = "DATE"
                else:
                    bq_type = "STRING"

                if bq_type == "STRING":
                    field_selects.append(f"LAX_STRING(item.{name}) AS {name}")
                elif bq_type == "INT64":
                    field_selects.append(f"LAX_INT64(item.{name}) AS {name}")
                elif bq_type == "FLOAT64":
                    field_selects.append(f"LAX_FLOAT64(item.{name}) AS {name}")
                elif bq_type == "BOOL":
                    field_selects.append(f"LAX_BOOL(item.{name}) AS {name}")
                elif bq_type == "TIMESTAMP":
                    field_selects.append(f"TIMESTAMP(LAX_STRING(item.{name})) AS {name}")
                elif bq_type == "DATE":
                    field_selects.append(f"DATE(LAX_STRING(item.{name})) AS {name}")

            unnest_sql = f"""
                CREATE TEMP TABLE `{temp_table_name}` AS
                SELECT
                    {", ".join(field_selects)}
                FROM UNNEST(JSON_QUERY_ARRAY(PARSE_JSON(@json_data))) AS item;
            """

            full_script = f"""
                {unnest_sql}
                {merge_sql}
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("json_data", "STRING", json_data),
                ]
            )

            logger.info(f"[{self.job_name}] Executing merge chunk {i+1}/{len(chunks)}...")
            self.bq_client.query(full_script, job_config=job_config).result()

        logger.info(f"[{self.job_name}] MERGE completed successfully.")

    def run(self) -> int:
        """
        Orchestrate the full pipeline execution.

        Flow: Validate Schema -> Extract -> Transform -> Merge (via Temp Table) -> Cleanup

        Returns:
            int: Number of records processed.

        Raises:
            Exception: If any step fails, logs and RE-RAISES the exception.
                       Cleanup is NOT executed on failure.
        """
        logger.info(f"[{self.job_name}] Starting pipeline execution...")

        try:
            # 0. Pre-flight Check: Validate Schema
            logger.info(f"[{self.job_name}] Validating BigQuery Schema...")

            def _validate_schema():
                """Helper to run schema validation with current pipeline settings."""
                self.guardian.validate_schema(
                    table_id=self.fact_table_id,
                    model=self.schema_model,
                    require_partitioning=True,
                    clustering_fields=self.clustering_fields,
                )

            try:
                # The guardian will raise an exception if strict_mode is True and there's a mismatch
                # It will also raise NotFound if table doesn't exist
                _validate_schema()
            except (SchemaMismatchError, NotFound) as e:
                logger.warning(
                    "[{}] Schema issue detected on fact table: {}. Attempting auto-migration/creation...",
                    self.job_name,
                    str(e),
                )
                if self.settings.SCHEMA_MIGRATION_AUTO:
                    # migrate_schema handles both creation (if missing) and updates (if mismatched)
                    self.guardian.migrate_schema(
                        self.fact_table_id,
                        self.schema_model,
                        partition_column=self.partition_column,
                        clustering_fields=self.clustering_fields,
                    )

                    # Retry validation to ensure compliance
                    logger.info(f"[{self.job_name}] Re-validating Fact Table Schema...")
                    _validate_schema()
                else:
                    raise

            # 1. Extract
            raw_data = self.extract()
            if not raw_data:
                logger.info(f"[{self.job_name}] No data found. Exiting.")
                return 0

            # 2. Transform
            transformed_data = self.transform(raw_data)

            # 3. Execute Merge via Temp Table
            self._merge_via_temp_table(transformed_data)

            # 4. Cleanup - Re-validate for type safety (cheap vs BQ/Network ops)
            # Use transformed_data to ensure all fields required by schema are present
            cleanup_models = [
                self.schema_model.model_validate(d) for d in transformed_data
            ]
            self.cleanup(cleanup_models)

            logger.info(f"[{self.job_name}] Pipeline finished successfully.")
            return len(transformed_data)

        except Exception as e:
            # Use structured logging to avoid f-string formatting issues with Loguru (Issue #149)
            logger.opt(exception=True).error(
                "[{}] Pipeline FAILED: {}", self.job_name, str(e)
            )
            # CRITICAL: Re-raise to ensure job failure is reported to Cloud Run
            raise
