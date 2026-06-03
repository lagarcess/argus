from __future__ import annotations

import calendar
from datetime import date

from argus.agent_runtime.strategy_contract import (
    MONTH_ALIASES,
    parse_relative_date_token,
)
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES

MONTH_TOKENS = frozenset(MONTH_ALIASES)


def current_message_dca_cadence(message: str) -> str | None:
    """Return a user-stated DCA cadence using the strategy capability contract."""

    tokens = field_fidelity_tokens(str(message or "").casefold())
    if not tokens:
        return None
    capability = STRATEGY_CAPABILITIES.get("dca_accumulation")
    cadence_spec = capability.parameters.get("dca_cadence") if capability else None
    if cadence_spec is None:
        return None
    for cadence in cadence_spec.allowed_values:
        normalized = str(cadence).strip().casefold()
        if not normalized:
            continue
        aliases = [normalized, *cadence_spec.value_aliases.get(normalized, [])]
        for alias in aliases:
            alias_tokens = field_fidelity_tokens(str(alias).casefold())
            if alias_tokens and _contains_ordered_token_span(tokens, alias_tokens):
                return normalized
    return None


def current_message_execution_context_tokens(
    message: str,
    *,
    strategy_type: str | None,
) -> set[str]:
    """Return tokens consumed by strategy capability fields in the current turn."""

    tokens = field_fidelity_tokens(str(message or "").casefold())
    if not tokens:
        return set()
    capability = STRATEGY_CAPABILITIES.get(str(strategy_type or "").strip())
    if capability is None:
        return set()

    matched_tokens: set[str] = set()
    for parameter in capability.parameters.values():
        alias_phrases: list[str] = []
        for value in parameter.allowed_values:
            normalized = str(value).strip().casefold()
            if not normalized:
                continue
            alias_phrases.append(normalized)
            alias_phrases.extend(
                str(alias).strip().casefold()
                for alias in parameter.value_aliases.get(normalized, [])
                if str(alias).strip()
            )
        for alias in alias_phrases:
            alias_tokens = field_fidelity_tokens(alias)
            if alias_tokens and _contains_ordered_token_span(tokens, alias_tokens):
                matched_tokens.update(alias_tokens)
    return matched_tokens


def _contains_ordered_token_span(tokens: list[str], span: list[str]) -> bool:
    if len(span) > len(tokens):
        return False
    last_start = len(tokens) - len(span)
    for start in range(last_start + 1):
        if tokens[start : start + len(span)] == span:
            return True
    return False


def current_message_date_range(
    message: str,
    *,
    today: date | None = None,
) -> dict[str, str] | None:
    folded_message = str(message or "").casefold()
    tokens = field_fidelity_tokens(folded_message)
    current_date = today or date.today()
    month_year = _month_year_date_range_from_tokens(
        _date_range_fidelity_tokens(folded_message)
    )
    if month_year is not None:
        return month_year
    multi_year = _multi_year_date_range_from_tokens(tokens, today=current_date)
    if multi_year is not None:
        return multi_year
    year_so_far = _year_so_far_date_range_from_tokens(tokens, today=current_date)
    if year_so_far is not None:
        return year_so_far
    start_endpoint = _date_endpoint_from_marker_tokens(
        tokens,
        markers={"start", "starting", "beginning"},
        endpoint="start",
    )
    end_endpoint = _date_endpoint_from_marker_tokens(
        tokens,
        markers={"end", "ending"},
        endpoint="end",
    )
    if start_endpoint is not None and end_endpoint is not None:
        return {"start": start_endpoint, "end": end_endpoint}
    if start_endpoint is not None and not _tokens_after_year_include_date_endpoint(
        tokens,
        endpoint=start_endpoint,
    ):
        return {"start": start_endpoint}
    if end_endpoint is not None:
        return {"end": end_endpoint}
    relative_endpoint = _relative_date_endpoint_from_marker_tokens(
        tokens,
        today=current_date,
    )
    if relative_endpoint is not None:
        return relative_endpoint
    calendar_year = _calendar_year_date_range_from_tokens(tokens, today=current_date)
    if calendar_year is not None:
        return calendar_year
    return None


def field_fidelity_tokens(text: str) -> list[str]:
    separators = ",.;:!?()[]{}"
    cleaned = text
    for separator in separators:
        cleaned = cleaned.replace(separator, " ")
    return [token for token in cleaned.split() if token]


def _date_range_fidelity_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in text:
        if char.isalnum():
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def message_states_bar_timeframe(message: str) -> bool:
    tokens = set(field_fidelity_tokens(str(message or "").casefold()))
    return bool(
        tokens
        & {
            "bar",
            "bars",
            "candle",
            "candles",
            "daily",
            "hour",
            "hourly",
            "intraday",
            "minute",
            "minutes",
            "1d",
            "1h",
            "4h",
        }
    )


def _year_so_far_date_range_from_tokens(
    tokens: list[str],
    *,
    today: date,
) -> dict[str, str] | None:
    if not ({"so", "far"} <= set(tokens)):
        return None
    if {"this", "year"} <= set(tokens):
        return {"start": f"{today.year}-01-01", "end": today.isoformat()}
    for token in tokens:
        if not (len(token) == 4 and token.isdigit()):
            continue
        year = int(token)
        if year == today.year:
            return {"start": f"{year}-01-01", "end": today.isoformat()}
    return None


