"""Deterministic latest-result fact answers for typed result follow-ups."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.response_style import (
    result_followup_heading,
    with_response_heading,
)
from argus.agent_runtime.result_followups import (
    date_range_label,
    metric_number,
    result_followup_fact_bank,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    ResultFollowupFocus,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import TaskSnapshot

_FACT_FOCUSES: dict[ResultFollowupFocus, str] = {
    "peak_date": "peak_date",
    "peak_value": "peak_value",
    "drawdown_date": "drawdown_date",
    "max_drawdown": "max_drawdown",
}

_FACT_KEY_ALIASES = {
    "aggregate_peak": "peak_value",
    "highest_value": "peak_value",
    "peak": "peak_value",
    "peak_portfolio_value": "peak_value",
    "portfolio_peak": "peak_value",
    "peak_time": "peak_date",
    "peak_day": "peak_date",
    "highest_date": "peak_date",
    "highest_value_date": "peak_date",
    "drawdown": "max_drawdown",
    "largest_drawdown": "max_drawdown",
    "max_drawdown_pct": "max_drawdown",
    "worst_drop": "max_drawdown",
    "worst_drop_date": "drawdown_date",
    "drawdown_trough": "drawdown_date",
    "drawdown_trough_date": "drawdown_date",
    "lowest": "lowest_value",
    "min_value": "lowest_value",
    "minimum_value": "lowest_value",
    "lowest_time": "lowest_date",
    "min_date": "lowest_date",
    "ending_value": "final_value",
    "ending_portfolio_value": "final_value",
    "cash_value": "final_value",
    "total_return_pct": "total_return",
    "benchmark_return_pct": "benchmark_return",
    "delta_vs_benchmark_pct": "benchmark_delta",
    "total_trades": "trade_count",
}


def overrides_refinement(
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot,
    proposed: str | None,
    reason_codes: list[str],
) -> bool:
    """Keep typed latest-result questions answerable during pending refinements."""

    if (
        interpretation.semantic_turn_act != "result_followup"
        or snapshot.latest_backtest_result_reference is None
    ):
        return False
    # Only claim the latest-result target when a fact key actually resolves;
    # otherwise leave the target as pending_refinement so the misroute guard
    # re-prompts the user to finish their refinement instead of silently
    # answering and stalling the refinement.
    if _requested_fact_key(interpretation) is None:
        return False
    if proposed != "latest_result":
        reason_codes.append("latest_result_overrode_pending_refinement")
    return True


@dataclass(frozen=True)
class _CurvePoint:
    time: str
    value: float


@dataclass(frozen=True)
class _FactAnswer:
    fact_key: str
    response: str
    facts: dict[str, Any]


@dataclass(frozen=True)
class _FactLimitation:
    fact_key: str
    response: str
    supported_next_step: str
    facts: dict[str, Any]


@dataclass(frozen=True)
class _CatalogFact:
    key: str
    label: str
    value: str
    source: str


def latest_result_answer_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
    language: str = "en",
) -> StageResult | None:
    """Answer factual latest-result questions from typed intent and run facts."""

    if decision.semantic_turn_act != "result_followup":
        return None
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return None
    requested_fact_key = _requested_fact_key(decision)
    if requested_fact_key is None:
        return None

    reference = snapshot.latest_backtest_result_reference
    metadata = dict(reference.metadata)
    answer_language = _answer_language(decision=decision, fallback=language)
    answer = _answer_for_fact_key(
        metadata=metadata,
        fact_key=requested_fact_key,
        language=answer_language,
    )
    if answer is None:
        return None

    run_patch = _run_reference_patch(
        metadata=metadata,
        artifact_id=reference.artifact_id,
    )
    focus = _focus_for_heading(decision.result_followup_focus, requested_fact_key)
    if isinstance(answer, _FactAnswer):
        updated_decision = decision.model_copy(
            update={
                "intent": "conversation_followup",
                "requires_clarification": False,
                "missing_required_fields": [],
                "semantic_turn_act": "result_followup",
                "result_followup_focus": focus,
                "result_followup_fact_key": answer.fact_key,
                "reason_codes": [
                    *decision.reason_codes,
                    "latest_result_fact_answer",
                ],
            }
        )
        return StageResult(
            outcome="ready_to_respond",
            decision=updated_decision,
            stage_patch={
                "assistant_response": with_response_heading(
                    heading=result_followup_heading(focus, language=answer_language),
                    body=answer.response,
                ),
                "response_intent": {
                    "kind": "beginner_guidance",
                    "facts": {
                        **answer.facts,
                        "fact_key": answer.fact_key,
                        "source": answer.facts.get("source", "latest_result_facts"),
                    },
                },
                **run_patch,
            },
        )

    updated_decision = decision.model_copy(
        update={
            "intent": "conversation_followup",
            "requires_clarification": False,
            "missing_required_fields": [],
            "semantic_turn_act": "result_followup",
            "result_followup_focus": focus,
            "result_followup_fact_key": answer.fact_key,
            "reason_codes": [
                *decision.reason_codes,
                "latest_result_fact_limitation",
            ],
        }
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=updated_decision,
        stage_patch={
            "assistant_response": with_response_heading(
                heading=result_followup_heading(focus, language=answer_language),
                body=answer.response,
            ),
            "response_intent": {
                "kind": "unsupported_recovery",
                "facts": {
                    **answer.facts,
                    "limitation_code": "latest_result_metric_unavailable",
                    "requested_metric": answer.fact_key,
                    "supported_next_step": answer.supported_next_step,
                },
                "options": [
                    {
                        "label": answer.supported_next_step,
                        "replacement_values": {
                            "semantic_turn_act": "result_followup",
                            "artifact_target": "latest_result",
                        },
                    }
                ],
            },
            **run_patch,
        },
    )


def _answer_language(*, decision: InterpretDecision, fallback: str) -> str:
    if (
        isinstance(decision.detected_user_language, str)
        and decision.detected_user_language.strip()
    ):
        return decision.detected_user_language.strip()
    extra_parameters = decision.candidate_strategy_draft.extra_parameters
    typed_language = extra_parameters.get("language")
    if isinstance(typed_language, str) and typed_language.strip():
        return typed_language.strip()
    return fallback


def _requested_fact_key(
    decision: InterpretDecision | StructuredInterpretation,
) -> str | None:
    explicit_key = _normalize_fact_key(decision.result_followup_fact_key)
    if explicit_key:
        return explicit_key
    focus = decision.result_followup_focus
    if focus is None:
        return None
    return _FACT_FOCUSES.get(focus)


def _answer_for_fact_key(
    *,
    metadata: dict[str, Any],
    fact_key: str,
    language: str,
) -> _FactAnswer | _FactLimitation | None:
    if fact_key in {"peak_date", "peak_value"}:
        return _peak_answer(metadata=metadata, fact_key=fact_key, language=language)
    if fact_key in {"drawdown_date", "max_drawdown"}:
        return _drawdown_answer(metadata=metadata, fact_key=fact_key, language=language)
    if fact_key in {"lowest_date", "lowest_value"}:
        return _lowest_answer(metadata=metadata, fact_key=fact_key, language=language)
    if fact_key == "final_value":
        return _final_value_answer(metadata=metadata, language=language)

    catalog = _result_fact_catalog(metadata)
    fact = catalog.get(fact_key)
    if fact is None:
        return _limitation(
            fact_key=fact_key,
            available_facts=sorted(catalog),
            language=language,
        )
    return _generic_fact_answer(fact=fact, language=language)


def _peak_answer(
    *,
    metadata: dict[str, Any],
    fact_key: str,
    language: str,
) -> _FactAnswer | _FactLimitation:
    point = _peak_point(metadata)
    fallback_value = _peak_value(metadata)
    currency = _currency(metadata)
    if point is not None:
        value = _format_money(point.value, currency=currency)
        if _is_spanish(language):
            response = (
                f"El valor máximo de la cartera fue {value} el {point.time}. "
                "Viene de la curva de valor guardada de la estrategia, no del "
                "máximo intradía de un activo."
            )
        else:
            response = (
                f"The peak portfolio value was {value} on {point.time}. That comes "
                "from the saved strategy equity curve, not an asset's intraday high."
            )
        return _FactAnswer(
            fact_key=fact_key,
            response=response,
            facts={
                "peak_date": point.time,
                "peak_value": round(point.value, 2),
                "currency": currency,
                "source": "chart.series",
            },
        )
    if fact_key == "peak_value" and fallback_value is not None:
        value = _format_money(fallback_value, currency=currency)
        response = (
            f"El valor máximo de la cartera fue {value}. Este resultado guardado "
            "no incluye la curva necesaria para decir la fecha exacta."
            if _is_spanish(language)
            else (
                f"The peak portfolio value was {value}. This saved result does "
                "not include the equity curve needed to name the exact date."
            )
        )
        return _FactAnswer(
            fact_key=fact_key,
            response=response,
            facts={
                "peak_value": round(fallback_value, 2),
                "currency": currency,
                "source": "value_summary",
            },
        )
    return _limitation(
        fact_key=fact_key,
        available_facts=sorted(_result_fact_catalog(metadata)),
        language=language,
        related_fact=(
            f"peak value {_format_money(fallback_value, currency=currency)}"
            if fallback_value is not None
            else None
        ),
    )


def _drawdown_answer(
    *,
    metadata: dict[str, Any],
    fact_key: str,
    language: str,
) -> _FactAnswer | _FactLimitation:
    drawdown = _drawdown_trough(metadata)
    metric = metric_number(
        metadata,
        paths=(
            ("metrics", "aggregate", "risk", "max_drawdown_pct"),
            ("metrics", "aggregate", "max_drawdown_pct"),
        ),
    )
    if drawdown is None and fact_key == "drawdown_date":
        return _limitation(
            fact_key=fact_key,
            available_facts=sorted(_result_fact_catalog(metadata)),
            language=language,
            related_fact=(
                f"max drawdown {_format_percent(metric, signed=False)}"
                if metric is not None
                else None
            ),
        )
    if drawdown is None and metric is None:
        return _limitation(
            fact_key=fact_key,
            available_facts=sorted(_result_fact_catalog(metadata)),
            language=language,
        )

    drawdown_pct = metric if metric is not None else drawdown[1]
    formatted = _format_percent(drawdown_pct, signed=False)
    facts: dict[str, Any] = {
        "max_drawdown": formatted,
        "source": "metrics.aggregate.risk",
    }
    if drawdown is not None:
        facts["drawdown_date"] = drawdown[0]
        facts["source"] = "chart.series"
    if fact_key == "drawdown_date" and drawdown is not None:
        # Pair the trough DATE with the magnitude computed at that same trough,
        # not the aggregate metric — otherwise the stated % and date can
        # describe different drawdown points.
        trough_formatted = _format_percent(drawdown[1], signed=False)
        facts["max_drawdown"] = trough_formatted
        response = (
            f"La caída más grande tocó fondo el {drawdown[0]}, con {trough_formatted} "
            "por debajo del máximo anterior de la cartera."
            if _is_spanish(language)
            else (
                f"The largest drawdown bottomed on {drawdown[0]} at {trough_formatted} "
                "below the prior portfolio peak."
            )
        )
    elif drawdown is not None:
        response = (
            f"La caída máxima fue {formatted}, y tocó fondo el {drawdown[0]}."
            if _is_spanish(language)
            else f"The max drawdown was {formatted}, bottoming on {drawdown[0]}."
        )
    else:
        response = (
            f"La caída máxima fue {formatted}."
            if _is_spanish(language)
            else f"The max drawdown was {formatted}."
        )
    return _FactAnswer(fact_key=fact_key, response=response, facts=facts)


def _lowest_answer(
    *,
    metadata: dict[str, Any],
    fact_key: str,
    language: str,
) -> _FactAnswer | _FactLimitation:
    point = _lowest_point(metadata)
    fallback_value = _lowest_value(metadata)
    currency = _currency(metadata)
    if point is not None:
        value = _format_money(point.value, currency=currency)
        response = (
            f"El valor más bajo de la cartera fue {value} el {point.time}."
            if _is_spanish(language)
            else f"The lowest portfolio value was {value} on {point.time}."
        )
        return _FactAnswer(
            fact_key=fact_key,
            response=response,
            facts={
                "lowest_date": point.time,
                "lowest_value": round(point.value, 2),
                "currency": currency,
                "source": "chart.series",
            },
        )
    if fact_key == "lowest_value" and fallback_value is not None:
        value = _format_money(fallback_value, currency=currency)
        response = (
            f"El valor más bajo de la cartera fue {value}. Este resultado guardado "
            "no incluye la curva necesaria para decir la fecha exacta."
            if _is_spanish(language)
            else (
                f"The lowest portfolio value was {value}. This saved result does "
                "not include the equity curve needed to name the exact date."
            )
        )
        return _FactAnswer(
            fact_key=fact_key,
            response=response,
            facts={
                "lowest_value": round(fallback_value, 2),
                "currency": currency,
                "source": "value_summary",
            },
        )
    return _limitation(
        fact_key=fact_key,
        available_facts=sorted(_result_fact_catalog(metadata)),
        language=language,
    )


def _final_value_answer(
    *,
    metadata: dict[str, Any],
    language: str,
) -> _FactAnswer | _FactLimitation:
    series = _curve_points(metadata)
    if series:
        point = series[-1]
        value = _format_money(point.value, currency=_currency(metadata))
        response = (
            f"El valor final guardado de la cartera fue {value} el {point.time}."
            if _is_spanish(language)
            else f"The saved final portfolio value was {value} on {point.time}."
        )
        return _FactAnswer(
            fact_key="final_value",
            response=response,
            facts={
                "final_date": point.time,
                "final_value": round(point.value, 2),
                "currency": _currency(metadata),
                "source": "chart.series",
            },
        )
    catalog = _result_fact_catalog(metadata)
    fact = catalog.get("final_value")
    if fact is not None:
        return _generic_fact_answer(fact=fact, language=language)
    return _limitation(
        fact_key="final_value",
        available_facts=sorted(catalog),
        language=language,
    )


def _generic_fact_answer(*, fact: _CatalogFact, language: str) -> _FactAnswer:
    label = " ".join(fact.label.split()).strip() or fact.key.replace("_", " ")
    value = " ".join(fact.value.split()).strip()
    response = (
        f"El dato de {label} para este resultado es {value}."
        if _is_spanish(language)
        else f"The {label} for this result is {value}."
    )
    return _FactAnswer(
        fact_key=fact.key,
        response=response,
        facts={"label": label, "value": value, "source": fact.source},
    )


def _limitation(
    *,
    fact_key: str,
    available_facts: list[str],
    language: str,
    related_fact: str | None = None,
) -> _FactLimitation:
    supported_next_step = (
        "Ask about total return, benchmark comparison, max drawdown, or what was tested"
    )
    if _is_spanish(language):
        supported_next_step = (
            "Pregunta por retorno total, comparación con referencia, caída máxima, "
            "o qué se probó"
        )
        response = (
            f"El dato exacto de {_human_fact_name(fact_key, language=language)} "
            "no está disponible para este resultado guardado."
        )
        if related_fact:
            response += f" Sí puedo ver {related_fact}."
        response += f" {supported_next_step}."
    else:
        response = (
            f"The exact {_human_fact_name(fact_key, language=language)} is not "
            "available for this saved result because the stored equity curve or "
            "metric is missing."
        )
        if related_fact:
            response += f" I can still see the {related_fact}."
        response += (
            " I can still answer supported facts from this result, like total "
            "return, benchmark comparison, max drawdown, or what was tested."
        )
    return _FactLimitation(
        fact_key=fact_key,
        response=response,
        supported_next_step=supported_next_step,
        facts={
            "available_result_facts": available_facts,
            "related_fact": related_fact,
        },
    )


def _result_fact_catalog(metadata: dict[str, Any]) -> dict[str, _CatalogFact]:
    catalog: dict[str, _CatalogFact] = {}
    for key, value in result_followup_fact_bank(metadata).items():
        if key in {"next_experiment_options"}:
            continue
        _add_catalog_fact(
            catalog,
            key=key,
            label=_human_fact_name(key),
            value=value,
            source="result_followup_fact_bank",
        )

    result_card = _mapping(metadata.get("result_card"))
    for row in _rows(result_card.get("rows")):
        key = _normalize_fact_key(row.get("key"))
        value = str(row.get("value") or "").strip()
        if key and value:
            _add_catalog_fact(
                catalog,
                key=key,
                label=str(row.get("label") or key.replace("_", " ")),
                value=value,
                source="result_card.rows",
            )

    for key, label, paths, formatter in _metric_fact_specs():
        value = metric_number(metadata, paths=paths)
        if value is None:
            continue
        _add_catalog_fact(
            catalog,
            key=key,
            label=label,
            value=formatter(value),
            source="metrics.aggregate",
        )

    config = _mapping(metadata.get("config_snapshot") or metadata.get("config"))
    date_range = date_range_label(config.get("date_range") or metadata.get("date_range"))
    if date_range:
        _add_catalog_fact(
            catalog,
            key="date_range",
            label="date range",
            value=date_range,
            source="config_snapshot",
        )
    benchmark = str(
        config.get("benchmark_symbol") or metadata.get("benchmark_symbol") or ""
    ).strip()
    if benchmark:
        _add_catalog_fact(
            catalog,
            key="benchmark_symbol",
            label="benchmark",
            value=benchmark,
            source="config_snapshot",
        )
    symbols = metadata.get("symbols") or config.get("symbols")
    if isinstance(symbols, list) and symbols:
        _add_catalog_fact(
            catalog,
            key="symbols",
            label="symbols",
            value=", ".join(str(symbol) for symbol in symbols),
            source="config_snapshot",
        )
    return catalog


def _metric_fact_specs() -> list[
    tuple[str, str, tuple[tuple[str, ...], ...], Any]
]:
    return [
        (
            "total_return",
            "total return",
            (("metrics", "aggregate", "performance", "total_return_pct"),),
            lambda value: _format_percent(value),
        ),
        (
            "benchmark_return",
            "benchmark return",
            (("metrics", "aggregate", "performance", "benchmark_return_pct"),),
            lambda value: _format_percent(value),
        ),
        (
            "benchmark_delta",
            "benchmark comparison",
            (("metrics", "aggregate", "performance", "delta_vs_benchmark_pct"),),
            lambda value: _format_percent(value),
        ),
        (
            "profit",
            "profit",
            (("metrics", "aggregate", "performance", "profit"),),
            lambda value: _format_money(value),
        ),
        (
            "annualized_return",
            "annualized return",
            (("metrics", "aggregate", "performance", "annualized_return_pct"),),
            lambda value: _format_percent(value),
        ),
        (
            "max_drawdown",
            "max drawdown",
            (
                ("metrics", "aggregate", "risk", "max_drawdown_pct"),
                ("metrics", "aggregate", "max_drawdown_pct"),
            ),
            lambda value: _format_percent(value, signed=False),
        ),
        (
            "volatility",
            "volatility",
            (("metrics", "aggregate", "risk", "volatility_pct"),),
            lambda value: _format_percent(value, signed=False),
        ),
        (
            "win_rate",
            "win rate",
            (("metrics", "aggregate", "efficiency", "win_rate"),),
            lambda value: _format_percent(value * 100.0, signed=False),
        ),
        (
            "trade_count",
            "trade count",
            (("metrics", "aggregate", "efficiency", "total_trades"),),
            lambda value: f"{int(value)} trades",
        ),
        (
            "profit_factor",
            "profit factor",
            (("metrics", "aggregate", "efficiency", "profit_factor"),),
            lambda value: _format_decimal(value),
        ),
        (
            "sharpe_ratio",
            "Sharpe ratio",
            (("metrics", "aggregate", "efficiency", "sharpe_ratio"),),
            lambda value: _format_decimal(value),
        ),
    ]


def _add_catalog_fact(
    catalog: dict[str, _CatalogFact],
    *,
    key: str,
    label: str,
    value: str,
    source: str,
) -> None:
    normalized = _normalize_fact_key(key)
    if not normalized or not value:
        return
    canonical_key = _FACT_KEY_ALIASES.get(normalized, normalized)
    catalog[canonical_key] = _CatalogFact(
        key=canonical_key,
        label=label,
        value=value,
        source=source,
    )
    if normalized != canonical_key:
        catalog[normalized] = catalog[canonical_key]


def _curve_points(metadata: dict[str, Any]) -> list[_CurvePoint]:
    chart = _chart(metadata)
    raw_series = chart.get("series")
    if not isinstance(raw_series, list):
        return []
    points: list[_CurvePoint] = []
    for item in raw_series:
        point = _mapping(item)
        raw_time = point.get("time") or point.get("date") or point.get("timestamp")
        value = _coerce_float(
            point.get("value")
            if "value" in point
            else point.get("portfolio_value", point.get("equity", point.get("y")))
        )
        if raw_time is None or value is None:
            continue
        points.append(_CurvePoint(time=str(raw_time), value=value))
    return points


def _peak_point(metadata: dict[str, Any]) -> _CurvePoint | None:
    points = _curve_points(metadata)
    if not points:
        return None
    return max(enumerate(points), key=lambda item: (item[1].value, -item[0]))[1]


def _lowest_point(metadata: dict[str, Any]) -> _CurvePoint | None:
    points = _curve_points(metadata)
    if not points:
        return None
    return min(enumerate(points), key=lambda item: (item[1].value, item[0]))[1]


def _drawdown_trough(metadata: dict[str, Any]) -> tuple[str, float] | None:
    points = _curve_points(metadata)
    if not points:
        return None
    running_peak = points[0].value
    worst: tuple[str, float] | None = None
    for point in points:
        if point.value > running_peak:
            running_peak = point.value
        if running_peak <= 0:
            continue
        drawdown_pct = (point.value / running_peak - 1.0) * 100.0
        if worst is None or drawdown_pct < worst[1]:
            worst = (point.time, drawdown_pct)
    return worst


def _peak_value(metadata: dict[str, Any]) -> float | None:
    point = _peak_point(metadata)
    if point is not None:
        return point.value
    return metric_number(
        metadata,
        paths=(
            ("chart", "value_summary", "peak_value"),
            ("result_card", "chart", "value_summary", "peak_value"),
            ("metrics", "aggregate", "performance", "portfolio_value_range", "peak_value"),
            ("value_summary", "peak_value"),
            ("value_extrema", "peak_value"),
        ),
    )


def _lowest_value(metadata: dict[str, Any]) -> float | None:
    point = _lowest_point(metadata)
    if point is not None:
        return point.value
    return metric_number(
        metadata,
        paths=(
            ("chart", "value_summary", "lowest_value"),
            ("result_card", "chart", "value_summary", "lowest_value"),
            ("metrics", "aggregate", "performance", "portfolio_value_range", "lowest_value"),
            ("value_summary", "lowest_value"),
            ("value_extrema", "lowest_value"),
        ),
    )


def _chart(metadata: dict[str, Any]) -> dict[str, Any]:
    chart = _mapping(metadata.get("chart"))
    if chart:
        return dict(chart)
    result_card = _mapping(metadata.get("result_card"))
    return dict(_mapping(result_card.get("chart")))


def _currency(metadata: dict[str, Any]) -> str:
    chart = _chart(metadata)
    summary = _mapping(chart.get("value_summary"))
    value = str(
        chart.get("currency")
        or summary.get("currency")
        or _get_path(
            metadata,
            ("metrics", "aggregate", "performance", "portfolio_value_range", "currency"),
        )
        or "USD"
    ).strip()
    return value or "USD"


def _run_reference_patch(
    *,
    metadata: dict[str, Any],
    artifact_id: str,
) -> dict[str, Any]:
    run_id = _string_value(
        metadata.get("run_id")
        or metadata.get("result_run_id")
        or metadata.get("latest_run_id")
        or artifact_id
    )
    patch: dict[str, Any] = {
        "result_fact_bank": metadata,
    }
    if run_id:
        patch["result_run_id"] = run_id
        patch["latest_run_id"] = _string_value(metadata.get("latest_run_id")) or run_id
    strategy_id = _string_value(
        metadata.get("strategy_id") or metadata.get("result_strategy_id")
    )
    if strategy_id:
        patch["result_strategy_id"] = strategy_id
    conversation_id = _string_value(
        metadata.get("conversation_id") or metadata.get("result_conversation_id")
    )
    if conversation_id:
        patch["result_conversation_id"] = conversation_id
    return patch


def _focus_for_heading(
    focus: ResultFollowupFocus | None,
    fact_key: str,
) -> ResultFollowupFocus:
    if fact_key == "peak_date":
        return "peak_date"
    if fact_key == "peak_value":
        return "peak_value"
    if fact_key == "drawdown_date":
        return "drawdown_date"
    if fact_key == "max_drawdown":
        return "max_drawdown"
    if focus in {
        "peak_date",
        "peak_value",
        "drawdown_date",
        "max_drawdown",
        "result_card_fact",
    }:
        return focus
    return "result_card_fact"


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[Mapping[str, Any]] = []
    for item in value:
        row = _mapping(item)
        if row:
            rows.append(row)
    return rows


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _get_path(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for part in path:
        current = _mapping(current).get(part)
        if current is None:
            return None
    return current


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_value(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_fact_key(value: Any) -> str | None:
    text = str(value or "").strip().casefold()
    if not text:
        return None
    for old, new in (("-", "_"), (" ", "_"), (".", "_"), ("/", "_")):
        text = text.replace(old, new)
    text = "_".join(part for part in text.split("_") if part)
    return _FACT_KEY_ALIASES.get(text, text)


def _format_money(value: float, *, currency: str = "USD") -> str:
    prefix = "$" if currency.upper() == "USD" else f"{currency.upper()} "
    rounded = round(float(value), 2)
    if abs(rounded - round(rounded)) < 0.005:
        return f"{prefix}{rounded:,.0f}"
    return f"{prefix}{rounded:,.2f}"


def _format_percent(value: float, *, signed: bool = True) -> str:
    number = abs(float(value)) if not signed else float(value)
    sign = "+" if signed and number > 0 else ""
    return f"{sign}{_format_decimal(number)}%"


def _format_decimal(value: float) -> str:
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _human_fact_name(key: str, *, language: str = "en") -> str:
    english = {
        "peak_date": "peak date",
        "peak_value": "peak value",
        "drawdown_date": "drawdown date",
        "max_drawdown": "max drawdown",
        "lowest_date": "lowest date",
        "lowest_value": "lowest value",
        "final_value": "final value",
        "total_return": "total return",
        "benchmark_return": "benchmark return",
        "benchmark_delta": "benchmark comparison",
        "benchmark_symbol": "benchmark",
        "trade_count": "trade count",
        "sortino_ratio": "Sortino ratio",
        "sharpe_ratio": "Sharpe ratio",
        "volatility": "volatility",
        "win_rate": "win rate",
        "profit_factor": "profit factor",
        "date_range": "date range",
        "symbols": "symbols",
        "strategy": "strategy",
    }
    spanish = {
        "peak_date": "fecha del máximo",
        "peak_value": "valor máximo",
        "drawdown_date": "fecha de la caída máxima",
        "max_drawdown": "caída máxima",
        "lowest_date": "fecha del valor más bajo",
        "lowest_value": "valor más bajo",
        "final_value": "valor final",
        "total_return": "retorno total",
        "benchmark_return": "retorno de referencia",
        "benchmark_delta": "comparación con referencia",
        "benchmark_symbol": "referencia",
        "trade_count": "número de operaciones",
        "sortino_ratio": "ratio de Sortino",
        "sharpe_ratio": "ratio de Sharpe",
        "volatility": "volatilidad",
        "win_rate": "tasa de aciertos",
        "profit_factor": "factor de beneficio",
        "date_range": "periodo",
        "symbols": "activos",
        "strategy": "estrategia",
    }
    labels = spanish if _is_spanish(language) else english
    return labels.get(key, key.replace("_", " "))


def _is_spanish(language: str) -> bool:
    return str(language or "").lower().startswith("es")
