"""No-network proofs for the #606 shared measurement ceiling."""

import httpx
import pytest
from argus.domain.research.perplexity_agent import PerplexityAgentClient
from argus.domain.result_readout_research import result_research_spec

from tests.evals.measurement_spend_guard import (
    guard_http,
    initialize_budget,
    read_budget,
    request_reservation,
)


@pytest.fixture
def rates():
    return {
        "openrouter": {
            "priced": {
                "input_per_million": 1,
                "output_per_million": 2,
                "context_window_tokens": 10000,
            }
        },
        "perplexity_agent": {
            "cheap": {
                "input_per_million": 1,
                "output_per_million": 2,
                "context_window_tokens": 10000,
            },
            "costly": {
                "input_per_million": 3,
                "output_per_million": 4,
                "context_window_tokens": 10000,
            },
        },
        "tools": {"web_search": 0.0025, "fetch_url": 0.0005},
    }


def agent_body(models):
    spec = result_research_spec("en").model_copy(update={"models": tuple(models)})
    body = PerplexityAgentClient(api_key="test-only")._request_body(
        "Authored result fixture", spec
    )
    # run_structured adds this canonical caller limit after _request_body.
    from argus.domain.result_readout_research import RESULT_RESEARCH_LIMITS

    body["max_tool_calls"] = RESULT_RESEARCH_LIMITS.max_tool_calls
    return body


@pytest.mark.parametrize("models", [("cheap", "costly"), ("costly", "cheap")])
def test_actual_agent_request_reserves_the_most_expensive_fallback(rates, models):
    body = agent_body(models)
    assert "model" not in body
    assert body["models"] == list(models)
    reserve = request_reservation("perplexity_agent", body, rates)
    assert reserve == request_reservation(
        "perplexity_agent", agent_body(["costly"]), rates
    )
    assert reserve > request_reservation("perplexity_agent", agent_body(["cheap"]), rates)


def test_unpriced_fallback_is_refused_even_when_primary_is_priced(rates):
    with pytest.raises(ValueError, match="unpriced_model:unknown"):
        request_reservation("perplexity_agent", agent_body(["cheap", "unknown"]), rates)


def test_real_agent_body_can_be_reserved_without_a_single_model_field(tmp_path, rates):
    ledger = tmp_path / "budget.json"
    initialize_budget(ledger, rates)
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "usage": {
                    "cost": {
                        "currency": "USD",
                        "total_cost": 0.01,
                    }
                }
            },
        )

    with guard_http(ledger, rates, live=True, scope="authored-test"):
        client = PerplexityAgentClient(
            api_key="test-only", transport=httpx.MockTransport(response)
        )
        client._post(agent_body(["cheap", "costly"]), timeout_seconds=10)
    state = read_budget(ledger)
    assert len(calls) == 1
    assert state["charged_usd"] == pytest.approx(0.01)
    assert state["requests"][0]["models"] == ["cheap", "costly"]


@pytest.mark.parametrize("mode", ["no_go", "cap", "time", "http_error", "unknown_cost"])
def test_guard_stops_paid_dispatch_before_retries(tmp_path, rates, mode):
    ledger = tmp_path / "budget.json"
    initialize_budget(ledger, rates, budget_usd=0.00001 if mode == "cap" else 12.50)
    if mode == "time":
        import json

        state = read_budget(ledger)
        state["deadline_epoch"] = 0
        ledger.write_text(json.dumps(state))
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(429 if mode == "http_error" else 200, json={})

    with guard_http(ledger, rates, live=mode != "no_go", scope="test"):
        with httpx.Client(transport=httpx.MockTransport(response)) as client:
            for _ in range(2):
                with pytest.raises(ValueError):
                    client.post(
                        "https://api.perplexity.ai/v1/agent", json=agent_body(["cheap"])
                    )
    assert len(calls) == (1 if mode in {"http_error", "unknown_cost"} else 0)


def test_budget_cannot_be_reset_or_expanded(tmp_path, rates):
    ledger = tmp_path / "budget.json"
    with pytest.raises(ValueError):
        initialize_budget(ledger, rates, budget_usd=13)
    initialize_budget(ledger, rates)
    with pytest.raises(FileExistsError):
        initialize_budget(ledger, rates)


@pytest.mark.asyncio
async def test_openrouter_async_dispatch_shares_the_ledger_and_blocks_retries(
    tmp_path, rates
):
    ledger = tmp_path / "budget.json"
    initialize_budget(ledger, rates)
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(200, json={"usage": {"cost": 0.001}})

    payload = {"model": "priced", "max_tokens": 100, "messages": []}
    for scope in ("baseline", "candidate"):
        with guard_http(ledger, rates, live=True, scope=scope):
            async with httpx.AsyncClient(
                transport=httpx.MockTransport(response)
            ) as client:
                await client.post(
                    "https://openrouter.ai/api/v1/chat/completions", json=payload
                )
    state = read_budget(ledger)
    assert state["charged_usd"] == pytest.approx(0.002)
    with guard_http(ledger, rates, live=True, scope="candidate"):
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
            with pytest.raises(ValueError, match="automatic_retry_forbidden"):
                await client.post(
                    "https://openrouter.ai/api/v1/chat/completions", json=payload
                )
    assert len(calls) == 2


def test_agent_http_failure_cannot_trigger_its_builtin_retry(tmp_path, rates):
    ledger = tmp_path / "budget.json"
    initialize_budget(ledger, rates)
    calls = []

    def response(request):
        calls.append(request)
        return httpx.Response(429, json={})

    with guard_http(ledger, rates, live=True, scope="rate-limit"):
        client = PerplexityAgentClient(
            api_key="test-only", transport=httpx.MockTransport(response)
        )
        with pytest.raises(ValueError, match="provider_http_429"):
            client._post(agent_body(["cheap"]), timeout_seconds=10)
    assert len(calls) == 1
    assert read_budget(ledger)["stopped"]
