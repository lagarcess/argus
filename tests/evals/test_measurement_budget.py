"""Free transport-level reproductions of the paid measurement stop boundary."""

from __future__ import annotations

import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from argus.domain.research.config import RESEARCH_CONFIG_SPECS
from argus.domain.research.perplexity_agent import (
    PerplexityAgentClient,
    _usage_from_response,
)

from tests.evals.measurement_budget import MeasurementBudget, MeasurementBudgetStop
from tests.evals.measurement_eval_harness import load_eval_cases

AGENT_URL = "https://api.perplexity.ai/v1/agent"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
SEARCH_URL = "https://api.perplexity.ai/search"


def agent_body(spec=None):
    return PerplexityAgentClient(api_key="offline-test")._request_body(
        "What is Apple's price?", spec or RESEARCH_CONFIG_SPECS["fast"]
    )


@pytest.mark.parametrize("shape", RESEARCH_CONFIG_SPECS)
def test_real_agent_fallback_list_reaches_transport(budget, agent_invoice, shape):
    calls = []
    body = agent_body(RESEARCH_CONFIG_SPECS[shape])
    assert "models" in body and "model" not in body
    client = PerplexityAgentClient(
        api_key="offline-test",
        transport=httpx.MockTransport(
            lambda req: calls.append(json.loads(req.content))
            or httpx.Response(200, json=agent_invoice)
        ),
    )
    with budget.case(agent_case(budget)):
        client._post(body, timeout_seconds=1)
    assert calls == [body]
    budget.assert_complete()


@pytest.mark.parametrize("unknown_index", [0, 1])
def test_unpriced_fallback_is_rejected_before_dispatch(budget, unknown_index):
    spec = RESEARCH_CONFIG_SPECS["fast"]
    models = list(spec.models)
    models[unknown_index] = "unpriced-model"
    body = agent_body(spec.model_copy(update={"models": tuple(models)}))
    calls = []
    client = PerplexityAgentClient(
        api_key="offline-test",
        transport=httpx.MockTransport(lambda req: calls.append(req)),
    )
    with pytest.raises(MeasurementBudgetStop, match="unpriced_agent_request_model"):
        with budget.case(agent_case(budget)):
            client._post(body, timeout_seconds=1)
    assert calls == []
    assert budget.snapshot()["sends"] == []


def test_reservation_uses_most_expensive_fallback_independent_of_order(budget):
    spec = RESEARCH_CONFIG_SPECS["fast"].model_copy(
        update={"max_output_tokens": 100_000, "max_steps": 1}
    )
    body = agent_body(spec)
    reserve = budget.agent_reservation(body)
    assert reserve >= Decimal("4.5")
    body["models"].reverse()
    assert budget.agent_reservation(body) == reserve
    body["models"] = ["openai/gpt-5.6-luna"]
    assert budget.agent_reservation(body) < reserve


def test_highest_fallback_reservation_controls_real_dispatch(budget):
    spec = RESEARCH_CONFIG_SPECS["fast"].model_copy(
        update={"max_output_tokens": 100_000, "max_steps": 1}
    )
    budget._settled["agent"] = Decimal("4")
    calls = []
    client = PerplexityAgentClient(
        api_key="offline-test",
        transport=httpx.MockTransport(lambda req: calls.append(req)),
    )
    with pytest.raises(MeasurementBudgetStop, match="provider_admission_budget"):
        with budget.case(agent_case(budget)):
            client._post(agent_body(spec), timeout_seconds=1)
    assert calls == []
    assert budget.snapshot()["sends"] == []


@pytest.fixture
def budget(tmp_path, monkeypatch):
    guard = MeasurementBudget(tmp_path / "costs.jsonl", {c.id for c in load_eval_cases()})
    guard.install(monkeypatch)
    yield guard
    guard.close()


@pytest.fixture
def agent_invoice():
    path = Path("tests/research/fixtures/perplexity_fast_quote_2026-09-09.json")
    return json.loads(path.read_text())["exchanges"][0]["response"]


def agent_case(budget):
    return sorted(budget.agent_cases)[0]


def ordinary_case(budget):
    return sorted(
        budget.case_ids
        - budget.agent_cases
        - budget.search_cases
        - budget.no_research_cases
    )[0]


def test_prices_raw_invoice_even_when_answer_is_malformed(budget, agent_invoice):
    agent_invoice["output"] = "broken response with secret body"
    expected = _usage_from_response(agent_invoice, latency_ms=0).cost_usd
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=agent_invoice)

    with (
        budget.case(agent_case(budget)),
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
    ):
        assert (
            client.post(AGENT_URL, json=agent_body()).json()["output"]
            == agent_invoice["output"]
        )
    budget.assert_complete()
    assert len(calls) == 1
    assert float(budget.snapshot()["total_settled_usd"]) == expected
    evidence = Path(budget._file.name).read_text()
    assert "broken response" not in evidence
    assert '"event": "invoice"' in evidence


