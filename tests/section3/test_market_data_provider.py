from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from argus.domain.market_data import assets, provider
from argus.domain.market_data.assets import ResolvedAsset


def test_normalize_df_enforces_utc_sorted_lowercase_ohlcv() -> None:
    frame = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [101.0, 102.0],
            "Low": [99.0, 100.0],
            "Close": [100.5, 101.5],
            "Volume": [10.0, 12.0],
        },
        index=pd.to_datetime(["2025-01-02", "2025-01-01"]),
    )
    normalized = provider._normalize_df(frame, symbol="AAPL")
    assert list(normalized.columns) == ["open", "high", "low", "close", "volume"]
    assert str(normalized.index.tz) == "UTC"
    assert normalized.index[0] < normalized.index[1]


@pytest.mark.parametrize(
    ("symbol", "asset_class", "expected"),
    [
        ("aapl", "equity", "AAPL"),
        ("btc", "crypto", "BTC/USD"),
        ("btcusd", "crypto", "BTC/USD"),
        ("eth/usd", "crypto", "ETH/USD"),
    ],
)
def test_to_alpaca_symbol_normalizes_symbol_forms(
    symbol: str, asset_class: provider.AssetClass, expected: str
) -> None:
    assert provider._to_alpaca_symbol(symbol, asset_class) == expected


def test_fetch_ohlcv_passes_ttl_cache_bin(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_cached(**kwargs):  # noqa: ANN003
        captured.update(kwargs)
        return pd.DataFrame(
            {
                "open": [1.0],
                "high": [1.0],
                "low": [1.0],
                "close": [1.0],
                "volume": [1.0],
            },
            index=pd.DatetimeIndex([pd.Timestamp("2025-01-01T00:00:00Z")]),
        )

    monkeypatch.setenv("MARKET_DATA_CACHE_TTL", "900")
    monkeypatch.setattr(provider, "_fetch_bars_cached", fake_cached)
    monkeypatch.setattr(provider.time_module, "time", lambda: 1801)

    provider.fetch_ohlcv(
        symbol="AAPL",
        asset_class="equity",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        timeframe="1D",
    )

    assert captured["cache_bin"] == 2


def test_fetch_ohlcv_fail_closed_without_synthetic_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_cached(**kwargs):  # noqa: ANN003, ARG001
        raise ValueError("market_data_unavailable")

    monkeypatch.setattr(provider, "_fetch_bars_cached", fake_cached)

    with pytest.raises(ValueError, match="market_data_unavailable"):
        provider.fetch_ohlcv(
            symbol="AAPL",
            asset_class="equity",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
            timeframe="1D",
        )


def test_resolve_asset_aliases_and_caches_universe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}

    def fake_load_assets() -> dict[str, ResolvedAsset]:
        calls["count"] += 1
        mapping: dict[str, ResolvedAsset] = {}
        assets._add_aliases(
            mapping,
            ResolvedAsset(
                canonical_symbol="AAPL",
                asset_class="equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            ),
            canonical="AAPL",
        )
        assets._add_aliases(
            mapping,
            ResolvedAsset(
                canonical_symbol="BTC",
                asset_class="crypto",
                name="Bitcoin",
                raw_symbol="BTC/USD",
            ),
            canonical="BTC",
        )
        return mapping

    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", fake_load_assets)
    monkeypatch.setattr(assets, "_load_assets_from_kraken", lambda: {})

    assert assets.resolve_asset("aapl").asset_class == "equity"
    assert assets.resolve_asset("btc/usd").canonical_symbol == "BTC"
    assert assets.resolve_asset("BTCUSD").canonical_symbol == "BTC"
    assert calls["count"] == 1


def test_resolve_asset_rejects_unknown_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_assets() -> dict[str, ResolvedAsset]:
        mapping: dict[str, ResolvedAsset] = {}
        assets._add_aliases(
            mapping,
            ResolvedAsset(
                canonical_symbol="AAPL",
                asset_class="equity",
                name="Apple Inc.",
                raw_symbol="AAPL",
            ),
            canonical="AAPL",
        )
        return mapping

    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", fake_load_assets)
    monkeypatch.setattr(assets, "_load_assets_from_kraken", lambda: {})

    with pytest.raises(ValueError, match="invalid_symbol"):
        assets.resolve_asset("NOTREAL")


def test_live_provider_mode_fails_closed_when_provider_catalog_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setattr(
        assets,
        "_load_assets_from_alpaca",
        lambda: (_ for _ in ()).throw(ValueError("asset_universe_unavailable")),
    )
    monkeypatch.setattr(assets, "_load_assets_from_kraken", lambda: {})

    with pytest.raises(ValueError, match="asset_universe_unavailable"):
        assets.resolve_asset("Apple")


def test_warm_asset_universe_fails_closed_when_cache_refresh_leaves_no_alias_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets.clear_asset_cache()
    monkeypatch.setattr(assets, "_refresh_asset_cache_if_needed", lambda *, force=False: None)

    with pytest.raises(ValueError, match="asset_universe_unavailable"):
        assets.warm_asset_universe(force=True)


def test_synthetic_unit_fixture_is_explicitly_opted_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")

    apple = assets.resolve_asset("Apple")
    nvidia = assets.search_assets("nvidia")[0]
    eurusd = assets.search_assets("eur")[0]

    assert apple.canonical_symbol == "AAPL"
    assert apple.asset_class == "equity"
    assert nvidia.canonical_symbol == "NVDA"
    assert eurusd.canonical_symbol == "EURUSD"
    assert eurusd.asset_class == "currency_pair"


def test_recorded_provider_fixture_uses_provider_shaped_payloads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    fixture_path = tmp_path / "asset-catalog.json"
    fixture_path.write_text(
        """
        {
          "manifest": {
            "provider_mode": "recorded_provider_fixture",
            "snapshot_date": "2026-05-13",
            "sources": ["alpaca:/v2/assets", "kraken:/public/AssetPairs"]
          },
          "alpaca_assets": [
            {
              "symbol": "AAPL",
              "name": "Apple Inc.",
              "asset_class": "us_equity",
              "status": "active"
            }
          ],
          "kraken_asset_pairs": {
            "ZEURZUSD": {
              "altname": "EURUSD",
              "wsname": "EUR/USD",
              "base": "ZEUR",
              "quote": "ZUSD",
              "status": "online"
            }
          }
        }
        """,
        encoding="utf-8",
    )

    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "recorded_provider_fixture")
    monkeypatch.setenv("ARGUS_ASSET_FIXTURE_PATH", str(fixture_path))

    apple = assets.resolve_asset("Apple Inc.")
    eurusd = assets.resolve_asset("EUR/USD")

    assert apple.canonical_symbol == "AAPL"
    assert apple.asset_class == "equity"
    assert eurusd.canonical_symbol == "EURUSD"
    assert eurusd.asset_class == "currency_pair"


