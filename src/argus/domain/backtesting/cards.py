from __future__ import annotations

from datetime import date
from typing import Any

from argus.domain.backtesting.execution import _execution_realism_settings


def _format_money(value: float) -> str:
    if abs(value) >= 1000:
        return f"${value / 1000:.1f}k"
    return f"${value:,.0f}"


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
        "rsi_mean_reversion": "Reversión a la Media RSI"
        if is_es
        else "RSI Mean Reversion",
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

    benchmark_note = f"Universe: {symbols}. Benchmark: {config['benchmark_symbol']}."
    if is_es:
        benchmark_note = f"Universo: {symbols}. Referencia: {config['benchmark_symbol']}."
        assumptions = [
            f"Universo: {symbols}.",
            "La simulación utiliza el preajuste solo-largo.",
            f"Capital inicial: ${config['starting_capital']:,.0f}.",
            "Asignación: igual peso.",
            "No se incluyen deslizamientos ni comisiones.",
            f"Referencia: {config['benchmark_symbol']}.",
        ]
        if bool(realism["enabled"]):
            assumptions[4] = (
                "Realismo de ejecución habilitado (comisiones/deslizamiento aplicados)."
            )
    else:
        assumptions = [
            f"Universe: {symbols}.",
            "Simulation uses long-only preset.",
            (
                f"Recurring contribution: ${config['starting_capital']:,.0f}."
                if is_dca
                else f"Starting capital: ${config['starting_capital']:,.0f}."
            ),
            "Allocation: equal weight.",
            "No slippage or fees included.",
            f"Benchmark: {config['benchmark_symbol']}.",
        ]
        if bool(realism["enabled"]):
            assumptions[4] = "Execution realism enabled (fees/slippage applied)."

    rows = [
        {
            "key": "total_return_pct",
            "label": "Retorno Total (%)" if is_es else "Total Return (%)",
            "value": f"{performance['total_return_pct']:+.1f}%",
        },
        {
            "key": "cash_value",
            "label": (
                "Valor Final ($)"
                if is_es and is_dca
                else "Valor en Efectivo ($)"
                if is_es
                else "Final Value ($)"
                if is_dca
                else "Cash Value ($)"
            ),
            "value": f"{_format_money(capital_basis)} -> {_format_money(ending_capital)}",
        },
        {
            "key": "max_drawdown_pct",
            "label": "Máxima Caída" if is_es else "Max Drawdown",
            "value": f"{risk['max_drawdown_pct']:.1f}%",
        },
        {
            "key": "benchmark_delta",
            "label": "Vs referencia" if is_es else "Vs benchmark",
            "value": f"{performance['delta_vs_benchmark_pct']:+.1f} pts vs {config['benchmark_symbol']}",
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
            "label": "Ver desglose" if is_es else "Show a breakdown",
            "presentation": "result",
            "payload": {},
        },
        {
            "id": "save-strategy",
            "type": "save_strategy",
            "label": "Guardar estrategia" if is_es else "Save strategy",
            "presentation": "result",
            "payload": {},
        },
        {
            "id": "refine-strategy",
            "type": "refine_strategy",
            "label": "Refinar estrategia" if is_es else "Refine strategy",
            "presentation": "result",
            "payload": {},
        },
    ]
    return {
        "title": f"{symbols} {template_display}",
        "symbols": list(config["symbols"]),
        "strategy_label": template_display,
        "date_range": {
            "start": config["start_date"],
            "end": config["end_date"],
            "display": f"{start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}"
            if is_es
            else f"{start.strftime('%B')} {start.day}, {start.year} to {end.strftime('%B')} {end.day}, {end.year}",
        },
        "status_label": status_label,
        "rows": rows,
        "assumptions": assumptions,
        "benchmark_note": benchmark_note,
        "actions": actions,
        "chart": chart,
    }


def _should_show_win_rate(config: dict[str, Any], efficiency: dict[str, Any]) -> bool:
    if config["template"] in {"buy_and_hold", "dca_accumulation"}:
        return False
    return int(efficiency.get("total_trades", 0) or 0) > 1
