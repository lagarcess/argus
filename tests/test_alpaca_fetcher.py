import urllib.parse
from datetime import datetime, timezone

import pytest
import respx
from argus.config import get_settings
from argus.core.alpaca_fetcher import AlpacaDataFetcher
from argus.market.exceptions import MarketDataError
from httpx import Response


@pytest.fixture(autouse=True)
def bypass_rate_limit_delay(monkeypatch):
    """Bypass the delay in retry_with_backoff to speed up tests."""
    monkeypatch.setattr("time.sleep", lambda x: None)


@pytest.fixture
def mock_settings(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("SUPABASE_URL", "http://mock-supabase.com")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "mock-anon-key")
    return get_settings()


@pytest.fixture
def mock_edge_api(mock_settings):
    base_url = f"{mock_settings.SUPABASE_URL}/functions/v1/alpaca-data-service"

    with respx.mock(assert_all_called=False) as respx_mock:
        # Mock /assets
        assets_payload = [
            {
                "id": "1",
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "class": "us_equity",
                "status": "active",
            },
            {
                "id": "2",
                "symbol": "BTCUSD",
                "name": "Bitcoin",
                "class": "crypto",
                "status": "active",
            },
            {
                "id": "3",
                "symbol": "XYZ",
                "name": "XYZ Corp",
                "class": "us_equity",
                "status": "inactive",
            },
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
                    }
                ]
            }
        }
        respx_mock.get(url__regex=rf"^{base_url}\?action=bars&symbol=AAPL.*").mock(
            return_value=Response(200, json=aapl_bars_payload)
        )

        # Mock /bars for BTC/USD (verify it hits BTC/USD even if map has BTCUSD)
        # Note: respx matches the raw URL, so params are already encoded if sent correctly
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
                    }
                ]
            }
        }

        # Explicitly check for encoded slash if we were testing the Edge Function URL directly,
        # but here we test the Python side which just passes the string to params={}.
        # httpx handles encoding for us.
        respx_mock.get(url__regex=rf"^{base_url}\?action=bars&symbol=BTC%2FUSD.*").mock(
            return_value=Response(200, json=btc_bars_payload)
        )

        yield respx_mock


@pytest.fixture
def fetcher(mock_edge_api):
    with AlpacaDataFetcher() as f:
        yield f


def test_validate_asset_valid_equity(fetcher):
    is_valid, asset_class = fetcher.validate_asset("AAPL")
    assert is_valid is True
    assert asset_class == "us_equity"


def test_validate_asset_valid_crypto_fallback(fetcher):
    # BTC/USD should match BTCUSD in the cache
    is_valid, asset_class = fetcher.validate_asset("BTC/USD")
    assert is_valid is True
    assert asset_class == "crypto"


def test_validate_asset_invalid(fetcher):
    is_valid, asset_class = fetcher.validate_asset("INVALID")
    assert is_valid is False
    assert asset_class is None


def test_fetch_bars_invalid_timeframe(fetcher):
    with pytest.raises(MarketDataError, match="fetch_bars failed after 3 attempts"):
        fetcher.fetch_bars("AAPL", "invalid", datetime.now(timezone.utc))


def test_fetch_bars_success(fetcher):
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    df = fetcher.fetch_bars("AAPL", "1d", start)

    assert not df.empty
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "vwap"]
    assert len(df) == 1
    assert df.iloc[0]["open"] == 150.0


def test_fetch_bars_crypto_slash_encoding(fetcher, mock_edge_api, monkeypatch):
    """Verify that symbols with slashes are passed correctly."""
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)

    # This should hit the respx route with symbol=BTC%2FUSD
    df = fetcher.fetch_bars("BTC/USD", "1Hour", start)

    assert not df.empty
    assert df.iloc[0]["open"] == 60000.0


def test_fetch_bars_timezone_safety(fetcher, mock_edge_api, monkeypatch):
    """Verify that naive datetimes are handled safely."""
    start = datetime(2026, 4, 1)  # Naive

    # Should not raise error, and should be formatted as Z in the URL
    fetcher.fetch_bars("AAPL", "1d", start)

    last_request = mock_edge_api.calls.last.request
    query = urllib.parse.parse_qs(last_request.url.query.decode())
    assert "Z" in query["start"][0]


def test_context_manager_lifecycle():
    """Verify that the context manager closes the client."""
    with AlpacaDataFetcher() as fetcher:
        assert not fetcher.client.is_closed
    assert fetcher.client.is_closed


def test_lazy_loading_cache_efficiency(fetcher, mock_edge_api):
    """Verify that assets are only fetched once."""
    fetcher.validate_asset("AAPL")
    fetcher.validate_asset("BTC/USD")

    # Check number of calls to action=assets
    asset_calls = [
        c for c in mock_edge_api.calls if "action=assets" in str(c.request.url)
    ]
    assert len(asset_calls) == 1
