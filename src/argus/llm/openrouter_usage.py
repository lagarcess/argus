"""OpenRouter usage/cost payload parsing.

Pure helpers that read token counts and provider-reported spend out of
OpenRouter response payloads and LangChain message objects, and normalize them
into ledger-ready values. Kept separate from ``openrouter.py`` so the invoke
layer stays focused on request/routing and the cost slice does not grow the
routing module past its modularity budget.
"""

from __future__ import annotations


def openrouter_token_usage_from_payload(data: dict[str, object]) -> dict[str, int] | None:
    usage = data.get("usage")
    return normalize_openrouter_token_usage(usage if isinstance(usage, dict) else None)


def openrouter_usage_cost_from_payload(data: dict[str, object]) -> float | None:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return None
    return normalize_openrouter_usage_cost(usage.get("cost"))


def openrouter_token_usage_from_message(message: object) -> dict[str, int] | None:
    usage_metadata = getattr(message, "usage_metadata", None)
    normalized = normalize_openrouter_token_usage(
        usage_metadata if isinstance(usage_metadata, dict) else None
    )
    if normalized is not None:
        return normalized
    response_metadata = getattr(message, "response_metadata", None)
    if not isinstance(response_metadata, dict):
        return None
    for key in ("token_usage", "usage"):
        value = response_metadata.get(key)
        normalized = normalize_openrouter_token_usage(
            value if isinstance(value, dict) else None
        )
        if normalized is not None:
            return normalized
    return None


def merge_openrouter_token_usage(
    current: dict[str, int] | None,
    incoming: dict[str, int] | None,
) -> dict[str, int] | None:
    if current is None:
        return dict(incoming) if incoming is not None else None
    if incoming is None:
        return dict(current)
    merged = dict(current)
    for key, value in incoming.items():
        merged[key] = value
    return merged


def normalize_openrouter_token_usage(
    value: dict[str, object] | None,
) -> dict[str, int] | None:
    if not value:
        return None
    normalized: dict[str, int] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or isinstance(raw, bool):
            continue
        if key == "prompt_tokens_details" and isinstance(raw, dict):
            for detail_key in ("cached_tokens", "cache_write_tokens"):
                detail_value = raw.get(detail_key)
                if isinstance(detail_value, bool):
                    continue
                if isinstance(detail_value, int):
                    normalized[detail_key] = detail_value
                elif isinstance(detail_value, float) and detail_value.is_integer():
                    normalized[detail_key] = int(detail_value)
            continue
        if isinstance(raw, int):
            normalized[key] = raw
        elif isinstance(raw, float) and raw.is_integer():
            normalized[key] = int(raw)
    return normalized or None


def normalize_openrouter_usage_cost(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        cost = float(value)
    elif isinstance(value, str):
        try:
            cost = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if cost < 0:
        return None
    return cost
