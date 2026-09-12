"""A money question Argus computes itself, from the interpreter's typed read.

The model maps the question to a declared calculation and the numbers the
user stated (``interpretation.calculation``); everything after that is
deterministic: the declaration validates the inputs, a missing one becomes
the model's own clarification and is asked for once, the tool runs in
process with no provider call, and the card carries every figure. The prose
lead never states a number. A read that needs published inputs for a named
asset is left to research, which computes the same way after retrieval.
Every guard that compensates for the read records a reason code.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from loguru import logger
from pydantic import ValidationError

from argus.agent_runtime.calculation_rows import market_counterfactual_rows
from argus.agent_runtime.interpreter.calculation_request import (
    RUNTIME_ARGUMENTS,
    CalculationRequest,
)
from argus.agent_runtime.interpreter.research_routing import primary_research_query
from argus.agent_runtime.result_next_steps import (
    QUESTION_STEP,
    NextStep,
    next_steps_patch,
    offered_test_steps,
)
from argus.agent_runtime.stages.interpret_types import (
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async
from argus.agent_runtime.state.models import RunState, UserState
from argus.domain.calculations import is_free_calculation
from argus.domain.calculations._shared import MISSING_INPUT_CODE
from argus.domain.tool_contracts import ToolCall
from argus.domain.tool_declaration import ToolDeclaration, ToolInvocationError

CALCULATION_ANSWER_REASON_CODE = "calculation_answer"
CALCULATION_FOLLOW_UPS_REASON_CODE = "calculation_follow_ups"
INPUT_MISSING_REASON_CODE = "calculation_input_missing"
# Guards after the read, each recorded when it fires.
PENDING_MERGED_REASON_CODE = "calculation_pending_merged"
KIND_UNKNOWN_REASON_CODE = "calculation_kind_unknown"
INPUTS_DROPPED_REASON_CODE = "calculation_inputs_dropped"
SOLVE_FOR_CLEARED_REASON_CODE = "calculation_solve_for_cleared"
CURRENCY_DEFAULTED_REASON_CODE = "calculation_currency_defaulted"
LEAD_REPLACED_REASON_CODE = "calculation_lead_replaced"
RETRIEVAL_OWNS_REASON_CODE = "calculation_retrieval_needed"
NOTHING_TO_SOLVE_REASON_CODE = "calculation_nothing_to_solve"
DEFAULT_CURRENCY = "USD"
CURRENCY_FIELD = "currency"
PENDING_PAYLOAD_KEY = "calculation"


async def calculation_turn_stage_result(
    *,
    interpretation: StructuredInterpretation,
    state: RunState,
    user: UserState,
    selected_thread_metadata: dict[str, Any],
) -> StageResult | None:
    request = _request_for_turn(interpretation, selected_thread_metadata)
    if request is None:
        return None
    if request.kind is None:
        return _follow_up_result(interpretation, request, user)
    from argus.domain.capability_registry import get_tool_catalog

    catalog = get_tool_catalog()
    declaration = catalog.get(request.kind)
    if declaration is None or not is_free_calculation(declaration):
        _note(interpretation, KIND_UNKNOWN_REASON_CODE, kind=request.kind)
        return None
    if request.retrieve and primary_research_query(interpretation) is not None:
        # Published inputs about a named asset: research retrieves them with
        # their pages and computes the same declaration afterwards.
        _note(interpretation, RETRIEVAL_OWNS_REASON_CODE, retrieve=request.retrieve)
        return None
    arguments = _arguments(declaration, request, interpretation=interpretation, user=user)
    missing = _missing_inputs(declaration, arguments, request, interpretation)
    if missing is None:
        return None
    if missing:
        return _clarification_result(
            interpretation, request, user=user, missing=missing, arguments=arguments
        )
    return await _computed_result(
        interpretation, declaration, arguments, state=state, user=user, catalog=catalog
    )


def _request_for_turn(
    interpretation: StructuredInterpretation, metadata: dict[str, Any]
) -> CalculationRequest | None:
    """The turn's read, merged over a pending calculation the user is answering."""
    read = interpretation.calculation
    pending = _pending_request(metadata)
    if pending is None:
        return read
    if read is not None and read.kind not in (None, pending.kind):
        return read
    merged = CalculationRequest(
        kind=pending.kind,
        inputs={**pending.inputs, **(read.inputs if read else {})},
        solve_for=(read.solve_for if read and read.solve_for else pending.solve_for),
        retrieve=list(read.retrieve if read and read.retrieve else pending.retrieve),
    )
    _note(interpretation, PENDING_MERGED_REASON_CODE, kind=pending.kind)
    return merged


