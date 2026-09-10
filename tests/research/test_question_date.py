"""A research question is dated by the New York calendar (#579).

The question date bounds which dated pages can describe a question: it is a
current survey's freshness lower bound and the upper bound of every bounded
period. Read in UTC, a survey asked after 20:00 ET was already dated the next
day and dropped every page from the day it asked about.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.state.models import UserState
from argus.domain.research.contracts import ResearchSource
from argus.domain.research.perplexity_agent import _packet_from_response
from argus.domain.research.source_selection import (
    question_date,
    select_public_sources,
)

from tests.research.conftest import (
    PUBLISHER,
    RESEARCH_USER_ID,
    agent_response,
    educational_interpretation,
    retrieved_row,
    run_research_turn,
    search_results_item,
    set_research_query,
    typed_answer_text,
    wire_grounded_client,
)

# 20:17 in New York on 2026-09-09, the evening the recorded S&P turn was asked
# (docs/reports/evidence/open-the-gates/after/argus-spx-week.json).
AFTER_THE_CLOSE = datetime(2026, 9, 10, 0, 17, tzinfo=timezone.utc)
ASKED_ON = date(2026, 9, 9)
DAY_BEFORE = "https://www.cnbc.com/2026/09/08/stock-market-today-dow-sp-500.html"
SAME_DAY = (
    "https://lasvegassun.com/news/2026/sep/09/"
    "how-major-us-stock-indexes-fared-wednesday-992026/"
)
BEFORE_THE_PERIOD = "https://www.cnbc.com/2026/09/04/nvidia-stock-last-week.html"
UTC_STAMPED = "https://www.marketwatch.com/story/stocks-after-the-bell-2026-09-10"
TWO_DAYS_AHEAD = "https://www.reuters.com/markets/us/stocks-2026-09-11/"


@pytest.mark.parametrize(
    ("asked_at", "asked_on"),
    [
        (AFTER_THE_CLOSE, ASKED_ON),
        (datetime(2026, 9, 10, 3, 59, tzinfo=timezone.utc), date(2026, 9, 9)),
        (datetime(2026, 9, 10, 4, 0, tzinfo=timezone.utc), date(2026, 9, 10)),
        (datetime(2026, 1, 15, 4, 59, tzinfo=timezone.utc), date(2026, 1, 14)),
        (datetime(2026, 1, 15, 5, 0, tzinfo=timezone.utc), date(2026, 1, 15)),
    ],
    ids=[
        "daylight-evening",
        "daylight-last-minute",
        "daylight-midnight",
        "standard-last-minute",
        "standard-midnight",
    ],
)
def test_a_question_is_dated_by_the_new_york_calendar(
    freeze_new_york_clock, asked_at: datetime, asked_on: date
) -> None:
    """The date turns at midnight in New York, in daylight and standard time
    alike, never at midnight UTC."""
    freeze_new_york_clock(asked_at)

    assert question_date() == asked_on


def test_a_survey_asked_after_the_close_keeps_the_pages_of_the_day_it_asked_about(
    monkeypatch, freeze_new_york_clock
) -> None:
    """The recorded S&P turn, asked at 00:17 UTC: its rows cited a page dated
    that New York day and the drawer was empty, because the freshness bound
    had already moved to the next UTC date."""
    freeze_new_york_clock(AFTER_THE_CLOSE)
    set_research_query(
        monkeypatch, globals(), question_kind="market_pulse", symbols=["SPY"]
    )
    document = agent_response(
        text=typed_answer_text(
            "The S&P 500 is down **1.1%** this week; SPY last traded at **$762.40**.",
            [
                retrieved_row(
                    subject="S&P 500",
                    symbol="SPY",
                    label="week-to-date change",
                    value=-1.1,
                    as_of="2026-09-09",
                    source_url=SAME_DAY,
                )
            ],
        ),
        tickers=["SPY"],
        web_search_invocations=1,
    )
    document["output"].insert(
        1,
        search_results_item(
            {"url": DAY_BEFORE, "title": "Stock market today", "date": "2026-09-08"},
            {"url": SAME_DAY, "title": "How major indexes fared", "date": "2026-09-09"},
        ),
    )
    wire_grounded_client(monkeypatch, [document])

    result = run_research_turn("how much did the S&P 500 move this week?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert [source["url"] for source in sidecar["sources"]] == [SAME_DAY]


@pytest.mark.parametrize(
    ("question_kind", "period_start"),
    [("market_pulse", None), ("current_external", date(2026, 9, 7))],
    ids=["survey-freshness", "explicit-period"],
)
def test_a_page_dated_one_day_past_the_question_is_kept_and_two_days_is_not(
    question_kind: str, period_start: date | None
) -> None:
    """Kept, by decision. A publisher that stamps pages in UTC dates a page
    written this New York evening tomorrow, and no clock is a full day ahead
    of New York, so one date past the question date is a real page and two
    dates past is not."""
    selected = select_public_sources(
        [
            ResearchSource(url=UTC_STAMPED, source_date="2026-09-10"),
            ResearchSource(url=TWO_DAYS_AHEAD, source_date="2026-09-11"),
        ],
        question_kind=question_kind,
        period_start=period_start,
        question_as_of=ASKED_ON,
    )

    assert [source.url for source in selected] == [UTC_STAMPED]


def test_inline_and_background_research_date_the_question_alike(
    monkeypatch, freeze_new_york_clock
) -> None:
    """One owner dates the question on both paths: at the same instant the
    inline turn and the background job keep the same pages of the same
    packet, and the job carries the date it was asked on to its completion."""
    freeze_new_york_clock(AFTER_THE_CLOSE)
    period_start = date(2026, 9, 7)
    set_research_query(
        monkeypatch,
        globals(),
        question_kind="current_external",
        symbols=["NVDA"],
        period_of_interest="this week",
        period_start_date=period_start,
    )
    document = agent_response(
        text=typed_answer_text(
            "NVIDIA fell **4.3%** this week.",
            [retrieved_row(as_of="2026-09-09", source_url=PUBLISHER)],
        ),
        tickers=["NVDA"],
        web_search_invocations=1,
    )
    document["output"].insert(
        1,
        search_results_item(
            {"url": BEFORE_THE_PERIOD, "title": "Last week", "date": "2026-09-04"},
            {"url": PUBLISHER, "title": "Nvidia stock falls", "date": "2026-09-09"},
            {"url": UTC_STAMPED, "title": "After the bell", "date": "2026-09-10"},
            {"url": TWO_DAYS_AHEAD, "title": "Stocks", "date": "2026-09-11"},
        ),
    )
    wire_grounded_client(monkeypatch, [document])

    inline = run_research_turn("why is NVIDIA stock moving this week?")
    job = grounded.thorough_job_result(
        query=ResearchQueryExtraction(
            question_kind="cross_company",
            symbols=["NVDA"],
            period_of_interest="this week",
            period_start_date=period_start,
        ),
        subjects=[{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}],
        interpretation=educational_interpretation(),
        user=UserState(user_id=RESEARCH_USER_ID, language_preference="en"),
        message="why is NVIDIA stock moving this week?",
    )
    request = job.stage_patch["research_job_request"]
    completed = grounded.compose_completed_research(
        job_request=request,
        packet=_packet_from_response(document, latency_ms=1, on_unpriced=lambda _: None),
    )

    assert inline is not None
    assert request["question_as_of_date"] == ASKED_ON.isoformat()
    kept = [PUBLISHER, UTC_STAMPED]
    assert [s["url"] for s in inline.stage_patch["research"]["sources"]] == kept
    assert [s["url"] for s in completed["research"]["sources"]] == kept
