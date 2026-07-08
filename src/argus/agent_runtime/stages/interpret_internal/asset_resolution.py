"""Asset resolution, canonicalization, requested-asset handling, artifact-target validation, and indicator-simplification helpers.

Behavior-preserving relocation from stages/interpret.py (issue #131)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.asset_text_grounding import (
    grounded_asset_mention_has_name_support,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy as canonical_indicator_parameters_from_strategy,
)
from argus.agent_runtime.rule_specs import (
    moving_average_crossover_text,
    opposite_moving_average_crossover_rule,
    strategy_rule,
)
from argus.agent_runtime.stages.artifact_context import (
    RESULT_EXPLANATION_TARGET_INFERRED,
    RESULT_FOLLOWUP_TARGET_INFERRED,
)
from argus.agent_runtime.stages.interpret_internal import latest_result_answer as lra
from argus.agent_runtime.stages.interpret_internal.draft_only_indicator_evidence import (
    explicit_draft_only_indicator_evidence,
    strategy_type_is_user_selected,
)
from argus.agent_runtime.stages.interpret_internal.shared import (
    _field_base,
    _should_preserve_prior_asset_context,
    _strategy_supplies_executable_rule_edit,
)
from argus.agent_runtime.stages.interpret_types import (
    ArtifactTarget,
    InterpretDecision,
    SemanticTurnAct,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import (
    AmbiguousField,
    IntentName,
    ResolutionProvenance,
    ResolutionSource,
    StrategySummary,
    TaskSnapshot,
    UnsupportedConstraint,
    dedupe_resolution_provenance_items,
)
from argus.agent_runtime.strategy_contract import (
    SUPPORTED_STRATEGY_TYPES,
    executable_strategy_type,
)
from argus.agent_runtime.strategy_requirements import (
    missing_required_fields_for_strategy,
    strategy_has_executable_signal_rule,
)
from argus.agent_runtime.strategy_requirements import (
    valid_rule_spec_from_strategy as _valid_rule_spec_from_strategy,
)
from argus.domain.indicators import (
    IndicatorExecutionSpec,
    draft_only_indicator_from_text,
    executable_indicator_spec,
    normalize_indicator_parameters,
)

STRATEGY_TURN_ACTS: set[SemanticTurnAct] = {
    "new_idea",
    "answer_pending_need",
    "refine_current_idea",
    "approval",
}


_USER_GROUNDED_CAPITAL_SOURCES = frozenset(
    {
        "explicit_user",
        "prior",
        "recurring_contribution",
        "contribution_amount",
        "periodic_contribution",
        "dca_contribution",
    }
)


_USER_GROUNDED_CADENCE_SOURCES = frozenset(
    {
        "explicit_user",
        "prior",
        "visible_draft",
    }
)


@dataclass(frozen=True)
class _RequestedAssetCandidate:
    text: str
    source: ResolutionSource
    from_user_answer: bool = False


def _validated_artifact_target(
    *,
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
) -> tuple[ArtifactTarget | None, list[str]]:
    proposed = interpretation.artifact_target
    reason_codes: list[str] = []
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field == "refinement" and snapshot is not None:
        if snapshot.pending_strategy_summary is not None:
            if lra.overrides_refinement(interpretation, snapshot, proposed, reason_codes):
                return "latest_result", reason_codes
            if proposed != "pending_refinement":
                reason_codes.append("pending_refinement_overrode_latest_result")
            return "pending_refinement", reason_codes
    if proposed == "latest_result":
        if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
            return "latest_result", reason_codes
        reason_codes.append("invalid_latest_result_target_cleared")
        return "none", reason_codes
    if proposed == "active_confirmation":
        if snapshot is not None and snapshot.active_confirmation_reference is not None:
            return "active_confirmation", reason_codes
        reason_codes.append("invalid_active_confirmation_target_cleared")
        return "none", reason_codes
    if proposed in {"none", "pending_refinement"}:
        return proposed, reason_codes
    if (
        interpretation.semantic_turn_act == "result_followup"
        and snapshot is not None
        and snapshot.latest_backtest_result_reference is not None
    ):
        reason_codes.append(RESULT_FOLLOWUP_TARGET_INFERRED)
        return "latest_result", reason_codes
    if (
        interpretation.intent == "results_explanation"
        and snapshot is not None
        and snapshot.latest_backtest_result_reference is not None
    ):
        reason_codes.append(RESULT_EXPLANATION_TARGET_INFERRED)
        return "latest_result", reason_codes
    return proposed, reason_codes


def _pending_refinement_misroute_result_if_applicable(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> StageResult | None:
    if decision.artifact_target != "pending_refinement":
        return None
    if decision.semantic_turn_act != "result_followup":
        return None
    if _candidate_strategy_has_backtest_shape(decision.candidate_strategy_draft):
        return None
    strategy = (
        snapshot.pending_strategy_summary.model_copy(deep=True)
        if snapshot is not None and snapshot.pending_strategy_summary is not None
        else decision.candidate_strategy_draft
    )
    refined = decision.model_copy(
        update={
            "intent": "strategy_drafting",
            "task_relation": "refine",
            "requires_clarification": True,
            "candidate_strategy_draft": strategy,
            "missing_required_fields": ["refinement"],
            "semantic_turn_act": "answer_pending_need",
            "artifact_target": "pending_refinement",
            "reason_codes": [
                *decision.reason_codes,
                "pending_refinement_result_followup_suppressed",
            ],
        }
    )
    return StageResult(
        outcome="needs_clarification",
        decision=refined,
        stage_patch={
            "requested_field": "refinement",
            "missing_required_fields": ["refinement"],
            "response_intent": {
                "kind": "clarification",
                "semantic_needs": ["rule_definition"],
                "requested_fields": ["refinement"],
                "facts": {"strategy": strategy.model_dump(mode="python")},
                "options": [],
            },
        },
    )


def _strategy_with_hidden_context_guard(
    *,
    strategy: StrategySummary,
    interpretation: StructuredInterpretation,
    snapshot: TaskSnapshot | None,
    artifact_target: ArtifactTarget | None,
    current_user_message: str,
) -> tuple[StrategySummary, list[str], bool]:
    if artifact_target != "none":
        return strategy, [], False
    if interpretation.semantic_turn_act != "new_idea":
        return strategy, [], False
    if interpretation.task_relation != "new_task":
        return strategy, [], False
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return strategy, [], False
    prior = snapshot.pending_strategy_summary
    if not prior.asset_universe or strategy.asset_universe != prior.asset_universe:
        return strategy, [], False
    if _strategy_has_fresh_execution_detail(strategy=strategy, prior=prior):
        return strategy, [], False
    if _message_explicitly_mentions_symbol(
        current_user_message,
        symbols=strategy.asset_universe,
    ):
        return strategy, [], False
    updated = strategy.model_copy(deep=True)
    updated.asset_universe = []
    updated.asset_class = None
    updated.resolution_provenance = []
    return updated, ["hidden_artifact_asset_context_cleared"], True


def _strategy_has_fresh_execution_detail(
    *,
    strategy: StrategySummary,
    prior: StrategySummary,
) -> bool:
    for field_name in (
        "date_range",
        "timeframe",
        "cadence",
        "entry_logic",
        "exit_logic",
        "entry_rule",
        "exit_rule",
        "rule_spec",
        "capital_amount",
        "position_size",
        "comparison_baseline",
    ):
        value = getattr(strategy, field_name)
        if value in (None, "", [], {}):
            continue
        if value != getattr(prior, field_name):
            return True
    return False


def _message_explicitly_mentions_symbol(
    message: str,
    *,
    symbols: list[str],
) -> bool:
    punctuation = ".,;:!?()[]{}<>\"'`"
    token_map = str.maketrans({char: " " for char in punctuation})
    tokens = set(message.translate(token_map).split())
    cashtag_tokens = {
        token.lstrip("$").casefold()
        for token in tokens
        if token.startswith("$")
    }
    return any(
        symbol in tokens
        or f"${symbol}" in tokens
        or symbol.casefold() in cashtag_tokens
        for symbol in symbols
    )


def _strategy_with_pending_resolution_affirmation(
    *,
    strategy: StrategySummary,
    explicit_strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    current_user_message: str,
    semantic_turn_act: str | None,
) -> tuple[StrategySummary, bool]:
    if semantic_turn_act != "answer_pending_need":
        return strategy, False
    pending_resolution = selected_thread_metadata.get("pending_resolution")
    if not isinstance(pending_resolution, dict):
        return strategy, False
    field = _field_base(str(pending_resolution.get("field") or ""))
    if field != "asset_universe":
        return strategy, False
    if explicit_strategy.asset_universe:
        return strategy, False
    del current_user_message
    candidate = pending_resolution.get(
        "candidate_normalized_value"
    ) or pending_resolution.get("canonical_symbol")
    if not isinstance(candidate, str) or not candidate.strip():
        return strategy, False
    updated = strategy.model_copy(deep=True)
    updated.asset_universe = [candidate.strip().upper()]
    asset_class = pending_resolution.get("asset_class")
    if isinstance(asset_class, str) and asset_class.strip():
        updated.asset_class = asset_class.strip()
    updated.resolution_provenance = [
        item
        for item in updated.resolution_provenance
        if not _is_ambiguous_asset_resolution(item)
    ]
    return updated, True


def _without_stale_requested_asset_rejection_constraints(
    constraints: list[UnsupportedConstraint],
    *,
    strategy: StrategySummary,
) -> list[UnsupportedConstraint]:
    if not strategy.asset_universe:
        return list(constraints)
    stale_rejection_categories = {"action", "navigation_or_tool"}
    return [
        constraint
        for constraint in constraints
        if constraint.category not in stale_rejection_categories
    ]


def _unresolved_requested_asset_resolution(
    query: str,
    *,
    field: str,
    source: ResolutionSource,
) -> AssetResolution:
    return AssetResolution(
        status="unsupported",
        raw_text=query,
        asset=None,
        candidates=(),
        provenance=ResolutionProvenance(
            field=field,
            raw_text=query,
            source=source,
            candidate_kind="asset",
            resolution_status="unsupported",
            validated_by="provider_catalog",
            confidence="low",
        ),
    )


def _strategy_canonical_asset_symbols(strategy: StrategySummary | None) -> set[str]:
    if strategy is None:
        return set()
    return {
        symbol.strip().upper()
        for symbol in strategy.asset_universe
        if isinstance(symbol, str) and symbol.strip()
    }


def _provenance_field(item: ResolutionProvenance | dict[str, Any]) -> str:
    if isinstance(item, ResolutionProvenance):
        return item.field
    field = item.get("field")
    return field if isinstance(field, str) else ""


def _requested_asset_answer_candidates(
    *,
    explicit_strategy: StrategySummary,
    current_user_message: str,
) -> list[_RequestedAssetCandidate]:
    candidates: list[_RequestedAssetCandidate] = []
    for symbol in explicit_strategy.asset_universe:
        candidate = str(symbol or "").strip()
        if candidate:
            candidates.append(
                _RequestedAssetCandidate(text=candidate, source="llm_extraction")
            )
    answer = current_user_message.strip()
    if answer:
        candidates.append(
            _RequestedAssetCandidate(
                text=answer,
                source="user_mention",
                from_user_answer=True,
            )
        )
    deduped: list[_RequestedAssetCandidate] = []
    seen: dict[str, int] = {}
    for candidate in candidates:
        key = candidate.text.casefold()
        existing_index = seen.get(key)
        if existing_index is not None:
            existing = deduped[existing_index]
            if candidate.from_user_answer and not existing.from_user_answer:
                deduped[existing_index] = candidate
            continue
        seen[key] = len(deduped)
        deduped.append(candidate)
    return deduped


def _strategy_with_supported_indicator_simplification(
    *,
    strategy: StrategySummary,
    snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
) -> tuple[StrategySummary, bool]:
    if semantic_turn_act == "approval":
        return strategy, False
    indicator_key = _indicator_key_from_strategy(strategy)
    if indicator_key is None:
        return strategy, False

    prior = _active_strategy_from_snapshot(snapshot)
    if prior is None and not _strategy_has_content(strategy):
        return strategy, False
    base = (
        prior.model_copy(deep=True)
        if prior is not None
        else strategy.model_copy(deep=True)
    )
    spec = executable_indicator_spec(indicator_key)
    if spec is None or not _indicator_supports_default_threshold_rule(spec):
        return strategy, False

    preserve_prior_asset_context = (
        prior is not None
        and _should_preserve_prior_asset_context(
            prior=prior,
            selected_thread_metadata=selected_thread_metadata,
            semantic_turn_act=semantic_turn_act,
            task_relation=task_relation,
        )
    )
    merge_fields = [
        "asset_universe",
        "asset_class",
        "date_range",
        "timeframe",
        "capital_amount",
        "position_size",
        "comparison_baseline",
        "entry_logic",
        "exit_logic",
        "extra_parameters",
    ]
    if preserve_prior_asset_context:
        merge_fields = [
            field
            for field in merge_fields
            if field not in {"asset_universe", "asset_class"}
        ]
    updated = _merge_non_empty_strategy_fields(
        base=base,
        incoming=strategy,
        field_names=tuple(merge_fields),
    )
    prior_strategy_type = executable_strategy_type(base)
    incoming_indicator_parameters = _indicator_parameters_from_strategy(strategy)
    parameters = normalize_indicator_parameters(
        spec.key,
        {
            **_indicator_parameters_from_strategy(updated),
            **incoming_indicator_parameters,
            "indicator": spec.key,
        },
    )
    updated.raw_user_phrasing = strategy.raw_user_phrasing or updated.raw_user_phrasing
    updated.strategy_type = "indicator_threshold"
    updated.entry_rule = None
    updated.exit_rule = None
    updated.strategy_thesis = _indicator_simplification_thesis(
        strategy=updated,
        spec=spec,
    )
    rewrite_threshold_logic = (
        prior_strategy_type != "indicator_threshold" or bool(incoming_indicator_parameters)
    )
    if rewrite_threshold_logic or not updated.entry_logic:
        updated.entry_logic = spec.format_threshold_rule(
            "entry",
            threshold=float(parameters["entry_threshold"]),
            period=int(parameters["indicator_period"]),
        )
    if rewrite_threshold_logic or not updated.exit_logic:
        updated.exit_logic = spec.format_threshold_rule(
            "exit",
            threshold=float(parameters["exit_threshold"]),
            period=int(parameters["indicator_period"]),
        )
    updated.extra_parameters = {
        **{
            key: value
            for key, value in updated.extra_parameters.items()
            if key not in {"entry_rule", "exit_rule"}
        },
        "indicator": spec.key,
        "indicator_parameters": parameters,
        "simplified_from_strategy_type": (
            prior.strategy_type if prior is not None else strategy.strategy_type
        ),
    }
    return updated, True


def _indicator_key_from_strategy(strategy: StrategySummary) -> str | None:
    indicator_parameters = canonical_indicator_parameters_from_strategy(strategy)
    parameter_indicator = indicator_parameters.get("indicator")
    if isinstance(parameter_indicator, str) and parameter_indicator.strip():
        return parameter_indicator.strip()
    raw_indicator = strategy.extra_parameters.get("indicator")
    if isinstance(raw_indicator, str) and raw_indicator.strip():
        return raw_indicator.strip()
    raw_parameters = strategy.extra_parameters.get("indicator_parameters")
    if isinstance(raw_parameters, dict):
        parameter_indicator = raw_parameters.get("indicator")
        if isinstance(parameter_indicator, str) and parameter_indicator.strip():
            return parameter_indicator.strip()
    return None


def _active_strategy_from_snapshot(snapshot: TaskSnapshot | None) -> StrategySummary | None:
    if snapshot is None:
        return None
    return snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary


def _strategy_has_content(strategy: StrategySummary) -> bool:
    return any(
        value not in (None, "", [], {})
        for value in strategy.model_dump(mode="python").values()
    )


def _indicator_supports_default_threshold_rule(
    spec: IndicatorExecutionSpec,
) -> bool:
    return spec.default_entry_threshold != spec.default_exit_threshold and any(
        parameter.key == "entry_threshold" for parameter in spec.parameter_schema
    )


def _indicator_parameters_from_strategy(strategy: StrategySummary) -> dict[str, Any]:
    return canonical_indicator_parameters_from_strategy(strategy)


def _merge_non_empty_strategy_fields(
    *,
    base: StrategySummary,
    incoming: StrategySummary,
    field_names: tuple[str, ...],
) -> StrategySummary:
    updated = base.model_copy(deep=True)
    incoming_payload = incoming.model_dump(mode="python")
    for field_name in field_names:
        value = incoming_payload.get(field_name)
        if value in (None, "", [], {}):
            continue
        setattr(updated, field_name, value)
    return updated


def _indicator_simplification_thesis(
    *,
    strategy: StrategySummary,
    spec: IndicatorExecutionSpec,
) -> str:
    assets = ", ".join(strategy.asset_universe)
    if assets:
        return f"Test {assets} with a supported {spec.label} threshold rule."
    return f"Test the current idea with a supported {spec.label} threshold rule."


def _is_ambiguous_asset_resolution(item: ResolutionProvenance | dict[str, Any]) -> bool:
    if not isinstance(item, ResolutionProvenance):
        try:
            item = ResolutionProvenance.model_validate(item)
        except (TypeError, ValueError):
            return False
    return (
        item.source == "llm_extraction"
        and item.resolution_status == "ambiguous"
        and _field_base(item.field) == "asset_universe"
    )


def _supported_timeframes(contract: Any) -> tuple[str, ...]:
    parameter = contract.get_optional_parameter("timeframe")
    if parameter is None or parameter.allowed_range is None:
        return ()
    return tuple(str(value) for value in parameter.allowed_range.allowed_values)


def _optional_parameter_stage_patch(
    *,
    decision: InterpretDecision,
    values: dict[str, Any],
) -> dict[str, Any]:
    if not values:
        return {}
    optional_parameter_status = dict(decision.to_patch()["optional_parameter_status"])
    optional_parameter_status.update(values)
    return {"optional_parameter_status": optional_parameter_status}


def _clear_incompatible_strategy_rule_state(
    strategy: StrategySummary,
    strategy_family: str,
) -> None:
    """Keep one declared strategy family from carrying another family's rules."""

    if strategy_family in {"buy_and_hold", "dca_accumulation"}:
        strategy.entry_logic = None
        strategy.exit_logic = None
    if strategy_family != "signal_strategy":
        strategy.entry_rule = None
        strategy.exit_rule = None
        strategy.rule_spec = None
    if strategy_family != "dca_accumulation":
        strategy.cadence = None
    strategy.extra_parameters = _extra_parameters_for_strategy_family(
        strategy.extra_parameters,
        strategy_family,
    )


