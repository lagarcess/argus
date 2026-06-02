from __future__ import annotations

from datetime import date
from typing import Any

from argus.domain.backtesting.execution import _execution_realism_settings


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

    if is_es:
        assumptions = [
            "Solo largo",
            "Peso igual",
            "Sin comisiones/deslizamiento",
            f"Referencia: {config['benchmark_symbol']}",
        ]
        if bool(realism["enabled"]):
            assumptions[2] = "Realismo de ejecución activado"
    else:
        assumptions = [
            "Long-only",
            "Equal weight",
            "No fees/slippage",
            f"Benchmark: {config['benchmark_symbol']}",
        ]
        if bool(realism["enabled"]):
            assumptions[2] = "Execution realism enabled"

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
            "value": f"{performance['delta_vs_benchmark_pct']:+.1f} pts vs {config['benchmark_symbol']}",
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
            "presentation": "result",
            "payload": {},
        },
        {
            "id": "save-strategy",
            "type": "save_strategy",
            "label": "Guardar" if is_es else "Save",
            "presentation": "result",
            "payload": {},
        },
        {
            "id": "refine-strategy",
            "type": "refine_strategy",
            "label": "Refinar idea" if is_es else "Refine idea",
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
        "benchmark_note": None,
        "actions": actions,
        "chart": chart,
    }


def _should_show_win_rate(config: dict[str, Any], efficiency: dict[str, Any]) -> bool:
    if config["template"] in {"buy_and_hold", "dca_accumulation"}:
        return False
    return int(efficiency.get("total_trades", 0) or 0) > 1
