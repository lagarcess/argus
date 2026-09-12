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
            "Listed inputs the user did not state that a published page "
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


CALCULATION_GUIDANCE = (
    "Money questions Argus computes. Independent of the act, decide on every "
    "turn whether the user wants a figure computed, in any language: a saving "
    "or loan payment, what a balance grows to, the rate or time a plan needs, "
    "what an income affords, a yield, a price multiple, an effective rate, a "
    "debt ratio, what a fee costs, a ranking of offers, a discounted cash flow, "
    "a bond or certificate value, or what an investment will be worth. If yes, "
    "fill calculation and keep a question turn (conversation_followup or "
    "beginner_guidance with an educational_question act). Never read such a "
    "question as a test or a strategy, and never put a product, loan, bond, "
    "certificate or card in candidate_strategy_draft or "
    "unsupported_constraints. Choose the closest kind below even when inputs "
    "are missing: put the numbers the user stated in inputs, and put every "
    "input a published page states (a product's price, a lender's or bank's "
    "rate, local inflation, an asset's price or earnings) in retrieve; never "
    "ask the user for those. When an input only the user knows is still "
    "missing (their income, balance, payment or horizon), set "
    "requires_clarification=true, name that one argument in "
    "missing_required_fields and ask for it in assistant_response. For "
    "example, a 25,000 loan at 9 percent with no payment stated fills "
    "time_value with direction borrow, present_value 25000, future_value 0 and "
    "annual_rate_pct 9, and asks for the monthly payment. Leave kind null and "
    "fill follow_up_questions only when no kind below fits the question at "
    "all. Argus shows every computed figure, so write assistant_response as one "
    "short lead with no numbers in it. A reply to a pending calculation "
    "question (requested_field in the selected thread metadata) fills "
    "calculation with the answered argument alone; Argus keeps the rest. Leave "
    "calculation null for requests to build or run a test over past market "
    "data, edits, approvals, questions about a visible result or confirmation, "
    "and questions whose answer is a figure read from a page rather than "
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
