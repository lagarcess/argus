"""The interpreter's typed read of a money question Argus computes itself.

The model maps the question to one declared calculation and the numbers the
user stated; the runtime validates against the declaration, computes, and
renders the card. Nothing here reads the message: a missing input is the
model's own clarification, a broad question is the model's own follow-ups.
The kinds and their argument names come from the declarations, so the
catalogue the model reads and the math that runs share one owner.
"""

from __future__ import annotations

from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel, Field, JsonValue

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


class CalculationRequest(BaseModel):
    kind: CalculationKind | None = Field(
        default=None,
        description=(
            "The calculation Argus runs for this turn, from the kinds listed in "
            "the instructions. Null when the money question is too broad to "
            "compute; fill follow_up_questions instead."
        ),
    )
    inputs: dict[str, JsonValue] = Field(
        default_factory=dict,
        description=(
            "Every input the user stated, under the argument names the "
            "instructions list for the kind: amounts as plain numbers, "
            "percentages as plain percent numbers (7 for 7%), counts of periods "
            "as integers, dates as ISO dates, a ticker under symbol, and "
            "currency as an ISO 4217 code only when the user names one. Never "
            "put a value you computed or assumed here."
        ),
    )
    solve_for: str | None = Field(
        default=None,
        description=(
            "For a kind that lists blanks, the one argument the user wants "
            "solved; leave it out of inputs. Null for kinds without blanks."
        ),
    )
    retrieve: list[str] = Field(
        default_factory=list,
        max_length=MAX_RETRIEVED_INPUTS,
        description=(
            "Listed inputs the user did not state that a published page about "
            "the named asset supplies, such as the current price, per-share "
            "earnings, published growth rates or valuation multiples. Empty "
            "when every input is the user's own."
        ),
    )
    follow_up_questions: list[str] = Field(
        default_factory=list,
        max_length=MAX_FOLLOW_UP_QUESTIONS,
        description=(
            "When kind is null because the question is too broad to compute, up "
            "to three specific questions in the user's own words and language "
            "that would make it computable, each asking for one concrete figure "
            "or choice. Never a list of what Argus can calculate."
        ),
    )


CALCULATION_GUIDANCE = (
    "Independent of the act, answer one more question for every turn: does "
    "the user want a figure computed from numbers they stated or from "
    "published inputs about a named asset, in any language? A balance that "
    "grows, a loan or saving payment, the rate or term that fits a plan, a "
    "yield, a price multiple, an effective rate, a debt ratio, what a fee "
    "costs, a ranking of stated offers, a discounted cash flow, a bond price "
    "and what an investment or asset will be worth are all calculations. If "
    "yes, fill calculation from the kinds below and keep a question turn "
    "(conversation_followup or beginner_guidance with an educational_question "
    "act); Argus computes and shows every figure, so write assistant_response "
    "as one short lead with no numbers in it. When an input only the user can "
    "supply is missing, keep calculation filled, set "
    "requires_clarification=true, name the argument in missing_required_fields "
    "and ask for that one value in assistant_response. When the question is "
    "too broad to compute, leave kind null and fill follow_up_questions. A "
    "reply to a pending calculation question (requested_field in the selected "
    "thread metadata) fills calculation with the answered argument alone; "
    "Argus keeps the rest. "
    "Leave calculation null for requests to build or run a test, edits, "
    "approvals, questions about a visible result or confirmation, and "
    "questions whose answer is a figure read from a page rather than "
    "computed. Kinds and their inputs:\n"
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
