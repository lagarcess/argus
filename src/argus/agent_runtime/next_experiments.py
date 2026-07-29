"""Stage-0 Try next selection: typed, result-aware, capped experiment rows.

The stacked rows are the one Try next surface (spec
2026-07-29-try-next-surface-ownership.md). Selection here is a
deterministic policy over the supported experiment set for the strategy
family that actually ran; smarter layers (telemetry ordering, an LLM
selector) arrive later behind the same contract and may reorder rows but
never mint them."""

from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.result_facts import structured_next_experiments

NEXT_EXPERIMENTS_VERSION = "argus_next_experiments/v1"
NEXT_EXPERIMENTS_ROW_CAP = 3

_LABEL_KEY_PREFIX = "chat.next_experiments.labels."

# The tapped row sends this localized text as an ordinary conversational
# turn; every label must read as a supported ask for its family.
NEXT_EXPERIMENT_ACTION_LABELS: dict[str, dict[str, str]] = {
    "en": {
        f"{_LABEL_KEY_PREFIX}change_date_range": "Change the date range",
        f"{_LABEL_KEY_PREFIX}same_setup_peer_asset": (
            "Test the same setup on a similar asset"
        ),
        f"{_LABEL_KEY_PREFIX}same_rule_peer_asset": (
            "Test the same rule on a similar asset"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_threshold": (
            "Try a supported RSI threshold rule"
        ),
        f"{_LABEL_KEY_PREFIX}supported_ma_crossover": (
            "Try a supported SMA/EMA crossover"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_or_ma_rule": (
            "Simplify into a supported RSI or SMA/EMA rule"
        ),
        f"{_LABEL_KEY_PREFIX}adjust_indicator_thresholds": (
            "Adjust the indicator period or thresholds"
        ),
        f"{_LABEL_KEY_PREFIX}adjust_signal_periods": "Adjust the signal periods",
        f"{_LABEL_KEY_PREFIX}adjust_contribution_cadence": (
            "Adjust the contribution cadence"
        ),
        f"{_LABEL_KEY_PREFIX}compare_buy_and_hold": "Compare with buy and hold",
    },
    "es-419": {
        f"{_LABEL_KEY_PREFIX}change_date_range": "Cambiar el rango de fechas",
        f"{_LABEL_KEY_PREFIX}same_setup_peer_asset": (
            "Probar el mismo enfoque en un activo similar"
        ),
        f"{_LABEL_KEY_PREFIX}same_rule_peer_asset": (
            "Probar la misma regla en un activo similar"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_threshold": (
            "Probar una regla RSI compatible"
        ),
        f"{_LABEL_KEY_PREFIX}supported_ma_crossover": (
            "Probar un cruce SMA/EMA compatible"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_or_ma_rule": (
            "Simplificar a una regla RSI o SMA/EMA compatible"
        ),
        f"{_LABEL_KEY_PREFIX}adjust_indicator_thresholds": (
            "Ajustar el período o los umbrales del indicador"
        ),
        f"{_LABEL_KEY_PREFIX}adjust_signal_periods": "Ajustar los períodos de la señal",
        f"{_LABEL_KEY_PREFIX}adjust_contribution_cadence": (
            "Ajustar la cadencia de aportes"
        ),
        f"{_LABEL_KEY_PREFIX}compare_buy_and_hold": "Comparar con comprar y mantener",
    },
}

_REFINEMENT_KINDS = frozenset(
    {
        "adjust_indicator_thresholds",
        "adjust_signal_periods",
        "adjust_contribution_cadence",
        "supported_rsi_threshold",
        "supported_ma_crossover",
        "supported_rsi_or_ma_rule",
        "compare_buy_and_hold",
    }
)
_EXPLORATION_KINDS = frozenset(
    {"change_date_range", "same_setup_peer_asset", "same_rule_peer_asset"}
)
_DEEP_DRAWDOWN_THRESHOLD_PCT = -15.0


def next_experiment_label_key(kind: str) -> str:
    return f"{_LABEL_KEY_PREFIX}{kind}"


def next_experiments_sidecar(
    result_facts: dict[str, Any],
    *,
    total_return: float | None = None,
    benchmark_return: float | None = None,
    max_drawdown: float | None = None,
) -> dict[str, Any] | None:
    options = structured_next_experiments(result_facts)
    if not options:
        return None
    delta = (
        total_return - benchmark_return
        if total_return is not None and benchmark_return is not None
        else None
    )
    why = _row_reason(delta=delta, max_drawdown=max_drawdown)
    ordered = _ordered_kinds(
        [str(option["kind"]) for option in options],
        delta=delta,
        max_drawdown=max_drawdown,
    )
    labels = {str(option["kind"]): str(option["label"]) for option in options}
    english = NEXT_EXPERIMENT_ACTION_LABELS["en"]
    rows = []
    for kind in ordered[:NEXT_EXPERIMENTS_ROW_CAP]:
        label_key = next_experiment_label_key(kind)
        row: dict[str, Any] = {
            "kind": kind,
            "label": english.get(label_key) or labels[kind],
            "label_key": label_key,
        }
        if why is not None:
            row["why"] = why
        rows.append(row)
    if not rows:
        return None
    return {"version": NEXT_EXPERIMENTS_VERSION, "rows": rows}


def _ordered_kinds(
    kinds: list[str],
    *,
    delta: float | None,
    max_drawdown: float | None,
) -> list[str]:
    """Result-aware order: a losing or high-drawdown run leads with
    refinement, a winning run leads with exploration; ties keep the
    family's own order."""
    lost = delta is not None and delta < 0
    deep_drawdown = (
        max_drawdown is not None and max_drawdown <= _DEEP_DRAWDOWN_THRESHOLD_PCT
    )
    prefer_refinement = lost or deep_drawdown

    def sort_key(index_kind: tuple[int, str]) -> tuple[int, int]:
        index, kind = index_kind
        refinement = kind in _REFINEMENT_KINDS
        preferred = refinement if prefer_refinement else kind in _EXPLORATION_KINDS
        return (0 if preferred else 1, index)

    return [kind for _, kind in sorted(enumerate(kinds), key=sort_key)]


def _row_reason(
    *,
    delta: float | None,
    max_drawdown: float | None,
) -> dict[str, Any] | None:
    if max_drawdown is not None and max_drawdown <= _DEEP_DRAWDOWN_THRESHOLD_PCT:
        return {"code": "deep_drawdown", "params": {"drawdown": round(max_drawdown, 1)}}
    if delta is not None and delta < 0:
        return {"code": "lost_to_benchmark", "params": {"points": round(-delta, 1)}}
    if delta is not None and delta > 0:
        return {"code": "beat_benchmark", "params": {"points": round(delta, 1)}}
    return None
