"""The typed calculations an answer asks Argus to compute.

An answering model, the research provider or the no-search voicing model,
returns its prose and a short list of ``AnswerCalculation``, one per option the
reader weighs: each a declared kind and each input with its source. The kinds,
argument names and result names come from the declarations, so the catalogue a
model reads and the math that runs share one owner. Names are advertised as enums and parsed leniently: one stray
name never fails the whole answer, and the runtime drops it on record.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, field_validator

from argus.domain.calculations import get_calculation_declarations
from argus.domain.tool_declaration import ToolDeclaration

# Arguments the runtime supplies, never a model.
RUNTIME_ARGUMENTS = frozenset({"sources"})
MAX_ANSWER_INPUTS = 16
# Calculations one answer carries, bounded at parse time like its inputs.
MAX_ANSWER_CALCULATIONS = 4


def calculation_kinds() -> tuple[str, ...]:
    return tuple(sorted(item.name for item in get_calculation_declarations()))


def calculation_argument_names() -> tuple[str, ...]:
    """Every argument a declared calculation accepts from a model."""
    names: set[str] = set()
    for declaration in get_calculation_declarations():
        names.update(
            name
            for name in declaration.arguments_type.model_fields
            if name not in RUNTIME_ARGUMENTS
        )
    return tuple(sorted(names))


def all_properties_required(schema: dict[str, Any]) -> None:
    """A structured output writes every field; parsing keeps the defaults."""
    schema["required"] = list(schema.get("properties", {}))


_OFFER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "label": {"type": "string"},
        "symbol": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "value": {"type": "number"},
    },
    "required": ["label", "symbol", "value"],
    "additionalProperties": False,
}
AnswerInputValue = Annotated[
    bool | float | str | list[dict[str, Any]] | None,
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "number"},
                {"type": "string"},
                {"type": "boolean"},
                {"type": "array", "items": _OFFER_SCHEMA},
                {"type": "null"},
            ]
        }
    ),
]
AnswerSourceKind = Literal["page", "market_data", "user", "assumption"]


class AnswerCalculationInput(BaseModel):
    """One input the calculation uses, with where its value came from."""

    model_config = ConfigDict(frozen=True, json_schema_extra=all_properties_required)

    name: Annotated[
        str,
        WithJsonSchema({"type": "string", "enum": list(calculation_argument_names())}),
    ] = Field(description="The input's name, exactly as the calculation list writes it.")
    value: AnswerInputValue = Field(
        default=None,
        description=(
            "The value: a plain number (7 for 7 percent, 1250000 for 1.25 million), "
            "one of the listed options, a list of offers, or null for a figure only "
            "the user knows and has not said."
        ),
    )
    source: AnswerSourceKind = Field(
        description=(
            "page: read from a page retrieved for this answer. market_data: the "
            "current price of the named asset, which Argus fills from its own "
            "market data. user: stated by the user. assumption: a figure you chose, "
            "which the answer states plainly as an assumption."
        )
    )
    source_url: str | None = Field(
        default=None,
        description="For page, the URL of the retrieved page the value was read from; otherwise null.",
    )
    as_of: str | None = Field(
        default=None,
        description="For page, the date the page gives for the value as YYYY-MM-DD; otherwise null.",
    )
    currency: str | None = Field(
        default=None,
        description="For a money amount, its ISO 4217 code; otherwise null.",
    )


class AnswerCalculation(BaseModel):
    """One calculation Argus computes for this answer."""

    model_config = ConfigDict(frozen=True, json_schema_extra=all_properties_required)

    prior_artifact_id: str | None = None
    updated_fields: list[str] = Field(default_factory=list)

    name: str = Field(
        default="",
        description=(
            "A short lowercase name for this calculation, such as the option it "
            "computes; with more than one calculation, each figure reference starts "
            "with it."
        ),
    )
    kind: Annotated[
        str, WithJsonSchema({"type": "string", "enum": list(calculation_kinds())})
    ] = Field(
        description="The listed calculation that computes the figure the answer turns on."
    )
    solve_for: Annotated[
        str | None,
        WithJsonSchema(
            {
                "anyOf": [
                    {"type": "string", "enum": list(calculation_argument_names())},
                    {"type": "null"},
                ]
            }
        ),
    ] = Field(
        default=None,
        description=(
            "For a kind that lists blanks, the name of the one blank to solve, left "
            "out of inputs; null otherwise."
        ),
    )
    inputs: list[AnswerCalculationInput] = Field(
        default_factory=list,
        description="Every input the kind needs, one entry each, with its source.",
    )

    @field_validator("inputs")
    @classmethod
    def _bounded(
        cls, inputs: list[AnswerCalculationInput]
    ) -> list[AnswerCalculationInput]:
        # Enforced here, not advertised: a strict provider schema that carries an
        # item bound is refused outright by Anthropic-backed research models.
        return inputs[:MAX_ANSWER_INPUTS]


# Model-facing contract shared by every answering model; frozen by the
# fingerprint and, for research, by the recorded retrieval probe.
ANSWER_CALCULATION_INSTRUCTIONS = (
    "Fill calculations only when the answer computes on specific figures, such as "
    "what a plan, loan or purchase costs, what an amount earns or grows to, "
    "how many years a sum takes to double, which option costs less or what "
    "a dividend yields at today's price, each with the one kind listed below that "
    "computes it. When the reader weighs options, fill one calculation for each "
    "option under its own short name, with the same kind when one kind computes "
    "them all, and never say which option to choose. Argus computes each one: never "
    "compute a figure yourself, such as a change, a percentage, a ratio or a total; "
    "state each figure as its source gives it, or let a calculation produce it. "
    "List every input the kind needs with its "
    "source: page for a figure read from a page retrieved for this answer, with "
    "that page's URL and date; market_data for the current price of the named "
    "asset, which Argus fills from its own market data; user for a figure the user "
    "stated; assumption for any other figure you choose, which the answer must "
    "state plainly as an assumption. Count every money input in one currency, give "
    "its ISO 4217 code, and add that code as the currency input. A figure only the "
    "user knows that the user did not state is listed with source user and a null "
    "value. Only when you fill calculations, write each figure a calculation uses or "
    "produces as {{name}}, with its input or result name, or as "
    "{{calculation_name.name}} when there is more than one calculation, never as "
    "digits, including in a worked example; Argus fills each one from the computed "
    "result. Every other figure is written in digits and is never a reference. "
    "Leave calculations empty when the answer computes nothing. Kinds, their inputs "
    "and their results:\n"
)


def calculation_kinds_clause() -> str:
    """The catalogue an answering model reads, generated from the declarations."""
    lines = [
        f"- {declaration.name}: {declaration.description} Inputs: "
        f"{', '.join(_argument_lines(declaration))}."
        + "".join(
            f" Exactly one blank among {', '.join(rule.fields)}."
            for rule in declaration.rules
        )
        + _result_line(declaration)
        for declaration in get_calculation_declarations()
    ]
    return "\n".join(lines) + "\n\n"


def _argument_lines(declaration: ToolDeclaration) -> list[str]:
    return [
        f"{name}{_shape_hint(model_field.annotation)}"
        for name, model_field in declaration.arguments_type.model_fields.items()
        if name not in RUNTIME_ARGUMENTS
    ]


def _result_line(declaration: ToolDeclaration) -> str:
    names = [
        name
        for name, model_field in declaration.result_type.model_fields.items()
        if not name.startswith("solved_")
        and get_origin(model_field.annotation) is not list
        and model_field.annotation in (float, int, float | None, int | None)
    ]
    return f" Results: {', '.join(names)}." if names else ""


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
