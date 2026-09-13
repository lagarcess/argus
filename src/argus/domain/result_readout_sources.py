"""Show the Agent's returned sources without asking the model to recreate them."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import Field, create_model

from argus.domain.research.contracts import ResearchSource
from argus.domain.result_readout_grounding import (
    ResultReadoutDraft,
    ResultReadoutFigure,
    accepted_readout_text,
)
from argus.domain.result_readout_links import returned_source_links
from argus.domain.result_readout_quotes import readout_figure_keys


class ResultBreakdownDraft(ResultReadoutDraft):
    """The same small language, text and run-reference contract as Quick take."""


def result_breakdown_schema(facts: dict[str, Any]) -> type[ResultBreakdownDraft]:
    """Use the supplied labels as the model's allowed reference names."""
    labels = readout_figure_keys(facts)
    if not labels:
        return create_model(
            "ResultBreakdownDraft",
            __base__=ResultBreakdownDraft,
            figures=(list[ResultReadoutFigure], Field(max_length=0)),
        )
    figure = create_model(
        "ResultBreakdownFigure",
        __base__=ResultReadoutFigure,
        fact_key=(Literal[labels], ...),
    )
    return create_model(
        "ResultBreakdownDraft",
        __base__=ResultBreakdownDraft,
        figures=(list[figure], ...),
    )


BREAKDOWN_SOURCE_INSTRUCTIONS = (
    "Search the web for sources about what happened during this historical window. "
    "Use them to explain events and distinguish evidence from inference. "
    "The supplied run facts alone own this backtest's figures; web context must not replace them. "
    "Use short descriptive link text in the sentence the source supports, never a bare URL. "
    "We show the returned sources in a separate "
    "panel, so do not recreate a source list."
)


def accepted_breakdown_text(
    draft: object,
    *,
    facts: dict[str, Any],
    language: str,
    sources: Sequence[ResearchSource] = (),
) -> tuple[str | None, str | None]:
    """Keep the complete prose and in-text citations; sources travel separately."""
    text, failure = accepted_readout_text(draft, facts=facts, language=language)
    return (
        (returned_source_links(text, sources), None)
        if text is not None
        else (None, failure)
    )
