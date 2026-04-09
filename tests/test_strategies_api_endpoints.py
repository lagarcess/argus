from unittest.mock import MagicMock

import pytest
from argus.api.main import app
from argus.api.strategies import persistence_service
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
        "symbol": faker.random_element(elements=("BTC/USDT", "ETH/USD", "AAPL", "MSFT")),
        "timeframe": faker.random_element(elements=("1Hour", "4Hour", "1Day")),
        "start_date": None,
        "end_date": None,
        "entry_criteria": [],
        "exit_criteria": {},
        "indicators_config": {},
        "patterns": [],
    }


@pytest.fixture
def mock_strategy_db():
    return {
        "id": faker.uuid4(),
        "user_id": faker.uuid4(),
        "name": faker.catch_phrase(),
        "symbol": faker.random_element(elements=("BTC/USDT", "ETH/USD", "AAPL", "MSFT")),
        "timeframe": faker.random_element(elements=("1Hour", "4Hour", "1Day")),
        "start_date": None,
        "end_date": None,
        "entry_criteria": [],
        "exit_criteria": {},
        "indicators_config": {},
        "patterns": [],
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
    mock_save = MagicMock(return_value=mock_strategy_db)
    monkeypatch.setattr(persistence_service, "save_strategy", mock_save)

    response = client.post("/api/v1/strategies", json=valid_strategy_payload)
    assert response.status_code == 201
    assert response.json()["id"] == mock_strategy_db["id"]
    assert "x-ratelimit-limit" in response.headers
    assert response.headers["x-ratelimit-limit"] == "30"
    mock_save.assert_called_once_with(str(mock_user.id), valid_strategy_payload)


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
