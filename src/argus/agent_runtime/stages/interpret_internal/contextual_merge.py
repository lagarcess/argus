"""Strategy contextual-merge helpers: preserve/merge prior strategy context across turns.

Behavior-preserving relocation from stages/interpret.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.artifacts.asset_edits import (
    normalized_asset_universe_operation,
    same_asset_universe,
)
from argus.agent_runtime.artifacts.strategy_edits import (
    ArtifactPatch,
    apply_artifact_patch,
)
from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _clear_incompatible_strategy_rule_state,
    _indicator_key_from_strategy,
    _provenance_field,
    _strategy_looks_like_pending_artifact_edit,
    _strategy_supplies_contextual_rule_edit,
)
from argus.agent_runtime.stages.interpret_internal.date_contract import (
    _date_range_endpoints,
    _strategy_date_evidence_candidates,
)
from argus.agent_runtime.stages.interpret_internal.shared import (
    _field_base,
    _should_preserve_prior_asset_context,
    _strategy_supplies_executable_rule_edit,
)
from argus.agent_runtime.state.models import (
    StrategySummary,
    TaskSnapshot,
)
from argus.agent_runtime.strategy_contract import (
    SUPPORTED_STRATEGY_TYPES,
    canonical_strategy_type,
    executable_strategy_type,
    resolve_date_range_intent,
)
from argus.domain.indicators import executable_indicator_spec
from argus.nlp.natural_time import resolve_date_range_text

CONTEXTUAL_EDIT_TURN_ACTS = {
    "answer_pending_need",
    "approval",
    "refine_current_idea",
}

_PENDING_RULE_FIELD_BASES = {
    "entry_logic",
    "exit_logic",
    "entry_rule",
    "exit_rule",
    "rule_spec",
    "indicator",
    "indicator_period",
    "entry_threshold",
    "exit_threshold",
    "indicator_parameters",
}


def _strategy_with_contextual_merge(
    *,
    strategy: StrategySummary,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
    current_user_message: str | None = None,
    reason_codes: list[str] | None = None,
) -> StrategySummary:
    if snapshot is None:
        return strategy
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return strategy
    if "pending_response_option_selected" in set(reason_codes or []):
        return strategy
    should_merge = (
        semantic_turn_act in CONTEXTUAL_EDIT_TURN_ACTS
        or task_relation == "refine"
        or _strategy_supplies_contextual_rule_edit(prior=prior, strategy=strategy)
        or _strategy_fills_pending_execution_context(
            prior=prior,
            strategy=strategy,
            selected_thread_metadata=selected_thread_metadata,
        )
        or _strategy_looks_like_pending_artifact_edit(
            prior=prior,
            strategy=strategy,
            selected_thread_metadata=selected_thread_metadata,
        )
    )
    if not should_merge:
        return strategy
    incoming_strategy_family = _declared_strategy_family(strategy)
    prior_strategy_family = executable_strategy_type(prior)
    strategy_family_changed = (
        incoming_strategy_family in SUPPORTED_STRATEGY_TYPES
        and prior_strategy_family in SUPPORTED_STRATEGY_TYPES
        and incoming_strategy_family != prior_strategy_family
    )
    preserve_prior_family = _should_preserve_pending_strategy_family(
        prior=prior,
        strategy=strategy,
        incoming_strategy_family=incoming_strategy_family,
        prior_strategy_family=prior_strategy_family,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=semantic_turn_act,
        task_relation=task_relation,
    )
    preserve_prior_asset_context = _should_preserve_prior_asset_context(
        prior=prior,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=semantic_turn_act,
        task_relation=task_relation,
    )
    if _should_preserve_prior_asset_for_pending_rule_answer(
        prior=prior,
        strategy=strategy,
        selected_thread_metadata=selected_thread_metadata,
        task_relation=task_relation,
        current_user_message=current_user_message,
    ):
        preserve_prior_asset_context = True
    if (
        normalized_asset_universe_operation(
            strategy.extra_parameters.get("asset_universe_operation")
        )
        is not None
    ):
        preserve_prior_asset_context = False
    preserve_prior_money_context = _should_preserve_prior_money_context(
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=semantic_turn_act,
    )
    preserve_prior_date_context = _should_preserve_prior_date_context(
        strategy=strategy,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=semantic_turn_act,
        task_relation=task_relation,
        current_user_message=current_user_message,
    )
    asset_field_requested = (
        _field_base(str(selected_thread_metadata.get("requested_field") or ""))
        == "asset_universe"
    )
    preserve_prior_asset_for_field_owned_indicator = bool(
        prior.asset_universe
        and _strategy_asset_universe_is_field_owned_indicator_context(
            strategy,
            current_user_message=current_user_message,
            asset_field_requested=asset_field_requested,
        )
    )
    if preserve_prior_family:
        strategy_family_changed = False
        incoming_strategy_family = prior_strategy_family
    merged = (
        _reset_contextual_strategy_definition(
            prior,
            incoming_strategy_family,
        )
        if strategy_family_changed and incoming_strategy_family is not None
        else prior.model_copy(deep=True)
    )
    incoming = strategy.model_dump(mode="python")
    for key, value in incoming.items():
        if key == "raw_user_phrasing":
            continue
        if key == "strategy_thesis" and not strategy_family_changed:
            continue
        if key == "strategy_type" and preserve_prior_family:
            continue
        if (
            preserve_prior_asset_context
            or preserve_prior_asset_for_field_owned_indicator
        ) and key in {
            "asset_universe",
            "asset_class",
            "resolution_provenance",
        }:
            continue
        if preserve_prior_money_context and key in {
            "capital_amount",
            "initial_capital",
            "total_capital",
            "position_size",
        }:
            continue
        if preserve_prior_date_context and key in {"date_range", "timeframe"}:
            continue
        if value in (None, "", [], {}):
            continue
        if key == "date_range" and isinstance(value, dict):
            value = _contextual_date_range_value(
                base=merged.date_range,
                incoming=value,
                current_user_message=current_user_message,
                selected_thread_metadata=selected_thread_metadata,
            )
        if key == "asset_universe":
            operation = normalized_asset_universe_operation(
                strategy.extra_parameters.get("asset_universe_operation")
            )
            if operation is None and same_asset_universe(value, merged.asset_universe):
                continue
            operation = operation or "replace"
            merged = apply_artifact_patch(
                merged,
                ArtifactPatch(
                    source="llm_patch",
                    asset_universe=value,
                    asset_universe_operation=operation,
                ),
            )
            continue
        if key == "extra_parameters":
            if preserve_prior_family and isinstance(value, dict):
                value = {
                    nested_key: nested_value
                    for nested_key, nested_value in value.items()
                    if nested_key not in {"raw_strategy_type", "template"}
                }
            if preserve_prior_money_context and isinstance(value, dict):
                value = _extra_parameters_without_unrequested_money_context(value)
            if preserve_prior_date_context and isinstance(value, dict):
                value = _extra_parameters_without_unrequested_date_context(value)
            merged.extra_parameters = _merge_contextual_extra_parameters(
                base=merged.extra_parameters,
                incoming=value if isinstance(value, dict) else {},
            )
            continue
        setattr(merged, key, value)
    if strategy_family_changed and incoming_strategy_family is not None:
        merged.strategy_type = incoming_strategy_family
    if strategy.raw_user_phrasing:
        merged.raw_user_phrasing = strategy.raw_user_phrasing
    declared_family = _declared_strategy_family(merged)
    if declared_family in SUPPORTED_STRATEGY_TYPES:
        _clear_incompatible_strategy_rule_state(merged, declared_family)
    return merged


def _should_preserve_prior_money_context(
    *,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
) -> bool:
    if semantic_turn_act != "answer_pending_need":
        return False
    if selected_thread_metadata.get("last_stage_outcome") != "await_user_reply":
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    return requested_field in {"asset_universe", "date_range", "timeframe"}


def _should_preserve_prior_date_context(
    *,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
    current_user_message: str | None,
) -> bool:
    del semantic_turn_act
    if task_relation not in {"continue", "refine", "new_task"}:
        return False
    if selected_thread_metadata.get("last_stage_outcome") != "await_user_reply":
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field not in _PENDING_RULE_FIELD_BASES:
        return False
    return not _strategy_has_current_turn_date_evidence(
        strategy=strategy,
        current_user_message=current_user_message,
    )


def _strategy_has_current_turn_date_evidence(
    *,
    strategy: StrategySummary,
    current_user_message: str | None,
) -> bool:
    for candidate in [
        str(current_user_message or ""),
        *_strategy_date_evidence_candidates(strategy),
    ]:
        if resolve_date_range_text(candidate, languages=("en", "es")) is not None:
            return True
    intent = strategy.extra_parameters.get("date_range_intent")
    return isinstance(intent, dict) and resolve_date_range_intent(intent) is not None


def _should_preserve_prior_asset_for_pending_rule_answer(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    task_relation: str,
    current_user_message: str | None,
) -> bool:
    if not prior.asset_universe:
        return False
    if task_relation not in {"continue", "refine", "new_task"}:
        return False
    if selected_thread_metadata.get("last_stage_outcome") != "await_user_reply":
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field not in _PENDING_RULE_FIELD_BASES:
        return False
    return not _current_turn_has_strong_asset_override(
        strategy=strategy,
        current_user_message=current_user_message,
    )


def _current_turn_has_strong_asset_override(
    *,
    strategy: StrategySummary,
    current_user_message: str | None,
) -> bool:
    for symbol in strategy.asset_universe:
        target = _compact_asset_evidence_token(symbol)
        if not target:
            continue
        if _message_has_cashtag_for_asset(current_user_message, target=target):
            return True
        if _message_has_uppercase_asset_token(current_user_message, target=target):
            return True
        if _strategy_has_strong_asset_evidence(strategy=strategy, target=target):
            return True
    return False


def _strategy_has_strong_asset_evidence(
    *,
    strategy: StrategySummary,
    target: str,
) -> bool:
    evidence_spans = strategy.extra_parameters.get("evidence_spans")
    if isinstance(evidence_spans, dict):
        for field_name, evidence in evidence_spans.items():
            if _field_base(str(field_name)) != "asset_universe":
                continue
            evidence_text = str(evidence or "")
            if _message_has_cashtag_for_asset(evidence_text, target=target):
                return True
            if _message_has_uppercase_asset_token(evidence_text, target=target):
                return True
    for item in strategy.resolution_provenance:
        if _field_base(_provenance_field(item)) != "asset_universe":
            continue
        source = getattr(item, "source", None)
        raw_text = getattr(item, "raw_text", "")
        canonical_symbol = getattr(item, "canonical_symbol", "")
        if str(source or "") == "user_mention" and target in {
            _compact_asset_evidence_token(raw_text),
            _compact_asset_evidence_token(canonical_symbol),
        }:
            return True
    return False


def _extra_parameters_without_unrequested_money_context(
    extra_parameters: dict[str, Any],
) -> dict[str, Any]:
    money_context_keys = {
        "initial_capital",
        "starting_capital",
        "starting_principal",
        "initial_lump_sum",
        "initial_lump",
        "lump_sum",
        "total_capital",
        "total_budget",
        "max_budget",
        "investment_budget",
        "cap",
        "contribution_cap",
        "capital_cap",
        "investment_cap",
        "recurring_contribution",
        "contribution_amount",
        "periodic_contribution",
        "dca_contribution",
    }
    money_provenance_keys = {
        "capital_amount",
        "initial_capital",
        "total_capital",
        "position_size",
        "recurring_contribution",
    }
    cleaned: dict[str, Any] = {}
    for key, value in extra_parameters.items():
        if key in money_context_keys:
            continue
        if key == "field_provenance" and isinstance(value, dict):
            provenance = {
                provenance_key: provenance_value
                for provenance_key, provenance_value in value.items()
                if provenance_key not in money_provenance_keys
            }
            if provenance:
                cleaned[key] = provenance
            continue
        cleaned[key] = value
    return cleaned


def _extra_parameters_without_unrequested_date_context(
    extra_parameters: dict[str, Any],
) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in extra_parameters.items():
        if key in {"date_range_raw_text", "date_range_intent"}:
            continue
        if key == "evidence_spans" and isinstance(value, dict):
            evidence = {
                evidence_key: evidence_value
                for evidence_key, evidence_value in value.items()
                if _field_base(str(evidence_key)) != "date_range"
            }
            if evidence:
                cleaned[key] = evidence
            continue
        cleaned[key] = value
    return cleaned


def _contextual_date_range_value(
    *,
    base: Any,
    incoming: dict[str, Any],
    current_user_message: str | None,
    selected_thread_metadata: dict[str, Any],
) -> dict[str, Any]:
    if _has_complete_date_range(incoming):
        return incoming
    del current_user_message
    return _merged_contextual_date_range(
        base=base,
        incoming=incoming,
    )


def _has_complete_date_range(value: Any) -> bool:
    endpoints = _date_range_endpoints(value)
    return endpoints is not None and all(endpoints)


def _merged_contextual_date_range(
    *,
    base: Any,
    incoming: dict[str, Any],
) -> dict[str, Any]:
    incoming_endpoints = {
        "start": incoming.get("start") or incoming.get("from"),
        "end": incoming.get("end") or incoming.get("to"),
    }
    incoming_endpoints = {
        key: value
        for key, value in incoming_endpoints.items()
        if value not in (None, "", [], {})
    }
    if set(incoming_endpoints) == {"start", "end"}:
        return incoming
    if not isinstance(base, dict):
        return incoming
    merged = {
        "start": base.get("start") or base.get("from"),
        "end": base.get("end") or base.get("to"),
    }
    merged.update(incoming_endpoints)
    return {key: value for key, value in merged.items() if value not in (None, "")}


def _should_preserve_pending_strategy_family(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
    incoming_strategy_family: str | None,
    prior_strategy_family: str,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
) -> bool:
    # The LLM may label a pending-field answer as "refine"; the narrower
    # semantic turn act and selected artifact context decide whether family
    # changes are allowed.
    del task_relation
    if semantic_turn_act not in {"answer_pending_need", "new_idea"}:
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field in {"refinement", "entry_logic", "exit_logic"}:
        return False
    if not _strategy_fills_pending_execution_context(
        prior=prior,
        strategy=strategy,
        selected_thread_metadata=selected_thread_metadata,
    ):
        return False
    if (
        incoming_strategy_family not in SUPPORTED_STRATEGY_TYPES
        or prior_strategy_family not in SUPPORTED_STRATEGY_TYPES
        or incoming_strategy_family == prior_strategy_family
    ):
        return False
    if incoming_strategy_family not in {"buy_and_hold", "dca_accumulation"}:
        return False
    if not _strategy_supplies_executable_rule_edit(prior):
        return False
    if _strategy_supplies_executable_rule_edit(strategy):
        return False
    return True


def _strategy_asset_universe_is_field_owned_indicator_context(
    strategy: StrategySummary,
    *,
    current_user_message: str | None,
    asset_field_requested: bool,
) -> bool:
    if asset_field_requested or not strategy.asset_universe:
        return False
    if not _strategy_uses_rule_or_indicator_context(strategy):
        return False
    return all(
        _is_field_owned_indicator_asset_candidate(
            symbol,
            strategy=strategy,
            current_user_message=current_user_message,
            asset_field_requested=asset_field_requested,
        )
        for symbol in strategy.asset_universe
    )


def _is_field_owned_indicator_asset_candidate(
    symbol: str,
    *,
    strategy: StrategySummary,
    current_user_message: str | None,
    asset_field_requested: bool,
) -> bool:
    if asset_field_requested:
        return False
    if executable_indicator_spec(str(symbol or "")) is None:
        return False
    if not _strategy_uses_rule_or_indicator_context(strategy):
        return False
    return not _strategy_has_explicit_asset_evidence(
        strategy,
        symbol=str(symbol or ""),
        current_user_message=current_user_message,
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
            if _field_base(str(field_name)) != "asset_universe":
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
            if _field_base(str(field_name)) != "asset_universe":
                continue
            evidence_text = str(evidence or "")
            if _message_has_cashtag_for_asset(evidence_text, target=target):
                return True

    for item in strategy.resolution_provenance:
        if _field_base(_provenance_field(item)) != "asset_universe":
            continue
        source = getattr(item, "source", None)
        raw_text = getattr(item, "raw_text", "")
        canonical_symbol = getattr(item, "canonical_symbol", "")
        if str(source or "") == "user_mention" and target in {
            _compact_asset_evidence_token(raw_text),
            _compact_asset_evidence_token(canonical_symbol),
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
        if (
            cleaned.startswith("$")
            and _compact_asset_evidence_token(cleaned[1:]) == target
        ):
            return True
    return False


def _message_has_uppercase_asset_token(message: str | None, *, target: str) -> bool:
    for token in str(message or "").split():
        cleaned = "".join(
            character
            for character in token.strip()
            if character.isalnum() or character in {"/", "-"}
        )
        if not cleaned or cleaned != cleaned.upper():
            continue
        if not any(character.isalpha() and character.isupper() for character in cleaned):
            continue
        if _compact_asset_evidence_token(cleaned) == target:
            return True
    return False


def _compact_asset_evidence_token(value: Any) -> str:
    return "".join(
        character.casefold()
        for character in str(value or "")
        if character.isalnum()
    )


def _strategy_fills_pending_execution_context(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
) -> bool:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    context_fields = {
        "asset_universe",
        "date_range",
        "timeframe",
        "capital_amount",
        "initial_capital",
        "position_size",
        "assumption",
    }
    if requested_field in context_fields:
        return _strategy_supplies_execution_context(strategy)
    return (
        selected_thread_metadata.get("last_stage_outcome") == "await_user_reply"
        and (
            (not prior.asset_universe and bool(strategy.asset_universe))
            or (prior.date_range in (None, "") and bool(strategy.date_range))
            or (prior.timeframe in (None, "") and bool(strategy.timeframe))
            or (prior.capital_amount is None and strategy.capital_amount is not None)
            or (prior.position_size is None and strategy.position_size is not None)
        )
    )


def _strategy_supplies_execution_context(strategy: StrategySummary) -> bool:
    return bool(
        strategy.asset_universe
        or strategy.date_range
        or strategy.timeframe
        or strategy.capital_amount is not None
        or strategy.position_size is not None
    )


def _merge_contextual_extra_parameters(
    *,
    base: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in incoming.items():
        if key == "asset_universe_operation":
            continue
        if value in (None, "", [], {}):
            continue
        if (
            key == "indicator_parameters"
            and isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            nested = dict(merged[key])
            for nested_key, nested_value in value.items():
                if nested_value in (None, "", [], {}):
                    continue
                nested[nested_key] = nested_value
            merged[key] = nested
            continue
        if (
            key == "field_provenance"
            and isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            nested = dict(merged[key])
            for nested_key, nested_value in value.items():
                if nested_value in (None, "", [], {}):
                    continue
                nested[nested_key] = nested_value
            merged[key] = nested
            continue
        if (
            key == "date_range_intent"
            and isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            if _date_range_intent_replaces_prior_intent(
                prior=merged.get(key),
                incoming=value,
            ):
                merged = _without_stale_date_evidence(merged)
            base_intent = dict(merged[key])
            if (
                str(value.get("kind") or "").strip() == "endpoint_patch"
                and str(base_intent.get("kind") or "").strip() == "rolling_window"
            ):
                nested = dict(value)
                nested["base_intent"] = base_intent
                merged[key] = nested
                continue
        merged[key] = value
    return merged


def _date_range_intent_replaces_prior_intent(
    *,
    prior: Any,
    incoming: dict[str, Any],
) -> bool:
    if not isinstance(prior, dict):
        return False
    incoming_resolution = resolve_date_range_intent(incoming)
    prior_resolution = resolve_date_range_intent(prior)
    if incoming_resolution is None:
        return False
    if prior_resolution is None:
        return True
    return _date_range_endpoints(incoming_resolution.payload) != _date_range_endpoints(
        prior_resolution.payload
    )


def _without_stale_date_evidence(extra_parameters: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(extra_parameters)
    cleaned.pop("date_range_raw_text", None)
    evidence_spans = cleaned.get("evidence_spans")
    if isinstance(evidence_spans, dict):
        evidence = {
            key: value
            for key, value in evidence_spans.items()
            if _field_base(str(key)) != "date_range"
        }
        if evidence:
            cleaned["evidence_spans"] = evidence
        else:
            cleaned.pop("evidence_spans", None)
    return cleaned


def _declared_strategy_family(strategy: StrategySummary) -> str | None:
    """Return the family the LLM explicitly declared, ignoring derived rule state."""

    raw_candidates: list[Any] = [strategy.strategy_type]
    extra_parameters = dict(strategy.extra_parameters or {})
    raw_candidates.extend(
        [
            extra_parameters.get("raw_strategy_type"),
            extra_parameters.get("template"),
        ]
    )
    for raw_candidate in raw_candidates:
        candidate = canonical_strategy_type(raw_candidate)
        if candidate in SUPPORTED_STRATEGY_TYPES:
            return candidate
    if _indicator_key_from_strategy(strategy) is not None:
        return "indicator_threshold"
    return None


def _reset_contextual_strategy_definition(
    prior: StrategySummary,
    incoming_strategy_family: str,
) -> StrategySummary:
    """Preserve context fields while clearing incompatible strategy-rule state."""

    updated = prior.model_copy(deep=True)
    updated.strategy_type = incoming_strategy_family
    updated.strategy_thesis = None
    _clear_incompatible_strategy_rule_state(updated, incoming_strategy_family)
    return updated
