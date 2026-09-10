"""Read back the cache and source-period rules actually used by research."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat

from argus.domain.research.cache import DataClass, data_class_for, ttl_for_packet
from argus.domain.research.contracts import ResearchSource
from argus.domain.research.source_selection import select_public_sources


class ResearchEvidencePolicy(BaseModel):
    """Cache retention is separate from a source's publication-period eligibility.

    This records resolved runtime policy. It does not assert that a retrieved
    figure is current, nor make retrieval time stand in for publication time.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    data_class: DataClass
    max_age_seconds: StrictFloat = Field(gt=0)
    question_kind: str | None = None
    period_start_date: date | None = None
    question_as_of_date: date | None = None
    current_survey: StrictBool = False
    closed_period: StrictBool = False

    def select_sources(
        self, sources: Iterable[ResearchSource]
    ) -> tuple[ResearchSource, ...]:
        """Apply the existing selector with the recorded source bounds."""
        return select_public_sources(
            sources,
            question_kind=self.question_kind,
            period_start=self.period_start_date,
            question_as_of=self.question_as_of_date,
            current_survey=self.current_survey,
        )


def build_research_evidence_policy(
    *,
    question_kind: str | None,
    categories: Sequence[str] = (),
    data_class: DataClass | None = None,
    closed_period: bool = False,
    withheld: bool = False,
    period_start_date: date | None = None,
    question_as_of_date: date | None = None,
    current_survey: bool = False,
) -> ResearchEvidencePolicy:
    """Resolve class and TTL through the cache owner; retain source bounds as given."""
    resolved_class = data_class_for(
        question_kind=question_kind,
        categories=categories,
        closed_period=closed_period,
        requested_data_class=data_class,
    )
    return ResearchEvidencePolicy(
        data_class=resolved_class,
        max_age_seconds=ttl_for_packet(
            question_kind=question_kind,
            categories=categories,
            closed_period=closed_period,
            withheld=withheld,
            data_class=resolved_class,
        ),
        question_kind=question_kind,
        period_start_date=period_start_date,
        question_as_of_date=question_as_of_date,
        current_survey=current_survey,
        closed_period=closed_period,
    )