def _extra_parameters_for_strategy_family(
    extra_parameters: dict[str, Any],
    strategy_family: str,
) -> dict[str, Any]:
    incompatible_keys = {"entry_rule", "exit_rule", "rule_spec"}
    if strategy_family != "indicator_threshold":
        incompatible_keys.update({"indicator", "indicator_parameters"})
    if strategy_family != "dca_accumulation":
        incompatible_keys.update(
            {
                "cadence",
                "recurring_contribution",
                "contribution_amount",
                "periodic_contribution",
                "dca_contribution",
            }
        )
    return {
        key: value
        for key, value in extra_parameters.items()
        if key not in incompatible_keys
    }


def _strategy_looks_like_pending_artifact_edit(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
) -> bool:
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if not requested_field:
        return False
    if requested_field == "date_range":
        return bool(strategy.date_range)
    if requested_field == "asset_universe":
        return bool(strategy.asset_universe)
    if requested_field in {"entry_logic", "exit_logic"}:
        return _strategy_supplies_executable_rule_edit(strategy)
    if requested_field == "refinement":
        return _strategy_has_execution_anchor(strategy) and bool(
            prior.asset_universe or prior.date_range
        )
    return False


def _strategy_supplies_contextual_rule_edit(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
) -> bool:
    if not _strategy_supplies_executable_rule_edit(strategy):
        return False
    return bool(
        prior.asset_universe
        or prior.date_range
        or prior.asset_class
        or prior.capital_amount is not None
        or prior.position_size is not None
    )


