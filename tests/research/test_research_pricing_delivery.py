"""Billing drift must not erase a provider answer that passed grounding, and
the rate table follows the invoice the provider actually sends."""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from argus.api import app_setup
from argus.api import state as api_state
from argus.api.chat.research_evidence import record_research_turn_evidence
from argus.api.chat.research_pricing_evidence import (
    ResearchPricingRecorder,
    record_unpriced_research_spend,
)
from argus.domain.research import billing, pricing
from argus.domain.research.config import RESEARCH_CONFIG_SPECS
from argus.domain.research.perplexity_agent import PerplexityAgentClient
from argus.domain.supabase_gateway import SupabaseGateway
from fastapi import FastAPI
from loguru import logger

from tests.research.conftest import RecordingTransport, recorded_agent_response
from tests.research.test_research_answer import _classify, _run, _wire_client
from tests.research.test_research_evidence import _LedgerGateway
from tests.test_supabase_gateway import _RecordingSupabaseClient


@pytest.fixture
def netflix_response() -> dict[str, Any]:
    return json.loads(
        (
            Path(__file__).parent / "fixtures/perplexity_netflix_2026-09-03.json"
        ).read_text()
    )["response"]


@pytest.fixture
def ledger(monkeypatch):
    gateway = _LedgerGateway()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setattr(billing, "_recorder", record_unpriced_research_spend)
    return gateway.entries


@pytest.fixture
def mismatched_rates(monkeypatch):
    """A table that disagrees with the served model's invoice, the way the
    published page disagreed with every sol invoice until the table followed
    the bill: the output rate here is one no invoice carries."""
    model = "openai/gpt-5.6-sol"
    monkeypatch.setitem(
        pricing.MODEL_RATE_TABLE_USD_PER_MILLION,
        model,
        tuple(
            replace(tier, output_usd_per_million=Decimal("100"))
            for tier in pricing.MODEL_RATE_TABLE_USD_PER_MILLION[model]
        ),
    )


@pytest.fixture
def alerts():
    messages: list[str] = []
    sink = logger.add(
        lambda message: messages.append(message.record["message"]), level="ERROR"
    )
    try:
        yield messages
    finally:
        logger.remove(sink)


def _netflix_result(monkeypatch, response):
    _classify(
        monkeypatch,
        question_kind="company_lookup",
        symbols=["NFLX"],
        requires_publisher_sources=True,
    )
    _wire_client(monkeypatch, [response])
    result = _run("What changed for Netflix in its most recent quarterly earnings?")
    assert result is not None
    return result


@pytest.mark.parametrize("component", ["input", "output"])
def test_recorded_answer_reaches_user_despite_rate_disagreement(monkeypatch, component):
    response = recorded_agent_response()
    model = response["model"]
    monkeypatch.setitem(
        pricing.MODEL_RATE_TABLE_USD_PER_MILLION,
        model,
        tuple(
            replace(tier, **{f"{component}_usd_per_million": Decimal("100")})
            for tier in pricing.MODEL_RATE_TABLE_USD_PER_MILLION[model]
        ),
    )
    _classify(monkeypatch, question_kind="live_quote", symbols=["AAPL"])
    _wire_client(monkeypatch, [response])

    result = _run("What was Apple's latest close?")

    assert result is not None
    assert "316.22" in result.stage_patch["assistant_response"]
    assert "degraded" not in result.stage_patch["research"]
    assert result.stage_patch["research"]["usage"]["cost_usd"] is None


@pytest.mark.parametrize(
    "probe",
    [
        "fast_quote_typed",
        "typed_rows_current_external",
        "thorough_typed_background",
        "market_pulse_retry_finance_only",
    ],
)
def test_recorded_invoice_reconciles_against_current_rates(probe, ledger, alerts):
    """Changing the rates without matching recorded evidence fails this check:
    the sol and opus invoices recorded on 2026-09-09 are what the table must
    reconcile. Two of them read no cache and carry no cache_read_cost key at
    all, which the reader once rejected as an invalid invoice."""
    response = recorded_agent_response(probe)
    client = PerplexityAgentClient("test", transport=RecordingTransport([response]))
    packet = client.run_research("quote", RESEARCH_CONFIG_SPECS["fast"])
    assert packet.usage.cost_usd == response["usage"]["cost"]["total_cost"]
    assert not ledger
    assert not alerts


