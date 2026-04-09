from unittest.mock import patch

from argus.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@patch("argus.api.main.alpaca_fetcher.get_active_assets")
@patch("argus.api.main.check_asset_search_rate_limit")
@patch("argus.api.auth._decode_supabase_jwt")
def test_get_assets_success_and_caching(mock_decode, mock_rate_limit, mock_get_assets):
    # Setup mocks
    mock_decode.return_value = {"sub": "user123", "email": "test@test.com"}
    mock_rate_limit.return_value = {
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "99",
        "X-RateLimit-Reset": "1000",
        "Retry-After": "0",
    }

    # Setup mock data using Faker
    mock_get_assets.return_value = ["AAPL", "BTC/USD", "ZZZ", "MSFT"]

    # Clear cache before test explicitly safely
    from argus.api.main import asset_cache

    if hasattr(asset_cache, "_assets"):
        asset_cache._assets = []
    if hasattr(asset_cache, "_timestamp"):
        asset_cache._timestamp = 0

    # 1. First call - should hit Alpaca Proxy
    response1 = client.get(
        "/api/v1/assets?search=a&timeframe=15m",
        headers={"Authorization": "Bearer fake_token"},
    )

    assert response1.status_code == 200
    assert response1.json() == ["AAPL"]
    assert "X-RateLimit-Limit" in response1.headers
    assert mock_get_assets.call_count == 1

    # 2. Second call - should hit cache
    response2 = client.get(
        "/api/v1/assets?search=b",  # Testing optional timeframe parameter
        headers={"Authorization": "Bearer fake_token"},
    )

    assert response2.status_code == 200
    assert response2.json() == ["BTC/USD"]
    # Verify Alpaca wasn't called again
    assert mock_get_assets.call_count == 1


@patch("argus.api.auth._decode_supabase_jwt")
def test_get_assets_invalid_timeframe(mock_decode):
    mock_decode.return_value = {"sub": "user123", "email": "test@test.com"}

    # Test invalid timeframe
    response = client.get(
        "/api/v1/assets?search=apple&timeframe=5m",
        headers={"Authorization": "Bearer fake_token"},
    )

    assert response.status_code == 422
    assert "timeframe must be one of" in response.json()["detail"]