def _grounded_symbols_have_name_support(
    *,
    symbols: list[str],
    mentions: list[Any],
) -> bool:
    symbol_set = set(symbols)
    if not symbol_set:
        return False
    return any(
        symbol in symbol_set and grounded_asset_mention_has_name_support(mention)
        for mention in mentions
        if (
            symbol := _normalized_symbol(
                getattr(mention.asset, "canonical_symbol", None)
            )
        )
    )


def _without_field_provenance_keys(
    extra_parameters: dict[str, Any],
    field_names: set[str],
) -> dict[str, Any]:
    if not extra_parameters:
        return {}
    updated = dict(extra_parameters)
    field_provenance = updated.get("field_provenance")
    if isinstance(field_provenance, dict):
        remaining = {
            key: value
            for key, value in field_provenance.items()
            if key not in field_names
        }
        if remaining:
            updated["field_provenance"] = remaining
        else:
            updated.pop("field_provenance", None)
    return updated


def _without_invalid_symbols(extra_parameters: dict[str, Any]) -> dict[str, Any]:
    if not extra_parameters:
        return {}
    updated = dict(extra_parameters)
    updated.pop("invalid_symbols", None)
    return updated


def _without_weak_implicit_current_symbols(
    *,
    current_symbols: list[str],
    benchmark_symbol: str | None,
    current_user_message: str,
) -> list[str]:
    if benchmark_symbol is None or not current_symbols:
        return current_symbols
    weak_symbols = _weak_implicit_current_symbol_set(
        current_symbols=current_symbols,
        benchmark_symbol=benchmark_symbol,
        current_user_message=current_user_message,
    )
    if not weak_symbols:
        return current_symbols
    stronger_symbols = [symbol for symbol in current_symbols if symbol not in weak_symbols]
    return stronger_symbols or current_symbols


