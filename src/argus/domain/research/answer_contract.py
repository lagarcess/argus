"""The research answer's typed shape: prose, cited rows and at most one calculation.

It lives apart from ``contracts`` because tool contracts import research
contracts and the calculation catalogue imports tool contracts; the provider
schema that joins them is assembled here. Class and attribute docstrings are
the schema descriptions the provider reads, frozen by the recorded probe.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict

from argus.domain.calculations.answer_request import AnswerCalculation
from argus.domain.research.contracts import RetrievedRow, TypedRetrieval, _strict_schema

# The provider-side name of the strict response schema. A schema change travels
# with a new name and a new recorded probe under it.
TYPED_ANSWER_SCHEMA_NAME = "argus_typed_answer"


class TypedAnswer(TypedRetrieval):
    """A grounded answer: prose for the reader, every figure it states in digits as a cited row, and at most one calculation Argus computes."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    answer_markdown: str
    """The answer for the reader in markdown: no links, no list of sources, no mention of tools, providers or models. Every figure the calculation uses or produces is written as its {{name}} reference."""
    rows: list[RetrievedRow]
    """Every figure answer_markdown states in digits, one row each, with the retrieved page it was read from."""
    calculation: AnswerCalculation | None = None
    """The one calculation Argus computes for this answer, with every input and its source, or null when no computed figure is needed."""


def typed_answer_json_schema() -> dict[str, Any]:
    """The strict request schema, derived from the model the parser validates."""
    schema = TypedAnswer.model_json_schema()
    definitions = schema.pop("$defs", {})
    return _strict_schema(schema, definitions)


def typed_answer_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": TYPED_ANSWER_SCHEMA_NAME,
            "strict": True,
            "schema": typed_answer_json_schema(),
        },
    }
