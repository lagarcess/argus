from __future__ import annotations

import re

_SEARCH_SEPARATOR_RE = re.compile(r"[\W_]+", re.UNICODE)
SEARCH_INDEXABLE_TOKEN_MIN_LENGTH = 3
SEARCH_SYMBOL_QUERY_MIN_LENGTH = 2


def normalize_search_text(value: object) -> str:
    return " ".join(_SEARCH_SEPARATOR_RE.sub(" ", str(value).casefold()).split())


def search_has_indexable_token(value: object) -> bool:
    return any(
        len(token) >= SEARCH_INDEXABLE_TOKEN_MIN_LENGTH
        for token in normalize_search_text(value).split()
    )


def normalize_search_symbol(value: object) -> str | None:
    """Normalize one canonical symbol without discarding its punctuation."""
    symbol = str(value).strip()
    if not symbol or any(character.isspace() for character in symbol):
        return None
    return symbol.casefold()


def search_query_is_indexable(value: object) -> bool:
    if search_has_indexable_token(value):
        return True
    symbol = normalize_search_symbol(value)
    return (
        symbol is not None
        and "\x00" not in symbol
        and len(symbol) >= SEARCH_SYMBOL_QUERY_MIN_LENGTH
        and any(character.isalnum() for character in symbol)
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
