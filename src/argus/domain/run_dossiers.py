from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast

from argus.api.schemas import (
    DecisionState,
    RunDossier,
    RunDossierTested,
    SearchDecisionAction,
    SearchDossierDecision,
    SearchDossierMetric,
    SearchDossierOutcome,
    SearchRunFreshAction,
    SearchRunFreshSetup,
)
from argus.domain.evidence import evidence_preview_from_payload

_DECISION_STATES: tuple[DecisionState, ...] = (
    "promising",
    "watching",
    "rejected",
    "revisit_later",
)
_MAX_METRICS = 4
_MAX_LABEL_LENGTH = 160
_RUN_FRESH_STRATEGIES = {
    "buy_and_hold",
    "dca_accumulation",
    "indicator_threshold",
    "signal_strategy",
}
_RUN_FRESH_CADENCES = {
    "daily",
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
}
_RUN_FRESH_PARAMETER_KEYS = (
    "indicator",
    "indicator_period",
    "entry_threshold",
    "exit_threshold",
    "fast_period",
    "slow_period",
    "moving_average_type",
)


def project_run_dossier(
    *,
    run: Mapping[str, Any],
    artifact: Mapping[str, Any],
    decision: Mapping[str, Any] | None,
    result_message_id: str | None,
    allow_decision_action: bool,
    language: str,
) -> RunDossier:
    """Project one run and its artifact into the bounded public dossier shape."""
    run_id = text(run.get("id"))
    artifact_id = text(artifact.get("id"))
    if run_id is None or text(artifact.get("source_run_id")) != run_id:
        raise ValueError("Run dossier requires one matching evidence-backed run.")
    if artifact_id is None:
        raise ValueError("Run dossier evidence artifact requires an id.")

    run_label = run_label_for(run)
    preview = evidence_preview_from_payload(
        digest=artifact.get("digest"),
        title=artifact.get("title"),
        payload=(
            artifact.get("payload")
            if isinstance(artifact.get("payload"), dict)
            else None
        ),
    )
    metric_rows: list[SearchDossierMetric] = []
    metrics = preview.get("metrics_summary")
    if isinstance(metrics, dict):
        for name, value in metrics.items():
            if len(metric_rows) >= _MAX_METRICS:
                break
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                metric_rows.append(SearchDossierMetric(name=name, value=value))

    current_decision = (
        decision
        if decision is not None
        and text(decision.get("evidence_artifact_id")) == artifact_id
        else None
    )
    decision_state = (
        current_decision.get("decision_state") if current_decision is not None else None
    )
    decision_projection = (
        SearchDossierDecision(
            state=cast(DecisionState, decision_state),
            note=_bounded_note(current_decision.get("note"), 2000),
            run_label=run_label,
        )
        if decision_state in _DECISION_STATES
        else None
    )

    actions = []
    # The run-fresh transport remains the already-shipped typed action until the
    # separate typed-retest lane replaces it.
    run_fresh_action = project_run_fresh_action(run=run, language=language)
    if run_fresh_action is not None:
        actions.append(run_fresh_action)
    if allow_decision_action:
        actions.append(
            SearchDecisionAction(
                evidence_artifact_id=artifact_id,
                decision_state=(
                    cast(DecisionState, decision_state)
                    if decision_state in _DECISION_STATES
                    else None
                ),
                note=(
                    _bounded_note(current_decision.get("note"), 2000)
                    if current_decision is not None
                    else None
                ),
                run_label=run_label,
            )
        )

    config = mapping(run.get("config_snapshot"))
    resolved_parameters = mapping(config.get("resolved_parameters"))
    start_date, end_date = run_date_span(run)
    return RunDossier(
        run_id=run_id,
        run_label=run_label,
        completed_at=row_activity(run),
        result_message_id=text(result_message_id),
        tested=RunDossierTested(
            symbols=run_symbols(run),
            strategy_family=_bounded_text(strategy_family_for(run), 80),
            cadence=_bounded_text(
                resolved_parameters.get("cadence") or config.get("cadence"),
                24,
            ),
            timeframe=_bounded_text(
                resolved_parameters.get("timeframe") or config.get("timeframe"),
                24,
            ),
            start_date=start_date,
            end_date=end_date,
        ),
        outcome=SearchDossierOutcome(
            run_label=run_label,
            completed_at=row_activity(run),
            benchmark_symbol=_bounded_text(
                preview.get("benchmark_symbol") or run.get("benchmark_symbol"),
                24,
            ),
            quick_take=_bounded_text(preview.get("quick_take"), 500),
            metrics=metric_rows,
        ),
        decision=decision_projection,
        actions=actions,
    )


