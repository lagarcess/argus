"""What a Try next row is: its kinds, its copy, and the reply that accepts it.

The row vocabulary and the typed round trip back from a user turn. Nothing
here reads a result; selecting which rows a given run earns lives with the
composer in `next_experiments.py`.
"""

from __future__ import annotations

from typing import Any

NEXT_EXPERIMENTS_VERSION = "argus_next_experiments/v1"
NEXT_EXPERIMENTS_ROW_CAP = 3

_LABEL_KEY_PREFIX = "chat.next_experiments.labels."

# The tapped row sends this localized text as an ordinary conversational
# turn; every label must read, in everyday words, as an ask Argus can run.
NEXT_EXPERIMENT_ACTION_LABELS: dict[str, dict[str, str]] = {
    "en": {
        f"{_LABEL_KEY_PREFIX}change_date_range": "Test a different date range",
        f"{_LABEL_KEY_PREFIX}same_setup_peer_asset": (
            "Test the same setup on a similar asset"
        ),
        f"{_LABEL_KEY_PREFIX}same_rule_peer_asset": (
            "Test the same rule on a similar asset"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_threshold": "Try an RSI threshold rule",
        f"{_LABEL_KEY_PREFIX}recurring_monthly_buys": "Try monthly recurring buys",
        f"{_LABEL_KEY_PREFIX}supported_ma_crossover": ("Try a moving average crossover"),
        f"{_LABEL_KEY_PREFIX}supported_rsi_or_ma_rule": (
            "Simplify into an RSI or moving average rule"
        ),
        f"{_LABEL_KEY_PREFIX}adjust_indicator_thresholds": (
            "Test different indicator thresholds"
        ),
        f"{_LABEL_KEY_PREFIX}adjust_signal_periods": "Test different signal periods",
        f"{_LABEL_KEY_PREFIX}adjust_contribution_cadence": (
            "Test a different contribution schedule"
        ),
        f"{_LABEL_KEY_PREFIX}compare_buy_and_hold": "Compare with buy and hold",
    },
    "es-419": {
        f"{_LABEL_KEY_PREFIX}change_date_range": "Probar otro rango de fechas",
        f"{_LABEL_KEY_PREFIX}same_setup_peer_asset": (
            "Probar el mismo enfoque en un activo similar"
        ),
        f"{_LABEL_KEY_PREFIX}same_rule_peer_asset": (
            "Probar la misma regla en un activo similar"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_threshold": ("Probar una regla de umbral RSI"),
        f"{_LABEL_KEY_PREFIX}recurring_monthly_buys": (
            "Probar compras mensuales recurrentes"
        ),
        f"{_LABEL_KEY_PREFIX}supported_ma_crossover": (
            "Probar un cruce de medias móviles"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_or_ma_rule": (
            "Simplificar a una regla RSI o de medias móviles"
        ),
        f"{_LABEL_KEY_PREFIX}adjust_indicator_thresholds": (
            "Probar otros umbrales del indicador"
        ),
        f"{_LABEL_KEY_PREFIX}adjust_signal_periods": "Probar otros períodos de la señal",
        f"{_LABEL_KEY_PREFIX}adjust_contribution_cadence": (
            "Probar otro calendario de aportes"
        ),
        f"{_LABEL_KEY_PREFIX}compare_buy_and_hold": "Comparar con comprar y mantener",
    },
}

_SHORT_LABEL_KEY_PREFIX = "chat.next_experiments.labels_short."

# Narrow screens get a shorter form of the same ask. The backend owns
# user-facing copy, so the short form is composed here rather than clipped in
# the client. Every entry must still read as an ask Argus can run on its own.
NEXT_EXPERIMENT_SHORT_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "change_date_range": "Different dates",
        "same_setup_peer_asset": "Similar asset",
        "same_rule_peer_asset": "Same rule, similar asset",
        "supported_rsi_threshold": "RSI rule",
        "recurring_monthly_buys": "Monthly buys",
        "supported_ma_crossover": "Moving average crossover",
        "supported_rsi_or_ma_rule": "Simplify the rule",
        "adjust_indicator_thresholds": "Other thresholds",
        "adjust_signal_periods": "Other signal periods",
        "adjust_contribution_cadence": "How often",
        "compare_buy_and_hold": "Compare with holding",
    },
    "es-419": {
        "change_date_range": "Otras fechas",
        "same_setup_peer_asset": "Activo similar",
        "same_rule_peer_asset": "Misma regla, activo similar",
        "supported_rsi_threshold": "Regla RSI",
        "recurring_monthly_buys": "Compras mensuales",
        "supported_ma_crossover": "Cruce de medias móviles",
        "supported_rsi_or_ma_rule": "Simplificar la regla",
        "adjust_indicator_thresholds": "Otros umbrales",
        "adjust_signal_periods": "Otros períodos",
        "adjust_contribution_cadence": "Cada cuánto",
        "compare_buy_and_hold": "Comparar con mantener",
    },
}

CONTINUITY_NEXT_EXPERIMENT_KINDS = frozenset(
    {"change_date_range", "compare_buy_and_hold"}
)


def next_experiment_label_key(kind: str) -> str:
    return f"{_LABEL_KEY_PREFIX}{kind}"


def next_experiment_short_label_key(kind: str) -> str:
    return f"{_SHORT_LABEL_KEY_PREFIX}{kind}"


def offered_kinds_from_thread_metadata(metadata: dict[str, Any] | None) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    kinds = metadata.get("next_experiments_offered_kinds")
    if not isinstance(kinds, list):
        return []
    return [str(kind) for kind in kinds if isinstance(kind, str) and kind]


def continuity_next_experiment_kind(
    *,
    action_type: str,
    action_payload: dict[str, Any],
) -> str | None:
    """Resolve only the two issue-345 rows from typed action metadata."""

    if action_type != "refine_strategy":
        return None
    raw_kind = action_payload.get("next_experiment_kind")
    if not isinstance(raw_kind, str):
        return None
    kind = raw_kind.strip()
    if kind not in CONTINUITY_NEXT_EXPERIMENT_KINDS:
        return None
    return kind


def continuity_next_experiment_label_key(kind: str) -> str | None:
    """Return the canonical presentation key for a validated continuity kind."""

    if kind not in CONTINUITY_NEXT_EXPERIMENT_KINDS:
        return None
    return f"{_LABEL_KEY_PREFIX}{kind}"


def detect_next_experiment_acceptance(
    message: str,
    thread_metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """A user turn that exactly matches an offered row's label (either
    language) is that row's acceptance; position feeds Stage-1 ordering."""
    offered = offered_kinds_from_thread_metadata(thread_metadata)
    if not offered:
        return None
    normalized = message.strip().casefold()
    if not normalized:
        return None
    sends = (
        thread_metadata.get("next_experiments_offered_texts")
        if isinstance(thread_metadata, dict)
        else None
    )
    if isinstance(sends, dict):
        for kind, send_text in sends.items():
            if (
                isinstance(send_text, str)
                and send_text.strip().casefold() == normalized
                and kind in offered
            ):
                return {"kind": str(kind), "position": offered.index(str(kind))}
    for labels in NEXT_EXPERIMENT_ACTION_LABELS.values():
        for label_key, label in labels.items():
            if label.strip().casefold() != normalized:
                continue
            kind = label_key.removeprefix(_LABEL_KEY_PREFIX)
            if kind in offered:
                return {"kind": kind, "position": offered.index(kind)}
    return None
