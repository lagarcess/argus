"""Contracts for public evidence receipts.

A receipt is an immutable, sanitized snapshot of one completed backtest.
``PublicExcerptPayload`` is the closed public payload: every model here sets
``extra="forbid"`` so a field cannot reach a public page without a schema
change and the review that comes with it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from argus.api.public_excerpt_fact_schemas import PublicExcerptFactBank
from argus.api.schemas import AssetClass, Language

PUBLIC_EXCERPT_SCHEMA_VERSION = 1
PUBLIC_EXCERPT_OWNER_NOTE_MAX_LENGTH = 280
PUBLIC_EXCERPT_ROBOTS_DIRECTIVE = "noindex, nofollow"

RevocationReason = Literal["owner_revoked", "source_deleted", "removed_by_argus"]
PublicExcerptStatus = Literal["available", "revoked"]


class PublicExcerptDateRange(BaseModel):
    """The tested window, frozen as two dates and rendered in the viewer's locale.

    No rendered ``display`` string: the run writes one in the author's language, and
    a receipt is opened by strangers whose language has nothing to do with the
    author's. Two ISO dates carry the same fact and can be spoken by anyone.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: str
    end: str


# Exactly what a receipt can carry, and nothing aspirational. The first five are
# the result card's own row keys; the last two are read from the run's metrics
# because the card renders that comparison as an English sentence rather than a
# number. `contribution_return_pct` is the recurring-plan headline: a simple
# return on contributed cash, never comparable with `total_return_pct`. A key
# the projection does not know is refused rather than dropped, and
# `tests/test_public_excerpt_language.py` drives the production generator across
# every executable template to keep this set honest.
MetricKey = Literal[
    "cash_value",
    "total_return_pct",
    "contribution_return_pct",
    "max_drawdown_pct",
    "win_rate",
    "benchmark_return_pct",
    "delta_vs_benchmark_pct",
]


class PublicExcerptMetric(BaseModel):
    """One result number, frozen as the run reported it, under a closed key.

    No frozen label, for the same reason the strategy facts and the assumptions have
    none: the run writes it in the author's language.

    ``value`` is the run's own display string, which is digits and a percent sign and
    reads the same in either language. ``delta_vs_benchmark_pct`` is the one
    exception and carries a bare signed number, because its unit is percentage
    points and every way of writing that unit is a word. The page supplies the word.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: MetricKey
    value: str


StrategyFactKey = Literal[
    "strategy_type",
    "cadence",
    "indicator",
    "indicator_period",
    "entry_threshold",
    "exit_threshold",
    # A crossover is defined by both of its windows, so neither one is optional.
    "fast_indicator",
    "fast_period",
    "slow_indicator",
    "slow_period",
    # Entry and exit are compiled independently and need not match, so when they
    # differ the exit side gets its own facts rather than being spoken for.
    "exit_fast_indicator",
    "exit_fast_period",
    "exit_slow_indicator",
    "exit_slow_period",
    "signal_period",
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


AssumptionKey = Literal[
    # Structural, and true of every Argus run by construction.
    "long_only",
    "equal_weight",
    # Execution costs. Either the run modeled none, or it modeled both numbers.
    "no_costs",
    "modeled_fee_bps",
    "modeled_slippage_bps",
    # What the result was measured against. The two forms are exclusive: the second
    # says the benchmark carried the same modeled costs the strategy did.
    "benchmark",
    "benchmark_same_modeled_costs",
    # Recurring contribution runs. The plan declares all three, so none is absent.
    "recurring_contribution",
    "contribution_cadence",
    "starting_principal",
    "fractional_shares",
]


class PublicExcerptAssumption(BaseModel):
    """One assumption the run was executed under, frozen as a key and a value.

    Same discipline as :class:`PublicExcerptStrategyFact`, and for the same reason:
    the sentence is composed at view time in the viewer's language while the value
    stays frozen. ``value`` is the raw scalar the run reported, so a number is a
    number here and gets its separators from the viewer's locale, not the author's.

    Keys with nothing to measure carry no value: ``long_only`` is the whole fact.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: AssumptionKey
    value: str | None = None


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
    # No frozen strategy label: it named a category in the author's language while
    # strategy_facts already carries the shape as a closed key. Two names for one
    # thing, one of them untranslatable.
    strategy_facts: list[PublicExcerptStrategyFact] = Field(default_factory=list)
    assumptions: list[PublicExcerptAssumption] = Field(default_factory=list)
    date_range: PublicExcerptDateRange
    metrics: list[PublicExcerptMetric] = Field(default_factory=list)
    benchmark_symbol: str | None = None
    visual: PublicExcerptVisual | None = None
    owner_note: str | None = None
    content_language: Language = "en"
    framing: Literal["historical_simulation_not_advice"] = (
        "historical_simulation_not_advice"
    )
    provenance_mark: Literal["tested_with_argus"] = "tested_with_argus"


