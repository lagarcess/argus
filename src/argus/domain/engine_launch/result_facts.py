from __future__ import annotations

from typing import Any

from argus.domain.backtesting.rules import describe_rule_spec

NO_ENTRY_TRADES_NOTE = (
    "No entry trades were executed; the strategy stayed in cash because the "
    "entry condition did not trigger in that window."
)


def execution_note(facts: dict[str, Any]) -> str | None:
    if not _is_signal_like_strategy(facts):
        return None
    trade_count = _total_trade_count(facts)
    if trade_count != 0:
        return None
    return NO_ENTRY_TRADES_NOTE


def resolved_rule_summary(facts: dict[str, Any]) -> str | None:
    resolved_strategy = _resolved_strategy(facts)
    resolved_parameters = _resolved_parameters(facts)
    strategy_type = _strategy_type(facts)
    if strategy_type == "indicator_threshold" or resolved_parameters.get("indicator"):
        return _indicator_threshold_summary(
            resolved_strategy=resolved_strategy,
            resolved_parameters=resolved_parameters,
        )
    if strategy_type == "signal_strategy":
        return _signal_strategy_summary(resolved_strategy)
    if strategy_type == "buy_and_hold":
        return "Entry rule: buy at the start of the period; exit rule: hold through the end."
    if strategy_type == "dca_accumulation":
        cadence = str(resolved_parameters.get("cadence") or "recurring").strip()
        return f"Entry rule: buy on the {cadence} cadence; exit rule: hold through the end."
    return None


def runnable_next_tests(facts: dict[str, Any]) -> str:
    """Return truthful next experiments for the strategy family that actually ran."""
    options = structured_next_experiments(facts)
    if options:
        labels = ", ".join(str(option["label"]) for option in options[:-1])
        if len(options) > 1:
            labels = f"{labels}, or {options[-1]['label']}"
        else:
            labels = str(options[0]["label"])
        return f"Try next: {labels}"

    return (
        "Try next: change the date range, test the same supported setup on "
        "a different same-class asset, or simplify the idea into a supported RSI or "
        "SMA/EMA rule"
    )


def structured_next_experiments(facts: dict[str, Any]) -> list[dict[str, Any]]:
    """Return structured, executable next-step options grounded in the completed run."""

    strategy_type = _strategy_type(facts)
    symbols = _symbols_label(facts)
    asset_phrase = f" on {symbols}" if symbols else ""
    asset_label = symbols or "this asset"
    peer_phrase = "a different same-class asset"

    if strategy_type == "buy_and_hold":
        return [
            _next_experiment("change_date_range", "change the date range"),
            _next_experiment(
                "same_setup_peer_asset",
                f"test the same buy-and-hold setup on {peer_phrase}",
            ),
            _next_experiment(
                "supported_rsi_threshold",
                f"try a supported RSI threshold{asset_phrase}",
            ),
            _next_experiment(
                "supported_ma_crossover",
                f"try a supported SMA/EMA crossover{asset_phrase}",
            ),
        ]
    if strategy_type == "indicator_threshold":
        return [
            _next_experiment(
                "adjust_indicator_thresholds",
                "adjust the indicator period or thresholds",
            ),
            _next_experiment(
                "compare_buy_and_hold",
                f"compare {asset_label} with buy-and-hold",
            ),
            _next_experiment("change_date_range", "change the date range"),
            _next_experiment("same_rule_peer_asset", f"test the rule on {peer_phrase}"),
        ]
    if strategy_type == "signal_strategy":
        return [
            _next_experiment(
                "adjust_signal_periods",
                "adjust the signal periods or crossover direction",
            ),
            _next_experiment(
                "compare_buy_and_hold",
                f"compare {asset_label} with buy-and-hold",
            ),
            _next_experiment("change_date_range", "change the date range"),
            _next_experiment("same_rule_peer_asset", f"test the rule on {peer_phrase}"),
        ]
    if strategy_type == "dca_accumulation":
        return [
            _next_experiment("change_date_range", "change the date range"),
            _next_experiment(
                "adjust_contribution_cadence",
                "adjust the contribution cadence",
            ),
            _next_experiment(
                "same_setup_peer_asset",
                f"test the same recurring-buy setup on {peer_phrase}",
            ),
            _next_experiment(
                "compare_buy_and_hold",
                f"compare {asset_label} with buy-and-hold",
            ),
        ]
    return [
        _next_experiment("change_date_range", "change the date range"),
        _next_experiment(
            "same_setup_peer_asset",
            "test the same supported setup on a different same-class asset",
        ),
        _next_experiment(
            "supported_rsi_or_ma_rule",
            "simplify the idea into a supported RSI or SMA/EMA rule",
        ),
    ]


def _next_experiment(kind: str, label: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
        "contract": "supported_backtest_experiment",
    }


def append_execution_note_to_result_card(
    card: dict[str, Any],
    facts: dict[str, Any],
) -> dict[str, Any]:
    note = execution_note(facts)
    if note is None:
        return card
    updated = dict(card)
    assumptions = updated.get("assumptions")
    if not isinstance(assumptions, list):
        assumptions = []
    normalized = [str(item) for item in assumptions if str(item).strip()]
    if note not in normalized:
        normalized.append(note)
    updated["assumptions"] = normalized
    return updated


