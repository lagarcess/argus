"""Unit tests for the BigQueryPipelineBase class."""

from datetime import date
from typing import Any, List
from unittest.mock import patch

import pytest
from crypto_signals.pipelines.base import BigQueryPipelineBase
from pydantic import BaseModel, Field

from tests.utils.sql_assertion import assert_merge_query_structure, assert_sql_equal

# --- Mocks & Fixtures ---


class MockSchema(BaseModel):
    """Mock Schema for testing."""

    id: str = Field(..., description="Primary Key")
    ds: date = Field(..., description="Partition Key")
    value: int = Field(..., description="Some value")


class ConcretePipeline(BigQueryPipelineBase):
    """Concrete implementation for testing purposes."""

    def extract(self) -> List[Any]:
        """Return dummy data."""
        return [{"id": "1", "ds": date(2024, 1, 1), "value": 100}]

    def cleanup(self, data: List[BaseModel]) -> None:
        """Do nothing."""


@pytest.fixture
def mock_bq_client():
    """Mock the BigQuery Client."""
    with patch("crypto_signals.pipelines.base.bigquery.Client") as mock:
        yield mock.return_value


@pytest.fixture
def pipeline(mock_bq_client):
    """Return a concrete pipeline instance with mocked clients."""
    # Mock settings to avoid loading .env
    with patch("crypto_signals.pipelines.base.get_settings") as mock_settings:
        mock_settings.return_value.GOOGLE_CLOUD_PROJECT = "test-project"

        # Mock SchemaGuardian to prevent real BQ calls during pipeline tests
        with patch("crypto_signals.pipelines.base.SchemaGuardian"):
            return ConcretePipeline(
                job_name="test_pipeline",
                staging_table_id=None,
                fact_table_id="test-project.dataset.fact_test",
                id_column="id",
                partition_column="ds",
                schema_model=MockSchema,
            )


# --- Tests ---


def test_transform_validates_and_dumps_json(pipeline):
    """Test that transform validates data and returns JSON-compatible dicts."""
    raw_data = [{"id": "1", "ds": date(2024, 1, 1), "value": 100}]

    transformed = pipeline.transform(raw_data)

    assert len(transformed) == 1
    assert isinstance(transformed[0], dict)
    # Date should be serialized to string for JSON
    assert transformed[0]["ds"] == "2024-01-01"
    assert transformed[0]["id"] == "1"


def test_get_merge_sql_constructs_correct_sql(pipeline):
    """Test dynamic SQL generation for MERGE statement."""
    source_table = "test_source"
    query = pipeline._get_merge_sql(source_table)

    # 1. Verify specific components (robust against order/whitespace)
    assert_merge_query_structure(
        query,
        target_table=f"`{pipeline.fact_table_id}`",
        source_table=f"`{source_table}`",
        join_keys=[pipeline.id_column, pipeline.partition_column],
        update_columns=[
            col
            for col in pipeline.schema_model.model_fields.keys()
            if col not in [pipeline.id_column, pipeline.partition_column]
        ],
        insert_columns=sorted(list(pipeline.schema_model.model_fields.keys())),
    )

    # 2. Verify semantic equality against a canonical expected version
    cols = sorted(list(pipeline.schema_model.model_fields.keys()))
    update_list = [
        f"T.{c} = S.{c}"
        for c in cols
        if c not in [pipeline.id_column, pipeline.partition_column]
    ]
    update_clause = ", ".join(update_list)
    insert_cols = ", ".join(cols)
    insert_vals = ", ".join([f"S.{c}" for c in cols])

    expected_sql = f"""
        MERGE `{pipeline.fact_table_id}` AS T
        USING `{source_table}` AS S
        ON T.{pipeline.id_column} = S.{pipeline.id_column}
        AND T.{pipeline.partition_column} = S.{pipeline.partition_column}
        WHEN MATCHED THEN
            UPDATE SET {update_clause}
        WHEN NOT MATCHED THEN
            INSERT ({insert_cols})
            VALUES ({insert_vals})
    """
    assert_sql_equal(query, expected_sql)


def test_merge_via_temp_table_executes_queries(pipeline, mock_bq_client):
    """Test that _merge_via_temp_table runs the correct SQL script."""
    data = [{"id": "1", "ds": "2024-01-01", "value": 100}]
    pipeline._merge_via_temp_table(data)

    call_args = mock_bq_client.query.call_args
    assert call_args is not None
    called_sql = call_args[0][0]

    assert "CREATE TEMP TABLE" in called_sql
    assert "MERGE" in called_sql
    assert "_stg_test_pipeline_0" in called_sql

    # Check for structural SQL assertion as requested
    assert (
        "CREATE TEMP TABLE" in called_sql
    ), f"Expected CREATE TEMP TABLE in SQL, got: {called_sql[:200]}"
    assert (
        "MERGE" in called_sql
    ), f"Expected MERGE statement in SQL, got: {called_sql[:200]}"


def test_run_orchestrates_flow(pipeline):
    """Test that run calls all steps in order."""
    # Mock methods to verify order
    with (
        patch.object(pipeline, "extract") as mock_extract,
        patch.object(pipeline, "transform") as mock_transform,
        patch.object(pipeline, "_merge_via_temp_table") as mock_merge,
        patch.object(pipeline, "cleanup") as mock_cleanup,
    ):
        mock_extract.return_value = [{"id": "1", "ds": date(2024, 1, 1), "value": 100}]
        mock_transform.return_value = [{"id": "1", "ds": "2024-01-01", "value": 100}]

        pipeline.run()

        mock_extract.assert_called_once()
        mock_transform.assert_called_once()
        mock_merge.assert_called_once()
        mock_cleanup.assert_called_once()


def test_run_reraises_exception(pipeline):
    """Test that run re-raises exceptions to alert Cloud Run."""
    with patch.object(pipeline, "extract", side_effect=ValueError("Boom!")):
        with pytest.raises(ValueError, match="Boom!"):
            pipeline.run()


def test_run_skips_if_extract_empty(pipeline):
    """Test that run exits early if extract returns empty list."""
    with patch.object(pipeline, "extract", return_value=[]):
        with patch.object(pipeline, "_merge_via_temp_table") as mock_merge:
            pipeline.run()
            mock_merge.assert_not_called()


def test_run_ensures_fact_table_exists(pipeline, mock_bq_client):
    """Test that run ensures fact table exists."""
    from google.api_core.exceptions import NotFound

    with (
        patch.object(pipeline, "extract", return_value=[]),
        patch("crypto_signals.pipelines.base.get_settings") as mock_settings,
    ):
        mock_settings.return_value.SCHEMA_MIGRATION_AUTO = True
        mock_settings.return_value.SCHEMA_GUARDIAN_STRICT_MODE = True

        # Force NotFound for fact table to trigger migrate_schema
        # 1. Fact Table (first try) -> NotFound
        # 2. Fact Table (retry) -> Success
        pipeline.guardian.validate_schema.side_effect = [
            NotFound("Not Found"),
            None,
        ]

        pipeline.run()

        # Should be called for fact table
        # migrate_schema is called via guardian
        pipeline.guardian.migrate_schema.assert_called_once_with(
            pipeline.fact_table_id,
            pipeline.schema_model,
            partition_column=pipeline.partition_column,
            clustering_fields=pipeline.clustering_fields,
        )