# A request-size bound, not a product rule: how many message ids one
# selection request may carry. No conversation reaches it, nothing tells the
# owner about it, and it exists so a request of nonexistent ids cannot buy
# unbounded work before it is refused.
PUBLIC_EXCERPT_SELECTION_REQUEST_LIMIT = 500
PublicExcerptKind = Literal["backtest", "research_answer", "mixed"]
PublicExcerptRefusalReason = Literal[
    "not_completed",
    "unsupported_turn",
    "unsupported_shape",
    "missing_sources",
    "degraded",
    "memory_used",
    "missing_question",
    "text_too_long",
    "unsafe_text",
    "unlisted_url",
    "invalid_selection",
    "preview_changed",
    "invalid_source",
    "unsupported_backtest",
]
PublicExcerptRefusalField = Literal["question", "answer", "owner_note", "sources"]


class PublicExcerptResearchSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    title: str
    domain: str
    url: str
    source_date: str | None = None


class PublicExcerptOfferedNextStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["research_test_single", "research_test_versus"]
    symbols: list[str] = Field(min_length=1, max_length=5)


class PublicExcerptResearchTurn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["research_answer"] = "research_answer"
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=4000)
    sources: list[PublicExcerptResearchSource] = Field(min_length=1, max_length=5)
    retrieved_at: datetime
    anchor_symbols: list[str] = Field(default_factory=list, max_length=5)
    asset_class: AssetClass | None = None
    offered_next_step: PublicExcerptOfferedNextStep | None = None
    owner_note: str | None = Field(default=None, max_length=280)
    content_language: Language = "en"
    framing: Literal["research_snapshot_not_advice"] = "research_snapshot_not_advice"
    provenance_mark: Literal["tested_with_argus"] = "tested_with_argus"


class PublicExcerptBacktestTurn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["backtest"] = "backtest"
    idea_title: str
    fact_bank: PublicExcerptFactBank
    visual: PublicExcerptVisual | None = None
    owner_note: str | None = Field(default=None, max_length=280)
    content_language: Language = "en"
    framing: Literal["historical_simulation_not_advice"] = (
        "historical_simulation_not_advice"
    )
    provenance_mark: Literal["tested_with_argus"] = "tested_with_argus"


PublicExcerptTurn = Annotated[
    PublicExcerptResearchTurn | PublicExcerptBacktestTurn, Field(discriminator="kind")
]


class PublicExcerptTurnsPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: Literal[2] = 2
    kind: Literal["turns"] = "turns"
    turns: list[PublicExcerptTurn] = Field(
        min_length=1, max_length=PUBLIC_EXCERPT_SELECTION_REQUEST_LIMIT
    )


PublicExcerptDocument = PublicExcerptPayload | PublicExcerptTurnsPayload
PUBLIC_EXCERPT_DOCUMENT_ADAPTER = TypeAdapter(PublicExcerptDocument)


class PublicExcerptSnapshot(BaseModel):
    """The owner-visible record. ``owner_id`` and the source ids stay private."""

    model_config = ConfigDict(frozen=True)

    id: str
    public_id: str
    owner_id: str
    evidence_artifact_id: str | None = None
    source_conversation_id: str | None = None
    source_run_id: str | None = None
    source_message_ids: list[str] = Field(default_factory=list)
    source_run_ids: list[str] = Field(default_factory=list)
    source_artifact_ids: list[str] = Field(default_factory=list)
    selection_key: str | None = None
    kind: PublicExcerptKind = "backtest"
    title: str
    payload: PublicExcerptDocument
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
    date_range: PublicExcerptDateRange | None = None
    kind: PublicExcerptKind = "backtest"
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
    kind: PublicExcerptKind = "backtest"


class PublicExcerptView(BaseModel):
    """Everything an unauthenticated viewer receives. Nothing else exists here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    public_id: str
    status: PublicExcerptStatus
    kind: PublicExcerptKind | None = None
    indexing: Literal["noindex, nofollow"] = PUBLIC_EXCERPT_ROBOTS_DIRECTIVE
    created_at: datetime | None = None
    payload: PublicExcerptDocument | None = None


class PublicExcerptSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_ids: list[UUID] = Field(
        min_length=1, max_length=PUBLIC_EXCERPT_SELECTION_REQUEST_LIMIT
    )
    owner_note: str | None = None

    @field_validator("message_ids")
    @classmethod
    def distinct_messages(cls, values: list[UUID]) -> list[UUID]:
        if len(set(values)) != len(values):
            raise ValueError("message_ids must be distinct")
        return values


class PublicExcerptSelectionCreate(PublicExcerptSelection):
    payload_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class PublicExcerptCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    message_id: str
    question: str | None = None
    kind: Literal["backtest", "research_answer"] | None = None
    eligible: bool
    reason: PublicExcerptRefusalReason | None = None
    field: PublicExcerptRefusalField | None = None


class PublicExcerptCandidates(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    items: list[PublicExcerptCandidate]


class PublicExcerptPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    payload: PublicExcerptDocument
    payload_digest: str
    kind: PublicExcerptKind
    existing_receipt: PublicExcerptListItem | None = None
