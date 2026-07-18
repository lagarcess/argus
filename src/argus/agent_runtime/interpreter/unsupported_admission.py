"""Issue #159: typed guards for the unsupported-intent vs executable-draft contradiction.

Invariant: an interpretation still carrying ``intent=unsupported_or_out_of_scope``
never admits to confirmation. Promotion to a supported intent stays LLM-owned via
the capability-conflict audit; every non-promoted outcome fails closed into typed
unsupported recovery."""

from __future__ import annotations

import json
from typing import Any

from argus.agent_runtime.interpreter.shared import (
    _llm_strategy_draft_has_concrete_execution_target,
)
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.agent_runtime.stages.interpret_internal.asset_resolution import (
    _optional_parameter_stage_patch,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretationRequest,
    InterpretDecision,
    StageResult,
)
from argus.agent_runtime.state.models import UnsupportedConstraint
from argus.agent_runtime.strategy_contract import canonical_strategy_type

UNSUPPORTED_INTENT_ADMISSION_BLOCKED = "unsupported_intent_confirmation_blocked"
CAPABILITY_CONFLICT_INVERSE_REASON = "supported_strategy_capability_conflict_inverse"

# Byte-identical to the constraint-present audit framing previously inlined in
# run_field_audits._supported_strategy_capability_conflict_messages.
CAPABILITY_CONFLICT_KEEP_DIRECTION_PROMPT = (
    "You are Argus's capability-conflict audit. The primary interpreter "
    "returned both a supported canonical strategy and an "
    "unsupported_strategy_logic constraint, or returned a raw natural-"
    "language strategy phrase as unsupported while preserving executable "
    "field evidence. Decide whether the current user message semantically "
    "selects a supported Alpha strategy or asks for real unsupported "
    "custom logic. Use semantic meaning, not keyword or phrase matching. "
    "Supported Alpha strategy families include buy_and_hold and "
    "dca_accumulation when the user is only asking to test holding or "
    "recurring fixed-dollar buys over a period. A plain performance, "
    "return, or benchmark comparison between one primary asset and a "
    "reference asset over a stated window is a supported buy_and_hold "
    "comparison with comparison_baseline; it is not unsupported custom "
    "strategy logic unless the user adds a separate unsupported rule. "
    "Keep the unsupported "
    "constraint when the current message adds an extra unsupported entry "
    "condition, exit condition, fundamental rule, sentiment/news/event "
    "rule, custom script, brokerage action, shorting, or other logic "
    "beyond the supported strategy family. Drop it only when the message "
    "semantically asks for the supported strategy itself and no extra "
    "unsupported rule. Set selected_strategy_type to the canonical "
    "supported family when dropping the constraint. Reason from the "
    "current message and structured draft meaning. Return only JSON "
    "matching the schema."
)

_CAPABILITY_CONFLICT_INVERSE_PROMPT = (
    "You are Argus's capability-conflict audit. The primary interpreter "
    "reported this turn as unsupported or out of scope, yet it also "
    "produced an executable supported strategy draft without any "
    "unsupported_strategy_logic constraint. Decide which half is true of "
    "the current user message. Use semantic meaning, not keyword or "
    "phrase matching. Set drop_unsupported_strategy_logic=true only when "
    "the message itself semantically asks for the supported canonical "
    "strategy in the draft (for example plain holding or recurring "
    "fixed-dollar buys over a period) and the unsupported classification "
    "is the contradiction; then set selected_strategy_type to that "
    "supported family. Set keep_unsupported_strategy_logic=true when the "
    "message asks for a capability the backtest engine does not execute, "
    "such as custom entry/exit conditions, fundamental or sentiment/news/"
    "event rules, custom scripting, brokerage actions, shorting, or "
    "instruments beyond plain spot holdings; treat the supported draft as "
    "a substitution the user did not ask for. Never treat the mere "
    "presence of the draft as consent. Return only JSON matching the "
    "schema."
)

_ADMISSION_CONSTRAINT_EXPLANATION = (
    "That idea needs a rule or data source the current backtest engine "
    "cannot execute directly yet."
)


def response_has_only_unsupported_strategy_logic_constraints(
    response: LLMInterpretationResponse,
) -> bool:
    constraints = response.unsupported_constraints
    return bool(constraints) and all(
        item.category == "unsupported_strategy_logic" for item in constraints
    )


def response_needs_inverse_capability_conflict_audit(
    response: LLMInterpretationResponse,
) -> bool:
    if any(
        item.category == "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    ):
        return False
    if (
        response.intent != "unsupported_or_out_of_scope"
        and response.semantic_turn_act != "unsupported_request"
    ):
        return False
    draft = response.candidate_strategy_draft
    if canonical_strategy_type(draft.strategy_type) not in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        return False
    return _llm_strategy_draft_has_concrete_execution_target(draft)


def inverse_capability_conflict_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _CAPABILITY_CONFLICT_INVERSE_PROMPT},
        {
            "role": "system",
            "content": (
                "Structured draft JSON: "
                f"{response.candidate_strategy_draft.model_dump(mode='json')}"
            ),
        },
        {
            "role": "system",
            "content": (
                "Primary interpretation verdict JSON: "
                + json.dumps(
                    {
                        "intent": response.intent,
                        "semantic_turn_act": response.semantic_turn_act,
                    },
                    ensure_ascii=False,
                )
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def inverse_promotion_reason_codes(
    response: LLMInterpretationResponse,
) -> list[str]:
    if any(
        item.category == "unsupported_strategy_logic"
        for item in response.unsupported_constraints
    ):
        return []
    return [CAPABILITY_CONFLICT_INVERSE_REASON]


def _admission_constraint_raw_value(decision: InterpretDecision) -> str:
    draft = decision.candidate_strategy_draft
    for candidate in (
        decision.user_goal_summary,
        draft.strategy_thesis,
        draft.raw_user_phrasing,
    ):
        value = str(candidate or "").strip()
        if value:
            return value
    return "the requested strategy"


def admitted_or_blocked_confirmation_result(
    *,
    decision: InterpretDecision,
    stage_patch: dict[str, Any],
    contract: Any,
    optional_parameter_values: dict[str, Any],
    assistant_response: str | None,
) -> StageResult:
    """Admission invariant: unsupported intent cannot become an executable card.

    Only a typed promotion path (audit, requested-asset answer, pending-option
    selection, artifact patch) rewrites intent before this boundary; anything
    still unsupported here fails closed into typed unsupported recovery."""

    if decision.intent != "unsupported_or_out_of_scope":
        return StageResult(
            outcome="ready_for_confirmation",
            decision=decision,
            stage_patch=stage_patch,
        )
    constraint = UnsupportedConstraint(
        category="unsupported_strategy_logic",
        raw_value=_admission_constraint_raw_value(decision),
        explanation=_ADMISSION_CONSTRAINT_EXPLANATION,
        simplification_options=contract.get_simplification_options(
            "unsupported_strategy_logic"
        ),
    )
    blocked_decision = decision.model_copy(
        update={
            "requires_clarification": True,
            "unsupported_constraints": [*decision.unsupported_constraints, constraint],
            "reason_codes": list(
                dict.fromkeys(
                    [*decision.reason_codes, UNSUPPORTED_INTENT_ADMISSION_BLOCKED]
                )
            ),
        }
    )
    blocked_patch = dict(
        _optional_parameter_stage_patch(
            decision=blocked_decision,
            values=optional_parameter_values,
        )
    )
    if assistant_response:
        blocked_patch["assistant_response"] = assistant_response
    return StageResult(
        outcome="needs_clarification",
        decision=blocked_decision,
        stage_patch=blocked_patch,
    )
