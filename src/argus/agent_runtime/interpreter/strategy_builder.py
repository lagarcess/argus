"""Canonical-strategy construction from LLM extraction: slot cleaning, capital grounding, indicator defaults, and field provenance.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.artifacts.asset_edits import normalized_asset_universe_operation
from argus.agent_runtime.interpreter.shared import (
    _RECURRING_CAPITAL_SOURCES,
    _TOTAL_CAPITAL_SOURCES,
    _bounded_date_evidence_candidates,
    _capital_source,
    _field_path_base,
    _has_complete_date_range_payload,
    _natural_time_language_candidates_from_hints,
    _selected_requested_field_base,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMRiskRule,
    LLMStrategyDraft,
    LLMUnsupportedConstraint,
)
from argus.agent_runtime.rule_specs import (
    executable_rule_spec_from_strategy,
    moving_average_crossover_text,
    opposite_moving_average_crossover_rule,
    strategy_rule,
)
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy as canonical_indicator_parameters_from_strategy,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import (
    ResolutionProvenance,
    SimplificationOption,
    StrategySummary,
    UnsupportedConstraint,
    dedupe_resolution_provenance_items,
)
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    executable_strategy_type,
    normalize_date_range_candidate,
)
from argus.domain.backtesting.rules import describe_rule_spec
from argus.domain.indicators import (
    executable_indicator_spec,
    normalize_indicator_parameters,
)
from argus.nlp.natural_time import (
    resolve_date_range_intent,
    resolve_rolling_window_intent_text,
)


def _strategy_from_llm(draft: LLMStrategyDraft) -> StrategySummary:
    payload = draft.model_dump(mode="python")
    field_provenance = payload.pop("field_provenance", {}) or {}
    language = _clean_optional_text(payload.pop("language", None))
    date_range_raw_text = _clean_optional_text(payload.pop("date_range_raw_text", None))
    date_range_intent = _clean_date_range_intent_payload(
        payload.pop("date_range_intent", None)
    )
    evidence_spans = _clean_evidence_spans(payload.pop("evidence_spans", {}) or {})
    asset_universe_operation = normalized_asset_universe_operation(
        payload.pop("asset_universe_operation", None)
    )
    if asset_universe_operation is not None:
        payload.setdefault("extra_parameters", {})["asset_universe_operation"] = (
            asset_universe_operation
        )
    if not date_range_intent:
        date_range_intent = _date_range_intent_from_bounded_evidence(draft)
    initial_capital = payload.pop("initial_capital", None)
    total_capital = payload.pop("total_capital", None)
    recurring_contribution = payload.pop("recurring_contribution", None)
    initial_capital = _grounded_initial_capital(
        initial_capital,
        field_provenance=field_provenance,
    )
    total_capital = _grounded_total_capital(
        total_capital,
        field_provenance=field_provenance,
    )
    recurring_contribution = _grounded_recurring_contribution(
        recurring_contribution,
        field_provenance=field_provenance,
    )
    indicator_parameters = {
        key: value
        for key, value in {
            "indicator": payload.pop("indicator", None),
            "indicator_period": payload.pop("indicator_period", None),
            "entry_threshold": payload.pop("entry_threshold", None),
            "exit_threshold": payload.pop("exit_threshold", None),
        }.items()
        if value is not None
    }
    if indicator_parameters:
        extra_parameters = payload.setdefault("extra_parameters", {})
        if indicator_parameters.get("indicator") is not None:
            extra_parameters["indicator"] = indicator_parameters["indicator"]
        merged_indicator_parameters = dict(
            extra_parameters.get("indicator_parameters") or {}
        )
        merged_indicator_parameters.update(indicator_parameters)
        extra_parameters["indicator_parameters"] = merged_indicator_parameters
    capital_parameters = {
        "initial_capital": initial_capital,
        "total_capital": total_capital,
        "recurring_contribution": recurring_contribution,
    }
    if any(value is not None for value in capital_parameters.values()):
        extra_parameters = payload.setdefault("extra_parameters", {})
        for key, value in capital_parameters.items():
            if value is not None:
                extra_parameters[key] = value
        if payload.get("capital_amount") is None and recurring_contribution is not None:
            payload["capital_amount"] = recurring_contribution
        if payload.get("capital_amount") is None:
            starting_capital = _non_dca_starting_capital_from_total_fields(
                payload=payload,
                initial_capital=initial_capital,
                total_capital=total_capital,
            )
            if starting_capital is not None:
                payload["capital_amount"] = starting_capital
                field_provenance["capital_amount"] = "starting_capital"
    if field_provenance:
        payload.setdefault("extra_parameters", {})["field_provenance"] = dict(
            field_provenance
        )
    if language:
        payload.setdefault("extra_parameters", {})["language"] = language
    if date_range_raw_text:
        payload.setdefault("extra_parameters", {})["date_range_raw_text"] = (
            date_range_raw_text
        )
    if date_range_intent:
        payload.setdefault("extra_parameters", {})["date_range_intent"] = (
            date_range_intent
        )
    if evidence_spans:
        payload.setdefault("extra_parameters", {})["evidence_spans"] = evidence_spans
    _normalize_llm_domain_slots(payload)
    field_provenance = _evidence_backed_field_provenance(
        payload=payload,
        field_provenance=field_provenance,
        evidence_spans=evidence_spans,
    )
    if field_provenance:
        payload.setdefault("extra_parameters", {})["field_provenance"] = dict(
            field_provenance
        )
    payload["date_range"] = normalize_date_range_candidate(
        payload.get("date_range"),
        raw_user_phrasing=payload.get("raw_user_phrasing"),
    )
    if date_range_intent:
        intent_resolution = resolve_date_range_intent(date_range_intent)
        intent_kind = str(date_range_intent.get("kind") or "").strip()
        if intent_resolution is not None and (
            intent_kind != "endpoint_patch"
            or not _has_complete_date_range_payload(payload["date_range"])
        ):
            payload["date_range"] = intent_resolution.payload
    if draft.strategy_type:
        payload.setdefault("extra_parameters", {})["raw_strategy_type"] = (
            draft.strategy_type
        )
    payload["risk_rules"] = [
        rule.model_dump(mode="python") if isinstance(rule, LLMRiskRule) else rule
        for rule in draft.risk_rules
    ]
    return StrategySummary.model_validate(payload)


def _evidence_backed_field_provenance(
    *,
    payload: dict[str, Any],
    field_provenance: dict[str, Any],
    evidence_spans: dict[str, str],
) -> dict[str, Any]:
    updated = dict(field_provenance or {})
    evidence_backed_fields = {
        "cadence": "explicit_user",
        "comparison_baseline": "explicit_user",
        "timeframe": "explicit_user",
    }
    for field_name, source in evidence_backed_fields.items():
        if field_name in updated:
            continue
        if field_name not in evidence_spans:
            continue
        if payload.get(field_name) in (None, "", [], {}):
            continue
        updated[field_name] = source
    return updated


def _normalize_llm_domain_slots(payload: dict[str, Any]) -> None:
    strategy_type = canonical_strategy_type(
        payload.get("strategy_type"),
        cadence=payload.get("cadence"),
    )
    if strategy_type != "dca_accumulation":
        return
    raw_cadence = payload.get("cadence")
    if raw_cadence in (None, "", [], {}):
        return
    cadence = _supported_dca_cadence_value(raw_cadence)
    if cadence is None:
        payload.setdefault("extra_parameters", {})["raw_cadence"] = raw_cadence
        payload["cadence"] = None
        return
    payload["cadence"] = cadence
    extra_parameters = payload.setdefault("extra_parameters", {})
    extra_parameters["recurring_cadence"] = cadence


def _clean_optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_evidence_spans(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, span in value.items():
        normalized_key = str(key or "").strip()
        normalized_span = str(span or "").strip()
        if normalized_key and normalized_span:
            cleaned[normalized_key] = normalized_span
    return cleaned


def _clean_date_range_intent_payload(value: Any) -> dict[str, Any]:
    if value in (None, "", [], {}):
        return {}
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        return dict(dumped) if isinstance(dumped, dict) else {}
    return {}


def _date_range_intent_from_bounded_evidence(
    draft: LLMStrategyDraft,
    *,
    language: str | None = None,
) -> dict[str, Any]:
    evidence_candidates = _bounded_date_evidence_candidates(draft)
    if not evidence_candidates:
        return {}
    language_candidates = _natural_time_language_candidates_from_hints(
        draft.language,
        language,
    )
    for candidate in evidence_candidates:
        for languages in language_candidates:
            intent = resolve_rolling_window_intent_text(
                candidate,
                languages=languages,
            )
            if intent is not None:
                return intent
    return {}


def _non_dca_starting_capital_from_total_fields(
    *,
    payload: dict[str, Any],
    initial_capital: Any,
    total_capital: Any,
) -> Any:
    if canonical_strategy_type(payload.get("strategy_type")) == "dca_accumulation":
        return None
    return initial_capital if initial_capital is not None else total_capital


def _grounded_initial_capital(
    value: Any,
    *,
    field_provenance: dict[str, str],
) -> Any:
    if value is None:
        return None
    if _capital_source(field_provenance, "initial_capital") in _TOTAL_CAPITAL_SOURCES:
        return value
    if _capital_source(field_provenance, "capital_amount") in _TOTAL_CAPITAL_SOURCES:
        return value
    return None


def _grounded_total_capital(
    value: Any,
    *,
    field_provenance: dict[str, str],
) -> Any:
    if value is None:
        return None
    if _capital_source(field_provenance, "total_capital") in _TOTAL_CAPITAL_SOURCES:
        return value
    if _capital_source(field_provenance, "capital_amount") in _TOTAL_CAPITAL_SOURCES:
        return value
    return None


def _grounded_recurring_contribution(
    value: Any,
    *,
    field_provenance: dict[str, str],
) -> Any:
    if value is None:
        return None
    if (
        _capital_source(field_provenance, "recurring_contribution")
        in _RECURRING_CAPITAL_SOURCES
    ):
        return value
    if _capital_source(field_provenance, "capital_amount") in _RECURRING_CAPITAL_SOURCES:
        return value
    return None


def _ground_strategy_in_current_turn(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
) -> None:
    current_message = request.current_user_message.strip()
    if current_message:
        strategy.raw_user_phrasing = current_message
        if not strategy.strategy_thesis:
            strategy.strategy_thesis = current_message
        strategy.date_range = normalize_date_range_candidate(
            strategy.date_range,
            raw_user_phrasing=current_message,
        )


def _merge_prior_strategy(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
    response: LLMInterpretationResponse,
) -> None:
    del strategy, request, response
    return None


def _field_owned_indicator_asset_candidate(
    *,
    strategy: StrategySummary,
    symbol: str,
    request: InterpretationRequest,
) -> bool:
    if _selected_requested_field_base(request) == "asset_universe":
        return False
    if executable_indicator_spec(str(symbol or "")) is None:
        return False
    if not _strategy_uses_rule_or_indicator_context(strategy):
        return False
    return not _strategy_has_explicit_asset_evidence(
        strategy,
        symbol=symbol,
        current_user_message=request.current_user_message,
    )


def _strategy_uses_rule_or_indicator_context(strategy: StrategySummary) -> bool:
    return bool(
        executable_strategy_type(strategy) in {"indicator_threshold", "signal_strategy"}
        or _indicator_key_from_strategy(strategy) is not None
        or strategy.entry_rule
        or strategy.exit_rule
        or strategy.rule_spec
    )


def _strategy_has_explicit_asset_evidence(
    strategy: StrategySummary,
    *,
    symbol: str,
    current_user_message: str | None,
) -> bool:
    target = _compact_asset_evidence_token(symbol)
    if not target:
        return False
    if _message_has_cashtag_for_asset(current_user_message, target=target):
        return True

    field_provenance = strategy.extra_parameters.get("field_provenance")
    if isinstance(field_provenance, dict):
        for field_name, source in field_provenance.items():
            if _field_path_base(field_name) != "asset_universe":
                continue
            if str(source or "").strip() in {
                "asset_field",
                "asset_mention",
                "cashtag",
                "composer_mention",
                "explicit_user",
                "user",
                "user_mention",
            }:
                return True

    evidence_spans = strategy.extra_parameters.get("evidence_spans")
    if isinstance(evidence_spans, dict):
        for field_name, evidence in evidence_spans.items():
            if _field_path_base(field_name) != "asset_universe":
                continue
            evidence_text = str(evidence or "")
            if _message_has_cashtag_for_asset(evidence_text, target=target):
                return True

    for item in strategy.resolution_provenance:
        if _field_path_base(item.field) != "asset_universe":
            continue
        if item.source == "user_mention" and target in {
            _compact_asset_evidence_token(item.raw_text),
            _compact_asset_evidence_token(item.canonical_symbol),
        }:
            return True
    return False


def _message_has_cashtag_for_asset(message: str | None, *, target: str) -> bool:
    for token in str(message or "").split():
        cleaned = "".join(
            character
            for character in token.strip()
            if character.isalnum() or character == "$"
        )
        if cleaned.startswith("$") and _compact_asset_evidence_token(cleaned[1:]) == target:
            return True
    return False


def _compact_asset_evidence_token(value: Any) -> str:
    return "".join(
        character.casefold()
        for character in str(value or "")
        if character.isalnum()
    )


def _ensure_dca_missing_execution_fields(
    *,
    strategy: StrategySummary,
    response: LLMInterpretationResponse,
) -> None:
    missing = list(response.missing_required_fields or [])
    if strategy.capital_amount is None and "capital_amount" not in missing:
        missing.append("capital_amount")
    if strategy.cadence in (None, "", [], {}) and "cadence" not in missing:
        missing.append("cadence")
    response.missing_required_fields = missing


def _remove_unstated_model_defaults(strategy: StrategySummary) -> None:
    field_provenance = strategy.extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        field_provenance = {}
    capital_source = str(field_provenance.get("capital_amount") or "").strip()
    if capital_source in {
        "default",
        "default_assumption",
        "assumed_default",
        "model_default",
    }:
        strategy.capital_amount = None
        if strategy.sizing_mode in {"fixed", "capital_amount"}:
            strategy.sizing_mode = None
        field_provenance.pop("capital_amount", None)
    position_source = str(field_provenance.get("position_size") or "").strip()
    if strategy.position_size == 1.0 and position_source in {
        "",
        "default",
        "default_assumption",
        "assumed_default",
        "model_default",
    }:
        strategy.position_size = None
        if strategy.sizing_mode in {"fixed", "position_size"}:
            strategy.sizing_mode = None
    strategy.risk_rules = [
        rule
        for rule in strategy.risk_rules
        if not _risk_rule_is_unstated_full_position_default(rule)
    ]
    if field_provenance:
        strategy.extra_parameters["field_provenance"] = dict(field_provenance)
    else:
        strategy.extra_parameters.pop("field_provenance", None)


def _risk_rule_is_unstated_full_position_default(rule: Any) -> bool:
    payload = rule.model_dump(mode="python") if hasattr(rule, "model_dump") else rule
    if not isinstance(payload, dict):
        return False
    if payload.get("type") != "max_position_size":
        return False
    raw_value = payload.get("value_pct")
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return False
    return value >= 100.0


def _validate_indicator_rule_support(
    *,
    strategy: StrategySummary,
    response: LLMInterpretationResponse,
) -> None:
    if executable_strategy_type(strategy) != "indicator_threshold":
        return
    if _strategy_has_executable_rule_semantics(strategy):
        response.unsupported_constraints = [
            item
            for item in response.unsupported_constraints
            if item.category != "unsupported_indicator_rule"
        ]


def _remove_stale_indicator_constraints(
    *,
    response: LLMInterpretationResponse,
    strategy: StrategySummary,
    current_message: str,
) -> None:
    del current_message
    if _strategy_has_rule_semantics(strategy):
        return
    response.unsupported_constraints = [
        item
        for item in response.unsupported_constraints
        if item.category != "unsupported_indicator_rule"
    ]


def _apply_executable_indicator_defaults(strategy: StrategySummary) -> None:
    indicator_key = _indicator_key_from_strategy(strategy)
    if indicator_key is None:
        return
    spec = executable_indicator_spec(indicator_key)
    if spec is None:
        return
    parameters = normalize_indicator_parameters(
        spec.key,
        {
            **_indicator_parameters_from_strategy(strategy),
            "indicator": spec.key,
        },
    )
    strategy.extra_parameters = {
        **strategy.extra_parameters,
        "indicator": spec.key,
        "indicator_parameters": parameters,
    }
    strategy.entry_logic = spec.format_threshold_rule(
        "entry",
        threshold=float(parameters["entry_threshold"]),
        period=int(parameters["indicator_period"]),
    )
    strategy.exit_logic = spec.format_threshold_rule(
        "exit",
        threshold=float(parameters["exit_threshold"]),
        period=int(parameters["indicator_period"]),
    )


def _apply_signal_strategy_defaults(strategy: StrategySummary) -> None:
    entry_rule = strategy_rule(strategy, "entry")
    rule_spec = executable_rule_spec_from_strategy(strategy)
    if entry_rule is None and rule_spec is None:
        return
    if strategy.entry_rule is None:
        strategy.entry_rule = entry_rule
    if strategy.exit_rule is None:
        strategy.exit_rule = strategy_rule(
            strategy, "exit"
        ) or opposite_moving_average_crossover_rule(entry_rule)
    strategy.extra_parameters = {
        **strategy.extra_parameters,
        "entry_rule": strategy.entry_rule,
        "exit_rule": strategy.exit_rule,
    }
    entry_text = describe_rule_spec(rule_spec, "entry") if rule_spec else None
    exit_text = describe_rule_spec(rule_spec, "exit") if rule_spec else None
    strategy.entry_logic = (
        entry_text
        or moving_average_crossover_text(strategy.entry_rule)
        or strategy.entry_logic
    )
    strategy.exit_logic = (
        exit_text
        or moving_average_crossover_text(strategy.exit_rule)
        or strategy.exit_logic
    )


def _dca_amount_has_user_provenance(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
) -> bool:
    if strategy.capital_amount is None:
        return False
    field_provenance = strategy.extra_parameters.get("field_provenance")
    if isinstance(field_provenance, dict):
        capital_source = field_provenance.get("capital_amount")
        if capital_source in {
            "user",
            "explicit_user",
            "prior",
            "recurring_contribution",
            "contribution_amount",
            "periodic_contribution",
            "dca_contribution",
        }:
            return True
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    return (
        prior is not None
        and prior.capital_amount is not None
        and strategy.capital_amount == prior.capital_amount
    )


def _dca_cadence_has_user_provenance(
    *,
    strategy: StrategySummary,
    request: InterpretationRequest,
) -> bool:
    cadence = str(strategy.cadence or "").strip().casefold()
    if not cadence:
        return False
    field_provenance = strategy.extra_parameters.get("field_provenance")
    if isinstance(field_provenance, dict):
        cadence_source = field_provenance.get("cadence")
        if cadence_source in {"user", "explicit_user", "prior", "visible_draft"}:
            return True
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return False
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    return (
        prior is not None
        and prior.cadence not in (None, "", [], {})
        and str(prior.cadence).strip().casefold() == cadence
    )


def _strategy_has_indicator_parameters(strategy: StrategySummary) -> bool:
    return bool(_indicator_parameters_from_strategy(strategy))


def _strategy_has_rule_semantics(strategy: StrategySummary) -> bool:
    return bool(
        strategy.entry_logic
        or strategy.exit_logic
        or strategy.entry_rule
        or strategy.exit_rule
        or strategy.rule_spec
        or _indicator_parameters_from_strategy(strategy)
    )


def _strategy_has_executable_rule_semantics(strategy: StrategySummary) -> bool:
    return bool(
        strategy.entry_rule
        or strategy.exit_rule
        or strategy.rule_spec
        or _indicator_parameters_from_strategy(strategy)
    )


def _indicator_parameters_from_strategy(strategy: StrategySummary) -> dict[str, Any]:
    return canonical_indicator_parameters_from_strategy(strategy)


def _indicator_key_from_strategy(strategy: StrategySummary) -> str | None:
    raw_indicator = strategy.extra_parameters.get("indicator")
    if isinstance(raw_indicator, str) and raw_indicator.strip():
        return raw_indicator.strip()
    raw_parameters = strategy.extra_parameters.get("indicator_parameters")
    if isinstance(raw_parameters, dict):
        parameter_indicator = raw_parameters.get("indicator")
        if isinstance(parameter_indicator, str) and parameter_indicator.strip():
            return parameter_indicator.strip()
    return None


def _unsupported_from_llm(item: LLMUnsupportedConstraint) -> UnsupportedConstraint:
    explanation = item.explanation or (
        "That exact indicator rule is not executable yet, but Argus can reframe it "
        "into a supported historical test."
    )
    return UnsupportedConstraint(
        category=item.category,
        raw_value=item.raw_value,
        explanation=explanation,
        simplification_options=[
            SimplificationOption(
                label=_humanize_simplification_label(label), replacement_values={}
            )
            for label in item.simplification_labels
        ],
    )


def _humanize_simplification_label(label: str) -> str:
    normalized = label.strip().lower().replace("-", "_").replace(" ", "_")
    labels = {
        "rsi_preset": "Use the supported RSI rule",
        "supported_rsi_strategy": "Use the supported RSI rule",
        "buy_and_hold": "Compare with buy and hold",
        "dca_accumulation": "Try recurring buys",
    }
    return labels.get(normalized, label.strip())


def _dedupe_resolution_provenance(
    items: list[ResolutionProvenance | dict[str, Any]],
) -> list[ResolutionProvenance]:
    return dedupe_resolution_provenance_items(items)
