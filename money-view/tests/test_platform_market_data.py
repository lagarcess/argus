import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from server.platform import market_data
from server.platform.market_data import (
    ALPACA_LATEST_BARS_URL,
    AlpacaMarketDataAdapter,
    FixtureMarketDataAdapter,
    MarketDataLoadError,
    initialize,
    latest_prices,
    load_market_prices,
)
from server.store import Store


def _response() -> dict[str, object]:
    return {
        "bars": {
            "AAPL": {
                "t": "2026-09-18T19:59:00Z",
                "o": 229.8,
                "h": 230.2,
                "l": 229.7,
                "c": 230.01,
                "v": 1211,
                "n": 21,
                "vw": 229.95,
            },
            "SPY": {
                "t": "2026-09-18T19:59:00Z",
                "o": 649.5,
                "h": 650.1,
                "l": 649.4,
                "c": 650,
                "v": 1257,
                "n": 48,
                "vw": 649.8,
            },
        }
    }


def _adapter(handler) -> AlpacaMarketDataAdapter:
    return AlpacaMarketDataAdapter(
        api_key="clara-test-key",
        api_secret="clara-test-secret",
        symbols=["aapl", "SPY", "AAPL"],
        feed="iex",
        transport=httpx.MockTransport(handler),
    )


def test_alpaca_adapter_uses_only_fixed_read_only_latest_bars_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url.copy_with(query=None)) == ALPACA_LATEST_BARS_URL
        assert request.url.host == "data.alpaca.markets"
        assert request.url.params["symbols"] == "AAPL,SPY"
        assert request.url.params["feed"] == "iex"
        assert request.url.params["currency"] == "USD"
        assert request.headers["APCA-API-KEY-ID"] == "clara-test-key"
        assert request.headers["APCA-API-SECRET-KEY"] == "clara-test-secret"
        assert "authorization" not in request.headers
        return httpx.Response(200, json=_response())

    batch = _adapter(handler).fetch_prices()

    assert batch.as_of.isoformat() == "2026-09-18"
    assert [(price.symbol, str(price.price)) for price in batch.prices] == [
        ("AAPL", "230.01"),
        ("SPY", "650"),
    ]
    assert batch.source.kind == "published"
    assert batch.source.published_on == batch.as_of
    assert batch.source.url == ALPACA_LATEST_BARS_URL
    assert batch.source.method and "not a broker quote" in batch.source.method


@pytest.mark.parametrize(
    ("bars", "code"),
    [
        ({"AAPL": _response()["bars"]["AAPL"]}, "alpaca_incomplete_price_set"),
        (
            {
                **_response()["bars"],
                "SPY": {**_response()["bars"]["SPY"], "c": "NaN"},
            },
            "invalid_alpaca_price",
        ),
        (
            {
                **_response()["bars"],
                "SPY": {**_response()["bars"]["SPY"], "t": "not-a-date"},
            },
            "invalid_alpaca_timestamp",
        ),
        (
            {
                **_response()["bars"],
                "SPY": {
                    **_response()["bars"]["SPY"],
                    "t": "2026-09-17T19:59:00Z",
                },
            },
            "inconsistent_alpaca_price_date",
        ),
    ],
)
def test_alpaca_adapter_fails_closed_on_incomplete_or_invalid_bars(
    bars: dict[str, object], code: str
) -> None:
    adapter = _adapter(lambda _request: httpx.Response(200, json={"bars": bars}))

    with pytest.raises(MarketDataLoadError, match=code):
        adapter.fetch_prices()


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (302, "alpaca_redirect_rejected"),
        (401, "alpaca_authentication_failed"),
        (403, "alpaca_authentication_failed"),
        (429, "alpaca_rate_limited"),
        (500, "alpaca_http_error"),
    ],
)
def test_alpaca_adapter_does_not_redirect_retry_or_expose_response_body(
    status: int, code: str
) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            status,
            headers={"location": "https://example.test/collect"},
            text="clara-test-secret",
        )

    with pytest.raises(MarketDataLoadError, match=code) as captured:
        _adapter(handler).fetch_prices()

    assert calls == 1
    assert "clara-test-secret" not in str(captured.value)


