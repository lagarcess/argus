"""Two computed answers of the same kind, side by side, with their differences.

The differences are computed here, once, from the cards' own typed facts: a
fact on both cards in the same section, numeric on both and in the same unit,
gives right minus left, rounded the way the card rounds that unit. Nothing is
compared across kinds, and rankings compare only when they rank the same items
by the same measure; a fact that is not numeric on both cards, or that is
counted in another currency, has no difference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from argus.domain.calculations._shared import (
    MONEY_DECIMALS,
    PERCENT_DECIMALS,
    UNIT_CURRENCY_KEY,
    UNIT_PERCENT_KEY,
)
from argus.domain.tool_contracts import LocalizedText, ToolFact, ToolResultCard

FactSection = Literal["answer", "row", "input"]
OTHER_DECIMALS = 4


class ComparisonKindMismatch(ValueError):
    """Two answers of different kinds have nothing to line up."""


@dataclass(frozen=True)
class FactDifference:
    section: FactSection
    name: str
    label: LocalizedText
    unit: LocalizedText | None
    left: float
    right: float
    difference: float


def card_differences(left: ToolResultCard, right: ToolResultCard) -> list[FactDifference]:
    """Right minus left for every fact both cards state as a number in one unit."""
    if left.tool_name != right.tool_name:
        raise ComparisonKindMismatch("Only answers of the same kind can be compared.")
    if _ranking(left) != _ranking(right):
        raise ComparisonKindMismatch(
            "Only rankings of the same items by the same measure can be compared."
        )
    others = {(section, fact.name): fact for section, fact in _facts(right)}
    differences: list[FactDifference] = []
    for section, fact in _facts(left):
        other = others.get((section, fact.name))
        if other is None or not _numeric(fact.value) or not _numeric(other.value):
            continue
        if _unit_identity(fact) != _unit_identity(other):
            continue
        left_value, right_value = float(fact.value), float(other.value)
        differences.append(
            FactDifference(
                section=section,
                name=fact.name,
                label=fact.label,
                unit=fact.unit,
                left=left_value,
                right=right_value,
                difference=round(right_value - left_value, _decimals(fact)),
            )
        )
    return differences


def _ranking(card: ToolResultCard) -> tuple[object, ...] | None:
    """What a ranking ranks: its measure, preference and items. Its facts are
    positions, so two rankings line up only when all of these match."""
    arguments = card.arguments or {}
    items = arguments.get("items")
    if "key_label" not in arguments or not isinstance(items, list):
        return None
    identities = sorted(
        (str(item.get("label") or "").casefold(), str(item.get("symbol") or "").upper())
        for item in items
        if isinstance(item, dict)
    )
    return (
        str(arguments.get("key_label") or "").casefold(),
        arguments.get("key_kind"),
        arguments.get("prefer"),
        tuple(identities),
    )


def _facts(card: ToolResultCard) -> list[tuple[FactSection, ToolFact]]:
    presentation = card.presentation
    facts: list[tuple[FactSection, ToolFact]] = []
    if card.outcome.status == "succeeded":
        if presentation.answer is not None:
            facts.append(("answer", presentation.answer))
        facts.extend(("row", fact) for fact in presentation.rows)
    facts.extend(("input", fact) for fact in presentation.inputs)
    return facts


def _numeric(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _unit_identity(fact: ToolFact) -> tuple[str, tuple[tuple[str, str], ...]] | None:
    if fact.unit is None:
        return None
    return (
        fact.unit.locale_key,
        tuple(
            sorted(
                (key, str(value)) for key, value in fact.unit.interpolation_args.items()
            )
        ),
    )


def _decimals(fact: ToolFact) -> int:
    key = fact.unit.locale_key if fact.unit is not None else ""
    if key == UNIT_CURRENCY_KEY:
        return MONEY_DECIMALS
    if key == UNIT_PERCENT_KEY:
        return PERCENT_DECIMALS
    return OTHER_DECIMALS
