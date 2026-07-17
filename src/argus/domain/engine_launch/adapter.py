from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from math import isfinite
from typing import Any

from loguru import logger

from argus.domain.backtesting.config import (
    _execution_realism_feature_enabled,
    _normalize_execution_realism,
)
from argus.domain.backtesting.coverage import (
    PreparedMarketData,
    apply_coverage_to_config,
    prepare_market_data,
)
from argus.domain.engine import (
    build_result_card,
    build_result_chart,
    classify_symbol,
    compute_alpha_metrics,
    validate_backtest_config,
)
from argus.domain.engine_launch.cadence import resolve_dca_cadence
from argus.domain.engine_launch.display import (
    format_recurring_entry_caveat,
    format_timeframe_data_caveat,
)
from argus.domain.engine_launch.models import (
    LaunchBacktestRequest,
    LaunchExecutionEnvelope,
)
from argus.domain.engine_launch.result_facts import (
    append_execution_note_to_result_card,
)
from argus.domain.engine_launch.results import (
    build_benchmark_metrics,
    build_explanation_context,
    build_failure_envelope,
    build_success_envelope,
)
from argus.domain.engine_launch.sizing import resolve_starting_capital
from argus.domain.engine_launch.strategies import (
    indicator_threshold_parameters,
    normalize_template_name,
    rule_spec_from_request,
    validate_launch_supported,
)
from argus.domain.market_data import fetch_ohlcv, fetch_price_series


@dataclass(frozen=True)
class LaunchExecutionAdapterResult:
    envelope: LaunchExecutionEnvelope
    result_card: dict[str, Any] | None = None
    explanation_context: dict[str, Any] | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)


def run_launch_backtest(
    request: LaunchBacktestRequest,
    *,
    language: str = "en",
) -> LaunchExecutionAdapterResult:
    recorder = _LaunchTimingRecorder()
    try:
        validate_launch_supported(request)
    except ValueError as exc:
        category, status = _normalize_value_error(str(exc))
        return _with_timings(
            _blocked_result(
                request,
                execution_status=status,
                failure_category=category,
                failure_reason=str(exc),
            ),
            recorder=recorder,
        )

    try:
        prepared_market_data = _prepared_market_data_for_request(
            request,
            recorder=recorder,
        )
        if request.strategy_type == "dca_accumulation":
            result = _run_dca_accumulation(
                request,
                language=language,
                recorder=recorder,
                prepared_market_data=prepared_market_data,
            )
        elif request.strategy_type == "signal_strategy":
            result = _run_signal_strategy(
                request,
                language=language,
                recorder=recorder,
                prepared_market_data=prepared_market_data,
            )
        elif request.strategy_type == "indicator_threshold":
            result = _run_indicator_threshold(
                request,
                language=language,
                recorder=recorder,
                prepared_market_data=prepared_market_data,
            )
        else:
            result = _run_buy_and_hold(
                request,
                language=language,
                recorder=recorder,
                prepared_market_data=prepared_market_data,
            )
    except ValueError as exc:
        failure_reason = str(exc)
        category, status = _normalize_value_error(failure_reason)
        return _with_timings(
            LaunchExecutionAdapterResult(
                envelope=build_failure_envelope(
                    request=request,
                    execution_status=status,
                    failure_category=category,
                    failure_reason=failure_reason,
                    provider_metadata=_failure_provider_metadata(request),
                )
            ),
            recorder=recorder,
        )
    except Exception:
        return _with_timings(
            LaunchExecutionAdapterResult(
                envelope=build_failure_envelope(
                    request=request,
                    execution_status="failed_internal",
                    failure_category="internal_system_error",
                    failure_reason="launch_execution_failed",
                )
            ),
            recorder=recorder,
        )
    return _with_timings(result, recorder=recorder)


