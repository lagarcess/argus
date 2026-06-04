from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.resolution import AssetResolution
from argus.domain.market_data import is_ticker_like_query

ResolveAssetCandidate = Callable[
    [str],
    AssetResolution | None,
]


@dataclass(frozen=True)
class GroundedAssetMention:
    raw_text: str
    asset: Any
    resolution: AssetResolution


def grounded_asset_mentions_from_text(
    text: str,
    *,
    resolve_candidate: ResolveAssetCandidate,
    excluded_tokens: set[str] | None = None,
    limit: int = 5,
) -> list[GroundedAssetMention]:
    """Return provider-grounded asset mentions that are supported by text evidence."""

    mentions: list[GroundedAssetMention] = []
    seen: set[str] = set()
    excluded = {
        token.strip().lstrip("$").lower()
        for token in (excluded_tokens or set())
        if token.strip()
    }
    for phrase in _asset_candidate_phrases(text):
        if _candidate_overlaps_excluded_tokens(phrase, excluded):
            continue
        resolution = resolve_candidate(phrase)
        if resolution is None:
            continue
        if resolution.status != "resolved" or resolution.asset is None:
            continue
        if not _candidate_text_supports_resolved_asset(phrase, resolution.asset):
            continue
        symbol = str(getattr(resolution.asset, "canonical_symbol", "") or "").upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        mentions.append(
            GroundedAssetMention(
                raw_text=phrase,
                asset=resolution.asset,
                resolution=resolution,
            )
        )
        if len(mentions) >= limit:
            break
    return mentions


def provider_ticker_mentions_from_text(
    text: str,
    *,
    resolve_candidate: ResolveAssetCandidate,
    excluded_tokens: set[str] | None = None,
    limit: int = 5,
) -> list[GroundedAssetMention]:
    """Return exact provider-backed ticker mentions from user text.

    This is intentionally narrower than general asset grounding. It supports
    contract repair for fields like explicit benchmarks where a user may type a
    lowercase ETF/ticker symbol, while still avoiding company-name alias tables
    or broad natural-language routing shortcuts.
    """

    mentions: list[GroundedAssetMention] = []
    seen: set[str] = set()
    excluded = {
        token.strip().lstrip("$").lower()
        for token in (excluded_tokens or set())
        if token.strip()
    }
    for token in _asset_candidate_tokens(text):
        candidate = token.lstrip("$").strip()
        if not candidate or candidate.lower() in excluded:
            continue
        if not is_ticker_like_query(candidate):
            continue
        resolution = resolve_candidate(candidate)
        if resolution is None:
            continue
        if resolution.status != "resolved" or resolution.asset is None:
            continue
        if _compact_asset_candidate(candidate) not in _asset_symbol_texts(
            resolution.asset
        ):
            continue
        symbol = str(
            getattr(resolution.asset, "canonical_symbol", "") or ""
        ).upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        mentions.append(
            GroundedAssetMention(
                raw_text=token,
                asset=resolution.asset,
                resolution=resolution,
            )
        )
        if len(mentions) >= limit:
            break
    return mentions


def _candidate_overlaps_excluded_tokens(phrase: str, excluded_tokens: set[str]) -> bool:
    if not excluded_tokens:
        return False
    return any(
        token.lstrip("$").lower() in excluded_tokens
        for token in _asset_candidate_tokens(phrase)
    )


def grounded_asset_mention_has_name_support(mention: GroundedAssetMention) -> bool:
    tokens = _asset_candidate_tokens(str(mention.raw_text or ""))
    if not tokens:
        return False
    name_words = {
        word
        for word in _asset_name_tokens(getattr(mention.asset, "name", ""))
        if word
    }
    if not name_words:
        return False
    lowered_tokens = [token.lstrip("$").lower() for token in tokens]
    if len(tokens) > 1:
        return (
            any(len(token) >= 4 for token in lowered_tokens)
            and all(token in name_words for token in lowered_tokens)
        )
    lowered = lowered_tokens[0]
    return (
        len(lowered) >= 4
        and lowered in name_words
        and _single_name_token_supports_asset(lowered, mention.asset)
    )


def _asset_candidate_phrases(message: str) -> list[str]:
    tokens = _asset_candidate_tokens(message)
    phrases: list[str] = []
    seen: set[str] = set()
    max_window = min(3, len(tokens))
    for window_size in range(max_window, 0, -1):
        for start in range(0, len(tokens) - window_size + 1):
            phrase = " ".join(tokens[start : start + window_size]).strip()
            if not phrase or phrase in seen:
                continue
            if not any(char.isalpha() for char in phrase):
                continue
            seen.add(phrase)
            phrases.append(phrase)
    return phrases


def _asset_candidate_tokens(message: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in str(message or ""):
        if char.isalnum() or char in {"/", "-", "$"}:
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _candidate_text_supports_resolved_asset(phrase: str, asset: Any) -> bool:
    candidate = str(phrase or "").strip()
    if not candidate:
        return False
    tokens = _asset_candidate_tokens(candidate)
    if not tokens:
        return False

    symbol_texts = _asset_symbol_texts(asset)
    name_words = {
        word for word in _asset_name_tokens(getattr(asset, "name", "")) if word
    }
    lowered_tokens = [token.lstrip("$").lower() for token in tokens]

    if len(tokens) > 1:
        return (
            any(len(token) >= 4 for token in lowered_tokens)
            and all(token in name_words for token in lowered_tokens)
        )

    token = tokens[0]
    compact_token = _compact_asset_candidate(token)
    if len(compact_token) < 2:
        return False
    if token.startswith("$"):
        return compact_token in symbol_texts
    if token == token.upper() and _token_has_uppercase_letter(token):
        return compact_token in symbol_texts
    lowered = token.lower()
    if len(lowered) >= 4 and lowered in name_words:
        return _single_name_token_supports_asset(lowered, asset)
    if ("/" in token or "-" in token) and compact_token in symbol_texts:
        return True
    return False


def _asset_symbol_texts(asset: Any) -> set[str]:
    values = {
        str(getattr(asset, "canonical_symbol", "") or ""),
        str(getattr(asset, "raw_symbol", "") or ""),
    }
    return {
        compact
        for value in values
        if (compact := _compact_asset_candidate(value))
    }


def _compact_asset_candidate(value: str) -> str:
    compact: list[str] = []
    for char in str(value or "").lower():
        if char.isalnum():
            compact.append(char)
    return "".join(compact)


def _token_has_uppercase_letter(value: str) -> bool:
    return any(char.isalpha() and char.isupper() for char in str(value or ""))


def _asset_name_tokens(name: str) -> set[str]:
    return set(_asset_name_token_sequence(name))


def _asset_name_token_sequence(name: str) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    current: list[str] = []
    for char in str(name or "").lower():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            token = "".join(current)
            if token not in seen:
                tokens.append(token)
                seen.add(token)
            current = []
    if current:
        token = "".join(current)
        if token not in seen:
            tokens.append(token)
    return tokens


def _single_name_token_supports_asset(token: str, asset: Any) -> bool:
    meaningful_name_tokens = [
        name_token
        for name_token in _asset_name_token_sequence(getattr(asset, "name", ""))
        if len(name_token) >= 2 and any(char.isalpha() for char in name_token)
    ]
    return (
        bool(meaningful_name_tokens)
        and token == meaningful_name_tokens[0]
        and len(meaningful_name_tokens) <= 4
    )
