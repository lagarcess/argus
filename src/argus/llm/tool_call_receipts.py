"""Private call identity attached to existing provider receipts."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_CALL_SCOPE: ContextVar[dict[str, object] | None] = ContextVar(
    "openrouter_tool_call_receipt_scope", default=None
)


def current_tool_call_receipt_scope() -> dict[str, object]:
    return dict(_CALL_SCOPE.get() or {})


def _identity(value: str) -> str:
    if value and len(value) <= 128 and all(
        character.isascii() and (character.isalnum() or character in "_-.:/")
        for character in value
    ):
        return value
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@contextmanager
def tool_call_receipt_scope(*, call_id: str, tool_name: str) -> Iterator[None]:
    token = _CALL_SCOPE.set(
        {"tool_call_id": _identity(call_id), "tool_name": _identity(tool_name)}
    )
    try:
        yield
    finally:
        _CALL_SCOPE.reset(token)
