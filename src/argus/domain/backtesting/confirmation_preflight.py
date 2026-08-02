from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from argus.domain.backtesting import coverage as coverage_service
from argus.domain.engine_launch import adapter as launch_adapter
from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.engine_launch.strategies import validate_launch_supported


@dataclass(frozen=True)
class ConfirmationLaunchPreflight:
    outcome: Literal["ready_to_confirm", "validation_failure", "coverage_failure"]
    launch_payload: dict[str, Any] | None = None
    error_code: str | None = None


def materialize_confirmation_strategy(
    strategy: dict[str, Any],
    *,
    launch_payload: dict[str, Any],
) -> dict[str, Any]:
    """Project canonical launch facts onto the visible confirmation strategy."""
    canonical = dict(strategy)
    benchmark = launch_payload.get("benchmark_symbol")
    if isinstance(benchmark, str) and benchmark.strip():
        canonical["comparison_baseline"] = benchmark.strip().upper()

    effective = launch_payload.get("date_range")
    requested = launch_payload.get("requested_date_range")
    if not isinstance(effective, dict) or not isinstance(requested, dict):
        return canonical
    extra_parameters = dict(canonical.get("extra_parameters") or {})
    extra_parameters["requested_date_range"] = dict(requested)
    extra_parameters["effective_date_range"] = dict(effective)
    return {
        **canonical,
        "date_range": dict(effective),
        "extra_parameters": extra_parameters,
    }


def prepare_confirmation_launch(
    launch_payload: dict[str, Any],
) -> ConfirmationLaunchPreflight:
    """Validate a launch and resolve its provider-backed coverage truth."""
    try:
        request = LaunchBacktestRequest.model_validate(launch_payload)
        validate_launch_supported(request)
        symbol_validation = launch_adapter.validate_request_symbols(request)
        if symbol_validation.outcome == "unavailable":
            return _coverage_failure("market_data_unavailable")
        if symbol_validation.outcome != "resolved":
            return _validation_failure(symbol_validation.error_code or "invalid_symbol")
        symbols = list(symbol_validation.symbols)
        asset_class = symbol_validation.asset_class
        if asset_class is None:
            return _validation_failure("invalid_asset_class")

        benchmark_validation = launch_adapter.validate_request_benchmark(
            request,
            asset_class=asset_class,
        )
        if benchmark_validation.outcome == "unavailable":
            return _coverage_failure("market_data_unavailable")
        if (
            benchmark_validation.outcome != "resolved"
            or benchmark_validation.benchmark_symbol is None
        ):
            return _validation_failure(
                benchmark_validation.error_code or "invalid_benchmark_symbol"
            )

        canonical_launch_payload = {
            **launch_payload,
            "benchmark_symbol": benchmark_validation.benchmark_symbol,
        }
        request = LaunchBacktestRequest.model_validate(canonical_launch_payload)
        requested_range = request.requested_date_range or request.date_range
        prepared = coverage_service.prepare_market_data(
            {
                "asset_class": asset_class,
                "symbols": symbols,
                "timeframe": request.timeframe,
                "start_date": request.date_range.start,
                "end_date": request.date_range.end,
                "requested_date_range": requested_range.model_dump(),
                "benchmark_symbol": request.benchmark_symbol,
            }
        )
    except coverage_service.MarketDataCoverageError as exc:
        return _coverage_failure(exc.code)
    except ValidationError as exc:
        return _validation_failure(_validation_error_code(exc))
    except ValueError as exc:
        return _validation_failure(str(exc))

    requested = prepared.requested_date_range.model_dump()
    effective = prepared.effective_date_range.model_dump()
    coverage = prepared.coverage_payload()
    coverage["preflight_id"] = coverage.pop("dataset_id")
    adjusted_launch_payload = {
        **canonical_launch_payload,
        "date_range": effective,
        "requested_date_range": requested,
        "coverage_preflight": coverage,
    }
    try:
        adjusted_request = LaunchBacktestRequest.model_validate(adjusted_launch_payload)
        validate_launch_supported(adjusted_request)
    except ValidationError as exc:
        return _validation_failure(_validation_error_code(exc))
    except ValueError as exc:
        return _validation_failure(str(exc))
    return ConfirmationLaunchPreflight(
        outcome="ready_to_confirm",
        launch_payload=adjusted_launch_payload,
    )


def _coverage_failure(error_code: str) -> ConfirmationLaunchPreflight:
    return ConfirmationLaunchPreflight(
        outcome="coverage_failure",
        error_code=error_code,
    )


def _validation_failure(error_code: str) -> ConfirmationLaunchPreflight:
    return ConfirmationLaunchPreflight(
        outcome="validation_failure",
        error_code=error_code,
    )


def _validation_error_code(exc: ValidationError) -> str:
    text = str(exc)
    for code in (
        "future_end_date",
        "invalid_chronological_date_range",
        "invalid_date_range",
        "capital_amount_required",
        "position_size_required",
    ):
        if code in text:
            return code
    return "missing_rule_group"
