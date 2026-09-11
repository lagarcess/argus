"""One isolated pair of real composer calls; invoked by result_readout_eval."""

from __future__ import annotations

import asyncio
import copy
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

try:
    from .result_readout_eval import (
        MAX_INPUT_BYTES,
        CostGuard,
        encoded,
        sha256,
    )
except ImportError:  # Direct script entry in the other checkout's subprocess.
    from result_readout_eval import (
        MAX_INPUT_BYTES,
        CostGuard,
        encoded,
        sha256,
    )

PRIOR_QUICK_TAKE_ALLOWANCE_BYTES = 8192  # Free sizing stress, not a prose limit.


def install_http_guards(
    stack: Any, *, guard: CostGuard, observations: dict[str, Any], live: bool
) -> None:
    """One HTTP boundary for OpenRouter and the Perplexity Agent client."""
    import httpx

    original_async = httpx.AsyncClient.request
    original_sync = httpx.Client.request

    def before(
        method: str, url: Any, kwargs: dict[str, Any]
    ) -> tuple[dict[str, Any], float]:
        payload = kwargs.get("json", {})
        endpoints = {
            "https://openrouter.ai/api/v1/chat/completions": (
                "result_summary",
                "openrouter",
                "QuickTakeDraft",
            ),
            "https://api.perplexity.ai/v1/agent": (
                "result_breakdown",
                "perplexity_agent",
                "ResultBreakdownDraft",
            ),
        }
        destination = endpoints.get(str(url))
        task, provider, schema = destination or (None, None, None)
        if (
            not observations["guard_failures"]
            and task
            and guard.by_task.get(task, 0) >= 1
        ):
            observations["blocked_dispatches"].append(
                {"task": task, "provider": provider, "reason": "single_attempt_policy"}
            )
            raise ValueError("single_attempt_policy")
        try:
            if observations["guard_failures"]:
                raise ValueError("prior_guard_failure")
            if not live or method.upper() != "POST" or destination is None:
                raise ValueError("network_not_authorized")
            if (
                payload.get("response_format", {}).get("json_schema", {}).get("name")
                != schema
            ):
                raise ValueError("unexpected_provider_task")
            reservation = guard.reserve(payload, task=task)
        except ValueError as exc:
            observations["guard_failures"].append(str(exc))
            raise
        receipt = {
            "attempt_id": guard.attempts,
            "task": task,
            "provider": provider,
            "model": guard.tasks[task]["model"],
            "reserved_usd": reservation,
            "outcome": "pending",
            "http_status": None,
            "payload_sha256": sha256(encoded(payload)),
            "payload_bytes": len(encoded(payload)),
            "max_output_tokens": guard.tasks[task]["max_output_tokens"],
        }
        observations["requests"].append(receipt)
        return receipt, time.monotonic()

    def after(response: Any, receipt: dict[str, Any], started: float) -> Any:
        try:
            document = response.json()
        except ValueError:
            document = None
        data = document if isinstance(document, dict) else {}
        raw_usage = data.get("usage")
        usage = raw_usage if isinstance(raw_usage, dict) else {}

        def items(value: Any) -> list[Any]:
            return value if isinstance(value, list) else []

        if receipt["provider"] == "openrouter":
            drafts = [
                choice["message"].get("content")
                for choice in items(data.get("choices"))
                if isinstance(choice, dict) and isinstance(choice.get("message"), dict)
            ]
            reported_cost = usage.get("cost")
        else:
            drafts = [
                chunk.get("text")
                for item in items(data.get("output"))
                if isinstance(item, dict) and item.get("type") == "message"
                for chunk in items(item.get("content"))
                if isinstance(chunk, dict) and chunk.get("type") == "output_text"
            ]
            cost = usage.get("cost")
            reported_cost = (
                cost.get("total_cost")
                if isinstance(cost, dict) and cost.get("currency") == "USD"
                else None
            )
        latency = round((time.monotonic() - started) * 1000)
        receipt.update(
            http_status=response.status_code,
            outcome="succeeded" if response.is_success else "failed",
            latency_ms=latency,
        )
        if not response.is_success:
            receipt["error"] = {
                "code": f"provider_http_{response.status_code}",
                "message": "Provider returned an unsuccessful HTTP status.",
            }
        observations["provider_responses"].append(
            {
                "attempt_id": receipt["attempt_id"],
                "task": receipt["task"],
                "provider": receipt["provider"],
                "http_status": response.status_code,
                "model": data.get("model"),
                "provider_response_id": data.get("id"),
                "raw_drafts": drafts,
                "raw_response": document,
                "raw_response_text": response.text,
                "raw_usage": raw_usage,
                "usage": {"cost": reported_cost},
                "latency_ms": latency,
            }
        )
        cost_accounting(guard=guard, observations=observations)
        return response

    def failed(exc: BaseException, receipt: dict[str, Any], started: float) -> None:
        receipt.update(
            outcome="canceled" if isinstance(exc, asyncio.CancelledError) else "failed",
            latency_ms=round((time.monotonic() - started) * 1000),
            error=safe_provider_error(exc),
        )

    async def async_request(self: Any, method: str, url: Any, **kwargs: Any) -> Any:
        receipt, started = before(method, url, kwargs)
        try:
            response = await original_async(self, method, url, **kwargs)
        except BaseException as exc:
            failed(exc, receipt, started)
            raise
        return after(response, receipt, started)

    def sync_request(self: Any, method: str, url: Any, **kwargs: Any) -> Any:
        receipt, started = before(method, url, kwargs)
        try:
            response = original_sync(self, method, url, **kwargs)
        except BaseException as exc:
            failed(exc, receipt, started)
            raise
        return after(response, receipt, started)

    stack.enter_context(patch.object(httpx.AsyncClient, "request", async_request))
    stack.enter_context(patch.object(httpx.Client, "request", sync_request))