def test_asset_search_does_not_promote_close_symbol_typos_as_provider_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping: dict[str, ResolvedAsset] = {}
    aapl = ResolvedAsset(
        canonical_symbol="AAPL",
        asset_class="equity",
        name="Apple Inc.",
        raw_symbol="AAPL",
    )
    aaoi = ResolvedAsset(
        canonical_symbol="AAOI",
        asset_class="equity",
        name="Applied Optoelectronics Inc.",
        raw_symbol="AAOI",
    )
    assets._add_aliases(mapping, aaoi, canonical="AAOI")
    assets._add_aliases(mapping, aapl, canonical="AAPL")
    mapping["apple inc."] = aapl

    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", lambda: mapping)
    monkeypatch.setattr(assets, "_load_assets_from_kraken", lambda: {})

    assert assets.search_assets("aapq") == []


def test_asset_search_supports_provider_backed_crypto_name_pair_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")

    bitcoin_usd = assets.search_assets("bitcoin usd")
    bitcoin_dollar = assets.search_assets("bitcoin dollar")
    btc_usd = assets.search_assets("btc usd")

    assert bitcoin_usd[0].canonical_symbol == "BTC"
    assert bitcoin_dollar[0].canonical_symbol == "BTC"
    assert btc_usd[0].canonical_symbol == "BTC"


def test_resolve_asset_accepts_unique_provider_name_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping: dict[str, ResolvedAsset] = {}
    record = ResolvedAsset(
        canonical_symbol="AAPL",
        asset_class="equity",
        name="Apple Inc.",
        raw_symbol="AAPL",
    )
    assets._add_aliases(mapping, record, canonical="AAPL")
    mapping[record.name.lower()] = record

    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", lambda: mapping)
    monkeypatch.setattr(assets, "_load_assets_from_kraken", lambda: {})

    assert assets.resolve_asset("apple").canonical_symbol == "AAPL"