class _LaunchTimingRecorder:
    def __init__(self) -> None:
        self._timings_ms: dict[str, float] = {}

    def record_elapsed(self, name: str, started: float) -> None:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if isfinite(elapsed_ms) and elapsed_ms >= 0.0:
            self._timings_ms[name] = self._timings_ms.get(name, 0.0) + elapsed_ms

    def fetch_ohlcv(self, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return fetch_ohlcv(*args, **kwargs)
        finally:
            self.record_elapsed("provider_fetch_total", started)

    def fetch_price_series(self, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        try:
            return fetch_price_series(*args, **kwargs)
        finally:
            self.record_elapsed("provider_fetch_total", started)

    def compute_alpha_metrics(
        self,
        config: dict[str, Any],
        *,
        prepared_market_data: PreparedMarketData | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            return compute_alpha_metrics(
                config,
                fetch_ohlcv_func=self.fetch_ohlcv,
                fetch_price_series_func=self.fetch_price_series,
                prepared_market_data=prepared_market_data,
            )
        finally:
            self.record_elapsed("engine_compute_total", started)

    def snapshot(self) -> dict[str, float]:
        return {
            name: round(elapsed_ms, 3)
            for name, elapsed_ms in sorted(self._timings_ms.items())
        }


def _with_timings(
    result: LaunchExecutionAdapterResult,
    *,
    recorder: _LaunchTimingRecorder,
) -> LaunchExecutionAdapterResult:
    return LaunchExecutionAdapterResult(
        envelope=result.envelope,
        result_card=result.result_card,
        explanation_context=result.explanation_context,
        timings_ms=recorder.snapshot(),
    )


def _run_indicator_threshold(
    request: LaunchBacktestRequest,
    *,
    language: str,
    recorder: _LaunchTimingRecorder,
    prepared_market_data: PreparedMarketData | None = None,
) -> LaunchExecutionAdapterResult:
    symbols, asset_class = _resolve_request_symbols(request)
    initial_price = _initial_price(
        request,
        asset_class=asset_class,
        recorder=recorder,
        prepared_market_data=prepared_market_data,
    )
    starting_capital = resolve_starting_capital(
        request,
        initial_price=initial_price,
    )
    indicator_parameters = indicator_threshold_parameters(request)
    config = _build_indicator_threshold_config(
        request=request,
        asset_class=asset_class,
        symbols=symbols,
        starting_capital=starting_capital,
        indicator_parameters=indicator_parameters,
    )
    config = _with_prepared_coverage(config, prepared_market_data)
    validate_backtest_config(config)

    metrics = recorder.compute_alpha_metrics(
        config,
        prepared_market_data=prepared_market_data,
    )
    result_card = _build_launch_result_card(
        config,
        metrics,
        language=language,
        recorder=recorder,
        prepared_market_data=prepared_market_data,
    )
    benchmark_metrics = build_benchmark_metrics(
        request=request,
        metrics=metrics,
        benchmark_symbol=config["benchmark_symbol"],
    )
    envelope = build_success_envelope(
        resolved_strategy={
            "strategy_type": request.strategy_type,
            "symbol": config["symbols"][0],
            "asset_universe": config["symbols"],
            "entry_rule": request.entry_rule,
            "exit_rule": request.exit_rule,
        },
        resolved_parameters={
            "timeframe": config["timeframe"],
            "date_range": {
                "start": config["start_date"],
                "end": config["end_date"],
            },
            "benchmark_symbol": config["benchmark_symbol"],
            "sizing_mode": request.sizing_mode,
            "capital_amount": starting_capital,
            "position_size": request.position_size,
            "cadence": request.cadence,
            "template": config["template"],
            "indicator": indicator_parameters["indicator"],
            "indicator_period": indicator_parameters["indicator_period"],
            "entry_threshold": indicator_parameters["entry_threshold"],
            "exit_threshold": indicator_parameters["exit_threshold"],
            "rule_spec": indicator_parameters["rule_spec"],
            "engine_config": dict(config),
            **_coverage_resolved_parameters(config),
        },
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        assumptions=list(result_card.get("assumptions", [])),
        caveats=[
            format_timeframe_data_caveat(config["timeframe"], language=language),
            (
                f"Only the confirmed {indicator_parameters['indicator'].upper()} "
                "threshold rule was simulated; no extra filters were added."
            ),
        ],
        provider_metadata=_provider_metadata(
            asset_class=asset_class,
            timeframe=config["timeframe"],
        ),
    )
    result_card = append_execution_note_to_result_card(
        result_card,
        {
            "resolved_strategy": envelope.resolved_strategy,
            "resolved_parameters": envelope.resolved_parameters,
            "metrics": envelope.metrics,
        },
    )
    return LaunchExecutionAdapterResult(
        envelope=envelope,
        result_card=result_card,
        explanation_context=build_explanation_context(
            request=request,
            envelope=envelope,
            result_card=result_card,
        ),
    )


def _run_signal_strategy(
    request: LaunchBacktestRequest,
    *,
    language: str,
    recorder: _LaunchTimingRecorder,
    prepared_market_data: PreparedMarketData | None = None,
) -> LaunchExecutionAdapterResult:
    symbols, asset_class = _resolve_request_symbols(request)
    initial_price = _initial_price(
        request,
        asset_class=asset_class,
        recorder=recorder,
        prepared_market_data=prepared_market_data,
    )
    starting_capital = resolve_starting_capital(
        request,
        initial_price=initial_price,
    )
    rule_spec = rule_spec_from_request(request)
    config = _build_signal_strategy_config(
        request=request,
        asset_class=asset_class,
        symbols=symbols,
        starting_capital=starting_capital,
        rule_spec=rule_spec,
    )
    config = _with_prepared_coverage(config, prepared_market_data)
    validate_backtest_config(config)

    metrics = recorder.compute_alpha_metrics(
        config,
        prepared_market_data=prepared_market_data,
    )
    result_card = _build_launch_result_card(
        config,
        metrics,
        language=language,
        recorder=recorder,
        prepared_market_data=prepared_market_data,
    )
    benchmark_metrics = build_benchmark_metrics(
        request=request,
        metrics=metrics,
        benchmark_symbol=config["benchmark_symbol"],
    )
    envelope = build_success_envelope(
        resolved_strategy={
            "strategy_type": request.strategy_type,
            "symbol": config["symbols"][0],
            "asset_universe": config["symbols"],
            "entry_rule": request.entry_rule,
            "exit_rule": request.exit_rule,
            "rule_spec": rule_spec,
        },
        resolved_parameters={
            "timeframe": config["timeframe"],
            "date_range": {
                "start": config["start_date"],
                "end": config["end_date"],
            },
            "benchmark_symbol": config["benchmark_symbol"],
            "sizing_mode": request.sizing_mode,
            "capital_amount": starting_capital,
            "position_size": request.position_size,
            "cadence": request.cadence,
            "template": config["template"],
            "rule_spec": rule_spec,
            "engine_config": dict(config),
            **_coverage_resolved_parameters(config),
        },
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        assumptions=list(result_card.get("assumptions", [])),
        caveats=[
            format_timeframe_data_caveat(config["timeframe"], language=language),
            "Only the confirmed signal rules were simulated; no extra filters were added.",
        ],
        provider_metadata=_provider_metadata(
            asset_class=asset_class,
            timeframe=config["timeframe"],
        ),
    )
    result_card = append_execution_note_to_result_card(
        result_card,
        {
            "resolved_strategy": envelope.resolved_strategy,
            "resolved_parameters": envelope.resolved_parameters,
            "metrics": envelope.metrics,
        },
    )
    return LaunchExecutionAdapterResult(
        envelope=envelope,
        result_card=result_card,
        explanation_context=build_explanation_context(
            request=request,
            envelope=envelope,
            result_card=result_card,
        ),
    )


def _run_dca_accumulation(
    request: LaunchBacktestRequest,
    *,
    language: str,
    recorder: _LaunchTimingRecorder,
    prepared_market_data: PreparedMarketData | None = None,
) -> LaunchExecutionAdapterResult:
    symbols, asset_class = _resolve_request_symbols(request)
    initial_price = _initial_price(
        request,
        asset_class=asset_class,
        recorder=recorder,
        prepared_market_data=prepared_market_data,
    )
    recurring_allocation = resolve_starting_capital(
        request,
        initial_price=initial_price,
    )
    cadence = resolve_dca_cadence(request.cadence)
    config = _build_periodic_config(
        request=request,
        asset_class=asset_class,
        symbols=symbols,
        recurring_contribution=recurring_allocation,
        cadence=cadence,
    )
    config = _with_prepared_coverage(config, prepared_market_data)
    _validate_launch_config(config)

    metrics = recorder.compute_alpha_metrics(
        config,
        prepared_market_data=prepared_market_data,
    )
    result_card = _build_launch_result_card(
        config,
        metrics,
        language=language,
        recorder=recorder,
        prepared_market_data=prepared_market_data,
    )
    benchmark_metrics = build_benchmark_metrics(
        request=request,
        metrics=metrics,
        benchmark_symbol=config["benchmark_symbol"],
    )
    envelope = build_success_envelope(
        resolved_strategy={
            "strategy_type": request.strategy_type,
            "symbol": config["symbols"][0],
            "asset_universe": config["symbols"],
            "entry_rule": {"type": "periodic_accumulation", "cadence": cadence},
            "exit_rule": {"type": "end_of_period"},
        },
        resolved_parameters={
            "timeframe": config["timeframe"],
            "date_range": {
                "start": config["start_date"],
                "end": config["end_date"],
            },
            "benchmark_symbol": config["benchmark_symbol"],
            "sizing_mode": request.sizing_mode,
            "capital_amount": recurring_allocation,
            "recurring_contribution": recurring_allocation,
            "starting_principal": 0.0,
            "position_size": request.position_size,
            "cadence": cadence,
            "engine_config": dict(config),
            **_coverage_resolved_parameters(config),
        },
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        assumptions=list(result_card.get("assumptions", [])),
        caveats=[
            format_timeframe_data_caveat(config["timeframe"], language=language),
            format_recurring_entry_caveat(config["timeframe"], language=language),
        ],
        provider_metadata=_provider_metadata(
            asset_class=asset_class,
            timeframe=config["timeframe"],
        ),
    )
    return LaunchExecutionAdapterResult(
        envelope=envelope,
        result_card=result_card,
        explanation_context=build_explanation_context(
            request=request,
            envelope=envelope,
            result_card=result_card,
        ),
    )


def _run_buy_and_hold(
    request: LaunchBacktestRequest,
    *,
    language: str,
    recorder: _LaunchTimingRecorder,
    prepared_market_data: PreparedMarketData | None = None,
) -> LaunchExecutionAdapterResult:
    symbols, asset_class = _resolve_request_symbols(request)
    initial_price = _initial_price(
        request,
        asset_class=asset_class,
        recorder=recorder,
        prepared_market_data=prepared_market_data,
    )
    starting_capital = resolve_starting_capital(
        request,
        initial_price=initial_price,
    )
    config = _build_buy_and_hold_config(
        request=request,
        asset_class=asset_class,
        symbols=symbols,
        starting_capital=starting_capital,
    )
    config = _with_prepared_coverage(config, prepared_market_data)
    validate_backtest_config(config)

    metrics = recorder.compute_alpha_metrics(
        config,
        prepared_market_data=prepared_market_data,
    )
    result_card = _build_launch_result_card(
        config,
        metrics,
        language=language,
        recorder=recorder,
        prepared_market_data=prepared_market_data,
    )
    benchmark_metrics = build_benchmark_metrics(
        request=request,
        metrics=metrics,
        benchmark_symbol=config["benchmark_symbol"],
    )
    envelope = build_success_envelope(
        resolved_strategy={
            "strategy_type": request.strategy_type,
            "symbol": config["symbols"][0],
            "asset_universe": config["symbols"],
            "entry_rule": {"type": "start_of_period"},
            "exit_rule": {"type": "end_of_period"},
        },
        resolved_parameters={
            "timeframe": config["timeframe"],
            "date_range": {
                "start": config["start_date"],
                "end": config["end_date"],
            },
            "benchmark_symbol": config["benchmark_symbol"],
            "sizing_mode": request.sizing_mode,
            "capital_amount": starting_capital,
            "position_size": request.position_size,
            "cadence": request.cadence,
            "engine_config": dict(config),
            **_coverage_resolved_parameters(config),
        },
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        assumptions=list(result_card.get("assumptions", [])),
        caveats=[format_timeframe_data_caveat(config["timeframe"], language=language)],
        provider_metadata=_provider_metadata(
            asset_class=asset_class,
            timeframe=config["timeframe"],
        ),
    )
    return LaunchExecutionAdapterResult(
        envelope=envelope,
        result_card=result_card,
        explanation_context=build_explanation_context(
            request=request,
            envelope=envelope,
            result_card=result_card,
        ),
    )


def _provider_metadata(*, asset_class: str, timeframe: str) -> dict[str, Any]:
    if asset_class == "currency_pair":
        return {
            "provider": "kraken",
            "asset_class": asset_class,
            "timeframe": timeframe,
        }
    if asset_class == "crypto":
        return {
            "provider": "alpaca",
            "fallback_provider": "kraken",
            "asset_class": asset_class,
            "timeframe": timeframe,
            "source_policy": "alpaca_crypto_with_kraken_fallback",
        }
    return {
        "provider": "alpaca",
        "asset_class": asset_class,
        "timeframe": timeframe,
        "feed": "iex",
    }


def _failure_provider_metadata(request: LaunchBacktestRequest) -> dict[str, Any]:
    resolved_symbols, asset_class = _safe_resolved_request_universe(request)
    if asset_class is None:
        return {}
    metadata = _provider_metadata(asset_class=asset_class, timeframe=request.timeframe)
    metadata.update(
        {
            "symbols": resolved_symbols or list(request.symbols),
            "date_range": request.date_range.model_dump(mode="python"),
        }
    )
    return metadata


def _safe_resolved_request_universe(
    request: LaunchBacktestRequest,
) -> tuple[list[str], str | None]:
    try:
        symbols, asset_class = _resolve_request_symbols(request)
    except Exception:
        return list(request.symbols), request.asset_class
    return symbols, asset_class


def _build_periodic_config(
    *,
    request: LaunchBacktestRequest,
    asset_class: str,
    symbols: list[str],
    recurring_contribution: float,
    cadence: str,
) -> dict[str, Any]:
    benchmark_asset = classify_symbol(request.benchmark_symbol)
    if benchmark_asset.asset_class != asset_class:
        raise ValueError("invalid_benchmark_symbol")

    config = {
        "template": "dca_accumulation",
        "asset_class": asset_class,
        "symbols": symbols,
        "timeframe": request.timeframe,
        "start_date": request.date_range.start,
        "end_date": request.date_range.end,
        "side": "long",
        # The shared engine still reads this field as the periodic contribution
        # for DCA. Keep product-facing names in parameters/envelopes.
        "starting_capital": recurring_contribution,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark_asset.symbol,
        "parameters": {"dca_cadence": cadence},
        "recurring_contribution": recurring_contribution,
        "starting_principal": 0.0,
    }
    return _with_execution_realism(config, request)


def _build_launch_result_card(
    config: dict[str, Any],
    metrics: dict[str, Any],
    *,
    language: str,
    recorder: _LaunchTimingRecorder | None = None,
    prepared_market_data: PreparedMarketData | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        if recorder is None:
            chart = build_result_chart(
                config,
                prepared_market_data=prepared_market_data,
            )
        else:
            chart = build_result_chart(
                config,
                fetch_ohlcv_func=recorder.fetch_ohlcv,
                prepared_market_data=prepared_market_data,
            )
    except Exception as exc:
        logger.warning("Result chart build failed", error=str(exc))
        chart = None
    try:
        return build_result_card(config, metrics, language=language, chart=chart)
    except TypeError as exc:
        if "chart" not in str(exc):
            raise
        return build_result_card(config, metrics, language=language)
    finally:
        if recorder is not None:
            recorder.record_elapsed("chart_result_build_total", started)


def _validate_launch_config(config: dict[str, Any]) -> None:
    if config["template"] == "dca_accumulation":
        validation_config = dict(config)
        # Shared engine validation treats starting_capital as a one-time bankroll.
        # Launch DCA uses it as the recurring contribution amount instead.
        validation_config["starting_capital"] = max(
            1000.0,
            float(config["starting_capital"]),
        )
        validate_backtest_config(validation_config)
        return
    validate_backtest_config(config)


def _build_buy_and_hold_config(
    *,
    request: LaunchBacktestRequest,
    asset_class: str,
    symbols: list[str],
    starting_capital: float,
) -> dict[str, Any]:
    benchmark_asset = classify_symbol(request.benchmark_symbol)
    if benchmark_asset.asset_class != asset_class:
        raise ValueError("invalid_benchmark_symbol")

    config = {
        "template": "buy_and_hold",
        "asset_class": asset_class,
        "symbols": symbols,
        "timeframe": request.timeframe,
        "start_date": request.date_range.start,
        "end_date": request.date_range.end,
        "side": "long",
        "starting_capital": starting_capital,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark_asset.symbol,
        "parameters": {},
    }
    return _with_execution_realism(config, request)


def _build_indicator_threshold_config(
    *,
    request: LaunchBacktestRequest,
    asset_class: str,
    symbols: list[str],
    starting_capital: float,
    indicator_parameters: dict[str, Any],
) -> dict[str, Any]:
    benchmark_asset = classify_symbol(request.benchmark_symbol)
    if benchmark_asset.asset_class != asset_class:
        raise ValueError("invalid_benchmark_symbol")

    config = {
        "template": normalize_template_name(request),
        "asset_class": asset_class,
        "symbols": symbols,
        "timeframe": request.timeframe,
        "start_date": request.date_range.start,
        "end_date": request.date_range.end,
        "side": "long",
        "starting_capital": starting_capital,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark_asset.symbol,
        "parameters": indicator_parameters,
    }
    return _with_execution_realism(config, request)


def _build_signal_strategy_config(
    *,
    request: LaunchBacktestRequest,
    asset_class: str,
    symbols: list[str],
    starting_capital: float,
    rule_spec: dict[str, Any],
) -> dict[str, Any]:
    benchmark_asset = classify_symbol(request.benchmark_symbol)
    if benchmark_asset.asset_class != asset_class:
        raise ValueError("invalid_benchmark_symbol")

    config = {
        "template": normalize_template_name(request),
        "asset_class": asset_class,
        "symbols": symbols,
        "timeframe": request.timeframe,
        "start_date": request.date_range.start,
        "end_date": request.date_range.end,
        "side": "long",
        "starting_capital": starting_capital,
        "allocation_method": "equal_weight",
        "benchmark_symbol": benchmark_asset.symbol,
        "parameters": {"rule_spec": rule_spec},
    }
    return _with_execution_realism(config, request)


def _with_execution_realism(
    config: dict[str, Any],
    request: LaunchBacktestRequest,
) -> dict[str, Any]:
    if not _execution_realism_feature_enabled():
        return config
    if request.execution_realism is None:
        return config
    return {
        **config,
        "_execution_realism": _normalize_execution_realism(request.execution_realism),
    }


def _initial_price(
    request: LaunchBacktestRequest,
    *,
    asset_class: str,
    recorder: _LaunchTimingRecorder,
    prepared_market_data: PreparedMarketData | None = None,
) -> float | None:
    if request.sizing_mode != "position_size":
        return None
    if len(request.symbols) > 1:
        raise ValueError("unsupported_multi_symbol_position_size")

    if prepared_market_data is None:
        series = recorder.fetch_price_series(
            symbol=request.symbol,
            asset_class=asset_class,
            start_date=date.fromisoformat(request.date_range.start),
            end_date=date.fromisoformat(request.date_range.end),
            timeframe=request.timeframe,
        )
    else:
        resolved_symbols, _ = _resolve_request_symbols(request)
        series = prepared_market_data.price_series_for(resolved_symbols[0])
    if series.empty:
        raise ValueError("market_data_unavailable")
    return float(series.iloc[0])


def _prepared_market_data_for_request(
    request: LaunchBacktestRequest,
    *,
    recorder: _LaunchTimingRecorder,
) -> PreparedMarketData | None:
    if request.coverage_preflight is None:
        return None
    symbols, asset_class = _resolve_request_symbols(request)
    config = {
        "asset_class": asset_class,
        "symbols": symbols,
        "timeframe": request.timeframe,
        "start_date": request.date_range.start,
        "end_date": request.date_range.end,
        "requested_date_range": request.requested_date_range.model_dump()
        if request.requested_date_range is not None
        else request.date_range.model_dump(),
        "benchmark_symbol": request.benchmark_symbol,
    }
    return prepare_market_data(
        config,
        fetch_ohlcv_func=recorder.fetch_ohlcv,
        approved_coverage=request.coverage_preflight.model_dump(),
    )


def _with_prepared_coverage(
    config: dict[str, Any],
    prepared_market_data: PreparedMarketData | None,
) -> dict[str, Any]:
    if prepared_market_data is None:
        return config
    return apply_coverage_to_config(config, prepared_market_data)


def _coverage_resolved_parameters(config: dict[str, Any]) -> dict[str, Any]:
    requested = config.get("requested_date_range")
    effective = config.get("effective_date_range")
    coverage = config.get("data_coverage")
    if (
        not isinstance(requested, dict)
        or not isinstance(effective, dict)
        or not isinstance(coverage, dict)
    ):
        return {}
    return {
        "requested_date_range": dict(requested),
        "effective_date_range": dict(effective),
        "data_coverage": dict(coverage),
    }


def _resolve_request_symbols(request: LaunchBacktestRequest) -> tuple[list[str], str]:
    assets = [classify_symbol(symbol) for symbol in request.symbols]
    if not assets:
        raise ValueError("invalid_symbol_count")
    if request.asset_class is not None:
        if any(asset.asset_class != request.asset_class for asset in assets):
            raise ValueError("asset_class_conflict")
        return [asset.symbol for asset in assets], request.asset_class
    asset_class = assets[0].asset_class
    if any(asset.asset_class != asset_class for asset in assets):
        raise ValueError("asset_class_conflict")
    return [asset.symbol for asset in assets], asset_class


def _blocked_result(
    request: LaunchBacktestRequest,
    *,
    execution_status: str = "blocked_unsupported",
    failure_category: str = "unsupported_capability",
    failure_reason: str,
) -> LaunchExecutionAdapterResult:
    return LaunchExecutionAdapterResult(
        envelope=build_failure_envelope(
            request=request,
            execution_status=execution_status,
            failure_category=failure_category,
            failure_reason=failure_reason,
        )
    )


def _normalize_value_error(error_code: str) -> tuple[str, str]:
    invalid_inputs = {
        "capital_amount_required",
        "position_size_required",
        "capital_amount_not_applicable",
        "position_size_not_applicable",
        "invalid_date_range",
        "invalid_chronological_date_range",
        "future_end_date",
        "invalid_starting_capital",
        "invalid_symbol_count",
        "position_price_required",
        "asset_class_conflict",
        "indicator_data_insufficient",
        "invalid_indicator_parameter",
        "indicator_period_out_of_bounds",
        "indicator_threshold_out_of_bounds",
        "missing_rule_group",
        "provider_history_start_unavailable",
        "kraken_ohlc_window_exceeded",
    }
    unsupported = {
        "cadence_required",
        "cadence_not_applicable",
        "unsupported_multi_symbol_position_size",
        "unsupported_timeframe",
        "unsupported_template",
        "stablecoin_not_supported",
        "unsupported_parameters",
        "unsupported_allocation_method",
        "unsupported_side",
        "unsupported_indicator",
        "unsupported_indicator_threshold",
        "unsupported_risk_rules",
        "unsupported_rule_operator",
        "provider_timeframe_unavailable",
    }
    if error_code in {
        "market_data_unavailable",
        "benchmark_data_unavailable",
        "no_common_data_window",
        "insufficient_common_data",
    }:
        return "upstream_dependency_error", "failed_upstream"
    if error_code == "approved_data_window_unavailable":
        return "parameter_validation_error", "blocked_invalid_input"
    if error_code in invalid_inputs or error_code.startswith(
        "invalid_execution_realism_"
    ):
        return "parameter_validation_error", "blocked_invalid_input"
    if error_code in unsupported:
        return "unsupported_capability", "blocked_unsupported"
    return "internal_system_error", "failed_internal"
