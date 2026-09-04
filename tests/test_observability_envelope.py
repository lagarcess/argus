from __future__ import annotations

import json
from typing import Any

import httpx
from argus.observability import (
    build_event_envelope,
    capture_event,
    live_analytics_sink_enabled,
    posthog_event_payload,
    sanitize_observability_attributes,
)
from argus.observability import envelope as envelope_module
from argus.observability.guest_funnel import build_guest_funnel_event
from hypothesis import given, settings
from hypothesis import strategies as st

_APPROVED_TOP_LEVEL_ATTRIBUTE_KEYS = frozenset(
    {
        "product_event",
        "language",
        "surface",
        "terminal_outcome",
        "conversion_reason",
        "strategy_category",
        "product_capability",
        "capability_class",
    }
)
_SCALAR_ATTRIBUTE_VALUES = st.one_of(
    st.text(max_size=40),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
)


def _posthog_properties(attributes: dict[str, Any]) -> dict[str, Any]:
    envelope = build_event_envelope(
        event_type="tool_result",
        event_action="completed",
        feature_area="guest_acquisition",
        attributes=attributes,
    )
    payload = posthog_event_payload(envelope, api_key="ph_project_token")
    properties = payload["properties"]
    assert isinstance(properties, dict)
    return properties


def test_posthog_top_level_attribute_allowlist_is_closed() -> None:
    assert envelope_module._POSTHOG_TOP_LEVEL_ATTRIBUTE_ALLOWLIST == (
        _APPROVED_TOP_LEVEL_ATTRIBUTE_KEYS
    )


def test_product_capability_has_an_unambiguous_native_filter_name() -> None:
    envelope = build_guest_funnel_event(
        "guest_limit_reached", user_id=None, product_capability="chat"
    )
    properties = posthog_event_payload(envelope, api_key="test-project-token")[
        "properties"
    ]
    assert properties["product_capability"] == "chat"
    assert "capability_category" not in properties["attributes"]
    assert "capability_class" not in properties


def test_private_alpha_event_envelope_is_non_emitting_by_default(monkeypatch) -> None:
    monkeypatch.delenv("POSTHOG_PROJECT_TOKEN", raising=False)
    monkeypatch.delenv("POSTHOG_REGION", raising=False)
    monkeypatch.delenv("POSTHOG_HOST", raising=False)
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
        "reason": "posthog_not_configured",
        "event_id": envelope.event_id,
        "destination": None,
    }


def test_posthog_capture_requires_explicit_region_or_host(monkeypatch) -> None:
    monkeypatch.setenv("POSTHOG_PROJECT_TOKEN", "ph_project_token")
    monkeypatch.delenv("POSTHOG_REGION", raising=False)
    monkeypatch.delenv("POSTHOG_HOST", raising=False)
    envelope = build_event_envelope(
        event_type="tool_result",
        event_action="completed",
        feature_area="recall",
    )

    assert live_analytics_sink_enabled() is False
    assert capture_event(envelope).model_dump(mode="python") == {
        "status": "suppressed",
        "reason": "posthog_region_not_configured",
        "event_id": envelope.event_id,
        "destination": None,
    }


