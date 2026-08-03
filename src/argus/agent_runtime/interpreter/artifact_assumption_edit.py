"""Artifact assumption-edit application: apply resolved/legacy edits to a draft and route pending artifact-assumption edits.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    ResolvedArtifactEdit,
    apply_edit_operations,
)
from argus.agent_runtime.artifacts.asset_edits import (
    normalized_asset_symbols,
    normalized_asset_universe_operation,
    same_asset_universe,
)
from argus.agent_runtime.asset_text_grounding import (
    provider_grounded_asset_evidence_from_text,
)
from argus.agent_runtime.interpreter.execution_cost_fidelity import (
    ground_planned_execution_costs,
    supported_cost_rate_value,
)
from argus.agent_runtime.interpreter.shared import (
    _RECURRING_CAPITAL_SOURCES,
    _TOTAL_CAPITAL_SOURCES,
    _date_window_intent_bound_to_latest_result,
    _field_path_base,
    _latest_result_date_window,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy,
    moving_average_crossover_text,
)
from argus.agent_runtime.stages.artifact_context import (
    active_confirmation_effective_strategy,
    strategy_from_result_reference,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import canonical_strategy_type
from argus.nlp.natural_time import resolve_date_range_intent

ResolveAssetCandidate = Callable[..., AssetResolution | None]

# Pending requested_field values whose next user reply edits the pending
# artifact. The result-card "Refine idea" action ("refinement",
# api/chat/result_actions.py) and the confirmation-card assumption prompts are
# two entry points into the same typed edit contract.
ARTIFACT_EDIT_PENDING_FIELDS = frozenset(
    {
        "assumption",
        "asset_universe",
        "comparison_baseline",
        "refinement",
    }
)


def _normalized_ticker_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper()
    return symbol or None


def _request_targets_pending_artifact_assumption_edit(
    request: InterpretationRequest,
) -> bool:
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    snapshot = request.latest_task_snapshot
    has_artifact_context = bool(
        snapshot
        and (
            snapshot.pending_strategy_summary
            or snapshot.confirmed_strategy_summary
            or snapshot.active_confirmation_reference
        )
    )
    if not has_artifact_context:
        return False
    if requested_field in ARTIFACT_EDIT_PENDING_FIELDS:
        return True
    return bool(
        not requested_field
        and snapshot is not None
        and snapshot.active_confirmation_reference is not None
        and request.current_user_message.strip()
    )


def _request_targets_post_result_artifact_edit(
    request: InterpretationRequest,
) -> bool:
    """Free-form post-result surface: a completed result and nothing pending.

    A reply here can still be an edit of the completed strategy ("could we
    try NVDA over the same period") — the no-chip twin of the Refine idea
    action. Chips and natural language are two entry points to one contract,
    so this surface may reach the same planner; response-conditioned guards
    decide whether a specific turn actually is an edit.
    """

    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    if requested_field and requested_field != "refinement":
        return False
    snapshot = request.latest_task_snapshot
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return False
    if (
        snapshot.pending_strategy_summary is not None
        or snapshot.active_confirmation_reference is not None
    ):
        return False
    return bool(request.current_user_message.strip())


def _current_artifact_asset_universe(request: InterpretationRequest) -> list[str]:
    strategy = _current_artifact_strategy(request)
    if strategy is not None and strategy.asset_universe:
        return list(strategy.asset_universe)
    reference = (
        request.latest_task_snapshot.active_confirmation_reference
        if request.latest_task_snapshot is not None
        else None
    )
    reference_assets = getattr(reference, "asset_universe", None)
    if reference_assets:
        return list(reference_assets)
    return []


def _current_artifact_strategy(request: InterpretationRequest) -> StrategySummary | None:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return None
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if snapshot.active_confirmation_reference is not None:
        effective = active_confirmation_effective_strategy(
            snapshot=snapshot,
            fallback=prior or StrategySummary(),
        )
        if effective != StrategySummary():
            return effective
    if prior is None and snapshot.latest_backtest_result_reference is not None:
        # Post-result surface: the canonical strategy is the one that ran.
        reconstructed = strategy_from_result_reference(
            snapshot.latest_backtest_result_reference
        )
        if reconstructed.asset_universe:
            return reconstructed
    return prior


def _current_total_capital_value(
    strategy: StrategySummary | None,
) -> float | None:
    if strategy is None:
        return None
    extra_parameters = strategy.extra_parameters or {}
    for field_name in ("initial_capital", "total_capital", "total_budget"):
        value = extra_parameters.get(field_name)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
    if canonical_strategy_type(strategy.strategy_type) != "dca_accumulation":
        return strategy.capital_amount
    return None


def _grounded_total_capital_alias_values(draft: LLMStrategyDraft) -> list[float]:
    provenance = draft.field_provenance or {}
    aliases = (
        ("initial_capital", draft.initial_capital),
        ("total_capital", draft.total_capital),
        ("capital_amount", draft.capital_amount),
    )
    return [
        value
        for field_name, value in aliases
        if value is not None
        and str(provenance.get(field_name) or "").strip() in _TOTAL_CAPITAL_SOURCES
        and not (
            field_name == "capital_amount"
            and canonical_strategy_type(draft.strategy_type) == "dca_accumulation"
        )
    ]


def _canonical_total_capital_value(draft: LLMStrategyDraft) -> float | None:
    grounded_values = _grounded_total_capital_alias_values(draft)
    if grounded_values:
        requested = grounded_values[0]
        return (
            requested
            if all(value == requested for value in grounded_values[1:])
            else None
        )
    if draft.initial_capital is not None:
        return draft.initial_capital
    if draft.total_capital is not None:
        return draft.total_capital
    return draft.capital_amount


def _has_conflicting_grounded_total_capital_aliases(
    draft: LLMStrategyDraft,
) -> bool:
    grounded_values = _grounded_total_capital_alias_values(draft)
    return bool(
        grounded_values
        and any(value != grounded_values[0] for value in grounded_values[1:])
    )


def _required_edit_targets_from_primary_draft(
    draft: LLMStrategyDraft | None,
    *,
    current_strategy: StrategySummary | None = None,
) -> set[str]:
    """Translate current-turn typed extraction into planner coverage requirements.

    The primary interpreter and edit planner are independent structured reads of
    the same turn. Requiring the planner to cover fields the primary interpreter
    marked explicit prevents a partial operation list from becoming a silent edit.
    """

    if draft is None:
        return set()
    provenance = draft.field_provenance or {}
    targets: set[str] = set()
    if (
        draft.asset_universe
        and normalized_asset_universe_operation(draft.asset_universe_operation)
        is not None
        and not same_asset_universe(
            draft.asset_universe,
            current_strategy.asset_universe if current_strategy else [],
        )
    ):
        targets.add("asset")
    if (
        str(draft.comparison_baseline or "").strip()
        and provenance.get("comparison_baseline") == "explicit_user"
        and _normalized_ticker_symbol(draft.comparison_baseline)
        != _normalized_ticker_symbol(
            current_strategy.comparison_baseline if current_strategy else None
        )
    ):
        targets.add("benchmark")
    has_explicit_date = (
        draft.date_range is not None
        or draft.date_range_intent is not None
        or str(draft.date_range_raw_text or "").strip()
    ) and provenance.get("date_range") == "explicit_user"
    date_matches_current = bool(
        draft.date_range is not None
        and current_strategy is not None
        and draft.date_range == current_strategy.date_range
        and draft.date_range_intent is None
        and not str(draft.date_range_raw_text or "").strip()
    )
    if has_explicit_date and not date_matches_current:
        targets.add("date_window")

    strategy_family_fields = (
        "requested_strategy_template",
        "strategy_type",
        "entry_rule",
        "exit_rule",
        "rule_spec",
    )
    has_explicit_strategy_family = any(
        provenance.get(field_name) == "explicit_user"
        for field_name in strategy_family_fields
    )
    strategy_family_changed = current_strategy is None or any(
        getattr(draft, field_name) != getattr(current_strategy, field_name, None)
        for field_name in strategy_family_fields
    )
    if (
        draft.requested_strategy_template is not None
        and has_explicit_strategy_family
        and strategy_family_changed
    ):
        targets.add("strategy_family")

    capital_source = str(provenance.get("capital_amount") or "").strip()
    current_capital = _current_total_capital_value(current_strategy)
    if any(
        value != current_capital for value in _grounded_total_capital_alias_values(draft)
    ):
        targets.add("capital")
    recurring_source = str(provenance.get("recurring_contribution") or "").strip()
    is_recurring_strategy = (
        canonical_strategy_type(draft.strategy_type) == "dca_accumulation"
    )
    recurring_amount = draft.recurring_contribution
    if recurring_amount is None and is_recurring_strategy:
        recurring_amount = draft.capital_amount
    if (
        (
            draft.recurring_contribution is not None
            and recurring_source in _RECURRING_CAPITAL_SOURCES
        )
        or (
            draft.capital_amount is not None
            and capital_source in _RECURRING_CAPITAL_SOURCES
            and is_recurring_strategy
        )
    ) and recurring_amount != (
        current_strategy.capital_amount if current_strategy else None
    ):
        targets.add("recurring_contribution")

    current_indicator_parameters = (
        indicator_parameters_from_strategy(current_strategy)
        if current_strategy is not None
        else {}
    )
    for field_name, target in (
        ("cadence", "cadence"),
        ("timeframe", "timeframe"),
    ):
        value = getattr(draft, field_name)
        current_value = getattr(current_strategy, field_name, None)
        if (
            value is not None
            and value != current_value
            and provenance.get(field_name) == "explicit_user"
        ):
            targets.add(target)
    for field_name, target in (
        ("indicator_period", "indicator_period"),
        ("entry_threshold", "indicator_entry_threshold"),
        ("exit_threshold", "indicator_exit_threshold"),
    ):
        value = getattr(draft, field_name)
        if (
            value is not None
            and value != current_indicator_parameters.get(field_name)
            and provenance.get(field_name) == "explicit_user"
        ):
            targets.add(target)
    for field_name, target in (("fee_rate", "fees"), ("slippage", "slippage")):
        if (
            field_name in draft.extra_parameters
            and provenance.get(field_name) == "explicit_user"
            and (
                current_strategy is None
                or draft.extra_parameters[field_name]
                != current_strategy.extra_parameters.get(field_name)
            )
        ):
            targets.add(target)
    return targets


def asset_edit_symbol_resolver(
    resolve_asset_candidate: ResolveAssetCandidate,
) -> Callable[[str], str | None]:
    def _resolve(raw_symbol: str) -> str | None:
        resolution = resolve_asset_candidate(
            raw_symbol,
            field="asset_edit",
            source="user_mention",
        )
        if (
            resolution is not None
            and resolution.status == "resolved"
            and resolution.asset
        ):
            return resolution.asset.canonical_symbol
        return None

    return _resolve


def _apply_resolved_edit_to_draft(
    resolved: ResolvedArtifactEdit,
    *,
    draft: LLMStrategyDraft,
    field_provenance: dict[str, str],
    extra_parameters: dict[str, Any],
    allow_indicator_parameters: bool = False,
    latest_result_window: dict[str, str] | None = None,
) -> None:
    if resolved.requested_strategy_template is not None:
        draft.requested_strategy_template = resolved.requested_strategy_template
        draft.strategy_type = resolved.strategy_type
        draft.entry_rule = resolved.entry_rule
        draft.exit_rule = resolved.exit_rule
        draft.rule_spec = resolved.rule_spec
        draft.entry_logic = moving_average_crossover_text(resolved.entry_rule)
        draft.exit_logic = moving_average_crossover_text(resolved.exit_rule)
        field_provenance["requested_strategy_template"] = "explicit_user"
        field_provenance["strategy_type"] = "explicit_user"
        field_provenance["entry_rule"] = "explicit_user"
        field_provenance["exit_rule"] = "explicit_user"
    if resolved.asset_universe is not None:
        draft.asset_universe = list(resolved.asset_universe)
        draft.asset_universe_operation = "replace"
        extra_parameters["asset_universe_operation"] = "replace"
        field_provenance["asset_universe"] = "explicit_user"
    if resolved.comparison_baseline:
        draft.comparison_baseline = resolved.comparison_baseline
        field_provenance["comparison_baseline"] = "explicit_user"
    if resolved.date_window is not None:
        date_window_intent = _date_window_intent_bound_to_latest_result(
            resolved.date_window,
            latest_result_window=latest_result_window,
        )
        if (
            date_window_intent is not None
            and str(date_window_intent.kind or "").strip() == "future_window"
        ):
            # A forward-looking edit is original intent for the future
            # admission boundary; it is never resolved, dropped, or partially
            # applied alongside the other edits.
            draft.date_range_intent = date_window_intent
        else:
            intent_resolution = (
                resolve_date_range_intent(date_window_intent)
                if date_window_intent is not None
                else None
            )
            if intent_resolution is not None:
                draft.date_range_intent = date_window_intent
                draft.date_range = intent_resolution.payload
                field_provenance["date_range"] = "explicit_user"
    if resolved.initial_capital is not None:
        draft.initial_capital = resolved.initial_capital
        field_provenance["initial_capital"] = "starting_capital"
    if resolved.recurring_contribution_amount is not None:
        recurring_amount = float(resolved.recurring_contribution_amount)
        draft.capital_amount = recurring_amount
        draft.recurring_contribution = recurring_amount
        field_provenance["capital_amount"] = "recurring_contribution"
        field_provenance["recurring_contribution"] = "recurring_contribution"
        extra_parameters["recurring_contribution"] = recurring_amount
    if resolved.cadence is not None:
        cadence = _supported_dca_cadence_value(resolved.cadence)
        if cadence is not None:
            draft.cadence = cadence
            field_provenance["cadence"] = "explicit_user"
            extra_parameters["recurring_cadence"] = cadence
    if resolved.timeframe is not None:
        draft.timeframe = resolved.timeframe
        field_provenance["timeframe"] = "explicit_user"
    if resolved.fee_rate is not None:
        extra_parameters["fee_rate"] = resolved.fee_rate
        field_provenance["fee_rate"] = "explicit_user"
    if resolved.slippage is not None:
        extra_parameters["slippage"] = resolved.slippage
        field_provenance["slippage"] = "explicit_user"
    if resolved.indicator_parameters and allow_indicator_parameters:
        draft.strategy_type = "indicator_threshold"
        draft.indicator = "rsi"
        indicator_parameters = {
            "indicator": "rsi",
            **resolved.indicator_parameters,
        }
        if "indicator_period" in resolved.indicator_parameters:
            draft.indicator_period = int(
                resolved.indicator_parameters["indicator_period"]
            )
            field_provenance["indicator_period"] = "explicit_user"
        if "entry_threshold" in resolved.indicator_parameters:
            draft.entry_threshold = float(
                resolved.indicator_parameters["entry_threshold"]
            )
            field_provenance["entry_threshold"] = "explicit_user"
        if "exit_threshold" in resolved.indicator_parameters:
            draft.exit_threshold = float(resolved.indicator_parameters["exit_threshold"])
            field_provenance["exit_threshold"] = "explicit_user"
        extra_parameters["indicator"] = "rsi"
        extra_parameters["indicator_parameters"] = indicator_parameters
        field_provenance["indicator_parameters"] = "explicit_user"


def _apply_legacy_flat_edit_fields(
    plan: ArtifactAssumptionEditPlan,
    *,
    draft: LLMStrategyDraft,
    field_provenance: dict[str, str],
    extra_parameters: dict[str, Any],
) -> None:
    if plan.asset_universe:
        operation = normalized_asset_universe_operation(plan.asset_universe_operation)
        draft.asset_universe = list(plan.asset_universe)
        if operation is not None:
            draft.asset_universe_operation = operation
            extra_parameters["asset_universe_operation"] = operation
        field_provenance["asset_universe"] = "explicit_user"
    if plan.comparison_baseline is not None:
        benchmark = str(plan.comparison_baseline or "").strip().upper()
        if benchmark:
            draft.comparison_baseline = benchmark
            field_provenance["comparison_baseline"] = "explicit_user"
    if plan.initial_capital is not None:
        draft.initial_capital = plan.initial_capital
        field_provenance["initial_capital"] = "starting_capital"
    if plan.recurring_contribution_amount is not None:
        recurring_amount = float(plan.recurring_contribution_amount)
        draft.capital_amount = recurring_amount
        draft.recurring_contribution = recurring_amount
        field_provenance["capital_amount"] = "recurring_contribution"
        field_provenance["recurring_contribution"] = "recurring_contribution"
        extra_parameters["recurring_contribution"] = recurring_amount
    if plan.cadence is not None:
        cadence = _supported_dca_cadence_value(plan.cadence)
        if cadence is not None:
            draft.cadence = cadence
            field_provenance["cadence"] = "explicit_user"
            extra_parameters["recurring_cadence"] = cadence
    if plan.timeframe is not None:
        draft.timeframe = plan.timeframe
        field_provenance["timeframe"] = "explicit_user"
    if plan.fee_rate is not None:
        fee_rate = supported_cost_rate_value(plan.fee_rate, field_name="fee_rate")
        if fee_rate is not None:
            extra_parameters["fee_rate"] = fee_rate
            field_provenance["fee_rate"] = "explicit_user"
    if plan.slippage is not None:
        slippage = supported_cost_rate_value(plan.slippage, field_name="slippage")
        if slippage is not None:
            extra_parameters["slippage"] = slippage
            field_provenance["slippage"] = "explicit_user"


def _edit_plan_reshapes_non_recurring_strategy(
    plan: ArtifactAssumptionEditPlan,
    *,
    prior_strategy_type: Any,
) -> bool:
    """Recurring-buy plan fields aimed at a non-recurring strategy are a
    reshape ("make it recurring buys instead"), not an assumption edit.

    The edit-operation set cannot change strategy_type, so applying such a
    plan would silently keep the old strategy; callers must step aside and
    let a reshape-capable interpretation path handle the turn.
    """

    proposes_recurring_fields = (
        plan.cadence is not None
        or plan.recurring_contribution_amount is not None
        or any(
            operation.target in {"cadence", "recurring_contribution"}
            for operation in plan.operations
        )
    )
    if not proposes_recurring_fields:
        return False
    return canonical_strategy_type(prior_strategy_type) != "dca_accumulation"


def _current_artifact_uses_rsi(request: InterpretationRequest) -> bool:
    strategy = _current_artifact_strategy(request)
    if strategy is None:
        return False
    parameters = indicator_parameters_from_strategy(strategy)
    indicator = (
        str(
            parameters.get("indicator")
            or strategy.extra_parameters.get("indicator")
            or ""
        )
        .strip()
        .casefold()
    )
    return indicator == "rsi"


_MATERIALIZED_FIELD_TARGETS = {
    "asset_universe": "asset",
    "comparison_baseline": "benchmark",
    "date_range": "date_window",
    "requested_strategy_template": "strategy_family",
    "initial_capital": "capital",
    "recurring_contribution": "recurring_contribution",
    "cadence": "cadence",
    "timeframe": "timeframe",
    "fee_rate": "fees",
    "slippage": "slippage",
    "indicator_period": "indicator_period",
    "entry_threshold": "indicator_entry_threshold",
    "exit_threshold": "indicator_exit_threshold",
}


def materialized_artifact_edit_targets(
    plan: ArtifactAssumptionEditPlan,
    *,
    request: InterpretationRequest,
    asset_symbol_resolver: Callable[[str], str | None] | None = None,
    resolve_asset_candidate: ResolveAssetCandidate | None = None,
    primary_draft: LLMStrategyDraft | None = None,
) -> set[str] | None:
    """Return requested deltas that survive the exact materialization path."""

    draft, field_provenance, _ = _materialized_artifact_edit(
        plan,
        request=request,
        asset_symbol_resolver=asset_symbol_resolver,
        primary_draft=primary_draft,
    )
    materialized_targets = {
        target
        for field_name, target in _MATERIALIZED_FIELD_TARGETS.items()
        if field_name in field_provenance
    }
    if draft.date_range_intent is not None:
        materialized_targets.add("date_window")
    if primary_draft is None:
        return materialized_targets
    if _has_conflicting_grounded_total_capital_aliases(primary_draft):
        return None
    current_strategy = _current_artifact_strategy(request)
    primary_has_material_delta = _primary_draft_has_material_delta(
        primary_draft,
        current_strategy=current_strategy,
        request=request,
    )
    requested_targets = _required_edit_targets_from_primary_draft(
        primary_draft,
        current_strategy=current_strategy,
    )
    grounded_asset_symbols = _grounded_asset_symbols_from_message(
        request.current_user_message,
        resolve_asset_candidate=resolve_asset_candidate,
    )
    if primary_draft is not None:
        grounded_asset_symbols.discard(
            _normalized_ticker_symbol(primary_draft.comparison_baseline)
        )
    grounded_asset_symbols.discard(_normalized_ticker_symbol(draft.comparison_baseline))
    current_assets = set(
        normalized_asset_symbols(
            current_strategy.asset_universe if current_strategy else []
        )
    )
    primary_assets = set(normalized_asset_symbols(primary_draft.asset_universe))
    if (
        "asset" in materialized_targets
        and (grounded_asset_symbols | primary_assets) - current_assets
    ):
        requested_targets.add("asset")
    matching_targets = {
        target
        for target in materialized_targets
        if (not primary_has_material_delta and target != "asset")
        or (
            (target != "asset" or target in requested_targets)
            and _materialized_target_matches_primary_delta(
                target,
                materialized_draft=draft,
                primary_draft=primary_draft,
                current_strategy=current_strategy,
                request=request,
                grounded_asset_symbols=grounded_asset_symbols,
            )
        )
    }
    if any(
        target not in matching_targets
        and _materialized_target_mutates_current(
            target,
            materialized_draft=draft,
            current_strategy=current_strategy,
            request=request,
        )
        for target in materialized_targets
    ):
        return None
    return matching_targets


def _materialized_target_matches_primary_delta(
    target: str,
    *,
    materialized_draft: LLMStrategyDraft,
    primary_draft: LLMStrategyDraft | None,
    current_strategy: StrategySummary | None,
    request: InterpretationRequest,
    grounded_asset_symbols: set[str] | None = None,
) -> bool:
    """Prove the candidate applied the primary interpreter's requested value."""

    if primary_draft is None:
        return False
    if target == "asset":
        current = set(
            normalized_asset_symbols(
                current_strategy.asset_universe if current_strategy else []
            )
        )
        primary_requested = set(normalized_asset_symbols(primary_draft.asset_universe))
        requested = primary_requested | set(grounded_asset_symbols or set())
        materialized = set(normalized_asset_symbols(materialized_draft.asset_universe))
        operation = normalized_asset_universe_operation(
            primary_draft.asset_universe_operation
        )
        materialized_operation = normalized_asset_universe_operation(
            materialized_draft.asset_universe_operation
        )
        if not requested or materialized == current:
            return False
        if operation == "replace" and primary_requested - current:
            return materialized == primary_requested
        if materialized_operation == "append":
            return bool(materialized - current) and materialized <= requested
        if operation == "replace" and materialized == primary_requested:
            return True
        if operation == "append":
            return (
                current <= materialized
                and primary_requested <= materialized
                and (current ^ materialized) <= requested
            )
        if materialized_operation == "replace":
            additions = materialized - current
            return bool(additions) and additions <= requested
        changed_symbols = current ^ materialized
        return changed_symbols <= requested and (
            not primary_requested
            or bool(changed_symbols & primary_requested)
            or materialized == primary_requested
        )
    if target == "benchmark":
        requested = _normalized_ticker_symbol(primary_draft.comparison_baseline)
        current = _normalized_ticker_symbol(
            current_strategy.comparison_baseline if current_strategy else None
        )
        return bool(
            requested
            and requested != current
            and _normalized_ticker_symbol(materialized_draft.comparison_baseline)
            == requested
        )
    if target == "date_window":
        requested = _canonical_draft_date_request(primary_draft, request=request)
        materialized = _canonical_draft_date_request(
            materialized_draft,
            request=request,
        )
        current_range = (
            current_strategy.date_range if current_strategy is not None else None
        )
        if (
            requested is not None
            and requested[0] == "range"
            and isinstance(requested[1], dict)
            and materialized is not None
            and materialized[0] == "range"
            and isinstance(materialized[1], dict)
        ):
            changed_endpoints = {
                endpoint: requested[1][endpoint]
                for endpoint in ("start", "end")
                if endpoint in requested[1]
                and (
                    not isinstance(current_range, dict)
                    or requested[1][endpoint] != current_range.get(endpoint)
                )
            }
            materialized_changed_endpoints = {
                endpoint
                for endpoint in ("start", "end")
                if endpoint in materialized[1]
                and (
                    not isinstance(current_range, dict)
                    or materialized[1][endpoint] != current_range.get(endpoint)
                )
            }
            return (
                bool(changed_endpoints)
                and materialized_changed_endpoints == set(changed_endpoints)
                and all(
                    materialized[1].get(endpoint) == value
                    for endpoint, value in changed_endpoints.items()
                )
            )
        current = ("range", current_range) if current_range is not None else None
        return (
            requested is not None and requested != current and materialized == requested
        )
    if target == "strategy_family":
        fields = (
            "requested_strategy_template",
            "strategy_type",
            "entry_rule",
            "exit_rule",
            "rule_spec",
        )
        requested = {
            field_name: getattr(primary_draft, field_name)
            for field_name in fields
            if getattr(primary_draft, field_name) is not None
        }
        return (
            bool(requested)
            and any(
                requested[field_name] != getattr(current_strategy, field_name, None)
                for field_name in requested
            )
            and all(
                getattr(materialized_draft, field_name) == value
                for field_name, value in requested.items()
            )
        )

    if target == "capital":
        requested = _canonical_total_capital_value(primary_draft)
        materialized = _canonical_total_capital_value(materialized_draft)
        current = _current_total_capital_value(current_strategy)
    elif target == "recurring_contribution":
        requested = (
            primary_draft.recurring_contribution
            if primary_draft.recurring_contribution is not None
            else primary_draft.capital_amount
        )
        materialized = materialized_draft.recurring_contribution
        current = current_strategy.capital_amount if current_strategy else None
    elif target in {"cadence", "timeframe"}:
        requested = getattr(primary_draft, target)
        materialized = getattr(materialized_draft, target)
        current = getattr(current_strategy, target, None)
    elif target in {"fees", "slippage"}:
        field_name = "fee_rate" if target == "fees" else "slippage"
        requested = primary_draft.extra_parameters.get(field_name)
        materialized = materialized_draft.extra_parameters.get(field_name)
        current = (
            current_strategy.extra_parameters.get(field_name)
            if current_strategy is not None
            else None
        )
    elif target in {
        "indicator_period",
        "indicator_entry_threshold",
        "indicator_exit_threshold",
    }:
        field_name = {
            "indicator_period": "indicator_period",
            "indicator_entry_threshold": "entry_threshold",
            "indicator_exit_threshold": "exit_threshold",
        }[target]
        requested = getattr(primary_draft, field_name)
        materialized = getattr(materialized_draft, field_name)
        current = (
            indicator_parameters_from_strategy(current_strategy).get(field_name)
            if current_strategy is not None
            else None
        )
    else:
        return False
    return requested is not None and requested != current and materialized == requested


def _primary_draft_has_material_delta(
    draft: LLMStrategyDraft,
    *,
    current_strategy: StrategySummary | None,
    request: InterpretationRequest,
) -> bool:
    return any(
        _materialized_target_matches_primary_delta(
            target,
            materialized_draft=draft,
            primary_draft=draft,
            current_strategy=current_strategy,
            request=request,
        )
        for target in set(_MATERIALIZED_FIELD_TARGETS.values()) | {"date_window"}
    )


def _materialized_target_mutates_current(
    target: str,
    *,
    materialized_draft: LLMStrategyDraft,
    current_strategy: StrategySummary | None,
    request: InterpretationRequest,
) -> bool:
    if target == "asset":
        current = set(
            normalized_asset_symbols(
                current_strategy.asset_universe if current_strategy else []
            )
        )
        materialized = set(normalized_asset_symbols(materialized_draft.asset_universe))
        if (
            normalized_asset_universe_operation(
                materialized_draft.asset_universe_operation
            )
            == "append"
        ):
            materialized |= current
        return materialized != current
    return _materialized_target_matches_primary_delta(
        target,
        materialized_draft=materialized_draft,
        primary_draft=materialized_draft,
        current_strategy=current_strategy,
        request=request,
    )


def _grounded_asset_symbols_from_message(
    message: str,
    *,
    resolve_asset_candidate: ResolveAssetCandidate | None,
) -> set[str]:
    if resolve_asset_candidate is None:
        return set()

    def resolve_candidate(query: str) -> AssetResolution | None:
        try:
            return resolve_asset_candidate(
                query,
                field="asset_edit",
                source="user_mention",
            )
        except Exception:
            return None

    return {
        evidence["symbol"]
        for evidence in provider_grounded_asset_evidence_from_text(
            message,
            resolve_candidate=resolve_candidate,
        )
    }


def _canonical_draft_date_request(
    draft: LLMStrategyDraft,
    *,
    request: InterpretationRequest,
) -> tuple[str, Any] | None:
    if draft.date_range_intent is not None:
        intent = _date_window_intent_bound_to_latest_result(
            draft.date_range_intent,
            latest_result_window=_latest_result_date_window(request),
        )
        resolution = resolve_date_range_intent(intent) if intent is not None else None
        if resolution is not None:
            return ("range", resolution.payload)
        if intent is not None and intent.kind == "future_window":
            return (
                "intent",
                intent.model_dump(
                    mode="json",
                    exclude={"confidence", "evidence"},
                ),
            )
    if draft.date_range is not None:
        return ("range", draft.date_range)
    return None


def _materialized_artifact_edit(
    plan: ArtifactAssumptionEditPlan,
    *,
    request: InterpretationRequest,
    asset_symbol_resolver: Callable[[str], str | None] | None,
    primary_draft: LLMStrategyDraft | None,
) -> tuple[LLMStrategyDraft, dict[str, str], dict[str, Any]]:
    draft = LLMStrategyDraft(raw_user_phrasing=request.current_user_message)
    current_strategy = _current_artifact_strategy(request)
    if current_strategy is not None and current_strategy.strategy_type:
        draft.strategy_type = current_strategy.strategy_type
    field_provenance: dict[str, str] = {}
    extra_parameters: dict[str, Any] = {}
    if plan.operations:
        resolved = apply_edit_operations(
            plan.operations,
            current_asset_universe=_current_artifact_asset_universe(request),
            asset_symbol_resolver=asset_symbol_resolver,
        )
        _apply_resolved_edit_to_draft(
            resolved,
            draft=draft,
            field_provenance=field_provenance,
            extra_parameters=extra_parameters,
            allow_indicator_parameters=_current_artifact_uses_rsi(request),
            latest_result_window=_latest_result_date_window(request),
        )
    else:
        _apply_legacy_flat_edit_fields(
            plan,
            draft=draft,
            field_provenance=field_provenance,
            extra_parameters=extra_parameters,
        )
    if extra_parameters:
        draft.extra_parameters.update(extra_parameters)
    if field_provenance:
        draft.field_provenance = field_provenance
    ground_planned_execution_costs(
        draft,
        current_message=request.current_user_message,
        primary_draft=primary_draft,
        extra_parameters=extra_parameters,
        field_provenance=field_provenance,
    )
    return draft, field_provenance, extra_parameters


def _response_from_artifact_assumption_edit_plan(
    *,
    plan: ArtifactAssumptionEditPlan,
    request: InterpretationRequest,
    asset_symbol_resolver: Callable[[str], str | None] | None = None,
    primary_draft: LLMStrategyDraft | None = None,
) -> LLMInterpretationResponse:
    artifact_target = (
        "latest_result"
        if _request_targets_post_result_artifact_edit(request)
        else (
            "active_confirmation"
            if request.latest_task_snapshot is not None
            and request.latest_task_snapshot.active_confirmation_reference is not None
            else None
        )
    )
    draft, field_provenance, extra_parameters = _materialized_artifact_edit(
        plan,
        request=request,
        asset_symbol_resolver=asset_symbol_resolver,
        primary_draft=primary_draft,
    )

    if plan.outcome == "ready_to_confirm":
        if plan.operations and not field_provenance and not extra_parameters:
            return LLMInterpretationResponse(
                intent="conversation_followup",
                task_relation="continue",
                requires_clarification=True,
                user_goal_summary=(
                    plan.user_goal_summary
                    or "The requested assumption change cannot be applied here."
                ),
                candidate_strategy_draft=draft,
                assistant_response=(
                    plan.assistant_response
                    or "I can change RSI thresholds only on an active RSI confirmation card."
                ),
                confidence=plan.confidence,
                reason_codes=["artifact_assumption_edit_planned"],
                semantic_turn_act="unsupported_request",
                artifact_target=artifact_target,
            )
        return LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary=(
                plan.user_goal_summary
                or "User changed a visible confirmation assumption."
            ),
            candidate_strategy_draft=draft,
            # Surface the model's note when an applied edit also had a part it could
            # not change (mixed supported/unsupported), so the reply never silently
            # drops the unsupported part. None for a clean edit.
            assistant_response=plan.assistant_response,
            confidence=plan.confidence,
            reason_codes=["artifact_assumption_edit_planned"],
            semantic_turn_act="answer_pending_need",
            artifact_target=artifact_target,
        )

    return LLMInterpretationResponse(
        intent=(
            "unsupported_or_out_of_scope"
            if plan.outcome == "unsupported"
            else "conversation_followup"
        ),
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary=(
            plan.user_goal_summary
            or "The requested assumption change needs clarification."
        ),
        candidate_strategy_draft=draft,
        missing_required_fields=list(plan.missing_required_fields),
        assistant_response=plan.assistant_response,
        confidence=plan.confidence,
        reason_codes=["artifact_assumption_edit_planned"],
        semantic_turn_act=(
            "unsupported_request"
            if plan.outcome == "unsupported"
            else "answer_pending_need"
        ),
        artifact_target=artifact_target,
    )
