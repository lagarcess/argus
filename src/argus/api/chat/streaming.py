from __future__ import annotations

import json
from typing import Any

from loguru import logger

from argus.api import state as api_state


def sse_data(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"


def fetch_run_metrics(user_id: str, run_id: str) -> dict[str, Any] | None:
    run = None
    if api_state.supabase_gateway is not None:
        try:
            run = api_state.supabase_gateway.get_backtest_run(
                user_id=user_id, run_id=run_id
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch run for result explanation",
                error=str(exc),
                run_id=run_id,
            )
    if run is None:
        run = api_state.store.backtest_runs.get(run_id)
    if run is None:
        return None
    return {
        "aggregate": run.metrics.get("aggregate", {}),
        "by_symbol": run.metrics.get("by_symbol", {}),
        "config": run.config_snapshot,
    }


def assistant_copy_for_result(symbols: list[str], language: str) -> str:
    joined = ", ".join(symbols)
    if language.startswith("es"):
        return (
            f"\u00a1Listo! Aqu\u00ed tienes los resultados del backtest para "
            f"{joined}. \u00bfQu\u00e9 te parecen estas m\u00e9tricas?"
        )
    return f"Done! Here are the backtest results for {joined}. What do you think about these metrics?"


def runtime_result_message(runtime_result: dict[str, Any]) -> str | None:
    assistant_response = runtime_result.get("assistant_response")
    if isinstance(assistant_response, str) and assistant_response:
        return assistant_response
    assistant_prompt = runtime_result.get("assistant_prompt")
    if isinstance(assistant_prompt, str) and assistant_prompt:
        return assistant_prompt
    return None


def runtime_stage_status(runtime_result: dict[str, Any]) -> str:
    stage_outcome = runtime_result.get("stage_outcome")
    if isinstance(stage_outcome, str) and stage_outcome:
        return stage_outcome
    return "agent_runtime_turn"


def runtime_result_card(runtime_result: dict[str, Any]) -> dict[str, Any] | None:
    final_payload = runtime_result.get("final_response_payload")
    if not isinstance(final_payload, dict):
        return None
    result_card = final_payload.get("result_card")
    if isinstance(result_card, dict):
        return result_card
    return None


def runtime_result_envelope(runtime_result: dict[str, Any]) -> dict[str, Any]:
    final_payload = runtime_result.get("final_response_payload")
    if not isinstance(final_payload, dict):
        return {}
    result = final_payload.get("result")
    return dict(result) if isinstance(result, dict) else {}
