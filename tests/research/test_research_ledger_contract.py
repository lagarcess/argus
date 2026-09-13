"""Ledger-only retirement covers direct job writes and preserves discovery truth."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from argus.api import message_store
from argus.api import state as api_state
from argus.api.chat import discovery_evidence, research_jobs
from argus.domain.research.contracts import ResearchPacket, ResearchUsage
from argus.domain.supabase_gateway import SupabaseGateway
from faker import Faker

from tests.test_supabase_gateway import _RecordingSupabaseClient


@pytest.mark.parametrize("fallback_code", [None, "provider_unavailable"])
def test_legacy_discovery_keeps_its_observed_fallback_status(monkeypatch, fallback_code):
    client = _RecordingSupabaseClient()
    monkeypatch.setattr(api_state, "supabase_gateway", SupabaseGateway(client=client))
    usage = {"provider_id": "test", "fallback_code": fallback_code, "cost_usd": 0.1}
    before = json.dumps(usage).encode()
    discovery_evidence._append_research_ledger_row(
        usage=usage,
        user_id=Faker().uuid4(),
        conversation_id=None,
        message_id=None,
        request_id=None,
    )
    row = client.inserted_by_table["cost_ledger_entries"]
    assert row["source"] == "research"
    assert row["feature_area"] == "discovery"
    assert row["status"] == ("succeeded" if fallback_code is None else "failed")
    assert row["metadata"] == {}
    assert row["cost_amount"] == usage["cost_usd"]
    assert json.dumps(usage).encode() == before


@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize("unreadable", [False, True])
def test_background_writes_retire_status_without_changing_reader_bytes(
    monkeypatch, language, unreadable
):
    fake = Faker()
    client = _RecordingSupabaseClient()
    gateway = SupabaseGateway(client=client)
    messages = []

    def persist(**kwargs):
        messages.append(
            json.dumps(
                {"content": kwargs["content"], "metadata": kwargs["metadata"]},
                sort_keys=True,
            ).encode()
        )
        return SimpleNamespace(id=message_id)

    job_id, user_id, conversation_id, message_id, request_id = [
        fake.uuid4() for _ in range(5)
    ]
    monkeypatch.setattr(message_store, "create_message", persist)
    monkeypatch.setattr(research_jobs, "_mark_completed", AsyncMock())
    monkeypatch.setattr(gateway, "mark_backtest_job_failed", lambda **kwargs: None)
    job_request = {"capability_class": "thorough_research", "language": language}
    usage = ResearchUsage(invocations=2, latency_ms=9100, cost_usd=0.42)
    packet = ResearchPacket(answer_markdown=fake.sentence(), usage=usage)
    kwargs = dict(
        job_id=job_id,
        user_id=user_id,
        conversation_id=conversation_id,
        request_id=request_id,
        job_request=job_request,
    )

    # Replay the same immutable inputs with and without ledger persistence.
    # Both the delivered answer and the unreadable-turn note must be identical.
    for active_gateway in (None, gateway):
        monkeypatch.setattr(api_state, "supabase_gateway", active_gateway)
        if unreadable:
            research_jobs._fail_job(
                **kwargs,
                detail="malformed response",
                post_note=True,
                billed_reason="malformed_response",
                billed_usage=usage,
            )
        else:
            asyncio.run(research_jobs._finalize_success(**kwargs, packet=packet))

    assert len(messages) == 2
    assert messages[0] == messages[1]
    assert b"research_ledger_contract" not in messages[1]
    row = client.inserted_by_table["cost_ledger_entries"]
    assert row["status"] is None
    assert row["metadata"] == {"research_ledger_contract": "argus_research_ledger/v2"}
    assert row["task"] == "thorough_research"
    assert row["cost_amount"] == usage.cost_usd
    assert row["message_id"] == message_id
    if unreadable:
        assert (
            row["usage_metadata"]["degraded_code"]
            == "research_unavailable_malformed_response"
        )
        assert json.loads(messages[1])["metadata"] == {"conversation_mode": "guide"}