def test_an_invoice_at_the_earlier_published_schedule_is_unpriced_not_reread(
    ledger, alerts
):
    """The 2026-08-07 recording was billed at the page's $5 and $30. The
    provider bills $4 and $20 now, and the table follows the bill, so the
    earlier invoice is recorded as unpriced spend for a person to reconcile
    rather than silently accepted at either schedule."""
    response = recorded_agent_response("equity_steps2")
    client = PerplexityAgentClient("test", transport=RecordingTransport([response]))
    packet = client.run_research("quote", RESEARCH_CONFIG_SPECS["fast"])
    assert packet.answer_markdown
    assert packet.usage.cost_usd is None
    assert ledger[0]["usage_metadata"]["reason"] == "rate_mismatch"
    assert ledger[0]["usage_metadata"]["reported_cost"]["total_cost"] == 0.05395
    assert any("rate_mismatch" in message for message in alerts)


def test_the_live_netflix_invoice_reconciles_at_the_billed_rates(
    monkeypatch,
    netflix_response,
    ledger,
    alerts,
):
    """The invoice the old table rejected at output_cost ($0.01416 for 708
    tokens against $0.02124 expected) is exactly what $20 per million
    bills, so the answer now carries its real cost and no unpriced row."""
    result = _netflix_result(monkeypatch, netflix_response)
    assert "Netflix" in result.stage_patch["assistant_response"]
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert sidecar["sources"]
    assert sidecar["usage"]["cost_usd"] == pytest.approx(0.08591)
    assert set(sidecar["usage"]) == {
        "invocations",
        "latency_ms",
        "cost_usd",
        "cache_status",
    }
    assert not ledger
    assert not alerts
    public = json.dumps(result.stage_patch)
    assert netflix_response["id"] not in public
    assert netflix_response["model"] not in public


def test_unpriced_invoice_reaches_real_gateway_insert_and_error_alert(
    monkeypatch,
    netflix_response,
    alerts,
    mismatched_rates,
):
    client = _RecordingSupabaseClient()
    monkeypatch.setattr(api_state, "supabase_gateway", SupabaseGateway(client=client))
    monkeypatch.setattr(billing, "_recorder", record_unpriced_research_spend)
    _netflix_result(monkeypatch, netflix_response)
    entry = client.inserted_by_table["cost_ledger_entries"]
    assert entry["status"] is None
    assert entry["metadata"] == {"research_ledger_contract": "argus_research_ledger/v2"}
    assert entry["cost_amount"] is None
    assert entry["cost_source"] == "unavailable"
    assert entry["provider_request_id"] == netflix_response["id"]
    assert entry["model"] == netflix_response["model"]
    report = entry["usage_metadata"]
    assert report["pricing_status"] == "unpriced"
    assert report["reported_cost"]["total_cost"] == 0.08591
    assert report["reported_component_usd"] == 0.01416
    assert report["expected_min_usd"] == report["expected_max_usd"] == 0.0708
    assert any(
        "research_cost_unpriced" in message
        and "0.08591" in message
        and "0.0708" in message
        for message in alerts
    )
    # Private report has no prompt, answer, source text, or unrelated metadata.
    assert set(report) == {
        "pricing_status",
        "provider_response_id",
        "usage",
        "reported_cost",
        "reason",
        "detail",
        "reported_component_usd",
        "expected_min_usd",
        "expected_max_usd",
    }
    assert "Netflix" not in json.dumps(report)


def test_terminal_metering_cannot_turn_unpriced_spend_into_zero(
    monkeypatch,
    netflix_response,
    ledger,
    mismatched_rates,
):
    result = _netflix_result(monkeypatch, netflix_response)
    record_research_turn_evidence(
        research=result.stage_patch["research"],
        user_id="user",
        conversation_id="chat",
        message_id="message",
        request_id="request",
    )
    assert len(ledger) == 2
    assert all(entry["cost_amount"] is None for entry in ledger)
    assert all(entry["cost_source"] == "unavailable" for entry in ledger)


