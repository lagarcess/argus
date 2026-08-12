"""Question-aware citation selection for the one research sources drawer."""

from __future__ import annotations

from datetime import date, datetime, timezone

from argus.domain.research.contracts import ResearchPacket, ResearchSource
from argus.domain.research.source_selection import select_public_sources


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


def test_market_pulse_uses_the_question_date_when_the_classifier_omits_a_period() -> None:
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
        question_kind="market_pulse",
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
