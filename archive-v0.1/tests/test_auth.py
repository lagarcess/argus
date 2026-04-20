from unittest.mock import patch

import pytest
from argus.api.auth import _user_cache, auth_required
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def clear_cache():
    # Clear the cache before each test
    _user_cache.cache = {}
    yield
    _user_cache.cache = {}


@patch("argus.api.auth.supabase_client")
def test_user_cache_utilized(mock_supabase_client):
    """
    Test that the UserCache prevents redundant Supabase DB queries.
    """
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    email = "test@example.com"
    payload = {"sub": user_id, "email": email}

    # Setup mock for profiles query
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "subscription_tier": "free",
        "is_admin": False,
        "theme": "dark",
        "lang": "en",
        "backtest_quota": 50,
        "remaining_quota": 45,
        "last_quota_reset": "2026-04-01T00:00:00Z",
        "feature_flags": {},
    }

    # First call: Should be a cache miss and hit the database
    user1 = auth_required(payload=payload)

    assert user1.id == user_id
    assert user1.remaining_quota == 45

    # Verify the database was called once for the profile query
    assert mock_supabase_client.table.call_count == 1

    # Second call: Should be a cache hit and NOT hit the database again
    user2 = auth_required(payload=payload)

    assert user2.id == user_id
    assert user2.remaining_quota == 45

    # Call count should still be 1, proving it didn't query the DB again
    assert mock_supabase_client.table.call_count == 1


def test_auth_required_missing_payload():
    with pytest.raises(HTTPException) as exc:
        auth_required(payload=None)
    assert exc.value.status_code == 401


def test_auth_required_missing_sub():
    with pytest.raises(HTTPException) as exc:
        auth_required(payload={"email": "test@example.com"})
    assert exc.value.status_code == 401
