from __future__ import annotations

from argus.observability import EventCaptureResult
from argus.observability.product_events import (
    build_product_event,
    capture_product_event,
)


def test_product_event_mapping_covers_measurement_lane_set() -> None:
    cases = {
        "evidence_capture": ("storage", "completed", "evidence_capture"),
        "decision_capture": ("decision_saved", "completed", "decision_capture"),
        "recall_usage": ("tool_result", "completed", "recall"),
        "continuity_mismatch": ("recovery", "failed", "continuity"),
        "compare_started": ("compare_started", "started", "result_explanation"),
        "eval_readiness": ("eval_suite_run", "completed", "chat_interpretation"),
    }

    for kind, expected in cases.items():
        envelope = build_product_event(
            kind,
            user_id="user-1",
            conversation_id="conversation-1",
            attributes={"raw_prompt": "do not keep", "safe_count": 1},
        )

        assert (
            envelope.event_type,
            envelope.event_action,
            envelope.feature_area,
        ) == expected
        assert envelope.actor_hash is not None
        assert envelope.actor_hash != "user-1"
        assert envelope.conversation_id == "conversation-1"
        assert envelope.attributes == {"safe_count": 1, "product_event": kind}


def test_capture_product_event_uses_shared_capture_path(monkeypatch) -> None:
    captured = []

    def fake_capture(envelope):  # noqa: ANN001
        captured.append(envelope)
        return EventCaptureResult(
            status="captured",
            reason=None,
            event_id=envelope.event_id,
            destination="posthog",
        )

    monkeypatch.setattr("argus.observability.product_events.capture_event", fake_capture)

    result = capture_product_event(
        "recall_usage",
        user_id="user-1",
        conversation_id="conversation-1",
        message_id="message-1",
        status="completed",
        attributes={"result_count": 3},
    )

    assert result.status == "captured"
    assert captured
    assert captured[0].feature_area == "recall"
    assert captured[0].message_id == "message-1"
    assert captured[0].attributes == {
        "result_count": 3,
        "product_event": "recall_usage",
    }
