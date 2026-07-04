from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

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
from argus.domain.market_data import ResolvedAsset, is_ticker_like_query
from argus.domain.market_data import resolve_asset as resolve_market_asset
from argus.domain.market_data import search_assets as search_market_assets


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


AssetResolutionMode = Literal["auto", "company_name", "symbol"]
_PRIMARY_EXCHANGES = {"NYSE", "NASDAQ", "NYSEARCA", "NYSEAMERICAN", "AMEX"}
_SECONDARY_EXCHANGES = {"OTC", "OTCMKTS", "PINK"}
_COMPANY_NAME_TRAILING_WORDS = {
    "corp",
    "corporation",
    "co",
    "company",
    "inc",
    "incorporated",
    "limited",
    "ltd",
    "plc",
}
_SECURITY_NAME_TRAILING_PHRASES = (
    ("class", "a", "common", "stock"),
    ("class", "b", "common", "stock"),
    ("common", "stock"),
    ("ordinary", "shares"),
)


def resolve_asset_candidate(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
    resolution_mode: AssetResolutionMode = "auto",
) -> AssetResolution:
    raw_text = str(query or "").strip()
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
    if resolution_mode == "company_name":
        return _resolve_company_name_asset(raw_text, field=field, source=source)
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
        if is_ticker_like_query(raw_text) and source != "user_mention":
            return _asset_resolution(
                status="unsupported",
                raw_text=raw_text,
                field=field,
                source=source,
                asset=None,
                candidates=(),
                confidence="high",
            )

    unique = _unique_assets(candidates)
    if len(unique) == 1:
        asset = unique[0]
        if source == "user_mention" and not _provider_name_prefix_match(
            raw_text,
            asset,
        ):
            return _asset_resolution(
                status="unsupported",
                raw_text=raw_text,
                field=field,
                source=source,
                asset=None,
                candidates=(asset,),
                confidence="low",
            )
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
        ranked_answer = _provider_ranked_user_mention_asset(raw_text, unique, source)
        if ranked_answer is not None:
            return _asset_resolution(
                status="resolved",
                raw_text=raw_text,
                field=field,
                source=source,
                asset=ranked_answer,
                candidates=(ranked_answer,),
                confidence="medium",
            )
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


def _resolve_company_name_asset(
    raw_text: str,
    *,
    field: str,
    source: ResolutionSource,
) -> AssetResolution:
    candidates = _unique_assets(_search_assets_safely(raw_text, limit=12))
    ranked = _rank_company_name_candidates(raw_text, candidates)
    if not ranked:
        return _asset_resolution(
            status="unsupported",
            raw_text=raw_text,
            field=field,
            source=source,
            asset=None,
            candidates=(),
            confidence="low",
        )
    best_key, best_asset = ranked[0]
    tied = [
        asset
        for key, asset in ranked
        if key[:3] == best_key[:3]
    ]
    if len(tied) > 1:
        return _asset_resolution(
            status="ambiguous",
            raw_text=raw_text,
            field=field,
            source=source,
            asset=None,
            candidates=tuple(tied[:5]),
            confidence="medium",
        )
    return _asset_resolution(
        status="resolved",
        raw_text=raw_text,
        field=field,
        source=source,
        asset=best_asset,
        candidates=(best_asset,),
        confidence="medium",
    )


def search_assets(query: str, *, limit: int = 12) -> list[ResolvedAsset]:
    return search_market_assets(query, limit=limit)


def _provider_ranked_user_mention_asset(
    raw_text: str,
    candidates: list[ResolvedAsset],
    source: ResolutionSource,
) -> ResolvedAsset | None:
    if source != "user_mention" or not candidates:
        return None
    top = candidates[0]
    if _provider_name_prefix_match(raw_text, top):
        return top
    return None


def _provider_name_prefix_match(raw_text: str, asset: ResolvedAsset) -> bool:
    lowered = " ".join(str(raw_text or "").casefold().split())
    top_name = " ".join(str(asset.name or "").casefold().split())
    return bool(lowered and top_name.startswith(lowered))


def _rank_company_name_candidates(
    raw_text: str,
    candidates: list[ResolvedAsset],
) -> list[tuple[tuple[int, int, int, int, str], ResolvedAsset]]:
    lowered = " ".join(str(raw_text or "").casefold().split())
    ranked: list[tuple[tuple[int, int, int, int, str], ResolvedAsset]] = []
    for asset in candidates:
        name_score = _company_name_match_score(lowered, asset)
        if name_score > 2:
            continue
        ranked.append(
            (
                (
                    name_score,
                    _asset_class_rank(asset),
                    _exchange_rank(asset),
                    len(str(asset.canonical_symbol or "")),
                    str(asset.canonical_symbol or ""),
                ),
                asset,
            )
        )
    ranked.sort(key=lambda item: item[0])
    return ranked


