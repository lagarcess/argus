"""Executable-strategy grounding audit helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from datetime import date

from argus.agent_runtime.interpreter.audits import ExecutableStrategyGroundingAudit
from argus.agent_runtime.interpreter.shared import (
    _EXECUTABLE_TIMEFRAMES,
    _llm_value_is_empty,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import canonical_strategy_type


def _response_needs_launch_field_fidelity_repair(
    *,
    response: LLMInterpretationResponse,
) -> bool:
    if response.requires_clarification:
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act in {
        "answer_pending_need",
        "approval",
        "refine_current_idea",
        "retry_failed_action",
        "result_followup",
        "unsupported_request",
    }:
        return False
    if "focused_strategy_extraction_repair" in response.reason_codes:
        return False
    if "stated_run_field_fidelity_audit" in response.reason_codes:
        return False
    draft = response.candidate_strategy_draft
    if not _llm_value_is_empty(draft.timeframe):
        return str(draft.timeframe).strip() in _EXECUTABLE_TIMEFRAMES
    asset_class = str(draft.asset_class or "").strip().lower()
    return asset_class in {"crypto", "currency_pair"} and not _llm_value_is_empty(
        draft.date_range
    )


def _response_needs_executable_strategy_grounding_audit(
    *,
    response: LLMInterpretationResponse,
) -> bool:
    if response.requires_clarification:
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.task_relation != "new_task":
        return False
    if response.semantic_turn_act in {
        "answer_pending_need",
        "approval",
        "refine_current_idea",
        "retry_failed_action",
        "result_followup",
        "unsupported_request",
    }:
        return False
    if "executable_strategy_grounding_audit" in response.reason_codes:
        return False
    if "stated_run_field_fidelity_audit" in response.reason_codes:
        return False
    if _response_needs_launch_field_fidelity_repair(response=response):
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        return False
    return _draft_has_non_executable_timeframe_label(
        draft
    ) or _draft_uses_launch_default_window(draft)


def _draft_has_non_executable_timeframe_label(draft: LLMStrategyDraft) -> bool:
    if _llm_value_is_empty(draft.timeframe):
        return False
    return str(draft.timeframe).strip() not in _EXECUTABLE_TIMEFRAMES


def _draft_uses_launch_default_window(draft: LLMStrategyDraft) -> bool:
    date_range_value = draft.date_range
    if not isinstance(date_range_value, dict):
        return False
    start = str(date_range_value.get("start") or "").strip()
    end = str(date_range_value.get("end") or "").strip()
    return start == "2016-01-01" and end in {"today", date.today().isoformat()}


def _executable_strategy_grounding_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's executable-strategy grounding audit. Decide whether "
                "a runnable draft faithfully represents the current user message before "
                "the product shows a confirmation card. Return grounded only when the "
                "user actually supplied enough meaning for this executable draft. "
                "Return needs_clarification when the draft silently turns a valuation, "
                "fundamental, sentiment, news, vague momentum, or otherwise ambiguous "
                "idea into buy-and-hold, DCA, or another executable strategy without "
                "the user's choice. Valuation language like cheap, undervalued, or P/E "
                "is financially valid context, but Argus needs a supported historical "
                "proxy or explicit baseline before running it. Do not expose provider "
                "plumbing. "
                f"{response_language_instruction(request.user.language_preference)} "
                "Write assistant_response in warm, plain language, with short "
                "sentences and no report tone. Return only JSON matching the schema."
            ),
        },
        {
            "role": "system",
            "content": (
                "Structured draft JSON: "
                f"{response.candidate_strategy_draft.model_dump(mode='json')}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_from_executable_strategy_grounding_audit(
    *,
    response: LLMInterpretationResponse,
    audit: ExecutableStrategyGroundingAudit,
) -> LLMInterpretationResponse | None:
    if audit.outcome == "grounded":
        return None
    if audit.outcome != "needs_clarification" or not audit.assistant_response:
        return None
    repaired = response.model_copy(deep=True)
    repaired.intent = "strategy_drafting"
    repaired.requires_clarification = True
    repaired.assistant_response = audit.assistant_response
    repaired.missing_required_fields = list(
        dict.fromkeys(audit.missing_required_fields or ["entry_logic"])
    )
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *repaired.reason_codes,
                "executable_strategy_grounding_audit",
                "executable_strategy_grounding_needs_clarification",
            ]
        )
    )
    if canonical_strategy_type(
        repaired.candidate_strategy_draft.strategy_type
    ) in {"buy_and_hold", "dca_accumulation"}:
        repaired.candidate_strategy_draft.strategy_type = None
    return repaired
