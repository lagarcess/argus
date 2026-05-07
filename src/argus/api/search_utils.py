from __future__ import annotations


def search_type_rank(kind: str) -> int:
    ranks = {
        "chat": 4,
        "strategy": 3,
        "collection": 2,
        "run": 1,
    }
    return ranks.get(kind, 0)


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
    lower_title = title.lower()
    lower_matched = matched_text.lower()
    if query == lower_title:
        score += 500
    elif query in lower_title:
        score += 100
    if query in lower_matched:
        score += 50
    if symbol_exact_match:
        score += 200
    return score


_search_type_rank = search_type_rank
_score_search_item = score_search_item
