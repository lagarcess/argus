"""Display figures for a completed result, attached where readers receive it.

``result_display_figures`` projects the engine's own metrics into the one-decimal
figures the result card, the Quick Take, the breakdown, the Try next reason, and
the dossier print. It runs at the reader boundary, from the metrics the payload
already carries, so historical results need no repair and no second metrics
owner exists. Readers never round; a payload without figures has no printable
figure.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from argus.domain.benchmark_comparison import benchmark_comparison_from_delta
from argus.domain.display_figure import display_figure

RESULT_FIGURES_KEY = "figures"


def result_display_figures(metrics: object) -> dict[str, Any] | None:
    aggregate = _mapping(_mapping(metrics).get("aggregate"))
    performance = _mapping(aggregate.get("performance"))
    if not performance:
        return None
    figures: dict[str, Any] = {}
    for key in ("total_return_pct", "benchmark_return_pct", "delta_vs_benchmark_pct"):
        figure = display_figure(performance.get(key))
        if figure is not None:
            figures[key] = figure
    if "delta_vs_benchmark_pct" in figures:
        figures["benchmark_comparison_claim"] = benchmark_comparison_from_delta(
            performance.get("delta_vs_benchmark_pct")
        ).claim
    drawdown = display_figure(_mapping(aggregate.get("risk")).get("max_drawdown_pct"))
    if drawdown is None:
        # Flat legacy shape kept readable; the canonical block is risk.
        drawdown = display_figure(performance.get("max_drawdown_pct"))
    if drawdown is not None:
        figures["max_drawdown_pct"] = drawdown
    realism = _mapping(performance.get("execution_realism"))
    if bool(realism.get("enabled")):
        for key in ("gross_total_return_pct", "net_total_return_pct"):
            figure = display_figure(realism.get(key))
            if figure is not None:
                figures[key] = figure
    return figures or None


def with_result_figures(fact_bank: object) -> object:
    """Attach figures to a fact bank in place, derived from its own metrics."""
    if not isinstance(fact_bank, dict):
        return fact_bank
    figures = result_display_figures(fact_bank.get("metrics"))
    if figures is not None:
        fact_bank[RESULT_FIGURES_KEY] = figures
    return fact_bank


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
