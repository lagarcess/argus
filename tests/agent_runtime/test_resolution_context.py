from __future__ import annotations

from dataclasses import dataclass

from argus.agent_runtime.state.models import ResolutionProvenance
from argus.domain.indicators import executable_indicator_spec, search_indicators


@dataclass(frozen=True)
class AssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


def test_asset_resolution_records_bitcoin_provenance(monkeypatch) -> None:
    from argus.agent_runtime import resolution

    monkeypatch.setattr(
        resolution,
        "resolve_market_asset",
        lambda query: AssetStub("BTC", "crypto", "Bitcoin", query),
    )

    result = resolution.resolve_asset_candidate(
        "Bitcoin",
        field="asset_universe[0]",
        source="llm_extraction",
    )

    assert result.status == "resolved"
    assert result.asset is not None
    assert result.asset.canonical_symbol == "BTC"
    assert result.provenance == ResolutionProvenance(
        field="asset_universe[0]",
        raw_text="Bitcoin",
        source="llm_extraction",
        candidate_kind="asset",
        resolution_status="resolved",
        canonical_symbol="BTC",
        asset_class="crypto",
        validated_by="provider_catalog",
        confidence="high",
    )


def test_vague_dollar_asset_language_is_ambiguous_not_unsupported(monkeypatch) -> None:
    from argus.agent_runtime import resolution

    def fail_resolve(_: str) -> AssetStub:
        raise ValueError("invalid_symbol")

    monkeypatch.setattr(resolution, "resolve_market_asset", fail_resolve)
    monkeypatch.setattr(resolution, "search_market_assets", lambda query, limit=5: [])

    result = resolution.resolve_asset_candidate(
        "the dollar",
        field="asset_universe[0]",
        source="llm_extraction",
    )

    assert result.status == "ambiguous"
    assert result.provenance.resolution_status == "ambiguous"
    assert result.provenance.canonical_symbol is None
    assert result.provenance.validated_by == "provider_catalog"


def test_currency_pair_resolution_preserves_direction(monkeypatch) -> None:
    from argus.agent_runtime import resolution

    monkeypatch.setattr(
        resolution,
        "resolve_market_asset",
        lambda query: AssetStub("EURUSD", "currency_pair", "EUR/USD", query),
    )

    result = resolution.resolve_asset_candidate(
        "EUR/USD",
        field="asset_universe[0]",
        source="llm_extraction",
    )

    assert result.status == "resolved"
    assert result.asset is not None
    assert result.asset.canonical_symbol == "EURUSD"
    assert result.provenance.raw_text == "EUR/USD"


def test_macd_is_searchable_but_not_executable() -> None:
    from argus.agent_runtime import resolution

    result = resolution.resolve_indicator_candidate(
        "MACD",
        field="entry_logic",
        source="llm_extraction",
    )

    assert search_indicators("MACD")[0].key == "macd"
    assert executable_indicator_spec("MACD") is None
    assert result.status == "unsupported"
    assert result.provenance.canonical_symbol == "macd"
    assert result.provenance.validated_by == "indicator_registry"

