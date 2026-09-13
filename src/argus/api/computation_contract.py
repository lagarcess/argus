"""Computed answers outside a chat turn: listed, compared, continued, refreshed.

Comparing and continuing are free and call no model or provider. Refreshing
the cited inputs is the one paid action; the user starts it and reviews the
result beside the stored answer, which is never rewritten.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from argus.api.decision_contract import DecisionComputation, DecisionRerun
from argus.api.schemas import Conversation
from argus.domain.tool_contracts import LocalizedText

MAX_LISTED_ANSWERS = 10


class ComputedAnswerRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(min_length=1, max_length=64)
    message_id: str = Field(min_length=1, max_length=64)


class ComputedAnswerSummary(BaseModel):
    """One owned computed answer a comparison can pick."""

    conversation_id: str
    message_id: str
    kind: str = Field(max_length=80)
    asked: str | None = Field(default=None, max_length=500)
    computed_at: datetime
    symbols: list[str] = Field(default_factory=list, max_length=5)


class ComputedAnswerList(BaseModel):
    items: list[ComputedAnswerSummary] = Field(max_length=MAX_LISTED_ANSWERS)


class ComputationCompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left: ComputedAnswerRef
    right: ComputedAnswerRef


class ComparedAnswer(BaseModel):
    conversation_id: str
    message_id: str
    asked: str | None = Field(default=None, max_length=500)
    computed_at: datetime
    card: dict[str, Any]


class ComputationDifference(BaseModel):
    """Right minus left for one fact both cards state as a number in one unit."""

    section: Literal["answer", "row", "input"]
    name: str
    label: LocalizedText
    unit: LocalizedText | None = None
    left: float
    right: float
    difference: float


class ComputationComparison(BaseModel):
    kind: str
    left: ComparedAnswer
    right: ComparedAnswer
    differences: list[ComputationDifference]


class ContinuedResultResponse(BaseModel):
    """The new chat and the one message that carries the continued result."""

    conversation: Conversation
    message_id: str


ComputationRefreshStatus = Literal["refreshed", "inputs_not_found"]


class ComputationRefreshResponse(BaseModel):
    """Freshly retrieved inputs computed beside the stored answer.

    ``refreshed`` carries one recomputed card per calculation in ``reruns``, in
    the computation's order; ``inputs_not_found`` means the retrieval named no
    cited input, so nothing was recomputed. ``sources`` lists the pages the
    retrieval read, dated.
    """

    computation: DecisionComputation
    status: ComputationRefreshStatus
    reruns: list[DecisionRerun] = Field(default_factory=list, max_length=4)
    sources: list[dict[str, Any]] = Field(default_factory=list)