@pytest.mark.parametrize("url", [AGENT_URL, SEARCH_URL])
def test_no_new_facts_blocks_first_attempt_before_transport(budget, url):
    calls = []
    transport = httpx.MockTransport(
        lambda req: calls.append(req) or httpx.Response(200, json={})
    )
    with pytest.raises(MeasurementBudgetStop, match="no_new_facts_research_attempt"):
        with (
            budget.case(sorted(budget.no_research_cases)[0]),
            httpx.Client(transport=transport) as client,
        ):
            client.post(url)
    assert calls == []
    assert budget.snapshot()["sends"] == []
    assert budget.snapshot()["attempts"][0]["count"] == 1
    with pytest.raises(MeasurementBudgetStop):
        with budget.case(ordinary_case(budget)):
            pass


def test_agent_second_http_send_never_reaches_transport(budget, agent_invoice):
    calls = []
    transport = httpx.MockTransport(
        lambda req: calls.append(req) or httpx.Response(200, json=agent_invoice)
    )
    with pytest.raises(MeasurementBudgetStop, match="agent_retry_denied"):
        with budget.case(agent_case(budget)), httpx.Client(transport=transport) as client:
            client.post(AGENT_URL, json=agent_body())
            client.post(AGENT_URL, json=agent_body())
    assert len(calls) == 1


def test_second_agent_application_stops_before_second_http_send(budget, agent_invoice):
    calls = []
    transport = httpx.MockTransport(
        lambda req: calls.append(req) or httpx.Response(200, json=agent_invoice)
    )
    client = PerplexityAgentClient(api_key="offline-test", transport=transport)
    with pytest.raises(MeasurementBudgetStop, match="agent_application_retry_denied"):
        with budget.case(agent_case(budget)):
            client._post(agent_body(), timeout_seconds=1)
            client._post(agent_body(), timeout_seconds=1)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "document", [{}, {"usage": {"cost": "NaN"}}, {"usage": {"cost": -1}}]
)
def test_unpriced_openrouter_stops_and_retains_reservation(budget, document):
    with pytest.raises(MeasurementBudgetStop, match="unresolved_invoice"):
        with (
            budget.case(ordinary_case(budget)),
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(200, json=document)
                )
            ) as client,
        ):
            client.post(OR_URL)
    assert budget.snapshot()["outstanding_sends"] == 1
    assert float(budget.snapshot()["total_settled_usd"]) == 0


def test_unknown_agent_model_is_unpriced_not_zero(budget, agent_invoice):
    agent_invoice["model"] = "unpriced-model"
    with pytest.raises(MeasurementBudgetStop, match="unresolved_invoice"):
        with (
            budget.case(agent_case(budget)),
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(200, json=agent_invoice)
                )
            ) as client,
        ):
            client.post(AGENT_URL, json=agent_body())
    assert budget.snapshot()["outstanding_sends"] == 1


def test_timeout_cannot_be_swallowed_by_production_exception_recovery(budget):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("sensitive request must not be recorded")

    with pytest.raises(MeasurementBudgetStop, match="unresolved_invoice"):
        with (
            budget.case(agent_case(budget)),
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
        ):
            try:
                client.post(AGENT_URL, json=agent_body())
            except Exception:
                pytest.fail("production fallback swallowed budget stop")
    assert len(calls) == 1
    assert "sensitive" not in Path(budget._file.name).read_text()


@pytest.mark.asyncio
async def test_async_and_thread_offload_share_one_ledger_and_replay_body(
    budget, agent_invoice
):
    with budget.case(agent_case(budget)):

        def sync_call():
            with httpx.Client(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(200, json=agent_invoice)
                )
            ) as client:
                return client.post(AGENT_URL, json=agent_body()).json()

        assert (await asyncio.to_thread(sync_call))["usage"] == agent_invoice["usage"]
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={"usage": {"cost": 0.02}, "choices": []}
                )
            )
        ) as client:
            response = await client.post(OR_URL)
            assert response.json()["choices"] == []
    assert len(budget.snapshot()["sends"]) == 2
    assert budget.snapshot()["outstanding_sends"] == 0


def test_outstanding_agent_blocks_other_case_before_second_send(budget, agent_invoice):
    entered, release = threading.Event(), threading.Event()
    cases = sorted(budget.agent_cases)

    def handler(_):
        entered.set()
        assert release.wait(5)
        return httpx.Response(200, json=agent_invoice)

    def pending_call():
        with (
            budget.case(cases[0]),
            httpx.Client(transport=httpx.MockTransport(handler)) as client,
        ):
            client.post(AGENT_URL, json=agent_body())

    with ThreadPoolExecutor() as executor:
        future = executor.submit(pending_call)
        assert entered.wait(5)
        try:
            with pytest.raises(
                MeasurementBudgetStop, match="agent_request_still_outstanding"
            ):
                with budget.case(cases[1]):
                    budget.admit("openrouter")
        finally:
            release.set()
        with pytest.raises(MeasurementBudgetStop):
            future.result(timeout=5)
    assert budget.snapshot()["outstanding_sends"] == 0
    assert len(budget.snapshot()["sends"]) == 1
    assert float(budget.snapshot()["total_settled_usd"]) > 0