def test_alpaca_adapter_timeout_is_not_retried() -> None:
    calls = 0

    def timeout(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("private upstream detail", request=request)

    with pytest.raises(MarketDataLoadError, match="alpaca_request_failed"):
        _adapter(timeout).fetch_prices()

    assert calls == 1


def test_alpaca_adapter_rejects_any_destination_outside_fixed_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=_response())

    monkeypatch.setattr(
        market_data,
        "ALPACA_LATEST_BARS_URL",
        "https://example.test/v2/stocks/bars/latest",
    )
    with pytest.raises(MarketDataLoadError, match="invalid_alpaca_destination"):
        _adapter(handler).fetch_prices()

    assert calls == 0


def test_alpaca_adapter_uses_existing_last_good_loader_path(tmp_path) -> None:
    store = Store(tmp_path / "market.sqlite3")
    initialize(store)
    result = load_market_prices(
        store,
        _adapter(lambda _request: httpx.Response(200, json=_response())),
    )

    assert result["status"] == "succeeded"
    assert result["as_of"] == "2026-09-18"
    saved = latest_prices(store)
    assert saved[("AAPL", "USD")]["price_minor"] == 23001
    assert saved[("SPY", "USD")]["price_minor"] == 65000


def test_failed_alpaca_load_retains_fixture_last_good_prices(tmp_path) -> None:
    store = Store(tmp_path / "last-good.sqlite3")
    initialize(store)
    succeeded = load_market_prices(
        store, FixtureMarketDataAdapter(symbols=["AAPL", "SPY"])
    )
    before = latest_prices(store)

    failed = load_market_prices(
        store,
        _adapter(lambda _request: httpx.Response(503, text="private upstream detail")),
    )

    assert succeeded["status"] == "succeeded"
    assert failed["status"] == "failed"
    assert failed["error_code"] == "alpaca_http_error"
    after = latest_prices(store)
    assert {
        key: (value["set_id"], value["price_minor"]) for key, value in after.items()
    } == {key: (value["set_id"], value["price_minor"]) for key, value in before.items()}


def test_fixture_cli_loads_explicit_symbols_without_credentials(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "fixture-cli.sqlite3"
    environment = os.environ.copy()
    environment.pop("CLARA_ALPACA_API_KEY", None)
    environment.pop("CLARA_ALPACA_API_SECRET", None)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "server.platform.market_job",
            "load",
            "--database",
            str(database),
            "--symbols",
            "AAPL,SPY",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    output = json.loads(completed.stdout)
    assert output["provider"] == "fixture"
    assert output["symbols"] == ["AAPL", "SPY"]
    assert output["load"]["status"] == "succeeded"
    assert set(latest_prices(Store(database))) == {("AAPL", "USD"), ("SPY", "USD")}


def test_alpaca_cli_requires_only_clara_credentials_before_network(tmp_path) -> None:
    root = Path(__file__).resolve().parents[1]
    database = tmp_path / "missing-config.sqlite3"
    environment = os.environ.copy()
    environment.pop("CLARA_ALPACA_API_KEY", None)
    environment.pop("CLARA_ALPACA_API_SECRET", None)
    environment["APCA_API_KEY_ID"] = "must-not-be-read"
    environment["APCA_API_SECRET_KEY"] = "must-not-be-read"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "server.platform.market_job",
            "load",
            "--provider",
            "alpaca",
            "--database",
            str(database),
            "--symbols",
            "AAPL",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout) == {
        "provider": "alpaca",
        "status": "failed",
        "error_code": "alpaca_configuration_missing",
    }
    assert completed.stderr == ""
    assert not database.exists()
