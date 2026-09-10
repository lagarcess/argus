"""Each declared background call owns its job and finalized typed card."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.chat import research_jobs
from argus.domain.tool_contracts import ToolResultCard
from faker import Faker

from tests.research.test_registered_research_tools import _packet
from tests.research.test_research_jobs import _FakeClient, _job_request, _JobGateway

FAKE = Faker()


def _tool_fields(call_id: str) -> dict[str, Any]:
    return {
        "tool_call_id": call_id,
        "tool_name": "thorough_research",
        "tool_artifact_id": FAKE.uuid4(),
        "tool_arguments": {"request": "Read the financial reports", "symbols": ["AAPL"]},
    }


def _wire(monkeypatch):
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    gateway, client = _JobGateway(), _FakeClient([])
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setattr(research_jobs, "_client", lambda: client)
    monkeypatch.setattr(research_jobs, "_spawn_poller", lambda **_: None)
    return gateway, client


def _apply(fields: dict[str, Any]):
    runtime_result = {"research_job_request": _job_request()}
    return research_jobs.apply_research_job_request(
        runtime_result,
        user_id="owner",
        conversation_id="conversation",
        request_message_id="message",
        request_id="request",
        **fields,
    )


def test_two_thorough_calls_do_not_alias_one_request_message(monkeypatch) -> None:
    gateway, client = _wire(monkeypatch)
    a, b = _tool_fields("first-read"), _tool_fields("second-read")
    first, second, replay = _apply(a), _apply(b), _apply(a)
    assert first["id"] != second["id"]
    assert replay["id"] == first["id"]
    assert len(gateway.rows) == len(client.submitted) == 2
    assert {row["request_message_id"] for row in gateway.rows.values()} == {"message"}


@pytest.mark.parametrize("disable_after_submission", [False, True])
@pytest.mark.parametrize("row_mode", ["cited", "unsourced", "none"])
def test_background_completion_persists_the_matching_typed_tool_card(
    monkeypatch, disable_after_submission: bool, row_mode: str
) -> None:
    gateway, _ = _wire(monkeypatch)
    fields = _tool_fields("source-read")
    job = _apply(fields)
    request = gateway.rows[job["id"]]["launch_payload"]["research_request"]
    if disable_after_submission:
        monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    written: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    def create(**kwargs):
        written.append(kwargs)
        return type("SavedMessage", (), {"id": FAKE.uuid4()})()

    monkeypatch.setattr("argus.api.message_store.create_message", create)
    monkeypatch.setattr(
        research_jobs,
        "record_research_turn_evidence",
        lambda **kwargs: evidence.append(kwargs),
    )
    packet = _packet()
    if row_mode != "cited":
        packet = packet.model_copy(
            update={
                "rows": (),
                "unsourced_rows": (
                    (packet.rows[0].model_copy(update={"source_url": None}),)
                    if row_mode == "unsourced"
                    else ()
                ),
            }
        )
    asyncio.run(
        research_jobs._finalize_success(
            job_id=job["id"],
            job_request=request,
            packet=packet,
            user_id="owner",
            conversation_id="conversation",
            request_id="request",
        )
    )
    card = ToolResultCard.model_validate(written[0]["metadata"]["tool_result_cards"][0])
    assert card.call_id == fields["tool_call_id"]
    assert card.artifact_id == fields["tool_artifact_id"]
    assert card.outcome.status == "succeeded"
    assert card.outcome.result["status"] == "completed"
    assert card.outcome.result["rows"] == [
        row.model_dump(mode="json") for row in packet.published_rows
    ]
    assert card.presentation.narrative.startswith(packet.answer_markdown)
    if packet.published_rows:
        assert card.presentation.answer.value == packet.published_rows[0].value
    if row_mode == "unsourced":
        assert card.outcome.result["rows"][0]["source_url"] is None
        assert len(card.presentation.narrative) > len(packet.answer_markdown)
    assert card.arguments["request"] == fields["tool_arguments"]["request"]
    assert evidence[0]["tool_call_id"] == fields["tool_call_id"]


def test_background_failure_persists_a_tool_failure_without_an_answer(
    monkeypatch,
) -> None:
    gateway, _ = _wire(monkeypatch)
    fields = _tool_fields("failed-read")
    job = _apply(fields)
    request = gateway.rows[job["id"]]["launch_payload"]["research_request"]
    written: list[dict[str, Any]] = []

    def create(**kwargs):
        written.append(kwargs)
        return type("SavedMessage", (), {"id": FAKE.uuid4()})()

    monkeypatch.setattr("argus.api.message_store.create_message", create)
    research_jobs._persist_failure_note(
        job_id=job["id"],
        user_id="owner",
        conversation_id="conversation",
        job_request=request,
    )
    card = ToolResultCard.model_validate(written[0]["metadata"]["tool_result_cards"][0])
    assert card.call_id == fields["tool_call_id"]
    assert card.outcome.status == "unavailable"
    assert card.outcome.result is None
    assert card.presentation.answer is None


def test_background_completion_uses_the_shared_version_failure(monkeypatch) -> None:
    from argus.api.chat.research_tool_results import research_tool_card_for_completion

    gateway, _ = _wire(monkeypatch)
    fields = _tool_fields("old-binding")
    job = _apply(fields)
    request = gateway.rows[job["id"]]["launch_payload"]["research_request"]
    request["tool_binding"]["card_version"] += 1
    card = ToolResultCard.model_validate(
        research_tool_card_for_completion(
            request, {"assistant_response": FAKE.sentence()}
        )
    )
    assert card.call_id == fields["tool_call_id"]
    assert card.outcome.failure.code == "tool_contract_changed"
    assert card.presentation.answer is None
    assert card.presentation.narrative is None
