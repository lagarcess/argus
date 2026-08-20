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
        f"{_LABEL_KEY_PREFIX}change_date_range": "Test a different date range",
        f"{_LABEL_KEY_PREFIX}same_setup_peer_asset": (
            "Test the same setup on a similar asset"
        ),
        f"{_LABEL_KEY_PREFIX}same_rule_peer_asset": (
            "Test the same rule on a similar asset"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_threshold": (
            "Try a supported RSI threshold rule"
        ),
        f"{_LABEL_KEY_PREFIX}recurring_monthly_buys": "Try monthly recurring buys",
        f"{_LABEL_KEY_PREFIX}supported_ma_crossover": (
            "Try a supported SMA/EMA crossover"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_or_ma_rule": (
            "Simplify into a supported RSI or SMA/EMA rule"
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
        f"{_LABEL_KEY_PREFIX}supported_rsi_threshold": (
            "Probar una regla RSI compatible"
        ),
        f"{_LABEL_KEY_PREFIX}recurring_monthly_buys": (
            "Probar compras mensuales recurrentes"
        ),
        f"{_LABEL_KEY_PREFIX}supported_ma_crossover": (
            "Probar un cruce SMA/EMA compatible"
        ),
        f"{_LABEL_KEY_PREFIX}supported_rsi_or_ma_rule": (
            "Simplificar a una regla RSI o SMA/EMA compatible"
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
# the client. Every entry must still read as a supported ask on its own.
NEXT_EXPERIMENT_SHORT_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "change_date_range": "Different dates",
        "same_setup_peer_asset": "Similar asset",
        "same_rule_peer_asset": "Same rule, similar asset",
        "supported_rsi_threshold": "Supported RSI rule",
        "recurring_monthly_buys": "Monthly buys",
        "supported_ma_crossover": "SMA/EMA crossover",
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
        "supported_rsi_threshold": "Regla RSI compatible",
        "recurring_monthly_buys": "Compras mensuales",
        "supported_ma_crossover": "Cruce SMA/EMA",
        "supported_rsi_or_ma_rule": "Simplificar la regla",
        "adjust_indicator_thresholds": "Otros umbrales",
        "adjust_signal_periods": "Otros períodos",
        "adjust_contribution_cadence": "Cada cuánto",
        "compare_buy_and_hold": "Comparar con mantener",
    },
}

_REFINEMENT_KINDS = frozenset(
    {
        "recurring_monthly_buys",
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
CONTINUITY_NEXT_EXPERIMENT_KINDS = frozenset(
    {"change_date_range", "compare_buy_and_hold"}
)
_DEEP_DRAWDOWN_THRESHOLD_PCT = -15.0

_PEER_ASSETS: dict[str, str] = {
    "AAPL": "MSFT",
    "MSFT": "AAPL",
    "NVDA": "AMD",
    "AMD": "NVDA",
    "GOOGL": "META",
    "META": "GOOGL",
    "AMZN": "AAPL",
    "TSLA": "NVDA",
    "SPY": "QQQ",
    "QQQ": "SPY",
    "COST": "TGT",
    "TGT": "COST",
    "NFLX": "DIS",
    "DIS": "NFLX",
    "BTC": "ETH",
    "ETH": "BTC",
}

_SEND_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "same_setup_peer_asset": (
            "Test the same buy and hold setup on {peer} from {start} to "
            "{end} with ${capital}."
        ),
        "recurring_monthly_buys": (
            "Try monthly recurring buys of {symbol} from {start} to {end} "
            "with ${capital} each month."
        ),
    },
    "es-419": {
        "same_setup_peer_asset": (
            "Probar el mismo enfoque de comprar y mantener con {peer} de "
            "{start} a {end} con ${capital}."
        ),
        "recurring_monthly_buys": (
            "Probar compras mensuales recurrentes de {symbol} de {start} a "
            "{end} con ${capital} cada mes."
        ),
    },
}


