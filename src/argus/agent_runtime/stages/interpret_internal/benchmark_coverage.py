"""Card-time price-coverage grounding for a resolved comparison benchmark.

Catalog membership does not guarantee price history (OTC listings,
post-window IPOs). A benchmark leg the data feed cannot uphold reconciles
to the class default before the card promises it; the cleared leg keeps
provenance so the confirmation card discloses the swap."""

from __future__ import annotations

from typing import Any, Callable

from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _normalized_symbol,
)
from argus.agent_runtime.stages.interpret_internal.benchmark_repairs import (
    BENCHMARK_DISCLOSURE_STATUSES,
    default_benchmark_for_asset_class,
)
from argus.agent_runtime.state.models import ResolutionProvenance, StrategySummary
from argus.agent_runtime.strategy_contract import resolve_date_range

# Timeframes the bars fetch accepts; anything else probes the launch default.
_PROBE_TIMEFRAMES = frozenset({"1D", "1d", "1h", "2h", "4h", "6h", "12h"})
_PROBE_DEFAULT_TIMEFRAME = "1D"

BENCHMARK_WITHOUT_PRICE_COVERAGE_CLEARED = "benchmark_without_price_coverage_cleared"


def strategy_with_benchmark_price_coverage(
    strategy: StrategySummary,
    *,
    fetch_ohlcv_func: Callable[..., Any] | None = None,
) -> tuple[StrategySummary, list[str]]:
    benchmark = _normalized_symbol(strategy.comparison_baseline)
    if benchmark is None:
        return strategy, []
    asset_class = (strategy.asset_class or "").strip()
    if not asset_class:
        return strategy, []
    default = default_benchmark_for_asset_class(
        asset_class,
        symbols=strategy.asset_universe,
    )
    # Without a default there is nothing to reconcile to, and clearing the
    # leg would be silent; the run corridor owns reporting that failure.
    if default is None or benchmark == default:
        return strategy, []
    if fetch_ohlcv_func is None:
        from argus.domain import market_data

        fetch_ohlcv_func = market_data.fetch_ohlcv
    window = resolve_date_range(strategy.date_range)
    timeframe = (strategy.timeframe or "").strip()
    if timeframe not in _PROBE_TIMEFRAMES:
        timeframe = _PROBE_DEFAULT_TIMEFRAME
    try:
        bars = fetch_ohlcv_func(
            symbol=benchmark,
            asset_class=asset_class,
            start_date=window.start,
            end_date=window.end,
            timeframe=timeframe,
        )
        has_coverage = bars is not None and len(bars) > 0
    except ValueError as exc:
        # Only the provider's explicit zero-bars answer clears the leg;
        # transport failures keep it — the run corridor owns those.
        if str(exc) != "market_data_empty":
            return strategy, []
        has_coverage = False
    except Exception:
        return strategy, []
    if has_coverage:
        return strategy, []
    updated = strategy.model_copy(deep=True)
    updated.comparison_baseline = None
    updated.resolution_provenance = _provenance_with_coverage_clearing(
        updated.resolution_provenance,
        benchmark=benchmark,
        asset_class=asset_class,
    )
    return updated, [BENCHMARK_WITHOUT_PRICE_COVERAGE_CLEARED]


def _provenance_with_coverage_clearing(
    provenance: list[ResolutionProvenance],
    *,
    benchmark: str,
    asset_class: str,
) -> list[ResolutionProvenance]:
    """Replace the leg's resolved entry in place (the dedupe key ignores
    status) and retire prior disclosures — the card must describe exactly
    this reconciliation, never an earlier one."""
    remaining: list[ResolutionProvenance] = []
    base: ResolutionProvenance | None = None
    for item in provenance:
        if item.field == "comparison_baseline":
            if (
                base is None
                and (item.canonical_symbol or "").strip().upper() == benchmark
            ):
                base = item
                continue
            if item.resolution_status in BENCHMARK_DISCLOSURE_STATUSES:
                continue
        remaining.append(item)
    if base is None:
        base = ResolutionProvenance(
            field="comparison_baseline",
            raw_text=benchmark,
            source="llm_extraction",
            candidate_kind="asset",
            canonical_symbol=benchmark,
            asset_class=asset_class,
        )
    return [
        *remaining,
        base.model_copy(
            update={
                "resolution_status": "unavailable_for_requested_run",
                "validated_by": "price_coverage_probe",
            }
        ),
    ]
