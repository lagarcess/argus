from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.engine.schema_guardian import SchemaMismatchError
from crypto_signals.pipelines.base import BigQueryPipelineBase
from google.cloud import bigquery
from pydantic import BaseModel

# --- Mocks ---


class MockModel(BaseModel):
    id: str
    value: int


class MockPipeline(BigQueryPipelineBase):
    def extract(self) -> List[Any]:
        return [{"id": "1", "value": 100}]

    def cleanup(self, data: List[BaseModel]) -> None:
        pass


@pytest.fixture
def mock_bq_client():
    return MagicMock(spec=bigquery.Client)


@pytest.fixture
def pipeline(mock_bq_client):
    with patch(
        "crypto_signals.pipelines.base.bigquery.Client", return_value=mock_bq_client
    ):
        # We also need to patch SchemaGuardian to assert calls or control behavior
        with patch("crypto_signals.pipelines.base.SchemaGuardian") as MockGuardian:
            # Create instance
            p = MockPipeline(
                job_name="test_pipeline",
                staging_table_id="proj.ds.stg",
                fact_table_id="proj.ds.fact",
                id_column="id",
                partition_column="ds",  # Not used in mock model but required by init
                schema_model=MockModel,
            )
            # Attach the mock instance to the pipeline object for easy access in tests
            p.mock_guardian_instance = MockGuardian.return_value
            return p


def test_pipeline_validates_schema_before_running(pipeline):
    """Test that schema validation is called at the start of run()."""
    # Setup mocks
    pipeline.mock_guardian_instance.validate_schema.return_value = None  # Success

    # Mock extract to return empty so we stop early after validation
    # pipeline.extract = MagicMock(return_value=[])
    # Actually, let's let it run deeper. We just want to check the CALL order.
    # But since we didn't fully mock everything (transform, truncate, etc will call real methods or need mocks)
    # The simplest is to make extract return empty, so run() returns 0 immediately after steps 0 and 1.
    pipeline.extract = MagicMock(return_value=[])

    pipeline.run()

    # Assert validation was called with correct args
    # Now called once for the fact table (temp table does not need validation)
    pipeline.mock_guardian_instance.validate_schema.assert_called_once_with(
        table_id="proj.ds.fact",
        model=MockModel,
        require_partitioning=True,
        clustering_fields=None,
    )


def test_pipeline_fails_on_schema_mismatch(pipeline):
    """Test that pipeline raises exception if schema validation fails."""
    # Setup mock to raise error
    pipeline.mock_guardian_instance.validate_schema.side_effect = SchemaMismatchError(
        "Boom"
    )

    # Run and expect raise
    with pytest.raises(SchemaMismatchError):
        pipeline.run()

    # Verify we didn't proceed to extract (optimization check)
    # Or at least that we crashed.
    # Note: Extract is called after validation in the code I wrote.
    # So if validation raises, extract should NOT be called?
    # Let's verify existing code structure.
    # Yes:
    # # 0. Pre-flight Check
    # self.guardian.validate_schema(...)
    # # 1. Extract
    # raw_data = self.extract()

    # Assuming the MockPipeline's extract/cleanup aren't mocked yet, we can mock extract to assert it wasn't called.
    pipeline.extract = MagicMock()

    with pytest.raises(SchemaMismatchError):
        pipeline.run()

    pipeline.extract.assert_not_called()


def test_pipeline_validates_clustering(pipeline):
    """Test that pipeline calls guardian with clustering_fields."""
    # We need to re-instantiate or modify pipeline to have clustering_fields
    pipeline.clustering_fields = ["id"]

    # Mock extract
    pipeline.extract = MagicMock(return_value=[])

    pipeline.run()

    instance = pipeline.mock_guardian_instance
    instance.validate_schema.assert_called_once_with(
        table_id="proj.ds.fact",
        model=MockModel,
        require_partitioning=True,
        clustering_fields=["id"],
    )
