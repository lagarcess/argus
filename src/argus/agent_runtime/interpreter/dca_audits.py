"""DCA contract, family-continuity, and contribution-role audit helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.interpreter.audits import DcaContractAudit
from argus.agent_runtime.interpreter.shared import (
    _TOTAL_CAPITAL_SOURCES,
    _capital_source,
    _date_range_from_intent_or_bounded_evidence,
    _field_path_base,
    _llm_value_is_empty,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    executable_strategy_type,
    has_partial_explicit_date_range,
)


def _response_needs_strategy_family_continuity_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if response.capability_question_focus is not None:
        return False
    if response.artifact_target == "latest_result":
        return False
    if response.semantic_turn_act in {
        "approval",
        "refine_current_idea",
        "result_followup",
        "retry_failed_action",
        "unsupported_request",
    }:
        return False
    if response.task_relation == "refine":
        return False
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if not request.recent_thread_history:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        return False
    return bool(
        draft.asset_universe
        or draft.date_range
        or draft.capital_amount is not None
        or draft.total_capital is not None
        or draft.initial_capital is not None
    )


def _response_from_dca_contract_audit(
    *,
    response: LLMInterpretationResponse,
    audit: Any,
) -> LLMInterpretationResponse | None:
    if (
        not isinstance(audit, DcaContractAudit)
        or not audit.is_recurring_buy_request
        or audit.confidence < 0.7
    ):
        return None
    cadence = _supported_dca_cadence_value(audit.cadence)
    recurring_amount = audit.recurring_contribution_amount
    if cadence is None or recurring_amount is None or recurring_amount <= 0:
        return None

    draft = response.candidate_strategy_draft.model_copy(deep=True)
    draft.strategy_type = "dca_accumulation"
    draft.capital_amount = float(recurring_amount)
    draft.recurring_contribution = float(recurring_amount)
    draft.cadence = cadence
    draft.sizing_mode = "capital_amount"

    field_provenance = dict(draft.field_provenance or {})
    field_provenance["capital_amount"] = "recurring_contribution"
    field_provenance["recurring_contribution"] = "recurring_contribution"

    extra_parameters = dict(draft.extra_parameters or {})
    extra_parameters["recurring_contribution"] = float(recurring_amount)
    extra_parameters["recurring_cadence"] = cadence

    if audit.total_budget_amount is not None and audit.total_budget_amount > 0:
        budget_source = _dca_total_budget_source(audit.total_budget_source)
        draft.total_capital = float(audit.total_budget_amount)
        field_provenance["total_capital"] = budget_source
        extra_parameters["total_budget"] = float(audit.total_budget_amount)

    draft.field_provenance = field_provenance
    draft.extra_parameters = extra_parameters

    missing_required_fields = _dca_contract_missing_fields(
        response.missing_required_fields,
        draft=draft,
    )
    return response.model_copy(
        update={
            "intent": "strategy_drafting"
            if missing_required_fields
            else "backtest_execution",
            "task_relation": "new_task",
            "requires_clarification": bool(missing_required_fields),
            "candidate_strategy_draft": draft,
            "missing_required_fields": missing_required_fields,
            "assistant_response": None,
            "semantic_turn_act": "new_idea",
            "capability_question_focus": None,
            "artifact_target": "none",
            "unsupported_constraints": [],
            "reason_codes": list(
                dict.fromkeys([*response.reason_codes, "dca_contract_audit"])
            ),
        }
    )


def _dca_contract_missing_fields(
    current_missing: list[str],
    *,
    draft: LLMStrategyDraft,
) -> list[str]:
    stale_rule_fields = {"entry_logic", "exit_logic", "strategy_type"}
    missing = [
        field
        for field in current_missing
        if _field_path_base(field) not in stale_rule_fields
    ]
    if _llm_value_is_empty(draft.date_range) or has_partial_explicit_date_range(
        draft.date_range
    ):
        resolved_date_range = _date_range_from_intent_or_bounded_evidence(draft)
        if resolved_date_range is not None:
            draft.date_range = resolved_date_range
    present_fields: set[str] = set()
    if draft.asset_universe:
        present_fields.add("asset_universe")
    if draft.date_range not in (None, "", [], {}):
        present_fields.add("date_range")
    if _dca_draft_has_recurring_amount(draft):
        present_fields.add("capital_amount")
    if draft.cadence not in (None, "", [], {}):
        present_fields.add("cadence")
    required_fields = ["asset_universe", "date_range", "capital_amount", "cadence"]
    missing = list(dict.fromkeys([*missing, *required_fields]))
    return [
        field
        for field in missing
        if _field_path_base(field) not in present_fields
    ]


def _capability_required_missing_fields_for_canonical_strategy(
    current_missing: list[str],
    *,
    draft: LLMStrategyDraft,
) -> list[str]:
    strategy_type = executable_strategy_type(draft.model_dump(mode="python"))
    if strategy_type == "buy_and_hold":
        if _llm_value_is_empty(draft.date_range) or has_partial_explicit_date_range(
            draft.date_range
        ):
            resolved_date_range = _date_range_from_intent_or_bounded_evidence(draft)
            if resolved_date_range is not None:
                draft.date_range = resolved_date_range
        missing: list[str] = []
        if not draft.asset_universe:
            missing.append("asset_universe")
        if _llm_value_is_empty(draft.date_range) or has_partial_explicit_date_range(
            draft.date_range
        ):
            missing.append("date_range")
        return missing
    if strategy_type == "dca_accumulation":
        return _dca_contract_missing_fields(current_missing, draft=draft)
    return list(current_missing)


def _dca_draft_has_recurring_amount(draft: LLMStrategyDraft) -> bool:
    if draft.recurring_contribution is not None:
        return True
    if draft.capital_amount is None:
        return False
    return _capital_source(draft.field_provenance, "capital_amount") in {
        "recurring_contribution",
        "explicit_recurring_contribution",
    }


def _dca_total_budget_source(value: Any) -> str:
    source = str(value or "").strip().casefold()
    if source in _TOTAL_CAPITAL_SOURCES:
        return source
    return "total_budget"


def _dca_contract_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's DCA contract audit. The primary interpreter may "
                "have misclassified a supported recurring-buy request as unsupported "
                "or may have mixed up recurring contribution and total budget/cap. "
                "Use semantic meaning, not keywords. Return true only when the "
                "current user message asks for a fixed contribution on a recurring "
                "cadence. The per-purchase amount belongs in "
                "recurring_contribution_amount. A total budget, starting principal, "
                "or cap belongs in total_budget_amount and must not replace the "
                "recurring contribution. Do not infer missing contribution or "
                "cadence. Provider and capability validation will run after this "
                "audit; return only JSON matching the schema."
            ),
        },
        {
            "role": "system",
            "content": (
                "Current structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_needs_dca_contribution_role_audit(
    response: LLMInterpretationResponse,
) -> bool:
    if "pending_response_option_selected" in response.reason_codes:
        return False
    draft = response.candidate_strategy_draft
    return (
        canonical_strategy_type(draft.strategy_type) == "dca_accumulation"
        and draft.capital_amount is not None
        and response.semantic_turn_act not in {
            "approval",
            "result_followup",
            "retry_failed_action",
        }
    )


def _dca_contribution_role_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's DCA money-role audit. Decide whether the money "
                "amount in the current user message is the recurring contribution "
                "for each DCA purchase, or a total budget/capital amount for the "
                "whole plan. Use semantic meaning, not keywords. A recurring "
                "contribution is explicit only when the user clearly ties the amount "
                "to each recurring purchase. If the amount is merely available "
                "capital, a budget, a starting principal, or an amount spread over "
                "the date range, mark total_budget_not_recurring true. If ambiguous, "
                "do not treat it as a recurring contribution."
            ),
        },
        {
            "role": "system",
            "content": (
                "Current structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _strategy_family_continuity_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    recent_history = [
        item.model_dump(mode="json")
        for item in request.recent_thread_history[-6:]
        if hasattr(item, "role") and hasattr(item, "content")
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's strategy-family continuity audit. Decide whether "
                "the current user message is answering a visible recent setup offer "
                "for a specific executable strategy family, and whether the primary "
                "interpretation chose the wrong family. Use semantic meaning from "
                "the recent visible conversation, not keywords. Do not infer from "
                "hidden state. Return false when the user is starting a standalone "
                "idea, explicitly asked for buy-and-hold, switched to another "
                "strategy, asked a capability question, or is talking about a result. "
                "If a prior assistant turn offered a recurring-buy/DCA setup and "
                "the current user supplies asset, date, or budget facts to continue "
                "that setup, return dca_accumulation. For DCA, mark "
                "total_budget_not_recurring true when the stated money is a total "
                "budget, starting principal, or cap instead of a per-purchase "
                "recurring contribution."
            ),
        },
        {
            "role": "system",
            "content": f"Recent visible conversation: {recent_history}",
        },
        {
            "role": "system",
            "content": (
                "Primary structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _move_dca_total_budget_out_of_recurring_amount(
    draft: LLMStrategyDraft,
) -> None:
    if draft.capital_amount is None:
        return
    total_budget = draft.total_capital or draft.initial_capital or draft.capital_amount
    draft.total_capital = total_budget
    draft.capital_amount = None
    draft.sizing_mode = None
    field_provenance = dict(draft.field_provenance or {})
    field_provenance.pop("capital_amount", None)
    field_provenance["total_capital"] = "total_budget"
    draft.field_provenance = field_provenance
    extra_parameters = dict(draft.extra_parameters or {})
    extra_parameters["total_budget"] = total_budget
    draft.extra_parameters = extra_parameters