def next_experiment_label_key(kind: str) -> str:
    return f"{_LABEL_KEY_PREFIX}{kind}"


def next_experiment_short_label_key(kind: str) -> str:
    return f"{_SHORT_LABEL_KEY_PREFIX}{kind}"


def next_experiments_sidecar(
    result_facts: dict[str, Any],
    *,
    total_return: float | None = None,
    benchmark_return: float | None = None,
    max_drawdown: float | None = None,
    recent_user_messages: list[str] | None = None,
    previously_offered_kinds: list[str] | None = None,
    language: str = "en",
    prebake_probe: Any | None = None,
) -> dict[str, Any] | None:
    options = structured_next_experiments(result_facts)
    if not options:
        return None
    # Ran or ignored, a kind from the previous offer is spent (spec §4.3);
    # restraint prefers fewer rows over repeated ones.
    already_asked = _kinds_already_asked(recent_user_messages) | set(
        previously_offered_kinds or []
    )
    delta = (
        total_return - benchmark_return
        if total_return is not None and benchmark_return is not None
        else None
    )
    why = _row_reason(delta=delta, max_drawdown=max_drawdown)
    ordered = _ordered_kinds(
        [
            str(option["kind"])
            for option in options
            if str(option["kind"]) not in already_asked
        ],
        delta=delta,
        max_drawdown=max_drawdown,
    )
    labels = {str(option["kind"]): str(option["label"]) for option in options}
    english = NEXT_EXPERIMENT_ACTION_LABELS["en"]
    prebake_params = _prebake_params(result_facts)
    rows = []
    for kind in ordered[:NEXT_EXPERIMENTS_ROW_CAP]:
        label_key = next_experiment_label_key(kind)
        short_label = NEXT_EXPERIMENT_SHORT_LABELS["en"].get(kind)
        row: dict[str, Any] = {
            "kind": kind,
            "label": english.get(label_key) or labels[kind],
            "label_key": label_key,
        }
        if short_label:
            row["label_short"] = short_label
            row["label_short_key"] = next_experiment_short_label_key(kind)
        prebaked = _prebaked_row_fields(
            kind,
            params=prebake_params,
            language=language,
            prebake_probe=prebake_probe,
        )
        if prebaked:
            row.update(prebaked)
        if why is not None:
            row["why"] = why
        rows.append(row)
    if not rows:
        return None
    return {"version": NEXT_EXPERIMENTS_VERSION, "rows": rows}


def _kinds_already_asked(recent_user_messages: list[str] | None) -> set[str]:
    """A row whose label the user already sent this conversation is spent;
    re-offering it is the padding the spec forbids."""
    if not recent_user_messages:
        return set()
    normalized = {
        message.strip().casefold()
        for message in recent_user_messages
        if isinstance(message, str) and message.strip()
    }
    if not normalized:
        return set()
    spent: set[str] = set()
    for labels in NEXT_EXPERIMENT_ACTION_LABELS.values():
        for label_key, label in labels.items():
            if label.strip().casefold() in normalized:
                spent.add(label_key.removeprefix(_LABEL_KEY_PREFIX))
    return spent


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


