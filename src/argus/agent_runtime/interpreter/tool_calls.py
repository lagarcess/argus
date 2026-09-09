"""Project declared calls into the existing runtime without a question classifier."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.interpreter import provider_context_assets
from argus.agent_runtime.interpreter.strategy_routing import strategy_route_expected
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import UserState
from argus.domain.tool_contracts import ToolCall


def catalog_standalone_response(
    response: LLMInterpretationResponse | StructuredInterpretation,
) -> bool:
    return (
        response.uses_tool_catalog
        and response.candidate_strategy_draft == type(response.candidate_strategy_draft)()
        and not response.requires_clarification
        and not response.missing_required_fields
        and not response.ambiguous_fields
        and not response.unsupported_constraints
        and not strategy_route_expected(
            intent=response.intent, semantic_turn_act=response.semantic_turn_act
        )
        and response.semantic_turn_act not in {"result_followup", "retry_failed_action"}
    )


def runtime_catalog_interpretation(
    response: LLMInterpretationResponse,
) -> StructuredInterpretation:
    interpretation = StructuredInterpretation.model_validate(
        {
            **response.model_dump(mode="json"),
            "uses_tool_catalog": True,
            "tool_calls": runtime_tool_calls(response.tool_calls),
            "candidate_strategy_draft": {},
            "missing_required_fields": [],
            "ambiguous_fields": [],
            "unsupported_constraints": [],
        }
    )
    interpretation._tool_asset_resolution_context = (
        response._tool_asset_resolution_context
    )
    return interpretation


async def catalog_stage_result(
    interpretation: StructuredInterpretation,
    *,
    user: UserState,
    current_user_message: str,
    contract: CapabilityContract,
    compose_capability_answer: Callable[..., Awaitable[str | None]],
) -> StageResult | None:
    if not interpretation.tool_calls and not catalog_standalone_response(interpretation):
        return None
    decision = InterpretDecision(
        **interpretation.model_dump(
            exclude={"research_query", "assistant_response", "response_profile_overrides"}
        ),
        effective_response_profile=resolve_effective_response_profile(
            user=user, explicit_overrides=interpretation.response_profile_overrides
        ),
    )
    if interpretation.tool_calls:
        return StageResult(
            outcome="approved_for_execution",
            decision=decision,
            stage_patch={
                "normalized_signals": {
                    provider_context_assets.TOOL_ASSET_CONTEXT_SIGNAL: interpretation._tool_asset_resolution_context,
                }
            },
        )
    answer = interpretation.assistant_response
    if interpretation.capability_question_focus is not None:
        capability_answer = await compose_capability_answer(
            focus=interpretation.capability_question_focus,
            semantic_turn_act=interpretation.semantic_turn_act,
            expects_strategy_route=False,
            requires_clarification=interpretation.requires_clarification,
            assistant_response=answer,
            current_user_message=current_user_message,
            capability_contract=contract,
            language=user.language_preference,
        )
        if capability_answer is not None:
            answer = capability_answer
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch={"assistant_response": answer},
    )


def runtime_tool_calls(calls: list[Any]) -> list[ToolCall]:
    """Preserve declared input; its confirmation handler owns preparation."""
    return [ToolCall.model_validate(call.model_dump(mode="json")) for call in calls]
