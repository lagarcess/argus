from datetime import datetime, timezone

import pytest
import respx
from argus.config import get_settings
from argus.core.alpaca_fetcher import AlpacaDataFetcher, _validate_asset_cached
from argus.market.exceptions import MarketDataError
from httpx import Response


@pytest.fixture(autouse=True)
def bypass_rate_limit_delay(monkeypatch):
    """Bypass the delay in retry_with_backoff to speed up tests."""
    monkeypatch.setattr("time.sleep", lambda x: None)


@pytest.fixture
def mock_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://mock-supabase.com")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "mock-anon-key")
    return get_settings()


@pytest.fixture
def mock_edge_api(mock_settings):
    base_url = f"{mock_settings.SUPABASE_URL}/functions/v1/alpaca-data-service"

    with respx.mock(assert_all_called=False) as respx_mock:
        # Mock /assets
        assets_payload = [
            {"id": "1", "symbol": "AAPL", "class": "us_equity", "status": "active"},
            {"id": "2", "symbol": "BTC/USD", "class": "crypto", "status": "active"},
            {"id": "3", "symbol": "XYZ", "class": "us_equity", "status": "inactive"},
        ]
        respx_mock.get(f"{base_url}?action=assets").mock(
            return_value=Response(200, json=assets_payload)
        )

        # Mock /bars for AAPL
        aapl_bars_payload = {
            "bars": {
                "AAPL": [
                    {
                        "t": "2026-04-01T00:00:00Z",
                        "o": 150.0,
                        "h": 155.0,
                        "l": 149.0,
                        "c": 154.0,
                        "v": 1000000,
                        "vw": 152.5,
                        "n": 50000,
                    }
                ]
            }
        }
        respx_mock.get(url__regex=rf"^{base_url}\?action=bars&symbol=AAPL.*").mock(
            return_value=Response(200, json=aapl_bars_payload)
        )

        # Mock /bars for BTC/USD
        btc_bars_payload = {
            "bars": {
                "BTC/USD": [
                    {
                        "t": "2026-04-01T00:00:00Z",
                        "o": 60000.0,
                        "h": 61000.0,
                        "l": 59500.0,
                        "c": 60500.0,
                        "v": 1500,
                        "vw": 60200.0,
                        "n": 10000,
                    }
                ]
            }
        }
        respx_mock.get(url__regex=rf"^{base_url}\?action=bars&symbol=BTC.*").mock(
            return_value=Response(200, json=btc_bars_payload)
        )

        # Mock /bars for empty response
        empty_bars_payload = {"bars": {}}
        respx_mock.get(url__regex=rf"^{base_url}\?action=bars&symbol=EMPTY.*").mock(
            return_value=Response(200, json=empty_bars_payload)
        )

        yield respx_mock


@pytest.fixture
def fetcher(mock_edge_api):
    f = AlpacaDataFetcher()
    # Clear the lru_cache between tests
    _validate_asset_cached.cache_clear()
    return f


def test_validate_asset_valid_equity(fetcher):
    is_valid, asset_class = fetcher.validate_asset("AAPL")
    assert is_valid is True
    assert asset_class == "us_equity"


def test_validate_asset_valid_crypto(fetcher):
    is_valid, asset_class = fetcher.validate_asset("BTC/USD")
    assert is_valid is True
    assert asset_class == "crypto"


def test_validate_asset_invalid(fetcher):
    is_valid, asset_class = fetcher.validate_asset("INVALID")
    assert is_valid is False
    assert asset_class is None


def test_fetch_bars_invalid_timeframe(fetcher):
    # retry_with_backoff will catch ValueError and wrap in MarketDataError
    with pytest.raises(MarketDataError, match="fetch_bars failed after 3 attempts"):
        fetcher.fetch_bars("AAPL", "invalid", datetime.now(timezone.utc))


def test_fetch_bars_invalid_asset(fetcher):
    with pytest.raises(MarketDataError, match="fetch_bars failed after 3 attempts"):
        fetcher.fetch_bars("INVALID", "1d", datetime.now(timezone.utc))


def test_fetch_bars_success(fetcher):
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    df = fetcher.fetch_bars("AAPL", "1d", start)

    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "vwap"]
    assert len(df) == 1
    assert df.iloc[0]["open"] == 150.0
    assert df.iloc[0]["vwap"] == 152.5


def test_fetch_bars_crypto_success(fetcher):
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    df = fetcher.fetch_bars("BTC/USD", "1Hour", start)

    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "vwap"]
    assert len(df) == 1
    assert df.iloc[0]["open"] == 60000.0


def test_fetch_bars_empty_response(fetcher, mock_edge_api):
    # First we need to make EMPTY a valid asset in our mock
    assets_payload = [
        {"id": "4", "symbol": "EMPTY", "class": "us_equity", "status": "active"},
    ]
    # We override the existing mock to also provide the empty asset
    mock_edge_api.get(f"{fetcher.edge_function_url}?action=assets").mock(
        return_value=Response(200, json=assets_payload)
    )

    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    df = fetcher.fetch_bars("EMPTY", "1d", start)

    assert df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "vwap"]


def test_fetch_bars_missing_columns(fetcher, mock_edge_api):
    # Mock /bars for AAPL with missing columns
    aapl_bars_payload = {
        "bars": {
            "AAPL": [
                {
                    "t": "2026-04-01T00:00:00Z",
                    "o": 150.0,
                    # missing high, low, close
                }
            ]
        }
    }
    # Clear routes to ensure our new mock takes precedence
    mock_edge_api.clear()

    # Remock assets so validation passes
    assets_payload = [
        {"id": "1", "symbol": "AAPL", "class": "us_equity", "status": "active"},
    ]
    mock_edge_api.get(f"{fetcher.edge_function_url}?action=assets").mock(
        return_value=Response(200, json=assets_payload)
    )

    # Mock the bars call with missing columns
    mock_edge_api.get(
        url__regex=rf"^{fetcher.edge_function_url}\?action=bars&symbol=AAPL.*"
    ).mock(return_value=Response(200, json=aapl_bars_payload))

    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    with pytest.raises(MarketDataError, match="fetch_bars failed after 3 attempts"):
        fetcher.fetch_bars("AAPL", "1d", start)
