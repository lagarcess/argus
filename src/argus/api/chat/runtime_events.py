"""Runtime SSE event pacing: per-event timeout, keepalives, and diagnostics.

Two independent walls bound the stream: the per-event stall guard (which
resets for every event) and the accepted turn's absolute deadline (which
never resets — see argus.agent_runtime.turn_execution)."""

from __future__ import annotations

import asyncio
import math
import os
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Any

from argus.agent_runtime.turn_execution import (
    active_turn_execution,
    mark_turn_deadline_exhausted,
)

RUNTIME_EVENT_TIMEOUT_SECONDS = 120.0
RUNTIME_EVENT_KEEPALIVE_SECONDS = 15.0


class RuntimeEventTimeoutError(asyncio.TimeoutError):
    def __init__(self, diagnostics: dict[str, Any]) -> None:
        super().__init__("agent_runtime_event_timeout")
        self.diagnostics = diagnostics


def _runtime_event_timeout_seconds() -> float:
    return _positive_float_env(
        "ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS",
        RUNTIME_EVENT_TIMEOUT_SECONDS,
        min_value=1.0,
    )


def _runtime_event_keepalive_seconds() -> float:
    timeout_seconds = _runtime_event_timeout_seconds()
    return min(
        timeout_seconds,
        _positive_float_env(
            "ARGUS_RUNTIME_EVENT_KEEPALIVE_SECONDS",
            RUNTIME_EVENT_KEEPALIVE_SECONDS,
            min_value=0.1,
        ),
    )


def _positive_float_env(name: str, default: float, *, min_value: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(value, min_value)


async def _cancel_runtime_event_task(
    runtime_event_task: asyncio.Task[dict[str, Any]],
) -> None:
    runtime_event_task.cancel()
    with suppress(asyncio.CancelledError, StopAsyncIteration):
        await runtime_event_task


async def _runtime_events_with_keepalive(
    runtime_events: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[dict[str, Any] | None]:
    next_runtime_event: asyncio.Task[dict[str, Any]] | None = None
    next_runtime_event_started = time.monotonic()
    runtime_timeout_seconds = _runtime_event_timeout_seconds()
    runtime_keepalive_seconds = _runtime_event_keepalive_seconds()
    turn_context = active_turn_execution()
    last_event: dict[str, str] | None = None
    event_count = 0

    def _turn_remaining_seconds() -> float:
        if turn_context is None:
            return math.inf
        return turn_context.remaining_deadline_seconds()

    def _raise_turn_deadline_exhausted(elapsed_seconds: float) -> None:
        # The absolute turn wall: events kept arriving, but the accepted
        # turn's single monotonic deadline is spent.
        mark_turn_deadline_exhausted()
        raise RuntimeEventTimeoutError(
            {
                "code": "turn_deadline_exhausted",
                "timeout_seconds": runtime_timeout_seconds,
                "elapsed_seconds": round(elapsed_seconds, 3),
                "keepalive_seconds": runtime_keepalive_seconds,
                "event_count": event_count,
                "last_event": last_event,
            }
        ) from None

    try:
        while True:
            if next_runtime_event is None:
                next_runtime_event = asyncio.create_task(anext(runtime_events))
                next_runtime_event_started = time.monotonic()
            try:
                elapsed_seconds = time.monotonic() - next_runtime_event_started
                remaining_seconds = runtime_timeout_seconds - elapsed_seconds
                if remaining_seconds <= 0 or _turn_remaining_seconds() <= 0:
                    raise asyncio.TimeoutError
                runtime_event = await asyncio.wait_for(
                    asyncio.shield(next_runtime_event),
                    timeout=min(
                        runtime_keepalive_seconds,
                        remaining_seconds,
                        _turn_remaining_seconds(),
                    ),
                )
                next_runtime_event = None
            except asyncio.TimeoutError:
                elapsed_seconds = time.monotonic() - next_runtime_event_started
                if _turn_remaining_seconds() <= 0:
                    await _cancel_runtime_event_task(next_runtime_event)
                    next_runtime_event = None
                    _raise_turn_deadline_exhausted(elapsed_seconds)
                if elapsed_seconds >= runtime_timeout_seconds:
                    await _cancel_runtime_event_task(next_runtime_event)
                    next_runtime_event = None
                    raise RuntimeEventTimeoutError(
                        {
                            "code": "agent_runtime_event_timeout",
                            "timeout_seconds": runtime_timeout_seconds,
                            "elapsed_seconds": round(elapsed_seconds, 3),
                            "keepalive_seconds": runtime_keepalive_seconds,
                            "event_count": event_count,
                            "last_event": last_event,
                        }
                    ) from None
                yield None
                continue
            except StopAsyncIteration:
                break
            event_count += 1
            last_event = _runtime_event_boundary(runtime_event)
            yield runtime_event
    finally:
        if next_runtime_event is not None and not next_runtime_event.done():
            await _cancel_runtime_event_task(next_runtime_event)


def _runtime_event_boundary(runtime_event: dict[str, Any]) -> dict[str, str]:
    boundary = {"type": str(runtime_event.get("type") or "unknown")}
    stage = runtime_event.get("stage")
    if stage not in (None, "", [], {}):
        boundary["stage"] = str(stage)
    outcome = runtime_event.get("outcome")
    if outcome not in (None, "", [], {}):
        boundary["outcome"] = str(outcome)
    return boundary
