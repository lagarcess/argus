"""Display figures for a completed result, attached where readers receive it.

``result_display_figures`` projects the engine's own metrics into the one-decimal
figures the result card, the Quick Take, the breakdown, the Try next reason, and
the dossier print. It runs at the reader boundary, from the metrics the payload
already carries, so historical results need no repair and no second metrics
owner exists. Readers never round; a payload without figures has no printable
figure.

A stated difference is the difference of the two figures shown beside it. The
benchmark gap is the shown return minus the shown benchmark return, and the
modeled cost drag is the shown gross return minus the shown net return. The
engine's stored gap and drag, taken before rounding, are quoted only when one of
the two returns is missing. Every reader, stored runs included, states the gap
and the drag through ``shown_benchmark_gap`` and ``shown_cost_drag``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from argus.domain.benchmark_comparison import benchmark_comparison_from_delta
from argus.domain.display_figure import display_difference, display_figure

RESULT_FIGURES_KEY = "figures"


def shown_benchmark_gap(
    total_return_pct: object, benchmark_return_pct: object, stored_gap: object
) -> float | None:
    """The benchmark gap every reader states: the shown returns' difference."""
    shown = display_difference(total_return_pct, benchmark_return_pct)
    return shown if shown is not None else display_figure(stored_gap)


def shown_cost_drag(
    gross_return_pct: object, net_return_pct: object, stored_drag: object
) -> float | None:
    """The modeled cost drag every reader states: shown gross minus shown net."""
    shown = display_difference(gross_return_pct, net_return_pct)
    return shown if shown is not None else display_figure(stored_drag)


def result_display_figures(metrics: object) -> dict[str, Any] | None:
    aggregate = _mapping(_mapping(metrics).get("aggregate"))
    performance = _mapping(aggregate.get("performance"))
    if not performance:
        return None
    figures: dict[str, Any] = {}
    for key in ("total_return_pct", "benchmark_return_pct"):
        figure = display_figure(performance.get(key))
        if figure is not None:
            figures[key] = figure
    gap = shown_benchmark_gap(
        performance.get("total_return_pct"),
        performance.get("benchmark_return_pct"),
        performance.get("delta_vs_benchmark_pct"),
    )
    if gap is not None:
        figures["delta_vs_benchmark_pct"] = gap
        figures["benchmark_comparison_claim"] = benchmark_comparison_from_delta(gap).claim
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
        drag = shown_cost_drag(
            realism.get("gross_total_return_pct"),
            realism.get("net_total_return_pct"),
            realism.get("return_drag_pct"),
        )
        if drag is not None:
            figures["return_drag_pct"] = drag
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
