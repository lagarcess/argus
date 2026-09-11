"""Show the Agent's returned sources without asking the model to recreate them."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal
from urllib.parse import quote

from babel.dates import format_date
from pydantic import create_model

from argus.domain.research.contracts import ResearchSource
from argus.domain.result_readout_grounding import (
    ResultReadoutDraft,
    ResultReadoutFigure,
    accepted_readout_text,
)


class ResultBreakdownDraft(ResultReadoutDraft):
    """The same small language, text and run-reference contract as Quick take."""


def result_breakdown_schema(facts: dict[str, Any]) -> type[ResultBreakdownDraft]:
    """Use the supplied labels as the model's allowed reference names."""
    labels = tuple(facts.get("facts", {}))
    if not labels:
        return ResultBreakdownDraft
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
    "We show the sources returned by search, so do not recreate a source list."
)


def _label(value: str) -> str:
    value = re.sub(r"[ \t]*—[ \t]*", ", ", value)
    return re.sub(r"([\\`*{}\[\]<>()])", r"\\\1", value).replace("\n", " ")


def accepted_breakdown_text(
    draft: object,
    *,
    facts: dict[str, Any],
    language: str,
    sources: tuple[ResearchSource, ...],
) -> tuple[str | None, str | None]:
    text, failure = accepted_readout_text(draft, facts=facts, language=language)
    if failure or text is None:
        return None, failure
    links = []
    for source in sources:
        label = _label(source.title or source.url)
        if source.source_date:
            try:
                source_date = format_date(
                    date.fromisoformat(source.source_date),
                    locale="es_MX" if language == "es-419" else "en",
                )
            except ValueError:
                source_date = source.source_date
            label += f" ({_label(source_date)})"
        links.append(f"- [{label}]({quote(source.url, safe='/:?&=#%+;,@~!$*-')})")
    return text + ("\n\n" + "\n".join(links) if links else ""), None
