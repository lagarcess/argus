"""Typed wire inputs for the financial loop and its review step."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from argus.domain.recording.schemas import WriteOpeningRequest

CATEGORY_IDS = (
    "other",
    "groceries",
    "dining",
    "transport",
    "housing",
    "health",
    "shopping",
    "interest_fees",
)


class CoverageAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_id: str
    included: bool


class ActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    expected_revision: int | None = Field(default=None, ge=1)
    amount: str = Field(max_length=40)
    occurred_at: datetime
    time_zone: str = Field(default="America/Santo_Domingo", max_length=64)
    note: str | None = Field(default=None, max_length=200)
    category_id: str | None = None
    reason: str | None = Field(default=None, max_length=200)
    coverage: list[CoverageAnswer] = Field(default_factory=list, max_length=1000)
    preview_token: str | None = Field(default=None, max_length=128)


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    amount: str = Field(max_length=40)
    as_of: datetime
    time_zone: str = Field(default="America/Santo_Domingo", max_length=64)
    source: Literal["manual"] = "manual"
    note: str | None = Field(default=None, max_length=200)
    preview_token: str | None = Field(default=None, max_length=128)


class OpeningCoverageAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_id: str
    included: bool


class LoopOpeningRequest(WriteOpeningRequest):
    coverage: list[OpeningCoverageAnswer] = Field(default_factory=list, max_length=1000)
    preview_token: str | None = Field(default=None, max_length=128)