def _weak_implicit_current_symbol_set(
    *,
    current_symbols: list[str],
    benchmark_symbol: str | None,
    current_user_message: str,
) -> set[str]:
    if benchmark_symbol is None:
        return set()
    return {
        symbol
        for symbol in current_symbols
        if len(symbol) <= 2
        and not _message_explicitly_mentions_symbol(
            current_user_message,
            symbols=[symbol],
        )
    }


def _without_weak_implicit_short_symbol_mentions(
    *,
    grounded_symbols: list[str],
    grounded_mentions: list[Any],
    current_symbols: list[str],
    benchmark_symbol: str | None,
    current_user_message: str,
) -> list[str]:
    if benchmark_symbol is None or not current_symbols:
        return grounded_symbols

    current_symbol_set = set(current_symbols)
    weak_symbols: set[str] = set()
    for mention in grounded_mentions:
        symbol = _normalized_symbol(getattr(mention.asset, "canonical_symbol", None))
        if symbol is None or symbol not in current_symbol_set:
            continue
        if _message_explicitly_mentions_symbol(current_user_message, symbols=[symbol]):
            continue
        if len(symbol) > 2:
            continue
        raw_text = str(getattr(mention, "raw_text", "") or "").strip()
        if not raw_text or raw_text != raw_text.lower() or len(raw_text.split()) != 1:
            continue
        weak_symbols.add(symbol)

    if not weak_symbols:
        pruned_current_symbols = _without_weak_implicit_current_symbols(
            current_symbols=current_symbols,
            benchmark_symbol=benchmark_symbol,
            current_user_message=current_user_message,
        )
        weak_symbols = set(current_symbols) - set(pruned_current_symbols)
        if not weak_symbols:
            return grounded_symbols

    filtered = [symbol for symbol in grounded_symbols if symbol not in weak_symbols]
    if not filtered:
        filtered = [symbol for symbol in current_symbols if symbol not in weak_symbols]
    if not filtered:
        return grounded_symbols
    return filtered


