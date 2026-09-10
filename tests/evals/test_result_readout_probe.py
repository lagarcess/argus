"""Failed provider attempts keep their reservation without inventing actual cost."""

import asyncio
import json
from contextlib import ExitStack

import httpx
import pytest

from tests.evals.result_readout_eval import CostGuard
from tests.evals.result_readout_probe import install_http_guards


@pytest.mark.asyncio
@pytest.mark.parametrize("async_client", [False, True])
@pytest.mark.parametrize(
    "failure", [httpx.ReadTimeout, asyncio.CancelledError, BaseException]
)
async def test_failed_and_canceled_attempts_retain_safe_receipt_and_reservation(
    monkeypatch: pytest.MonkeyPatch,
    async_client: bool,
    failure: type[BaseException],
) -> None:
    def fail(*args, **kwargs):
        raise failure("secret-test-value")

    async def fail_async(*args, **kwargs):
        fail()

    monkeypatch.setattr(httpx.Client, "post", fail)
    monkeypatch.setattr(httpx.AsyncClient, "post", fail_async)
    guard = CostGuard(
        budget_usd=4,
        rates={"fixture-model": {"input_per_million": 0.1, "output_per_million": 0.2}},
    )
    observations = {"requests": [], "provider_responses": [], "guard_failures": []}
    payload = {
        "model": "fixture-model",
        "max_tokens": 700,
        "messages": [],
        "response_format": {"json_schema": {"name": "QuickTakeDraft"}},
    }
    with ExitStack() as stack:
        install_http_guards(stack, guard=guard, observations=observations, live=True)
        with pytest.raises(failure):
            if async_client:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "https://openrouter.ai/api/v1/chat/completions", json=payload
                    )
            else:
                with httpx.Client() as client:
                    client.post(
                        "https://openrouter.ai/api/v1/chat/completions", json=payload
                    )
    receipt = observations["requests"][0]
    assert receipt["reserved_usd"] == pytest.approx(guard.reserved_usd)
    assert receipt["outcome"] in {"failed", "canceled"}
    assert receipt["error"]["code"]
    assert receipt["error"]["message"]
    assert "secret-test-value" not in json.dumps(observations)


def test_missing_actual_cost_continues_only_with_complete_reservations() -> None:
    from tests.evals.result_readout_eval import measurement_can_continue

    probe = {
        "cost_complete": False,
        "unknown_cost_attempts": 1,
        "all_attempts_reserved": True,
        "guard_failures": [],
    }
    assert measurement_can_continue(probe)
    assert not measurement_can_continue({**probe, "all_attempts_reserved": False})
    assert not measurement_can_continue({**probe, "guard_failures": ["unpriced_model"]})


def test_mixed_actual_and_unknown_costs_have_honest_upper_bound() -> None:
    from tests.evals.result_readout_probe import cost_accounting

    guard = CostGuard(
        budget_usd=4,
        rates={"fixture-model": {"input_per_million": 0.1, "output_per_million": 0.2}},
    )
    payload = {"model": "fixture-model", "max_tokens": 700, "messages": []}
    observations = {"requests": [], "provider_responses": [], "guard_failures": []}
    for index in range(2):
        reservation = guard.reserve(payload, task="result_summary")
        observations["requests"].append(
            {"attempt_id": index + 1, "reserved_usd": reservation}
        )
    actual_cost = guard.reserved_usd / 10
    observations["provider_responses"].append(
        {"attempt_id": 2, "usage": {"cost": actual_cost}}
    )
    accounted = cost_accounting(guard=guard, observations=observations)
    assert accounted["observed_cost_usd"] == pytest.approx(actual_cost)
    assert accounted["unknown_cost_attempts"] == 1
    assert accounted["unknown_cost_reserved_usd"] == pytest.approx(guard.reserved_usd / 2)
    assert accounted["accounted_upper_bound_usd"] == pytest.approx(
        actual_cost + guard.reserved_usd / 2
    )
    assert accounted["cost_complete"] is False
    assert accounted["all_attempts_reserved"] is True


@pytest.mark.parametrize("cost", [-1, float("inf"), float("nan"), True, "0.001", 10])
def test_invalid_or_excess_actual_cost_stops_before_another_request(
    monkeypatch: pytest.MonkeyPatch, cost: object
) -> None:
    from tests.evals.result_readout_probe import cost_accounting

    calls = []

    def response(*args, **kwargs):
        calls.append(kwargs)
        # httpx's JSON encoder correctly refuses nonfinite numbers; a provider's
        # decoded response can still contain one, so exercise that boundary.
        result = httpx.Response(200, json={})
        result.json = lambda: {"usage": {"cost": cost}}
        return result

    monkeypatch.setattr(httpx.Client, "post", response)
    guard = CostGuard(
        budget_usd=4,
        rates={"fixture-model": {"input_per_million": 0.1, "output_per_million": 0.2}},
    )
    observations = {"requests": [], "provider_responses": [], "guard_failures": []}
    payload = {
        "model": "fixture-model",
        "max_tokens": 700,
        "messages": [],
        "response_format": {"json_schema": {"name": "QuickTakeDraft"}},
    }
    with ExitStack() as stack:
        install_http_guards(stack, guard=guard, observations=observations, live=True)
        with httpx.Client() as client:
            client.post("https://openrouter.ai/api/v1/chat/completions", json=payload)
            with pytest.raises(ValueError, match="prior_guard_failure"):
                client.post("https://openrouter.ai/api/v1/chat/completions", json=payload)
    assert len(calls) == 1
    assert (
        cost_accounting(guard=guard, observations=observations)["cost_complete"] is False
    )


