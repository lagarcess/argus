from __future__ import annotations

import re

_SEARCH_SEPARATOR_RE = re.compile(r"[\W_]+", re.UNICODE)
SEARCH_INDEXABLE_TOKEN_MIN_LENGTH = 3


def normalize_search_text(value: object) -> str:
    return " ".join(_SEARCH_SEPARATOR_RE.sub(" ", str(value).casefold()).split())


def search_has_indexable_token(value: object) -> bool:
    return any(
        len(token) >= SEARCH_INDEXABLE_TOKEN_MIN_LENGTH
        for token in normalize_search_text(value).split()
    )


def search_text_contains_query(*, query: str, text: object) -> bool:
    normalized_query = normalize_search_text(query)
    if not normalized_query:
        return False
    return normalized_query in normalize_search_text(text)


def search_text_matches_query(*, query: str, text: object) -> bool:
    normalized_query = normalize_search_text(query)
    if not normalized_query:
        return False
    normalized_text = normalize_search_text(text)
    if normalized_query in normalized_text:
        return True
    return all(token in normalized_text for token in normalized_query.split())
