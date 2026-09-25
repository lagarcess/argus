from __future__ import annotations

import asyncio
import threading

import pytest
from argus.api.chat.measurement_events import (
    emit_runtime_measurement_events,
    schedule_runtime_measurement_events_after_stream,
)
from argus.observability import EventCaptureResult
from faker import Faker

fake = Faker()


def test_runtime_boundary_emits_continuity_mismatch_event(monkeypatch) -> None:
    observed: list[dict[str, object]] = []

    def fake_capture(kind: str, **kwargs: object) -> None:
        observed.append({"kind": kind, **kwargs})

    monkeypatch.setattr(
        "argus.api.chat.measurement_events.capture_product_event",
        fake_capture,
        raising=False,
    )

    emit_runtime_measurement_events(
        user_id="user-1",
        conversation_id="conversation-1",
        runtime_result={},
        metadata={
            "agent_runtime_stage_outcome": "await_approval",
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

    assert observed == [
        {
            "kind": "continuity_mismatch",
            "user_id": "user-1",
            "conversation_id": "conversation-1",
            "status": "launch_payload_symbols_mismatch",
            "attributes": {
                "failure_code": "launch_payload_symbols_mismatch",
                "stage_outcome": "await_approval",
            },
        }
    ]


def test_runtime_boundary_emits_compare_started_from_explicit_metadata(
    monkeypatch,
) -> None:
    observed: list[dict[str, object]] = []

    def fake_capture(kind: str, **kwargs: object) -> None:
        observed.append({"kind": kind, **kwargs})

    monkeypatch.setattr(
        "argus.api.chat.measurement_events.capture_product_event",
        fake_capture,
        raising=False,
    )

    emit_runtime_measurement_events(
        user_id="user-1",
        conversation_id="conversation-1",
        runtime_result={
            "comparison_started": {
                "source": "linked_version_compare",
                "candidate_count": 2,
                "baseline": "previous_version",
            }
        },
        metadata={"agent_runtime_stage_outcome": "ready_to_respond"},
    )

    assert observed == [
        {
            "kind": "compare_started",
            "user_id": "user-1",
            "conversation_id": "conversation-1",
            "status": "started",
            "attributes": {
                "source": "linked_version_compare",
                "candidate_count": 2,
                "baseline_present": True,
            },
        }
    ]


def test_runtime_boundary_captures_compare_started_after_next_experiments(
    monkeypatch,
) -> None:
    captured: list[object] = []
    user_id = fake.uuid4()
    conversation_id = fake.uuid4()
    offered_kinds = ["change_date_range", "recurring_monthly_buys"]

    def fake_capture(envelope):  # noqa: ANN001
        captured.append(envelope)
        return EventCaptureResult(
            status="captured",
            reason=None,
            event_id=envelope.event_id,
            destination="posthog",
        )

    monkeypatch.setattr(
        "argus.observability.product_events.capture_event",
        fake_capture,
    )

    emit_runtime_measurement_events(
        user_id=user_id,
        conversation_id=conversation_id,
        runtime_result={
            "comparison_started": {
                "source": "linked_version_compare",
                "candidate_count": 2,
                "baseline": "previous_version",
            }
        },
        metadata={
            "next_experiments": {
                "rows": [{"kind": kind} for kind in offered_kinds],
            }
        },
    )

    product_events = [envelope.attributes.get("product_event") for envelope in captured]
    assert product_events == ["next_experiments_offered", "compare_started"]
    assert captured[0].event_type == "system"
    assert captured[0].event_action == "completed"
    assert captured[0].feature_area == "result_explanation"
    assert captured[0].attributes["kinds"] == offered_kinds
    assert captured[0].attributes["row_count"] == len(offered_kinds)
    assert captured[1].event_type == "compare_started"
    assert captured[1].status == "started"


def test_runtime_boundary_keeps_compare_started_when_prior_capture_raises(
    monkeypatch,
) -> None:
    observed: list[dict[str, object]] = []

    def flaky_capture(kind: str, **kwargs: object) -> None:
        if kind == "next_experiments_offered":
            raise RuntimeError("forced product event failure")
        observed.append({"kind": kind, **kwargs})

    monkeypatch.setattr(
        "argus.api.chat.measurement_events.capture_product_event",
        flaky_capture,
        raising=False,
    )

    emit_runtime_measurement_events(
        user_id="user-1",
        conversation_id="conversation-1",
        runtime_result={
            "comparison_started": {
                "source": "linked_version_compare",
                "candidate_count": 1,
                "baseline": "previous_version",
            }
        },
        metadata={
            "next_experiments": {
                "rows": [{"kind": "change_date_range"}],
            }
        },
    )

    assert observed == [
        {
            "kind": "compare_started",
            "user_id": "user-1",
            "conversation_id": "conversation-1",
            "status": "started",
            "attributes": {
                "source": "linked_version_compare",
                "candidate_count": 1,
                "baseline_present": True,
            },
        }
    ]


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
