from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from contextvars import copy_context
from dataclasses import dataclass
from threading import Thread
from typing import Any, TypeVar

from argus.agent_runtime.stages.explain import (
    RESULT_READOUT_SOURCE_DETERMINISTIC_FALLBACK,
    RESULT_READOUT_SOURCE_LLM,
    explain_stage_async,
)
from argus.agent_runtime.state.models import (
    ConfirmationPayload,
    FinalResponsePayload,
    RunState,
    StrategySummary,
)

RESULT_READOUT_SOURCE_UNAVAILABLE = "unavailable"
RESULT_READOUT_FAILURE_GENERATION_FAILED = "result_readout_generation_failed"
T = TypeVar("T")


@dataclass(frozen=True)
class ResultReadout:
    text: str | None
    source: str
    fallback_used: bool
    failure_mode: str | None = None


def result_readout_from_backtest_payload(
    *,
    request: dict[str, Any],
    envelope: dict[str, Any],
    result_card: dict[str, Any],
    explanation_context: dict[str, Any] | None,
    language: str | None = None,
) -> str | None:
    """Render backend-owned completed-result prose from canonical backtest payloads."""

    return result_readout_with_metadata_from_backtest_payload(
        request=request,
        envelope=envelope,
        result_card=result_card,
        explanation_context=explanation_context,
        language=language,
    ).text


def result_readout_with_metadata_from_backtest_payload(
    *,
    request: dict[str, Any],
    envelope: dict[str, Any],
    result_card: dict[str, Any],
    explanation_context: dict[str, Any] | None,
    language: str | None = None,
) -> ResultReadout:
    """Synchronously compose the completed-result prose and its provenance."""

    return _run_coroutine_sync(
        result_readout_with_metadata_from_backtest_payload_async(
            request=request,
            envelope=envelope,
            result_card=result_card,
            explanation_context=explanation_context,
            language=language,
        )
    )


async def result_readout_with_metadata_from_backtest_payload_async(
    *,
    request: dict[str, Any],
    envelope: dict[str, Any],
    result_card: dict[str, Any],
    explanation_context: dict[str, Any] | None,
    language: str | None = None,
) -> ResultReadout:
    """Render completed-result prose through the mainline async explain path."""

    normalized_context = _normalized_explanation_context(
        envelope=envelope,
        result_card=result_card,
        explanation_context=explanation_context,
    )
    state = RunState.new(
        current_user_message=_optional_str(
            request.get("raw_user_phrasing") or request.get("current_user_message")
        )
        or "",
        recent_thread_history=[],
    )
    state.confirmation_payload = ConfirmationPayload(
        strategy=_strategy_summary_from_payload(
            request=request,
            envelope=envelope,
            explanation_context=normalized_context,
        ),
        optional_parameters=_optional_parameters_from_request(request),
        launch_payload=dict(request),
        validation={},
    )
    state.final_response_payload = FinalResponsePayload(
        result=dict(envelope),
        result_card=dict(result_card),
        explanation_context=normalized_context,
    )

    result = await explain_stage_async(
        state=state,
        language=_optional_str(language or request.get("language")) or "en",
    )
    patch = result.stage_patch
    text = patch.get("assistant_response")
    source = _optional_str(patch.get("assistant_response_source"))
    fallback_used = bool(patch.get("assistant_response_fallback_used"))
    failure_mode = _optional_str(patch.get("assistant_response_failure_mode"))
    if not isinstance(text, str):
        return ResultReadout(
            text=None,
            source=source or RESULT_READOUT_SOURCE_UNAVAILABLE,
            fallback_used=True,
            failure_mode=failure_mode or RESULT_READOUT_FAILURE_GENERATION_FAILED,
        )
    normalized = text.strip()
    if not normalized:
        return ResultReadout(
            text=None,
            source=source or RESULT_READOUT_SOURCE_UNAVAILABLE,
            fallback_used=True,
            failure_mode=failure_mode or RESULT_READOUT_FAILURE_GENERATION_FAILED,
        )
    return ResultReadout(
        text=normalized,
        source=source or _default_source_for_fallback(fallback_used),
        fallback_used=fallback_used,
        failure_mode=failure_mode,
    )


def unavailable_result_readout(
    failure_mode: str = RESULT_READOUT_FAILURE_GENERATION_FAILED,
) -> ResultReadout:
    return ResultReadout(
        text=None,
        source=RESULT_READOUT_SOURCE_UNAVAILABLE,
        fallback_used=True,
        failure_mode=failure_mode,
    )


def _default_source_for_fallback(fallback_used: bool) -> str:
    return (
        RESULT_READOUT_SOURCE_DETERMINISTIC_FALLBACK
        if fallback_used
        else RESULT_READOUT_SOURCE_LLM
    )


