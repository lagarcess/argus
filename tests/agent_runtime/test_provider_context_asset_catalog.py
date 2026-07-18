from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from argus.agent_runtime.interpreter.asset_resolution_context import (
    provider_asset_resolution_context_from_extraction,
)
from argus.agent_runtime.llm_interpreter_types import LLMAssetMentionExtraction
from argus.agent_runtime.resolution import resolve_asset_candidate
from argus.domain.market_data import assets
from argus.domain.market_data.provider import fetch_ohlcv


def _write_provider_catalog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "alpaca_assets": [
                    {
                        "symbol": "TGT",
                        "name": "Target Corporation",
                        "asset_class": "us_equity",
                        "status": "active",
                    },
                    {
                        "symbol": "WMT",
                        "name": "Walmart Inc.",
                        "asset_class": "us_equity",
                        "status": "active",
                    },
                    {
                        "symbol": "COST",
                        "name": "Costco Wholesale Corporation",
                        "asset_class": "us_equity",
                        "status": "active",
                    },
                    {
                        "symbol": "AAPL",
                        "name": "Apple Inc.",
                        "asset_class": "us_equity",
                        "status": "active",
                    },
                    {
                        "symbol": "BTC/USD",
                        "name": "Bitcoin / US Dollar",
                        "asset_class": "crypto",
                        "status": "active",
                    },
                ],
                "kraken_asset_pairs": {
                    "ZEURZUSD": {
                        "altname": "EURUSD",
                        "wsname": "EUR/USD",
                        "base": "ZEUR",
                        "quote": "ZUSD",
                        "status": "online",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def recorded_catalog(monkeypatch, tmp_path: Path) -> Iterator[Path]:
    fixture_path = tmp_path / "provider-asset-catalog.json"
    _write_provider_catalog(fixture_path)
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setenv("ARGUS_ASSET_PROVIDER_MODE", "recorded_provider_fixture")
    monkeypatch.setenv("ARGUS_ASSET_FIXTURE_PATH", str(fixture_path))
    assets.clear_asset_cache()
    yield fixture_path
    assets.clear_asset_cache()


def _provider_context_rows(
    mentions: list[dict[str, object]],
) -> list[dict[str, object]]:
    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction(asset_mentions=mentions),
        resolve_asset_candidate=resolve_asset_candidate,
    )
    assert context is not None
    return json.loads(context)["asset_resolution_candidates"]


def test_provider_context_uses_recorded_catalog_with_synthetic_market_data(
    recorded_catalog: Path,
) -> None:
    assert recorded_catalog.is_file()
    rows = _provider_context_rows(
        [
            {
                "raw_text": "target",
                "role": "traded_asset",
                "mention_kind": "company_name",
                "confidence": 0.9,
            },
            {
                "raw_text": "walmart",
                "role": "traded_asset",
                "mention_kind": "company_name",
                "confidence": 0.9,
            },
            {
                "raw_text": "costco",
                "role": "traded_asset",
                "mention_kind": "company_name",
                "confidence": 0.9,
            },
        ]
    )

    assert [row["symbol"] for row in rows] == ["TGT", "WMT", "COST"]
    assert [row["asset_class"] for row in rows] == ["equity"] * 3


def test_provider_context_single_company_name_still_resolves(
    recorded_catalog: Path,
) -> None:
    assert recorded_catalog.is_file()
    rows = _provider_context_rows(
        [
            {
                "raw_text": "target",
                "role": "traded_asset",
                "mention_kind": "company_name",
                "confidence": 0.9,
            }
        ]
    )

    assert [row["symbol"] for row in rows] == ["TGT"]


def test_provider_context_keeps_supported_name_and_does_not_invent_unknown_asset(
    recorded_catalog: Path,
) -> None:
    assert recorded_catalog.is_file()
    rows = _provider_context_rows(
        [
            {
                "raw_text": "target",
                "role": "traded_asset",
                "mention_kind": "company_name",
                "confidence": 0.9,
            },
            {
                "raw_text": "fictional moon fund",
                "role": "traded_asset",
                "mention_kind": "company_name",
                "confidence": 0.9,
            },
        ]
    )
    unknown = resolve_asset_candidate(
        "fictional moon fund",
        field="asset_universe[1]",
        source="llm_extraction",
        resolution_mode="company_name",
    )

    assert [row["symbol"] for row in rows] == ["TGT"]
    assert unknown.status == "unsupported"
    assert unknown.asset is None


@pytest.mark.parametrize(
    ("raw_text", "mention_kind", "expected_symbol", "expected_asset_class"),
    [
        ("AAPL", "ticker", "AAPL", "equity"),
        ("bitcoin", "crypto", "BTC", "crypto"),
        ("EUR/USD", "currency_pair", "EURUSD", "currency_pair"),
    ],
)
def test_provider_context_preserves_ticker_crypto_and_currency_resolution(
    recorded_catalog: Path,
    raw_text: str,
    mention_kind: str,
    expected_symbol: str,
    expected_asset_class: str,
) -> None:
    assert recorded_catalog.is_file()
    rows = _provider_context_rows(
        [
            {
                "raw_text": raw_text,
                "role": "traded_asset",
                "mention_kind": mention_kind,
                "confidence": 0.9,
            }
        ]
    )

    assert [(row["symbol"], row["asset_class"]) for row in rows] == [
        (expected_symbol, expected_asset_class)
    ]


def test_asset_catalog_override_does_not_change_synthetic_bar_provider(
    recorded_catalog: Path,
) -> None:
    assert recorded_catalog.is_file()
    frame = fetch_ohlcv(
        symbol="TGT",
        asset_class="equity",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 5),
        timeframe="1D",
    )

    assert list(frame.index.strftime("%Y-%m-%d")) == [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
    ]