def _pending_request(metadata: dict[str, Any]) -> CalculationRequest | None:
    if metadata.get("last_stage_outcome") != "await_user_reply":
        return None
    clarification = metadata.get("clarification")
    payload = clarification.get("payload") if isinstance(clarification, dict) else None
    pending = payload.get(PENDING_PAYLOAD_KEY) if isinstance(payload, dict) else None
    if not isinstance(pending, dict):
        return None
    try:
        request = CalculationRequest.model_validate(pending)
    except ValidationError:
        return None
    return request if request.kind is not None else None


def _arguments(
    declaration: ToolDeclaration,
    request: CalculationRequest,
    *,
    interpretation: StructuredInterpretation,
    user: UserState,
) -> dict[str, Any]:
    declared = set(declaration.arguments_type.model_fields) - RUNTIME_ARGUMENTS
    arguments = {
        name: value for name, value in request.inputs.items() if name in declared
    }
    dropped = sorted(set(request.inputs) - set(arguments))
    if dropped:
        _note(interpretation, INPUTS_DROPPED_REASON_CODE, dropped=dropped)
    if request.solve_for in arguments and arguments[request.solve_for] is not None:
        arguments[request.solve_for] = None
        _note(interpretation, SOLVE_FOR_CLEARED_REASON_CODE, field=request.solve_for)
    if not arguments.get(CURRENCY_FIELD):
        arguments[CURRENCY_FIELD] = user.currency or DEFAULT_CURRENCY
        if not user.currency:
            _note(
                interpretation, CURRENCY_DEFAULTED_REASON_CODE, currency=DEFAULT_CURRENCY
            )
    return arguments


def _missing_inputs(
    declaration: ToolDeclaration,
    arguments: dict[str, Any],
    request: CalculationRequest,
    interpretation: StructuredInterpretation,
) -> list[str] | None:
    """Inputs the user still has to give, ``[]`` when the calculation can run,
    ``None`` when there is nothing to solve."""
    try:
        declaration.validate_arguments(arguments)
    except ToolInvocationError as exc:
        failure = exc.outcome.failure
        if failure is not None and failure.code == MISSING_INPUT_CODE:
            return _ordered(list(failure.fields), interpretation)
        if failure is None or failure.code != "exactly_one_unknown":
            return []
        blanks = [name for name in failure.fields if arguments.get(name) is None]
        if not blanks:
            _note(interpretation, NOTHING_TO_SOLVE_REASON_CODE, kind=declaration.name)
            return None
        return _ordered(
            [name for name in blanks if name != request.solve_for], interpretation
        )
    except ValidationError as exc:
        missing = [
            str(error["loc"][0])
            for error in exc.errors()
            if error.get("type") == "missing" and error.get("loc")
        ]
        return _ordered(missing, interpretation) if missing else []
    except (ValueError, TypeError):
        return []
    return []


def _ordered(missing: list[str], interpretation: StructuredInterpretation) -> list[str]:
    """The model's own naming of the missing input goes first."""
    named = [name for name in interpretation.missing_required_fields if name in missing]
    return list(dict.fromkeys([*named, *missing]))


def _clarification_result(
    interpretation: StructuredInterpretation,
    request: CalculationRequest,
    *,
    user: UserState,
    missing: list[str],
    arguments: dict[str, Any],
) -> StageResult:
    field = missing[0]
    prompt = (
        interpretation.assistant_response
        if interpretation.requires_clarification and interpretation.assistant_response
        else None
    )
    pending = request.model_copy(
        update={
            "inputs": {
                name: value for name, value in arguments.items() if value is not None
            }
        }
    )
    return StageResult(
        outcome="await_user_reply",
        decision=_decision(interpretation, user, INPUT_MISSING_REASON_CODE),
        stage_patch={
            "assistant_prompt": prompt or _fallback_question(field, user),
            "requested_field": field,
            "missing_required_fields": list(missing),
            "clarification": {
                "kind": "clarification",
                "reason_code": INPUT_MISSING_REASON_CODE,
                "prompt_source": "llm_generated" if prompt else "degraded_fallback",
                "requested_field": field,
                "requested_fields": list(missing),
                "semantic_needs": [],
                "payload": {PENDING_PAYLOAD_KEY: pending.model_dump(mode="json")},
                "options": [],
            },
        },
    )


