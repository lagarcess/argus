"""Comparison over a set: items ranked by one computed key, never recommended."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from argus.domain.calculations._shared import (
    CalculationArguments,
    CalculationResult,
    Symbol,
    free_policy,
    input_fact,
    text,
)
from argus.domain.finance import comparison
from argus.domain.tool_contracts import (
    LocalizedText,
    ToolCardPresentation,
    ToolFact,
    ToolOutcome,
)
from argus.domain.tool_declaration import (
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)
from argus.domain.tool_fact_projection import ResultFact, ResultProjection

KeyKind = Literal["percent", "money", "multiple", "count"]


class ComparisonItem(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    label: str = Field(min_length=1, max_length=120)
    symbol: Symbol
    value: float


MAX_COMPARISON_ITEMS = 12


class RankedComparisonArguments(CalculationArguments):
    key_label: str = Field(min_length=1, max_length=120)
    key_kind: KeyKind = "percent"
    prefer: Literal["higher", "lower"] = "lower"
    items: list[ComparisonItem] = Field(min_length=2, max_length=MAX_COMPARISON_ITEMS)


# Each ranked figure's fact name: the prefix and its position from the best item.
RANK_FACT_PREFIX = "rank_"
# Each ranked item's gap to the best, named by its position like its figure.
GAP_FACT_PREFIX = "gap_"


class RankedRow(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    label: str
    symbol: str | None
    value: float
    rank: int
    gap_to_best: float


class RankedComparisonResult(CalculationResult):
    key_label: str
    prefer: str
    rows: list[RankedRow]


def compute_ranked_comparison(
    arguments: RankedComparisonArguments,
) -> RankedComparisonResult:
    # Ranked by position, so items that share a label keep their own symbols.
    ranked = comparison.rank_by_key(
        [(str(index), item.value) for index, item in enumerate(arguments.items)],
        prefer=arguments.prefer,
    )
    return RankedComparisonResult(
        key_label=arguments.key_label,
        prefer=arguments.prefer,
        rows=[
            RankedRow(
                label=arguments.items[int(row.label)].label,
                symbol=arguments.items[int(row.label)].symbol,
                value=row.value,
                rank=row.rank,
                gap_to_best=row.gap_to_best,
            )
            for row in ranked
        ],
    )


def _unit(kind: KeyKind, currency: str) -> LocalizedText | None:
    if kind == "percent":
        return text("chat.tools.units.percent")
    if kind == "money":
        return text("tools.calc.units.currency", code=currency)
    if kind == "multiple":
        return text("tools.calc.units.multiple")
    return None


def _ranked_projection() -> ResultProjection:
    facts = []
    for index in range(MAX_COMPARISON_ITEMS):
        facts.extend(
            (
                ResultFact(
                    f"{RANK_FACT_PREFIX}{index}",
                    lambda name, a, r, position=index: ToolFact(
                        name=name,
                        label=text(
                            "tools.calc.ranked_comparison.row",
                            rank=r.rows[position].rank,
                            label=r.rows[position].label,
                        ),
                        value=round(r.rows[position].value, 2),
                        unit=_unit(a.key_kind, a.currency),
                    ),
                    placement="answer" if index == 0 else "row",
                    when=lambda a, r, position=index: position < len(r.rows),
                ),
                ResultFact(
                    f"{GAP_FACT_PREFIX}{index}",
                    lambda name, a, r, position=index: ToolFact(
                        name=name,
                        label=text(
                            "tools.calc.ranked_comparison.gap",
                            label=r.rows[position].label,
                        ),
                        value=round(r.rows[position].gap_to_best, 2),
                        unit=_unit(a.key_kind, a.currency),
                        comparison_only=position == 0,
                    ),
                    when=lambda a, r, position=index: position < len(r.rows),
                ),
            )
        )
    return ResultProjection(tuple(facts))


RESULT_PROJECTION = _ranked_projection()


def present_ranked_comparison(
    arguments: RankedComparisonArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    inputs = [
        input_fact("key_label", arguments.key_label),
        input_fact("prefer", arguments.prefer),
    ]
    title = text("tools.calc.ranked_comparison.title", key=arguments.key_label)
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    return ToolCardPresentation(
        title=title,
        inputs=inputs,
        notes=[text("tools.calc.notes.ranked_not_recommended")],
    )


def get_ranked_comparison_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="ranked_comparison",
        description=(
            "Rank a set of products or instruments by one stated numeric key, "
            "preferring higher or lower values, and show each item's gap to the best. "
            "Items carry the figure a page or the user supplied; nothing is recommended. "
            "The ranked figures are rank_0, rank_1 and so on, from the best item."
        ),
        handler=compute_ranked_comparison,
        policy=replace(
            free_policy("prefer", "key_label", driving=()), public_receipt="cited_facts"
        ),
        progress=ToolProgressTemplate(
            locale_key="tools.calc.ranked_comparison.progress",
            argument_fields=("key_label",),
        ),
        card=ToolCardBinding(
            result_projection=RESULT_PROJECTION,
            card_type="ranked_comparison",
            version=1,
            presenter=present_ranked_comparison,
        ),
        domain=("Ranked by the stated key only; ties share a rank (decision 6).",),
    )
