from __future__ import annotations

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState


BEGINNER_GUIDANCE_PROMPT = (
    "What is one idea or market question you want to explore first?"
)
AMBIGUOUS_TURN_PROMPT = (
    "Should I keep working on the current idea, or are you starting a new backtest?"
)
OPTIONAL_PARAMETER_OPT_IN_LIMIT = 3


def clarify_stage(*, state: RunState, contract: CapabilityContract) -> StageResult:
    requested_field = _first_missing_required_field(
        missing_required_fields=state.missing_required_fields,
        contract=contract,
    )

    if requested_field is not None:
        field_description = contract.describe_field(requested_field)
        label = (
            field_description.label.lower()
            if field_description is not None
            else requested_field.replace("_", " ")
        )
        prompt = _required_field_prompt(requested_field=requested_field, label=label)

        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": prompt,
                "requested_field": requested_field,
            },
        )

    if _is_beginner_guidance_turn(state):
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": BEGINNER_GUIDANCE_PROMPT,
                "requested_field": None,
            },
        )

    if _needs_ambiguity_clarification(state):
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": _ambiguous_turn_prompt(state),
                "requested_field": None,
            },
        )

    optional_parameter_choices = _optional_parameter_choices(state.optional_parameter_status)
    if optional_parameter_choices:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": _optional_parameter_opt_in_prompt(
                    optional_parameter_choices=optional_parameter_choices,
                    contract=contract,
                ),
                "requested_field": None,
                "optional_parameter_choices": optional_parameter_choices,
            },
        )

    return StageResult(
        outcome="ready_for_confirmation",
        stage_patch={
            "assistant_prompt": None,
            "requested_field": None,
        },
    )


def _optional_parameter_choices(
    optional_parameter_status: dict[str, object],
) -> list[str]:
    opportunities = optional_parameter_status.get("optional_parameter_opportunity", [])
    if not isinstance(opportunities, list):
        return []
    choices = [value for value in opportunities if isinstance(value, str)]
    return choices[:OPTIONAL_PARAMETER_OPT_IN_LIMIT]


def _optional_parameter_opt_in_prompt(
    *,
    optional_parameter_choices: list[str],
    contract: CapabilityContract,
) -> str:
    labels = ", ".join(
        _optional_parameter_label(choice, contract=contract)
        for choice in optional_parameter_choices
    )
    descriptions = "; ".join(
        _optional_parameter_description(choice, contract=contract)
        for choice in optional_parameter_choices
    )
    return (
        "I can use the defaults, or adjust a few optional settings first. "
        f"Do you want to change any of these: {labels}? {descriptions}"
    )


def _optional_parameter_label(field_name: str, *, contract: CapabilityContract) -> str:
    field_description = contract.describe_field(field_name)
    if field_description is None:
        return field_name.replace("_", " ")
    return field_description.label


def _optional_parameter_description(
    field_name: str,
    *,
    contract: CapabilityContract,
) -> str:
    field_description = contract.describe_field(field_name)
    if field_description is None:
        return field_name.replace("_", " ")
    return f"{field_description.label}: {field_description.description}"


def _needs_ambiguity_clarification(state: RunState) -> bool:
    return state.task_relation == "ambiguous" and state.intent != "beginner_guidance"


def _is_beginner_guidance_turn(state: RunState) -> bool:
    return state.intent == "beginner_guidance"


def _ambiguous_turn_prompt(state: RunState) -> str:
    return AMBIGUOUS_TURN_PROMPT


def _first_missing_required_field(
    *,
    missing_required_fields: list[str],
    contract: CapabilityContract,
) -> str | None:
    required_fields = set(contract.required_fields)
    for field_name in missing_required_fields:
        if field_name in required_fields:
            return field_name
    return None


def _required_field_prompt(*, requested_field: str, label: str) -> str:
    prompts = {
        "strategy_thesis": "What investing idea do you want to test?",
        "asset_universe": "Which symbol or symbols should I include?",
        "entry_logic": "What entry logic should I use?",
        "exit_logic": "What exit logic should I use?",
        "date_range": "What date range should I test?",
    }
    return prompts.get(requested_field, f"What {label} should I use?")
