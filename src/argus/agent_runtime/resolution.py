from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.state.models import (
    ResolutionProvenance,
    ResolutionSource,
    ResolutionStatus,
)
from argus.domain.indicators import (
    IndicatorInfo,
    executable_indicator_spec,
    normalize_indicator_parameters,
    search_indicators,
)
from argus.domain.market_data import ResolvedAsset
from argus.domain.market_data import resolve_asset as resolve_market_asset
from argus.domain.market_data import search_assets as search_market_assets

VAGUE_ASSET_REFERENCES = {
    "dollar",
    "the dollar",
    "usd",
    "cash",
    "the market",
    "market",
    "crypto",
    "stocks",
    "stock market",
    "forex",
}


@dataclass(frozen=True)
class AssetResolution:
    status: ResolutionStatus
    raw_text: str
    asset: ResolvedAsset | None
    candidates: tuple[ResolvedAsset, ...]
    provenance: ResolutionProvenance


@dataclass(frozen=True)
class IndicatorResolution:
    status: ResolutionStatus
    raw_text: str
    indicator: IndicatorInfo | None
    candidates: tuple[IndicatorInfo, ...]
    provenance: ResolutionProvenance


def resolve_asset_candidate(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
) -> AssetResolution:
    raw_text = str(query or "").strip()
    normalized = " ".join(raw_text.lower().replace("-", " ").split())
    if not raw_text:
        return _asset_resolution(
            status="unsupported",
            raw_text=raw_text,
            field=field,
            source=source,
            asset=None,
            candidates=(),
            confidence="low",
        )
    if normalized in VAGUE_ASSET_REFERENCES:
        candidates = _search_assets_safely(raw_text, limit=5)
        return _asset_resolution(
            status="ambiguous",
            raw_text=raw_text,
            field=field,
            source=source,
            asset=None,
            candidates=candidates,
            confidence="low",
        )
    try:
        asset = resolve_market_asset(raw_text)
        return _asset_resolution(
            status="resolved",
            raw_text=raw_text,
            field=field,
            source=source,
            asset=asset,
            candidates=(asset,),
            confidence="high",
        )
    except Exception:
        candidates = _search_assets_safely(raw_text, limit=5)

    unique = _unique_assets(candidates)
    if len(unique) == 1:
        asset = unique[0]
        return _asset_resolution(
            status="resolved",
            raw_text=raw_text,
            field=field,
            source=source,
            asset=asset,
            candidates=(asset,),
            confidence="medium",
        )
    if len(unique) > 1:
        return _asset_resolution(
            status="ambiguous",
            raw_text=raw_text,
            field=field,
            source=source,
            asset=None,
            candidates=tuple(unique),
            confidence="medium",
        )
    return _asset_resolution(
        status="unsupported",
        raw_text=raw_text,
        field=field,
        source=source,
        asset=None,
        candidates=(),
        confidence="low",
    )


def search_assets(query: str, *, limit: int = 12) -> list[ResolvedAsset]:
    return search_market_assets(query, limit=limit)


def resolve_indicator_candidate(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
) -> IndicatorResolution:
    raw_text = str(query or "").strip()
    if not raw_text:
        return _indicator_resolution(
            status="unsupported",
            raw_text=raw_text,
            field=field,
            source=source,
            indicator=None,
            candidates=(),
            confidence="low",
        )
    candidates = tuple(search_indicators(raw_text, limit=5))
    exact = _exact_indicator(raw_text, candidates)
    indicator = exact or (candidates[0] if len(candidates) == 1 else None)
    if indicator is not None and executable_indicator_spec(indicator.key) is not None:
        return _indicator_resolution(
            status="resolved",
            raw_text=raw_text,
            field=field,
            source=source,
            indicator=indicator,
            candidates=(indicator,),
            confidence="high" if exact else "medium",
        )
    if indicator is not None:
        return _indicator_resolution(
            status="unsupported",
            raw_text=raw_text,
            field=field,
            source=source,
            indicator=indicator,
            candidates=(indicator,),
            confidence="high" if exact else "medium",
        )
    if candidates:
        return _indicator_resolution(
            status="ambiguous",
            raw_text=raw_text,
            field=field,
            source=source,
            indicator=None,
            candidates=candidates,
            confidence="medium",
        )
    return _indicator_resolution(
        status="unsupported",
        raw_text=raw_text,
        field=field,
        source=source,
        indicator=None,
        candidates=(),
        confidence="low",
    )


def search_indicator_candidates(query: str, *, limit: int = 12) -> list[IndicatorInfo]:
    return search_indicators(query, limit=limit)


