from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.domain.schemas import Signal
from crypto_signals.repository.firestore import SignalRepository
from google.cloud.firestore_v1.base_query import BaseQuery
from google.cloud.firestore_v1.client import Client
from polyfactory.factories.pydantic_factory import ModelFactory


@pytest.fixture
def mock_firestore_client():
    """Fixture for a mocked Firestore client."""
    return MagicMock(spec=Client)


@pytest.fixture
def signal_repository(mock_firestore_client):
    """Fixture for a SignalRepository with a mocked Firestore client."""
    with patch(
        "crypto_signals.repository.firestore.firestore.Client",
        return_value=mock_firestore_client,
    ):
        return SignalRepository()


def test_cleanup_expired_signals(
    signal_repository: SignalRepository, mock_firestore_client: MagicMock
):
    """
    Test that cleanup_expired correctly deletes signals that have passed their delete_at time.
    """
    # Arrange
    now = datetime.now(timezone.utc)
    expired_date = now - timedelta(hours=1)

    class SignalFactory(ModelFactory[Signal]):
        __model__ = Signal

    # Create a signal that is already expired
    old_signal = SignalFactory.build(delete_at=expired_date)

    # Mock the query and stream results
    mock_query = MagicMock(spec=BaseQuery)
    mock_firestore_client.collection.return_value.where.return_value = mock_query

    # Create mock documents with references
    mock_old_doc = MagicMock()
    mock_old_doc.to_dict.return_value = old_signal.model_dump()
    mock_old_doc.reference = MagicMock()

    mock_query.stream.return_value = [mock_old_doc]

    # Act
    deleted_count = signal_repository.cleanup_expired()

    # Assert
    assert deleted_count == 1
    mock_firestore_client.collection.assert_called_with(signal_repository.collection_name)
    signal_repository.db.batch.assert_called()
    signal_repository.db.batch().delete.assert_called_with(mock_old_doc.reference)
    signal_repository.db.batch().commit.assert_called()

    # Verify the query was made with the correct cutoff date (now)
    mock_firestore_client.collection.return_value.where.assert_called_once()
    call_args = mock_firestore_client.collection.return_value.where.call_args
    assert "filter" in call_args.kwargs
    firestore_filter = call_args.kwargs["filter"]
    assert firestore_filter.field_path == "delete_at"
    assert firestore_filter.op_string == "<"
    # The value should be close to 'now'
    assert abs((firestore_filter.value - now).total_seconds()) < 10