def _asset_resolution_source_for_canonicalization(
    strategy: StrategySummary,
    *,
    index: int,
    symbol: str,
) -> ResolutionSource:
    field = f"asset_universe[{index}]"
    normalized_symbol = str(symbol or "").strip().upper()
    for item in strategy.resolution_provenance:
        if _field_base(_provenance_field(item)) != "asset_universe":
            continue
        if _provenance_field(item) != field and len(strategy.asset_universe) > 1:
            continue
        raw_text = (
            item.raw_text
            if isinstance(item, ResolutionProvenance)
            else item.get("raw_text")
        )
        canonical = (
            item.canonical_symbol
            if isinstance(item, ResolutionProvenance)
            else item.get("canonical_symbol")
        )
        if str(canonical or "").strip().upper() == normalized_symbol or (
            str(raw_text or "").strip().upper() == normalized_symbol
        ):
            source = (
                item.source
                if isinstance(item, ResolutionProvenance)
                else item.get("source")
            )
            if source in {"llm_extraction", "user_mention"}:
                return source
    return "llm_extraction"


def _strategy_with_execution_defaults(strategy: StrategySummary) -> StrategySummary:
    strategy_type = executable_strategy_type(strategy)
    updated = strategy.model_copy(deep=True)
    if strategy_type == "signal_strategy":
        updated.strategy_type = "signal_strategy"
        entry_rule = strategy_rule(updated, "entry")
        if entry_rule is not None:
            updated.entry_rule = entry_rule
            updated.exit_rule = strategy_rule(
                updated, "exit"
            ) or opposite_moving_average_crossover_rule(entry_rule)
            updated.extra_parameters = {
                **updated.extra_parameters,
                "entry_rule": updated.entry_rule,
                "exit_rule": updated.exit_rule,
            }
            if not updated.entry_logic:
                updated.entry_logic = moving_average_crossover_text(updated.entry_rule)
            if not updated.exit_logic:
                updated.exit_logic = moving_average_crossover_text(updated.exit_rule)
    return updated