def _indicator_threshold_summary(
    *,
    resolved_strategy: dict[str, Any],
    resolved_parameters: dict[str, Any],
) -> str | None:
    entry_rule = _rule_dict(resolved_strategy.get("entry_rule"))
    exit_rule = _rule_dict(resolved_strategy.get("exit_rule"))
    indicator = str(
        resolved_parameters.get("indicator")
        or entry_rule.get("indicator")
        or exit_rule.get("indicator")
        or ""
    ).strip()
    period = _first_present(
        resolved_parameters.get("indicator_period"),
        entry_rule.get("period"),
        exit_rule.get("period"),
    )
    entry_threshold = _first_present(
        resolved_parameters.get("entry_threshold"),
        entry_rule.get("threshold"),
    )
    exit_threshold = _first_present(
        resolved_parameters.get("exit_threshold"),
        exit_rule.get("threshold"),
    )
    if not indicator or entry_threshold is None or exit_threshold is None:
        return None
    indicator_label = indicator.upper()
    period_label = f"({int(float(period))})" if period is not None else ""
    return (
        f"Entry rule: buy when {indicator_label}{period_label} is at or below "
        f"{_format_number(entry_threshold)}; exit rule: sell when "
        f"{indicator_label}{period_label} is at or above "
        f"{_format_number(exit_threshold)}."
    )


def _signal_strategy_summary(resolved_strategy: dict[str, Any]) -> str | None:
    rule_spec = _rule_dict(resolved_strategy.get("rule_spec"))
    entry_text = describe_rule_spec(rule_spec, "entry") if rule_spec else None
    exit_text = describe_rule_spec(rule_spec, "exit") if rule_spec else None
    if entry_text and exit_text:
        return f"Entry rule: {entry_text}; exit rule: {exit_text}."
    if entry_text:
        return f"Entry rule: {entry_text}."

    entry_text = _moving_average_crossover_text(
        _rule_dict(resolved_strategy.get("entry_rule"))
    )
    exit_text = _moving_average_crossover_text(
        _rule_dict(resolved_strategy.get("exit_rule"))
    )
    if entry_text and exit_text:
        return f"Entry rule: {entry_text}; exit rule: {exit_text}."
    if entry_text:
        return f"Entry rule: {entry_text}."
    return None


def _moving_average_crossover_text(rule: dict[str, Any]) -> str | None:
    if rule.get("type") != "moving_average_crossover":
        return None
    fast_period = _first_present(rule.get("fast_period"), rule.get("fast"))
    slow_period = _first_present(rule.get("slow_period"), rule.get("slow"))
    if fast_period is None or slow_period is None:
        return None
    fast_indicator = str(rule.get("fast_indicator") or "sma").upper()
    slow_indicator = str(rule.get("slow_indicator") or fast_indicator).upper()
    direction = "below" if rule.get("direction") == "bearish" else "above"
    return (
        f"{int(float(fast_period))}-day {fast_indicator} crosses {direction} "
        f"{int(float(slow_period))}-day {slow_indicator}"
    )


def _total_trade_count(facts: dict[str, Any]) -> int | None:
    metric_value = _nested_value(
        _metrics(facts),
        ("aggregate", "efficiency", "total_trades"),
    )
    number = _as_float(metric_value)
    if number is not None:
        return int(number)
    trades = facts.get("trades")
    if isinstance(trades, list):
        return len(trades)
    return None


def _is_signal_like_strategy(facts: dict[str, Any]) -> bool:
    return _strategy_type(facts) in {"indicator_threshold", "signal_strategy"}


def _strategy_type(facts: dict[str, Any]) -> str | None:
    resolved_strategy = _resolved_strategy(facts)
    raw = (
        resolved_strategy.get("strategy_type")
        or facts.get("strategy_type")
        or _config_snapshot(facts).get("template")
    )
    if isinstance(raw, str) and raw.strip() == "rsi_mean_reversion":
        return "indicator_threshold"
    return raw.strip() if isinstance(raw, str) and raw.strip() else None


def _symbols_label(facts: dict[str, Any]) -> str:
    symbols = facts.get("symbols")
    if not isinstance(symbols, list) or not symbols:
        symbols = _config_snapshot(facts).get("symbols")
    if not isinstance(symbols, list) or not symbols:
        resolved_strategy = _resolved_strategy(facts)
        symbols = resolved_strategy.get("asset_universe")
    if not isinstance(symbols, list) or not symbols:
        symbol = facts.get("symbol") or _resolved_strategy(facts).get("symbol")
        return str(symbol or "").strip().upper()
    values = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
    return ", ".join(values)


def _metrics(facts: dict[str, Any]) -> dict[str, Any]:
    metrics = facts.get("metrics")
    return dict(metrics) if isinstance(metrics, dict) else {}


def _resolved_strategy(facts: dict[str, Any]) -> dict[str, Any]:
    direct = facts.get("resolved_strategy")
    if isinstance(direct, dict):
        return dict(direct)
    nested = _config_snapshot(facts).get("resolved_strategy")
    return dict(nested) if isinstance(nested, dict) else {}


def _resolved_parameters(facts: dict[str, Any]) -> dict[str, Any]:
    direct = facts.get("resolved_parameters")
    if isinstance(direct, dict):
        return dict(direct)
    nested = _config_snapshot(facts).get("resolved_parameters")
    return dict(nested) if isinstance(nested, dict) else {}


def _config_snapshot(facts: dict[str, Any]) -> dict[str, Any]:
    config = facts.get("config_snapshot")
    return dict(config) if isinstance(config, dict) else {}


def _rule_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _first_present(*values: Any) -> Any | None:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _nested_value(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "").replace("%", ""))
        except ValueError:
            return None
    return None


def _format_number(value: Any) -> str:
    number = _as_float(value)
    if number is None:
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"
