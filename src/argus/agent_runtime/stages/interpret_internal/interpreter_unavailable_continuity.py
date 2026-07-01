"""Interpreter-unavailable continuity helpers for interpret stage."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    apply_edit_operations,
)
from argus.agent_runtime.artifact_edit_planner import (
    plan_artifact_assumption_edit as _plan_artifact_assumption_edit,
)
from argus.agent_runtime.artifacts.asset_edits import (
    normalized_asset_universe_operation,
    same_asset_universe,
)
from argus.agent_runtime.asset_text_grounding import provider_ticker_mentions_from_text
from argus.agent_runtime.interpreter.pending_option import (
    _apply_pending_response_option_replacement,
    _llm_draft_from_strategy_summary,
    _pending_response_intent_options,
)
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.resolution import AssetResolution
from argus.agent_runtime.stages.artifact_context import (
    active_confirmation_effective_strategy,
)
from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _dedupe_resolution_provenance,
)
from argus.agent_runtime.stages.interpret_internal.confirmation_artifact_edits import (
    apply_resolved_artifact_edit_to_strategy_summary,
    asset_edit_symbol_resolver,
    strategy_summary_uses_rsi,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, StrategySummary, TaskSnapshot
from argus.agent_runtime.strategy_contract import canonical_strategy_type
from argus.domain.indicators import draft_only_indicator_from_text

ResolveAssetCandidate = Callable[..., AssetResolution | None]
DefaultBenchmarkForAssetClass = Callable[..., str | None]
PlanArtifactAssumptionEdit = Callable[..., Any]


def pending_response_option_when_interpreter_unavailable(
    *,
    state: RunState,
    user: Any,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    selected_thread_metadata: dict[str, Any],
) -> StructuredInterpretation | None:
    if snapshot is None or snapshot.pending_strategy_summary is None:
        return None
    if not current_user_message.strip():
        return None
    request = InterpretationRequest(
        current_user_message=current_user_message,
        recent_thread_history=list(state.recent_thread_history),
        latest_task_snapshot=snapshot,
        selected_thread_metadata=selected_thread_metadata,
        user=user,
    )
    options = _pending_response_intent_options(request)
    option_index = _pending_response_option_index_from_text(
        current_user_message,
        options=options,
    )
    if option_index is None:
        return None
    replacement_values = options[option_index].get("replacement_values")
    if not isinstance(replacement_values, dict):
        return None
    draft = _llm_draft_from_strategy_summary(snapshot.pending_strategy_summary)
    replacement_result = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values=replacement_values,
        current_missing=[],
    )
    strategy = _strategy_from_llm(replacement_result["draft"])
    missing_fields = list(replacement_result["missing_fields"])
    return StructuredInterpretation(
        intent="strategy_drafting" if missing_fields else "backtest_execution",
        task_relation="continue",
        requires_clarification=bool(missing_fields),
        user_goal_summary=(
            "User selected a pending simplification option while structured "
            "interpretation was unavailable."
        ),
        candidate_strategy_draft=strategy,
        missing_required_fields=missing_fields,
        semantic_turn_act="answer_pending_need",
        reason_codes=[
            "pending_response_option_selected",
            "pending_response_option_interpreter_unavailable_repaired",
        ],
    )


def draft_only_indicator_interpretation_when_interpreter_unavailable(
    *,
    snapshot: TaskSnapshot | None,
    current_user_message: str,
    resolve_asset_candidate: ResolveAssetCandidate,
    default_benchmark_for_asset_class: DefaultBenchmarkForAssetClass,
) -> StructuredInterpretation | None:
    if snapshot is not None:
        return None
    text = current_user_message.strip()
    if not text:
        return None
    indicator = draft_only_indicator_from_text(text)
    if indicator is None:
        return None

    def _resolve_candidate(query: str) -> AssetResolution | None:
        return resolve_asset_candidate(
            query,
            field="asset_universe",
            source="user_mention",
        )

    mentions = provider_ticker_mentions_from_text(
        text,
        resolve_candidate=_resolve_candidate,
        limit=5,
    )
    if not mentions:
        return None
    symbols: list[str] = []
    asset_classes: set[str] = set()
    provenance = []
    for mention in mentions:
        asset = mention.asset
        symbol = str(getattr(asset, "canonical_symbol", "") or "").strip().upper()
        asset_class = str(getattr(asset, "asset_class", "") or "").strip()
        if not symbol or not asset_class:
            continue
        if symbol not in symbols:
            symbols.append(symbol)
        asset_classes.add(asset_class)
        provenance.append(mention.resolution.provenance)
    if not symbols or len(asset_classes) != 1:
        return None
    asset_class = next(iter(asset_classes))
    strategy = StrategySummary(
        raw_user_phrasing=text,
        strategy_thesis=text,
        asset_universe=symbols[:5],
        asset_class=asset_class,
        comparison_baseline=default_benchmark_for_asset_class(
            asset_class,
            symbols=symbols[:5],
        ),
        resolution_provenance=_dedupe_resolution_provenance(provenance),
        extra_parameters={
            "unsupported_indicator": indicator.key,
            "unsupported_indicator_label": indicator.label,
        },
    )
    return StructuredInterpretation(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=(
            "Structured interpretation was unavailable, but the user supplied "
            "a provider-backed asset and a draft-only indicator."
        ),
        candidate_strategy_draft=strategy,
        missing_required_fields=[],
        assistant_response=None,
        semantic_turn_act="new_idea",
        reason_codes=[
            "llm_interpreter_unavailable_draft_only_indicator_recovered",
            "draft_only_indicator_text_preserved",
        ],
    )


async def planned_active_confirmation_edit_interpretation(
    *,
    snapshot: TaskSnapshot,
    current_user_message: str,
    resolve_asset_candidate: ResolveAssetCandidate,
    plan_artifact_assumption_edit_fn: PlanArtifactAssumptionEdit
    | None = None,
) -> StructuredInterpretation | None:
    active_confirmation = snapshot.active_confirmation_reference
    if active_confirmation is None:
        return None
    prior_strategy = active_confirmation_effective_strategy(
        snapshot=snapshot,
        fallback=(
            snapshot.pending_strategy_summary
            or snapshot.confirmed_strategy_summary
            or StrategySummary()
        ),
    )
    if not prior_strategy.asset_universe:
        return None
    planner = plan_artifact_assumption_edit_fn or _plan_artifact_assumption_edit
    plan: ArtifactAssumptionEditPlan | None = await planner(
        current_user_message=current_user_message,
        prior_strategy=prior_strategy.model_dump(mode="json"),
        active_confirmation=active_confirmation.model_dump(mode="json"),
        preferred_model="",
    )
    if plan is None or plan.outcome != "ready_to_confirm":
        return None
    candidate = StrategySummary(raw_user_phrasing=current_user_message)
    field_provenance: dict[str, str] = {}
    if plan.operations:
        apply_resolved_artifact_edit_to_strategy_summary(
            apply_edit_operations(
                plan.operations,
                current_asset_universe=prior_strategy.asset_universe,
                asset_symbol_resolver=asset_edit_symbol_resolver(
                    resolve_asset_candidate
                ),
            ),
            candidate=candidate,
            field_provenance=field_provenance,
            allow_indicator_parameters=strategy_summary_uses_rsi(prior_strategy),
        )
    elif plan.asset_universe:
        operation = normalized_asset_universe_operation(plan.asset_universe_operation)
        if operation is None:
            if not same_asset_universe(
                plan.asset_universe,
                prior_strategy.asset_universe,
            ):
                return None
        else:
            candidate.asset_universe = list(plan.asset_universe)
            candidate.extra_parameters["asset_universe_operation"] = operation
            field_provenance["asset_universe"] = "explicit_user"
    if plan.comparison_baseline is not None:
        baseline = str(plan.comparison_baseline or "").strip().upper()
        if baseline:
            candidate.comparison_baseline = baseline
            field_provenance["comparison_baseline"] = "explicit_user"
    if plan.initial_capital is not None:
        candidate.capital_amount = float(plan.initial_capital)
        field_provenance["capital_amount"] = "starting_capital"
    if plan.timeframe is not None:
        candidate.timeframe = str(plan.timeframe)
        field_provenance["timeframe"] = "explicit_user"
    if not field_provenance:
        return None
    candidate.extra_parameters["field_provenance"] = field_provenance
    return StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=False,
        user_goal_summary=(
            plan.user_goal_summary or "User changed a visible confirmation assumption."
        ),
        candidate_strategy_draft=candidate,
        confidence=plan.confidence,
        reason_codes=["artifact_assumption_edit_planned"],
        semantic_turn_act="answer_pending_need",
        artifact_target="active_confirmation",
    )


def structured_interpretation_has_supported_artifact_assumption_edit(
    interpretation: StructuredInterpretation,
) -> bool:
    if interpretation.semantic_turn_act in {
        "approval",
        "educational_question",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    if interpretation.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    strategy = interpretation.candidate_strategy_draft
    extra_parameters = strategy.extra_parameters or {}
    return bool(strategy.asset_universe) and (
        normalized_asset_universe_operation(
            extra_parameters.get("asset_universe_operation")
        )
        is not None
    )


def structured_interpretation_has_complete_typed_asset_patch(
    interpretation: StructuredInterpretation,
) -> bool:
    strategy = interpretation.candidate_strategy_draft
    if not strategy.asset_universe:
        return False
    extra_parameters = strategy.extra_parameters or {}
    if (
        normalized_asset_universe_operation(
            extra_parameters.get("asset_universe_operation")
        )
        is None
    ):
        return False
    return bool(
        strategy.date_range in (None, {}, "")
        and strategy.capital_amount is None
        and strategy.position_size is None
        and strategy.timeframe in (None, "")
    )


def _pending_response_option_index_from_text(
    text: str,
    *,
    options: list[dict[str, Any]],
) -> int | None:
    user_tokens = _pending_option_selection_tokens(text)
    if not user_tokens:
        return None
    best_index: int | None = None
    best_overlap = 0
    tied = False
    for index, option in enumerate(options):
        option_tokens = _pending_option_selection_tokens(
            " ".join(
                [
                    str(option.get("label") or ""),
                    _pending_option_replacement_selection_terms(
                        option.get("replacement_values")
                    ),
                ]
            )
        )
        overlap = len(user_tokens & option_tokens)
        if overlap < 2:
            continue
        if overlap > best_overlap:
            best_index = index
            best_overlap = overlap
            tied = False
        elif overlap == best_overlap:
            tied = True
    return None if tied else best_index


def _pending_option_replacement_selection_terms(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    terms: list[str] = []
    strategy_type = canonical_strategy_type(value.get("strategy_type"))
    if strategy_type == "buy_and_hold":
        terms.extend(["buy hold", "buy and hold", "compra mantener"])
    elif strategy_type == "indicator_threshold":
        terms.extend(["indicator threshold", "rsi threshold"])
    elif strategy_type == "moving_average_crossover":
        terms.extend(["moving average crossover"])
    for key in ("requested_field", "cadence", "timeframe", "comparison_baseline"):
        if value.get(key) not in (None, "", [], {}):
            terms.append(str(value[key]))
    return " ".join(terms)


def _pending_option_selection_tokens(value: str) -> set[str]:
    normalized = (
        str(value or "")
        .casefold()
        .replace("&", " and ")
        .replace("/", " ")
        .replace("-", " ")
    )
    chars = [char if char.isalnum() else " " for char in normalized]
    aliases = {
        "w": "with",
        "ma": "moving",
        "comprar": "compra",
        "mantén": "mantener",
        "manten": "mantener",
    }
    stopwords = {
        "a",
        "an",
        "and",
        "con",
        "el",
        "la",
        "los",
        "ok",
        "okay",
        "pls",
        "please",
        "porfa",
        "si",
        "sí",
        "the",
        "use",
        "with",
        "yeah",
        "y",
    }
    return {
        token
        for raw_token in "".join(chars).split()
        if (token := aliases.get(raw_token, raw_token)) not in stopwords
    }