def _strategy_with_default_template_for_complete_no_rule_shape(
    strategy: StrategySummary,
) -> tuple[StrategySummary, list[str]]:
    if executable_strategy_type(strategy) in SUPPORTED_STRATEGY_TYPES:
        return strategy, []
    if strategy.strategy_type not in (None, ""):
        return strategy, []
    if not _strategy_has_complete_no_rule_execution_shape(strategy):
        return strategy, []
    if _strategy_supplies_executable_rule_edit(strategy):
        return strategy, []
    updated = strategy.model_copy(deep=True)
    updated.strategy_type = "buy_and_hold"
    _clear_incompatible_strategy_rule_state(updated, "buy_and_hold")
    return updated, ["complete_no_rule_shape_defaulted_to_buy_and_hold"]


def _strategy_has_complete_no_rule_execution_shape(strategy: StrategySummary) -> bool:
    return bool(
        strategy.asset_universe
        and strategy.date_range
        and not strategy.cadence
        and not strategy.entry_logic
        and not strategy.exit_logic
        and not strategy.entry_rule
        and not strategy.exit_rule
        and not strategy.rule_spec
    )


def _normalized_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


def _unsupported_symbol_constraints(
    *,
    strategy: StrategySummary,
    contract: Any,
) -> list[UnsupportedConstraint]:
    invalid_symbols = strategy.extra_parameters.get("invalid_symbols", [])
    if not invalid_symbols:
        return []
    return [
        UnsupportedConstraint(
            category="unsupported_symbol",
            raw_value=", ".join(str(symbol) for symbol in invalid_symbols),
            explanation=(
                "I understood the asset reference, but I could not verify it in "
                "the supported market data universe for this run."
            ),
            simplification_options=contract.get_simplification_options(
                "unsupported_symbol"
            ),
        )
    ]


def _unsupported_strategy_logic_constraint(
    *,
    strategy: StrategySummary,
    existing_constraints: list[UnsupportedConstraint],
    contract: Any,
) -> UnsupportedConstraint | None:
    if existing_constraints:
        return None
    if executable_strategy_type(strategy) in SUPPORTED_STRATEGY_TYPES:
        return None
    if _strategy_supplies_executable_rule_edit(strategy):
        return None
    if not _strategy_has_unstructured_strategy_thesis(strategy):
        return None
    raw_value = _unstructured_strategy_raw_value(strategy)
    return UnsupportedConstraint(
        category="unsupported_strategy_logic",
        raw_value=raw_value,
        explanation=(
            "That idea needs a rule or data source the current backtest engine "
            "cannot execute directly yet."
        ),
        simplification_options=contract.get_simplification_options(
            "unsupported_strategy_logic"
        ),
    )


def _strategy_with_current_message_draft_only_indicator_text(
    *,
    strategy: StrategySummary,
    interpretation: StructuredInterpretation,
    current_user_message: str,
) -> tuple[StrategySummary, list[str]]:
    explicit_indicator = explicit_draft_only_indicator_evidence(
        strategy=strategy,
        current_user_message=current_user_message,
    )
    if explicit_indicator is not None:
        if _strategy_supplies_executable_rule_edit(strategy):
            return strategy, []
        if strategy_type_is_user_selected(strategy):
            return strategy, []
        updated = strategy.model_copy(deep=True)
        updated.strategy_type = None
        extra_parameters = dict(updated.extra_parameters or {})
        for key in ("raw_strategy_type", "strategy_type", "template"):
            extra_parameters.pop(key, None)
        updated.extra_parameters = extra_parameters
        updated.raw_user_phrasing = str(current_user_message or "").strip() or None
        _indicator, raw_indicator_text = explicit_indicator
        updated.entry_logic = updated.entry_logic or raw_indicator_text
        return updated, [
            "draft_only_indicator_text_preserved",
            "explicit_unsupported_indicator_overrode_strategy_label",
        ]
    if executable_strategy_type(strategy) in SUPPORTED_STRATEGY_TYPES:
        return strategy, []
    if _strategy_supplies_executable_rule_edit(strategy):
        return strategy, []
    if not (
        strategy.asset_universe
        or strategy.strategy_type
        or strategy.entry_logic
        or strategy.exit_logic
        or strategy.rule_spec
    ):
        return strategy, []
    missing_field_bases = {
        _field_base(str(field)) for field in interpretation.missing_required_fields
    }
    if not missing_field_bases.intersection(
        {"strategy_type", "entry_logic", "exit_logic"}
    ):
        return strategy, []
    if draft_only_indicator_from_text(current_user_message) is None:
        return strategy, []
    updated = strategy.model_copy(deep=True)
    updated.raw_user_phrasing = str(current_user_message or "").strip() or None
    if updated.raw_user_phrasing is None:
        return strategy, []
    return updated, ["draft_only_indicator_text_preserved"]


