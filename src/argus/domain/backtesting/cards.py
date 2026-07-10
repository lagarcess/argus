from __future__ import annotations

from datetime import date
from typing import Any

from argus.domain.backtesting.execution import _execution_realism_settings
from argus.domain.benchmark_comparison import (
    benchmark_comparison_from_delta,
)
from argus.domain.engine_launch.display import format_date_range_label


def _format_money(value: float) -> str:
    prefix = "-$" if value < 0 else "$"
    return f"{prefix}{abs(value):,.0f}"


def build_result_card(
    config: dict[str, Any],
    metrics: dict[str, Any],
    language: str = "en",
    chart: dict[str, Any] | None = None,
) -> dict[str, Any]:
    aggregate = metrics["aggregate"]
    performance = aggregate["performance"]
    risk = aggregate["risk"]
    efficiency = aggregate["efficiency"]
    start = date.fromisoformat(config["start_date"])
    end = date.fromisoformat(config["end_date"])
    symbols = ", ".join(config["symbols"])
    is_dca = config["template"] == "dca_accumulation"
    capital_basis = float(config["starting_capital"])
    if is_dca:
        capital_basis = (
            float(config["starting_capital"])
            / max(len(config["symbols"]), 1)
            * max(int(efficiency.get("total_trades", 0)), 1)
        )
    ending_capital = capital_basis + performance["profit"]
    realism = _execution_realism_settings(config)

    is_es = language.startswith("es")
    template_names = {
        "buy_and_hold": "Comprar y Mantener" if is_es else "Buy and Hold",
        "buy_the_dip": "Comprar la Caída" if is_es else "Buy the Dip",
        "rsi_mean_reversion": "Umbral RSI" if is_es else "RSI Threshold",
        "moving_average_crossover": "Cruce de Medias Móviles"
        if is_es
        else "Moving Average Crossover",
        "dca_accumulation": "Acumulación DCA" if is_es else "DCA Accumulation",
        "momentum_breakout": "Ruptura de Impulso" if is_es else "Momentum Breakout",
        "trend_follow": "Seguimiento de Tendencia" if is_es else "Trend Follow",
    }
    template_display = template_names.get(
        config["template"], config["template"].replace("_", " ").title()
    )

    status_label = "Simulación Completa" if is_es else "Simulation Complete"

    cost_assumption = _execution_realism_assumption(
        realism=realism,
        is_es=is_es,
    )
    if is_es:
        assumptions = [
            "Solo largo",
            "Peso igual",
            "Sin comisiones/deslizamiento",
            _benchmark_assumption(config, realism=realism, is_es=True),
        ]
        if cost_assumption is not None:
            assumptions[2] = cost_assumption
    else:
        assumptions = [
            "Long-only",
            "Equal weight",
            "No fees/slippage",
            _benchmark_assumption(config, realism=realism, is_es=False),
        ]
        if cost_assumption is not None:
            assumptions[2] = cost_assumption
    if is_dca:
        assumptions = _dca_assumptions(config, is_es=is_es) + assumptions

    rows = [
        {
            "key": "cash_value",
            "label": "Valor final" if is_es else "Ending value",
            "value": f"{_format_money(capital_basis)} -> {_format_money(ending_capital)}",
        },
        {
            "key": "total_return_pct",
            "label": "Retorno total" if is_es else "Total return",
            "value": f"{performance['total_return_pct']:+.1f}%",
        },
        {
            "key": "benchmark_delta",
            "label": (
                f"Comparado con {config['benchmark_symbol']}"
                if is_es
                else f"Compared with {config['benchmark_symbol']}"
            ),
            "value": benchmark_comparison_from_delta(
                performance["delta_vs_benchmark_pct"]
            ).user_phrase,
        },
        {
            "key": "max_drawdown_pct",
            "label": "Peor caída" if is_es else "Worst drop",
            "value": f"{risk['max_drawdown_pct']:.1f}%",
        },
    ]
    if _should_show_win_rate(config, efficiency):
        rows.append(
            {
                "key": "win_rate",
                "label": "Tasa de Acierto" if is_es else "Win Rate",
                "value": f"{efficiency['win_rate'] * 100:.1f}%",
            }
        )

    actions = [
        {
            "id": "show-breakdown",
            "type": "show_breakdown",
            "label": "Explicar resultado" if is_es else "Explain result",
            "labelKey": "chat.result_card.explain_result",
            "presentation": "result",
            "payload": {},
        },
        {
            "id": "save-strategy",
            "type": "save_strategy",
            "label": "Guardar" if is_es else "Save",
            "labelKey": "chat.result_card.save",
            "presentation": "result",
            "payload": {},
        },
        {
            "id": "refine-strategy",
            "type": "refine_strategy",
            "label": "Refinar idea" if is_es else "Refine idea",
            "labelKey": "chat.result_card.refine_idea",
            "presentation": "result",
            "payload": {},
        },
    ]
    card = {
        "title": f"{symbols} {template_display}",
        "symbols": list(config["symbols"]),
        "strategy_label": template_display,
        "asset_class": config["asset_class"],
        "date_range": {
            "start": config["start_date"],
            "end": config["end_date"],
            "display": format_date_range_label(
                start,
                end,
                language=language,
                separator=" to " if not is_es else None,
            ),
        },
        "status_label": status_label,
        "rows": rows,
        "assumptions": assumptions,
        "benchmark_note": None,
        "actions": actions,
        "chart": chart,
    }
    execution_costs = _execution_costs_payload(performance)
    if execution_costs is not None:
        card["execution_costs"] = execution_costs
    return card