def newest_evidence_backed_completed_runs(
    *,
    runs: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Return newest-first completed runs with one current evidence artifact."""
    latest_artifact_by_run: dict[str, Mapping[str, Any]] = {}
    for artifact in evidence:
        run_id = text(artifact.get("source_run_id"))
        artifact_id = text(artifact.get("id"))
        if run_id is None or artifact_id is None:
            continue
        current = latest_artifact_by_run.get(run_id)
        if current is None or (
            row_activity(artifact),
            artifact_id,
        ) > (
            row_activity(current),
            text(current.get("id")) or "",
        ):
            latest_artifact_by_run[run_id] = artifact

    eligible = [
        (run, latest_artifact_by_run[run_id])
        for run in runs
        if run.get("status", "completed") == "completed"
        and (run_id := text(run.get("id"))) is not None
        and run_id in latest_artifact_by_run
    ]
    return sorted(
        eligible,
        key=lambda pair: (row_activity(pair[0]), text(pair[0].get("id")) or ""),
        reverse=True,
    )


def current_decision_for(
    artifact: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    artifact_id = text(artifact.get("id"))
    return max(
        (
            decision
            for decision in decisions
            if text(decision.get("evidence_artifact_id")) == artifact_id
        ),
        key=lambda row: (row_activity(row), text(row.get("id")) or ""),
        default=None,
    )


def result_message_id_for(
    run: Mapping[str, Any],
    messages: Sequence[Mapping[str, Any]],
) -> str | None:
    run_id = text(run.get("id"))
    candidates = [
        message
        for message in messages
        if message.get("role") == "assistant"
        and (
            text(message_metadata(message).get("result_run_id")) == run_id
            or text(message_metadata(message).get("latest_run_id")) == run_id
        )
        and text(message.get("id")) is not None
    ]
    latest = max(
        candidates,
        key=lambda row: (row_activity(row), text(row.get("id")) or ""),
        default=None,
    )
    return text(latest.get("id")) if latest is not None else None


def project_run_fresh_action(
    *,
    run: Mapping[str, Any],
    language: str,
) -> SearchRunFreshAction | None:
    run_id = text(run.get("id"))
    config = mapping(run.get("config_snapshot"))
    resolved_strategy = mapping(config.get("resolved_strategy"))
    resolved_parameters = mapping(config.get("resolved_parameters"))
    resolved_engine_config = mapping(resolved_parameters.get("engine_config"))
    snapshot_engine_config = mapping(config.get("engine_config"))
    strategy_type = text(
        resolved_strategy.get("strategy_type") or config.get("template")
    )
    if strategy_type not in _RUN_FRESH_STRATEGIES or run_id is None:
        return None

    symbols = run_symbols(run)
    asset_class = text(
        resolved_strategy.get("asset_class") or run.get("asset_class")
    )
    timeframe = text(resolved_parameters.get("timeframe") or config.get("timeframe"))
    benchmark_symbol = text(
        resolved_parameters.get("benchmark_symbol")
        or config.get("benchmark_symbol")
        or run.get("benchmark_symbol")
    )
    original_start, original_end = run_date_span(run)
    if (
        not symbols
        or asset_class not in {"equity", "crypto", "currency_pair"}
        or timeframe is None
        or benchmark_symbol is None
        or original_start is None
        or original_end is None
        or original_end < original_start
    ):
        return None

    sizing_mode = text(resolved_parameters.get("sizing_mode"))
    capital_amount = _positive_number(
        resolved_parameters.get("capital_amount")
        or config.get("starting_capital")
        or config.get("capital_amount")
    )
    position_size = _positive_number(resolved_parameters.get("position_size"))
    if sizing_mode is None:
        sizing_mode = "position_size" if position_size is not None else "capital_amount"
    if sizing_mode == "capital_amount":
        position_size = None
    elif sizing_mode == "position_size":
        capital_amount = None
    else:
        return None

    cadence = text(resolved_parameters.get("cadence") or config.get("cadence"))
    if strategy_type == "dca_accumulation":
        if cadence not in _RUN_FRESH_CADENCES:
            return None
        recurring_contribution = _consistent_number(
            resolved_parameters.get("recurring_contribution"),
            resolved_engine_config.get("recurring_contribution"),
            snapshot_engine_config.get("recurring_contribution"),
        )
        starting_principal = _consistent_number(
            resolved_parameters.get("starting_principal"),
            resolved_engine_config.get("starting_principal"),
            snapshot_engine_config.get("starting_principal"),
            allow_zero=True,
        )
        if (
            recurring_contribution is None
            or starting_principal != 0
            or capital_amount != recurring_contribution
        ):
            return None
    else:
        cadence = None
        recurring_contribution = None
        starting_principal = None

    today = date.today()
    current_start = today - timedelta(days=(original_end - original_start).days)
    parameters = {
        key: resolved_parameters[key]
        for key in _RUN_FRESH_PARAMETER_KEYS
        if key in resolved_parameters
        and isinstance(resolved_parameters[key], (str, int, float, bool))
    }
    execution_realism_valid, execution_realism = _consistent_mapping(
        resolved_engine_config.get("_execution_realism"),
        snapshot_engine_config.get("_execution_realism"),
        resolved_parameters.get("_execution_realism"),
        resolved_parameters.get("execution_realism"),
        config.get("_execution_realism"),
    )
    if not execution_realism_valid:
        return None
    try:
        setup = SearchRunFreshSetup(
            strategy_type=strategy_type,
            symbols=symbols,
            asset_class=asset_class,
            timeframe=timeframe,
            date_range={"start": current_start, "end": today},
            sizing_mode=sizing_mode,
            capital_amount=capital_amount,
            position_size=position_size,
            cadence=cadence,
            recurring_contribution=recurring_contribution,
            starting_principal=starting_principal,
            benchmark_symbol=benchmark_symbol,
            entry_rule=_mapping_or_none(resolved_strategy.get("entry_rule")),
            exit_rule=_mapping_or_none(resolved_strategy.get("exit_rule")),
            rule_spec=_mapping_or_none(
                resolved_strategy.get("rule_spec")
                or resolved_parameters.get("rule_spec")
                or config.get("rule_spec")
            ),
            parameters=parameters,
            execution_realism=execution_realism,
        )
        return SearchRunFreshAction(
            source_run_id=run_id,
            run_label=run_label_for(run),
            canonical_setup=setup,
            send_text=_run_fresh_send_text(setup=setup, language=language),
        )
    except ValueError:
        return None


def _run_fresh_send_text(*, setup: SearchRunFreshSetup, language: str) -> str:
    symbols = ", ".join(setup.symbols)
    amount = (
        _format_number(setup.capital_amount)
        if setup.sizing_mode == "capital_amount"
        else _format_number(setup.position_size)
    )
    if language == "es-419":
        cadence = {
            "daily": "diaria",
            "weekly": "semanal",
            "biweekly": "quincenal",
            "monthly": "mensual",
            "quarterly": "trimestral",
        }.get(setup.cadence or "", setup.cadence or "")
        strategy = {
            "buy_and_hold": "comprar y mantener",
            "dca_accumulation": f"acumulación DCA {cadence}",
            "indicator_threshold": "estrategia de umbral de indicador",
            "signal_strategy": "estrategia de señales",
        }[setup.strategy_type]
        if setup.strategy_type == "dca_accumulation":
            sizing = (
                f"un aporte recurrente de "
                f"${_format_number(setup.recurring_contribution)} {cadence} y "
                f"capital inicial de ${_format_number(setup.starting_principal)}"
            )
        else:
            sizing = (
                f"${amount} de capital inicial"
                if setup.sizing_mode == "capital_amount"
                else f"{amount} por posición"
            )
        prefix = (
            "Prueba nuevamente esta configuración compatible exacta del "
            f"{setup.date_range.start.isoformat()} al "
            f"{setup.date_range.end.isoformat()}: {strategy} {symbols} en "
            f"{setup.timeframe} con {sizing}, referencia "
            f"{setup.benchmark_symbol}, solo posiciones largas y pesos iguales"
        )
        suffix = (
            ". Muestra la confirmación Lista para ejecutar; todavía no la ejecutes."
        )
        detail_labels = {
            "entry_rule": "regla de entrada",
            "exit_rule": "regla de salida",
            "rule_spec": "especificación de reglas",
            "parameters": "parámetros",
            "execution_realism": "costos modelados",
        }
    else:
        cadence = setup.cadence or ""
        strategy = {
            "buy_and_hold": "buy and hold",
            "dca_accumulation": f"{cadence} DCA accumulation",
            "indicator_threshold": "indicator threshold strategy",
            "signal_strategy": "signal strategy",
        }[setup.strategy_type]
        if setup.strategy_type == "dca_accumulation":
            sizing = (
                f"a ${_format_number(setup.recurring_contribution)} {cadence} "
                "recurring contribution and "
                f"${_format_number(setup.starting_principal)} starting principal"
            )
        else:
            sizing = (
                f"${amount} starting capital"
                if setup.sizing_mode == "capital_amount"
                else f"{amount} per position"
            )
        prefix = (
            "Test this exact supported setup again from "
            f"{setup.date_range.start.isoformat()} to "
            f"{setup.date_range.end.isoformat()}: {strategy} {symbols} on "
            f"{setup.timeframe} with {sizing}, benchmark "
            f"{setup.benchmark_symbol}, long only and equal weight"
        )
        suffix = ". Show the Ready-to-run confirmation; do not run it yet."
        detail_labels = {
            "entry_rule": "entry rule",
            "exit_rule": "exit rule",
            "rule_spec": "rule spec",
            "parameters": "parameters",
            "execution_realism": "execution realism",
        }
    details = [
        (detail_id, value)
        for detail_id, value in (
            ("entry_rule", setup.entry_rule),
            ("exit_rule", setup.exit_rule),
            ("rule_spec", setup.rule_spec),
            ("parameters", setup.parameters or None),
            ("execution_realism", setup.execution_realism),
        )
        if value is not None
    ]
    if setup.strategy_type == "buy_and_hold":
        details = [
            pair for pair in details if pair[0] not in {"entry_rule", "exit_rule"}
        ]
    detail_text = "".join(
        f"; {detail_labels[detail_id]} {_stable_json(value)}"
        for detail_id, value in details
    )
    return f"{prefix}{detail_text}{suffix}"


def run_label_for(run: Mapping[str, Any]) -> str:
    card = run.get("conversation_result_card")
    if isinstance(card, Mapping):
        label = _bounded_text(card.get("title"), _MAX_LABEL_LENGTH)
        if label:
            return label
    symbols = ", ".join(run_symbols(run))
    return _bounded_text(f"{symbols} Backtest", _MAX_LABEL_LENGTH) or "Backtest run"


def strategy_family_for(run: Mapping[str, Any]) -> str | None:
    card = run.get("conversation_result_card")
    return text(mapping(run.get("config_snapshot")).get("template")) or (
        text(card.get("strategy_label")) if isinstance(card, Mapping) else None
    )


def run_symbols(run: Mapping[str, Any]) -> list[str]:
    symbols = text_list(run.get("symbols"))
    if symbols:
        return symbols
    card = run.get("conversation_result_card")
    return text_list(card.get("symbols")) if isinstance(card, Mapping) else []


def run_date_span(run: Mapping[str, Any]) -> tuple[date | None, date | None]:
    config = mapping(run.get("config_snapshot"))
    config_date_range = mapping(config.get("date_range"))
    card = run.get("conversation_result_card")
    card_date_range = (
        mapping(card.get("date_range")) if isinstance(card, Mapping) else {}
    )
    return (
        date_value(
            config.get("start_date")
            or config_date_range.get("start")
            or card_date_range.get("start")
        ),
        date_value(
            config.get("end_date")
            or config_date_range.get("end")
            or card_date_range.get("end")
        ),
    )


def row_activity(row: Mapping[str, Any]) -> datetime:
    for key in ("completed_at", "updated_at", "created_at"):
        value = row.get(key)
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is not None:
                return parsed
    return datetime.min.replace(tzinfo=timezone.utc)


def mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        bounded
        for item in value[:5]
        if (bounded := _bounded_text(item, 40)) is not None
    ]


def date_value(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def message_metadata(message: Mapping[str, Any]) -> Mapping[str, Any]:
    return mapping(message.get("metadata"))


def _bounded_text(value: object, maximum: int) -> str | None:
    value_text = text(value)
    return value_text[:maximum] if value_text is not None else None


def _bounded_note(value: object, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:maximum]


def _mapping_or_none(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _consistent_mapping(*values: object) -> tuple[bool, dict[str, Any] | None]:
    present = [value for value in values if value is not None]
    if not present:
        return True, None
    if any(not isinstance(value, Mapping) for value in present):
        return False, None
    mappings = [dict(cast(Mapping[str, Any], value)) for value in present]
    if any(value != mappings[0] for value in mappings[1:]):
        return False, None
    return True, mappings[0]


def _consistent_number(
    *values: object,
    allow_zero: bool = False,
) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    parsed = [
        _nonnegative_number(value) if allow_zero else _positive_number(value)
        for value in present
    ]
    if any(value is None for value in parsed):
        return None
    numbers = cast(list[float], parsed)
    if any(value != numbers[0] for value in numbers[1:]):
        return None
    return numbers[0]


def _positive_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value > 0 else None


def _nonnegative_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if value >= 0 else None


def _format_number(value: float | None) -> str:
    if value is None:
        return "0"
    return f"{value:g}"


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
