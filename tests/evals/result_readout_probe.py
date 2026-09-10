"""One isolated pair of real composer calls; invoked by result_readout_eval."""

from __future__ import annotations

import asyncio
import copy
import json
import math
import os
import platform
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

try:
    from .result_readout_eval import (
        MAX_ATTEMPTS,
        MAX_INPUT_BYTES,
        TASK_OUTPUT_LIMITS,
        CostGuard,
        encoded,
        sha256,
    )
except ImportError:  # Direct script entry in the other checkout's subprocess.
    from result_readout_eval import (
        MAX_ATTEMPTS,
        MAX_INPUT_BYTES,
        TASK_OUTPUT_LIMITS,
        CostGuard,
        encoded,
        sha256,
    )

PRIOR_QUICK_TAKE_ALLOWANCE_BYTES = 8192  # Free sizing stress, not a prose limit.


def install_http_guards(
    stack: Any,
    *,
    guard: CostGuard,
    observations: dict[str, Any],
    live: bool,
) -> None:
    """Intercept every real HTTP attempt, including provider fallback/retries."""
    import httpx

    original_async = httpx.AsyncClient.post
    original_sync = httpx.Client.post

    def before(url: Any, kwargs: dict[str, Any]) -> tuple[dict[str, Any], float]:
        payload = kwargs.get("json", {})
        schema = payload.get("response_format", {}).get("json_schema", {}).get("name")
        task = {
            "QuickTakeDraft": "result_summary",
            "ResultBreakdownDraft": "result_breakdown",
        }.get(schema)
        try:
            if observations["guard_failures"]:
                raise ValueError("prior_guard_failure")
            if observations.get("http_closed"):
                raise ValueError("probe_finalized")
            if not live or str(url) != "https://openrouter.ai/api/v1/chat/completions":
                raise ValueError("network_not_authorized")
            if task is None:
                raise ValueError("unexpected_provider_task")
            reservation = guard.reserve(payload, task=task)
        except ValueError as exc:
            observations["guard_failures"].append(str(exc))
            raise
        receipt = {
            "attempt_id": guard.attempts,
            "task": task,
            "model": payload["model"],
            "reserved_usd": reservation,
            "outcome": "pending",
            "http_status": None,
            "payload_sha256": sha256(encoded(payload)),
            "payload_bytes": len(encoded(payload)),
            "max_output_tokens": payload["max_tokens"],
        }
        observations["requests"].append(receipt)
        return receipt, time.monotonic()

    def after(response: Any, receipt: dict[str, Any], started: float) -> Any:
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        drafts = [
            choice.get("message", {}).get("content") for choice in data.get("choices", [])
        ]
        usage = data.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        receipt.update(
            {
                "http_status": response.status_code,
                "outcome": "succeeded" if response.is_success else "failed",
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
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
                "http_status": response.status_code,
                "model": data.get("model"),
                "raw_drafts": drafts,
                "usage": {
                    key: usage[key]
                    for key in (
                        "prompt_tokens",
                        "completion_tokens",
                        "total_tokens",
                        "cost",
                    )
                    if key in usage
                },
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
        )
        # Stop subsequent retries immediately if returned billing evidence
        # contradicts the amount reserved before this request.
        cost_accounting(guard=guard, observations=observations)
        return response

    def failed(exc: BaseException, receipt: dict[str, Any], started: float) -> None:
        canceled = isinstance(exc, asyncio.CancelledError)
        receipt.update(
            {
                "outcome": "canceled" if canceled else "failed",
                "latency_ms": round((time.monotonic() - started) * 1000),
                "error": safe_provider_error(exc),
            }
        )

    async def async_post(self: Any, url: Any, **kwargs: Any) -> Any:
        receipt, started = before(url, kwargs)
        try:
            response = await original_async(self, url, **kwargs)
        except BaseException as exc:
            failed(exc, receipt, started)
            raise
        return after(response, receipt, started)

    def sync_post(self: Any, url: Any, **kwargs: Any) -> Any:
        receipt, started = before(url, kwargs)
        try:
            response = original_sync(self, url, **kwargs)
        except BaseException as exc:
            failed(exc, receipt, started)
            raise
        return after(response, receipt, started)

    def other_network(*args: Any, **kwargs: Any) -> Any:
        observations["guard_failures"].append("unexpected_network_method")
        raise ValueError("unexpected_network_method")

    stack.enter_context(patch.object(httpx.AsyncClient, "post", async_post))
    stack.enter_context(patch.object(httpx.Client, "post", sync_post))
    for method in ("get", "put", "patch", "delete"):
        stack.enter_context(patch.object(httpx.AsyncClient, method, other_network))
        stack.enter_context(patch.object(httpx.Client, method, other_network))


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
    # accepted candidate readout may not leak into baseline Quick take input.
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


class CompletionTracker:
    """Observe a production worker's lifetime without changing its deadline."""

    def __init__(self, invoke: Any) -> None:
        self.invoke = invoke
        self.started = threading.Event()
        self.finished = threading.Event()

    def __call__(self, **kwargs: Any) -> Any:
        self.started.set()
        try:
            return self.invoke(**kwargs)
        finally:
            self.finished.set()

    def settle(self, timeout: float) -> bool:
        return not self.started.is_set() or self.finished.wait(timeout=max(0.0, timeout))


def run_probe(request: dict[str, Any]) -> dict[str, Any]:
    from contextlib import ExitStack

    from argus.agent_runtime import result_readout
    from argus.agent_runtime.stages import explain
    from argus.api.chat import breakdown
    from argus.api.schemas import BacktestRun
    from argus.llm import openrouter
    from argus.llm.openrouter_key_policy import resolve_openrouter_api_key

    language = request["language"]
    live = request["live"]
    run_data = copy.deepcopy(request["case"]["run"])
    run = BacktestRun.model_validate(run_data)
    configuration = {
        "python_version": platform.python_version(),
        "llm_mode": "live_provider" if live else "preflight_no_calls",
        "market_data_provider_mode": "recorded_run_fixture_no_fetch",
        "asset_provider_mode": "recorded_run_fixture_no_fetch",
        "credential_present": bool(resolve_openrouter_api_key()),
        "max_input_bytes": request.get("max_input_bytes", MAX_INPUT_BYTES),
        "tasks": {
            task: {
                "tier": openrouter.openrouter_model_tier_for_task(task),
                "models": openrouter.openrouter_model_candidates(task=task),
                "max_output_tokens": openrouter.openrouter_profile_for_task(
                    task
                ).max_tokens,
                "timeout_seconds": openrouter.openrouter_profile_for_task(
                    task
                ).timeout_seconds,
                "temperature": openrouter.openrouter_profile_for_task(task).temperature,
                "reasoning_effort": openrouter.openrouter_profile_for_task(
                    task
                ).reasoning_effort,
                "max_retries": openrouter.openrouter_profile_for_task(task).max_retries,
            }
            for task in TASK_OUTPUT_LIMITS
        },
    }
    if live and not configuration["credential_present"]:
        raise ValueError("missing_provider_credential")
    observations: dict[str, Any] = {
        "configuration": configuration,
        "requests": [],
        "provider_responses": [],
        "guard_failures": [],
        "preflight_payloads": [],
        "composition_mode": "fresh composition from a stored run fixture; no persistence",
    }
    guard = CostGuard(
        budget_usd=request["budget_usd"],
        rates=request["rates"],
        max_input_bytes=configuration["max_input_bytes"],
    )

    def dry_completion(**kwargs: Any) -> None:
        task = kwargs["task"]
        models = configuration["tasks"][task]["models"] or ["UNCONFIGURED"]
        for model in models:
            payload = openrouter._json_schema_payload(
                model=model,
                messages=kwargs["messages"],
                schema_model=kwargs["schema_model"],
                schema_name=kwargs["schema_name"],
                profile=openrouter.openrouter_profile_for_task(task),
            )
            observations["preflight_payloads"].append(
                {
                    "task": task,
                    "model": model,
                    "bytes": len(encoded(payload)),
                    "payload_sha256": sha256(encoded(payload)),
                    "prior_quick_take_allowance_bytes": PRIOR_QUICK_TAKE_ALLOWANCE_BYTES
                    if task == "result_breakdown"
                    else 0,
                    "bytes_with_prior_quick_take_allowance": len(encoded(payload))
                    + (
                        PRIOR_QUICK_TAKE_ALLOWANCE_BYTES
                        if task == "result_breakdown"
                        else 0
                    ),
                }
            )
        return None

    async def dry_async_completion(**kwargs: Any) -> None:
        return dry_completion(**kwargs)

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
    tracker = CompletionTracker(
        openrouter.invoke_openrouter_json_schema_sync if live else dry_completion
    )
    openrouter.clear_openrouter_route_receipts()
    with ExitStack() as stack:
        install_http_guards(stack, guard=guard, observations=observations, live=live)
        if not live:
            stack.enter_context(
                patch.object(
                    explain, "invoke_openrouter_json_schema", dry_async_completion
                )
            )
        try:
            quick_started = time.monotonic()
            quick = asyncio.run(
                result_readout.result_readout_with_metadata_from_backtest_payload_async(
                    **quick_payload
                )
            )
            observations["quick_take"] = {
                "complete_text": quick.text,
                "accepted_text": None if quick.fallback_used else quick.text,
                "source": quick.source,
                "fallback_used": quick.fallback_used,
                "failure_mode": quick.failure_mode,
                "latency_ms": round((time.monotonic() - quick_started) * 1000),
            }
            # This is a new composition against the fixture, not an edit to history.
            # Candidate Breakdown receives exactly its paired accepted Quick take.
            run.conversation_result_card["result_readout_content"] = {
                "schema_version": "result_readout/v1",
                "surface": "quick_take",
                "language": language,
                "text": None if quick.fallback_used else quick.text,
            }
            context = breakdown.result_breakdown_context(run)
            deeper_started = time.monotonic()
            detailed = getattr(breakdown, "_llm_result_breakdown_with_metadata", None)
            if detailed is not None:
                deeper, failure = detailed(
                    context, language=language, invoke_json_schema_func=tracker
                )
            else:
                deeper = breakdown.llm_result_breakdown_message(
                    context, language=language, invoke_json_schema_func=tracker
                )
                failure = None if deeper else "llm_unavailable_or_contract_rejected"
            fallback_text = breakdown.fallback_result_breakdown_message(
                context, language=language
            )
            observations["breakdown"] = {
                "complete_text": deeper if deeper else fallback_text,
                "accepted_text": deeper,
                "source": "llm_breakdown_stage" if deeper else "deterministic_fallback",
                "fallback_used": not bool(deeper),
                "failure_mode": failure,
                "latency_ms": round((time.monotonic() - deeper_started) * 1000),
            }
        except BaseException as exc:
            # Cancellation can escape a composer's ordinary fallback handler.
            # Preserve receipts without inventing a user-visible frame response.
            observations["interruption"] = safe_provider_error(exc)
            observations["stop_requested"] = True
        finally:
            settlement_started = time.monotonic()
            timeout = configuration["tasks"]["result_breakdown"]["timeout_seconds"]
            settled = tracker.settle(MAX_ATTEMPTS * timeout + 5)
            observations["provider_worker_settled"] = settled
            observations["receipt_settlement_ms"] = round(
                (time.monotonic() - settlement_started) * 1000
            )
            observations["http_closed"] = True
            if not settled:
                observations["guard_failures"].append("provider_worker_unsettled")
                observations["stop_requested"] = True
                observations["requires_process_exit"] = True
                # Keep late calls blocked until the isolated probe process exits.
                # Restoring HTTP methods while its worker lives would bypass the cap.
                stack.pop_all()
    observations = copy.deepcopy(observations)
    observations["route_receipts"] = [
        receipt.as_dict() for receipt in openrouter.get_openrouter_route_receipts()
    ]
    observations.update(cost_accounting(guard=guard, observations=observations))
    observations["attempt_receipts_complete"] = observations["provider_worker_settled"]
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
    if result.get("requires_process_exit"):
        # Only the standalone, owned subprocess uses this termination path.
        os._exit(0)


if __name__ == "__main__":
    main()