@pytest.mark.parametrize("recorder_state", ["missing", "database_failure"])
def test_accounting_failure_does_not_recreate_the_outage(
    monkeypatch,
    netflix_response,
    alerts,
    recorder_state,
    mismatched_rates,
):
    def fail(_spend):
        raise RuntimeError("secret database detail must not enter logs")

    monkeypatch.setattr(
        billing, "_recorder", fail if recorder_state == "database_failure" else None
    )
    result = _netflix_result(monkeypatch, netflix_response)
    assert "Netflix" in result.stage_patch["assistant_response"]
    assert any("research_cost_unpriced" in message for message in alerts)
    assert any(
        "research_cost_unrecorded" in message and "0.08591" in message
        for message in alerts
    )
    assert all("secret database detail" not in message for message in alerts)


def test_unknown_served_model_returns_answer_with_unpriced_spend(ledger, alerts):
    response = recorded_agent_response()
    response["model"] = "vendor/new-served-model"
    client = PerplexityAgentClient("test", transport=RecordingTransport([response]))
    packet = client.run_research("quote", RESEARCH_CONFIG_SPECS["fast"])
    assert packet.answer_markdown
    assert packet.usage.cost_usd is None
    assert ledger[0]["usage_metadata"]["reason"] == "unknown_model_rate"
    assert ledger[0]["usage_metadata"]["reported_cost"]["total_cost"] == 0.0487
    assert any("unknown_model_rate" in message for message in alerts)


@pytest.mark.parametrize(
    "malformation",
    ["missing_model", "missing_usage", "missing_tokens", "cache_disagreement"],
)
def test_incomplete_billing_metadata_cannot_erase_a_valid_answer(malformation, ledger):
    response = recorded_agent_response()
    if malformation == "missing_model":
        del response["model"]
    elif malformation == "missing_usage":
        del response["usage"]
    elif malformation == "missing_tokens":
        del response["usage"]["input_tokens"]
    else:
        response["usage"]["input_tokens_details"]["cached_tokens"] += 1
    client = PerplexityAgentClient("test", transport=RecordingTransport([response]))
    packet = client.run_research("quote", RESEARCH_CONFIG_SPECS["fast"])
    assert packet.answer_markdown
    assert packet.usage.cost_usd is None
    assert ledger[0]["usage_metadata"]["pricing_status"] == "unpriced"
    # The recorded output keeps its retrieval record; the count is unknown
    # only when the invoice itself is gone, never a zero.
    assert packet.tool_results == ("finance_results",)
    assert packet.usage.finance_search_invocations == (
        None if malformation == "missing_usage" else 1
    )


@pytest.mark.parametrize(
    "cost", [None, {}, {"currency": "EUR"}, {"currency": "USD", "input_cost": "NaN"}]
)
def test_invalid_invoice_does_not_discard_answer(cost, ledger):
    response = recorded_agent_response()
    response["usage"]["cost"] = cost
    client = PerplexityAgentClient("test", transport=RecordingTransport([response]))
    packet = client.run_research("quote", RESEARCH_CONFIG_SPECS["fast"])
    assert packet.answer_markdown
    assert packet.usage.cost_usd is None
    assert ledger[0]["cost_amount"] is None
    json.dumps(ledger[0], allow_nan=False)


def test_repeated_background_completion_records_invoice_once(
    netflix_response, ledger, alerts, mismatched_rates
):
    client = PerplexityAgentClient(
        "test", transport=RecordingTransport([netflix_response, netflix_response])
    )
    first = client.poll_background(netflix_response["id"])
    second = client.poll_background(netflix_response["id"])
    assert first.packet is not None and second.packet is not None
    assert "Netflix" in first.packet.answer_markdown
    assert first.packet.usage.cost_usd is None
    assert len(ledger) == 1
    assert sum("research_cost_unpriced" in message for message in alerts) == 1


