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
