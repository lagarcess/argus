"""Signal-rule recovery, planning, and grounding helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.interpreter.shared import (
    _field_path_base,
    _llm_strategy_draft_has_extractable_fields,
    _llm_strategy_draft_has_rule_or_indicator_fields,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMSimplificationOption,
    LLMStrategyDraft,
    LLMUnsupportedConstraint,
)
from argus.agent_runtime.signal_rule_repair import (
    SignalRuleGroundingAudit,
    SignalRulePlan,
    audit_signal_rule_grounding,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import canonical_strategy_type
from argus.domain.backtesting.rules import canonicalize_rule_spec
from argus.domain.indicators import executable_indicator_spec


def _response_needs_supported_signal_rule_recovery(
    response: LLMInterpretationResponse,
    *,
    current_user_message: str,
) -> bool:
    del current_user_message
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) == "signal_strategy":
        return False
    if draft.rule_spec or draft.entry_rule:
        return False
    if not (draft.raw_user_phrasing or draft.strategy_thesis):
        return False
    if not _response_has_signal_rule_shape(response):
        return False
    if response.intent == "unsupported_or_out_of_scope":
        return True
    if response.requires_clarification and response.assistant_response:
        return True
    return any(
        item.category == "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    )


def _response_has_signal_rule_shape(response: LLMInterpretationResponse) -> bool:
    if any(
        item.category == "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    ):
        return True
    return any(
        _field_path_base(field) in {"entry_logic", "exit_logic", "rule_spec"}
        for field in response.missing_required_fields
    ) or any(
        _field_path_base(field.field_name)
        in {"entry_logic", "exit_logic", "rule_spec"}
        for field in response.ambiguous_fields
    )


def _supported_signal_rule_planning_response(
    response: LLMInterpretationResponse,
) -> LLMInterpretationResponse:
    planning = response.model_copy(deep=True)
    planning.intent = "strategy_drafting"
    planning.requires_clarification = True
    planning.assistant_response = None
    planning.missing_required_fields = ["entry_logic", "exit_logic"]
    planning.unsupported_constraints = []
    planning.candidate_strategy_draft.strategy_type = "signal_strategy"
    planning.reason_codes = list(
        dict.fromkeys(
            [
                *planning.reason_codes,
                "supported_signal_rule_contract_recovery",
            ]
        )
    )
    return planning


def _asset_recovery_query_is_explicit_ticker(query: str) -> bool:
    candidate = str(query or "").strip().lstrip("$")
    if not candidate:
        return False
    compact = "".join(
        character
        for character in candidate
        if character.isalnum()
    )
    return (
        len(compact) >= 2
        and any(character.isalpha() for character in compact)
        and candidate == candidate.upper()
    )


def _llm_strategy_draft_has_non_asset_strategy_anchor(
    draft: LLMStrategyDraft,
) -> bool:
    return any(
        [
            bool(canonical_strategy_type(draft.strategy_type)),
            bool(draft.cadence),
            _llm_strategy_draft_has_rule_or_indicator_fields(draft),
        ]
    )


def _request_targets_pending_signal_rule(request: InterpretationRequest) -> bool:
    requested_field = _field_path_base(
        request.selected_thread_metadata.get("requested_field")
    )
    return requested_field in {"entry_logic", "exit_logic", "entry_rule", "exit_rule"}


def _pending_signal_rule_planning_response(
    *,
    response: LLMInterpretationResponse,
    prior_strategy: dict[str, Any],
    current_user_message: str,
) -> LLMInterpretationResponse:
    repaired = response.model_copy(deep=True)
    payload = _signal_rule_planning_context_from_prior(prior_strategy)
    incoming = response.candidate_strategy_draft.model_dump(mode="json")
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        payload[key] = value
    payload["raw_user_phrasing"] = current_user_message
    repaired.candidate_strategy_draft = LLMStrategyDraft.model_validate(payload)
    return repaired


def _signal_rule_planning_context_from_prior(
    prior_strategy: dict[str, Any],
) -> dict[str, Any]:
    context_fields = {
        "strategy_type",
        "asset_universe",
        "asset_class",
        "timeframe",
        "date_range",
        "sizing_mode",
        "capital_amount",
        "position_size",
        "assumptions",
        "comparison_baseline",
        "refinement_of",
        "resolution_provenance",
    }
    return {
        key: value
        for key, value in prior_strategy.items()
        if key in context_fields and value not in (None, "", [], {})
    }


async def _audit_signal_rule_grounding_if_needed(
    *,
    response: LLMInterpretationResponse,
    preferred_model: str,
    request: InterpretationRequest,
) -> LLMInterpretationResponse | None:
    if not _response_needs_signal_rule_grounding_audit(response):
        return None
    audit = await audit_signal_rule_grounding(
        current_user_message=request.current_user_message,
        candidate_strategy=response.candidate_strategy_draft.model_dump(mode="json"),
        prior_strategy=_prior_strategy_payload(request),
        preferred_model=preferred_model,
    )
    if audit is None or audit.outcome == "grounded":
        return None
    return _response_from_signal_grounding_audit(
        response=response,
        audit=audit,
    )


def _response_needs_signal_rule_grounding_audit(
    response: LLMInterpretationResponse,
) -> bool:
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) != "signal_strategy":
        return False
    return bool(draft.rule_spec or draft.entry_rule)


def _response_from_signal_grounding_audit(
    *,
    response: LLMInterpretationResponse,
    audit: SignalRuleGroundingAudit,
) -> LLMInterpretationResponse:
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    draft.entry_logic = None
    draft.exit_logic = None
    draft.entry_rule = None
    draft.exit_rule = None
    draft.rule_spec = None
    for key in ("entry_rule", "exit_rule", "rule_spec"):
        draft.extra_parameters.pop(key, None)

    repaired.intent = "strategy_drafting"
    repaired.requires_clarification = True
    repaired.assistant_response = audit.assistant_response
    repaired.missing_required_fields = list(
        dict.fromkeys(audit.missing_required_fields or ["entry_logic"])
    )
    repaired.confidence = min(repaired.confidence, audit.confidence)
    repaired.reason_codes = list(
        dict.fromkeys(
            [*repaired.reason_codes, "signal_rule_grounding_needs_clarification"]
        )
    )
    return repaired


def _response_needs_signal_rule_plan(response: LLMInterpretationResponse) -> bool:
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) != "signal_strategy":
        return False
    if draft.rule_spec or draft.entry_rule:
        return False
    return _llm_strategy_draft_has_extractable_fields(draft)


def _response_needs_indicator_parameter_repair(
    response: LLMInterpretationResponse,
) -> bool:
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    draft = response.candidate_strategy_draft
    indicator_spec = _llm_draft_executable_indicator_spec(draft)
    if indicator_spec is None:
        return False
    if not _llm_strategy_draft_has_extractable_fields(draft):
        return False
    missing_executable_parameter = any(
        [
            draft.indicator is None and indicator_spec is None,
            draft.entry_threshold is None,
            draft.exit_threshold is None,
        ]
    )
    return missing_executable_parameter


def _response_needs_indicator_default_grounding_repair(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    del request
    if response.intent not in {"strategy_drafting", "backtest_execution"}:
        return False
    if response.semantic_turn_act in {
        "approval",
        "result_followup",
        "retry_failed_action",
    }:
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) != "indicator_threshold":
        return False
    indicator_spec = _llm_draft_executable_indicator_spec(draft)
    if indicator_spec is None:
        return False
    default_like_fields = [
        draft.indicator_period == indicator_spec.default_period,
        draft.entry_threshold == indicator_spec.default_entry_threshold,
        draft.exit_threshold == indicator_spec.default_exit_threshold,
    ]
    return any(default_like_fields)


def _llm_draft_executable_indicator_spec(
    draft: LLMStrategyDraft,
):
    for candidate in (
        draft.indicator,
        draft.strategy_type,
        draft.extra_parameters.get("raw_strategy_type"),
        draft.extra_parameters.get("indicator"),
    ):
        spec = executable_indicator_spec(candidate)
        if spec is not None:
            return spec
    return None


def _response_from_signal_rule_plan(
    *,
    response: LLMInterpretationResponse,
    plan: SignalRulePlan,
) -> LLMInterpretationResponse:
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    if plan.user_goal_summary:
        repaired.user_goal_summary = plan.user_goal_summary
    if plan.strategy_thesis:
        draft.strategy_thesis = plan.strategy_thesis
    if plan.asset_universe:
        draft.asset_universe = [
            str(value).strip()
            for value in plan.asset_universe[:5]
            if str(value or "").strip()
        ]
    if plan.asset_class:
        draft.asset_class = str(plan.asset_class).strip().lower() or None
    if plan.entry_logic:
        draft.entry_logic = plan.entry_logic
    if plan.exit_logic:
        draft.exit_logic = plan.exit_logic
    if plan.rule_spec is not None:
        draft.rule_spec = canonicalize_rule_spec(plan.rule_spec)

    repaired.confidence = min(repaired.confidence, plan.confidence)
    repaired.reason_codes = list(
        dict.fromkeys([*repaired.reason_codes, "signal_rule_plan_repair"])
    )
    if plan.outcome == "draft_only":
        draft.strategy_type = None
        draft.entry_rule = None
        draft.exit_rule = None
        draft.rule_spec = None
        draft.risk_rules = []
        repaired.intent = "unsupported_or_out_of_scope"
        repaired.semantic_turn_act = "unsupported_request"
        repaired.requires_clarification = True
        repaired.assistant_response = plan.assistant_response
        repaired.missing_required_fields = []
        repaired.unsupported_constraints = [
            *repaired.unsupported_constraints,
            LLMUnsupportedConstraint(
                category="unsupported_strategy_logic",
                raw_value=_signal_rule_plan_raw_value(draft),
                explanation=(
                    plan.assistant_response
                    or "This idea depends on strategy logic that is not executable yet."
                ),
                simplification_options=[
                    LLMSimplificationOption(
                        label="Use a supported RSI threshold rule",
                        replacement_values={"simplify_logic": "rsi_only"},
                    ),
                    LLMSimplificationOption(
                        label="Compare with buy and hold",
                        replacement_values={"strategy_type": "buy_and_hold"},
                    ),
                    LLMSimplificationOption(
                        label="Use a supported moving-average crossover",
                        replacement_values={
                            "strategy_type": "signal_strategy",
                            "rule_family": "moving_average_crossover",
                        },
                    ),
                ],
            ),
        ]
        repaired.reason_codes = list(
            dict.fromkeys([*repaired.reason_codes, "signal_rule_plan_draft_only"])
        )
        return repaired

    draft.strategy_type = "signal_strategy"
    if plan.outcome == "ready_to_confirm":
        # A ready signal-rule plan is the executable contract. Drop unrelated
        # non-executable draft fields that the planner did not ground in the rule.
        draft.risk_rules = []
        repaired.intent = "backtest_execution"
        repaired.requires_clarification = False
        repaired.missing_required_fields = []
        repaired.assistant_response = None
        return repaired

    repaired.intent = "strategy_drafting"
    repaired.requires_clarification = True
    repaired.assistant_response = plan.assistant_response
    repaired.missing_required_fields = list(
        dict.fromkeys(plan.missing_required_fields or ["entry_logic"])
    )
    repaired.reason_codes = list(
        dict.fromkeys([*repaired.reason_codes, "signal_rule_plan_needs_clarification"])
    )
    return repaired


def _signal_rule_plan_raw_value(draft: LLMStrategyDraft) -> str:
    value = (
        draft.entry_logic
        or draft.strategy_thesis
        or draft.raw_user_phrasing
        or draft.strategy_type
        or "unsupported signal strategy"
    )
    return str(value)


def _prior_strategy_payload(
    request: InterpretationRequest,
) -> dict[str, Any] | None:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return None
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None:
        return None
    return prior.model_dump(mode="json")
