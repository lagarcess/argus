from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.engine.schema_guardian import SchemaMismatchError
from crypto_signals.pipelines.base import BigQueryPipelineBase
from google.cloud import bigquery
from pydantic import BaseModel


class MockModel(BaseModel):
    id: str
    value: int
    new_field: str  # This field is missing in BQ


class MockPipeline(BigQueryPipelineBase):
    def extract(self):
        return [{"id": "1", "value": 10, "new_field": "data"}]

    def cleanup(self, data):
        pass


@pytest.fixture
def mock_bq_client():
    client = MagicMock(spec=bigquery.Client)
    return client


@pytest.fixture
def mock_settings():
    with patch("crypto_signals.pipelines.base.get_settings") as mock:
        mock.return_value.GOOGLE_CLOUD_PROJECT = "test-project"
        mock.return_value.SCHEMA_GUARDIAN_STRICT_MODE = True
        mock.return_value.SCHEMA_MIGRATION_AUTO = True  # Enable auto migration
        yield mock


def test_pipeline_fails_strict_validation(mock_bq_client, mock_settings):
    """Verify strict mode without auto-migration raises SchemaMismatchError."""
    # Disable migration to test strict failure
    mock_settings.return_value.SCHEMA_MIGRATION_AUTO = False

    # Setup Schema Guardian to fail
    mock_table = MagicMock()
    mock_table.schema = [
        bigquery.SchemaField("id", "STRING"),
        bigquery.SchemaField("value", "INTEGER"),
    ]
    mock_table.time_partitioning = MagicMock()
    mock_bq_client.get_table.return_value = mock_table

    with patch("google.cloud.bigquery.Client", return_value=mock_bq_client):
        pipeline = MockPipeline(
            job_name="test_job",
            staging_table_id="project.dataset.staging",
            fact_table_id="project.dataset.fact",
            id_column="id",
            partition_column="date",
            schema_model=MockModel,
        )

        with pytest.raises(SchemaMismatchError) as excinfo:
            pipeline.run()

        assert "Missing columns: new_field (STRING)" in str(excinfo.value)


def test_pipeline_migrates_schema_and_succeeds(mock_bq_client, mock_settings):
    """Verify the pipeline auto-migrates BigQuery schema for missing fields."""
    # Ensure migration is enabled
    mock_settings.return_value.SCHEMA_MIGRATION_AUTO = True

    mock_table = MagicMock()
    # Initial schema missing 'new_field'
    mock_table.schema = [
        bigquery.SchemaField("id", "STRING"),
        bigquery.SchemaField("value", "INTEGER"),
    ]
    mock_table.time_partitioning = MagicMock()

    # We need get_table to return the table.
    # When migrate_schema calls get_table, it gets this table.
    # Then it updates table.schema in place (on the mock).
    # Then it calls update_table.
    # Then validate_schema is called AGAIN. It calls get_table again.
    # We need to ensure that the SECOND call to get_table returns the updated schema,
    # OR that our mock table object's schema was mutated in place (which it is in the code).

    mock_bq_client.get_table.return_value = mock_table
    mock_bq_client.insert_rows_json.return_value = []  # Success

    with patch("google.cloud.bigquery.Client", return_value=mock_bq_client):
        pipeline = MockPipeline(
            job_name="test_job",
            staging_table_id="project.dataset.staging",
            fact_table_id="project.dataset.fact",
            id_column="id",
            partition_column="date",
            schema_model=MockModel,
        )

        # Run pipeline
        count = pipeline.run()

        assert count == 1

        # Verify migration happened
        # 1. update_table called
        mock_bq_client.update_table.assert_called_once()

        # 2. bq_client.query called (via _merge_via_temp_table)
        assert mock_bq_client.query.called
        called_sql = mock_bq_client.query.call_args[0][0]
        assert "CREATE TEMP TABLE" in called_sql
        assert "MERGE" in called_sql

        # 3. Check that schema was updated on the mock table
        # The code does: table.schema = updated_schema
        # Let's check if 'new_field' is in mock_table.schema
        field_names = [f.name for f in mock_table.schema]
        assert "new_field" in field_names
