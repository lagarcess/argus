"""The rendered facts available to an answer, with card display precedence."""

from argus.domain.tool_contracts import ToolCardPresentation, ToolFact


def presentation_reference_facts(
    presentation: ToolCardPresentation,
) -> dict[str, ToolFact]:
    facts = {fact.name: fact for fact in presentation.inputs if fact.value is not None}
    facts.update({row.name: row for row in presentation.rows})
    if presentation.answer is not None:
        facts[presentation.answer.name] = presentation.answer
    return facts
