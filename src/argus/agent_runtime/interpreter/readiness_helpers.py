"""Asset-universe-operation clarification and runtime-readiness logging helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from loguru import logger

from argus.agent_runtime.artifacts.asset_edits import normalized_asset_universe_operation
from argus.agent_runtime.interpreter.artifact_assumption_edit import (
    _normalized_ticker_symbol,
)
from argus.agent_runtime.interpreter.shared import _llm_value_is_empty
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.presentation_i18n import (
    asset_universe_operation_clarification_message,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import canonical_strategy_type


def _active_artifact_asset_universe_operation_needs_planner(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    draft = response.candidate_strategy_draft
    if not draft.asset_universe:
        return False
    if normalized_asset_universe_operation(draft.asset_universe_operation) is not None:
        return False
    snapshot = request.latest_task_snapshot
    prior = (
        snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
        if snapshot is not None
        else None
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
    return response.model_copy(
        update={
            "intent": "conversation_followup",
            "task_relation": "continue",
            "requires_clarification": True,
            "assistant_response": asset_universe_operation_clarification_message(
                language=request.user.language_preference
            ),
            "candidate_strategy_draft": LLMStrategyDraft(
                raw_user_phrasing=request.current_user_message
            ),
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
