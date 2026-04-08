import pytest
from fastapi.testclient import TestClient
from argus.api.main import app
from unittest.mock import patch, MagicMock

client = TestClient(app)

@patch("argus.api.main.get_trading_client")
@patch("argus.api.auth._decode_supabase_jwt")
def test_get_assets_success(mock_decode, mock_get_trading_client):
    # Mock auth to return admin
    mock_decode.return_value = {"sub": "user123", "email": "test@test.com"}

    # Mock trading client
    mock_client = MagicMock()
    mock_get_trading_client.return_value = mock_client

    # Mock assets
    mock_asset1 = MagicMock()
    mock_asset1.symbol = "AAPL"
    mock_asset1.name = "Apple Inc."

    mock_asset2 = MagicMock()
    mock_asset2.symbol = "BTC/USD"
    mock_asset2.name = "Bitcoin"

    mock_client.get_all_assets.return_value = [mock_asset1, mock_asset2]

    # Test valid request
    response = client.get(
        "/api/v1/assets?search=apple&timeframe=15m",
        headers={"Authorization": "Bearer fake_token"}
    )

    assert response.status_code == 200
    assert response.json() == ["AAPL"]
    assert "X-RateLimit-Limit" in response.headers

@patch("argus.api.auth._decode_supabase_jwt")
def test_get_assets_invalid_timeframe(mock_decode):
    mock_decode.return_value = {"sub": "user123", "email": "test@test.com"}

    # Test invalid timeframe
    response = client.get(
        "/api/v1/assets?search=apple&timeframe=5m",
        headers={"Authorization": "Bearer fake_token"}
    )

    assert response.status_code == 422
    assert "timeframe must be one of" in response.json()["detail"]
