from __future__ import annotations

from argus.api.chat.measurement_events import emit_runtime_measurement_events


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
