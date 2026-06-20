from __future__ import annotations

from argus.observability import (
    build_event_envelope,
    capture_event,
    live_analytics_sink_enabled,
    sanitize_observability_attributes,
)


def test_private_alpha_event_envelope_is_non_emitting_by_default() -> None:
    envelope = build_event_envelope(
        event_type="decision_saved",
        event_action="completed",
        feature_area="evidence_capture",
        conversation_id="conversation-1",
        backtest_run_id="run-1",
        status="completed",
        attributes={"decision_state": "promising"},
    )

    assert envelope.schema_version == "argus_observability_event/v1"
    assert envelope.privacy_mode == "metadata_only"
    assert envelope.event_type == "decision_saved"
    assert envelope.event_action == "completed"
    assert envelope.feature_area == "evidence_capture"
    assert envelope.conversation_id == "conversation-1"
    assert envelope.backtest_run_id == "run-1"
    assert envelope.attributes == {"decision_state": "promising"}
    assert live_analytics_sink_enabled() is False
    assert capture_event(envelope).model_dump(mode="python") == {
        "status": "suppressed",
        "reason": "p1_measurement_only",
        "event_id": envelope.event_id,
    }


def test_observability_sanitizer_blocks_sensitive_and_raw_payloads() -> None:
    sanitized = sanitize_observability_attributes(
        {
            "decision_state": "watching",
            "raw_prompt": "buy my whole account",
            "context_packets": [{"provider": "internal"}],
            "provider_metadata": {"model": "internal"},
            "account_balance": "$100,000",
            "nested": {
                "transcript": "full audio transcript",
                "safe_count": 2,
            },
            "items": [
                {"api_key": "secret", "safe": "yes"},
                "keep short text",
            ],
        }
    )

    assert sanitized == {
        "decision_state": "watching",
        "nested": {"safe_count": 2},
        "items": [{"safe": "yes"}, "keep short text"],
    }
