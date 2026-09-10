"""Runtime policy readback retains cache and publisher-date boundaries separately."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from argus.domain.research import cache
from argus.domain.research.contracts import ResearchSource
from argus.domain.research.evidence_policy import (
    ResearchEvidencePolicy,
    build_research_evidence_policy,
)
from pydantic import ValidationError


@pytest.mark.parametrize(
    "arguments",
    [
        {"question_kind": "live_quote"},
        {"question_kind": "find_assets"},
        {"question_kind": "company_lookup", "categories": ("earnings_transcript",)},
        {"question_kind": "cross_company", "data_class": "fundamentals"},
        {"question_kind": "live_quote", "closed_period": True},
        {"question_kind": "company_lookup", "withheld": True},
    ],
)
def test_policy_reads_the_existing_cache_class_and_ttl(arguments):
    policy = build_research_evidence_policy(**arguments)

    class_arguments = {
        key: value for key, value in arguments.items() if key != "withheld"
    }
    if "data_class" in class_arguments:
        class_arguments["requested_data_class"] = class_arguments.pop("data_class")
    assert policy.data_class == cache.data_class_for(**class_arguments)
    assert policy.max_age_seconds == cache.ttl_for_packet(**arguments)
    assert ResearchEvidencePolicy.model_validate_json(policy.model_dump_json()) == policy
    with pytest.raises(ValidationError):
        policy.max_age_seconds = 0


def test_policy_observes_a_changed_canonical_ttl(monkeypatch):
    monkeypatch.setitem(cache.DATA_CLASS_TTL_SECONDS, "movers", 41.0)
    assert (
        build_research_evidence_policy(question_kind="find_assets").max_age_seconds == 41
    )


@pytest.mark.parametrize("max_age", [0, -1, float("nan"), float("inf")])
def test_invalid_retained_max_age_is_not_a_policy(max_age):
    raw = build_research_evidence_policy(question_kind="find_assets").model_dump()
    with pytest.raises(ValidationError):
        ResearchEvidencePolicy.model_validate({**raw, "max_age_seconds": max_age})


def _sources(as_of: date) -> tuple[ResearchSource, ...]:
    dates = (
        (as_of - timedelta(days=2)).isoformat(),
        (as_of - timedelta(days=1)).isoformat(),
        as_of.isoformat(),
        (as_of + timedelta(days=1)).isoformat(),
        "unparseable publication date",
        None,
    )
    return tuple(
        ResearchSource(url=f"https://publisher-{index}.example/story", source_date=value)
        for index, value in enumerate(dates)
    )


def test_closed_window_selects_publisher_dates_independently_of_cache_age():
    as_of = date(2026, 9, 9)
    policy = build_research_evidence_policy(
        question_kind="live_quote",
        period_start_date=as_of - timedelta(days=1),
        question_as_of_date=as_of,
        closed_period=True,
    )
    sources = _sources(as_of)

    assert policy.data_class == "closed_ohlcv"
    assert policy.select_sources(sources) == (sources[1], sources[2], sources[5])
    # A long retention window does not certify an old, malformed or future article.
    assert policy.max_age_seconds == cache.ttl_for_packet(
        question_kind="live_quote", closed_period=True
    )


def test_current_survey_uses_the_recorded_question_date():
    as_of = date(2026, 9, 9)
    policy = build_research_evidence_policy(
        question_kind="company_lookup", question_as_of_date=as_of, current_survey=True
    )
    sources = _sources(as_of)

    assert policy.select_sources(sources) == (sources[2], sources[5])


def test_find_cache_age_does_not_invent_a_same_day_publisher_bound():
    policy = build_research_evidence_policy(question_kind="find_assets")
    source = ResearchSource(
        url="https://publisher.example/company-profile", source_date="2024-01-02"
    )

    assert policy.data_class == "movers"
    assert policy.period_start_date is None
    assert policy.question_as_of_date is None
    assert policy.current_survey is False
    assert policy.select_sources((source,)) == (source,)
