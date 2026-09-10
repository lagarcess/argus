"""Find's cache and sidecar read the same resolved evidence policy."""

from __future__ import annotations

import socket
from datetime import datetime, timezone

import pytest
from argus.agent_runtime import research_find
from argus.agent_runtime.discovery import composer
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, UserState
from argus.domain.research import cache
from argus.domain.research.contracts import ResearchPacket
from argus.domain.research.evidence_policy import ResearchEvidencePolicy


@pytest.mark.asyncio
@pytest.mark.parametrize("relationship", ["category", "peer"])
async def test_find_cache_and_readback_share_resolved_policy(monkeypatch, relationship):
    observed = {}
    packet = ResearchPacket(
        answer_markdown="Find result",
        retrieved_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )

    def no_network(*args, **kwargs):
        raise AssertionError("Policy readback must not open a provider connection")

    def put(key, value, *, ttl_seconds):
        assert value is packet
        observed["ttl_seconds"] = ttl_seconds

    async def discover(**kwargs):
        kwargs["packet_cache"].put(packet)
        # A later read of the table must not replace the policy used for this call.
        monkeypatch.setitem(cache.DATA_CLASS_TTL_SECONDS, "movers", 99.0)
        return StageResult(
            outcome="ready_to_respond",
            stage_patch={
                "discovery": {"retrieved_at": packet.retrieved_at.isoformat()},
                "discovery_usage": {"search_attempted": True, "cache_status": "miss"},
            },
        )

    def sidecar(**values):
        observed["policy"] = values["evidence_policy"]
        return {"evidence_policy": values["evidence_policy"].model_dump(mode="json")}

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setitem(cache.DATA_CLASS_TTL_SECONDS, "movers", 41.0)
    monkeypatch.setattr(research_find, "cache_put", put)
    monkeypatch.setattr(composer, "discovery_operation_result", discover)
    monkeypatch.setattr(research_find.grounded, "build_research_sidecar", sidecar)
    result = await research_find.find_assets_stage_result(
        request=AssetDiscoveryRequest(
            relationship=relationship,
            anchor_symbols=["AAPL"] if relationship == "peer" else [],
            needs_current_facts=True,
        ),
        interpretation=StructuredInterpretation(
            intent="explain", task_relation="new_task", user_goal_summary="Find assets"
        ),
        decision=None,
        state=RunState(current_user_message="Find current assets"),
        user=UserState(user_id="policy-control"),
    )

    policy = observed["policy"]
    assert policy.max_age_seconds == observed["ttl_seconds"] == 41
    assert policy.data_class == "movers"
    assert policy.question_kind == "find_assets"
    assert policy.question_as_of_date is None
    assert policy.period_start_date is None
    assert policy.current_survey is False
    assert (
        ResearchEvidencePolicy.model_validate(result.patch["research"]["evidence_policy"])
        == policy
    )
