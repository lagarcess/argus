"""Neutral tool transports; importing these types never loads the tool catalog.

Arguments and returns are validated by each declaration. These envelopes carry
them without pretending every tool has the same inputs or financial result.
"""

from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from argus.domain.research.contracts import ResearchSource

ToolScalar = StrictBool | StrictInt | StrictFloat | StrictStr | None
ToolFailureStatus = Literal["invalid", "ambiguous", "bounded", "unavailable"]
ToolStatus = Literal["succeeded", ToolFailureStatus]
MAX_TOOL_CALLS = 8


class ToolContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ToolCall(ToolContract):
    tool_name: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    call_id: str = Field(min_length=1, max_length=128)
    arguments: dict[str, JsonValue] = Field(default_factory=dict)


class ToolFailure(ToolContract):
    code: str = Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_]*$")
    fields: list[str] = Field(default_factory=list)


class ToolOutcome(ToolContract):
    status: ToolStatus
    result: dict[str, JsonValue] | None = None
    failure: ToolFailure | None = None

    @model_validator(mode="after")
    def answer_and_failure_are_exclusive(self) -> ToolOutcome:
        if self.status == "succeeded":
            if self.result is None or self.failure is not None:
                raise ValueError("A successful tool must have a result and no failure")
        elif self.result is not None or self.failure is None:
            raise ValueError("An unsuccessful tool must have a failure and no result")
        return self


class LocalizedText(ToolContract):
    locale_key: str = Field(min_length=1, max_length=160)
    interpolation_args: dict[str, ToolScalar] = Field(default_factory=dict)


class ToolProgress(LocalizedText):
    call_id: str
    tool_name: str


class ToolFact(ToolContract):
    name: str
    label: LocalizedText
    value: ToolScalar
    value_text: LocalizedText | None = None
    unit: LocalizedText | None = None


class ToolInputFact(ToolFact):
    editable: bool = False
    unknown: bool = False
    visibility: Literal["public", "private"] = "private"

    @model_validator(mode="after")
    def unknown_is_blank_and_read_only(self) -> ToolInputFact:
        if self.unknown and (self.value is not None or self.editable):
            raise ValueError("The retained unknown must be blank and read-only")
        return self


class ToolVisualPoint(ToolContract):
    time: str
    value: StrictFloat


class ToolVisual(ToolContract):
    """Frozen visual evidence owned by the tool card, without a later fetch."""

    kind: Literal["portfolio_equity"]
    currency: str | None = None
    base_value: StrictFloat | None = None
    series: list[ToolVisualPoint]


class ToolCardPresentation(ToolContract):
    title: LocalizedText
    answer: ToolFact | None = None
    narrative: str | None = None
    sources: list[ResearchSource] = Field(default_factory=list)
    visual: ToolVisual | None = None
    rows: list[ToolFact] = Field(default_factory=list)
    inputs: list[ToolInputFact] = Field(default_factory=list)
    notes: list[LocalizedText] = Field(default_factory=list)


class ToolResultCard(ToolContract):
    kind: Literal["tool_result"] = "tool_result"
    schema_version: Literal[1] = 1
    tool_name: str
    call_id: str
    artifact_id: str
    input_revision: int = Field(default=0, ge=0)
    card_type: str = Field(min_length=1)
    card_version: int = Field(ge=1)
    arguments: dict[str, JsonValue]
    outcome: ToolOutcome
    presentation: ToolCardPresentation
    artifact_state: Literal["active", "consumed", "cancelled", "superseded"] = "active"

    @model_validator(mode="after")
    def failure_cannot_present_an_answer(self) -> ToolResultCard:
        if self.outcome.status != "succeeded" and (
            self.presentation.answer is not None
            or self.presentation.narrative is not None
            or self.presentation.visual is not None
        ):
            raise ValueError("A failed or bounded tool cannot present an answer")
        return self
