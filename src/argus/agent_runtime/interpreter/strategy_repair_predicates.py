"""Strategy-repair predicates: vague-start detection, execution anchors, and structured-repair gating.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from argus.agent_runtime.interpreter.draft_shape import (
    _llm_strategy_draft_has_structural_execution_fields,
    _llm_strategy_draft_has_structured_rule_or_indicator_fields,
    _llm_strategy_draft_has_unstructured_strategy_text,
)
from argus.agent_runtime.interpreter.shared import (
    _llm_strategy_draft_has_extractable_fields,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.strategy_contract import canonical_strategy_type


def _response_needs_artifact_context_repair(
    response: LLMInterpretationResponse,
) -> bool:
    if response.unsupported_constraints:
        return False
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_structural_execution_fields(draft):
        return False
    if response.intent == "unsupported_or_out_of_scope":
        return bool(response.assistant_response)
    return (
        response.intent == "conversation_followup"
        and response.semantic_turn_act == "educational_question"
        and bool(response.assistant_response)
        and _llm_strategy_draft_has_unstructured_strategy_text(draft)
    )


def _supported_partial_draft_has_repairable_shape(draft: LLMStrategyDraft) -> bool:
    return any(
        [
            bool(draft.asset_universe),
            bool(draft.asset_class),
            bool(draft.timeframe),
            bool(draft.cadence),
            bool(draft.date_range),
            bool(draft.date_range_raw_text),
            bool(draft.comparison_baseline),
            draft.capital_amount is not None,
            draft.total_capital is not None,
            draft.initial_capital is not None,
            draft.recurring_contribution is not None,
            bool(draft.evidence_spans),
            bool(draft.field_provenance),
            bool(draft.extra_parameters),
        ]
    )


def _vague_strategy_start_as_guidance(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    if not _is_vague_strategy_start(response):
        return response
    return response.model_copy(
        update={
            "intent": "beginner_guidance",
            "requires_clarification": True,
            "missing_required_fields": [],
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "vague_strategy_start_guidance",
                    ]
                )
            ),
        }
    )


def _is_vague_strategy_start_guidance(response: LLMInterpretationResponse) -> bool:
    return "vague_strategy_start_guidance" in response.reason_codes


def _is_vague_strategy_start(response: LLMInterpretationResponse) -> bool:
    if response.intent != "strategy_drafting":
        return False
    if response.capability_question_focus is not None:
        return False
    if response.semantic_turn_act not in {None, "new_idea"}:
        return False
    if response.unsupported_constraints or response.ambiguous_fields:
        return False
    draft = response.candidate_strategy_draft
    return not _llm_strategy_draft_has_semantic_execution_anchor(draft)


def _response_needs_structured_strategy_repair(
    *,
    response: LLMInterpretationResponse,
) -> bool:
    if not response.requires_clarification:
        return False
    if response.intent not in {
        "strategy_drafting",
        "backtest_execution",
        "unsupported_or_out_of_scope",
    }:
        return False
    if response.semantic_turn_act in {
        "answer_pending_need",
        "approval",
        "refine_current_idea",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if response.unsupported_constraints:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type):
        return False
    if _llm_strategy_draft_has_structured_rule_or_indicator_fields(draft):
        return False
    if not _llm_strategy_draft_has_extractable_fields(draft):
        return False
    return bool(draft.raw_user_phrasing or draft.strategy_thesis)


def _llm_strategy_draft_has_semantic_execution_anchor(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(draft.strategy_type),
            bool(draft.asset_universe),
            bool(draft.asset_class),
            bool(draft.timeframe),
            bool(draft.cadence),
            bool(draft.entry_logic),
            bool(draft.exit_logic),
            bool(draft.entry_rule),
            bool(draft.exit_rule),
            bool(draft.rule_spec),
            bool(draft.indicator),
            draft.indicator_period is not None,
            draft.entry_threshold is not None,
            draft.exit_threshold is not None,
            bool(draft.date_range),
            bool(draft.risk_rules),
            bool(draft.extra_parameters),
        ]
    )
