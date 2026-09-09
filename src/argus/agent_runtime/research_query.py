"""Research question shape owned by the primary structured interpreter."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from argus.domain.research.cache import DataClass
from argus.domain.research.contracts import CapabilityClass, QuestionShape


class ResearchQueryExtraction(BaseModel):
    """One interpreter-owned question shape, shared by both rail entries."""

    question_kind: Literal[
        "live_quote",
        "company_lookup",
        "cross_company",
        "etf_constituents",
        "market_pulse",
        "screening",
        "sector_radar",
        "find_assets",
        "market_stats",
        "current_external",
        "concept",
        "none",
    ] = Field(
        description=(
            "Shape of a finance question, not an execution request. live_quote: only "
            "a current price, quote, level, market cap, multiple or pre/after-hours "
            "figure. A request also asking why, what changed, or growth drivers is "
            "not live_quote in any language. company_lookup: one company's history, "
            "fundamentals, financial statements, earnings, business model, peers or "
            "explanation. cross_company: comparison or multi-year trend analysis of "
            "named companies, sectors or funds, with every subject already named. "
            "etf_constituents: fund holdings or weights. market_pulse: current market "
            "or index moves, gainers, losers or most-active assets. screening: assets "
            "that must satisfy any stated condition or threshold, regardless of "
            "phrasing. sector_radar: an industry's performance or drivers. "
            "find_assets: names or ideas by similarity/category with no performance "
            "condition and not every desired asset named. market_stats: historical "
            "asset statistics or price behavior over a period. current_external: "
            "news, events or macro facts outside those shapes. concept: a general "
            "term or mechanism, no specific company. none: everything else, including "
            "requests to build or run a test. Counterfactual investment simulations "
            "are build requests, not market_stats."
        )
    )
    symbols: list[str] = Field(
        default_factory=list,
        description=(
            "Provider tickers for question subjects; map well-known indexes to their "
            "liquid proxy (S&P 500 -> SPY). These are research subjects, not traded assets."
        ),
    )
    asset_class_hint: Literal["equity", "crypto", "currency_pair"] | None = None
    period_of_interest: str | None = Field(
        default=None, description="Time window exactly as the user phrased it."
    )
    period_is_closed_window: bool = Field(
        default=False,
        description="True only for a window entirely in the past, such as a finished year or quarter.",
    )
    period_start_date: date | None = Field(
        default=None,
        description="Earliest ISO date implied by the requested period, including relative periods, using the current runtime date; null without a period.",
    )
    requires_publisher_sources: bool = Field(
        default=False,
        description="True for narrative, causal or explanatory claims requiring a publisher page; false for a pure market-data number. True can never use live_quote.",
    )
    date_range_raw_text: str | None = Field(
        default=None, description="Same user-stated text as period_of_interest."
    )
    discovery_category: str | None = Field(
        default=None, description="The user's own category or theme phrase, if any."
    )
    screening_criteria: list[str] = Field(
        default_factory=list,
        description="Every stated condition in the user's own words, including their category or sector, one per entry.",
    )
    sector_of_interest: str | None = Field(
        default=None, description="The industry, sector or theme named by the user."
    )


class ResearchOperationQuery(BaseModel):
    """Validated operation facts passed to the existing retrieval machinery.

    This internal request is never a model-facing tool input. A registered
    handler supplies its execution policy directly; legacy question-kind
    consumers receive no classifier value from it.
    """

    model_config = ConfigDict(frozen=True)

    shape: QuestionShape
    capability_class: CapabilityClass
    data_class: DataClass
    symbols: list[str] = Field(default_factory=list)
    asset_class_hint: Literal["equity", "crypto", "currency_pair"] | None = None
    period_of_interest: str | None = None
    period_is_closed_window: bool = False
    period_start_date: date | None = None
    requires_publisher_sources: bool = False
    survey: bool = False
    screening_criteria: list[str] = Field(default_factory=list)
    sector_of_interest: str | None = None

    @property
    def question_kind(self) -> None:
        """Compatibility readers get no question classifier on this path."""
        return None

    @property
    def date_range_raw_text(self) -> str | None:
        return self.period_of_interest