def test_resolve_asset_does_not_force_ambiguous_company_hints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping: dict[str, ResolvedAsset] = {}
    for symbol, name in (
        ("GOOG", "Alphabet Inc. Class C Capital Stock"),
        ("GOOGL", "Alphabet Inc. Class A Common Stock"),
        ("GOOP", "Kurv Yield Premium Strategy Google ETF"),
        ("MSFT", "Microsoft Corporation Common Stock"),
        ("MSFX", "T-Rex 2X Long Microsoft Daily Target ETF"),
    ):
        record = ResolvedAsset(
            canonical_symbol=symbol,
            asset_class="equity",
            name=name,
            raw_symbol=symbol,
        )
        assets._add_aliases(mapping, record, canonical=symbol)
        mapping[name.lower()] = record

    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", lambda: mapping)
    monkeypatch.setattr(assets, "_load_assets_from_kraken", lambda: {})

    with pytest.raises(ValueError, match="invalid_symbol"):
        assets.resolve_asset("google")


def test_live_provider_does_not_use_static_company_hint_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping: dict[str, ResolvedAsset] = {}
    record = ResolvedAsset(
        canonical_symbol="GOOGL",
        asset_class="equity",
        name="Alphabet Inc. Class A Common Stock",
        raw_symbol="GOOGL",
    )
    assets._add_aliases(mapping, record, canonical="GOOGL")
    mapping[record.name.lower()] = record

    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", lambda: mapping)
    monkeypatch.setattr(assets, "_load_assets_from_kraken", lambda: {})

    with pytest.raises(ValueError, match="invalid_symbol"):
        assets.resolve_asset("google")


def test_resolve_asset_does_not_fuzzy_replace_exact_ticker_like_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping: dict[str, ResolvedAsset] = {}
    slay = ResolvedAsset(
        canonical_symbol="SLAY",
        asset_class="crypto",
        name="Slex Token/USD",
        raw_symbol="SLAY/USD",
    )
    assets._add_aliases(mapping, slay, canonical="SLAY")

    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", lambda: {})
    monkeypatch.setattr(assets, "_load_assets_from_kraken", lambda: mapping)

    with pytest.raises(ValueError, match="invalid_symbol"):
        assets.resolve_asset("TSLA")


def test_kraken_currency_pairs_are_available_without_alpaca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_kraken_get(path: str, params: dict[str, object] | None = None):
        assert path == "/public/AssetPairs"
        assert params is None
        return {
            "error": [],
            "result": {
                "ZEURZUSD": {
                    "altname": "EURUSD",
                    "wsname": "EUR/USD",
                    "base": "ZEUR",
                    "quote": "ZUSD",
                    "status": "online",
                }
            },
        }

    assets.clear_asset_cache()
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setattr(assets, "_load_assets_from_alpaca", lambda: {})
    monkeypatch.setattr(assets, "_kraken_public_get", fake_kraken_get)

    resolved = assets.resolve_asset("EUR/USD")

    assert resolved.canonical_symbol == "EURUSD"
    assert resolved.asset_class == "currency_pair"
    assert assets.search_assets("euro dollar")[0].canonical_symbol == "EURUSD"


def test_fetch_kraken_ohlcv_parses_currency_pair_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_kraken_get(path: str, params: dict[str, object] | None = None):
        assert path == "/public/OHLC"
        assert params == {"pair": "EURUSD", "interval": 1440, "since": 1735689600}
        return {
            "error": [],
            "result": {
                "ZEURZUSD": [
                    [1735689600, "1.0", "1.2", "0.9", "1.1", "1.05", "100", 12],
                    [1735776000, "1.1", "1.3", "1.0", "1.2", "1.15", "150", 15],
                ],
                "last": 1735776000,
            },
        }

    monkeypatch.setattr(provider, "_kraken_public_get", fake_kraken_get)

    bars = provider.fetch_ohlcv(
        symbol="EURUSD",
        asset_class="currency_pair",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        timeframe="1D",
    )

    assert list(bars.columns) == ["open", "high", "low", "close", "volume"]
    assert bars["close"].tolist() == [1.1, 1.2]
    assert str(bars.index.tz) == "UTC"


def test_fetch_kraken_ohlcv_rejects_windows_over_720_candles() -> None:
    with pytest.raises(ValueError, match="kraken_ohlc_window_exceeded"):
        provider.fetch_ohlcv(
            symbol="EURUSD",
            asset_class="currency_pair",
            start_date=date(2023, 1, 1),
            end_date=date(2025, 1, 1),
            timeframe="1D",
        )
