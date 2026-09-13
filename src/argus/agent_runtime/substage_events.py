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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from argus.domain.tool_contracts import ToolProgress

MergeItem = tuple[str, Any]


@dataclass
class _SubstageChannel:
    queue: asyncio.Queue[MergeItem]
    loop: asyncio.AbstractEventLoop
    active: bool = True


_substage_queue: contextvars.ContextVar[_SubstageChannel | None] = contextvars.ContextVar(
    "argus_substage_queue", default=None
)


def bind_substage_channel(
    queue: asyncio.Queue[MergeItem],
) -> contextvars.Token[_SubstageChannel | None]:
    """Bind for the current task and everything it starts afterwards."""
    return _substage_queue.set(_SubstageChannel(queue, asyncio.get_running_loop()))


def close_substage_channel(token: contextvars.Token[_SubstageChannel | None]) -> None:
    """Reset in the same task that bound; the binding dies with its context."""
    channel = _substage_queue.get()
    if channel is not None:
        channel.active = False
    _substage_queue.reset(token)


def emit_substage(stage: str, detail: str | None = None) -> None:
    """No-op outside a bound channel, so stages never need to know the caller."""
    payload: dict[str, str] = {"stage": stage}
    if detail:
        payload["detail"] = detail
    _emit(payload)


def emit_tool_progress(progress: ToolProgress) -> None:
    """Publish declared facts only when the corresponding callable is invoked."""
    _emit({"stage": "execute", "tool_progress": progress.model_dump(mode="json")})


def _emit(payload: dict[str, Any]) -> None:
    channel = _substage_queue.get()
    if channel is None or not channel.active:
        return
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None
    item = ("substage", payload)
    if current_loop is channel.loop:
        channel.queue.put_nowait(item)
    else:
        # Sync backtest handlers run in a worker thread. Queue.put_nowait is
        # not thread-safe and cannot wake an awaiting SSE consumer by itself.
        channel.loop.call_soon_threadsafe(channel.queue.put_nowait, item)
