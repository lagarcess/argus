"""Contracts for public evidence receipts.

A receipt is an immutable, sanitized snapshot of one completed backtest.
``PublicExcerptPayload`` is the closed public payload: every model here sets
``extra="forbid"`` so a field cannot reach a public page without a schema
change and the review that comes with it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from argus.api.schemas import AssetClass, Language

PUBLIC_EXCERPT_SCHEMA_VERSION = 1
PUBLIC_EXCERPT_OWNER_NOTE_MAX_LENGTH = 280
PUBLIC_EXCERPT_ROBOTS_DIRECTIVE = "noindex, nofollow"

RevocationReason = Literal["owner_revoked", "source_deleted"]
PublicExcerptStatus = Literal["available", "revoked"]


class PublicExcerptDateRange(BaseModel):
    """The tested window, frozen as the run reported it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: str
    end: str
    display: str


class PublicExcerptMetric(BaseModel):
    """One result metric, already formatted for reading."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    label: str
    value: str


StrategyFactKey = Literal[
    "strategy_type",
    "cadence",
    "indicator",
    "indicator_period",
    "entry_threshold",
    "exit_threshold",
    "direction",
]


class PublicExcerptStrategyFact(BaseModel):
    """One fact that defines the executed strategy, frozen from the run.

    ``key`` is a closed enum and the label is rendered from it at view time, so the
    viewer reads it in their own language while ``value`` stays frozen. The
    alternative, freezing an English label, would put untranslatable chrome inside
    the payload.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: StrategyFactKey
    value: str


class PublicExcerptVisualPoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    time: str
    value: float


class PublicExcerptVisual(BaseModel):
    """Frozen visual evidence. No series is fetched at view time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["portfolio_equity"]
    currency: str | None = None
    base_value: float | None = None
    series: list[PublicExcerptVisualPoint]


class PublicExcerptPayload(BaseModel):
    """The closed receipt payload. Adding a field here is a product decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = PUBLIC_EXCERPT_SCHEMA_VERSION
    idea_title: str
    asset_class: AssetClass | None = None
    symbols: list[str] = Field(default_factory=list)
    strategy_label: str | None = None
    # The label alone names a category. For anything but buy and hold it does not
    # identify what was executed, so the defining parameters are frozen beside it.
    strategy_facts: list[PublicExcerptStrategyFact] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    date_range: PublicExcerptDateRange
    metrics: list[PublicExcerptMetric] = Field(default_factory=list)
    benchmark_symbol: str | None = None
    benchmark_note: str | None = None
    visual: PublicExcerptVisual | None = None
    owner_note: str | None = None
    content_language: Language = "en"
    framing: Literal["historical_simulation_not_advice"] = (
        "historical_simulation_not_advice"
    )
    provenance_mark: Literal["tested_with_argus"] = "tested_with_argus"


class PublicExcerptSnapshot(BaseModel):
    """The owner-visible record. ``owner_id`` and the source ids stay private."""

    model_config = ConfigDict(frozen=True)

    id: str
    public_id: str
    owner_id: str
    evidence_artifact_id: str | None = None
    source_conversation_id: str | None = None
    source_run_id: str | None = None
    title: str
    payload: PublicExcerptPayload
    payload_digest: str
    created_at: datetime
    revoked_at: datetime | None = None
    revocation_reason: RevocationReason | None = None


class PublicExcerptListItem(BaseModel):
    """One row of the owner's receipt list in Data Controls."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    public_id: str
    path: str
    title: str
    symbols: list[str] = Field(default_factory=list)
    date_range_display: str
    created_at: datetime
    revoked_at: datetime | None = None
    revocation_reason: RevocationReason | None = None


class PublicExcerptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_note: str | None = Field(
        default=None,
        max_length=PUBLIC_EXCERPT_OWNER_NOTE_MAX_LENGTH,
    )


class PublicExcerptCreateResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt: PublicExcerptListItem


class PublicExcerptListResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    items: list[PublicExcerptListItem]
    next_cursor: str | None = None


class PublicExcerptRevokeResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    receipt: PublicExcerptListItem


class PublicExcerptFunnelStage(BaseModel):
    """One viewer-side funnel stage. There is deliberately nothing else in it.

    ``viewed`` is reported by the rendered page rather than counted on the read
    endpoint, which also answers metadata passes and preview-image renders.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: Literal["viewed", "try_argus"]


class PublicExcerptView(BaseModel):
    """Everything an unauthenticated viewer receives. Nothing else exists here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    public_id: str
    status: PublicExcerptStatus
    indexing: Literal["noindex, nofollow"] = PUBLIC_EXCERPT_ROBOTS_DIRECTIVE
    created_at: datetime | None = None
    payload: PublicExcerptPayload | None = None