def _run_coroutine_sync(coroutine: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result_box: dict[str, T] = {}
    error_box: dict[str, BaseException] = {}

    context = copy_context()

    def runner() -> None:
        try:
            result_box["value"] = context.run(lambda: asyncio.run(coroutine))
        except BaseException as exc:  # pragma: no cover - re-raised in caller thread
            error_box["error"] = exc

    thread = Thread(target=runner, name="argus-result-readout", daemon=True)
    thread.start()
    thread.join()
    if "error" in error_box:
        raise error_box["error"]
    return result_box["value"]


def _strategy_summary_from_payload(
    *,
    request: dict[str, Any],
    envelope: dict[str, Any],
    explanation_context: dict[str, Any],
) -> StrategySummary:
    resolved_strategy = _dict(envelope.get("resolved_strategy"))
    resolved_parameters = _dict(envelope.get("resolved_parameters"))
    return StrategySummary(
        raw_user_phrasing=_optional_str(
            request.get("raw_user_phrasing") or request.get("current_user_message")
        ),
        strategy_type=_optional_str(
            request.get("strategy_type")
            or resolved_strategy.get("strategy_type")
            or explanation_context.get("strategy_type")
        ),
        asset_universe=_symbols_from_payload(
            request=request,
            resolved_strategy=resolved_strategy,
            explanation_context=explanation_context,
        ),
        asset_class=_optional_str(
            request.get("asset_class")
            or resolved_strategy.get("asset_class")
            or explanation_context.get("asset_class")
        ),
        timeframe=_optional_str(
            request.get("timeframe")
            or resolved_parameters.get("timeframe")
            or explanation_context.get("timeframe")
        ),
        cadence=_optional_str(
            request.get("cadence")
            or resolved_parameters.get("cadence")
            or explanation_context.get("cadence")
        ),
        date_range=_date_range_from_payload(
            request=request,
            resolved_parameters=resolved_parameters,
            explanation_context=explanation_context,
        ),
        sizing_mode=_optional_str(
            request.get("sizing_mode") or resolved_parameters.get("sizing_mode")
        ),
        capital_amount=_optional_float(
            request.get("capital_amount")
            or request.get("starting_capital")
            or resolved_parameters.get("capital_amount")
        ),
        position_size=_optional_float(
            request.get("position_size") or resolved_parameters.get("position_size")
        ),
        comparison_baseline=_optional_str(
            request.get("benchmark_symbol")
            or resolved_parameters.get("benchmark_symbol")
            or explanation_context.get("benchmark_symbol")
        ),
        entry_rule=_optional_dict(request.get("entry_rule"))
        or _optional_dict(resolved_strategy.get("entry_rule")),
        exit_rule=_optional_dict(request.get("exit_rule"))
        or _optional_dict(resolved_strategy.get("exit_rule")),
        rule_spec=_optional_dict(request.get("rule_spec"))
        or _optional_dict(resolved_strategy.get("rule_spec")),
        extra_parameters=_dict(request.get("parameters")),
    )


def _normalized_explanation_context(
    *,
    envelope: dict[str, Any],
    result_card: dict[str, Any],
    explanation_context: dict[str, Any] | None,
) -> dict[str, Any]:
    context = dict(explanation_context or {})
    resolved_parameters = _dict(envelope.get("resolved_parameters"))
    resolved_strategy = _dict(envelope.get("resolved_strategy"))
    context.setdefault("result_card", dict(result_card))
    context.setdefault("metrics", _dict(envelope.get("metrics")))
    context.setdefault("benchmark_metrics", _dict(envelope.get("benchmark_metrics")))
    context.setdefault("resolved_parameters", resolved_parameters)
    context.setdefault("resolved_strategy", resolved_strategy)
    context.setdefault("strategy_type", resolved_strategy.get("strategy_type"))
    context.setdefault("timeframe", resolved_parameters.get("timeframe"))
    context.setdefault("date_range", resolved_parameters.get("date_range"))
    context.setdefault("benchmark_symbol", resolved_parameters.get("benchmark_symbol"))
    context.setdefault("assumptions", _list(envelope.get("assumptions")))
    context.setdefault("caveats", _list(envelope.get("caveats")))
    return context


def _optional_parameters_from_request(request: dict[str, Any]) -> dict[str, Any]:
    raw_optional = request.get("optional_parameters")
    if isinstance(raw_optional, dict):
        return dict(raw_optional)

    parameters: dict[str, Any] = {}
    for key, label in (
        ("date_range", "Date range"),
        ("timeframe", "Timeframe"),
        ("benchmark_symbol", "Benchmark"),
        ("capital_amount", "Starting capital"),
        ("starting_capital", "Starting capital"),
        ("position_size", "Position size"),
        ("cadence", "Cadence"),
    ):
        if key in request and request.get(key) not in (None, ""):
            parameters[key] = {"label": label, "source": "user"}
    return parameters


def _symbols_from_payload(
    *,
    request: dict[str, Any],
    resolved_strategy: dict[str, Any],
    explanation_context: dict[str, Any],
) -> list[str]:
    candidates: list[Any] = []
    for value in (
        request.get("symbols"),
        request.get("symbol"),
        resolved_strategy.get("asset_universe"),
        resolved_strategy.get("symbol"),
        explanation_context.get("symbols"),
        explanation_context.get("symbol"),
    ):
        if isinstance(value, list):
            candidates.extend(value)
        elif value is not None:
            candidates.append(value)

    symbols: list[str] = []
    for candidate in candidates:
        symbol = str(candidate or "").strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def _date_range_from_payload(
    *,
    request: dict[str, Any],
    resolved_parameters: dict[str, Any],
    explanation_context: dict[str, Any],
) -> str | dict[str, Any] | None:
    for value in (
        request.get("date_range"),
        resolved_parameters.get("date_range"),
        explanation_context.get("date_range"),
    ):
        if isinstance(value, dict):
            return dict(value)
        text = _optional_str(value)
        if text:
            return text
    return None


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_dict(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