def _strategy_has_unstructured_strategy_thesis(strategy: StrategySummary) -> bool:
    return bool(
        str(strategy.strategy_thesis or "").strip()
        or str(strategy.raw_user_phrasing or "").strip()
    )


def _unstructured_strategy_raw_value(strategy: StrategySummary) -> str:
    for value in (
        strategy.entry_logic,
        strategy.strategy_thesis,
        strategy.raw_user_phrasing,
        strategy.strategy_type,
    ):
        text = str(value or "").strip()
        if text:
            return text
    return "unsupported strategy logic"


def _ambiguous_fields_from_resolution(
    provenance: list[ResolutionProvenance],
) -> list[AmbiguousField]:
    return [
        AmbiguousField(
            field_name=item.field,
            raw_value=item.raw_text,
            candidate_normalized_value=item.canonical_symbol,
            reason_code=f"{item.candidate_kind}_resolution_ambiguous",
        )
        for item in provenance
        if item.source == "llm_extraction" and item.resolution_status == "ambiguous"
    ]


def _filter_resolved_strategy_ambiguities(
    *,
    strategy: StrategySummary,
    fields: list[AmbiguousField],
) -> tuple[list[AmbiguousField], list[str]]:
    filtered: list[AmbiguousField] = []
    suppressed = False
    for field in fields:
        field_name = _field_base(field.field_name)
        if _strategy_field_is_executable(strategy=strategy, field_name=field_name):
            suppressed = True
            continue
        filtered.append(field)
    reason_codes = ["resolved_strategy_ambiguity_suppressed"] if suppressed else []
    return filtered, reason_codes


def _strategy_field_is_executable(
    *,
    strategy: StrategySummary,
    field_name: str,
) -> bool:
    if field_name == "entry_logic":
        return bool(
            strategy_rule(strategy, "entry")
            or _valid_rule_spec_from_strategy(strategy)
            or canonical_indicator_parameters_from_strategy(strategy)
        )
    if field_name == "exit_logic":
        return bool(
            strategy_rule(strategy, "exit")
            or _valid_rule_spec_from_strategy(strategy)
            or canonical_indicator_parameters_from_strategy(strategy)
        )
    if field_name in {"entry_rule", "exit_rule", "rule_spec"}:
        return bool(
            strategy_rule(strategy, "entry")
            or strategy_rule(strategy, "exit")
            or _valid_rule_spec_from_strategy(strategy)
        )
    if field_name == "capital_amount":
        return _strategy_has_user_grounded_capital_amount(strategy)
    if field_name == "cadence":
        return _strategy_has_user_grounded_cadence(strategy)
    return False


def _strategy_has_user_grounded_capital_amount(strategy: StrategySummary) -> bool:
    if strategy.capital_amount is None:
        return False
    return _strategy_field_provenance(strategy, "capital_amount") in (
        _USER_GROUNDED_CAPITAL_SOURCES
    )


def _strategy_has_user_grounded_cadence(strategy: StrategySummary) -> bool:
    if strategy.cadence in (None, "", [], {}):
        return False
    return _strategy_field_provenance(strategy, "cadence") in (
        _USER_GROUNDED_CADENCE_SOURCES
    )


def _strategy_field_provenance(strategy: StrategySummary, field_name: str) -> str:
    field_provenance = dict(strategy.extra_parameters or {}).get("field_provenance")
    if not isinstance(field_provenance, dict):
        return ""
    return str(field_provenance.get(field_name) or "").strip()


def _unsupported_constraints_from_resolution(
    provenance: list[ResolutionProvenance],
    *,
    contract: Any,
) -> list[UnsupportedConstraint]:
    constraints: list[UnsupportedConstraint] = []
    for item in provenance:
        if (
            item.resolution_status
            not in {
                "unsupported",
                "unavailable_for_requested_run",
            }
            or item.source != "llm_extraction"
        ):
            continue
        category = (
            "unavailable_for_requested_run"
            if item.resolution_status == "unavailable_for_requested_run"
            else f"unsupported_{item.candidate_kind}"
        )
        if item.resolution_status == "unavailable_for_requested_run":
            explanation = (
                "I found the instrument, but the requested date range or timeframe "
                "is not available for a supported run."
            )
        else:
            explanation = (
                "I understood the asset reference, but Argus Alpha cannot execute it "
                "as requested yet."
                if item.candidate_kind == "asset"
                else "I understand that indicator, but Argus Alpha cannot execute it yet."
            )
        constraints.append(
            UnsupportedConstraint(
                category=category,
                raw_value=item.raw_text,
                explanation=explanation,
                simplification_options=contract.get_simplification_options(category),
            )
        )
    return constraints