def _month_year_date_range_from_tokens(tokens: list[str]) -> dict[str, str] | None:
    connectors = {"to", "through", "thru", "until", "till"}
    for index in range(0, len(tokens)):
        start = _month_year_endpoint(tokens, index=index, endpoint="start")
        if start is None:
            continue
        end_index = index + 2
        if end_index < len(tokens) and tokens[end_index] in connectors:
            end_index += 1
        end = _month_year_endpoint(tokens, index=end_index, endpoint="end")
        if end is None or end < start:
            continue
        return {"start": start.isoformat(), "end": end.isoformat()}
    return None


def _month_year_endpoint(
    tokens: list[str],
    *,
    index: int,
    endpoint: str,
) -> date | None:
    if index < 0 or index + 1 >= len(tokens):
        return None
    month = MONTH_ALIASES.get(tokens[index])
    year_text = tokens[index + 1]
    if month is None or not (len(year_text) == 4 and year_text.isdigit()):
        return None
    year = int(year_text)
    if not 1900 <= year <= 2100:
        return None
    day = 1 if endpoint == "start" else calendar.monthrange(year, month)[1]
    return date(year, month, day)


def _multi_year_date_range_from_tokens(
    tokens: list[str],
    *,
    today: date,
) -> dict[str, str] | None:
    if set(tokens) & MONTH_TOKENS:
        return None
    years: list[int] = []
    for token in tokens:
        if not (len(token) == 4 and token.isdigit()):
            continue
        year = int(token)
        if 1900 <= year <= today.year and year not in years:
            years.append(year)
    if len(years) != 2:
        return None
    if not (
        set(tokens)
        & {
            "and",
            "to",
            "through",
            "thru",
            "until",
            "till",
            "from",
            "between",
            "over",
            "during",
        }
    ):
        return None
    start_year, end_year = years
    if end_year < start_year:
        return None
    if end_year == today.year and (
        {"so", "far"} <= set(tokens)
        or set(tokens) & {"today", "now", "present", "current"}
    ):
        end = today.isoformat()
    else:
        end = date(end_year, 12, 31).isoformat()
    return {"start": date(start_year, 1, 1).isoformat(), "end": end}


def _calendar_year_date_range_from_tokens(
    tokens: list[str],
    *,
    today: date,
) -> dict[str, str] | None:
    if set(tokens) & MONTH_TOKENS:
        return None
    year_tokens = [
        token
        for token in tokens
        if len(token) == 4 and token.isdigit() and 1900 <= int(token) <= today.year
    ]
    if len(set(year_tokens)) != 1:
        return None
    for index, token in enumerate(tokens):
        if not (len(token) == 4 and token.isdigit()):
            continue
        year = int(token)
        if year < 1900 or year > today.year:
            continue
        previous = tokens[index - 1] if index > 0 else ""
        if len(tokens) == 1 or previous in {
            "in",
            "during",
            "throughout",
            "for",
            "over",
        }:
            return {"start": f"{year}-01-01", "end": f"{year}-12-31"}
    return None


def _date_endpoint_from_marker_tokens(
    tokens: list[str],
    *,
    markers: set[str],
    endpoint: str,
) -> str | None:
    for index, token in enumerate(tokens):
        if token not in markers:
            continue
        year_index = _first_year_token_index(tokens, start=index + 1, limit=index + 5)
        if year_index is None:
            continue
        year = int(tokens[year_index])
        if endpoint == "end":
            return date(year, 12, 31).isoformat()
        return date(year, 1, 1).isoformat()
    return None


def _relative_date_endpoint_from_marker_tokens(
    tokens: list[str],
    *,
    today: date,
) -> dict[str, str] | None:
    endpoint_markers = (
        ({"start", "starting", "beginning", "from"}, "start"),
        ({"end", "ending", "through", "thru", "until", "till"}, "end"),
    )
    for markers, endpoint in endpoint_markers:
        for index, token in enumerate(tokens):
            if token not in markers:
                continue
            relative_date = _relative_date_token_after_marker(
                tokens,
                start=index + 1,
                limit=index + 5,
                today=today,
            )
            if relative_date is not None:
                return {endpoint: relative_date.isoformat()}
    return None


def _relative_date_token_after_marker(
    tokens: list[str],
    *,
    start: int,
    limit: int,
    today: date,
) -> date | None:
    for index in range(max(start, 0), min(limit, len(tokens))):
        token = tokens[index]
        parsed = parse_relative_date_token(token, today=today)
        if parsed is not None:
            return parsed
    return None


def _first_year_token_index(
    tokens: list[str],
    *,
    start: int,
    limit: int,
) -> int | None:
    for index in range(max(start, 0), min(limit, len(tokens))):
        token = tokens[index]
        if len(token) != 4 or not token.isdigit():
            continue
        year = int(token)
        if 1900 <= year <= 2100:
            return index
    return None


def _tokens_after_year_include_date_endpoint(
    tokens: list[str],
    *,
    endpoint: str,
) -> bool:
    year = endpoint.split("-", 1)[0]
    try:
        index = tokens.index(year)
    except ValueError:
        return False
    endpoint_tokens = {
        "to",
        "through",
        "until",
        "till",
        "end",
        "ending",
        "today",
        "now",
        "present",
        "current",
    }
    return any(token in endpoint_tokens for token in tokens[index + 1 :])
