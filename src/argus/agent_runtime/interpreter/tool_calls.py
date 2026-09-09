"""Project declared calls into the existing runtime without a question classifier."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.interpreter.strategy_routing import STRATEGY_TURN_ACTS
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.profile.response_profile import (
    resolve_effective_response_profile,
)
from argus.agent_runtime.stages.interpret_types import (
    InterpretDecision,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import StrategySummary, UserState
from argus.domain.tool_contracts import ToolCall


def catalog_standalone_response(
    response: LLMInterpretationResponse | StructuredInterpretation,
) -> bool:
    return (
        response.uses_tool_catalog
        and response.candidate_strategy_draft == type(response.candidate_strategy_draft)()
        and response.semantic_turn_act
        not in {
            *STRATEGY_TURN_ACTS,
            "result_followup",
            "retry_failed_action",
        }
    )


def runtime_catalog_interpretation(
    response: LLMInterpretationResponse,
    *,
    current_user_message: str,
    normalize_strategy: Callable[[LLMStrategyDraft, str], StrategySummary],
) -> StructuredInterpretation:
    return StructuredInterpretation.model_validate(
        {
            **response.model_dump(mode="json"),
            "uses_tool_catalog": True,
            "tool_calls": runtime_tool_calls(
                response.tool_calls,
                current_user_message=current_user_message,
                normalize_strategy=normalize_strategy,
            ),
            "candidate_strategy_draft": {},
            "missing_required_fields": [],
            "ambiguous_fields": [],
            "unsupported_constraints": [],
        }
    )


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
        return StageResult(outcome="approved_for_execution", decision=decision)
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


def runtime_tool_calls(
    calls: list[Any],
    *,
    current_user_message: str,
    normalize_strategy: Callable[[LLMStrategyDraft, str], StrategySummary],
) -> list[ToolCall]:
    """Each backtest draft derives from its own call, never the whole batch.

    The existing draft converter resolves typed temporal intent and preserves
    the backtest's own evidence. Provider and launch validity remain the
    confirmation/launch owner's job; no rejected asset is silently dropped here.
    """
    normalized: list[ToolCall] = []
    for raw_call in calls:
        call = ToolCall.model_validate(raw_call.model_dump(mode="json"))
        if call.tool_name == "backtest":
            raw_strategy = call.arguments.get("strategy")
            if isinstance(raw_strategy, dict):
                payload = dict(raw_strategy)
                extra = payload.get("extra_parameters")
                if isinstance(extra, dict):
                    for name in LLMStrategyDraft.model_fields:
                        if name not in payload and name in extra:
                            payload[name] = extra[name]
                draft = LLMStrategyDraft.model_validate(payload)
                strategy = normalize_strategy(draft, current_user_message)
                if raw_strategy.get("resolution_provenance") is not None:
                    strategy.resolution_provenance = StrategySummary.model_validate(
                        raw_strategy
                    ).resolution_provenance
                call = call.model_copy(
                    update={
                        "arguments": {
                            **call.arguments,
                            "strategy": strategy.model_dump(mode="json"),
                        }
                    }
                )
        normalized.append(call)
    return normalized
