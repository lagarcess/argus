"""Research settlement must reach native PostHog filters, including failures."""

from __future__ import annotations

import asyncio
from threading import Event
from typing import Any, get_args

import httpx
import pytest
from argus.agent_runtime.research_grounded import build_research_sidecar
from argus.api import state as api_state
from argus.api.chat.research_evidence import record_research_turn_evidence
from argus.domain.research.contracts import CapabilityClass
from argus.observability import envelope as envelope_module


@pytest.fixture
def capture_payloads(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    monkeypatch.setenv("POSTHOG_PROJECT_TOKEN", "test-project-token")
    monkeypatch.setenv("POSTHOG_REGION", "us")
    monkeypatch.delenv("POSTHOG_HOST", raising=False)
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setattr(api_state.store, "usage_counters", {})

    def post(url: str, *, json: dict[str, Any], timeout: float) -> httpx.Response:
        payloads.append(json)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(envelope_module.httpx, "post", post)
    return payloads


@pytest.mark.parametrize("capability_class", get_args(CapabilityClass))
@pytest.mark.parametrize("cache_status", ["miss", "hit", "bypass"])
@pytest.mark.parametrize("degraded_code", [None, "research_unavailable"])
def test_settlement_projects_research_work_and_outcome_without_private_data(
    capability_class: CapabilityClass,
    cache_status: str,
    degraded_code: str | None,
    capture_payloads: list[dict[str, Any]],
    faker: Any,
) -> None:
    private_text = faker.sentence()
    research = build_research_sidecar(
        capability_class=capability_class,
        shape="balanced",
        sources=[{"title": private_text, "url": faker.url()}],
        retrieved_at=faker.iso8601(),
        subjects=[{"symbol": "SPY", "name": private_text}],
        peers=[],
        usage={"cache_status": cache_status, "cost_usd": 0.005, "latency_ms": 640},
        period_of_interest=None,
        degraded_code=degraded_code,
    )
    user_id, conversation_id, message_id, request_id = [faker.uuid4() for _ in range(4)]
    record_research_turn_evidence(
        research=research,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )

    assert len(capture_payloads) == 1
    payload = capture_payloads[0]
    assert payload["event"] == "research"
    properties = payload["properties"]
    assert properties["capability_class"] == capability_class
    assert properties["event_action"] == ("failed" if degraded_code else "completed")
    assert properties["status"] == ("degraded" if degraded_code else "completed")
    assert properties["$process_person_profile"] is False
    assert properties["attributes"] == {
        "capability_class": capability_class,
        "cache_status": cache_status,
    }
    assert set(properties) == {
        "$process_person_profile",
        "schema_version",
        "event_id",
        "occurred_at",
        "environment",
        "privacy_mode",
        "event_type",
        "event_action",
        "feature_area",
        "actor_hash",
        "conversation_id_hash",
        "message_id_hash",
        "status",
        "capability_class",
        "attributes",
    }
    for raw in (private_text, user_id, conversation_id, message_id, request_id):
        assert raw not in str(payload)


def test_non_research_settlement_does_not_emit(capture_payloads, faker) -> None:
    record_research_turn_evidence(
        research=None,
        user_id=faker.uuid4(),
        conversation_id=None,
        message_id=None,
        request_id=None,
    )
    assert capture_payloads == []


def test_unrecognized_dimension_values_cannot_leak_sidecar_text(capture_payloads, faker):
    private_text = faker.sentence()
    record_research_turn_evidence(
        research={
            "capability_class": private_text,
            "usage": {"cache_status": private_text},
        },
        user_id=faker.uuid4(),
        conversation_id=None,
        message_id=None,
        request_id=None,
    )
    properties = capture_payloads[0]["properties"]
    assert properties["capability_class"] == "unknown"
    assert properties["attributes"]["cache_status"] == "unknown"
    assert private_text not in str(properties)


@pytest.mark.asyncio
async def test_posthog_capture_does_not_block_the_streaming_event_loop(
    monkeypatch, capture_payloads, faker
) -> None:
    captured = Event()
    post = envelope_module.httpx.post

    def record_post(*args, **kwargs):
        response = post(*args, **kwargs)
        captured.set()
        return response

    monkeypatch.setattr(envelope_module.httpx, "post", record_post)
    record_research_turn_evidence(
        research={
            "capability_class": "balanced_lookup",
            "usage": {"cache_status": "hit"},
        },
        user_id=faker.uuid4(),
        conversation_id=None,
        message_id=None,
        request_id=None,
    )
    assert capture_payloads == []
    assert await asyncio.to_thread(captured.wait, 2)
    assert capture_payloads[0]["properties"]["capability_class"] == "balanced_lookup"
