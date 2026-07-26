from __future__ import annotations

from typing import Any, Callable

from loguru import logger

from argus.agent_runtime.discovery.contracts import (
    MAX_CANDIDATE_NAME_CHARS,
    MAX_REASON_CHARS,
    MAX_SYMBOL_GUESS_CHARS,
    MAX_UNVERIFIED_NAMES,
    DiscoveryExtraction,
    ValidatedCandidate,
)
from argus.domain.discovery_search import SearchResultPacket


def _bounded_text(value: str, limit: int) -> str:
    cleaned = "".join(char for char in value if char >= " " and char != "\x7f")
    return cleaned.strip()[:limit]


def validated_candidates(
    extraction: DiscoveryExtraction,
    *,
    packet: SearchResultPacket,
    resolve: Callable[..., Any],
    max_candidates: int,
) -> tuple[list[ValidatedCandidate], list[str]]:
    """Independently verify every extracted candidate before it can act.

    The resolver is the hard gate: a name the provider catalog cannot resolve
    never becomes selectable, no matter what the sources or the extraction
    model claimed about it.
    """

    validated: list[ValidatedCandidate] = []
    unverified: list[str] = []
    seen_symbols: set[str] = set()
    result_count = len(packet.results)
    for candidate in extraction.candidates:
        display_name = _bounded_text(candidate.name, MAX_CANDIDATE_NAME_CHARS)
        symbol_guess = _bounded_text(
            candidate.symbol_guess, MAX_SYMBOL_GUESS_CHARS
        ).upper()
        if not symbol_guess:
            _note_unverified(unverified, display_name)
            continue
        try:
            resolved = resolve(symbol_guess)
        except Exception as exc:
            logger.debug(
                "Discovery candidate failed provider resolution",
                symbol_guess=symbol_guess,
                error=str(exc),
            )
            resolved = None
        asset_class = getattr(resolved, "asset_class", None)
        canonical_symbol = getattr(resolved, "canonical_symbol", None)
        if (
            resolved is None
            or not canonical_symbol
            or asset_class not in {"equity", "crypto", "currency_pair"}
        ):
            _note_unverified(unverified, display_name or symbol_guess)
            continue
        canonical = str(canonical_symbol).upper()
        if canonical in seen_symbols:
            continue
        valid_source_indices = tuple(
            index
            for index in candidate.source_indices
            if isinstance(index, int) and 0 <= index < result_count
        )
        # Grounded means source-backed: a resolvable ticker with no surviving
        # source evidence must not become selectable.
        if not valid_source_indices:
            _note_unverified(unverified, display_name or symbol_guess)
            continue
        seen_symbols.add(canonical)
        # The resolver owns the actionable identity. The extracted name is
        # untrusted and could pair a real ticker with the wrong company.
        resolved_name = _bounded_text(
            str(getattr(resolved, "name", "") or ""), MAX_CANDIDATE_NAME_CHARS
        )
        validated.append(
            ValidatedCandidate(
                symbol=canonical,
                name=resolved_name or canonical,
                asset_class=asset_class,
                reason_text=_bounded_text(candidate.reason_text, MAX_REASON_CHARS),
                source_indices=valid_source_indices,
            )
        )
        if len(validated) >= max_candidates:
            break
    return validated, unverified


def _note_unverified(unverified: list[str], name: str) -> None:
    cleaned = _bounded_text(name, MAX_CANDIDATE_NAME_CHARS)
    if cleaned and cleaned not in unverified and len(unverified) < MAX_UNVERIFIED_NAMES:
        unverified.append(cleaned)
