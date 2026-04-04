from datetime import date
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.repository.firestore import JobMetadataRepository
from google.cloud.firestore_v1.client import Client


@pytest.fixture
def mock_firestore_client():
    """Fixture for a mocked Firestore client."""
    return MagicMock(spec=Client)


@pytest.fixture
def job_metadata_repository(mock_firestore_client):
    """Fixture for a JobMetadataRepository with a mocked Firestore client."""
    with patch(
        "crypto_signals.repository.firestore.firestore.Client",
        return_value=mock_firestore_client,
    ):
        return JobMetadataRepository()


def test_get_last_run_date_exists(
    job_metadata_repository: JobMetadataRepository, mock_firestore_client: MagicMock
):
    """
    Test that get_last_run_date returns the date when the document exists.
    """
    # Arrange
    job_id = "test_job"
    run_date = date(2023, 1, 1)
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"last_run_date": run_date.isoformat()}
    mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc

    # Act
    last_run_date = job_metadata_repository.get_last_run_date(job_id)

    # Assert
    assert last_run_date == run_date
    mock_firestore_client.collection.return_value.document.assert_called_with(job_id)


def test_get_last_run_date_not_exists(
    job_metadata_repository: JobMetadataRepository, mock_firestore_client: MagicMock
):
    """
    Test that get_last_run_date returns None when the document does not exist.
    """
    # Arrange
    job_id = "test_job"
    mock_doc = MagicMock()
    mock_doc.exists = False
    mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc

    # Act
    last_run_date = job_metadata_repository.get_last_run_date(job_id)

    # Assert
    assert last_run_date is None


def test_update_last_run_date(
    job_metadata_repository: JobMetadataRepository, mock_firestore_client: MagicMock
):
    """
    Test that update_last_run_date sets the correct date in Firestore.
    """
    # Arrange
    job_id = "test_job"
    run_date = date(2023, 1, 1)
    mock_doc_ref = MagicMock()
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref

    # Act
    job_metadata_repository.update_last_run_date(job_id, run_date)

    # Assert
    mock_doc_ref.set.assert_called_with(
        {"last_run_date": run_date.isoformat()}, merge=True
    )


def test_save_job_metadata(
    job_metadata_repository: JobMetadataRepository, mock_firestore_client: MagicMock
):
    """
    Test that save_job_metadata merges metadata correctly.
    """
    # Arrange
    job_id = "test_job_full"
    metadata: Dict[str, Any] = {
        "git_hash": "abc1234",
        "last_run_date": date(2023, 10, 27),
        "config": {"MAX_POSITIONS": 10},
        "duration": 5.5,
    }
    mock_doc_ref = MagicMock()
    mock_firestore_client.collection.return_value.document.return_value = mock_doc_ref

    # Act
    job_metadata_repository.save_job_metadata(job_id, metadata)

    # Assert
    # Verify date serialization and merge=True
    expected_data = {
        "git_hash": "abc1234",
        "last_run_date": "2023-10-27",
        "config": {"MAX_POSITIONS": 10},
        "duration": 5.5,
    }
    mock_doc_ref.set.assert_called_with(expected_data, merge=True)