def _execution_costs_payload(performance: dict[str, Any]) -> dict[str, Any] | None:
    # Structured cost evidence for the client: present only when the engine
    # actually modeled costs, so idealized cards stay byte-identical.
    effect = performance.get("execution_realism")
    if not isinstance(effect, dict) or not bool(effect.get("enabled")):
        return None
    return {
        "fee_bps": effect.get("fee_bps"),
        "slippage_bps": effect.get("slippage_bps"),
        "gross_total_return_pct": effect.get("gross_total_return_pct"),
        "net_total_return_pct": effect.get("net_total_return_pct"),
        "return_drag_pct": effect.get("return_drag_pct"),
        "benchmark_treatment": "same_modeled_costs",
    }


def _should_show_win_rate(config: dict[str, Any], efficiency: dict[str, Any]) -> bool:
    if config["template"] in {"buy_and_hold", "dca_accumulation"}:
        return False
    return int(efficiency.get("total_trades", 0) or 0) > 1


def _execution_realism_assumption(
    *,
    realism: dict[str, float | bool],
    is_es: bool,
) -> str | None:
    # One tight honesty line; the gross-vs-net numbers live in the details
    # pane, so the strip only states that returns already include the costs.
    if not bool(realism["enabled"]):
        return None
    fee_bps = float(realism["fees"]) * 10000.0
    slippage_bps = float(realism["slippage"]) * 10000.0
    if fee_bps <= 0.0 and slippage_bps <= 0.0:
        return None
    if is_es:
        return (
            f"Neto de comisión de {_format_bps(fee_bps)} bps + "
            f"deslizamiento de {_format_bps(slippage_bps)} bps"
        )
    return (
        f"Net of {_format_bps(fee_bps)} bps fee + "
        f"{_format_bps(slippage_bps)} bps slippage"
    )


def _benchmark_assumption(
    config: dict[str, Any],
    *,
    realism: dict[str, float | bool],
    is_es: bool,
) -> str:
    symbol = config["benchmark_symbol"]
    has_modeled_costs = bool(realism["enabled"]) and (
        float(realism["fees"]) > 0.0 or float(realism["slippage"]) > 0.0
    )
    if is_es:
        suffix = " (mismos costos modelados)" if has_modeled_costs else ""
        return f"Referencia: {symbol}{suffix}"
    suffix = " (same modeled costs)" if has_modeled_costs else ""
    return f"Benchmark: {symbol}{suffix}"


def _format_bps(value: float) -> str:
    rounded = round(value, 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:g}"


def _dca_assumptions(config: dict[str, Any], *, is_es: bool) -> list[str]:
    contribution = float(
        config.get("recurring_contribution") or config["starting_capital"]
    )
    principal = float(config.get("starting_principal") or 0.0)
    cadence = _dca_cadence_label(config, is_es=is_es)
    cadence_suffix = f" {cadence}" if cadence else ""
    if is_es:
        return [
            f"Aporte recurrente: {_format_money(contribution)}{cadence_suffix}",
            f"Capital inicial: {_format_money(principal)}",
        ]
    return [
        f"Recurring contribution: {_format_money(contribution)}{cadence_suffix}",
        f"Starting principal: {_format_money(principal)}",
    ]


def _dca_cadence_label(config: dict[str, Any], *, is_es: bool) -> str:
    parameters = (
        config.get("parameters") if isinstance(config.get("parameters"), dict) else {}
    )
    cadence = str(parameters.get("dca_cadence") or "").strip().lower()
    if not cadence:
        return ""
    if is_es:
        return {
            "daily": "diario",
            "weekly": "semanal",
            "biweekly": "quincenal",
            "monthly": "mensual",
            "quarterly": "trimestral",
        }.get(cadence, cadence.replace("_", " "))
    return cadence.replace("_", " ")
