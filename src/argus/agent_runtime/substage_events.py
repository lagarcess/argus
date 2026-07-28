"""Sub-stage progress events from inside a running workflow stage.

LangGraph surfaces node-level starts only; work inside a node (the discovery
composer's search and verify) has no event of its own. Stages push here and
the runtime merges the queue into the client stream as the work happens,
bypassing the node-name filter and the per-node dedupe.

The binding must happen inside the task that drives the workflow: contextvar
tokens cannot be reset across asyncio contexts, and generator frames may be
driven from more than one.
"""

from __future__ import annotations

import asyncio
import contextvars
from typing import Any

MergeItem = tuple[str, Any]

_substage_queue: contextvars.ContextVar[asyncio.Queue[MergeItem] | None] = (
    contextvars.ContextVar("argus_substage_queue", default=None)
)


def bind_substage_channel(queue: asyncio.Queue[MergeItem]) -> contextvars.Token:
    """Bind for the current task and everything it starts afterwards."""
    return _substage_queue.set(queue)


def close_substage_channel(token: contextvars.Token) -> None:
    """Reset in the same task that bound; the binding dies with its context."""
    _substage_queue.reset(token)


def emit_substage(stage: str, detail: str | None = None) -> None:
    """No-op outside a bound channel, so stages never need to know the caller."""
    queue = _substage_queue.get()
    if queue is None:
        return
    payload: dict[str, str] = {"stage": stage}
    if detail:
        payload["detail"] = detail
    queue.put_nowait(("substage", payload))
