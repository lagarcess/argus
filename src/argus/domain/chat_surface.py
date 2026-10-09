"""The chat a turn speaks in, read from its stored conversation.

A Business turn runs only Business-declared tools and never researches. The
turn's entry sets the surface from the conversation row (``owner_space_id``),
never from the request; code outside a turn sees Personal, which is every
pre-Business behavior. Each gate that holds a Business turn back logs once per
turn when it fires, so a refusal is visible instead of silent.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Literal

from loguru import logger

ChatSurface = Literal["personal", "business"]

SurfaceGate = Literal[
    "tool_catalog",
    "research",
    "tool_call",
    "backtest_confirmation",
    "backtest_clarification",
    "calculation",
    "asset_discovery",
    "memory_recall",
    "memory_source",
    "personal_route",
]


@dataclass
class _TurnSurface:
    surface: ChatSurface
    fired: set[SurfaceGate] = field(default_factory=set)


_ACTIVE_TURN_SURFACE: ContextVar[_TurnSurface | None] = ContextVar(
    "argus_turn_surface", default=None
)


@contextmanager
def turn_surface_scope(surface: ChatSurface) -> Iterator[None]:
    token = _ACTIVE_TURN_SURFACE.set(_TurnSurface(surface))
    try:
        yield
    finally:
        _ACTIVE_TURN_SURFACE.reset(token)


def turn_surface() -> ChatSurface:
    active = _ACTIVE_TURN_SURFACE.get()
    return "personal" if active is None else active.surface


def record_surface_gate(
    gate: SurfaceGate, *, surface: ChatSurface, **facts: object
) -> None:
    """Log that ``gate`` held a ``surface`` turn back; once per gate inside a turn."""

    active = _ACTIVE_TURN_SURFACE.get()
    if active is not None:
        if gate in active.fired:
            return
        active.fired.add(gate)
    logger.bind(surface_gate=gate, surface=surface, **facts).info(
        "Chat surface gate fired gate={} surface={}", gate, surface
    )


def surface_allows(gate: SurfaceGate) -> bool:
    """Whether this turn may use what ``gate`` reserves for Personal chats."""

    surface = turn_surface()
    if surface == "personal":
        return True
    record_surface_gate(gate, surface=surface)
    return False