def _prebake_params(result_facts: dict[str, Any]) -> dict[str, Any] | None:
    """Accepts both fact shapes: the persisted config_snapshot and the
    engine envelope with resolved_* at the top level."""
    config = result_facts.get("config_snapshot")
    config = config if isinstance(config, dict) else {}
    resolved_params = config.get("resolved_parameters") or result_facts.get(
        "resolved_parameters"
    )
    resolved_params = resolved_params if isinstance(resolved_params, dict) else {}
    resolved_strategy = config.get("resolved_strategy") or result_facts.get(
        "resolved_strategy"
    )
    resolved_strategy = resolved_strategy if isinstance(resolved_strategy, dict) else {}
    template = str(
        config.get("template")
        or config.get("strategy_type")
        or resolved_strategy.get("strategy_type")
        or ""
    )
    if template != "buy_and_hold":
        return None
    symbols = (
        config.get("symbols")
        or result_facts.get("symbols")
        or resolved_strategy.get("asset_universe")
        or ([resolved_strategy["symbol"]] if resolved_strategy.get("symbol") else None)
    )
    symbol = (
        str(symbols[0]).strip().upper() if isinstance(symbols, list) and symbols else ""
    )
    date_range = config.get("date_range") or resolved_params.get("date_range")
    start = end = ""
    if isinstance(date_range, dict):
        start = str(date_range.get("start") or "").strip()
        end = str(date_range.get("end") or "").strip()
    if not start or not end:
        start = str(config.get("start_date") or "").strip()
        end = str(config.get("end_date") or "").strip()
    capital = (
        config.get("initial_capital")
        or config.get("capital_amount")
        or resolved_params.get("capital_amount")
        or resolved_params.get("initial_capital")
    )
    if not symbol or not start or not end or not isinstance(capital, (int, float)):
        return None
    asset_class = str(
        config.get("asset_class") or resolved_strategy.get("asset_class") or "equity"
    )
    return {
        "symbol": symbol,
        "start": start,
        "end": end,
        "capital": int(capital) if float(capital).is_integer() else capital,
        "asset_class": asset_class,
    }


def _prebaked_row_fields(
    kind: str,
    *,
    params: dict[str, Any] | None,
    language: str,
    prebake_probe: Any | None,
) -> dict[str, Any] | None:
    """A prebaked row's tap sends a fully specified ask: nothing is missing,
    so the normal lifecycle answers with the next confirmation card and no
    questions. Prebaking only happens when the grounding chain agrees."""
    if params is None or kind not in {"same_setup_peer_asset", "recurring_monthly_buys"}:
        return None
    templates = _SEND_TEMPLATES.get(
        "es-419" if (language or "en").lower().startswith("es") else "en",
        _SEND_TEMPLATES["en"],
    )
    template = templates.get(kind)
    if template is None:
        return None
    fields = dict(params)
    if kind == "same_setup_peer_asset":
        peer = _PEER_ASSETS.get(params["symbol"])
        if not peer or not _peer_is_grounded(
            peer,
            asset_class=params["asset_class"],
            start=params["start"],
            end=params["end"],
            prebake_probe=prebake_probe,
        ):
            return None
        fields["peer"] = peer
        return {"detail": peer, "send_text": template.format(**fields)}
    return {"send_text": template.format(**fields)}


_PREBAKE_PROBE_BUDGET_SECONDS = 2.0


def _peer_is_grounded(
    peer: str,
    *,
    asset_class: str,
    start: str,
    end: str,
    prebake_probe: Any | None,
) -> bool:
    """Result-paints-first: the optional row may never delay the completed
    result, so grounding runs under a hard budget and degrades to the
    generic row when the provider is slow."""

    def _probe() -> bool:
        if prebake_probe is not None:
            return bool(prebake_probe(peer))
        from datetime import date, timedelta

        from argus.domain import market_data

        resolved = market_data.resolve_asset(peer)
        if resolved is None or resolved.canonical_symbol.upper() != peer:
            return False
        # One owner decides whether a tap gets bars; this probe only adds the
        # window-tail question on top of it.
        if not market_data.tradable_history(peer, asset_class).is_tradable:
            return False
        # Coverage probe over the window's tail; a mid-window gap surfaces
        # at run time through the ordinary coverage recovery.
        end_date = date.fromisoformat(end)
        probe_start = max(date.fromisoformat(start), end_date - timedelta(days=14))
        bars = market_data.fetch_ohlcv(
            symbol=peer,
            asset_class=asset_class,
            start_date=probe_start,
            end_date=end_date,
            timeframe="1D",
        )
        return bars is not None and len(bars) > 0

    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return bool(executor.submit(_probe).result(timeout=_PREBAKE_PROBE_BUDGET_SECONDS))
    except Exception:
        return False
    finally:
        executor.shutdown(wait=False, cancel_futures=False)
