"""§9 Slice B channel: sub-stage events reach the stream while the node runs.

The merge is the point — a design that only drains sub-stage events when the
next LangGraph event arrives would deliver both progress lines together at
the end, which is the dishonesty the slice removes. The workflow below blocks
after emitting until the consumer has observed the event, so a non-live merge
fails this suite by timeout instead of passing quietly.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from argus.agent_runtime.runtime import stream_agent_turn_events
from argus.agent_runtime.state.models import UserState
from argus.agent_runtime.substage_events import (
    bind_substage_channel,
    close_substage_channel,
    emit_substage,
)


class _SubStageWorkflow:
    """Emits sub-stage events from inside a running node, like the composer."""

    def __init__(self, release: asyncio.Event) -> None:
        self._release = release

    async def astream_events(self, initial_state, *, config, version):
        yield {"event": "on_chain_start", "name": "interpret", "metadata": {}}
        emit_substage("discovery_search", detail="cybersecurity stocks")
        # Block until the consumer has seen the event: proves live delivery.
        await asyncio.wait_for(self._release.wait(), timeout=2)
        emit_substage("discovery_verify")
        emit_substage("discovery_verify")
        yield {
            "event": "on_chain_end",
            "name": "interpret",
            "data": {"output": {"stage_outcome": "end_run"}},
        }

    async def aget_state(self, config):
        return SimpleNamespace(
            values={"stage_outcome": "end_run", "assistant_response": "done"}
        )


@pytest.mark.asyncio()
async def test_substage_events_stream_while_the_node_is_still_running() -> None:
    release = asyncio.Event()
    events = []
    async for event in stream_agent_turn_events(
        workflow=_SubStageWorkflow(release),
        user=UserState(user_id="user-1"),
        thread_id="thread-1",
        message="what cybersecurity stocks could I test?",
    ):
        events.append(event)
        if (
            event.get("type") == "stage_start"
            and event.get("stage") == "discovery_search"
        ):
            release.set()

    assert [
        (event["type"], event.get("stage"), event.get("detail"))
        for event in events
        if event["type"] == "stage_start"
    ] == [
        ("stage_start", "interpret", None),
        ("stage_start", "discovery_search", "cybersecurity stocks"),
        # Sub-stage events bypass the node-name filter and the dedupe set:
        # the stage is no workflow node, and the repeat is not swallowed.
        ("stage_start", "discovery_verify", None),
        ("stage_start", "discovery_verify", None),
    ]
    assert events[-1]["type"] == "final"
    assert events[-1]["payload"]["assistant_response"] == "done"


@pytest.mark.asyncio()
async def test_closed_channel_drops_events_instead_of_leaking() -> None:
    queue: asyncio.Queue = asyncio.Queue()
    token = bind_substage_channel(queue)
    emit_substage("discovery_search")
    close_substage_channel(token)
    emit_substage("discovery_verify")
    assert queue.qsize() == 1


@pytest.mark.asyncio()
async def test_emit_without_a_channel_is_a_no_op() -> None:
    emit_substage("discovery_search", detail="anything")
