from __future__ import annotations

import asyncio
import inspect
from typing import Protocol

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.llm_clarifier import ClarificationRequest
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import PendingNeedName, ResponseIntent, RunState

OPTIONAL_PARAMETER_OPT_IN_LIMIT = 3
OFFLINE_CLARIFICATION_FALLBACK = (
    "I could not generate the clarifying question right now. Please try again."
)


class StructuredClarificationGenerator(Protocol):
    def __call__(self, request: ClarificationRequest) -> str | None: ...

    async def ainvoke(self, request: ClarificationRequest) -> str | None: ...


def clarify_stage(
    *,
    state: RunState,
    contract: CapabilityContract,
    clarification_generator: StructuredClarificationGenerator | None = None,
    language: str = "en",
    prefilled_assistant_prompt: str | None = None,
) -> StageResult:
    return asyncio.run(
        clarify_stage_async(
            state=state,
            contract=contract,
            clarification_generator=clarification_generator,
            language=language,
            prefilled_assistant_prompt=prefilled_assistant_prompt,
        )
    )


async def clarify_stage_async(
    *,
    state: RunState,
    contract: CapabilityContract,
    clarification_generator: StructuredClarificationGenerator | None = None,
    language: str = "en",
    prefilled_assistant_prompt: str | None = None,
) -> StageResult:
    del prefilled_assistant_prompt
    unsupported_constraints = _unsupported_constraints(state.optional_parameter_status)
    ambiguous_fields = _ambiguous_fields(state.optional_parameter_status)
    optional_parameter_choices = _optional_parameter_choices(
        state.optional_parameter_status
    )
    requested_fields = _requested_fields(
        state=state,
        contract=contract,
        ambiguous_fields=ambiguous_fields,
        unsupported_constraints=unsupported_constraints,
        optional_parameter_choices=optional_parameter_choices,
    )

    if unsupported_constraints:
        options = _simplification_options(unsupported_constraints)
        response_intent = _response_intent(
            kind="unsupported_recovery",
            state=state,
            semantic_needs=["simplification_choice"],
            facts={"unsupported_constraints": unsupported_constraints},
            options=options,
        )
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": await _generate_clarifying_question(
                    state=state,
                    response_intent=response_intent,
                    missing_required_fields=[],
                    ambiguous_fields=[],
                    unsupported_constraints=unsupported_constraints,
                    optional_parameter_choices=[],
                    clarification_generator=clarification_generator,
                    language=language,
                ),
                "response_intent": response_intent,
                "requested_field": state.requested_field,
                "missing_required_fields": list(state.missing_required_fields),
                "unsupported_constraints": unsupported_constraints,
                "simplification_options": options,
            },
        )

    if ambiguous_fields:
        response_intent = _response_intent(
            kind="clarification",
            state=state,
            semantic_needs=_semantic_needs_from_fields(ambiguous_fields),
            requested_fields=requested_fields,
            facts={"ambiguous_fields": ambiguous_fields},
        )
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": await _generate_clarifying_question(
                    state=state,
                    response_intent=response_intent,
                    missing_required_fields=requested_fields,
                    ambiguous_fields=ambiguous_fields,
                    unsupported_constraints=[],
                    optional_parameter_choices=[],
                    clarification_generator=clarification_generator,
                    language=language,
                ),
                "response_intent": response_intent,
                "requested_field": None,
                "ambiguous_fields": ambiguous_fields,
            },
        )

    if requested_fields:
        response_intent = _response_intent(
            kind="clarification",
            state=state,
            semantic_needs=_semantic_needs_from_required_fields(requested_fields),
            requested_fields=requested_fields,
        )
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": await _generate_clarifying_question(
                    state=state,
                    response_intent=response_intent,
                    missing_required_fields=requested_fields,
                    ambiguous_fields=[],
                    unsupported_constraints=[],
                    optional_parameter_choices=[],
                    clarification_generator=clarification_generator,
                    language=language,
                ),
                "response_intent": response_intent,
                "requested_field": requested_fields[0]
                if len(requested_fields) == 1
                else None,
                "requested_fields": requested_fields,
            },
        )

    if _is_beginner_guidance_turn(state):
        response_intent = _response_intent(kind="beginner_guidance", state=state)
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": await _generate_clarifying_question(
                    state=state,
                    response_intent=response_intent,
                    missing_required_fields=[],
                    ambiguous_fields=[],
                    unsupported_constraints=[],
                    optional_parameter_choices=[],
                    clarification_generator=clarification_generator,
                    language=language,
                ),
                "response_intent": response_intent,
                "requested_field": None,
            },
        )

    if _needs_ambiguity_clarification(state):
        response_intent = _response_intent(kind="ambiguity_check", state=state)
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": await _generate_clarifying_question(
                    state=state,
                    response_intent=response_intent,
                    missing_required_fields=[],
                    ambiguous_fields=[],
                    unsupported_constraints=[],
                    optional_parameter_choices=[],
                    clarification_generator=clarification_generator,
                    language=language,
                ),
                "response_intent": response_intent,
                "requested_field": None,
            },
        )

    if optional_parameter_choices:
        return StageResult(
            outcome="ready_for_confirmation",
            stage_patch={
                "requested_field": None,
                "assistant_prompt": None,
            },
        )

    return StageResult(
        outcome="ready_for_confirmation",
        stage_patch={
            "assistant_prompt": None,
            "requested_field": None,
        },
    )


