"""Question-aware citation selection for the one research sources drawer."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from argus.domain.research.contracts import ResearchPacket, ResearchSource, RetrievedRow
from argus.domain.research.perplexity_agent import _packet_from_response
from argus.domain.research.source_selection import answer_sources, select_public_sources

GROUNDED_MATH = (
    Path(__file__).resolve().parents[2] / "docs/reports/evidence/grounded-math"
)


def _packet(*sources: ResearchSource) -> ResearchPacket:
    return ResearchPacket(
        answer_markdown="Grounded answer.",
        sources=sources,
        retrieved_at=datetime(2026, 8, 12, 14, 30, tzinfo=timezone.utc),
    )


def test_today_drops_sources_that_cannot_describe_today() -> None:
    packet = _packet(
        ResearchSource(
            url="https://www.cnbc.com/2016/06/16/old-market-story.html",
            title="Old market story",
            source_date="2016-06-16",
        ),
        ResearchSource(
            url="https://www.slickcharts.com/gainers",
            title="Gainers",
            source_date="2026-04-01",
        ),
        ResearchSource(
            url="https://www.nasdaq.com/market-activity/stocks/screener",
            title="Current market activity",
            source_date="2026-08-12",
        ),
        ResearchSource(
            url="https://finance.yahoo.com/markets/stocks/gainers/",
            title="Live gainers",
            source_date=None,
        ),
    )

    selected = select_public_sources(
        packet.sources,
        question_kind="market_pulse",
        period_start=date(2026, 8, 12),
        question_as_of=date(2026, 8, 12),
    )

    assert [source.url for source in selected] == [
        "https://www.nasdaq.com/market-activity/stocks/screener",
        "https://finance.yahoo.com/markets/stocks/gainers/",
    ]


@pytest.mark.parametrize(
    "question_kind",
    ["market_pulse", "screening", "sector_radar"],
)
def test_current_survey_uses_the_question_date_when_classifier_omits_a_period(
    question_kind: str,
) -> None:
    packet = _packet(
        ResearchSource(
            url="https://www.cnbc.com/2026/08/11/yesterdays-movers.html",
            source_date="2026-08-11",
        ),
        ResearchSource(
            url="https://www.reuters.com/markets/us/todays-movers-2026-08-12/",
            source_date="2026-08-12",
        ),
    )

    selected = select_public_sources(
        packet.sources,
        question_kind=question_kind,
        question_as_of=date(2026, 8, 12),
    )

    assert [source.url for source in selected] == [
        "https://www.reuters.com/markets/us/todays-movers-2026-08-12/"
    ]


def test_one_publisher_cannot_crowd_out_distinct_sources() -> None:
    packet = _packet(
        *(
            ResearchSource(
                url=(
                    f"https://finance.yahoo.com/news/story-{index}.html"
                    if index % 2 == 0
                    else f"https://news.yahoo.com/story-{index}.html"
                ),
                title=f"Yahoo story {index}",
            )
            for index in range(5)
        ),
        ResearchSource(url="https://www.reuters.com/markets/story"),
        ResearchSource(url="https://www.nasdaq.com/articles/story"),
        ResearchSource(url="https://www.cnbc.com/markets/story"),
        ResearchSource(url="https://www.morningstar.com/markets/story"),
        ResearchSource(url="https://www.marketwatch.com/story"),
    )

    selected = select_public_sources(packet.sources)

    assert [source.url for source in selected] == [
        "https://finance.yahoo.com/news/story-0.html",
        "https://www.reuters.com/markets/story",
        "https://www.nasdaq.com/articles/story",
        "https://www.cnbc.com/markets/story",
        "https://www.morningstar.com/markets/story",
    ]


def test_malformed_explicit_date_is_not_plausible_for_a_bounded_period() -> None:
    packet = _packet(
        ResearchSource(
            url="https://example.com/ambiguous",
            source_date="June 16, 2016",
        ),
        ResearchSource(url="https://other.example/live", source_date=None),
    )

    selected = select_public_sources(
        packet.sources,
        period_start=date(2026, 8, 12),
        question_as_of=date(2026, 8, 12),
    )

    assert [source.url for source in selected] == ["https://other.example/live"]


def test_the_recorded_credit_card_answer_publishes_only_the_pages_it_cites() -> None:
    """The credit card answer's recorded provider output: every search hit entered
    the pool ahead of the pages the model opened and cited, so selection by
    retrieval order kept hits the answer never used and let one publisher's hit
    stand in for its cited page. The drawer now holds the cited pages, in order."""
    recording = json.loads(
        (GROUNDED_MATH / "probes/q5_credit_card_replay.json").read_text()
    )
    packet = _packet_from_response(
        recording["exchanges"][0]["response"], latency_ms=0, on_unpriced=lambda _: None
    )
    cited = {row.source_url for row in packet.rows}
    before = [source.url for source in select_public_sources(packet.sources)]
    assert [url for url in before if url not in cited]
    assert [source.url for source in select_public_sources(answer_sources(packet))] == [
        "https://www.citi.com/credit-cards/citi-double-cash-credit-card",
        "https://creditcards.chase.com/cash-back-credit-cards/freedom/unlimited",
        "https://www.capitalone.com/credit-cards/venture-x/",
    ]


def test_search_hits_an_answer_never_cites_publish_nothing_it_says() -> None:
    """The saving currency and savings account answers as stored: the first states
    no figure and names no page, so none of its five hits publish; the second
    cites one statistics page, so the deposit insurance hits beside it do not.
    The stored turn kept five pages of its pool, so its cited page is added back
    as retrieved."""
    saving = _stored_packet("q7-en")
    assert saving.sources and answer_sources(saving) == ()
    inflation = _stored_packet("q8-en")
    cited = str(inflation.rows[0].source_url)
    retrieved = inflation.model_copy(
        update={"sources": (*inflation.sources, ResearchSource(url=cited))}
    )
    assert [source.url for source in answer_sources(retrieved)] == [cited]


def test_an_answer_names_its_pages_and_only_retrieved_ones_publish() -> None:
    retrieved = (
        ResearchSource(url="https://www.reuters.com/markets/rates/"),
        ResearchSource(url="https://www.bls.gov/cpi.htm"),
        ResearchSource(url="https://hits.example/unrelated"),
    )
    packet = ResearchPacket(
        answer_markdown="Rates and prices.",
        typed_answer=True,
        sources=retrieved,
        source_urls=("https://bls.gov/cpi.htm#table", "https://invented.example/page"),
        rows=(
            RetrievedRow(
                subject="United States",
                symbol=None,
                label="policy rate",
                value=4.25,
                kind="percent",
                unit="%",
                as_of="2026-09-01",
                source_url="https://reuters.com/markets/rates",
            ),
        ),
    )
    assert [source.url for source in answer_sources(packet)] == [
        "https://www.bls.gov/cpi.htm",
        "https://www.reuters.com/markets/rates/",
    ]
    assert answer_sources(packet.model_copy(update={"typed_answer": False})) == retrieved


def _stored_packet(label: str) -> ResearchPacket:
    turn = json.loads((GROUNDED_MATH / f"turns/{label}.json").read_text())["turns"][0]
    research = turn["metadata"]["research"]
    return ResearchPacket(
        answer_markdown=str(turn.get("content") or "stored answer"),
        typed_answer=True,
        sources=tuple(
            ResearchSource(
                url=source["url"],
                title=source.get("title") or "",
                source_date=source.get("source_date"),
            )
            for source in research["sources"]
        ),
        rows=tuple(RetrievedRow.model_validate(row) for row in research["rows"]),
    )
