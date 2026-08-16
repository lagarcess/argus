"""Asset-universe-operation clarification and runtime-readiness logging helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from argus.agent_runtime.artifacts.asset_edits import normalized_asset_universe_operation
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _current_artifact_strategy,
    _normalized_ticker_symbol,
)
from argus.agent_runtime.interpreter.shared import (
    _llm_value_is_empty,
    _selected_requested_field_base,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.presentation_i18n import (
    asset_universe_operation_clarification_message,
)
from argus.agent_runtime.stages.artifact_context import (
    active_confirmation_effective_strategy,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import canonical_strategy_type


def _active_artifact_asset_universe_operation_needs_planner(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    draft = response.candidate_strategy_draft
    if not draft.asset_universe:
        return False
    snapshot = request.latest_task_snapshot
    has_active_confirmation = (
        snapshot is not None and snapshot.active_confirmation_reference is not None
    )
    if (
        not has_active_confirmation
        and normalized_asset_universe_operation(draft.asset_universe_operation)
        is not None
    ):
        return False
    prior = (
        snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
        if snapshot is not None
        else None
    )
    if snapshot is not None and snapshot.active_confirmation_reference is not None:
        prior = active_confirmation_effective_strategy(
            snapshot=snapshot,
            fallback=prior or StrategySummary(),
        )
    if prior is None:
        return False
    candidate_symbols = {
        symbol
        for value in draft.asset_universe
        if (symbol := _normalized_ticker_symbol(value)) is not None
    }
    prior_symbols = {
        symbol
        for value in prior.asset_universe
        if (symbol := _normalized_ticker_symbol(value)) is not None
    }
    return bool(candidate_symbols and candidate_symbols != prior_symbols)


def _asset_universe_operation_clarification_response(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMInterpretationResponse:
    clarification_draft = _asset_universe_operation_clarification_draft(
        response=response,
        request=request,
    )
    return response.model_copy(
        update={
            "intent": "conversation_followup",
            "task_relation": "continue",
            "requires_clarification": True,
            "assistant_response": asset_universe_operation_clarification_message(
                language=request.user.language_preference
            ),
            "candidate_strategy_draft": clarification_draft,
            "missing_required_fields": [],
            "ambiguous_fields": [],
            "unsupported_constraints": [],
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "asset_universe_operation_needs_clarification",
                    ]
                )
            ),
            "semantic_turn_act": "answer_pending_need",
        }
    )


def _asset_universe_operation_clarification_draft(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMStrategyDraft:
    """Keep proven non-asset edits while asking how to apply ambiguous assets."""

    clarification = LLMStrategyDraft(raw_user_phrasing=request.current_user_message)
    primary = response.candidate_strategy_draft
    current = _current_artifact_strategy(request)
    if (
        primary.position_size is not None
        and primary.field_provenance.get("position_size") == "explicit_user"
        and primary.position_size != getattr(current, "position_size", None)
    ):
        clarification.sizing_mode = "position_size"
        clarification.position_size = primary.position_size
        clarification.field_provenance = {"position_size": "explicit_user"}
        position_evidence = primary.evidence_spans.get("position_size")
        if position_evidence:
            clarification.evidence_spans = {"position_size": position_evidence}
    return clarification


# The only acts whose bare answers this guard may rewrite: the ones the
# downstream routes are verified to serve (the provider-resolution append
# corridor for answer_pending_need, the planner's stated-operation union for
# refine_current_idea). A tenth act fails closed, not open.
_BARE_ANSWER_ELIGIBLE_ACTS = frozenset({"answer_pending_need", "refine_current_idea"})


def _bare_asset_answer_without_unevidenced_operation(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    resolve_asset_candidate: Callable[..., Any],
) -> LLMInterpretationResponse:
    """Type a bare asset answer to the asset slot as that asset's inclusion (#190).

    When the whole reply resolves as one asset, the turn carried no words that
    could express an operation, so a guessed "replace" label (which would wipe
    a multi-asset card) and an empty universe (which would trigger a second
    add-or-replace question) are both unevidenced shapes of the same answer.
    The product rule is append. Routing after the rewrite: an
    answer_pending_need continue turn takes the deterministic
    provider-resolution append corridor; a refine_current_idea turn reaches
    the edit planner, whose stated-operation union injects the typed
    inclusion as an add. A model-labelled "append" is already the product
    rule and is deliberately left untouched.
    """
    draft = response.candidate_strategy_draft
    if _selected_requested_field_base(request) != "asset_universe":
        return response
    if response.semantic_turn_act not in _BARE_ANSWER_ELIGIBLE_ACTS:
        return response
    if response.asset_discovery is not None:
        return response
    if draft.asset_exclusions:
        return response
    operation_label = normalized_asset_universe_operation(draft.asset_universe_operation)
    if operation_label != "replace" and draft.asset_universe:
        # Only a wipe-shaped guess or a truly bare draft needs the rewrite;
        # append and unlabeled non-empty shapes already route correctly.
        return response
    prior = _current_artifact_strategy(request)
    prior_symbols = {
        symbol
        for value in (prior.asset_universe if prior is not None else [])
        if (symbol := _normalized_ticker_symbol(value)) is not None
    }
    if len(prior_symbols) <= 1:
        return response
    answer = request.current_user_message.strip()
    if not answer:
        return response
    try:
        resolution = resolve_asset_candidate(
            answer,
            field="asset_universe[0]",
            source="user_mention",
        )
    except ValueError:
        return response
    if (
        resolution is None
        or getattr(resolution, "status", None) != "resolved"
        or resolution.asset is None
    ):
        return response
    symbol = resolution.asset.canonical_symbol
    if symbol in prior_symbols:
        return response
    draft_symbols = {
        draft_symbol
        for value in draft.asset_universe
        if (draft_symbol := _normalized_ticker_symbol(value)) is not None
    }
    if draft_symbols - {symbol}:
        return response
    # An inclusion role naming exactly the answered symbol is the same bare
    # shape; anything beyond it means the turn stated more than the mention.
    inclusion_symbols = {
        inclusion_symbol
        for value in draft.asset_inclusions
        if (inclusion_symbol := _normalized_ticker_symbol(value)) is not None
    }
    if inclusion_symbols - {symbol}:
        return response
    field_provenance = dict(draft.field_provenance or {})
    field_provenance["asset_inclusions"] = "explicit_user"
    field_provenance.pop("asset_universe_operation", None)
    updated_draft = draft.model_copy(
        update={
            "asset_universe": [symbol],
            "asset_inclusions": [symbol],
            "asset_universe_operation": None,
            "field_provenance": field_provenance,
        }
    )
    logger.info(
        "Bare asset answer typed as inclusion symbol={}",
        symbol,
        symbol=symbol,
    )
    return response.model_copy(
        update={
            "candidate_strategy_draft": updated_draft,
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "bare_asset_answer_typed_as_inclusion",
                    ]
                )
            ),
        }
    )


def _plain_requested_asset_answer_can_use_provider_resolution(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    draft_has_valid_requested_asset_update: Callable[
        [LLMStrategyDraft, InterpretationRequest], bool
    ],
) -> bool:
    draft = response.candidate_strategy_draft
    return bool(
        _selected_requested_field_base(request) == "asset_universe"
        and response.semantic_turn_act == "answer_pending_need"
        and response.task_relation == "continue"
        and normalized_asset_universe_operation(draft.asset_universe_operation) is None
        and draft_has_valid_requested_asset_update(draft, request)
    )


def _log_runtime_readiness_step(
    step: str,
    *,
    response: LLMInterpretationResponse,
) -> None:
    draft = response.candidate_strategy_draft
    logger.debug(
        "Structured interpreter runtime readiness step={} intent={} "
        "semantic_turn_act={} strategy_type={} requires_clarification={} "
        "has_date_range={} has_date_range_intent={} has_date_range_raw_text={} "
        "missing_required_fields={} ambiguous_field_count={} "
        "unsupported_constraint_count={} reason_codes={}",
        step,
        response.intent,
        response.semantic_turn_act,
        canonical_strategy_type(draft.strategy_type),
        response.requires_clarification,
        not _llm_value_is_empty(draft.date_range),
        draft.date_range_intent is not None,
        not _llm_value_is_empty(draft.date_range_raw_text),
        list(response.missing_required_fields),
        len(response.ambiguous_fields),
        len(response.unsupported_constraints),
        list(response.reason_codes),
        step=step,
        intent=response.intent,
        task_relation=response.task_relation,
        semantic_turn_act=response.semantic_turn_act,
        requires_clarification=response.requires_clarification,
        strategy_type=canonical_strategy_type(draft.strategy_type),
        has_date_range=not _llm_value_is_empty(draft.date_range),
        has_date_range_intent=draft.date_range_intent is not None,
        has_date_range_raw_text=not _llm_value_is_empty(draft.date_range_raw_text),
        missing_required_fields=list(response.missing_required_fields),
        ambiguous_field_count=len(response.ambiguous_fields),
        unsupported_constraint_count=len(response.unsupported_constraints),
        reason_codes=list(response.reason_codes),
    )
