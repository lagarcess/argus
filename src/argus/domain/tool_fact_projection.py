"""Result facts own the names both a card and an answering model can reference.

Factories receive the declared name; values, units and labels still use each
calculation's existing presenter helpers. Conditions apply before factories run,
so an absent optional result is never manufactured for the catalogue.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from argus.domain.tool_contracts import ToolFact

FactFactory = Callable[[str, Any, Any], ToolFact]
FactCondition = Callable[[Any, Any], bool]


@dataclass(frozen=True)
class ResultReference:
    name: str
    conditional: bool


@dataclass(frozen=True)
class ResultFact:
    name: str
    factory: FactFactory
    placement: Literal["answer", "row", "answer_and_row"] = "row"
    when: FactCondition | None = None


@dataclass(frozen=True)
class ResultProjection:
    facts: tuple[ResultFact, ...]

    @property
    def references(self) -> tuple[ResultReference, ...]:
        """Possible names, marking ones whose presence depends on the result."""
        conditions: dict[str, bool] = {}
        for fact in self.facts:
            conditions[fact.name] = (
                conditions.get(fact.name, True) and fact.when is not None
            )
        return tuple(
            ResultReference(name, conditional) for name, conditional in conditions.items()
        )

    def render(
        self, arguments: Any, result: Any
    ) -> tuple[ToolFact | None, list[ToolFact]]:
        answer: ToolFact | None = None
        rows: list[ToolFact] = []
        for spec in self.facts:
            if spec.when is not None and not spec.when(arguments, result):
                continue
            fact = spec.factory(spec.name, arguments, result).model_copy(
                update={"name": spec.name}
            )
            if spec.placement in {"answer", "answer_and_row"}:
                if answer is not None:
                    raise ValueError("A result projection produced more than one answer")
                answer = fact
            if spec.placement != "answer":
                rows.append(fact)
        return answer, rows


def solved_facts(fields: tuple[str, ...], factory: FactFactory) -> tuple[ResultFact, ...]:
    """Each existing unknown can become the answer; the rule owns its domain."""
    return tuple(
        ResultFact(
            name,
            factory,
            placement="answer",
            when=lambda _a, r, key=name: r.solved_field == key,
        )
        for name in fields
    )