def test_posthog_capture_uses_metadata_only_personless_server_event(monkeypatch) -> None:
    sent: list[tuple[str, dict[str, object], float]] = []

    def fake_post(url: str, *, json: dict[str, object], timeout: float) -> httpx.Response:
        sent.append((url, json, timeout))
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setenv("POSTHOG_PROJECT_TOKEN", "ph_project_token")
    monkeypatch.setenv("POSTHOG_REGION", "US Cloud")
    monkeypatch.delenv("POSTHOG_HOST", raising=False)
    monkeypatch.setenv("APP_ENV", "private-alpha")
    monkeypatch.setattr("argus.observability.envelope.httpx.post", fake_post)

    envelope = build_event_envelope(
        event_type="decision_saved",
        event_action="completed",
        feature_area="decision_capture",
        actor_hash="actor_hash_1",
        conversation_id="conversation-raw-id",
        backtest_run_id="run-raw-id",
        route_receipt_id="route-receipt-raw-id",
        provider="openrouter",
        model="internal-model",
        provider_request_id="provider-request-raw-id",
        status="promising",
        attributes={
            "decision_state": "promising",
            "raw_prompt": "buy my whole account",
            "account_balance": "$100,000",
            "safe_count": 2,
        },
    )

    result = capture_event(envelope)

    assert result.model_dump(mode="python") == {
        "status": "captured",
        "reason": None,
        "event_id": envelope.event_id,
        "destination": "posthog",
    }
    assert sent
    url, body, timeout = sent[0]
    assert url == "https://us.i.posthog.com/i/v0/e/"
    assert timeout == 0.75
    assert body["api_key"] == "ph_project_token"
    assert body["event"] == "decision_saved"
    assert body["distinct_id"] == "actor_hash_1"
    properties = body["properties"]
    assert isinstance(properties, dict)
    assert properties["$process_person_profile"] is False
    assert properties["schema_version"] == "argus_observability_event/v1"
    assert properties["privacy_mode"] == "metadata_only"
    assert properties["environment"] == "private-alpha"
    assert properties["event_type"] == "decision_saved"
    assert properties["event_action"] == "completed"
    assert properties["feature_area"] == "decision_capture"
    assert properties["conversation_id_hash"]
    assert properties["backtest_run_id_hash"]
    assert properties["attributes"] == {
        "decision_state": "promising",
        "safe_count": 2,
    }
    assert "conversation-raw-id" not in str(properties)
    assert "run-raw-id" not in str(properties)
    assert "route-receipt-raw-id" not in str(properties)
    assert "provider-request-raw-id" not in str(properties)
    assert "openrouter" not in str(properties)
    assert "internal-model" not in str(properties)
    assert "buy my whole account" not in str(properties)
    assert "$100,000" not in str(properties)


def test_posthog_event_payload_is_data_minimizing_without_network() -> None:
    envelope = build_event_envelope(
        event_type="tool_result",
        event_action="completed",
        feature_area="recall",
        conversation_id="conversation-raw-id",
        message_id="message-raw-id",
        attributes={"query_present": True, "result_count": 3},
    )

    payload = posthog_event_payload(envelope, api_key="ph_project_token")

    assert payload["api_key"] == "ph_project_token"
    assert payload["event"] == "tool_result"
    assert payload["distinct_id"] == envelope.event_id
    assert payload["properties"]["$process_person_profile"] is False
    assert payload["properties"]["conversation_id_hash"]
    assert payload["properties"]["message_id_hash"]
    assert "conversation-raw-id" not in str(payload)
    assert "message-raw-id" not in str(payload)


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


@settings(max_examples=100, deadline=None)
@given(
    attributes=st.dictionaries(
        keys=st.one_of(
            st.sampled_from(sorted(_APPROVED_TOP_LEVEL_ATTRIBUTE_KEYS)),
            st.text(min_size=1, max_size=24),
        ),
        values=_SCALAR_ATTRIBUTE_VALUES,
        max_size=20,
    )
)
def test_posthog_projection_matches_allowlist_intersection_for_scalar_attributes(
    attributes: dict[str, str | int | float | bool],
) -> None:
    envelope = build_event_envelope(
        event_type="tool_result",
        event_action="completed",
        feature_area="guest_acquisition",
        attributes=attributes,
    )
    payload = posthog_event_payload(envelope, api_key="ph_project_token")
    properties = payload["properties"]
    assert isinstance(properties, dict)

    expected = _APPROVED_TOP_LEVEL_ATTRIBUTE_KEYS & envelope.attributes.keys()
    preexisting_top_level_keys = set(_posthog_properties({})) | {"attributes"}
    promoted = (set(properties) - preexisting_top_level_keys) & envelope.attributes.keys()

    assert promoted == expected
    for key in promoted:
        assert properties[key] == envelope.attributes[key]


