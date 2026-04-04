from unittest.mock import patch

import pytest
from crypto_signals.pipelines.base import BigQueryPipelineBase
from pydantic import BaseModel


class MockSchema(BaseModel):
    id: str


class ConcretePipeline(BigQueryPipelineBase):
    def extract(self):
        return []

    def cleanup(self, data):
        pass


@pytest.fixture
def mock_bq():
    with patch("crypto_signals.pipelines.base.bigquery.Client"):
        yield


def test_pipeline_strict_mode_configuration(mock_bq):
    """Test that pipeline initializes SchemaGuardian with correct strict_mode from settings."""

    # Case 1: Default (True)
    with patch("crypto_signals.pipelines.base.get_settings") as mock_settings:
        mock_settings.return_value.GOOGLE_CLOUD_PROJECT = "test"
        mock_settings.return_value.SCHEMA_GUARDIAN_STRICT_MODE = True

        # We need to NOT patch SchemaGuardian class itself, but we can verify the instance content
        # However, Base pipeline creates real SchemaGuardian instance if we don't patch it.
        # That's fine as long as BQ Client is mocked.

        pipeline = ConcretePipeline("job", "stg", "fact", "id", "ds", MockSchema)
        assert pipeline.guardian.strict_mode is True

    # Case 2: Configured False
    with patch("crypto_signals.pipelines.base.get_settings") as mock_settings:
        mock_settings.return_value.GOOGLE_CLOUD_PROJECT = "test"
        mock_settings.return_value.SCHEMA_GUARDIAN_STRICT_MODE = False

        pipeline = ConcretePipeline("job", "stg", "fact", "id", "ds", MockSchema)
        assert pipeline.guardian.strict_mode is False
