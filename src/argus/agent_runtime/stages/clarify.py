from __future__ import annotations

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import RunState

BEGINNER_GUIDANCE_PROMPT = (
    "No problem. I can help you pick a starting point. We can test a simple buy-and-hold idea, a recurring investment plan, or a rule like buying when RSI is low. If you want the simplest path, name an asset and say a timeframe, like 'Tesla over 2 years'."
)
AMBIGUOUS_TURN_PROMPT = (
    "Should I keep working on the current idea, or are you starting a new backtest?"
)
OPTIONAL_PARAMETER_OPT_IN_LIMIT = 3


def clarify_stage(*, state: RunState, contract: CapabilityContract) -> StageResult:
    unsupported_constraints = _unsupported_constraints(state.optional_parameter_status)
    if unsupported_constraints:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": _unsupported_constraint_prompt(
                    unsupported_constraints
                ),
                "requested_field": None,
                "unsupported_constraints": unsupported_constraints,
                "simplification_options": _simplification_options(
                    unsupported_constraints
                ),
            },
        )

    ambiguous_fields = _ambiguous_fields(state.optional_parameter_status)
    if ambiguous_fields:
        return StageResult(
            outcome="await_user_reply",
            stage_patch={
                "assistant_prompt": _ambiguous_fields_prompt(ambiguous_fields),
                "requested_field": None,
                "ambiguous_fields": ambiguous_fields,
            },
        )

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


def _ambiguous_fields(optional_parameter_status: dict[str, object]) -> list[dict[str, object]]:
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


def _ambiguous_fields_prompt(ambiguous_fields: list[dict[str, object]]) -> str:
    if len(ambiguous_fields) == 1 and ambiguous_fields[0].get("field_name") == "entry_logic":
        raw_value = str(ambiguous_fields[0].get("raw_value", "")).strip()
        if raw_value:
            return (
                f"I understand the idea as buying on {raw_value}. To backtest it, "
                "I need to turn that into a specific rule. Do you want to define the dip as a percent drop, "
                "use a supported RSI rule, or keep drafting the idea first?"
            )
    parts = []
    for field in ambiguous_fields:
        field_name = str(field["field_name"]).replace("_", " ")
        raw_value = str(field.get("raw_value", "")).strip()
        candidate = str(field.get("candidate_normalized_value", "")).strip()
        if raw_value and candidate and candidate.lower() != "none":
            parts.append(
                f"{field_name}: you said '{raw_value}', and I interpreted it as '{candidate}'"
            )
        elif raw_value:
            parts.append(f"{field_name}: you said '{raw_value}'")
    joined = "; ".join(parts)
    return (
        "I need to clarify a couple of strategy details before I continue. "
        f"{joined}. Which of those should I use?"
    )


def _unsupported_constraint_prompt(
    unsupported_constraints: list[dict[str, object]],
) -> str:
    first_constraint = unsupported_constraints[0]
    explanation = str(first_constraint.get("explanation", "")).strip()
    labels = [
        _friendly_option_label(str(option.get("label", "")).strip())
        for option in _simplification_options(unsupported_constraints)
        if str(option.get("label", "")).strip()
    ]
    prompt = explanation or "Part of this strategy is not supported yet."
    if labels:
        prompt += " I can " + _choice_phrase(labels) + ". Which direction should I take?"
    return prompt


def _friendly_option_label(label: str) -> str:
    normalized = label.strip().lower()
    if normalized in {"max_available", "maximum_available"}:
        return "use the maximum available history"
    if normalized == "since_ipo":
        return "start at the IPO date"
    if normalized.startswith("last_") and normalized.endswith("_years"):
        count = normalized.removeprefix("last_").removesuffix("_years")
        if count.isdigit():
            return f"use the last {count} years"
    if "_" in label and not label.lower().startswith("run "):
        return label.replace("_", " ")
    return label


def _choice_phrase(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]}, or {labels[1]}"
    return ", ".join(labels[:-1]) + f", or {labels[-1]}"


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
        "strategy_thesis": "I can help shape this. Are you thinking buy-and-hold, recurring buys, or a rule-based strategy?",
        "asset_universe": "Which asset should I test?",
        "entry_logic": "What should trigger the buy?",
        "exit_logic": "What should trigger the sell or exit?",
        "date_range": "What time period should I test?",
    }
    return prompts.get(requested_field, f"What {label} should I use?")