def test_agent_reservations_stop_before_ninth_dollar(budget):
    cases = sorted(budget.agent_cases)
    for case in cases[:5]:
        with budget.case(case):
            budget.settle(budget.admit("agent"), "1.40")
    with pytest.raises(MeasurementBudgetStop, match="provider_admission_budget"):
        with budget.case(cases[5]):
            budget.admit("agent")
    assert float(budget.snapshot()["total_settled_usd"]) == 7
    assert len(budget.snapshot()["sends"]) == 5


def test_agent_overshoot_accounts_actual_invoice_before_stopping(budget):
    with pytest.raises(MeasurementBudgetStop, match="agent_invoice_exceeds_reservation"):
        with budget.case(agent_case(budget)):
            budget.settle(budget.admit("agent"), "2.50")
    assert budget.snapshot()["settled_usd"]["agent"] == "2.50"
    assert budget.snapshot()["outstanding_sends"] == 0


def test_duplicate_invoice_cannot_double_charge(budget):
    with pytest.raises(MeasurementBudgetStop, match="duplicate_or_unknown_settlement"):
        with budget.case(agent_case(budget)):
            send = budget.admit("agent")
            budget.settle(send, ".2")
            budget.settle(send, ".2")
    assert float(budget.snapshot()["total_settled_usd"]) == 0.2


def test_all_sixteen_agent_cases_can_send_once(budget):
    for case in sorted(budget.agent_cases):
        with budget.case(case):
            budget.settle(budget.admit("agent"), ".01")
    budget.assert_complete()
    assert len(budget.snapshot()["sends"]) == 16


def test_search_uses_canonical_fixed_fee_and_allowlist(budget):
    with (
        budget.case(sorted(budget.search_cases)[0]),
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"results": []})
            )
        ) as client,
    ):
        client.post(SEARCH_URL)
    assert float(budget.snapshot()["settled_usd"]["search"]) == 0.005
    with pytest.raises(MeasurementBudgetStop, match="search_case_not_allowed"):
        with budget.case(ordinary_case(budget)):
            budget.admit("search")


def test_no_case_or_new_endpoint_stops_before_network(budget):
    with pytest.raises(MeasurementBudgetStop, match="paid_send_outside_case"):
        budget.admit("openrouter")


def test_http_error_invoice_is_charged_before_stopping(budget):
    with pytest.raises(MeasurementBudgetStop, match="provider_http_error"):
        with (
            budget.case(ordinary_case(budget)),
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda _: httpx.Response(429, json={"usage": {"cost": 0.02}})
                )
            ) as client,
        ):
            client.post(OR_URL)
    assert float(budget.snapshot()["total_settled_usd"]) == 0.02


@pytest.mark.asyncio
async def test_openrouter_sse_invoice_is_counted_once_and_remains_replayable(budget):
    content = 'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: {"usage":{"cost":0.03},"choices":[]}\n\ndata: [DONE]\n\n'
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=content
        )
    )
    with budget.case(ordinary_case(budget)):
        async with httpx.AsyncClient(transport=transport) as client:
            async with client.stream("POST", OR_URL) as response:
                assert "\n".join(
                    [line async for line in response.aiter_lines()]
                ).startswith('data: {"choices"')
                assert response.text == content
    assert float(budget.snapshot()["total_settled_usd"]) == 0.03


@pytest.mark.asyncio
async def test_async_transport_cancellation_latches_global_stop(budget):
    entered = asyncio.Event()

    async def handler(_):
        entered.set()
        await asyncio.Event().wait()

    with (
        pytest.raises(MeasurementBudgetStop, match="unresolved_invoice"),
        budget.case(ordinary_case(budget)),
    ):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            task = asyncio.create_task(client.post(OR_URL))
            await entered.wait()
            task.cancel()
            with pytest.raises(MeasurementBudgetStop, match="unresolved_invoice"):
                await task
        with pytest.raises(MeasurementBudgetStop):
            budget.check()


def test_openrouter_each_retry_and_judge_send_counts_toward_pool(budget):
    calls = []
    transport = httpx.MockTransport(
        lambda request: calls.append(request)
        or httpx.Response(200, json={"usage": {"cost": 0.99}})
    )
    with pytest.raises(MeasurementBudgetStop, match="provider_admission_budget"):
        with (
            budget.case(ordinary_case(budget)),
            httpx.Client(transport=transport) as client,
        ):
            for _ in range(5):
                client.post(OR_URL)
    assert len(calls) == 4
    assert float(budget.snapshot()["total_settled_usd"]) == 3.96


def test_unknown_provider_endpoint_is_blocked_before_transport(budget):
    calls = []
    with pytest.raises(MeasurementBudgetStop, match="unbudgeted_provider_endpoint"):
        with (
            budget.case(agent_case(budget)),
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: calls.append(request) or httpx.Response(200)
                )
            ) as client,
        ):
            client.post("https://api.perplexity.ai/new-endpoint")
    assert calls == []


def test_case_cannot_complete_with_unresolved_thread_invoice(budget):
    with pytest.raises(MeasurementBudgetStop, match="outstanding_invoice_at_case_end"):
        with budget.case(agent_case(budget)):
            budget.admit("agent")
    assert budget.snapshot()["outstanding_sends"] == 1
