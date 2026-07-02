"""Current-message asset clarification helpers for the interpret stage."""

from __future__ import annotations

from collections.abc import Callable

from argus.agent_runtime.asset_text_grounding import (
    ambiguous_asset_resolutions_from_text,
    grounded_asset_mentions_from_text,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.run_field_contract import (
    current_message_execution_context_tokens,
)
from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _message_explicitly_mentions_symbol,
    _normalized_symbol,
)
from argus.agent_runtime.state.models import AmbiguousField, StrategySummary

ResolveAssetCandidate = Callable[[str], AssetResolution | None]


def ambiguous_asset_fields_from_current_message(
    *,
    strategy: StrategySummary,
    current_user_message: str,
    resolve_candidate: ResolveAssetCandidate,
) -> list[AmbiguousField]:
    if not current_user_message.strip():
        return []

    resolutions = ambiguous_asset_resolutions_from_text(
        current_user_message,
        resolve_candidate=resolve_candidate,
        excluded_tokens=current_message_execution_context_tokens(
            current_user_message,
            strategy_type=strategy.strategy_type,
        ),
        limit=5,
    )
    covered_symbols = {
        symbol
        for raw_symbol in strategy.asset_universe
        if (symbol := _normalized_symbol(raw_symbol))
    }
    fields: list[AmbiguousField] = []
    for resolution in resolutions:
        candidate_symbols = [
            symbol
            for candidate in resolution.candidates
            if (
                symbol := _normalized_symbol(
                    getattr(candidate, "canonical_symbol", None)
                )
            )
        ]
        raw_text = str(resolution.raw_text or "").strip()
        if (
            covered_symbols
            and candidate_symbols
            and any(symbol in covered_symbols for symbol in candidate_symbols)
            and _message_explicitly_mentions_symbol(
                raw_text,
                symbols=sorted(covered_symbols),
            )
        ):
            continue
        fields.append(
            AmbiguousField(
                field_name="asset_universe[0]",
                raw_value=raw_text or resolution.raw_text,
                candidate_normalized_value=candidate_symbols or None,
                reason_code="asset_resolution_ambiguous",
            )
        )
    return fields


def symbols_corroborated_by_strategy_text(
    *,
    symbols: list[str],
    strategy: StrategySummary,
    benchmark_symbol: str | None,
    resolve_candidate: ResolveAssetCandidate,
) -> list[str]:
    if len(symbols) <= 1:
        return symbols
    strategy_text = str(strategy.strategy_thesis or "").strip()
    if not strategy_text:
        return symbols

    semantic_mentions = grounded_asset_mentions_from_text(
        strategy_text,
        resolve_candidate=resolve_candidate,
        excluded_tokens=current_message_execution_context_tokens(
            strategy_text,
            strategy_type=strategy.strategy_type,
        ),
        limit=5,
    )
    if not semantic_mentions:
        return symbols

    semantic_symbols = {
        symbol
        for mention in semantic_mentions
        if (
            symbol := _normalized_symbol(
                getattr(mention.asset, "canonical_symbol", None)
            )
        )
        and symbol != benchmark_symbol
    }
    if not semantic_symbols:
        return symbols
    filtered = [symbol for symbol in symbols if symbol in semantic_symbols]
    return filtered or symbols
