"""Capability/context Q&A audit helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from argus.agent_runtime.interpreter.run_field_audits import (
    _response_targets_latest_result_followup,
)
from argus.agent_runtime.interpreter.shared import (
    _field_path_base,
    _llm_strategy_draft_has_concrete_execution_target,
)
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.agent_runtime.stages.interpret_types import InterpretationRequest


def _response_had_unsubstantiated_asset_removed(
    response: LLMInterpretationResponse,
) -> bool:
    return any(
        reason_code.startswith("asset_grounding_audit_")
        and (
            "removed_unsubstantiated" in reason_code
            or "cleared_suspicious" in reason_code
        )
        for reason_code in response.reason_codes
    )


def _capability_side_question_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    pending_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).strip()
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's runtime arbitration audit. Decide whether the "
                "current user message is a capability or education side-question, "
                "even if the previous turn asked for a missing field. Use semantic "
                "meaning, not keywords. A capability side-question asks what Argus "
                "supports, what it can run, what supported concepts mean, what assets "
                "or indicators are available, or what limits apply. Return false for "
                "messages that supply assets, dates, sizing, cadence, rule details, "
                "approvals, result follow-ups, market-news/feed requests, or provider "
                "data requests. Choose one focus value only when true: "
                "supported_indicators, supported_strategies, limits, assets, or general."
            ),
        },
        {
            "role": "system",
            "content": (
                "Current structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {
            "role": "system",
            "content": f"Pending requested field, if any: {pending_field or 'none'}",
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_needs_context_question_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.context_question_focus is not None:
        return False
    if response.capability_question_focus not in {
        None,
        "general",
        "limits",
        "supported_strategies",
    }:
        return False
    if response.semantic_turn_act in {
        "approval",
        "retry_failed_action",
        "result_followup",
    }:
        return False
    if _llm_strategy_draft_has_concrete_execution_target(
        response.candidate_strategy_draft
    ):
        return False
    pending_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).strip()
    if _field_path_base(pending_field) == "refinement":
        return False
    if _response_targets_latest_result_followup(response=response, request=request):
        return False
    if (
        response.intent == "strategy_drafting"
        and response.semantic_turn_act == "unsupported_request"
        and response.requires_clarification
        and not response.missing_required_fields
    ):
        return True
    return (
        response.intent == "conversation_followup"
        and response.semantic_turn_act == "educational_question"
    )


def _context_question_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    pending_field = str(
        request.selected_thread_metadata.get("requested_field") or ""
    ).strip()
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's runtime arbitration audit. Decide whether the "
                "current user message is standalone market or macro context "
                "curiosity that should be answered as bounded context and connected "
                "to a historical experiment. Use semantic meaning, not keywords. "
                "Return true for macro backdrop, inflation/rates/Fed/recession, "
                "corporate events such as splits/dividends/earnings context, or "
                "movers/most-active/unusual-move curiosity. Return false when the "
                "user supplies executable strategy details, answers a pending field, "
                "asks what Argus supports, approves a run, or targets a visible "
                "result. Choose one focus only when true: macro_context, "
                "corporate_events, or market_movers."
            ),
        },
        {
            "role": "system",
            "content": (
                "Current structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {
            "role": "system",
            "content": f"Pending requested field, if any: {pending_field or 'none'}",
        },
        {"role": "user", "content": request.current_user_message},
    ]