def _follow_up_result(
    interpretation: StructuredInterpretation,
    request: CalculationRequest,
    user: UserState,
) -> StageResult | None:
    questions = [text for text in request.follow_up_questions if text.strip()]
    if not questions:
        return None
    steps = [NextStep(kind=QUESTION_STEP, text=text) for text in questions]
    patch = next_steps_patch(None, steps)
    if not patch:
        return None
    return StageResult(
        outcome="ready_to_respond",
        decision=_decision(interpretation, user, CALCULATION_FOLLOW_UPS_REASON_CODE),
        stage_patch={
            "assistant_response": interpretation.assistant_response
            or _fallback_lead(user, succeeded=True),
            **patch,
        },
    )


async def _computed_result(
    interpretation: StructuredInterpretation,
    declaration: ToolDeclaration,
    arguments: dict[str, Any],
    *,
    state: RunState,
    user: UserState,
    catalog: Any,
) -> StageResult:
    call = ToolCall(
        tool_name=declaration.name,
        call_id=f"calculation-{uuid4()}",
        arguments=arguments,
    )
    executed = await execute_tool_calls_async(
        state=state.model_copy(update={"tool_calls": [call]}),
        tool=None,
        catalog=catalog,
        language=user.language_preference,
        user=user,
    )
    patch = dict(executed.stage_patch)
    cards = (patch.get("final_response_payload") or {}).get("tool_result_cards") or []
    succeeded = bool(cards) and cards[0].get("outcome", {}).get("status") == "succeeded"
    patch["assistant_response"] = _lead(interpretation, user, succeeded=succeeded)
    if succeeded:
        rows = market_counterfactual_rows(arguments, language=user.language_preference)
        patch.update(next_steps_patch(rows, offered_test_steps(rows)))
    return StageResult(
        outcome="ready_to_respond",
        decision=_decision(interpretation, user, CALCULATION_ANSWER_REASON_CODE),
        stage_patch=patch,
    )


def _lead(
    interpretation: StructuredInterpretation, user: UserState, *, succeeded: bool
) -> str:
    """The model's own short lead when it states no figure and the card succeeded;
    the card states every figure, and a failed card explains itself."""
    lead = (interpretation.assistant_response or "").strip()
    if succeeded and lead and not any(character.isdigit() for character in lead):
        return lead
    if succeeded and lead:
        _note(interpretation, LEAD_REPLACED_REASON_CODE)
    return _fallback_lead(user, succeeded=succeeded)


def _fallback_lead(user: UserState, *, succeeded: bool) -> str:
    spanish = user.language_preference.startswith("es")
    if succeeded:
        if spanish:
            return "Aquí está el cálculo con tus números. Cambia cualquier dato para recalcularlo."
        return (
            "Here is the calculation from your numbers. Change any input to recompute it."
        )
    if spanish:
        return (
            "Los números tal como están no tienen solución. La tarjeta indica qué "
            "falta y ofrece una corrección."
        )
    return "The numbers as stated do not solve. The card names what is missing and offers a fix."


def _fallback_question(field: str, user: UserState) -> str:
    label = field.replace("_pct", " (%)").replace("_", " ")
    if user.language_preference.startswith("es"):
        return f"Para calcularlo me falta un dato: {label}. ¿Qué valor uso?"
    return f"To compute this I need one more value: {label}. What should I use?"


def _decision(interpretation: StructuredInterpretation, user: UserState, code: str):
    from argus.agent_runtime.research_grounded import research_decision

    return research_decision(interpretation, user, code)


def _note(interpretation: StructuredInterpretation, code: str, **context: Any) -> None:
    if code not in interpretation.reason_codes:
        interpretation.reason_codes.append(code)
    logger.info(
        "Calculation turn guard {} {}", code, context, failure_classification=code
    )