def test_posthog_projection_promotes_only_the_approved_categorical_dimensions() -> None:
    attributes = {
        "product_event": "first_result_completed",
        "language": "en",
        "surface": "chat",
        "terminal_outcome": "completed",
        "conversion_reason": "first_result",
        "strategy_category": "dca",
        "product_capability": "simulation",
        "capability_class": "balanced_lookup",
        "safe_count": 2,
    }

    properties = _posthog_properties(attributes)

    assert {
        key: properties[key]
        for key in _APPROVED_TOP_LEVEL_ATTRIBUTE_KEYS
        if key in properties
    } == {key: attributes[key] for key in _APPROVED_TOP_LEVEL_ATTRIBUTE_KEYS}
    assert "safe_count" not in properties


def test_posthog_projection_never_promotes_nested_allowlisted_values() -> None:
    properties = _posthog_properties(
        {
            "product_event": ["first_result_completed"],
            "language": {"code": "en"},
            "surface": ["chat"],
            "terminal_outcome": "completed",
        }
    )

    assert "product_event" not in properties
    assert "language" not in properties
    assert "surface" not in properties
    assert properties["terminal_outcome"] == "completed"
    assert properties["attributes"] == {
        "product_event": ["first_result_completed"],
        "language": {"code": "en"},
        "surface": ["chat"],
        "terminal_outcome": "completed",
    }


def test_posthog_projection_preserves_existing_top_level_property_on_collision(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        envelope_module,
        "_POSTHOG_TOP_LEVEL_ATTRIBUTE_ALLOWLIST",
        frozenset({"product_event", "status"}),
        raising=False,
    )
    envelope = build_event_envelope(
        event_type="tool_result",
        event_action="completed",
        feature_area="guest_acquisition",
        status="completed",
        attributes={"product_event": "first_result_completed", "status": "ignored"},
    )
    payload = posthog_event_payload(envelope, api_key="ph_project_token")
    properties = payload["properties"]
    assert isinstance(properties, dict)

    assert properties["product_event"] == "first_result_completed"
    assert properties["status"] == "completed"
    assert properties["attributes"]["status"] == "ignored"


def test_posthog_projection_keeps_sanitized_attributes_byte_identical() -> None:
    envelope = build_event_envelope(
        event_type="tool_result",
        event_action="completed",
        feature_area="guest_acquisition",
        attributes={
            "product_event": "first_result_completed",
            "language": "en",
            "safe_count": 2,
            "nested": {"safe": "value"},
        },
    )
    payload = posthog_event_payload(envelope, api_key="ph_project_token")
    properties = payload["properties"]
    assert isinstance(properties, dict)

    assert json.dumps(
        properties["attributes"], sort_keys=True, separators=(",", ":")
    ) == json.dumps(envelope.attributes, sort_keys=True, separators=(",", ":"))


def test_posthog_projection_keeps_sensitive_values_and_raw_identifiers_out() -> None:
    raw_conversation_id = "conversation-raw-id"
    envelope = build_event_envelope(
        event_type="tool_result",
        event_action="completed",
        feature_area="guest_acquisition",
        conversation_id=raw_conversation_id,
        attributes={
            "product_event": "first_result_completed",
            "raw_prompt": "buy all of my account",
            "assistant_prose": "private message text",
            "account_balance": "$100,000",
            "api_key": "credential-secret",
        },
    )
    payload = posthog_event_payload(envelope, api_key="ph_project_token")
    properties = payload["properties"]
    assert isinstance(properties, dict)

    assert properties["product_event"] == "first_result_completed"
    assert properties["conversation_id_hash"]
    assert properties["attributes"] == {
        "product_event": "first_result_completed",
    }
    for blocked_value in (
        raw_conversation_id,
        "buy all of my account",
        "private message text",
        "$100,000",
        "credential-secret",
    ):
        assert blocked_value not in str(properties)
