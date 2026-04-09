import base64
from unittest.mock import MagicMock

import pytest
from argus.api.schemas import StrategyCreate
from argus.domain.persistence import PersistenceService


def test_strategy_create_timeframe_validator_valid():
    # Should not raise
    StrategyCreate(
        name="Valid",
        symbol="BTC",
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
            symbol="BTC",
            timeframe="5Min",  # Not in allowed list
            start_date=None,
            end_date=None,
            entry_criteria=[],
            exit_criteria={},
            indicators_config={},
            patterns=[],
        )
    assert "timeframe must be one of" in str(excinfo.value)


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


def test_save_strategy_returns_full_object():
    from unittest.mock import MagicMock

    import argus.api.strategies as strategies_module
    from argus.api.schemas import StrategyCreate
    from argus.api.strategies import create_strategy
    from argus.domain.schemas import UserResponse

    # Mock the persistence service inside the strategies router
    mock_service = MagicMock()
    # Ensure it returns a dictionary and not a string
    expected_response = {
        "id": "some-uuid",
        "user_id": "user123",
        "name": "My Strategy",
        "symbol": "BTC",
        "timeframe": "1Hour",
        "start_date": None,
        "end_date": None,
        "entry_criteria": [],
        "exit_criteria": {},
        "indicators_config": {},
        "patterns": [],
        "executed_at": None,
    }
    mock_service.save_strategy.return_value = expected_response

    # Temporarily replace the real service with the mock
    original_service = strategies_module.persistence_service
    strategies_module.persistence_service = mock_service

    try:
        user = UserResponse(user_id="user123", email="test@test.com")
        strategy = StrategyCreate(
            name="My Strategy",
            symbol="BTC",
            timeframe="1Hour",
            start_date=None,
            end_date=None,
            entry_criteria=[],
            exit_criteria={},
            indicators_config={},
            patterns=[],
        )
        response = MagicMock()

        result = create_strategy(strategy, response, user)

        assert result == expected_response
        mock_service.save_strategy.assert_called_once()
        # Verify get_strategy was NOT called (no redundant fetch)
        mock_service.get_strategy.assert_not_called()
    finally:
        # Restore the real service
        strategies_module.persistence_service = original_service
