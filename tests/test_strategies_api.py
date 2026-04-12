import base64
from unittest.mock import MagicMock

import pytest
from argus.api.main import app
from argus.api.schemas import StrategyCreate
from argus.api.strategies import persistence_service
from argus.domain.persistence import PersistenceService
from argus.domain.schemas import UserResponse
from faker import Faker
from fastapi.testclient import TestClient

faker = Faker()

client = TestClient(app)


@pytest.fixture
def mock_user():
    return UserResponse(
        id=faker.uuid4(),
        email=faker.email(),
        subscription_tier="free",
        is_admin=False,
        backtest_quota=50,
        remaining_quota=50,
    )


@pytest.fixture(autouse=True)
def auth_override(mock_user):
    from argus.api.auth import auth_required, check_rate_limit

    app.dependency_overrides[auth_required] = lambda: mock_user
    app.dependency_overrides[check_rate_limit] = lambda: mock_user
    yield
    app.dependency_overrides.pop(auth_required, None)
    app.dependency_overrides.pop(check_rate_limit, None)


@pytest.fixture
def valid_strategy_payload():
    return {
        "name": faker.catch_phrase(),
        "symbols": [
            faker.random_element(elements=("BTC/USDT", "ETH/USD", "AAPL", "MSFT"))
        ],
        "timeframe": faker.random_element(elements=("1Hour", "4Hour", "1Day")),
        "start_date": None,
        "end_date": None,
        "entry_criteria": [],
        "exit_criteria": {},
        "indicators_config": {},
        "patterns": [],
        "fees": 0.001,
        "slippage": 0.001,
    }


@pytest.fixture
def mock_strategy_db():
    return {
        "id": faker.uuid4(),
        "user_id": faker.uuid4(),
        "name": faker.catch_phrase(),
        "symbols": [
            faker.random_element(elements=("BTC/USDT", "ETH/USD", "AAPL", "MSFT"))
        ],
        "timeframe": faker.random_element(elements=("1Hour", "4Hour", "1Day")),
        "start_date": None,
        "end_date": None,
        "entry_criteria": [],
        "exit_criteria": {},
        "indicators_config": {},
        "patterns": [],
        "fees": 0.001,
        "slippage": 0.001,
        "executed_at": None,
    }


# --- GET /api/v1/strategies (List) ---


def test_list_strategies_success(mock_user, mock_strategy_db, monkeypatch):
    mock_list = MagicMock(return_value=([mock_strategy_db], "next_cursor_123"))
    monkeypatch.setattr(
        persistence_service,
        "list_strategies",
        mock_list,
    )

    response = client.get("/api/v1/strategies")
    assert response.status_code == 200
    data = response.json()
    assert len(data["strategies"]) == 1
    assert data["strategies"][0]["id"] == mock_strategy_db["id"]
    assert data["next_cursor"] == "next_cursor_123"
    mock_list.assert_called_once_with(str(mock_user.id), 10, None)


def test_list_strategies_error(monkeypatch):
    monkeypatch.setattr(
        persistence_service,
        "list_strategies",
        MagicMock(side_effect=Exception("Database connection failed")),
    )

    response = client.get("/api/v1/strategies")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


# --- GET /api/v1/strategies/{id} ---


