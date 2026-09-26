from __future__ import annotations

import asyncio
import threading

import pytest
from argus.api.chat.measurement_events import (
    emit_runtime_measurement_events,
    schedule_runtime_measurement_events_after_stream,
)
from faker import Faker

fake = Faker()


def test_runtime_boundary_sends_no_retired_product_event(monkeypatch) -> None:
    """Continuity mismatch, next experiments offered, and compare started were
    retired from PostHog by SPEC 0 package 0C-1; the runtime boundary sends none."""
    posts: list[object] = []
    monkeypatch.setenv("POSTHOG_PROJECT_TOKEN", "ph_project_token")
    monkeypatch.setenv("POSTHOG_REGION", "us")
    monkeypatch.setattr(
        "argus.observability.envelope.httpx.post",
        lambda *args, **kwargs: posts.append((args, kwargs)),
    )

    emit_runtime_measurement_events(
        user_id=fake.uuid4(),
        conversation_id=fake.uuid4(),
        runtime_result={
            "comparison_started": {
                "source": "linked_version_compare",
                "candidate_count": 2,
                "baseline": "previous_version",
            }
        },
        metadata={
            "agent_runtime_stage_outcome": "await_approval",
            "next_experiments": {"rows": [{"kind": "change_date_range"}]},
            "active_confirmation_reference": {
                "metadata": {
                    "validation": {
                        "executable": False,
                        "failure_code": "launch_payload_symbols_mismatch",
                    }
                }
            },
        },
    )

    assert posts == []


@pytest.mark.asyncio
async def test_runtime_measurement_scheduler_runs_after_terminal_frames(
    monkeypatch,
) -> None:
    observed: list[str] = []
    emitted = threading.Event()

    def fake_emit(**_: object) -> None:
        observed.append("capture")
        emitted.set()

    monkeypatch.setattr(
        "argus.api.chat.measurement_events.emit_runtime_measurement_events",
        fake_emit,
    )

    observed.extend(["final", "done"])
    schedule_runtime_measurement_events_after_stream(
        user_id="user-1",
        conversation_id="conversation-1",
        runtime_result={},
        metadata={},
    )

    assert observed == ["final", "done"]
    assert await asyncio.to_thread(emitted.wait, 1)
    assert observed == ["final", "done", "capture"]
