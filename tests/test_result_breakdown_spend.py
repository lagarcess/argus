import asyncio
import threading
from types import SimpleNamespace

import pytest
from argus.api import state as api_state
from argus.api.chat import breakdown, research_evidence
from argus.domain.research.contracts import ResearchUnavailableError, ResearchUsage
from argus.domain.research.perplexity_agent import StructuredAgentResult


@pytest.mark.parametrize("outcome", ["accepted", "language_mismatch", "invalid_response"])
@pytest.mark.parametrize("cost", [0.008, None])
def test_every_received_breakdown_invoice_reaches_shared_ledger(
    monkeypatch, outcome, cost
):
    usage = ResearchUsage(
        model=breakdown.RESULT_BREAKDOWN_MODEL,
        cost_usd=cost,
        input_tokens=120,
        output_tokens=90,
        web_search_invocations=1,
    )

    class Client:
        def run_structured(self, *args, **kwargs):
            if outcome == "invalid_response":
                raise ResearchUnavailableError(
                    "invalid_response", "malformed draft", usage=usage
                )
            draft = {
                "text": "The uneven path mattered to the holder.",
                "language": "es-419" if outcome == "language_mismatch" else "en",
                "figures": [],
                "source_figures": [],
                "citations": [],
            }
            return StructuredAgentResult(
                draft=draft,
                usage=usage,
                sources=(),
                tool_results=(),
                provider_response_id=None,
            )

    text, failure, received_usage, _ = breakdown._llm_result_breakdown_with_metadata(
        {}, client=Client()
    )
    assert received_usage == usage
    assert bool(text) is (outcome == "accepted")
    entries = []
    monkeypatch.setattr(
        api_state,
        "supabase_gateway",
        SimpleNamespace(create_cost_ledger_entry=lambda *, entry: entries.append(entry)),
    )
    research_evidence.record_result_breakdown_spend(
        usage=received_usage,
        failure_mode=failure,
        user_id="owner",
        conversation_id="conversation",
        request_id="request",
    )
    assert len(entries) == 1
    entry = entries[0]
    assert entry["task"] == "result_breakdown"
    assert entry["feature_area"] == "result_readout"
    assert entry["source"] == "research"
    assert entry["service"] == "perplexity_agent"
    assert entry["model"] == usage.model
    assert entry["cost_amount"] == cost
    assert entry["cost_source"] == (
        "provider_reported" if cost is not None else "unavailable"
    )
    assert entry["input_tokens"] == usage.input_tokens
    assert entry["output_tokens"] == usage.output_tokens
    assert entry["usage_metadata"]["web_search_invocations"] == 1
    assert entry["usage_metadata"].get("degraded_code") == failure
    assert "text" not in entry["usage_metadata"]


@pytest.mark.asyncio
async def test_stream_disconnect_does_not_drop_received_breakdown_spend(monkeypatch):
    started, release, recorded = threading.Event(), threading.Event(), threading.Event()
    usage = ResearchUsage(model=breakdown.RESULT_BREAKDOWN_MODEL, cost_usd=0.01)

    def compose(*args, **kwargs):
        started.set()
        assert release.wait(timeout=2)
        return breakdown.ResultBreakdownMessage(
            text="Complete readout.",
            source="llm_breakdown_stage",
            fallback_used=False,
            usage=usage,
        )

    def record(**kwargs):
        assert kwargs["usage"] == usage
        recorded.set()

    monkeypatch.setattr(breakdown, "result_breakdown_message_with_metadata", compose)
    monkeypatch.setattr(breakdown, "record_result_breakdown_spend", record)
    task = asyncio.create_task(
        asyncio.to_thread(
            breakdown.result_breakdown_action,
            None,
            language="en",
            user_id="owner",
            conversation_id="conversation",
            request_id="request",
        )
    )
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()
    assert await asyncio.to_thread(recorded.wait, 2)