async def _generate_clarifying_question(
    *,
    state: RunState,
    response_intent: dict[str, object],
    missing_required_fields: list[str],
    ambiguous_fields: list[dict[str, object]],
    unsupported_constraints: list[dict[str, object]],
    optional_parameter_choices: list[str],
    clarification_generator: StructuredClarificationGenerator | None,
    language: str,
) -> str:
    if clarification_generator is None:
        return OFFLINE_CLARIFICATION_FALLBACK
    request = ClarificationRequest(
        current_user_message=state.current_user_message,
        recent_thread_history=state.recent_thread_history,
        candidate_strategy_draft=state.candidate_strategy_draft,
        missing_required_fields=missing_required_fields,
        ambiguous_fields=ambiguous_fields,
        unsupported_constraints=unsupported_constraints,
        optional_parameter_choices=optional_parameter_choices,
        response_intent=response_intent,
        language=language,
    )
    async_invoke = getattr(clarification_generator, "ainvoke", None)
    if async_invoke is not None:
        result = async_invoke(request)
        question = await result if inspect.isawaitable(result) else result
    else:
        result = clarification_generator(request)
        question = await result if inspect.isawaitable(result) else result
    return question or OFFLINE_CLARIFICATION_FALLBACK


def _response_intent(
    *,
    kind: str,
    state: RunState,
    semantic_needs: list[PendingNeedName] | None = None,
    requested_fields: list[str] | None = None,
    facts: dict[str, object] | None = None,
    options: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    strategy = state.candidate_strategy_draft
    strategy_payload = (
        strategy.model_dump(mode="python")
        if hasattr(strategy, "model_dump")
        else dict(strategy or {})
        if isinstance(strategy, dict)
        else {}
    )
    payload = ResponseIntent(
        kind=kind,
        semantic_needs=semantic_needs or [],
        requested_fields=requested_fields or [],
        facts={
            "strategy": strategy_payload,
            "current_user_message": state.current_user_message,
            **(facts or {}),
        },
        options=options or [],
    )
    return payload.model_dump(mode="python")


def _requested_fields(
    *,
    state: RunState,
    contract: CapabilityContract,
    ambiguous_fields: list[dict[str, object]],
    unsupported_constraints: list[dict[str, object]],
    optional_parameter_choices: list[str],
) -> list[str]:
    del unsupported_constraints, optional_parameter_choices
    if ambiguous_fields:
        return [
            str(field.get("field_name"))
            for field in ambiguous_fields
            if isinstance(field.get("field_name"), str)
        ]
    first_missing = _first_missing_required_field(
        missing_required_fields=state.missing_required_fields,
        contract=contract,
    )
    if first_missing is not None and len(state.missing_required_fields) == 1:
        return [first_missing]
    return [
        field
        for field in state.missing_required_fields
        if field in contract.required_fields or field == "capital_amount"
    ]


def _semantic_needs_from_required_fields(fields: list[str]) -> list[PendingNeedName]:
    field_map: dict[str, PendingNeedName] = {
        "asset_universe": "asset_target",
        "capital_amount": "sizing_amount",
        "date_range": "period",
        "entry_logic": "rule_definition",
        "exit_logic": "rule_definition",
    }
    needs: list[PendingNeedName] = []
    for field in fields:
        need = field_map.get(field)
        if need is not None and need not in needs:
            needs.append(need)
    return needs


def _semantic_needs_from_fields(
    fields: list[dict[str, object]],
) -> list[PendingNeedName]:
    required_fields = [
        str(field.get("field_name", ""))
        for field in fields
        if isinstance(field.get("field_name"), str)
    ]
    needs = _semantic_needs_from_required_fields(required_fields)
    reason_codes = {
        str(field.get("reason_code", ""))
        for field in fields
        if isinstance(field.get("reason_code"), str)
    }
    reason_map: dict[str, PendingNeedName] = {
        "missing_asset_target": "asset_target",
        "missing_sizing_amount": "sizing_amount",
        "missing_period": "period",
        "entry_rule_needs_definition": "rule_definition",
    }
    for code, need in reason_map.items():
        if code in reason_codes and need not in needs:
            needs.append(need)
    return needs


def _optional_parameter_choices(
    optional_parameter_status: dict[str, object],
) -> list[str]:
    opportunities = optional_parameter_status.get("optional_parameter_opportunity", [])
    if not isinstance(opportunities, list):
        return []
    choices = [value for value in opportunities if isinstance(value, str)]
    return choices[:OPTIONAL_PARAMETER_OPT_IN_LIMIT]


def _ambiguous_fields(
    optional_parameter_status: dict[str, object],
) -> list[dict[str, object]]:
    ambiguous_fields = optional_parameter_status.get("ambiguous_fields", [])
    if not isinstance(ambiguous_fields, list):
        return []
    return [
        value
        for value in ambiguous_fields
        if isinstance(value, dict) and isinstance(value.get("field_name"), str)
    ]


def _unsupported_constraints(
    optional_parameter_status: dict[str, object],
) -> list[dict[str, object]]:
    unsupported_constraints = optional_parameter_status.get("unsupported_constraints", [])
    if not isinstance(unsupported_constraints, list):
        return []
    return [
        value
        for value in unsupported_constraints
        if isinstance(value, dict) and isinstance(value.get("category"), str)
    ]


def _simplification_options(
    unsupported_constraints: list[dict[str, object]],
) -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    for constraint in unsupported_constraints:
        raw_options = constraint.get("simplification_options", [])
        if not isinstance(raw_options, list):
            continue
        for option in raw_options:
            if not isinstance(option, dict):
                continue
            if isinstance(option.get("label"), str):
                options.append(option)
    return options


def _needs_ambiguity_clarification(state: RunState) -> bool:
    return state.task_relation == "ambiguous" and state.intent != "beginner_guidance"


def _is_beginner_guidance_turn(state: RunState) -> bool:
    return state.intent == "beginner_guidance"


def _first_missing_required_field(
    *,
    missing_required_fields: list[str],
    contract: CapabilityContract,
) -> str | None:
    required_fields = set(contract.required_fields)
    for field_name in missing_required_fields:
        if field_name in required_fields or field_name == "capital_amount":
            return field_name
    return None