def test_background_empty_answer_still_fails_closed(netflix_response):
    """A completed run whose answer cannot be read is the job's terminal
    failure: polling again cannot change a completed answer, so the poller
    must not spend its deadline retrying it."""
    netflix_response["output"] = []
    client = PerplexityAgentClient(
        "test", transport=RecordingTransport([netflix_response])
    )

    poll = client.poll_background(netflix_response["id"])

    assert poll.terminal and poll.status == "failed"
    assert poll.packet is None
    assert str(poll.failure_detail).startswith("empty_answer")


def test_api_lifespan_installs_and_removes_the_ledger_adapter(
    monkeypatch, netflix_response, ledger, mismatched_rates
):
    monkeypatch.setattr(billing, "_recorder", None)
    monkeypatch.setattr(api_state, "CHECKPOINTER_MODE", "memory")
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "false")

    async def exercise():
        async with app_setup.lifespan(FastAPI()):
            client = PerplexityAgentClient(
                "test", transport=RecordingTransport([netflix_response])
            )
            # Same context propagation as the actual inline and background callers.
            packet = await asyncio.to_thread(
                client.run_research, "question", RESEARCH_CONFIG_SPECS["balanced"]
            )
            assert packet.answer_markdown
        assert billing._recorder is None

    asyncio.run(exercise())
    assert len(ledger) == 1


@pytest.mark.parametrize("write_fails", [False, True])
def test_slow_ledger_cannot_hold_a_completed_provider_answer(
    monkeypatch,
    netflix_response,
    ledger,
    alerts,
    write_fails,
    mismatched_rates,
):
    started = threading.Event()
    release = threading.Event()
    gateway = api_state.supabase_gateway
    insert = gateway.create_cost_ledger_entry

    def blocked_insert(*, entry):
        started.set()
        assert release.wait(5)
        if write_fails:
            raise RuntimeError("database unavailable")
        return insert(entry=entry)

    monkeypatch.setattr(gateway, "create_cost_ledger_entry", blocked_insert)
    monkeypatch.setattr(api_state, "CHECKPOINTER_MODE", "memory")
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "false")

    async def exercise():
        async with app_setup.lifespan(FastAPI()):
            client = PerplexityAgentClient(
                "test", transport=RecordingTransport([netflix_response])
            )
            try:
                packet = await asyncio.wait_for(
                    asyncio.to_thread(
                        client.run_research, "question", RESEARCH_CONFIG_SPECS["balanced"]
                    ),
                    timeout=1,
                )
                assert packet.answer_markdown
                assert await asyncio.to_thread(started.wait, 1)
                assert not ledger
            finally:
                release.set()

    asyncio.run(exercise())
    assert len(ledger) == (0 if write_fails else 1)
    if write_fails:
        assert any("research_cost_unrecorded" in message for message in alerts)


def test_shutdown_cancels_queued_invoices_without_starting_more_writes(
    monkeypatch, netflix_response, ledger, alerts, mismatched_rates
):
    started = threading.Event()
    release = threading.Event()
    lock = threading.Lock()
    writes_started = 0
    gateway = api_state.supabase_gateway
    insert = gateway.create_cost_ledger_entry

    def blocked_insert(*, entry):
        nonlocal writes_started
        with lock:
            writes_started += 1
            if writes_started == 2:
                started.set()
        assert release.wait(5)
        return insert(entry=entry)

    monkeypatch.setattr(gateway, "create_cost_ledger_entry", blocked_insert)

    async def exercise():
        recorder = ResearchPricingRecorder()
        monkeypatch.setattr(billing, "_recorder", recorder)
        try:
            # Two running writes and two queued writes; every answer still returns.
            for index in range(4):
                response = {**netflix_response, "id": f"resp_shutdown_{index}"}
                client = PerplexityAgentClient(
                    "test", transport=RecordingTransport([response])
                )
                packet = client.run_research(
                    "question", RESEARCH_CONFIG_SPECS["balanced"]
                )
                assert packet.answer_markdown
            assert await asyncio.to_thread(started.wait, 1)
            await recorder.close()
        finally:
            release.set()
        await asyncio.gather(*tuple(recorder._pending), return_exceptions=True)

    asyncio.run(exercise())
    assert writes_started == len(ledger) == 2
    assert sum("research_cost_unpriced" in message for message in alerts) == 4
    assert any(
        "research_cost_persistence_pending_at_shutdown" in message for message in alerts
    )