def test_paid_probe_refuses_missing_resolved_launch_metadata() -> None:
    from pathlib import Path

    from argus.api.schemas import BacktestRun

    from tests.evals.result_readout_eval import load_fixture_set
    from tests.evals.result_readout_probe import production_quick_take_payload

    case = load_fixture_set(
        Path(__file__).with_name("result_readout_fixtures.json"), live=False
    )["cases"][0]
    with pytest.raises(ValueError, match="stored_launch_metadata_required"):
        production_quick_take_payload(
            run=BacktestRun.model_validate(case["run"]),
            prompt=case["prompts"]["en"],
            language="en",
            synthetic=False,
        )


def test_quick_take_payload_uses_launch_envelope_and_sibling_card() -> None:
    from pathlib import Path

    from argus.api.schemas import BacktestRun

    from tests.evals.result_readout_eval import load_fixture_set
    from tests.evals.result_readout_probe import production_quick_take_payload

    case = load_fixture_set(
        Path(__file__).with_name("result_readout_fixtures.json"), live=False
    )["cases"][0]
    run = BacktestRun.model_validate(case["run"])
    run.config_snapshot["resolved_strategy"] = {
        "strategy_type": "buy_and_hold",
        "asset_universe": run.symbols,
    }
    run.config_snapshot["resolved_parameters"] = {
        "date_range": run.conversation_result_card["date_range"],
        "timeframe": "1D",
        "capital_amount": 1000,
        "sizing_mode": "capital_amount",
        "engine_config": {"starting_capital": 1000},
        "data_coverage": {"outcome": "adjusted_coverage"},
    }
    run.conversation_result_card["chart"] = {"equity": [{"value": 1123.4}]}
    result = production_quick_take_payload(
        run=run, prompt=case["prompts"]["en"], language="en", synthetic=False
    )
    assert result["envelope"]["execution_status"] == "succeeded"
    assert (
        result["envelope"]["resolved_parameters"]
        == run.config_snapshot["resolved_parameters"]
    )
    assert result["envelope"]["metrics"] == run.metrics
    assert "chart" not in result["envelope"]
    assert result["result_card"]["chart"] == run.conversation_result_card["chart"]
    assert "comparable_same_period" not in json.dumps(result)
    assert result["explanation_context"]["result_card"] == result["result_card"]


@pytest.mark.parametrize("failure", [asyncio.CancelledError, BaseException])
def test_canceled_probe_preserves_charged_attempt_without_inventing_a_frame(
    monkeypatch: pytest.MonkeyPatch, failure: type[BaseException]
) -> None:
    from pathlib import Path

    from argus.llm import openrouter, openrouter_key_policy

    from tests.evals.result_readout_eval import load_fixture_set, measurement_can_continue
    from tests.evals.result_readout_probe import run_probe

    monkeypatch.setattr(openrouter, "resolve_openrouter_api_key", lambda: "test-only")
    monkeypatch.setattr(
        openrouter_key_policy, "resolve_openrouter_api_key", lambda: "test-only"
    )
    monkeypatch.setenv("ARGUS_CHAT_MODEL", "fixture-model")
    monkeypatch.setenv("ARGUS_CHAT_FALLBACK_MODEL", "")

    async def fail(*args, **kwargs):
        raise failure("secret-test-value")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail)
    case = load_fixture_set(
        Path(__file__).with_name("result_readout_fixtures.json"), live=False
    )["cases"][0]
    report = run_probe(
        {
            "case": case,
            "language": "en",
            "live": True,
            "budget_usd": 4,
            "rates": {
                "fixture-model": {"input_per_million": 0.1, "output_per_million": 0.2}
            },
        }
    )
    assert report["http_attempts"] == report["unknown_cost_attempts"] == 1
    assert report["accounted_upper_bound_usd"] == report["reserved_usd"]
    assert not report["cost_complete"]
    assert report["all_attempts_reserved"]
    assert not measurement_can_continue(report)
    assert "quick_take" not in report
    assert "breakdown" not in report
    assert "secret-test-value" not in json.dumps(report)