def _company_name_match_score(raw_text: str, asset: ResolvedAsset) -> int:
    name = " ".join(str(asset.name or "").casefold().split())
    core_name = _provider_company_name_core(asset.name)
    if raw_text in {name, core_name}:
        return 0
    if core_name.startswith(raw_text):
        return 1
    if name.startswith(raw_text):
        return 2
    if raw_text and raw_text in core_name:
        return 3
    if raw_text and raw_text in name:
        return 4
    return 5


def _provider_company_name_core(name: str) -> str:
    words = _normalized_name_words(name)
    words = _without_trailing_security_phrases(words)
    while words and words[-1] in _COMPANY_NAME_TRAILING_WORDS:
        words = words[:-1]
    return " ".join(words)


def _normalized_name_words(value: str) -> list[str]:
    normalized = str(value or "").casefold()
    for character in ".,()[]{}":
        normalized = normalized.replace(character, " ")
    return [word for word in normalized.split() if word]


def _without_trailing_security_phrases(words: list[str]) -> list[str]:
    trimmed = list(words)
    changed = True
    while changed and trimmed:
        changed = False
        for phrase in _SECURITY_NAME_TRAILING_PHRASES:
            length = len(phrase)
            if len(trimmed) >= length and tuple(trimmed[-length:]) == phrase:
                trimmed = trimmed[:-length]
                changed = True
                break
    return trimmed


def _asset_class_rank(asset: ResolvedAsset) -> int:
    if asset.asset_class == "equity":
        return 0
    if asset.asset_class == "crypto":
        return 1
    return 2


def _exchange_rank(asset: ResolvedAsset) -> int:
    exchange = _exchange_code(asset)
    if exchange in _PRIMARY_EXCHANGES:
        return 0
    if not exchange:
        return 1
    if exchange in _SECONDARY_EXCHANGES or "OTC" in exchange:
        return 2
    return 1


def _exchange_code(asset: ResolvedAsset) -> str:
    raw_exchange = str(getattr(asset, "exchange", "") or "").strip().upper()
    if "." in raw_exchange:
        raw_exchange = raw_exchange.rsplit(".", 1)[-1]
    return raw_exchange


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
        mention.get("symbol") or mention.get("insert_text") or mention.get("label") or ""
    ).strip()
    canonical = raw_text.upper() if candidate_kind == "asset" else raw_text.lower()
    # Defense-in-depth: the composer no longer sends support_status (drafts can't become
    # tokens — the @ picker filters them), but the backend still blocks any draft/unavailable
    # mention from another client, so this remains the authoritative containment gate.
    support_status = str(mention.get("support_status") or "supported")
    status: ResolutionStatus = "resolved"
    if support_status == "draft_only":
        status = "unsupported"
    elif support_status == "unavailable":
        status = "unavailable_for_requested_run"
    asset_class = _mention_asset_class(mention) if candidate_kind == "asset" else None
    return ResolutionProvenance(
        field=f"asset_universe[{index}]" if candidate_kind == "asset" else "entry_logic",
        raw_text=raw_text,
        source="user_mention",
        candidate_kind=candidate_kind,
        resolution_status=status,
        canonical_symbol=canonical or None,
        asset_class=asset_class,
        validated_by=(
            "client_mention" if candidate_kind == "asset" else "indicator_registry"
        ),
        confidence="high",
    )


def _mention_asset_class(mention: dict[str, Any]) -> str | None:
    explicit = str(mention.get("asset_class") or "").strip().lower()
    if explicit in {"equity", "crypto", "currency_pair"}:
        return explicit
    raw_id = str(mention.get("id") or "").strip().lower()
    id_parts = raw_id.split(":")
    if len(id_parts) >= 3 and id_parts[0] == "asset":
        id_asset_class = id_parts[1]
        if id_asset_class in {"equity", "crypto", "currency_pair"}:
            return id_asset_class
    description = str(mention.get("description") or "").strip().lower()
    labels = {
        "stock": "equity",
        "equity": "equity",
        "crypto": "crypto",
        "currency pair": "currency_pair",
        "currency_pair": "currency_pair",
    }
    return labels.get(description)


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