def safe_provider_error(exc: BaseException) -> dict[str, str]:
    """Do not retain exception text: it can contain credentials or request bodies."""
    canceled = isinstance(exc, asyncio.CancelledError)
    return {
        "code": "provider_request_canceled" if canceled else "provider_request_failed",
        "type": type(exc).__name__,
        "message": "Provider request was canceled before a response was recorded."
        if canceled
        else "Provider request failed before a response was recorded.",
    }


def cost_accounting(*, guard: CostGuard, observations: dict[str, Any]) -> dict[str, Any]:
    """Known actuals plus reserved unknowns, never a fabricated complete invoice."""
    requests = observations["requests"]
    reservations = {row["attempt_id"]: row["reserved_usd"] for row in requests}

    def valid(value: Any) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )

    all_reserved = (
        len(requests) == guard.attempts
        and set(reservations) == set(range(1, guard.attempts + 1))
        and all(valid(value) for value in reservations.values())
        and math.isclose(sum(reservations.values()), guard.reserved_usd, abs_tol=1e-12)
    )
    known: dict[int, float] = {}
    failures = observations["guard_failures"]
    for response in observations["provider_responses"]:
        attempt = response["attempt_id"]
        if attempt not in reservations or attempt in known:
            all_reserved = False
            continue
        cost = response["usage"].get("cost")
        if cost is None:
            continue
        failure = None
        if not valid(cost):
            failure = "invalid_provider_cost"
        else:
            known[attempt] = cost
            if cost > reservations[attempt] + 1e-12:
                failure = "provider_cost_exceeds_reservation"
                all_reserved = False
        if failure and failure not in failures:
            failures.append(failure)
    unknown = set(reservations) - known.keys()
    observed = sum(known.values())
    unknown_reserved = sum(reservations[attempt] for attempt in unknown)
    return {
        "reserved_usd": guard.reserved_usd,
        "http_attempts": guard.attempts,
        "observed_cost_usd": observed,
        "unknown_cost_attempts": len(unknown),
        "unknown_cost_reserved_usd": unknown_reserved,
        "accounted_upper_bound_usd": observed + unknown_reserved,
        "cost_complete": bool(requests) and not unknown and not failures and all_reserved,
        "all_attempts_reserved": all_reserved,
    }


