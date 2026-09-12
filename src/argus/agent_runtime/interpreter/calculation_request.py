"""The interpreter's typed read of a money question Argus computes itself.

The model maps the question to one declared calculation and the numbers the
user stated; the runtime validates against the declaration, computes, and
renders the card. Nothing here reads the message: a missing input is the
model's own clarification, a broad question is the model's own follow-ups.
The kinds and their argument names come from the declarations, so the
catalogue the model reads and the math that runs share one owner.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args, get_origin

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    JsonValue,
    WithJsonSchema,
)

from argus.domain.calculations import get_calculation_declarations
from argus.domain.tool_declaration import ToolDeclaration

MAX_FOLLOW_UP_QUESTIONS = 3
MAX_RETRIEVED_INPUTS = 12
# Arguments the runtime supplies, never the model.
RUNTIME_ARGUMENTS = frozenset({"sources"})


def calculation_kinds() -> tuple[str, ...]:
    return tuple(
        sorted(declaration.name for declaration in get_calculation_declarations())
    )


CalculationKind = Literal[calculation_kinds()]  # type: ignore[valid-type]


def calculation_argument_names() -> tuple[str, ...]:
    """Every argument a declared calculation accepts from the model."""
    names: set[str] = set()
    for declaration in get_calculation_declarations():
        names.update(
            name
            for name in declaration.arguments_type.model_fields
            if name not in RUNTIME_ARGUMENTS and name != "currency"
        )
    return tuple(sorted(names))


# Advertised to the model as the only valid names; parsed leniently so one
# stray name never fails the whole interpretation (the runtime drops it).
_ARGUMENT_NAMES = list(calculation_argument_names())


def _inputs_from_pairs(value: Any) -> Any:
    """The model sends inputs as name and value pairs; the runtime keeps a map."""
    if not isinstance(value, list):
        return value
    return {
        item["name"]: item.get("value")
        for item in value
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


_OFFER_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "symbol": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "value": {"type": "number"},
    },
    "required": ["label", "symbol", "value"],
    "additionalProperties": False,
}
# A strict structured output cannot describe an open object, so the inputs
# travel as a closed list of pairs and are folded into a map on parse.
_INPUT_PAIRS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "enum": [*_ARGUMENT_NAMES, "currency"]},
            "value": {
                "anyOf": [
                    {"type": "number"},
                    {"type": "string"},
                    {"type": "boolean"},
                    {"type": "array", "items": _OFFER_SCHEMA},
                    {"type": "null"},
                ]
            },
        },
        "required": ["name", "value"],
        "additionalProperties": False,
    },
}
CalculationInputs = Annotated[
    dict[str, JsonValue],
    BeforeValidator(_inputs_from_pairs),
    WithJsonSchema(_INPUT_PAIRS_SCHEMA),
]


def all_properties_required(schema: dict[str, Any]) -> None:
    """A structured read writes every field; parsing keeps the defaults."""
    schema["required"] = list(schema.get("properties", {}))


class CalculationRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra=all_properties_required)

    inputs: CalculationInputs = Field(
        default_factory=dict,
        description=(
            "Every input the user stated, one name and value pair each, under "
            "the argument names the "
            "instructions list for the kind: amounts as plain numbers, "
            "percentages as plain percent numbers (7 for 7%), counts of periods "
            "as integers, dates as ISO dates, a ticker under symbol, and "
            "currency as an ISO 4217 code only when the user names one. Never "
            "put a value you computed or assumed here."
        ),
    )
    solve_for: str | None = Field(
        default=None,
        json_schema_extra={
            "anyOf": [{"type": "string", "enum": _ARGUMENT_NAMES}, {"type": "null"}]
        },
        description=(
            "For a kind that lists blanks, the argument name of the one blank "
            "the user wants solved; leave it out of inputs. Null for kinds "
            "without blanks."
        ),
    )
    retrieve: list[str] = Field(
        default_factory=list,
        max_length=MAX_RETRIEVED_INPUTS,
        json_schema_extra={"items": {"type": "string", "enum": _ARGUMENT_NAMES}},
        description=(
            "Argument names, from the kind's listed inputs, that the user did "
            "not state and a published page "
            "supplies: a named product's or asset's price, a bank's or lender's "
            "published rate, the inflation rate where the user lives, per-share "
            "earnings, growth forecasts or multiples. Never ask the user for "
            "these. Empty when every input is the user's own."
        ),
    )
    follow_up_questions: list[str] = Field(
        default_factory=list,
        max_length=MAX_FOLLOW_UP_QUESTIONS,
        description=(
            "When kind is null because no calculation fits the question, up to "
            "three specific questions in the user's own words and language that "
            "would make it computable, each asking for one concrete figure "
            "or choice the user alone knows, never a figure a published page "
            "states. Never a list of what Argus can calculate."
        ),
    )
    kind: CalculationKind | None = Field(
        default=None,
        description=(
            "The calculation Argus runs for this turn: the kind listed in the "
            "instructions whose inputs the fields above name, chosen even when "
            "an input is still missing. Null only when no listed kind fits."
        ),
    )


def calculation_kinds_clause() -> str:
    """The catalogue the model reads, generated from the declarations."""
    lines = [
        f"- {declaration.name}: {declaration.description} Inputs: "
        f"{', '.join(_argument_lines(declaration))}."
        + "".join(
            f" Exactly one blank among {', '.join(rule.fields)}."
            for rule in declaration.rules
        )
        for declaration in get_calculation_declarations()
    ]
    return "\n".join(lines) + "\n\n"


def _argument_lines(declaration: ToolDeclaration) -> list[str]:
    lines: list[str] = []
    for name, model_field in declaration.arguments_type.model_fields.items():
        if name in RUNTIME_ARGUMENTS:
            continue
        lines.append(f"{name}{_shape_hint(model_field.annotation)}")
    return lines


def _shape_hint(annotation: Any) -> str:
    options = _literal_options(annotation)
    if options:
        return f" ({' or '.join(options)})"
    if get_origin(annotation) is list:
        (item,) = get_args(annotation)
        if isinstance(item, type) and issubclass(item, BaseModel):
            return f" (list of {{{', '.join(item.model_fields)}}})"
    if "date" in str(annotation):
        return " (ISO date)"
    return ""


def _literal_options(annotation: Any) -> tuple[str, ...]:
    if get_origin(annotation) is Literal:
        return tuple(str(option) for option in get_args(annotation))
    for member in get_args(annotation):
        options = _literal_options(member)
        if options:
            return options
    return ()