def validate_indicator_execution(
    indicator: str | None,
    parameters: dict[str, Any] | None = None,
) -> IndicatorResolution:
    resolution = resolve_indicator_candidate(
        indicator or "",
        field="entry_logic",
        source="llm_extraction",
    )
    if resolution.status != "resolved":
        return resolution
    try:
        normalize_indicator_parameters(indicator, parameters)
    except ValueError:
        return _indicator_resolution(
            status="unsupported",
            raw_text=resolution.raw_text,
            field=resolution.provenance.field,
            source=resolution.provenance.source,
            indicator=resolution.indicator,
            candidates=resolution.candidates,
            confidence=resolution.provenance.confidence or "medium",
        )
    return resolution


def mention_to_provenance(
    mention: dict[str, Any],
    *,
    index: int,
) -> ResolutionProvenance:
    candidate_kind = "indicator" if mention.get("type") == "indicator" else "asset"
    raw_text = str(
        mention.get("symbol")
        or mention.get("insert_text")
        or mention.get("label")
        or ""
    ).strip()
    canonical = raw_text.upper() if candidate_kind == "asset" else raw_text.lower()
    support_status = str(mention.get("support_status") or "supported")
    status: ResolutionStatus = "resolved"
    if support_status == "draft_only":
        status = "unsupported"
    elif support_status == "unavailable":
        status = "unavailable_for_requested_run"
    return ResolutionProvenance(
        field=f"asset_universe[{index}]" if candidate_kind == "asset" else "entry_logic",
        raw_text=raw_text,
        source="user_mention",
        candidate_kind=candidate_kind,
        resolution_status=status,
        canonical_symbol=canonical or None,
        asset_class=(
            str(mention.get("description")).lower()
            if candidate_kind == "asset"
            and str(mention.get("description") or "").lower()
            in {"equity", "crypto", "currency_pair"}
            else None
        ),
        validated_by=(
            "provider_catalog" if candidate_kind == "asset" else "indicator_registry"
        ),
        confidence="high",
    )


def _asset_resolution(
    *,
    status: ResolutionStatus,
    raw_text: str,
    field: str,
    source: ResolutionSource,
    asset: ResolvedAsset | None,
    candidates: tuple[ResolvedAsset, ...],
    confidence: str,
) -> AssetResolution:
    return AssetResolution(
        status=status,
        raw_text=raw_text,
        asset=asset,
        candidates=candidates,
        provenance=ResolutionProvenance(
            field=field,
            raw_text=raw_text,
            source=source,
            candidate_kind="asset",
            resolution_status=status,
            canonical_symbol=getattr(asset, "canonical_symbol", None),
            asset_class=getattr(asset, "asset_class", None),
            validated_by="provider_catalog",
            confidence=confidence,
        ),
    )


def _indicator_resolution(
    *,
    status: ResolutionStatus,
    raw_text: str,
    field: str,
    source: ResolutionSource,
    indicator: IndicatorInfo | None,
    candidates: tuple[IndicatorInfo, ...],
    confidence: str,
) -> IndicatorResolution:
    return IndicatorResolution(
        status=status,
        raw_text=raw_text,
        indicator=indicator,
        candidates=candidates,
        provenance=ResolutionProvenance(
            field=field,
            raw_text=raw_text,
            source=source,
            candidate_kind="indicator",
            resolution_status=status,
            canonical_symbol=getattr(indicator, "key", None),
            validated_by="indicator_registry",
            confidence=confidence,
        ),
    )


def _unique_assets(candidates: tuple[ResolvedAsset, ...]) -> list[ResolvedAsset]:
    unique: dict[tuple[str, str], ResolvedAsset] = {}
    for candidate in candidates:
        key = (candidate.canonical_symbol, candidate.asset_class)
        unique.setdefault(key, candidate)
    return list(unique.values())


def _search_assets_safely(query: str, *, limit: int) -> tuple[ResolvedAsset, ...]:
    try:
        return tuple(search_market_assets(query, limit=limit))
    except Exception:
        return ()


def _exact_indicator(
    raw_text: str,
    candidates: tuple[IndicatorInfo, ...],
) -> IndicatorInfo | None:
    normalized = " ".join(raw_text.lower().replace("-", " ").split())
    compact = normalized.replace(" ", "_")
    for candidate in candidates:
        aliases = {
            candidate.key.lower(),
            candidate.label.lower(),
            *(alias.lower() for alias in candidate.aliases),
        }
        if normalized in aliases or compact in aliases:
            return candidate
    return None