def production_quick_take_payload(
    *, run: Any, prompt: str, language: str, synthetic: bool
) -> dict[str, Any]:
    """Restore the actual launch envelope; the sibling card owns its chart.

    A genuine saved run must retain its canonical resolved launch fields.
    Synthetic free fixtures intentionally lack that provenance, so their
    minimal launch parameters are authored harness inputs, never live evidence.
    """
    from argus.domain.dca_capital import dca_capital_plan_from_config
    from argus.domain.engine_launch.models import (
        LaunchBacktestRequest,
        LaunchExecutionEnvelope,
    )
    from argus.domain.engine_launch.results import (
        build_benchmark_metrics,
        build_explanation_context,
    )

    config = run.config_snapshot
    strategy = copy.deepcopy(config.get("resolved_strategy"))
    parameters = copy.deepcopy(config.get("resolved_parameters"))
    if not isinstance(strategy, dict) or not isinstance(parameters, dict):
        if not synthetic:
            raise ValueError("stored_launch_metadata_required")
        # TEST ONLY: these shapes describe the committed free examples. They
        # are not a backwards inference rule for real engine templates.
        template = config["template"]
        strategy = {
            "strategy_type": "signal_strategy"
            if template == "sma_crossover"
            else template,
            "asset_universe": run.symbols,
        }
        parameters = {
            "date_range": run.conversation_result_card["date_range"],
            "timeframe": config["timeframe"],
            "sizing_mode": "capital_amount",
            "capital_amount": config.get("starting_capital"),
            "engine_config": copy.deepcopy(config),
        }
        if template == "dca_accumulation":
            plan = dca_capital_plan_from_config(config)
            parameters.update(
                capital_amount=plan.contribution,
                recurring_contribution=plan.contribution,
                starting_capital=plan.starting_capital,
                cadence=plan.period,
            )
    request = {
        key: parameters[key]
        for key in LaunchBacktestRequest.model_fields
        if key in parameters
    }
    request.update(
        strategy_type=strategy["strategy_type"],
        symbol=run.symbols[0],
        symbols=run.symbols,
        asset_class=run.asset_class,
        benchmark_symbol=run.benchmark_symbol,
        language=language,
    )
    for key in ("entry_rule", "exit_rule", "rule_spec"):
        if key in strategy:
            request[key] = strategy[key]
    typed_request = LaunchBacktestRequest.model_validate(request)
    card = copy.deepcopy(run.conversation_result_card)
    # Stored prose is not the newly measured composition. In particular an
    # saved readout may not leak into the fresh Quick take input.
    card.pop("result_readout_content", None)
    envelope = LaunchExecutionEnvelope(
        execution_status="succeeded",
        resolved_strategy=strategy,
        resolved_parameters=parameters,
        metrics=run.metrics,
        benchmark_metrics=build_benchmark_metrics(
            request=typed_request,
            metrics=run.metrics,
            benchmark_symbol=run.benchmark_symbol,
        ),
        assumptions=card.get("assumptions", []),
        caveats=[],
        provider_metadata={},
    )
    return {
        "request": {
            **typed_request.model_dump(mode="json", by_alias=True),
            "raw_user_phrasing": prompt,
        },
        "envelope": envelope.model_dump(mode="json"),
        "result_card": card,
        "explanation_context": build_explanation_context(
            request=typed_request, envelope=envelope, result_card=card
        ),
        "language": language,
    }


