"""A confirmation card turn's typed facts: the only form of that turn readers get.

A card turn persists no prose. Model thread history, artifact naming and the
conversation search text derive from these facts, so none of them carries the
language of the turn that produced the card.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def confirmation_turn_facts(metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Symbols, strategy type and dates of the card a message carries."""
    if not isinstance(metadata, Mapping):
        return None
    card = metadata.get("confirmation_card")
    if not isinstance(card, Mapping):
        return None
    payload = metadata.get("confirmation_payload")
    strategy = payload.get("strategy") if isinstance(payload, Mapping) else None
    if not isinstance(strategy, Mapping):
        strategy = {}
    symbols = strategy.get("asset_universe")
    strategy_type = card.get("strategy_type") or strategy.get("strategy_type")
    return {
        "strategy_type": strategy_type if isinstance(strategy_type, str) else None,
        "symbols": [symbol for symbol in symbols if isinstance(symbol, str) and symbol]
        if isinstance(symbols, list)
        else [],
        "date_range": _date_range(card.get("date_range"))
        or _date_range(strategy.get("date_range")),
    }


def confirmation_turn_history_text(facts: Mapping[str, Any]) -> str:
    """The card turn as model thread history and artifact naming read it."""
    return json.dumps({"confirmation_card": dict(facts)}, separators=(",", ":"))


def confirmation_turn_search_text(facts: Mapping[str, Any]) -> str:
    """The card turn as the conversation search index reads it."""
    date_range = facts.get("date_range") or {}
    parts = (
        *facts.get("symbols", []),
        facts.get("strategy_type"),
        date_range.get("start"),
        date_range.get("end"),
    )
    return " ".join(part for part in parts if part)


def _date_range(value: Any) -> dict[str, str] | None:
    if not (
        isinstance(value, Mapping)
        and isinstance(value.get("start"), str)
        and isinstance(value.get("end"), str)
    ):
        return None
    return {"start": value["start"], "end": value["end"]}
