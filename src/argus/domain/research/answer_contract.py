"""The research answer's typed shape: prose, cited rows and at most one calculation.

It lives apart from ``contracts`` because tool contracts import research
contracts and the calculation catalogue imports tool contracts; the provider
schema that joins them is assembled here. Class and attribute docstrings are
the schema descriptions the provider reads, frozen by the recorded probe.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, field_validator

from argus.domain.calculations.answer_request import AnswerCalculation
from argus.domain.research.contracts import RetrievedRow, TypedRetrieval, _strict_schema

# The provider-side name of the strict response schema. A schema change travels
# with a new name and a new recorded probe under it.
TYPED_ANSWER_SCHEMA_NAME = "argus_typed_answer"
# Questions the reader may ask next, bounded at parse time: a strict research
# model refuses an item bound in the schema.
MAX_FOLLOW_UP_QUESTIONS = 4


class TypedAnswer(TypedRetrieval):
    """A grounded answer: prose for the reader, every figure it states in digits as a cited row, at most one calculation Argus computes, and the questions the reader may ask next."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    answer_markdown: str
    """The answer for the reader in markdown: the direct answer first, then sections, a table, the formula, a worked example or steps where they help. No links, no list of sources, no mention of tools, providers or models. Every figure the calculation uses or produces is written as its {{name}} reference."""
    rows: list[RetrievedRow]
    """Every figure answer_markdown states in digits, one row each, with the retrieved page it was read from."""
    calculation: AnswerCalculation | None = None
    """The one calculation Argus computes for this answer, with every input and its source, or null when the answer computes nothing."""
    follow_up_questions: list[str] = Field(default_factory=list)
    """Two to four short questions, in the reader's language, that this reader is likely to ask next."""

    @field_validator("follow_up_questions")
    @classmethod
    def _bounded_questions(cls, value: list[str]) -> list[str]:
        return [text.strip() for text in value if text.strip()][:MAX_FOLLOW_UP_QUESTIONS]


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
