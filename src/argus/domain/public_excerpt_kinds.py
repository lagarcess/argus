"""Public document classification requires no owner or source access."""

from typing import Any


def document_kind(payload: Any) -> str:
    if payload.schema_version == 1:
        return "backtest"
    if not hasattr(payload, "turns"):
        return "tool_result"
    kinds = {turn.kind for turn in payload.turns}
    return next(iter(kinds)) if len(kinds) == 1 else "mixed"
