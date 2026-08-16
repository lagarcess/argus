from __future__ import annotations

from typing import Any, Callable

from loguru import logger

from argus.agent_runtime.asset_text_grounding import (
    asset_name_is_pair_shorthand,
    text_corroborates_resolved_asset,
)
from argus.agent_runtime.discovery.contracts import (
    MAX_CANDIDATE_NAME_CHARS,
    MAX_REASON_CHARS,
    MAX_SYMBOL_GUESS_CHARS,
    MAX_UNVERIFIED_NAMES,
    DiscoveryExtraction,
    ValidatedCandidate,
)
from argus.domain.research.search import SearchResultPacket


def _bounded_text(value: str, limit: int) -> str:
    cleaned = "".join(char for char in value if char >= " " and char != "\x7f")
    return cleaned.strip()[:limit]


def _resolution_matches_request(
    *,
    display_name: str,
    symbol_guess: str,
    resolved: Any,
    asset_class: str,
    asset_class_hint: str | None,
) -> bool:
    """Is the resolved asset about the entity the sources actually named?

    A ticker can exist in more than one asset class, so resolving the symbol
    alone can return an unrelated company that merely shares it. Corroboration
    is what separates a crypto-exposure equity (a Bitcoin trust answering a
    Bitcoin question) from a collision (a gold miner answering a Tron
    question).
    """

    # A decorated ticker ("$TRX", "(TRX)", "TRX.") still names no entity, and
    # corroborating it would only match the symbol back to itself. Compare on
    # alphanumerics so every spelling of a bare ticker takes the same branch.
    named_entity = "".join(char for char in display_name if char.isalnum()).upper()
    bare_symbol = "".join(char for char in symbol_guess if char.isalnum()).upper()
    if named_entity and named_entity != bare_symbol:
        if asset_name_is_pair_shorthand(resolved):
            # "ETH/USD" names no entity, so "Ethereum" can never match it and
            # every coin called by its proper name would be dropped as a
            # mismatch. With no name evidence either way, the request's own
            # class is the only signal, exactly as for a bare ticker.
            return asset_class_hint is None or asset_class == asset_class_hint
        return text_corroborates_resolved_asset(display_name, resolved)
    # The extraction named no entity beyond the ticker, so there is nothing to
    # corroborate against. The request's own class hint is the only remaining
    # signal; without one, the symbol stands on its own.
    return asset_class_hint is None or asset_class == asset_class_hint


def validated_candidates(
    extraction: DiscoveryExtraction,
    *,
    packet: SearchResultPacket,
    resolve: Callable[..., Any],
    max_candidates: int,
    asset_class_hint: str | None = None,
    require_source_evidence: bool = True,
    is_priceable: Callable[[str, str], bool] | None = None,
) -> tuple[list[ValidatedCandidate], list[str], list[str]]:
    """Independently verify every extracted candidate before it can act.

    The resolver is the hard gate: a name the provider catalog cannot resolve
    never becomes selectable, no matter what the sources or the extraction
    model claimed about it.

    require_source_evidence=False is for the model-knowledge path, which has
    no sources by construction; the resolver and corroboration gates apply
    identically on both paths.
    """

    validated: list[ValidatedCandidate] = []
    # Two different truths. `unverified` is "we could not confirm this is a
    # tradable asset". `uncorroborated` is "this resolves to something real,
    # but not to what the sources named" -- saying it is not tradable would be
    # false, since a Bitcoin trust plainly is.
    unverified: list[str] = []
    uncorroborated: list[str] = []
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
        if not _resolution_matches_request(
            display_name=display_name,
            symbol_guess=symbol_guess,
            resolved=resolved,
            asset_class=str(asset_class),
            asset_class_hint=asset_class_hint,
        ):
            logger.info(
                "Discovery candidate dropped: resolution does not match the named entity",
                symbol_guess=symbol_guess,
                extracted_name=display_name,
                resolved_name=str(getattr(resolved, "name", "") or ""),
                resolved_class=str(asset_class),
                asset_class_hint=asset_class_hint,
            )
            _note_unverified(uncorroborated, display_name or symbol_guess)
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
        if require_source_evidence and not valid_source_indices:
            _note_unverified(unverified, display_name or symbol_guess)
            continue
        if is_priceable is not None and not is_priceable(canonical, str(asset_class)):
            # The catalog lists it, but a row we cannot price is a row we
            # cannot backtest. Offering it would only move the dead end to
            # the moment the user taps it.
            logger.info(
                "Discovery candidate dropped: listed but no price history",
                symbol=canonical,
                extracted_name=display_name,
                asset_class=str(asset_class),
            )
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
    return validated, unverified, uncorroborated


def _note_unverified(unverified: list[str], name: str) -> None:
    cleaned = _bounded_text(name, MAX_CANDIDATE_NAME_CHARS)
    if cleaned and cleaned not in unverified and len(unverified) < MAX_UNVERIFIED_NAMES:
        unverified.append(cleaned)