def _missing_fields_for_interpretation(
    *,
    interpretation: StructuredInterpretation,
    strategy: StrategySummary,
    contract: Any,
    expects_strategy_route: bool | None = None,
) -> list[str]:
    route_expected = (
        expects_strategy_route
        if expects_strategy_route is not None
        else _strategy_route_expected(
            intent=interpretation.intent,
            semantic_turn_act=interpretation.semantic_turn_act,
        )
    )
    if not route_expected:
        return []
    required_missing_fields = missing_required_fields_for_strategy(
        strategy,
        contract=contract,
    )
    if (
        "pending_response_option_selected" in interpretation.reason_codes
        and (
            executable_strategy_type(strategy) == "indicator_threshold"
            or strategy_has_executable_signal_rule(strategy)
        )
    ):
        required_missing_fields = [
            field for field in required_missing_fields if field != "strategy_thesis"
        ]
    if executable_strategy_type(strategy) not in SUPPORTED_STRATEGY_TYPES:
        required_missing_fields = list(
            dict.fromkeys(["entry_logic", *required_missing_fields])
        )
    allowed_missing_fields = set(required_missing_fields)
    missing = [
        field
        for field in interpretation.missing_required_fields
        if isinstance(field, str) and field and field in allowed_missing_fields
    ]
    if "entry_logic" in required_missing_fields and "entry_logic" not in missing:
        missing.insert(0, "entry_logic")
    missing.extend(required_missing_fields)
    return list(dict.fromkeys(missing))


def _strategy_is_semantically_confirmable(
    *,
    expects_strategy_route: bool,
    ambiguous_fields: list[AmbiguousField],
    unsupported_constraints: list[UnsupportedConstraint],
    missing_required_fields: list[str],
) -> bool:
    return (
        expects_strategy_route
        and not ambiguous_fields
        and not unsupported_constraints
        and not missing_required_fields
    )


def _fresh_complete_restatement_started_new_confirmation(
    *,
    interpretation: StructuredInterpretation,
    selected_thread_metadata: dict[str, Any],
    expects_strategy_route: bool,
    requires_clarification: bool,
    ambiguous_fields: list[AmbiguousField],
    unsupported_constraints: list[UnsupportedConstraint],
    missing_required_fields: list[str],
) -> bool:
    if selected_thread_metadata.get("last_stage_outcome") != "await_user_reply":
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if not requested_field:
        return False
    if interpretation.semantic_turn_act != "new_idea":
        return False
    if interpretation.task_relation != "new_task":
        return False
    return _strategy_is_semantically_confirmable(
        expects_strategy_route=expects_strategy_route,
        ambiguous_fields=ambiguous_fields,
        unsupported_constraints=unsupported_constraints,
        missing_required_fields=missing_required_fields,
    ) and not requires_clarification


def _strategy_route_expected(
    *,
    intent: IntentName,
    semantic_turn_act: SemanticTurnAct | None,
) -> bool:
    return intent in {"strategy_drafting", "backtest_execution"} or (
        semantic_turn_act in STRATEGY_TURN_ACTS
    )


def _educational_turn_has_strategy_baggage(
    *,
    interpretation: StructuredInterpretation,
    expects_strategy_route: bool,
) -> bool:
    if interpretation.semantic_turn_act != "educational_question":
        return False
    return bool(
        expects_strategy_route
        or _strategy_has_content(interpretation.candidate_strategy_draft)
        or interpretation.requires_clarification
        or interpretation.missing_required_fields
        or interpretation.ambiguous_fields
        or interpretation.unsupported_constraints
    )


def _candidate_strategy_has_backtest_shape(strategy: StrategySummary) -> bool:
    return _strategy_has_execution_anchor(strategy)


def _strategy_has_execution_anchor(strategy: StrategySummary) -> bool:
    return any(
        value not in (None, "", [], {})
        for value in (
            strategy.strategy_type,
            strategy.asset_universe,
            strategy.asset_class,
            strategy.date_range,
            strategy.timeframe,
            strategy.entry_logic,
            strategy.exit_logic,
            strategy.rule_spec,
            strategy.cadence,
            strategy.capital_amount,
            strategy.position_size,
            strategy.risk_rules,
            strategy.comparison_baseline,
            strategy.extra_parameters,
        )
    )


def _dedupe_unsupported_constraints(
    constraints: list[UnsupportedConstraint],
) -> list[UnsupportedConstraint]:
    seen: set[tuple[str, str]] = set()
    deduped: list[UnsupportedConstraint] = []
    for constraint in constraints:
        key = (constraint.category, constraint.raw_value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(constraint)
    return deduped


def _dedupe_ambiguous_fields(fields: list[AmbiguousField]) -> list[AmbiguousField]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[AmbiguousField] = []
    for field in fields:
        key = (field.field_name, field.raw_value, field.reason_code)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(field)
    return deduped


def _dedupe_resolution_provenance(
    provenance: list[ResolutionProvenance | dict[str, Any]],
) -> list[ResolutionProvenance]:
    return dedupe_resolution_provenance_items(provenance)
