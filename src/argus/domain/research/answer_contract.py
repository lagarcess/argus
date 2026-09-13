"""The research answer's typed shape: prose, cited rows, the pages it relies on and
its calculations.

It lives apart from ``contracts`` because tool contracts import research
contracts and the calculation catalogue imports tool contracts; the provider
schema that joins them is assembled here. Class and attribute docstrings are
the schema descriptions the provider reads, frozen by the recorded probe.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from argus.domain.calculations.answer_request import (
    MAX_ANSWER_CALCULATIONS,
    AnswerCalculation,
)
from argus.domain.research.contracts import RetrievedRow, TypedRetrieval, _strict_schema

# The provider-side name of the strict response schema. A schema change travels
# with a new name and a new recorded probe under it.
TYPED_ANSWER_SCHEMA_NAME = "argus_typed_answer_calculations"
# Questions the reader may ask next, bounded at parse time: a strict research
# model refuses an item bound in the schema.
MAX_FOLLOW_UP_QUESTIONS = 4
# Pages the answer names as relied on, bounded at parse time for the same reason.
MAX_SOURCE_URLS = 12


class TypedAnswer(TypedRetrieval):
    """A grounded answer: prose for the reader, every figure it states in digits as a cited row, the retrieved pages it relies on, one calculation Argus computes for each option the reader weighs, and the questions the reader may ask next."""

    model_config = ConfigDict(frozen=True, use_attribute_docstrings=True)

    answer_markdown: str
    """The answer for the reader in markdown: the direct answer first, then sections, a table, the formula, a worked example or steps where they help. No links, no list of sources, no mention of tools, providers or models. Every figure a calculation uses or produces is written as its reference."""
    rows: list[RetrievedRow]
    """Every figure answer_markdown states in digits, one row each, with the retrieved page it was read from."""
    source_urls: list[str] = Field(default_factory=list)
    """The URL of every retrieved page answer_markdown relies on, most relied on first."""
    calculations: list[AnswerCalculation] = Field(default_factory=list)
    """One calculation Argus computes for each option the reader weighs, with every input and its source; empty when the answer computes nothing."""
    follow_up_questions: list[str] = Field(default_factory=list)
    """Two to four short questions, in the reader's language, that this reader is likely to ask next."""
    declined: bool = False
    """True when the request is not a money question, or asks Argus to place a trade, move money or act on an account; answer_markdown then says so plainly."""

    @model_validator(mode="before")
    @classmethod
    def _one_calculation_shape(cls, data: Any) -> Any:
        # A response recorded under the one-calculation schema reads as a list of one.
        if (
            isinstance(data, dict)
            and "calculation" in data
            and "calculations" not in data
        ):
            data = dict(data)
            single = data.pop("calculation")
            data["calculations"] = [single] if single else []
        return data

    @field_validator("follow_up_questions")
    @classmethod
    def _bounded_questions(cls, value: list[str]) -> list[str]:
        return [text.strip() for text in value if text.strip()][:MAX_FOLLOW_UP_QUESTIONS]

    @field_validator("calculations")
    @classmethod
    def _bounded_calculations(
        cls, value: list[AnswerCalculation]
    ) -> list[AnswerCalculation]:
        return value[:MAX_ANSWER_CALCULATIONS]

    @field_validator("source_urls")
    @classmethod
    def _bounded_urls(cls, value: list[str]) -> list[str]:
        urls = [text.strip() for text in value if text.strip()]
        return list(dict.fromkeys(urls))[:MAX_SOURCE_URLS]


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
