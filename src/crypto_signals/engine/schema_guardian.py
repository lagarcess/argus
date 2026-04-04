import datetime
import typing
from typing import Any, List, Optional, Type

from google.api_core.exceptions import Conflict, GoogleAPICallError, NotFound
from google.cloud import bigquery
from loguru import logger
from pydantic import BaseModel


class SchemaMismatchError(Exception):
    """Raised when BigQuery schema does not match Pydantic model."""

    pass


class SchemaGuardian:
    """
    Enforces schema parity between Pydantic Models (Source of Truth) and BigQuery Tables.
    """

    # Mapping Pydantic/Python types to BigQuery types
    TYPE_MAPPING = {
        str: "STRING",
        int: "INTEGER",
        float: "FLOAT",
        bool: "BOOLEAN",
        datetime.datetime: "TIMESTAMP",
        datetime.date: "DATE",
    }

    def __init__(self, bq_client: bigquery.Client, strict_mode: bool = True):
        self.client = bq_client
        self.strict_mode = strict_mode

    def validate_schema(
        self,
        table_id: str,
        model: Type[BaseModel],
        require_partitioning: bool = False,
        clustering_fields: Optional[List[str]] = None,
    ) -> tuple[List[tuple[str, str]], List[str]]:
        """
        Validates that the BigQuery table schema matches the Pydantic model.

        Args:
            table_id: Full table ID (project.dataset.table)
            model: Pydantic model class
            require_partitioning: Enforce that the table is partitioned (Time or Range).
            clustering_fields: Enforce exact match of clustering fields.

        Returns:
            A tuple containing:
              - missing_columns: List of (column_name, bq_type) tuples
              - type_mismatches: List of error message strings
        """
        try:
            table = self.client.get_table(table_id)
        except NotFound:
            # Table doesn't exist. expected during first run.
            raise
        except GoogleAPICallError as e:
            logger.error(
                f"Failed to fetch table schema for {table_id}.",
                extra={"table_id": table_id, "error": str(e)},
            )
            raise

        missing_columns, type_mismatches = self._validate_fields(
            model.model_fields.items(), table.schema
        )

        # --- New Checks (Partitioning & Clustering) ---
        partitioning_error = None
        if require_partitioning:
            # Check for either TimePartitioning or RangePartitioning
            if not (table.time_partitioning or table.range_partitioning):
                partitioning_error = "Table is not partitioned"

        clustering_error = None
        if clustering_fields is not None:
            # table.clustering_fields returns a list of strings or None
            actual_clustering = table.clustering_fields or []
            if actual_clustering != clustering_fields:
                clustering_error = f"Clustering mismatch: Expected {clustering_fields}, Found {actual_clustering}"

        if missing_columns or type_mismatches or partitioning_error or clustering_error:
            # Format the error messages for logging, but return the structured data
            error_messages = []
            if missing_columns:
                formatted_missing = [
                    f"{name} ({btype})" for name, btype in missing_columns
                ]
                error_messages.append(f"Missing columns: {', '.join(formatted_missing)}")
            if type_mismatches:
                error_messages.append(f"Type mismatch: {', '.join(type_mismatches)}")
            if partitioning_error:
                error_messages.append(partitioning_error)
            if clustering_error:
                error_messages.append(clustering_error)

            full_error = f"Schema Validation Failed for {table_id}: " + "; ".join(
                error_messages
            )
            logger.critical(full_error)

            if self.strict_mode:
                raise SchemaMismatchError(full_error)

        return missing_columns, type_mismatches

    def generate_schema(self, model: Type[BaseModel]) -> List[bigquery.SchemaField]:
        """
        Generates a BigQuery schema from a Pydantic model.
        """
        schema = []
        for name, field_info in model.model_fields.items():
            # Skip excluded fields (Issue #149: scaled_out_prices, etc.)
            if field_info.exclude:
                continue

            # 1. Resolve Type
            python_type = field_info.annotation

            # Detect Nullable (Optional[T] or Union[T, None])
            is_nullable = False
            origin = typing.get_origin(python_type)
            inner_type = python_type

            if origin is typing.Union:
                args = typing.get_args(python_type)
                if type(None) in args:
                    is_nullable = True
                for arg in args:
                    if arg is not type(None):
                        inner_type = arg
                        break

            # Detect Repeated (List[T])
            is_repeated = False
            inner_origin = typing.get_origin(inner_type)
            if inner_origin is list or inner_origin is List:
                is_repeated = True

            # Unwrap to get the core type for BQ mapping
            python_type = self._unwrap_type(python_type)

            mode = "REQUIRED"
            if is_nullable:
                mode = "NULLABLE"
            if is_repeated:
                mode = "REPEATED"

            bq_type, is_nested = self._get_bq_type(python_type)

            fields: tuple[bigquery.SchemaField, ...] = ()
            if is_nested:
                # Recursive generation for nested models
                fields = tuple(self.generate_schema(python_type))

            schema.append(bigquery.SchemaField(name, bq_type, mode=mode, fields=fields))

        return schema

    def migrate_schema(
        self,
        table_id: str,
        model: Type[BaseModel],
        partition_column: Optional[str] = None,
        clustering_fields: Optional[List[str]] = None,
    ) -> None:
        """
        Alters the BigQuery table to add missing columns.
        Creates the table if it doesn't exist.

        Args:
            table_id: Full table ID (project.dataset.table)
            model: Pydantic model class
            partition_column: Optional column to use for TimePartitioning (Day)
            clustering_fields: Optional list of columns for clustering
        """
        try:
            table = self.client.get_table(table_id)
        except (NotFound, GoogleAPICallError) as e:
            if isinstance(e, NotFound):
                logger.info(f"Table {table_id} not found. Creating it...")
                self._create_table(table_id, model, partition_column, clustering_fields)
                return
            else:
                logger.error(
                    f"Failed to fetch table schema for {table_id}.",
                    extra={"table_id": table_id, "error": str(e)},
                )
                raise

        desired_schema = self.generate_schema(model)
        current_schema_map = {field.name: field for field in table.schema}

        new_fields = []
        for field in desired_schema:
            if field.name not in current_schema_map:
                # CRITICAL: BigQuery does not allow adding REQUIRED columns to existing tables.
                # We force mode="NULLABLE" only if the desired mode is "REQUIRED".
                # "REPEATED" fields (Lists) can be added as-is.
                safe_mode = "NULLABLE" if field.mode == "REQUIRED" else field.mode

                safe_field = bigquery.SchemaField(
                    name=field.name,
                    field_type=field.field_type,
                    mode=safe_mode,
                    description=field.description,
                    fields=field.fields,
                    policy_tags=field.policy_tags,
                )
                new_fields.append(safe_field)
                logger.info(
                    f"Detected new field: {field.name} ({field.field_type}, mode={safe_mode})"
                )
            else:
                # Field exists - check for type mismatch (Issue #266)
                existing_field = current_schema_map[field.name]
                if not self._is_compatible(field.field_type, existing_field.field_type):
                    error_msg = (
                        f"Schema Migration Failed: Type mismatch for column '{field.name}'. "
                        f"Expected {field.field_type}, Found {existing_field.field_type}. "
                        "Manual intervention required (drop table or fix model)."
                    )
                    logger.critical(error_msg)
                    if self.strict_mode:
                        raise SchemaMismatchError(error_msg)

        update_fields = []

        if new_fields:
            updated_schema = table.schema[:]
            updated_schema.extend(new_fields)
            table.schema = updated_schema
            update_fields.append("schema")
            logger.info(
                f"Migrating schema for {table_id}: Adding {len(new_fields)} columns..."
            )

        if clustering_fields is not None:
            current_clustering = (
                list(table.clustering_fields) if table.clustering_fields else []
            )
            if current_clustering != clustering_fields:
                table.clustering_fields = clustering_fields
                update_fields.append("clustering_fields")
                logger.info(
                    f"Migrating clustering for {table_id}: Changing to {clustering_fields}"
                )

        if not update_fields:
            logger.info(f"No new fields or clustering updates needed for {table_id}.")
            return

        self.client.update_table(table, update_fields)
        logger.info(f"Schema migration successful for {table_id}.")

    def _create_table(
        self,
        table_id: str,
        model: Type[BaseModel],
        partition_column: Optional[str] = None,
        clustering_fields: Optional[List[str]] = None,
    ) -> None:
        """Helper to create a new table from Pydantic model.

        Args:
            table_id: Full table ID (project.dataset.table)
            model: Pydantic model class
            partition_column: Optional column to use for TimePartitioning (Day)
            clustering_fields: Optional list of columns for clustering
        """
        schema = self.generate_schema(model)
        table = bigquery.Table(table_id, schema=schema)

        if partition_column:
            logger.info(
                f"Configuring TimePartitioning for {table_id} on field '{partition_column}'"
            )
            table.time_partitioning = bigquery.TimePartitioning(
                field=partition_column,
                type_=bigquery.TimePartitioningType.DAY,
            )

        if clustering_fields:
            logger.info(f"Configuring Clustering for {table_id} on {clustering_fields}")
            table.clustering_fields = clustering_fields

        try:
            self.client.create_table(table)
            logger.info(f"Created table {table_id} successfully.")
        except Conflict:
            logger.info(
                f"Table {table_id} already exists (race condition) - treating as success."
            )
        except Exception as e:
            logger.error(
                f"Failed to create table {table_id}.",
                extra={"table_id": table_id, "error": str(e)},
            )
            raise

    def _validate_fields(
        self,
        model_fields: Any,
        bq_schema: List[bigquery.SchemaField],
        parent_path: str = "",
    ) -> tuple[List[tuple[str, str]], List[str]]:
        """
        Recursively validate Pydantic fields against BigQuery schema fields.

        Args:
            model_fields: Iterable of (name, FieldInfo) from Pydantic
            bq_schema: List of BigQuery SchemaField objects
            parent_path: Dot-notation path for nested fields (e.g. "user.address")

        Returns:
            Tuple containing (missing_columns, type_mismatches)
        """
        bq_columns = {field.name: field for field in bq_schema}
        missing = []
        mismatches = []

        for name, field_info in model_fields:
            # Skip excluded fields (Issue #149: scaled_out_prices, etc.)
            if field_info.exclude:
                continue

            full_name = f"{parent_path}.{name}" if parent_path else name

            # 1. Resolve Type
            python_type = field_info.annotation
            python_type = self._unwrap_type(python_type)

            expected_type, is_nested_model = self._get_bq_type(python_type)

            # 2. Check Existence
            if name not in bq_columns:
                missing.append((full_name, expected_type))
                continue

            bq_field = bq_columns[name]

            # 3. Check Type Compatibility
            if not self._is_compatible(expected_type, bq_field.field_type):
                mismatches.append(
                    f"{full_name}: Expected {expected_type}, Found {bq_field.field_type}"
                )
                continue

            # 4. Recursion for RECORD/STRUCT
            if is_nested_model and expected_type == "RECORD":
                # Recurse using the inner Pydantic model's fields and BQ field's sub-fields
                sub_missing, sub_mismatches = self._validate_fields(
                    python_type.model_fields.items(),
                    bq_field.fields,
                    parent_path=full_name,
                )
                missing.extend(sub_missing)
                mismatches.extend(sub_mismatches)

        return missing, mismatches

    def _is_compatible(self, expected: str, actual: str) -> bool:
        """Helper to allow fuzzy matching (e.g. FLOAT matches NUMERIC)."""
        if expected == actual:
            return True
        if expected == "FLOAT" and actual in ("NUMERIC", "BIGNUMERIC"):
            return True
        return False

    def _unwrap_type(self, py_type: Any) -> Any:
        """Unwraps Optional, List, Union to get the core type."""
        import typing

        # Unwind Optional / Union
        origin = typing.get_origin(py_type)
        if origin is typing.Union:
            args = typing.get_args(py_type)
            for arg in args:
                if arg is not type(None):
                    py_type = arg
                    break

        # Unwind List / Iterable (TODO: Add explicit REPEATED check if strictly enforcing modes)
        # For now, we just want the inner type to match the BQ type
        origin = typing.get_origin(py_type)
        if origin is list or origin is List:
            args = typing.get_args(py_type)
            if args:
                py_type = args[0]
                # Recursively unwrap inner type (e.g. List[Optional[int]])
                py_type = self._unwrap_type(py_type)

        # Note: This logic assumes simple Optional[T] or List[T].
        # Complex Unions (e.g. Union[int, float]) are not fully supported and default to STRING.
        if typing.get_origin(py_type) is typing.Union:
            logger.warning(
                f"Complex Union type detected: {py_type}. Defaulting to STRING validation."
            )

        return py_type

    def _get_bq_type(self, py_type: Any) -> tuple[str, bool]:
        """
        Resolves Python type to BQ string.
        Returns (bq_type_str, is_pydantic_model_bool)
        """
        # Check for Pydantic Model (Nested)
        try:
            # Note: Explicit check for Pydantic V2 BaseModel.
            # Ensure compat layers (V1) appear as subclasses if used.
            if issubclass(py_type, BaseModel):
                return "RECORD", True
        except TypeError:
            pass  # Not a class

        return self.TYPE_MAPPING.get(py_type, "STRING"), False
