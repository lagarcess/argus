from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.domain.schemas import StrategyConfig
from crypto_signals.repository.firestore import StrategyRepository


@pytest.fixture
def mock_firestore():
    with patch("google.cloud.firestore.Client") as mock:
        yield mock.return_value


@pytest.fixture
def repo(mock_firestore):
    return StrategyRepository()


def test_get_all_strategies(repo, mock_firestore):
    # Mock documents
    """Verify retrieval of all valid strategies from the repository."""
    doc1 = MagicMock()
    doc1.id = "strat_1"
    doc1.to_dict.return_value = {
        "strategy_id": "strat_1",
        "active": True,
        "timeframe": "4H",
        "asset_class": "CRYPTO",
        "assets": ["BTC/USD"],
        "risk_params": {"stop": 0.02},
    }

    mock_firestore.collection.return_value.stream.return_value = [doc1]

    results = repo.get_all_strategies()

    assert len(results) == 1
    assert isinstance(results[0], StrategyConfig)
    assert results[0].strategy_id == "strat_1"


def test_get_all_strategies_validation_error(repo, mock_firestore):
    # Mock valid and invalid documents
    """Ensure strategy validation errors are handled correctly."""
    doc1 = MagicMock()
    doc1.id = "valid"
    doc1.to_dict.return_value = {
        "strategy_id": "valid",
        "active": True,
        "timeframe": "4H",
        "asset_class": "CRYPTO",
        "assets": ["BTC/USD"],
    }

    doc2 = MagicMock()
    doc2.id = "invalid"
    doc2.to_dict.return_value = {
        "active": True  # Missing required fields
    }

    mock_firestore.collection.return_value.stream.return_value = [doc1, doc2]

    results = repo.get_all_strategies()

    assert len(results) == 1
    assert results[0].strategy_id == "valid"


def test_get_active_strategy_configs(repo, mock_firestore):
    """Verify that only active strategies are returned."""
    doc1 = MagicMock()
    doc1.id = "strat_active"
    doc1.to_dict.return_value = {
        "strategy_id": "strat_active",
        "active": True,
        "timeframe": "4H",
        "asset_class": "CRYPTO",
        "assets": ["BTC/USD"],
    }

    doc2 = MagicMock()
    doc2.id = "strat_inactive"
    doc2.to_dict.return_value = {
        "strategy_id": "strat_inactive",
        "active": False,
        "timeframe": "1D",
        "asset_class": "EQUITY",
        "assets": ["AAPL"],
    }

    mock_query = MagicMock()
    # Mocking the result of the `where` filter which would only return doc1
    mock_query.stream.return_value = [doc1]
    mock_firestore.collection.return_value.where.return_value = mock_query

    results = repo.get_active_strategy_configs()

    assert len(results) == 1, f"Expected 1 active strategy, got {len(results)}"
    assert (
        results[0].strategy_id == "strat_active"
    ), f"Expected strategy_id='strat_active', got {results[0].strategy_id!r}"
    assert results[0].active is True, f"Expected active=True, got {results[0].active!r}"
