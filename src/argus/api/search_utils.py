from __future__ import annotations

from datetime import datetime

from argus.domain.search_text import normalize_search_text, search_text_contains_query


def search_type_rank(kind: str) -> int:
    ranks = {
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
) -> tuple[int, int, int, int, datetime, int, str]:
    pinned_rank, exact_rank, symbol_rank, text_rank = _score_rank_parts(score)
    return (
        pinned_rank,
        exact_rank,
        symbol_rank,
        search_type_rank(kind),
        updated_at,
        text_rank,
        item_id,
    )


def _score_rank_parts(score: int) -> tuple[int, int, int, int]:
    remainder = score
    pinned_rank = int(remainder >= 1000)
    if pinned_rank:
        remainder -= 1000
    exact_rank = int(remainder >= 500)
    if exact_rank:
        remainder -= 500
    symbol_rank = int(remainder >= 200)
    if symbol_rank:
        remainder -= 200
    return pinned_rank, exact_rank, symbol_rank, remainder


def score_search_item(
    *,
    query: str,
    title: str,
    matched_text: str,
    pinned: bool,
    symbol_exact_match: bool = False,
) -> int:
    score = 0
    if pinned:
        score += 1000
    normalized_query = normalize_search_text(query)
    normalized_title = normalize_search_text(title)
    if normalized_query == normalized_title:
        score += 500
    elif search_text_contains_query(query=query, text=title):
        score += 100
    if search_text_contains_query(query=query, text=matched_text):
        score += 50
    if symbol_exact_match:
        score += 200
    return score


_search_type_rank = search_type_rank
_search_rank_key = search_rank_key
_score_search_item = score_search_item
