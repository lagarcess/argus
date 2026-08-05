from __future__ import annotations

from datetime import datetime

from argus.domain.search_text import normalize_search_text, search_text_contains_query


def search_type_rank(kind: str) -> int:
    ranks = {
        "conversation": 5,
        "decision": 5,
        "evidence": 5,
        "backtest": 5,
        "idea": 5,
        "chat": 4,
        "strategy": 3,
        "collection": 2,
        "run": 1,
    }
    return ranks.get(kind, 0)


def search_rank_key(
    *,
    score: int,
    kind: str,
    updated_at: datetime,
    item_id: str,
) -> tuple[int, int, int, int, datetime, int, int, str]:
    pinned_rank, exact_rank, symbol_rank, layer_rank, text_rank = _score_rank_parts(
        score
    )
    return (
        pinned_rank,
        exact_rank,
        symbol_rank,
        layer_rank,
        updated_at,
        text_rank,
        search_type_rank(kind),
        item_id,
    )


def _score_rank_parts(score: int) -> tuple[int, int, int, int, int]:
    pinned_rank, remainder = divmod(score, 1_000_000)
    exact_rank, remainder = divmod(remainder, 100_000)
    symbol_rank, remainder = divmod(remainder, 10_000)
    layer_rank, text_rank = divmod(remainder, 1_000)
    return pinned_rank, exact_rank, symbol_rank, layer_rank, text_rank


def score_search_item(
    *,
    query: str,
    title: str,
    matched_text: str,
    pinned: bool,
    symbol_exact_match: bool = False,
    match_layer_rank: int = 0,
) -> int:
    score = 0
    if pinned:
        score += 1_000_000
    normalized_query = normalize_search_text(query)
    normalized_title = normalize_search_text(title)
    if normalized_query == normalized_title:
        score += 100_000
    elif search_text_contains_query(query=query, text=title):
        score += 100
    if search_text_contains_query(query=query, text=matched_text):
        score += 50
    if symbol_exact_match:
        score += 10_000
    score += max(0, min(match_layer_rank, 9)) * 1_000
    return score


_search_type_rank = search_type_rank
_search_rank_key = search_rank_key
_score_search_item = score_search_item
