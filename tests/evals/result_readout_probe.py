"""One isolated pair of real composer calls; invoked by result_readout_eval."""

from __future__ import annotations

import asyncio
import copy
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

try:
    from .result_readout_eval import TASK_OUTPUT_LIMITS, CostGuard, encoded, sha256
except ImportError:  # Direct script entry in the other checkout's subprocess.
    from result_readout_eval import TASK_OUTPUT_LIMITS, CostGuard, encoded, sha256


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

    def before(url: Any, kwargs: dict[str, Any]) -> tuple[str, float]:
        payload = kwargs.get("json", {})
        schema = payload.get("response_format", {}).get("json_schema", {}).get("name")
        task = {
            "QuickTakeDraft": "result_summary",
            "ResultBreakdownDraft": "result_breakdown",
        }.get(schema)
        try:
            if not live or str(url) != "https://openrouter.ai/api/v1/chat/completions":
                raise ValueError("network_not_authorized")
            if task is None:
                raise ValueError("unexpected_provider_task")
            guard.reserve(payload, task=task)
        except ValueError as exc:
            observations["guard_failures"].append(str(exc))
            raise
        observations["requests"].append(
            {
                "task": task,
                "model": payload["model"],
                "payload_sha256": sha256(encoded(payload)),
                "payload_bytes": len(encoded(payload)),
                "max_output_tokens": payload["max_tokens"],
            }
        )
        return task, time.monotonic()

    def after(response: Any, task: str, started: float) -> Any:
        try:
            data = response.json()
        except ValueError:
            data = {}
        drafts = [
            choice.get("message", {}).get("content") for choice in data.get("choices", [])
        ]
        usage = data.get("usage", {})
        observations["provider_responses"].append(
            {
                "task": task,
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
        return response

    async def async_post(self: Any, url: Any, **kwargs: Any) -> Any:
        task, started = before(url, kwargs)
        return after(await original_async(self, url, **kwargs), task, started)

    def sync_post(self: Any, url: Any, **kwargs: Any) -> Any:
        task, started = before(url, kwargs)
        return after(original_sync(self, url, **kwargs), task, started)

    def other_network(*args: Any, **kwargs: Any) -> Any:
        observations["guard_failures"].append("unexpected_network_method")
        raise ValueError("unexpected_network_method")

    stack.enter_context(patch.object(httpx.AsyncClient, "post", async_post))
    stack.enter_context(patch.object(httpx.Client, "post", sync_post))
    for method in ("get", "put", "patch", "delete"):
        stack.enter_context(patch.object(httpx.AsyncClient, method, other_network))
        stack.enter_context(patch.object(httpx.Client, method, other_network))


def run_probe(request: dict[str, Any]) -> dict[str, Any]:
    from contextlib import ExitStack

    from argus.agent_runtime.stages import explain
    from argus.agent_runtime.state import RunState
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
    guard = CostGuard(budget_usd=request["budget_usd"], rates=request["rates"])

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
                }
            )
        return None

    async def dry_async_completion(**kwargs: Any) -> None:
        return dry_completion(**kwargs)

    config = run.config_snapshot
    engine = config.get("engine_config", config)
    date_range = run.conversation_result_card.get("date_range")
    strategy_type = engine.get("template", config.get("strategy_type", "buy_and_hold"))
    state = RunState.new(
        current_user_message=request["case"]["prompts"][language],
        recent_thread_history=[],
    )
    state.confirmation_payload = {
        "strategy": {
            "strategy_type": strategy_type,
            "asset_universe": run.symbols,
            "date_range": date_range,
            "asset_class": run.asset_class,
            "benchmark_symbol": run.benchmark_symbol,
        },
        "optional_parameters": engine,
    }
    performance = run.metrics.get("aggregate", {}).get("performance", {})
    benchmark = performance.get("benchmark_return_pct")
    # Reconstruct the documented completed-turn envelope from canonical stored
    # fields; no market figure is authored or recalculated by the harness.
    state.final_response_payload = {
        "result": run.model_dump(mode="json"),
        "explanation_context": {
            "metrics": run.metrics,
            "benchmark_metrics": {"benchmark_return_pct": benchmark},
            "benchmark_symbol": run.benchmark_symbol,
            "comparable_same_period": True,
            "resolved_parameters": engine,
            "config_snapshot": run.config_snapshot,
            "strategy_type": strategy_type,
        },
    }
    openrouter.clear_openrouter_route_receipts()
    with ExitStack() as stack:
        install_http_guards(stack, guard=guard, observations=observations, live=live)
        if not live:
            stack.enter_context(
                patch.object(
                    explain, "invoke_openrouter_json_schema", dry_async_completion
                )
            )
        quick_started = time.monotonic()
        quick = asyncio.run(
            explain.explain_stage_async(state=state, language=language)
        ).stage_patch
        quick_fallback = bool(quick.get("assistant_response_fallback_used", True))
        quick_text = quick.get("assistant_response", "")
        observations["quick_take"] = {
            "complete_text": quick_text,
            "accepted_text": None if quick_fallback else quick_text,
            "source": quick.get("assistant_response_source"),
            "fallback_used": quick_fallback,
            "failure_mode": quick.get("assistant_response_failure_mode"),
            "latency_ms": round((time.monotonic() - quick_started) * 1000),
        }
        # This is a new composition against the fixture, not an edit to history.
        # Candidate Breakdown receives exactly its paired accepted Quick take.
        run.conversation_result_card["result_readout_content"] = {
            "schema_version": "result_readout/v1",
            "surface": "quick_take",
            "language": language,
            "text": None if quick_fallback else quick_text,
        }
        context = breakdown.result_breakdown_context(run)
        deeper_started = time.monotonic()
        kwargs = {} if live else {"invoke_json_schema_func": dry_completion}
        deeper = breakdown.llm_result_breakdown_message(
            context, language=language, **kwargs
        )
        fallback_text = breakdown.fallback_result_breakdown_message(
            context, language=language
        )
        observations["breakdown"] = {
            "complete_text": deeper if deeper else fallback_text,
            "accepted_text": deeper,
            "source": "llm_breakdown_stage" if deeper else "deterministic_fallback",
            "fallback_used": not bool(deeper),
            "failure_mode": None if deeper else "llm_unavailable_or_contract_rejected",
            "latency_ms": round((time.monotonic() - deeper_started) * 1000),
        }
    observations["route_receipts"] = [
        receipt.as_dict() for receipt in openrouter.get_openrouter_route_receipts()
    ]
    observations["reserved_usd"] = guard.reserved_usd
    observations["http_attempts"] = guard.attempts
    responses = observations["provider_responses"]
    observations["cost_complete"] = (
        bool(responses)
        and all(isinstance(row["usage"].get("cost"), (int, float)) for row in responses)
        and len(responses) == guard.attempts
    )
    observations["observed_cost_usd"] = (
        sum(row["usage"].get("cost", 0) or 0 for row in responses)
        if observations["cost_complete"]
        else None
    )
    return observations


def main() -> None:
    request = json.loads(sys.stdin.read())
    sys.path.insert(0, str(Path(request["checkout"]) / "src"))
    try:
        result = run_probe(request)
    except Exception as exc:
        result = {"error": type(exc).__name__}
    sys.stdout.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")


if __name__ == "__main__":
    main()