def test_get_strategy_success(mock_user, mock_strategy_db, monkeypatch):
    mock_get = MagicMock(return_value=mock_strategy_db)
    monkeypatch.setattr(persistence_service, "get_strategy", mock_get)

    response = client.get(f"/api/v1/strategies/{mock_strategy_db['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == mock_strategy_db["id"]
    mock_get.assert_called_once_with(mock_strategy_db["id"], str(mock_user.id))


def test_get_strategy_not_found(mock_strategy_db, monkeypatch):
    monkeypatch.setattr(persistence_service, "get_strategy", MagicMock(return_value=None))

    response = client.get(f"/api/v1/strategies/{mock_strategy_db['id']}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Strategy not found"


# --- PUT /api/v1/strategies/{id} ---


def test_update_strategy_success(
    mock_user, mock_strategy_db, valid_strategy_payload, monkeypatch
):
    strategy_id = mock_strategy_db["id"]
    user_id = str(mock_user.id)

    # Mock getter
    mock_get = MagicMock(return_value=mock_strategy_db)
    monkeypatch.setattr(persistence_service, "get_strategy", mock_get)

    # Mock saver
    updated_db = {**mock_strategy_db, "name": "Updated Name"}
    mock_save = MagicMock(return_value=updated_db)
    monkeypatch.setattr(persistence_service, "save_strategy", mock_save)

    # Act
    payload = {**valid_strategy_payload, "name": "Updated Name"}
    response = client.put(f"/api/v1/strategies/{strategy_id}", json=payload)

    # Assert
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"
    mock_get.assert_called_once_with(strategy_id, user_id)
    mock_save.assert_called_once_with(user_id, payload, strategy_id)


def test_update_strategy_not_found(valid_strategy_payload, mock_strategy_db, monkeypatch):
    monkeypatch.setattr(persistence_service, "get_strategy", MagicMock(return_value=None))

    response = client.put(
        f"/api/v1/strategies/{mock_strategy_db['id']}", json=valid_strategy_payload
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Strategy not found"


def test_update_strategy_executed(mock_strategy_db, valid_strategy_payload, monkeypatch):
    executed_db = mock_strategy_db.copy()
    executed_db["executed_at"] = "2026-04-07T12:00:00Z"
    monkeypatch.setattr(
        persistence_service, "get_strategy", MagicMock(return_value=executed_db)
    )

    response = client.put(
        f"/api/v1/strategies/{mock_strategy_db['id']}", json=valid_strategy_payload
    )
    assert response.status_code == 403
    assert "Cannot modify an executed strategy" in response.json()["detail"]


def test_update_strategy_failed_save(
    mock_strategy_db, valid_strategy_payload, monkeypatch
):
    monkeypatch.setattr(
        persistence_service, "get_strategy", MagicMock(return_value=mock_strategy_db)
    )
    monkeypatch.setattr(
        persistence_service, "save_strategy", MagicMock(return_value=None)
    )

    response = client.put(
        f"/api/v1/strategies/{mock_strategy_db['id']}", json=valid_strategy_payload
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to update strategy."


# --- DELETE /api/v1/strategies/{id} ---


def test_delete_strategy_success(mock_user, mock_strategy_db, monkeypatch):
    mock_get = MagicMock(return_value=mock_strategy_db)
    monkeypatch.setattr(persistence_service, "get_strategy", mock_get)
    mock_delete = MagicMock(return_value=True)
    monkeypatch.setattr(persistence_service, "delete_strategy", mock_delete)

    response = client.delete(f"/api/v1/strategies/{mock_strategy_db['id']}")
    assert response.status_code == 204
    mock_get.assert_called_once_with(mock_strategy_db["id"], str(mock_user.id))
    mock_delete.assert_called_once_with(mock_strategy_db["id"], str(mock_user.id))


def test_delete_strategy_not_found(mock_strategy_db, monkeypatch):
    monkeypatch.setattr(persistence_service, "get_strategy", MagicMock(return_value=None))

    response = client.delete(f"/api/v1/strategies/{mock_strategy_db['id']}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Strategy not found"


def test_delete_strategy_executed(mock_strategy_db, monkeypatch):
    executed_db = mock_strategy_db.copy()
    executed_db["executed_at"] = "2026-04-07T12:00:00Z"
    monkeypatch.setattr(
        persistence_service, "get_strategy", MagicMock(return_value=executed_db)
    )

    response = client.delete(f"/api/v1/strategies/{mock_strategy_db['id']}")
    assert response.status_code == 403
    assert "Cannot delete an executed strategy" in response.json()["detail"]


def test_delete_strategy_failed_delete(mock_strategy_db, monkeypatch):
    monkeypatch.setattr(
        persistence_service, "get_strategy", MagicMock(return_value=mock_strategy_db)
    )
    monkeypatch.setattr(
        persistence_service, "delete_strategy", MagicMock(return_value=False)
    )

    response = client.delete(f"/api/v1/strategies/{mock_strategy_db['id']}")
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to delete strategy."


# --- POST /api/v1/strategies ---


def test_create_strategy_success(
    mock_user, mock_strategy_db, valid_strategy_payload, monkeypatch
):
    """
    Test creating a strategy.
    Verifies success status, payload mapping, and implementation efficiency
    (no redundant fetch after save).
    """
    # Mock the save operation
    mock_save = MagicMock(return_value=mock_strategy_db)
    monkeypatch.setattr(persistence_service, "save_strategy", mock_save)

    #  Mock get_strategy to verify it is NOT called (efficiency check)
    mock_get = MagicMock()
    monkeypatch.setattr(persistence_service, "get_strategy", mock_get)

    # Act
    response = client.post("/api/v1/strategies", json=valid_strategy_payload)

    # Assert Functionality
    assert response.status_code == 201
    assert response.json()["id"] == mock_strategy_db["id"]
    assert "x-ratelimit-limit" in response.headers
    assert response.headers["x-ratelimit-limit"] == "30"

    # Assert Correct Params
    mock_save.assert_called_once_with(str(mock_user.id), valid_strategy_payload)

    # Assert Efficiency
    mock_get.assert_not_called()


def test_create_strategy_failed_save(valid_strategy_payload, monkeypatch):
    monkeypatch.setattr(
        persistence_service, "save_strategy", MagicMock(return_value=None)
    )

    response = client.post("/api/v1/strategies", json=valid_strategy_payload)
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to create strategy in database."


def test_create_strategy_exception(valid_strategy_payload, monkeypatch):
    monkeypatch.setattr(
        persistence_service,
        "save_strategy",
        MagicMock(side_effect=Exception("Database down")),
    )

    response = client.post("/api/v1/strategies", json=valid_strategy_payload)
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


# --- Schema Validation ---


def test_strategy_create_timeframe_validator_valid():
    # Should not raise
    StrategyCreate(
        name="Valid",
        symbols=["BTC"],
        timeframe="1Hour",
        start_date=None,
        end_date=None,
        entry_criteria=[],
        exit_criteria={},
        indicators_config={},
        patterns=[],
    )


def test_strategy_create_timeframe_validator_invalid():
    with pytest.raises(ValueError) as excinfo:
        StrategyCreate(
            name="Invalid",
            symbols=["BTC"],
            timeframe="5Min",  # Not in allowed list
            start_date=None,
            end_date=None,
            entry_criteria=[],
            exit_criteria={},
            indicators_config={},
            patterns=[],
        )
    assert "timeframe must be one of" in str(excinfo.value)


# --- Pagination Cursor ---


def test_pagination_cursor_logic():
    # Setup mock client
    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.order.return_value.limit.return_value = mock_query

    # We just want to test if or_ was called correctly
    mock_query.or_.return_value.execute.return_value.data = []

    service = PersistenceService()
    service.client = mock_client

    cursor_str = "2024-01-01T00:00:00Z+some-uuid"
    cursor_b64 = base64.b64encode(cursor_str.encode("utf-8")).decode("utf-8")

    service.list_strategies("user_id", 10, cursor_b64)

    # Check if or_ was called with the right tie-breaking syntax
    mock_query.or_.assert_called_once_with(
        "created_at.lt.2024-01-01T00:00:00Z,and(created_at.eq.2024-01-01T00:00:00Z,id.lt.some-uuid)"
    )