def run_probe(request: dict[str, Any]) -> dict[str, Any]:
    from contextlib import ExitStack

    from argus.agent_runtime import result_readout
    from argus.agent_runtime.stages import explain
    from argus.api.chat import breakdown
    from argus.api.schemas import BacktestRun
    from argus.domain.research import billing
    from argus.domain.research.contracts import ResearchUnavailableError
    from argus.domain.research.credentials import perplexity_api_key
    from argus.domain.research.perplexity_agent import PerplexityAgentClient
    from argus.llm import openrouter
    from argus.llm.openrouter_key_policy import resolve_openrouter_api_key

    language, live = request["language"], request["live"]
    run = BacktestRun.model_validate(copy.deepcopy(request["case"]["run"]))
    profile = openrouter.openrouter_profile_for_task("result_summary")
    models = openrouter.openrouter_model_candidates(task="result_summary")
    if openrouter.openrouter_model_tier_for_task("result_summary") != "readout":
        raise ValueError("readout_tier_required")
    if models and models != [breakdown.RESULT_BREAKDOWN_MODEL]:
        raise ValueError("luna_only_readout_required")
    spec = breakdown.result_breakdown_spec(language)
    configuration = {
        "python_version": platform.python_version(),
        "llm_mode": "live_provider" if live else "preflight_no_calls",
        "market_data_provider_mode": "recorded_run_fixture_no_fetch",
        "asset_provider_mode": "recorded_run_fixture_no_fetch",
        "credentials_present": {
            "openrouter": bool(resolve_openrouter_api_key()),
            "perplexity_agent": bool(perplexity_api_key()),
        },
        "credential_present": bool(
            resolve_openrouter_api_key() and perplexity_api_key() and models
        ),
        "max_input_bytes": request.get("max_input_bytes", MAX_INPUT_BYTES),
        "tasks": {
            "result_summary": {
                "provider": "openrouter",
                "tier": "readout",
                "model": models[0] if models else "",
                "max_output_tokens": profile.max_tokens,
                "timeout_seconds": profile.timeout_seconds,
                "temperature": profile.temperature,
                "reasoning_effort": profile.reasoning_effort,
            },
            "result_breakdown": {
                "provider": "perplexity_agent",
                "model": spec.model,
                "max_output_tokens": spec.max_output_tokens,
                "timeout_seconds": spec.timeout_seconds,
            },
        },
    }
    if live:
        if not configuration["credential_present"]:
            raise ValueError("missing_provider_credential")
        previous = request["preflight_configuration"]
        for task, current in configuration["tasks"].items():
            if any(
                previous["tasks"][task].get(key) != value
                for key, value in current.items()
            ):
                raise ValueError("provider_configuration_changed_after_preflight")
        configuration["tasks"]["result_breakdown"]["request_limits"] = previous["tasks"][
            "result_breakdown"
        ]["request_limits"]
    observations = {
        "configuration": configuration,
        "requests": [],
        "provider_responses": [],
        "guard_failures": [],
        "blocked_dispatches": [],
        "preflight_payloads": [],
        "unpriced_spend": [],
        "composition_mode": "Fresh composition from saved run, no persistence; one HTTP request per frame.",
    }
    guard = CostGuard(
        budget_usd=request["budget_usd"],
        rates=request["rates"],
        tasks=configuration["tasks"],
        max_input_bytes=configuration["max_input_bytes"],
    )

    def capture_payload(task: str, payload: dict[str, Any]) -> None:
        allowance = PRIOR_QUICK_TAKE_ALLOWANCE_BYTES if task == "result_breakdown" else 0
        observations["preflight_payloads"].append(
            {
                "task": task,
                "provider": configuration["tasks"][task]["provider"],
                "model": configuration["tasks"][task]["model"],
                "bytes": len(encoded(payload)),
                "payload_sha256": sha256(encoded(payload)),
                "prior_quick_take_allowance_bytes": allowance,
                "bytes_with_prior_quick_take_allowance": len(encoded(payload))
                + allowance,
            }
        )

    async def dry_quick(**kwargs: Any) -> None:
        payload = openrouter._json_schema_payload(
            model=models[0] if models else "UNCONFIGURED",
            messages=kwargs["messages"],
            schema_model=kwargs["schema_model"],
            schema_name=kwargs["schema_name"],
            profile=profile,
        )
        capture_payload("result_summary", payload)
        return None

    def dry_agent_post(
        self: Any, payload: dict[str, Any], *, timeout_seconds: float
    ) -> Any:
        configuration["tasks"]["result_breakdown"]["request_limits"] = {
            key: payload[key]
            for key in (
                "models",
                "max_steps",
                "max_output_tokens",
                "max_tool_calls",
                "parallel_tool_calls",
                "tools",
            )
            if key in payload
        }
        capture_payload("result_breakdown", payload)
        raise ResearchUnavailableError("preflight_no_calls")

    def outcome(result: Any, started: float) -> dict[str, Any]:
        return {
            "complete_text": result.text,
            "accepted_text": None if result.fallback_used else result.text,
            "source": result.source,
            "fallback_used": result.fallback_used,
            "failure_mode": result.failure_mode,
            "latency_ms": round((time.monotonic() - started) * 1000),
        }

    quick_payload = production_quick_take_payload(
        run=run,
        prompt=request["case"]["prompts"][language],
        language=language,
        synthetic=request["case"]["source"]["kind"] == "synthetic_test_only",
    )
    observations["quick_take_input"] = {
        "owner": "result_readout_with_metadata_from_backtest_payload_async",
        "payload_sha256": sha256(encoded(quick_payload)),
        "resolved_launch_metadata_recorded": request["case"]["source"]["kind"]
        != "synthetic_test_only",
    }
    openrouter.clear_openrouter_route_receipts()
    with ExitStack() as stack:
        install_http_guards(stack, guard=guard, observations=observations, live=live)
        stack.enter_context(
            patch.object(
                billing,
                "_recorder",
                lambda spend: observations["unpriced_spend"].append(
                    spend.model_dump(mode="json")
                ),
            )
        )
        if not live:
            stack.enter_context(
                patch.object(explain, "invoke_openrouter_json_schema", dry_quick)
            )
            stack.enter_context(
                patch.object(PerplexityAgentClient, "_post", dry_agent_post)
            )
        try:
            started = time.monotonic()
            quick = asyncio.run(
                result_readout.result_readout_with_metadata_from_backtest_payload_async(
                    **quick_payload
                )
            )
            observations["quick_take"] = outcome(quick, started)
            run.conversation_result_card["result_readout_content"] = {
                "schema_version": "result_readout/v1",
                "surface": "quick_take",
                "language": language,
                "text": None if quick.fallback_used else quick.text,
            }
            started = time.monotonic()
            deeper = breakdown.result_breakdown_message_with_metadata(
                run, language=language, client=PerplexityAgentClient(perplexity_api_key())
            )
            observations["breakdown"] = {
                **outcome(deeper, started),
                "sources": [source.model_dump(mode="json") for source in deeper.sources],
                "usage": deeper.usage.model_dump(mode="json")
                if deeper.usage is not None
                else None,
            }
        except BaseException as exc:
            observations["interruption"] = safe_provider_error(exc)
            observations["stop_requested"] = True
    observations["route_receipts"] = [
        receipt.as_dict() for receipt in openrouter.get_openrouter_route_receipts()
    ]
    observations.update(cost_accounting(guard=guard, observations=observations))
    observations["attempt_receipts_complete"] = all(
        row["outcome"] != "pending" for row in observations["requests"]
    )
    return observations


def main() -> None:
    request = json.loads(sys.stdin.read())
    sys.path.insert(0, str(Path(request["checkout"]) / "src"))
    try:
        result = run_probe(request)
    except BaseException as exc:
        result = {"error": type(exc).__name__}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
