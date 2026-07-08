from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Protocol

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.clarification_contract import (
    offline_clarification_fallback,
    typed_clarification_contract,
)
from argus.agent_runtime.llm_clarifier import ClarificationRequest
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import (
    PendingNeedName,
    ResponseIntent,
    RunState,
    StrategySummary,
)

OPTIONAL_PARAMETER_OPT_IN_LIMIT = 3
ARTIFACT_EDIT_CLARIFICATION_FIELDS = {"assumption", "refinement"}


class StructuredClarificationGenerator(Protocol):
    def __call__(self, request: ClarificationRequest) -> str | None: ...

    async def ainvoke(self, request: ClarificationRequest) -> str | None: ...


@dataclass(frozen=True)
class ClarifyingQuestionResult:
    prompt: str
    used_degraded_fallback: bool


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
    unsupported_constraints = _blocking_unsupported_constraints(
        state=state,
        requested_fields=requested_fields,
        unsupported_constraints=unsupported_constraints,
    )

    if unsupported_constraints:
        options = _simplification_options(unsupported_constraints)
        response_intent = _response_intent(
            kind="unsupported_recovery",
            state=state,
            semantic_needs=["simplification_choice"],
            facts={"unsupported_constraints": unsupported_constraints},
            options=options,
            language=language,
        )
        generated = await _generate_clarifying_question_result(
            state=state,
            response_intent=response_intent,
            missing_required_fields=[],
            ambiguous_fields=[],
            unsupported_constraints=unsupported_constraints,
            optional_parameter_choices=[],
            clarification_generator=clarification_generator,
            language=language,
        )
        stage_patch = {
            "assistant_prompt": generated.prompt,
            "response_intent": response_intent,
            "requested_field": state.requested_field,
            "missing_required_fields": list(state.missing_required_fields),
            "unsupported_constraints": unsupported_constraints,
            "simplification_options": options,
        }
        if generated.used_degraded_fallback:
            stage_patch.update(
                _clarification_sidecar_patch(
                    state=state,
                    response_intent=response_intent,
                    requested_field=state.requested_field or "unsupported_constraints",
                )
            )
        return StageResult(
            outcome="await_user_reply",
            stage_patch=stage_patch,
        )

    if ambiguous_fields:
        response_intent = _response_intent(
            kind="clarification",
            state=state,
            semantic_needs=_semantic_needs_from_fields(ambiguous_fields),
            requested_fields=requested_fields,
            facts={"ambiguous_fields": ambiguous_fields},
            language=language,
        )
        requested_field = _requested_field_for_ambiguous_fields(
            state=state,
            requested_fields=requested_fields,
            ambiguous_fields=ambiguous_fields,
        )
        generated = await _generate_clarifying_question_result(
            state=state,
            response_intent=response_intent,
            missing_required_fields=requested_fields,
            ambiguous_fields=ambiguous_fields,
            unsupported_constraints=[],
            optional_parameter_choices=[],
            clarification_generator=clarification_generator,
            language=language,
        )
        stage_patch = {
            "assistant_prompt": generated.prompt,
            "response_intent": response_intent,
            "requested_field": requested_field,
            "ambiguous_fields": ambiguous_fields,
        }
        if generated.used_degraded_fallback:
            stage_patch.update(
                _clarification_sidecar_patch(
                    state=state,
                    response_intent=response_intent,
                    requested_field=requested_field,
                )
            )
        return StageResult(
            outcome="await_user_reply",
            stage_patch=stage_patch,
        )

    if requested_fields:
        response_intent = _response_intent(
            kind="clarification",
            state=state,
            semantic_needs=_semantic_needs_from_required_fields(requested_fields),
            requested_fields=requested_fields,
            language=language,
        )
        requested_field = requested_fields[0] if len(requested_fields) == 1 else None
        generated = await _generate_clarifying_question_result(
            state=state,
            response_intent=response_intent,
            missing_required_fields=requested_fields,
            ambiguous_fields=[],
            unsupported_constraints=[],
            optional_parameter_choices=[],
            clarification_generator=clarification_generator,
            language=language,
        )
        stage_patch = {
            "assistant_prompt": generated.prompt,
            "response_intent": response_intent,
            "requested_field": requested_field,
            "requested_fields": requested_fields,
        }
        if generated.used_degraded_fallback:
            stage_patch.update(
                _clarification_sidecar_patch(
                    state=state,
                    response_intent=response_intent,
                    requested_field=requested_field,
                )
            )
        return StageResult(
            outcome="await_user_reply",
            stage_patch=stage_patch,
        )

    if _is_beginner_guidance_turn(state):
        response_intent = _response_intent(
            kind="beginner_guidance",
            state=state,
            language=language,
        )
        prefilled = _usable_prefilled_prompt(prefilled_assistant_prompt)
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": prefilled
                or await _generate_clarifying_question(
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
        response_intent = _response_intent(
            kind="ambiguity_check",
            state=state,
            language=language,
        )
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
    result = await _generate_clarifying_question_result(
        state=state,
        response_intent=response_intent,
        missing_required_fields=missing_required_fields,
        ambiguous_fields=ambiguous_fields,
        unsupported_constraints=unsupported_constraints,
        optional_parameter_choices=optional_parameter_choices,
        clarification_generator=clarification_generator,
        language=language,
    )
    return result.prompt


async def _generate_clarifying_question_result(
    *,
    state: RunState,
    response_intent: dict[str, object],
    missing_required_fields: list[str],
    ambiguous_fields: list[dict[str, object]],
    unsupported_constraints: list[dict[str, object]],
    optional_parameter_choices: list[str],
    clarification_generator: StructuredClarificationGenerator | None,
    language: str,
) -> ClarifyingQuestionResult:
    if clarification_generator is None:
        return ClarifyingQuestionResult(
            prompt=offline_clarification_fallback(
                language=language,
                response_intent=response_intent,
                strategy=state.candidate_strategy_draft
                if state.candidate_strategy_draft is not None
                else None,
            ),
            used_degraded_fallback=True,
        )
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
    if question:
        return ClarifyingQuestionResult(
            prompt=question,
            used_degraded_fallback=False,
        )
    return ClarifyingQuestionResult(
        prompt=offline_clarification_fallback(
            language=language,
            response_intent=response_intent,
            strategy=state.candidate_strategy_draft
            if state.candidate_strategy_draft is not None
            else None,
        ),
        used_degraded_fallback=True,
    )


def _usable_prefilled_prompt(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _clarification_sidecar_patch(
    *,
    state: RunState,
    response_intent: dict[str, object],
    requested_field: str | None,
) -> dict[str, object]:
    clarification = typed_clarification_contract(
        response_intent=response_intent,
        requested_field=requested_field,
        strategy=state.candidate_strategy_draft,
    )
    return {"clarification": clarification} if clarification is not None else {}


def _response_intent(
    *,
    kind: str,
    state: RunState,
    semantic_needs: list[PendingNeedName] | None = None,
    requested_fields: list[str] | None = None,
    facts: dict[str, object] | None = None,
    options: list[dict[str, object]] | None = None,
    language: str = "en",
) -> dict[str, object]:
    strategy = state.candidate_strategy_draft
    semantic_needs = _expanded_semantic_needs(
        strategy=strategy,
        semantic_needs=semantic_needs or [],
    )
    strategy_payload = (
        strategy.model_dump(mode="python")
        if hasattr(strategy, "model_dump")
        else dict(strategy or {})
        if isinstance(strategy, dict)
        else {}
    )
    payload = ResponseIntent(
        kind=kind,
        semantic_needs=semantic_needs,
        requested_fields=requested_fields or [],
        facts={
            "strategy": strategy_payload,
            "current_user_message": state.current_user_message,
            "language": language,
            **(facts or {}),
        },
        options=options or [],
    )
    return payload.model_dump(mode="python")


def _expanded_semantic_needs(
    *,
    strategy: StrategySummary,
    semantic_needs: list[PendingNeedName],
) -> list[PendingNeedName]:
    needs = list(dict.fromkeys(semantic_needs))
    if (
        strategy.strategy_type == "dca_accumulation"
        and "sizing_amount" in needs
        and "schedule" not in needs
        and strategy.cadence in (None, "", [], {})
        and (strategy.extra_parameters or {}).get("cadence") in (None, "", [], {})
    ):
        needs.append("schedule")
    return needs


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
    requested_field = _field_base(state.requested_field or "")
    if (
        requested_field in ARTIFACT_EDIT_CLARIFICATION_FIELDS
        and requested_field in state.missing_required_fields
    ):
        return [requested_field]
    first_missing = _first_missing_required_field(
        missing_required_fields=state.missing_required_fields,
        contract=contract,
    )
    if first_missing is not None and len(state.missing_required_fields) == 1:
        return [first_missing]
    return [
        field
        for field in state.missing_required_fields
        if field in contract.required_fields or field in {"capital_amount", "cadence"}
    ]


def _requested_field_for_ambiguous_fields(
    *,
    state: RunState,
    requested_fields: list[str],
    ambiguous_fields: list[dict[str, object]],
) -> str | None:
    if state.requested_field:
        return _field_base(state.requested_field)
    base_fields = [
        _field_base(field)
        for field in requested_fields
        if isinstance(field, str) and _field_base(field)
    ]
    if len(set(base_fields)) == 1:
        return base_fields[0]
    ambiguous_base_fields = [
        _field_base(str(field.get("field_name") or ""))
        for field in ambiguous_fields
        if isinstance(field.get("field_name"), str)
    ]
    if len(set(ambiguous_base_fields)) == 1:
        return ambiguous_base_fields[0]
    return None


def _field_base(field: str) -> str:
    return field.split("[", 1)[0]


def _semantic_needs_from_required_fields(fields: list[str]) -> list[PendingNeedName]:
    field_map: dict[str, PendingNeedName] = {
        "asset_universe": "asset_target",
        "capital_amount": "sizing_amount",
        "cadence": "schedule",
        "date_range": "period",
        "entry_logic": "rule_definition",
        "exit_logic": "rule_definition",
        "assumption": "assumption",
    }
    needs: list[PendingNeedName] = []
    for field in fields:
        need = field_map.get(_field_base(field))
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


def _blocking_unsupported_constraints(
    *,
    state: RunState,
    requested_fields: list[str],
    unsupported_constraints: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not unsupported_constraints:
        return []
    if not _dca_execution_details_are_still_missing(state, requested_fields):
        return unsupported_constraints
    return [
        constraint
        for constraint in unsupported_constraints
        if constraint.get("category") != "unsupported_dca_starting_principal"
    ]


def _dca_execution_details_are_still_missing(
    state: RunState,
    requested_fields: list[str],
) -> bool:
    strategy = state.candidate_strategy_draft
    if strategy.strategy_type != "dca_accumulation":
        return False
    executable_fields = {"asset_universe", "date_range", "capital_amount", "cadence"}
    return bool(executable_fields.intersection(requested_fields))


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
        if field_name in required_fields or field_name in {"capital_amount", "cadence"}:
            return field_name
    return None
