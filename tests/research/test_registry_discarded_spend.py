"""Registered calls retain discarded spend through the existing research owners."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async
from argus.api import state as api_state
from argus.api.chat import research_jobs
from argus.api.chat.research_evidence import settle_research_turn
from argus.api.chat.tool_results import prepare_runtime_tool_publication
from argus.domain.research.perplexity_agent import PerplexityAgentClient
from argus.domain.tool_contracts import ToolCall, ToolResultCard
from faker import Faker

from tests.research import test_discarded_spend
from tests.research.conftest import (
    agent_response,
    retrieved_row,
    typed_answer_text,
    wire_grounded_client,
)
from tests.research.test_discarded_spend import (
    CALL_LATENCY_MS,
    ONE_RESPONSE_USD,
    _provider_only_document,
    _settle,
)
from tests.research.test_registered_research_tools import _context
from tests.research.test_research_jobs import _JobGateway

FAKE = Faker()
ledger = test_discarded_spend.ledger
stepping_clock = test_discarded_spend.stepping_clock


def _call(tool_name: str = "balanced_lookup") -> ToolCall:
    return ToolCall(
        tool_name=tool_name,
        call_id=FAKE.uuid4(),
        arguments={
            "request": "Read Netflix's source-backed figures",
            "symbols": ["NFLX"],
        },
    )


async def _execute(*calls: ToolCall):
    context = _context()
    context.state.tool_calls = list(calls)
    return await execute_tool_calls_async(
        state=context.state, tool=None, user=context.user
    )


@pytest.mark.asyncio()
@pytest.mark.parametrize("failure_reason", ["empty_answer", "malformed_response"])
async def test_billed_parser_failure_is_an_unavailable_call_with_retained_spend(
    monkeypatch, ledger, stepping_clock, failure_reason: str
) -> None:
    document = agent_response(text="   ")
    if failure_reason == "malformed_response":
        document["output"] = [{"type": "message", "content": 1}]
    transport = wire_grounded_client(monkeypatch, [document])

    result = await _execute(_call())

    assert len(transport.requests) == 1
    card = ToolResultCard.model_validate(
        result.stage_patch["final_response_payload"]["tool_result_cards"][0]
    )
    sidecar = result.stage_patch["tool_effects"][0]["stage_patch"]["research"]
    assert card.outcome.status == "unavailable"
    assert card.outcome.failure.code == sidecar["degraded"]["code"]
    assert card.outcome.failure.code == f"research_unavailable_{failure_reason}"
    assert card.outcome.result is None
    assert card.presentation.answer is None
    assert card.presentation.narrative is None
    assert card.presentation.sources == []
    assert sidecar["rows"] == []
    entry = _settle(result, ledger)
    assert entry["billable_quantity"] == 1
    assert entry["cost_amount"] == pytest.approx(ONE_RESPONSE_USD)
    assert entry["cost_source"] == "provider_reported"
    assert entry["latency_ms"] == CALL_LATENCY_MS
    assert entry["usage_metadata"]["degraded_code"] == card.outcome.failure.code


@pytest.mark.asyncio()
async def test_registered_retry_bills_the_turn_and_caches_only_the_served_packet(
    monkeypatch, ledger, stepping_clock
) -> None:
    publisher = "https://ir.netflix.net/financials/quarterly-earnings/"
    row = retrieved_row(subject="Netflix", symbol="NFLX", source_url=publisher, value=0.0)
    published = agent_response(
        text=typed_answer_text(f"{row['subject']}: {row['value']} {row['unit']}.", [row]),
        tickers=[row["symbol"]],
        sources=[publisher],
    )
    transport = wire_grounded_client(monkeypatch, [_provider_only_document(), published])

    paid = await _execute(_call())
    cached = await _execute(_call())

    assert len(transport.requests) == 2
    cards = [
        ToolResultCard.model_validate(
            result.stage_patch["final_response_payload"]["tool_result_cards"][0]
        )
        for result in (paid, cached)
    ]
    assert all(card.outcome.status == "succeeded" for card in cards)
    assert all(card.presentation.answer.value == row["value"] for card in cards)
    assert cards[0].outcome.result == cards[1].outcome.result
    paid_usage = paid.stage_patch["tool_effects"][0]["stage_patch"]["research"]["usage"]
    cached_usage = cached.stage_patch["tool_effects"][0]["stage_patch"]["research"][
        "usage"
    ]
    assert paid_usage == {
        "invocations": 2,
        "latency_ms": 2 * CALL_LATENCY_MS,
        "cost_usd": pytest.approx(2 * ONE_RESPONSE_USD),
        "cache_status": "miss",
    }
    assert cached_usage == {
        "invocations": 1,
        "latency_ms": CALL_LATENCY_MS,
        "cost_usd": pytest.approx(ONE_RESPONSE_USD),
        "cache_status": "hit",
    }
    paid_entry = _settle(paid, ledger)
    settle_research_turn(
        cached.stage_patch,
        user_id=paid_entry["user_id"],
        conversation_id=paid_entry["conversation_id"],
        message_id=FAKE.uuid4(),
        request_id=FAKE.uuid4(),
    )
    assert len(ledger.entries) == 2
    assert paid_entry["cost_amount"] == pytest.approx(2 * ONE_RESPONSE_USD)
    assert paid_entry["billable_quantity"] == 1
    assert ledger.entries[1]["billable_quantity"] == 0
    assert ledger.entries[1]["cost_amount"] is None
    assert ledger.entries[1]["cost_source"] == "unavailable"


@pytest.mark.asyncio()
async def test_two_billed_thorough_failures_keep_their_bound_call_correlations(
    monkeypatch, ledger, stepping_clock
) -> None:
    calls = [_call("thorough_research"), _call("thorough_research")]
    background_ids = [FAKE.uuid4() for _ in calls]
    documents = [
        {"id": background_id, "status": "queued"} for background_id in background_ids
    ] + [
        agent_response(text="   ", response_id=background_id, status="completed")
        for background_id in background_ids
    ]
    transport = wire_grounded_client(monkeypatch, documents)
    client = PerplexityAgentClient("k", transport=transport)
    gateway = _JobGateway()
    monkeypatch.setattr(
        gateway,
        "create_cost_ledger_entry",
        ledger.create_cost_ledger_entry,
        raising=False,
    )
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setattr(research_jobs, "_client", lambda: client)
    monkeypatch.setattr(research_jobs, "_spawn_poller", lambda **_: None)
    monkeypatch.setattr(research_jobs, "BACKGROUND_POLL_INTERVAL_SECONDS", 0)
    written: list[dict[str, Any]] = []

    def create_message(**kwargs):
        written.append(kwargs)
        return SimpleNamespace(id=FAKE.uuid4())

    monkeypatch.setattr("argus.api.message_store.create_message", create_message)
    identity = {
        "user_id": FAKE.uuid4(),
        "conversation_id": FAKE.uuid4(),
        "request_message_id": FAKE.uuid4(),
        "request_id": FAKE.uuid4(),
    }
    result = await _execute(*calls)
    runtime_result = result.stage_patch
    publication = prepare_runtime_tool_publication(
        runtime_result,
        runtime_result["tool_effects"],
        assistant_text=None,
        **identity,
    )
    assert len(publication.cards) == len(gateway.rows) == len(calls)
    assert all(
        card["outcome"]["result"]["status"] == "pending" for card in publication.cards
    )
    assert all(card["presentation"]["answer"] is None for card in publication.cards)
    for job in gateway.rows.values():
        launch = job["launch_payload"]
        await research_jobs._poll_and_finalize(
            job_id=job["id"],
            background_id=launch["perplexity_background_id"],
            job_request=launch["research_request"],
            user_id=identity["user_id"],
            conversation_id=identity["conversation_id"],
            request_id=identity["request_id"],
        )

    assert len(transport.requests) == 2 * len(calls)
    assert len(gateway.failed) == len(written) == len(ledger.entries) == len(calls)
    completed_cards = [
        ToolResultCard.model_validate(message["metadata"]["tool_result_cards"][0])
        for message in written
    ]
    assert [card.call_id for card in completed_cards] == [call.call_id for call in calls]
    assert all(card.outcome.status == "unavailable" for card in completed_cards)
    assert all(card.outcome.result is None for card in completed_cards)
    assert all(card.presentation.answer is None for card in completed_cards)
    assert all(card.presentation.narrative is None for card in completed_cards)
    assert {entry["request_id"] for entry in ledger.entries} == {identity["request_id"]}
    assert all(
        entry["cost_amount"] == pytest.approx(ONE_RESPONSE_USD)
        and entry["billable_quantity"] == 1
        for entry in ledger.entries
    )
    assert [entry["usage_metadata"].get("tool_call_id") for entry in ledger.entries] == [
        call.call_id for call in calls
    ]
    assert len({entry["correlation_id"] for entry in ledger.entries}) == len(calls)
