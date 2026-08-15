from __future__ import annotations

from datetime import date
from typing import Any

from argus.domain.backtesting.execution import _execution_realism_settings
from argus.domain.benchmark_comparison import (
    benchmark_comparison_from_delta,
)
from argus.domain.dca_capital import dca_capital_plan_from_config
from argus.domain.engine_launch.display import (
    format_benchmark_comparison_phrase,
    format_date_range_label,
)


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
    if is_dca:
        plan = dca_capital_plan_from_config(config)
        # Contributions are already summed across symbols by the fill count;
        # the seed is one whole-plan amount and joins the basis once.
        capital_basis = plan.starting_capital + plan.contribution / max(
            len(config["symbols"]), 1
        ) * max(int(efficiency.get("total_trades", 0)), 1)
    else:
        capital_basis = float(config["starting_capital"])
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

    benchmark_comparison = benchmark_comparison_from_delta(
        performance["delta_vs_benchmark_pct"]
    )

    rows = [
        {
            "key": "cash_value",
            "label": "Valor final" if is_es else "Ending value",
            "value": f"{_format_money(capital_basis)} -> {_format_money(ending_capital)}",
        },
        # A recurring plan's ratio is money-on-money over contributed cash,
        # not a time return on one bankroll, so it carries its own key and name.
        {
            "key": "contribution_return_pct" if is_dca else "total_return_pct",
            "label": (
                ("Retorno sobre aportes" if is_es else "Return on contributions")
                if is_dca
                else ("Retorno total" if is_es else "Total return")
            ),
            "value": f"{performance['total_return_pct']:+.1f}%",
        },
        {
            "key": "benchmark_delta",
            "label": (
                f"Comparado con {config['benchmark_symbol']}"
                if is_es
                else f"Compared with {config['benchmark_symbol']}"
            ),
            "value": format_benchmark_comparison_phrase(
                benchmark_comparison.claim,
                benchmark_comparison.magnitude_points,
                language=language,
            ),
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
    win_rate = efficiency.get("win_rate")
    return (
        isinstance(win_rate, int | float)
        and not isinstance(win_rate, bool)
        and int(efficiency.get("total_trades", 0) or 0) > 1
    )


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
    plan = dca_capital_plan_from_config(config)
    contribution = format_contribution_phrase(
        amount=plan.contribution,
        period=plan.period,
        is_es=is_es,
    )
    if is_es:
        return [
            f"Aporte: {contribution}",
            f"Capital inicial: {_format_money(plan.starting_capital)}",
            "Fracciones de acciones, nada queda en efectivo",
        ]
    return [
        f"Contribution: {contribution}",
        f"Starting capital: {_format_money(plan.starting_capital)}",
        "Fractional shares, nothing left as cash",
    ]


def format_contribution_phrase(
    *,
    amount: float,
    period: str,
    is_es: bool,
) -> str:
    """One phrase, never a labelled amount beside a labelled period."""
    return f"{_format_money(amount)} {_contribution_period_word(period, is_es=is_es)}"


def _contribution_period_word(period: str, *, is_es: bool) -> str:
    if is_es:
        return {
            "daily": "cada día",
            "weekly": "cada semana",
            "biweekly": "cada dos semanas",
            "monthly": "cada mes",
            "quarterly": "cada trimestre",
        }[period]
    return {
        "daily": "daily",
        "weekly": "weekly",
        "biweekly": "every two weeks",
        "monthly": "monthly",
        "quarterly": "quarterly",
    }[period]
